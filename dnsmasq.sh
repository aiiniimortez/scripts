#!/usr/bin/env bash
set -e

echo "[1/7] Install dnsmasq ..."
apt-get update -y >/dev/null
apt-get install dnsmasq -y >/dev/null

echo "[2/7] Stop systemd-resolved DNS stub listener (optional) ..."
sed -i 's/^#*DNSStubListener=.*/DNSStubListener=no/' /etc/systemd/resolved.conf || true
systemctl restart systemd-resolved || true

echo "[3/7] Configure dnsmasq ..."
DC_DNS=$(ip route | awk '/default/ {print $3; exit}')

cat >/etc/dnsmasq.d/custom.conf <<EOF
no-resolv
server=9.9.9.9
server=8.8.8.8
server=$DC_DNS
server=1.1.1.1

cache-size=10000
min-cache-ttl=3600
max-cache-ttl=86400
EOF

echo "[4/7] Restart dnsmasq ..."
systemctl enable dnsmasq
systemctl restart dnsmasq

echo "[5/7] Unlock resolv.conf if locked ..."
chattr -i /etc/resolv.conf 2>/dev/null || true

echo "[6/7] Point resolv.conf to local dnsmasq ..."
cat >/etc/resolv.conf <<EOF
nameserver 127.0.0.1
options timeout:1 attempts:2 rotate
EOF

echo "[7/7] Lock resolv.conf ..."
chattr +i /etc/resolv.conf

echo "Done ✅"
echo "Test cache with: resolvectl statistics  OR  dig google.com"
