#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Replicate the shell script's Instagram GraphQL call in Python:
- Sets the same headers (Cookie, X-FB-LSD, X-CSRFToken, X-IG-App-ID, etc.)
- Sends the same form fields (__a, __d, __req, __hs, __dyn, __csr, lsd, fb_api_req_friendly_name, variables, server_timestamps, doc_id, ...)
- Tests 6 shortcodes for should_mute_audio.

IMPORTANT: Fill PLACEHOLDER values from a real browser session cookies/network tab.
"""

import json
import re
import time
from typing import Dict, Optional, Tuple, List

try:
    import requests
except ImportError:
    import sys, subprocess
    print("⚙️  Installing missing package: requests ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


REQUEST_TIMEOUT = 12

SHORTCODES: List[str] = [
    "C2YEAdOh9AB",
    "Cx_DE0ZI1xc",
    "CyERUKpIS7Q",
    "C0Y6l7qrfi-",
    "CrfV3RxgKYl",
    "C2u22AltQEu",
    "DMzrSzCq3Fb",
    "DO4CkL2EmgQ",
    "DO_Bf6njYxx",
]

# ----------------- FILL THESE FROM A REAL SESSION -----------------
TOKENS = {
    # Cookies you see on instagram.com (Network tab) — keep them consistent with headers
    "csrftoken": "REPLACE_WITH_REAL_csrftoken",
    "ig_did": "REPLACE_WITH_REAL_IG_DID",  # looks like a UUID
    "dpr": "1.75",  # same as shell
    # Headers
    "x_fb_lsd": "REPLACE_WITH_REAL_X_FB_LSD",  # X-FB-LSD (aka lsd)
}

# Long meta params used by IG web GraphQL. These vary per session/build; paste real values.
IG_META = {
    "__hs": "REPLACE_WITH___hs",                 # e.g. "19750.HYP:instagram_web_pkg.2.1..0.0"
    "__rev": "REPLACE_WITH___rev",               # e.g. "1011068636"
    "__hsi": "REPLACE_WITH___hsi",               # e.g. "7328972521009111950"
    "__s": "REPLACE_WITH___s",                   # e.g. "drshru:gu4p3s:0d8tzk"
    "__dyn": "REPLACE_WITH___dyn",               # long string
    "__csr": "REPLACE_WITH___csr",               # long string
    "__ccg": "UNKNOWN",
    "__req": "3",
    "__spin_r": "REPLACE_WITH___spin_r",
    "__spin_t": "REPLACE_WITH___spin_t",         # epoch (int as string)
}

# GraphQL doc and friendly names from the shell script
DOC_ID = "10015901848480474"
FRIENDLY_NAME = "PolarisPostActionLoadPostQueryQuery"
# ------------------------------------------------------------------

BASE_URL = "https://www.instagram.com/api/graphql"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

class PrintTable:
    def __init__(self, headers, lengths):
        self.headers = headers
        self.lengths = lengths
        # الگوی regex برای حذف کدهای ANSI رنگ
        self.ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

    def print_headers(self):
        sum_length = sum(self.lengths) + 3 * len(self.lengths) + 1
        print("-" * sum_length)
        header = "| "
        for h, l in zip(self.headers, self.lengths):
            header += self.truncate_and_pad(h, l) + " | "
        header = header.strip()
        print(header)
        print("-" * sum_length)

    def truncate_and_pad(self, string, length):
        string = str(string) or ""
        # حذف کدهای رنگ ANSI برای محاسبه طول واقعی
        clean = self.ansi_escape.sub("", string)
        # برش متن تمیز
        if len(clean) > length:
            visible = clean[:length - 3] + "..."
        else:
            visible = clean
        # با رنگ اصلی چاپ بشه ولی padding بر اساس clean باشه
        padding = " " * (length - len(clean[:length]) if len(clean) < length else 0)
        return string + padding if len(clean) <= length else string.replace(clean, visible)

    def print_row(self, data):
        row = "| "
        for d, l in zip(data, self.lengths):
            row += self.truncate_and_pad(d, l) + " | "
        row = row.strip()
        print(row)

    def print_last_row(self):
        sum_length = sum(self.lengths) + 3 * len(self.lengths) + 1
        print("-" * sum_length)

def build_cookie_header(tokens: Dict[str, str]) -> str:
    # Mirror shell cookie pack; minimally csrftoken, dpr, ig_did
    parts = [
        f"csrftoken={tokens['csrftoken']}",
        f"dpr={tokens.get('dpr','1.75')}",
        f"ig_did={tokens['ig_did']}",
    ]
    return "; ".join(parts)

def build_headers(shortcode: str) -> Dict[str, str]:
    return {
        "Accept": "*/*",
        "Accept-Language": "ru-RU,zh;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": build_cookie_header(TOKENS),
        "Origin": "https://www.instagram.com",
        "Referer": f"https://www.instagram.com/p/{shortcode}/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": UA,
        "X-ASBD-ID": "129477",
        "X-CSRFToken": TOKENS["csrftoken"],
        "X-FB-Friendly-Name": FRIENDLY_NAME,
        "X-FB-LSD": TOKENS["x_fb_lsd"],
        "X-IG-App-ID": "936619743392459",
        "dpr": TOKENS.get("dpr","1.75"),
        "sec-ch-prefers-color-scheme": "light",
        # These Client Hints were present in the shell; optional but we include them
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-full-version-list': '"Not_A Brand";v="8.0.0.0", "Chromium";v="120.0.6099.225", "Google Chrome";v="120.0.6099.225"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-platform-version': '"10.0.0"',
        'viewport-width': '1640',
    }

def build_variables(shortcode: str) -> Dict:
    """
    Matches the structure hinted in the shell script: includes counts & flags often used by IG web.
    Exact fields may vary; fill to mirror the shell as closely as possible.
    """
    return {
        "shortcode": shortcode,
        "fetch_comment_count": 40,
        # these 3 were visible in the shell around variables:
        "fetch_ig_uad_comment_count": 3,          # if unknown, set a small int
        "fetch_like_count": 10,
        "fetch_tagged_user_count": None,          # null in shell
        "fetch_preview_comment_count": 2,
        "has_threaded_comments": True,
        "hoisted_comment_id": None,
        "hoisted_reply_id": None,
    }

def build_form(shortcode: str) -> Dict[str, str]:
    vars_json = json.dumps(build_variables(shortcode), separators=(",", ":"), ensure_ascii=False)
    form = {
        "av": "0",
        "__d": "www",
        "__user": "0",
        "__a": "1",
        "__req": IG_META["__req"],
        "__hs": IG_META["__hs"],
        "dpr": "1",
        "__ccg": IG_META["__ccg"],
        "__rev": IG_META["__rev"],
        "__s": IG_META["__s"],
        "__hsi": IG_META["__hsi"],
        "__dyn": IG_META["__dyn"],
        "__csr": IG_META["__csr"],
        "__comet_req": "7",
        "lsd": TOKENS["x_fb_lsd"],
        "__spin_r": IG_META["__spin_r"],
        "__spin_t": IG_META["__spin_t"],
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": FRIENDLY_NAME,
        "variables": vars_json,
        "server_timestamps": "true",
        "doc_id": DOC_ID,
    }
    return form

def call_instagram(shortcode: str) -> Tuple[bool, Dict]:
    headers = build_headers(shortcode)
    data = build_form(shortcode)
    try:
        resp = requests.post(
            BASE_URL,
            headers=headers,
            data=data,
            timeout=REQUEST_TIMEOUT,
        )
        # Graph responses often prefix "for (;;);" then JSON
        text = resp.text or ""
        if text.startswith("for (;;);"):
            try:
                payload = json.loads(text[len("for (;;);"):])
            except Exception:
                payload = {"status": resp.status_code, "text": text[:1200]}
        else:
            try:
                payload = resp.json()
            except Exception:
                payload = {"status": resp.status_code, "text": text[:1200]}
        return resp.ok, payload
    except Exception as e:
        return False, {"error": str(e)}

def extract_should_mute(payload: Dict) -> Optional[bool]:
    def deep_find(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "should_mute_audio" and isinstance(v, bool):
                    return v
                found = deep_find(v)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for it in obj:
                found = deep_find(it)
                if found is not None:
                    return found
        return None

    val = deep_find(payload)
    if val is not None:
        return val

    # fallback text scan (if response was stringified into 'text')
    txt = payload.get("text") if isinstance(payload, dict) else None
    if isinstance(txt, str):
        m = re.search(r'"should_mute_audio"\s*:\s*(true|false)', txt)
        if m:
            return m.group(1) == "true"
    return None


def extract_clips_music_attribution_info(payload):
    if isinstance(payload, dict):
        d = payload.get("data")
        if d:
            xdt = d.get("xdt_shortcode_media")
            if xdt:
                mu = xdt.get("clips_music_attribution_info")
                if mu:
                    return mu
    return None

headers = ["ShortCode", "RequestStatus", "Play Auido", "Artist", "Song", "OriginalAudio", "AuidoID", "MuteReason"]
lenghts = [13, 13, 13, 20, 20, 20, 20, 30]
printObj = PrintTable(headers, lenghts)
print_ok_snippet = True
print_no_snippet = True
def pretty_result(shortcode: str, ok: bool, payload: Dict):
    global print_ok_snippet, print_no_snippet
    mute = extract_should_mute(payload)
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    if mute is None:
        audio = f"{YELLOW}Unkown{RESET}"
    elif mute:
        audio = audio = f"{RED}NO{RESET}"
    else:
        audio = f"{GREEN}OK{RESET}"

    #print(f"--- {shortcode} ---")
    # print(f"{shortcode}\tRequest Status: {'OK' if ok else 'FAILED'}\tPlay Auido: {audio}")

    #print(f"should_mute_audio: {'unknown' if mute is None else mute}")
    try:
        snippet = json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        snippet = str(payload)
        
    d = extract_clips_music_attribution_info(payload)
    artist_name, song_name, uses_original_audio, should_mute_audio_reason, audio_id = "", "", "", "", ""
    if d:
        artist_name = d["artist_name"]
        song_name = d["song_name"]
        uses_original_audio = d["uses_original_audio"]
        should_mute_audio_reason = d["should_mute_audio_reason"]
        audio_id = d["audio_id"]
    data = [shortcode, 'OK' if ok else 'FAILED', audio, artist_name, song_name, uses_original_audio, audio_id, should_mute_audio_reason]
    
    printObj.print_row(data)
    # if len(snippet) > 1500:
    #     snippet = snippet[:1500] + "\n... (truncated)"

    #print("payload_snippet:")
    # if print_ok_snippet and audio == "OK":
    #     print(snippet)
    #     print_ok_snippet = False
    # if print_no_snippet and audio == "NO":
    #     print(snippet)
    #     print_no_snippet = False
    #print("--------------------\n")

def main():
    print(f"[v1.0] Starting checks for {len(SHORTCODES)} videos...\n")
    printObj.print_headers()
    for i, sc in enumerate(SHORTCODES, 1):
        # print(f"[{i}/{len(SHORTCODES)}] Testing shortcode: {sc}")   
        ok, payload = call_instagram(sc)
        pretty_result(sc, ok, payload)
        time.sleep(1.0)  # politeness
    printObj.print_last_row()

if __name__ == "__main__":
    main()
