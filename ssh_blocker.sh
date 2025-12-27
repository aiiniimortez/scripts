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
