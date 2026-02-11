#!/usr/bin/env bash
set -e

echo "[1/5] Fix IPv4 precedence ..."
grep -q "^precedence ::ffff:0:0/96  100" /etc/gai.conf && \
sed -i "s/^#precedence ::ffff:0:0\/96  100/precedence ::ffff:0:0\/96  100/" /etc/gai.conf || \
echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf

echo "[2/5] Detecting datacenter DNS (gateway) ..."
DC_DNS=$(ip route | awk '/default/ {print $3; exit}')
echo "Datacenter DNS detected: $DC_DNS"

echo "[3/5] Writing /etc/resolv.conf ..."
cat >/etc/resolv.conf <<EOF
nameserver 9.9.9.9
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver $DC_DNS
options timeout:1 attempts:2 rotate
EOF

echo "[4/5] Disabling DNSSEC in systemd-resolved ..."
mkdir -p /etc/systemd
cat >/etc/systemd/resolved.conf <<EOF
[Resolve]
DNSSEC=no
EOF

echo "[5/5] Restarting systemd-resolved ..."
systemctl restart systemd-resolved || true

echo "Done. Test with: dig google.com"
