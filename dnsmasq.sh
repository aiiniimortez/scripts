#!/usr/bin/env bash
set -e

echo "[1/8] Install dnsmasq ..."
apt-get update -y >/dev/null
apt-get install dnsmasq -y >/dev/null

echo "[2/8] Clean old dnsmasq configs ..."
rm -f /etc/dnsmasq.d/*.save /etc/dnsmasq.d/*.bak 2>/dev/null || true

echo "[3/8] Configure dnsmasq on port 53 ..."
cat >/etc/dnsmasq.d/custom.conf <<EOF
port=53
listen-address=127.0.0.1
bind-interfaces

no-resolv
server=9.9.9.9
server=8.8.8.8
server=80.191.40.136
server=80.191.40.146
server=185.206.92.250
server=46.245.69.110
server=5.145.115.33

cache-size=10000
min-cache-ttl=600
max-cache-ttl=600
EOF

echo "[4/8] Restart dnsmasq ..."
systemctl enable dnsmasq
systemctl restart dnsmasq

echo "[5/8] Verify dnsmasq is listening on 53 ..."
ss -lntup | grep 53 || { echo "dnsmasq not listening!"; exit 1; }

echo "[6/8] Unlock resolv.conf if locked ..."
chattr -i /etc/resolv.conf 2>/dev/null || true

echo "[7/8] Point resolv.conf to dnsmasq ..."
cat >/etc/resolv.conf <<EOF
nameserver 127.0.0.1
options timeout:1 attempts:2 rotate
EOF

echo "[8/8] Lock resolv.conf ..."
chattr +i /etc/resolv.conf

echo "Done ✅"
echo "Test with:"
echo "  dig google.com"
echo "  dig google.com"
