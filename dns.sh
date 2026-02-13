#!/usr/bin/env bash
set -e

echo "[1/6] Fix IPv4 precedence in /etc/gai.conf ..."
grep -q "^precedence ::ffff:0:0/96  100" /etc/gai.conf && \
sed -i "s/^#precedence ::ffff:0:0\/96  100/precedence ::ffff:0:0\/96  100/" /etc/gai.conf || \
echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf

echo "[2/6] Detect datacenter DNS (gateway) ..."
DC_DNS=$(ip route | awk '/default/ {print $3; exit}')
echo "Datacenter DNS: $DC_DNS"

echo "[3/6] Remove systemd stub resolv.conf ..."
chattr -i /etc/resolv.conf
rm -f /etc/resolv.conf

echo "[4/6] Write real /etc/resolv.conf ..."
cat >/etc/resolv.conf <<EOF
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver 9.9.9.9
nameserver 80.191.40.136
nameserver 80.191.40.146
nameserver 185.206.92.250
nameserver 46.245.69.110
nameserver 5.145.115.33
options timeout:1 attempts:1 rotate
EOF

echo "[5/6] Lock resolv.conf (immutable) ..."
chattr +i /etc/resolv.conf

echo "[6/6] Disable DNSSEC in systemd-resolved and restart ..."
sed -i 's/^#*DNSSEC=.*/DNSSEC=no/' /etc/systemd/resolved.conf
systemctl restart systemd-resolved || true

echo "Done ✅"
dig time.ir
