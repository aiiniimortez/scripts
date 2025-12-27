#!/usr/bin/env python3
"""
ssh_blocker.py
- modes: --analysis, --block
- GeoIP (country + ASN), prints tidy table
- local per-server DB: /var/lib/ssh_blocker/<server_id>.sqlite
- when analysis finishes: ask to upload report to Telegram (store token/chat_id in /usr/local/ssh_blocker/env)
- block mode: block local attackers (same logic as before), then optionally download merge_ips.db from Github and block new ranges
"""

import os
import sys
import subprocess
import re
import ipaddress
import sqlite3
import uuid
import datetime
import tempfile
import requests
import getpass
import shutil
from collections import Counter
from tqdm import tqdm
import geoip2.database

# ------------------ Config ------------------
GEOLITE_COUNTRY_PATH = "GeoLite2-Country.mmdb"
GEOLITE_ASN_PATH = "GeoLite2-ASN.mmdb"
MERGE_DB_URL = "https://raw.githubusercontent.com/aiiniimortez/scripts/refs/heads/main/merge_ips.sqlite"
ENV_DIR = "/usr/local/ssh_blocker"
ENV_FILE = os.path.join(ENV_DIR, "env")
SERVER_ID_PATH = "/etc/ssh_blocker.id"  # primary location, fallback to ~/.ssh_blocker_id
LOCAL_DB_DIR = "/var/lib/ssh_blocker"
os.makedirs(LOCAL_DB_DIR, exist_ok=True)
os.makedirs(ENV_DIR, exist_ok=True)

# ------------------ GeoIP helpers ------------------
def download(url, fname):
    if os.path.isfile(fname):
        return
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0) or 0)
    with open(fname, "wb") as f, tqdm(total=total, desc=fname, unit='iB', unit_scale=True, unit_divisor=1024) as bar:
        for chunk in r.iter_content(chunk_size=8192):
            if not chunk:
                continue
            f.write(chunk)
            bar.update(len(chunk))

def setup_geo():
    # assume these files will be in cwd; if not present, try to download (best-effort)
    if not os.path.isfile(GEOLITE_COUNTRY_PATH):
        try:
            download("https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb", GEOLITE_COUNTRY_PATH)
        except Exception:
            pass
    if not os.path.isfile(GEOLITE_ASN_PATH):
        try:
            download("https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-ASN.mmdb", GEOLITE_ASN_PATH)
        except Exception:
            pass

country_reader = None
asn_reader = None

def load_readers():
    global country_reader, asn_reader
    if os.path.isfile(GEOLITE_COUNTRY_PATH):
        country_reader = geoip2.database.Reader(GEOLITE_COUNTRY_PATH)
    if os.path.isfile(GEOLITE_ASN_PATH):
        asn_reader = geoip2.database.Reader(GEOLITE_ASN_PATH)

def find_country(ip):
    try:
        if country_reader:
            return country_reader.country(ip).country.name
    except Exception:
        pass
    return "Unknown"

def find_country_code(ip):
    try:
        if country_reader:
            return country_reader.country(ip).country.iso_code
    except Exception:
        pass
    return "XX"

def find_asn(ip):
    try:
        if asn_reader:
            return asn_reader.asn(ip).autonomous_system_organization
    except Exception:
        pass
    return "Unknown"

# ------------------ Print table helper ------------------
class PrintTable:
    def __init__(self, headers, lengths):
        self.headers = headers
        self.lengths = lengths
        self.ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

    def print_headers(self):
        s = sum(self.lengths) + 3 * len(self.lengths) + 1
        print("-" * s)
        header = "| "
        for h, l in zip(self.headers, self.lengths):
            header += self.truncate_and_pad(h, l) + " | "
        print(header.strip())
        print("-" * s)

    def truncate_and_pad(self, string, length):
        string = str(string) or ""
        clean = self.ansi_escape.sub("", string)
        visible = clean[:length] if len(clean) <= length else clean[:length - 3] + "..."
        padding = " " * (length - len(visible))
        return visible + padding

    def print_row(self, data):
        row = "| "
        for d, l in zip(data, self.lengths):
            row += self.truncate_and_pad(d, l) + " | "
        print(row.strip())

    def print_last_row(self):
        s = sum(self.lengths) + 3 * len(self.lengths) + 1
        print("-" * s)

# ------------------ Lastb parsing ------------------
def get_lastb_ips():
    # safe raw command, returns Counter of IP -> attempts
    raw = subprocess.getoutput(r"lastb -w | awk '{print $3}' | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}'")
    return Counter([line.strip() for line in raw.splitlines() if line.strip()])

# ------------------ iptables parsing ------------------
def load_blocked_networks():
    raw = subprocess.getoutput("iptables -L INPUT -n | grep DROP || true")
    nets = set()
    for line in raw.splitlines():
        for p in line.split():
            if "/" in p and "." in p:
                try:
                    nets.add(ipaddress.ip_network(p, strict=False))
                except Exception:
                    pass
    return nets

