# -*- coding: utf-8 -*-
# ping.py - Keep-Alive script to prevent Render spin-down

import os
import time
import urllib.request
from datetime import datetime

# Environment variable থেকে Render-এর অ্যাপ লিংকটি রিড করবে
RENDER_URL = os.environ.get("PING_URL") or os.environ.get("RENDER_URL")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [PINGER] {msg}")

if not RENDER_URL:
    log("Error: PING_URL or RENDER_URL environment variable is not set. Exiting.")
    exit(1)

log(f"Self-pinging started for: {RENDER_URL}")

while True:
    try:
        # Render-এর লিংকে রিকোয়েস্ট পাঠিয়ে সচল রাখা হচ্ছে
        response = urllib.request.urlopen(RENDER_URL, timeout=30)
        status = response.getcode()
        log(f"Ping successful! Status code: {status}")
    except Exception as e:
        log(f"Ping failed: {e}")
    
    # ১০ মিনিট (৬০০ সেকেন্ড) পর পর পুনরায় পিং করবে
    time.sleep(600)
