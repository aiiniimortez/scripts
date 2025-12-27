#!/bin/bash

set -e

PY_SCRIPT_URL="https://raw.githubusercontent.com/aiiniimortez/scripts/refs/heads/main/ssh_blocker.py"
PY_SCRIPT_NAME="ssh_blocker.py"

echo "== SSH Blocker Launcher =="

# -------------------------
# 1) Check root for block mode later
# -------------------------
if [[ $EUID -ne 0 ]]; then
  echo "[i] Not running as root. You can still use analysis mode."
fi

# -------------------------
# 2) Install prerequisites
# -------------------------
echo "[+] Checking prerequisites..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "[+] Installing python3..."
  sudo apt update
  sudo apt install -y python3
fi

if ! dpkg -s iptables-persistent >/dev/null 2>&1; then
  echo "[+] Installing iptables-persistent..."
  sudo apt update
  sudo apt install -y iptables-persistent
fi

# -------------------------
# 3) Download python script
# -------------------------
echo "[+] Downloading ssh_blocker.py ..."
curl -fsSL "$PY_SCRIPT_URL" -o "$PY_SCRIPT_NAME"
chmod +x "$PY_SCRIPT_NAME"

# -------------------------
# 4) Ask user for mode
# -------------------------
echo
echo "Select mode:"
echo "  1) Analysis (report only)"
echo "  2) Block (apply iptables rules)  [requires sudo]"
read -rp "Enter choice [1/2]: " choice

MODE=""
case "$choice" in
  1)
    MODE="--analysis"
    ;;
  2)
    MODE="--block"
    ;;
  *)
    echo "Invalid choice. Exiting."
    exit 1
    ;;
esac

# -------------------------
# 5) Run python script with selected mode
# -------------------------
echo
echo "[+] Running ssh_blocker.py $MODE"
if [[ "$MODE" == "--block" ]]; then
  # ensure root
  if [[ $EUID -ne 0 ]]; then
    echo "[!] Block mode needs sudo. Re-running with sudo..."
    sudo ./"$PY_SCRIPT_NAME" "$MODE"
  else
    ./"$PY_SCRIPT_NAME" "$MODE"
  fi
else
  ./"$PY_SCRIPT_NAME" "$MODE"
fi

echo
echo "[✓] Done."