# ------------------ Server ID & local DB ------------------
def get_or_create_server_id(path=SERVER_ID_PATH):
    # secure random uuid4, no identifying info
    try:
        if os.path.isfile(path):
            with open(path, "r") as f:
                sid = f.read().strip()
                if sid:
                    return sid
        sid = str(uuid.uuid4())
        try:
            with open(path, "w") as f:
                f.write(sid + "\n")
            os.chmod(path, 0o600)
        except PermissionError:
            # fallback
            fb = os.path.expanduser("~/.ssh_blocker_id")
            with open(fb, "w") as f:
                f.write(sid + "\n")
            try:
                os.chmod(fb, 0o600)
            except:
                pass
        return sid
    except Exception:
        # deterministic fallback (should not happen)
        return str(uuid.uuid4())

def local_db_path_for_sid(sid):
    return os.path.join(LOCAL_DB_DIR, f"{sid}.sqlite")

def ensure_db(sid):
    dbp = local_db_path_for_sid(sid)
    conn = sqlite3.connect(dbp, timeout=30)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY,
        server_id TEXT NOT NULL,
        ip TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        country TEXT,
        asn TEXT,
        last_seen TEXT,
        UNIQUE(server_id, ip)
    );
    """)
    conn.commit()
    return conn

def upsert_observation(conn, server_id, ip, attempts, country, asn):
    cur = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    cur.execute("""
    INSERT INTO observations (server_id, ip, attempts, country, asn, last_seen)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(server_id, ip) DO UPDATE SET
      attempts = observations.attempts + excluded.attempts,
      country = excluded.country,
      asn = excluded.asn,
      last_seen = excluded.last_seen
    ;
    """, (server_id, ip, attempts, country, asn, now))
    conn.commit()

def sum_attempts_for_ip_local(conn, ip):
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(attempts),0) FROM observations WHERE ip = ?", (ip,))
    r = cur.fetchone()
    return int(r[0]) if r else 0

# ------------------ Telegram helpers ------------------
def read_env():
    data = {}
    if os.path.isfile(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k,v = line.split("=",1)
                    data[k.strip()] = v.strip()
        except Exception:
            pass
    return data

def write_env(data):
    try:
        with open(ENV_FILE, "w") as f:
            for k,v in data.items():
                f.write(f"{k}={v}\n")
        os.chmod(ENV_FILE, 0o600)
    except Exception as e:
        print("[!] Warning: cannot write env file:", e)

def telegram_send_file(token, chat_id, file_path, caption=None):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {"document": (os.path.basename(file_path), open(file_path, "rb"))}
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    r = requests.post(url, data=data, files=files, timeout=120)
    return r

# ------------------ Merge remote feed helpers ------------------
def download_remote_merge_db(url):
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False)
        for chunk in r.iter_content(chunk_size=8192):
            if not chunk:
                continue
            tmp.write(chunk)
        tmp.flush()
        tmp.close()
        return tmp.name
    except Exception as e:
        print("[!] Failed to download remote merge DB:", e)
        return None

# merge remote (schema: ssh_ip_attempts(ip, total_attempts, asn, country))
# We'll read remote rows and for each ip compute combined attempts (remote.total_attempts + local sum)
def process_and_block_remote_feed(remote_db_path, blocked_nets, local_conn):
    added = 0
    try:
        rconn = sqlite3.connect(remote_db_path, timeout=30)
        rcur = rconn.cursor()
        rcur.execute("SELECT ip, total_attempts, asn, country FROM ssh_ip_attempts")
        rows = rcur.fetchall()
        print(f"[+] Remote feed contains {len(rows)} IPs")
        for ip, remote_attempts, rasn, rcountry in rows:
            try:
                ip_obj = ipaddress.ip_address(ip)
            except Exception:
                continue

            # check if ip is already covered by blocked_nets
            covered = False
            for net in blocked_nets:
                if ip_obj in net:
                    covered = True
                    break
            if covered:
                continue

            # choose net to block (same as local logic): /24
            try:
                net = ipaddress.ip_network(f"{ip}/24", strict=False)
            except Exception:
                continue

            # double-check net not in blocked_nets
            already = False
            for bn in blocked_nets:
                if net.subnet_of(bn) or bn.subnet_of(net):
                    already = True
                    break
            if already:
                continue

            # compute local attempts sum for reporting
            local_sum = 0
            if local_conn:
                local_sum = sum_attempts_for_ip_local(local_conn, ip)
            combined = int(remote_attempts) + int(local_sum)

            # insert iptables rule if not exists
            exists = subprocess.call(["iptables","-C","INPUT","-s",str(net),"-j","DROP"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if exists != 0:
                subprocess.call(["iptables","-I","INPUT","-s",str(net),"-j","DROP"])
                added += 1
                print(f"[BLOCKED REMOTE] {str(net)}  combined_attempts:{combined} (remote:{remote_attempts}, local:{local_sum})")
                blocked_nets.add(net)
        rconn.close()
    except Exception as e:
        print("[!] Error processing remote feed:", e)
    return added

# ------------------ Main flow ------------------
def main():
    if len(sys.argv) == 1:
        print("Use --analysis or --block")
        return

    # Setup geo readers (best-effort)
    setup_geo()
    load_readers()

    server_id = get_or_create_server_id()
    local_db = ensure_db(server_id)

    # collect lastb
    ip_stats = get_lastb_ips()
    blocked_nets = load_blocked_networks()

    enriched = {}
    for ip, cnt in ip_stats.items():
        status = "open"
        try:
            ip_obj = ipaddress.ip_address(ip)
            for net in blocked_nets:
                if ip_obj in net:
                    status = "blocked by iptables"
                    break
        except Exception:
            pass

        enriched[ip] = {
            "attempts": cnt,
            "country": find_country(ip),
            "cc": find_country_code(ip),
            "asn": find_asn(ip),
            "status": status
        }

    # ---------- ANALYSIS ----------
    if "--analysis" in sys.argv:
        headers = ["IP", "Attempts", "Country", "ASN", "Status"]
        lengths = [18, 8, 18, 40, 22]
        t = PrintTable(headers, lengths)
        t.print_headers()

        open_rows = []
        blocked_rows = []
        for ip, v in enriched.items():
            (open_rows if v["status"]=="open" else blocked_rows).append((ip, v))

        for ip, v in sorted(open_rows, key=lambda x: x[1]["attempts"], reverse=True):
            t.print_row([ip, v["attempts"], v["country"], v["asn"], v["status"]])
        for ip, v in sorted(blocked_rows, key=lambda x: x[1]["attempts"], reverse=True):
            t.print_row([ip, v["attempts"], v["country"], v["asn"], v["status"]])

        t.print_last_row()

        # store results locally into DB (UPSERT)
        for ip, v in enriched.items():
            try:
                upsert_observation(local_db, server_id, ip, v["attempts"], v["country"], v["asn"])
            except Exception as e:
                print("[!] DB upsert error for", ip, e)

        # ask to upload to Telegram
        ans = input("\nUpload local report to Telegram? (y/N): ").strip().lower()
        if ans == "y":
            env = read_env()
            token = env.get("TELEGRAM_TOKEN")
            chat = env.get("TELEGRAM_CHAT_ID")
            if not token:
                token = input("Enter Telegram bot token (botXXXXXXXX:...): ").strip()
            if not chat:
                chat = input("Enter your Telegram user/chat id: ").strip()

            # save for next time
            env["TELEGRAM_TOKEN"] = token
            env["TELEGRAM_CHAT_ID"] = chat
            write_env(env)

            # send DB file (create copy with server_id name)
            dbpath = local_db_path_for_sid(server_id)
            sendname = f"{server_id}.sqlite"
            # ensure file exists
            local_db.close()
            print("[+] Sending file to Telegram...")
            try:
                res = telegram_send_file(token, chat, dbpath, caption=f"ssh_blocker report from {os.uname().nodename} ({server_id})")
                if res and res.status_code == 200:
                    print("[✓] Sent to Telegram.")
                else:
                    print("[!] Telegram send failed:", getattr(res, "text", res))
            except Exception as e:
                print("[!] Telegram send error:", e)
            # reopen db for consistency
            local_db = sqlite3.connect(dbpath, timeout=30)

        return

    # ---------- BLOCK ----------
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

        # IR heavy ask
        if ir_candidates:
            ans = input("\nBlock IR IPs with more than 10 failed attempts? (y/N): ").strip().lower()
            if ans == "y":
                for ip in ir_candidates:
                    if subprocess.call(["iptables","-C","INPUT","-s",ip,"-j","DROP"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                        subprocess.call(["iptables","-I","INPUT","-s",ip,"-j","DROP"])
                        added += 1

        # Block non-IR ranges after uniq
        for net in sorted(networks):
            exists = subprocess.call(["iptables","-C","INPUT","-s",net,"-j","DROP"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if exists != 0:
                subprocess.call(["iptables","-I","INPUT","-s",net,"-j","DROP"])
                added += 1

        # save rules
        subprocess.call(["netfilter-persistent","save"])
        print(f"\nAdded {added} new iptables rules (local)")

        # after local blocking, ask whether to block remote shared feed
        ans2 = input("\nDo you want to fetch shared feed and block its IPs too? (y/N): ").strip().lower()
        if ans2 == "y":
            print("[+] Downloading remote merge feed...")
            remote_path = download_remote_merge_db(MERGE_DB_URL)
            if not remote_path:
                print("[!] Could not download remote feed.")
            else:
                print("[+] Processing remote feed and blocking new networks...")
                added_remote = process_and_block_remote_feed(remote_path, blocked_nets, local_db)
                subprocess.call(["netfilter-persistent","save"])
                print(f"\nAdded {added_remote} new iptables rules from remote feed.")
                try:
                    os.unlink(remote_path)
                except:
                    pass

        return

if __name__ == "__main__":
    main()
