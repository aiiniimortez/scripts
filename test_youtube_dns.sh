#!/usr/bin/env bash

DOMAIN="${1:-time.ir}"
URL="https://raw.githubusercontent.com/aiiniimortez/scripts/refs/heads/main/working-dns-youtube.txt"
TMP_FILE="/tmp/dns_list.txt"

echo "Target domain: $DOMAIN"
echo "[1/4] Downloading DNS list..."
curl -fsSL "$URL" -o "$TMP_FILE"

echo "[2/4] Testing DNS servers..."
echo "Please wait..."

RESULTS=()

while read -r DNS; do
    [[ -z "$DNS" ]] && continue

    TIME=$(dig "$DOMAIN" @"$DNS" +tries=1 +time=2 +nocookie +norecurse 2>/dev/null \
        | awk '/Query time:/ {print $4}')

    if [[ "$TIME" =~ ^[0-9]+$ ]]; then
        echo "OK   $DNS   ${TIME}ms"
        RESULTS+=("$TIME $DNS")
    else
        echo "FAIL $DNS"
    fi

done < "$TMP_FILE"

echo
echo "[3/4] Sorting best DNS servers..."

printf "%s\n" "${RESULTS[@]}" | sort -n | head -n 10 > /tmp/best_dns.txt

echo
echo "[4/4] Top 10 fastest DNS for $DOMAIN:"
echo "--------------------------------------"
awk '{printf "%-16s %s ms\n", $2, $1}' /tmp/best_dns.txt
