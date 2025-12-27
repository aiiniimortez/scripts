#!/usr/bin/env python3
import os, subprocess, sys, re, ipaddress
from collections import Counter

# ----------------- Dependencies -----------------
try:
    from tqdm import tqdm
    import requests
    import geoip2.database
except:
    subprocess.run("pip3 install tqdm requests geoip2", shell=True)
    from tqdm import tqdm
    import requests
    import geoip2.database

GEOLITE_COUNTRY_PATH = "GeoLite2-Country.mmdb"
GEOLITE_ASN_PATH = "GeoLite2-ASN.mmdb"

# ----------------- GeoIP Setup -----------------
def download(url, fname):
    if os.path.isfile(fname):
        os.remove(fname)
    r = requests.get(url, stream=True)
    total = int(r.headers.get('content-length', 0))
    with open(fname, 'wb') as f, tqdm(total=total, desc=fname, unit='iB', unit_scale=True, unit_divisor=1024) as bar:
        for c in r.iter_content(1024):
            bar.update(f.write(c))

def setup_geo():
    if not os.path.isfile(GEOLITE_COUNTRY_PATH):
        download("https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb", GEOLITE_COUNTRY_PATH)
    if not os.path.isfile(GEOLITE_ASN_PATH):
        download("https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-ASN.mmdb", GEOLITE_ASN_PATH)

country_reader = None
asn_reader = None

def load_readers():
    global country_reader, asn_reader
    country_reader = geoip2.database.Reader(GEOLITE_COUNTRY_PATH)
    asn_reader = geoip2.database.Reader(GEOLITE_ASN_PATH)

def find_country(ip):
    try:
        return country_reader.country(ip).country.name
    except:
        return "Unknown"

def find_country_code(ip):
    try:
        return country_reader.country(ip).country.iso_code
    except:
        return "XX"

def find_asn(ip):
    try:
        return asn_reader.asn(ip).autonomous_system_organization
    except:
        return "Unknown"

# ----------------- Print Table -----------------
class PrintTable:
    def __init__(self, headers, lengths):
        self.headers = headers
        self.lengths = lengths
        self.ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

    def print_headers(self):
        sum_length = sum(self.lengths) + 3 * len(self.lengths) + 1
        print("-" * sum_length)
        header = "| "
        for h, l in zip(self.headers, self.lengths):
            header += self.truncate_and_pad(h, l) + " | "
        print(header.strip())
        print("-" * sum_length)

    def truncate_and_pad(self, string, length):
        string = str(string) or ""
        clean = self.ansi_escape.sub("", string)
        if len(clean) > length:
            visible = clean[:length - 3] + "..."
        else:
            visible = clean
        padding = " " * (length - len(visible))
        return visible + padding

    def print_row(self, data):
        row = "| "
        for d, l in zip(data, self.lengths):
            row += self.truncate_and_pad(d, l) + " | "
        print(row.strip())

    def print_last_row(self):
        sum_length = sum(self.lengths) + 3 * len(self.lengths) + 1
        print("-" * sum_length)

# ----------------- Core Helpers -----------------
def get_lastb_ips():
    raw = subprocess.getoutput("lastb -w | awk '{print $3}' | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}'")
    return Counter(raw.splitlines())

def load_blocked_networks():
    raw = subprocess.getoutput("iptables -L INPUT -n | grep DROP")
    nets = set()
    for line in raw.splitlines():
        for p in line.split():
            if "/" in p and "." in p:
                try:
                    nets.add(ipaddress.ip_network(p, strict=False))
                except:
                    pass
    return nets

# ----------------- Main -----------------
def main():
    if len(sys.argv) == 1:
        print("Use --analysis or --block")
        return

    setup_geo()
    load_readers()

    ip_stats = get_lastb_ips()
    blocked_nets = load_blocked_networks()

    enriched = {}
    for ip, cnt in ip_stats.items():
        status = "open"
        ip_obj = ipaddress.ip_address(ip)
        for net in blocked_nets:
            if ip_obj in net:
                status = "blocked by iptables"
                break

        enriched[ip] = {
            "attempts": cnt,
            "country": find_country(ip),
            "cc": find_country_code(ip),
            "asn": find_asn(ip),
            "status": status
        }

    # -------- ANALYSIS MODE --------
    if "--analysis" in sys.argv:
        headers = ["IP", "Attempts", "Country", "ASN", "Status"]
        lengths = [18, 8, 18, 50, 22]
        t = PrintTable(headers, lengths)
        t.print_headers()

        open_rows = []
        blocked_rows = []
        for ip, v in enriched.items():
            if v["status"] == "open":
                open_rows.append((ip, v))
            else:
                blocked_rows.append((ip, v))

        for ip, v in sorted(open_rows, key=lambda x: x[1]["attempts"], reverse=True):
            t.print_row([ip, v["attempts"], v["country"], v["asn"], v["status"]])

        for ip, v in sorted(blocked_rows, key=lambda x: x[1]["attempts"], reverse=True):
            t.print_row([ip, v["attempts"], v["country"], v["asn"], v["status"]])

        t.print_last_row()
        return

    # -------- BLOCK MODE --------
    if "--block" in sys.argv:
        networks = set()
        skipped_ir = []
        ir_candidates = []

        for ip, v in enriched.items():
            if v["status"] == "blocked by iptables":
                continue

            if v["cc"] == "IR":
                skipped_ir.append((ip, v["attempts"]))
                if v["attempts"] > 10:
                    ir_candidates.append(ip)
                continue

            try:
                networks.add(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
            except:
                pass

        # Show IR skipped
        if skipped_ir:
            print("\nIR IPs skipped:")
            for ip, cnt in skipped_ir:
                print(f"{ip:16}  attempts:{cnt}")

        added = 0

        # Ask for blocking IR heavy attackers
        if ir_candidates:
            ans = input("\nBlock IR IPs with more than 10 failed attempts? (y/N): ").strip().lower()
            if ans == "y":
                for ip in ir_candidates:
                    if subprocess.call(["iptables", "-C", "INPUT", "-s", ip, "-j", "DROP"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                        subprocess.call(["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"])
                        added += 1

        # Block non-IR ranges
        for net in networks:
            if subprocess.call(["iptables", "-C", "INPUT", "-s", net, "-j", "DROP"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                subprocess.call(["iptables", "-I", "INPUT", "-s", net, "-j", "DROP"])
                added += 1

        subprocess.call(["netfilter-persistent", "save"])
        print(f"\nAdded {added} new iptables rules.")

if __name__ == "__main__":
    main()
