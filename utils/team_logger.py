# utils/team_logger.py

import os
from datetime import datetime

LOG_FILE = 'log.txt' 

def log_team_info(description, bot):
    return  # 🟢 এই একটি লাইনের কারণে লগার অফ হয়ে যাবে (ফাইলে কিছু লিখবে না)

    # config ফোল্ডার না থাকলে তৈরি করবে
    if not os.path.exists('config'):
        os.makedirs('config')
        
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # লগ করার জন্য প্রয়োজনীয় তথ্য
    bot_name = getattr(bot, 'bot_name', 'Unknown')
    owner = getattr(bot, 'current_chat_owner', 'None')
    code = getattr(bot, 'current_chat_code', 'None')
    
    log_entry = (
        f"[{time_now}] Bot: {bot_name}\n"
        f"    Description: {description}\n"
        f"    > Leader UID: {owner}\n"
        f"    > Chat Code : {code}\n"
        f"-----------------------------------------\n"
    )
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Logger Error: {e}")