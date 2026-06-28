# utils/packet_logger.py

import json
import os
from datetime import datetime

LOG_FILE = 'config/packet_log.txt'

def log_packet(packet_id, description, data):
    return  # 🟢 এই একটি লাইনের কারণে প্যাকেট লগার অফ হয়ে যাবে

    if not os.path.exists('config'):
        os.makedirs('config')
        
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = {
        "Time": time_now,
        "Packet_ID": packet_id,
        "Description": description,
        "Data": data
    }
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, indent=4, ensure_ascii=False) + "\n")
            f.write("="*50 + "\n")
    except Exception as e:
        print(f"Logger Error: {e}")