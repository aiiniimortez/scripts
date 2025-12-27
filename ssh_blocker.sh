#!/bin/bash
set -e

PY_SCRIPT_URL="https://raw.githubusercontent.com/aiiniimortez/scripts/refs/heads/main/ssh_blocker.py"
PY_SCRIPT_NAME="ssh_blocker.py"

echo "== SSH Security Toolkit =="

# -------------------------
# 1) Install prerequisites
# -------------------------
echo "[+] Checking prerequisites..."

need_install=()

command -v python3 >/dev/null 2>&1 || need_install+=(python3)
command -v pip3   >/dev/null 2>&1 || need_install+=(python3-pip)
dpkg -s iptables-persistent >/dev/null 2>&1 || need_install+=(iptables-persistent)
dpkg -s python3-requests >/dev/null 2>&1 || need_install+=(python3-requests)
dpkg -s python3-tqdm     >/dev/null 2>&1 || need_install+=(python3-tqdm)
dpkg -s python3-geoip2   >/dev/null 2>&1 || need_install+=(python3-geoip2)

if [ ${#need_install[@]} -ne 0 ]; then
    echo "[+] Installing missing packages: ${need_install[*]}"
    sudo apt update
    sudo apt install -y "${need_install[@]}"
else
    echo "[✓] All prerequisites already installed."
fi

clear

# -------------------------
# Menu
# -------------------------
echo
echo "Select option:"
echo "  1) SSH Attack Analysis (report only)"
echo "  2) Block attackers (iptables)"
echo "  3) Change SSH Port (hardening)"
read -rp "Enter choice [1/2/3]: " choice

# -------------------------
# Option 3: Change SSH Port
# -------------------------
if [[ "$choice" == "3" ]]; then
  echo

  CUR_PORT=$(ss -tnlp | grep sshd | awk '{print $4}' | sed 's/.*://' | sort -u)
  echo "Current SSH Port(s): $CUR_PORT"

  read -rp "Enter new SSH port (1024-65535): " NEWPORT

  if ! [[ "$NEWPORT" =~ ^[0-9]+$ ]] || (( NEWPORT < 1024 || NEWPORT > 65535 )); then
    echo "Invalid port."
    exit 1
  fi


  echo "[+] Writing new SSH port override..."
    SSHD_MAIN="/etc/ssh/sshd_config"
    
    sudo cp "$SSHD_MAIN" "${SSHD_MAIN}.bak.$(date +%F_%T)"
    
    if grep -q "^#\?Port" "$SSHD_MAIN"; then
        sudo sed -i "s/^#\?Port.*/Port $NEWPORT/" "$SSHD_MAIN"
    else
        echo "Port $NEWPORT" | sudo tee -a "$SSHD_MAIN"
    fi

  echo "[+] Opening firewall for new port..."
  sudo iptables -I INPUT -p tcp --dport "$NEWPORT" -j ACCEPT

  echo "[+] Testing sshd configuration..."
  if ! sudo sshd -t; then
      echo "[!] sshd config test FAILED. Rolling back..."
      sudo rm -f "$CUSTOM_CONF"
      sudo systemctl restart ssh
      sudo iptables -D INPUT -p tcp --dport "$NEWPORT" -j ACCEPT
      exit 1
  fi

  echo "[+] Restarting SSH..."
  sudo systemctl restart ssh
  sleep 2

  if ! ss -tnlp | grep sshd | grep -q ":$NEWPORT"; then
      echo "[!] New port did NOT come up. Rolling back..."
      sudo rm -f "$CUSTOM_CONF"
      sudo systemctl restart ssh
      sudo iptables -D INPUT -p tcp --dport "$NEWPORT" -j ACCEPT
      exit 1
  fi

  # ---------- Ask before closing old ports ----------
echo
read -rp "Do you want to CLOSE old SSH port(s): $CUR_PORT ? (y/N): " close_ans
if [[ "$close_ans" == "y" ]]; then
    for p in $CUR_PORT; do
        if [[ "$p" != "$NEWPORT" ]]; then
            sudo iptables -I INPUT -p tcp --dport "$p" -j DROP
            echo "Closed old port $p"
        else
            echo "Skipping $p (same as new port)"
        fi
    done
    echo "Old SSH port(s) processed."
else
    echo "Old SSH port(s) left open."
fi

  sudo netfilter-persistent save

  echo
  echo "✅ SSH port successfully changed to $NEWPORT"
  exit 0
fi

# -------------------------
# Option 1/2 (run python tool)
# -------------------------
echo "[+] Downloading ssh_blocker.py ..."
curl -fsSL "$PY_SCRIPT_URL" -o "$PY_SCRIPT_NAME"
chmod +x "$PY_SCRIPT_NAME"

MODE=""
if [[ "$choice" == "1" ]]; then MODE="--analysis"; fi
if [[ "$choice" == "2" ]]; then MODE="--block"; fi

if [[ -z "$MODE" ]]; then
  echo "Invalid choice."
  exit 1
fi

if [[ "$MODE" == "--block" && $EUID -ne 0 ]]; then
  sudo ./"$PY_SCRIPT_NAME" "$MODE"
else
  ./"$PY_SCRIPT_NAME" "$MODE"
fi
#!/bin/bash
set -e

PY_SCRIPT_URL="https://raw.githubusercontent.com/aiiniimortez/scripts/refs/heads/main/ssh_blocker.py"
PY_SCRIPT_NAME="ssh_blocker.py"

echo "== SSH Security Toolkit =="

# -------------------------
# 1) Install prerequisites
# -------------------------
echo "[+] Checking prerequisites..."

if ! command -v python3 >/dev/null 2>&1; then
  sudo apt update
  sudo apt install -y python3
fi

if ! dpkg -s iptables-persistent >/dev/null 2>&1; then
  sudo apt update
  sudo apt install -y iptables-persistent
fi

# -------------------------
# Menu
# -------------------------
echo
echo "Select option:"
echo "  1) SSH Attack Analysis (report only)"
echo "  2) Block attackers (iptables)"
echo "  3) Change SSH Port (hardening)"
read -rp "Enter choice [1/2/3]: " choice

# -------------------------
# Option 3: Change SSH Port
# -------------------------
if [[ "$choice" == "3" ]]; then
  echo
  CUR_PORT=$(ss -tnlp | grep sshd | awk '{print $4}' | sed 's/.*://')
  echo "Current SSH Port: $CUR_PORT"
  read -rp "Enter new SSH port (1024-65535): " NEWPORT

  if ! [[ "$NEWPORT" =~ ^[0-9]+$ ]] || (( NEWPORT < 1024 || NEWPORT > 65535 )); then
    echo "Invalid port."
    exit 1
  fi

  SSHD_CONF="/etc/ssh/sshd_config"

  sudo cp $SSHD_CONF ${SSHD_CONF}.bak.$(date +%F_%T)

  if grep -q "^#\?Port" $SSHD_CONF; then
    sudo sed -i "s/^#\?Port.*/Port $NEWPORT/" $SSHD_CONF
  else
    echo "Port $NEWPORT" | sudo tee -a $SSHD_CONF
  fi

  sudo systemctl restart ssh
  echo "SSH port changed to $NEWPORT"
  exit 0
fi

# -------------------------
# Option 1/2 (run python tool)
# -------------------------
echo "[+] Downloading ssh_blocker.py ..."
curl -fsSL "$PY_SCRIPT_URL" -o "$PY_SCRIPT_NAME"
chmod +x "$PY_SCRIPT_NAME"

MODE=""
if [[ "$choice" == "1" ]]; then MODE="--analysis"; fi
if [[ "$choice" == "2" ]]; then MODE="--block"; fi

if [[ -z "$MODE" ]]; then
  echo "Invalid choice."
  exit 1
fi

if [[ "$MODE" == "--block" && $EUID -ne 0 ]]; then
  sudo ./"$PY_SCRIPT_NAME" "$MODE"
else
  ./"$PY_SCRIPT_NAME" "$MODE"
fi
