#!/usr/bin/env bash
set -uo pipefail

DNS_SERVERS=("8.8.8.8" "1.1.1.1" "127.0.0.53")

DOMAINS=(
  "www.gstatic.com"
  "cdn.instagram.com"
  "instagram.com"
  "google.com"
  "youtube.com"
)

TRIALS=10
DIG_TIMEOUT=2
PING_TIMEOUT=1
RESOLV_CONF="/etc/resolv.conf"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1" >&2
    exit 1
  }
}

need_cmd dig
need_cmd ping
need_cmd awk
need_cmd sort
need_cmd tee

add_float() {
  awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { printf "%.3f", a + b }'
}

avg_float() {
  local sum="${1:-0}"
  local count="${2:-0}"
  awk -v s="$sum" -v c="$count" 'BEGIN {
    if (c > 0) printf "%.1f", s / c;
    else printf "n/a";
  }'
}

measure_cell() {
  local dns="$1"
  local domain="$2"

  local i out qt ip soa_host ptime
  local qt_sum=0
  local qt_count=0
  local ping_sum=0
  local ping_count=0
  local total_sum=0
  local total_count=0

  for ((i = 0; i < TRIALS; i++)); do
    out=$(dig @"$dns" "$domain" A +tries=1 +time="$DIG_TIMEOUT" 2>/dev/null || true)

    qt=$(awk '/Query time:/ {print $(NF-1); exit}' <<<"$out")
    ip=$(awk '$4 == "A" {print $5; exit}' <<<"$out")

    if [[ -n "${qt:-}" && "$qt" =~ ^[0-9]+$ ]]; then
      qt_sum=$((qt_sum + qt))
      qt_count=$((qt_count + 1))
    fi

    if [[ -z "${ip:-}" ]]; then
      soa_host=$(awk '$4 == "SOA" {print $5; exit}' <<<"$out")
      if [[ -n "${soa_host:-}" ]]; then
        ip=$(dig +short -4 A "$soa_host" 2>/dev/null | head -n1 || true)
      fi
    fi

    if [[ -n "${ip:-}" ]]; then
      ptime=$(
        ping -4 -n -c 1 -W "$PING_TIMEOUT" "$ip" 2>/dev/null \
          | awk -F'time=' '/time=/{split($2,a," "); print a[1]; exit}'
      )

      if [[ -n "${ptime:-}" ]]; then
        ping_sum=$(add_float "$ping_sum" "$ptime")
        ping_count=$((ping_count + 1))

        if [[ -n "${qt:-}" && "$qt" =~ ^[0-9]+$ ]]; then
          total_sum=$(add_float "$total_sum" "$(awk -v q="$qt" -v p="$ptime" 'BEGIN { printf "%.3f", q + p }')")
          total_count=$((total_count + 1))
        fi
      fi
    fi
  done

  local qt_avg ping_avg total_avg
  qt_avg=$(avg_float "$qt_sum" "$qt_count")
  ping_avg=$(avg_float "$ping_sum" "$ping_count")
  total_avg=$(avg_float "$total_sum" "$total_count")

  printf "%s|%s|%s\n" "$qt_avg" "$ping_avg" "$total_avg"
}

repeat_char() {
  local ch="$1"
  local count="$2"
  printf '%*s' "$count" '' | tr ' ' "$ch"
}

print_border() {
  local dns_w="$1"
  local cell_w="$2"
  local cols="$3"
  local border="+"

  border+="$(repeat_char '-' $((dns_w + 2)))+"
  for ((i = 0; i < cols; i++)); do
    border+="$(repeat_char '-' $((cell_w + 2)))+"
  done

  printf '%s\n' "$border"
}

print_row() {
  local dns_w="$1"
  local cell_w="$2"
  shift 2

  printf "| %-*s " "$dns_w" "$1"
  shift

  local cell
  for cell in "$@"; do
    printf "| %-*s " "$cell_w" "$cell"
  done
  printf "|\n"
}

declare -A CELL
declare -A ROWAVG

echo "Measuring DNS latency..."

for dns in "${DNS_SERVERS[@]}"; do
  for domain in "${DOMAINS[@]}"; do
    CELL["$dns|$domain"]="$(measure_cell "$dns" "$domain")"
  done

  row_q_sum=0
  row_q_count=0
  row_p_sum=0
  row_p_count=0
  row_t_sum=0
  row_t_count=0

  for domain in "${DOMAINS[@]}"; do
    IFS='|' read -r q p t <<<"${CELL["$dns|$domain"]}"

    if [[ "$q" != "n/a" ]]; then
      row_q_sum=$(add_float "$row_q_sum" "$q")
      row_q_count=$((row_q_count + 1))
    fi

    if [[ "$p" != "n/a" ]]; then
      row_p_sum=$(add_float "$row_p_sum" "$p")
      row_p_count=$((row_p_count + 1))
    fi

    if [[ "$t" != "n/a" ]]; then
      row_t_sum=$(add_float "$row_t_sum" "$t")
      row_t_count=$((row_t_count + 1))
    fi
  done

  ROWAVG["$dns"]="$(avg_float "$row_q_sum" "$row_q_count")|$(avg_float "$row_p_sum" "$row_p_count")|$(avg_float "$row_t_sum" "$row_t_count")"
done

sorted_dns=()
mapfile -t sorted_lines < <(
  for idx in "${!DNS_SERVERS[@]}"; do
    dns="${DNS_SERVERS[$idx]}"
    IFS='|' read -r _ _ total_avg <<<"${ROWAVG["$dns"]}"
    if [[ "$total_avg" == "n/a" ]]; then
      key="999999"
    else
      key="$total_avg"
    fi
    printf "%s\t%03d\t%s\n" "$key" "$idx" "$dns"
  done | sort -n -k1,1 -k2,2
)

for line in "${sorted_lines[@]}"; do
  IFS=$'\t' read -r _ _ dns <<<"$line"
  sorted_dns+=("$dns")
done

dns_w=15
cell_w=28
cols=$(( ${#DOMAINS[@]} + 1 ))

print_border "$dns_w" "$cell_w" "$cols"
print_row "$dns_w" "$cell_w" "DNS" "${DOMAINS[@]}" "Average"
print_border "$dns_w" "$cell_w" "$cols"

for dns in "${sorted_dns[@]}"; do
  row=("$dns")
  for domain in "${DOMAINS[@]}"; do
    row+=("${CELL["$dns|$domain"]}")
  done
  row+=("${ROWAVG["$dns"]}")
  print_row "$dns_w" "$cell_w" "${row[@]}"
done

print_border "$dns_w" "$cell_w" "$cols"

echo
echo "Final DNS order:"
for dns in "${sorted_dns[@]}"; do
  echo "  $dns"
done

if [[ $EUID -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
  else
    echo "Run this script as root or install sudo." >&2
    exit 1
  fi
else
  SUDO=()
fi

backup="${RESOLV_CONF}.bak.$(date +%Y%m%d-%H%M%S)"
"${SUDO[@]}" cp -L "$RESOLV_CONF" "$backup"

{
  for dns in "${sorted_dns[@]}"; do
    printf "nameserver %s\n" "$dns"
  done
} | "${SUDO[@]}" tee "$RESOLV_CONF" >/dev/null

echo
echo "Saved to: $RESOLV_CONF"
echo "Backup:    $backup"
