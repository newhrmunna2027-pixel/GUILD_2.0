# filepath: bot/core/logic.py
# bot/core/logic.py

import os
import json
import asyncio
from bot.packets import team_packets
from utils.helpers import delete_bot_room_state

TEAM_JSON_FILE = 'config/Team.json'

async def manage_team_file(bot, action, t_uid=None):
    if not os.path.exists('config'): 
        os.makedirs('config')
        
    try:
        with open(TEAM_JSON_FILE, 'r', encoding='utf-8') as f: 
            data = json.load(f)
    except Exception: 
        data = {}

    bot_uid = getattr(bot, 'my_uid', None)
    bot_key = str(bot_uid) if bot_uid else getattr(bot, 'bot_name', 'UnknownBot')
    
    if action == "sync_full_team" and t_uid is not None:
        valid_uids = [str(u) for u in t_uid if str(u).isdigit()]
        data[bot_key] = valid_uids

    elif action == "clear":
        data[bot_key] = []

    elif action == "add_member" and t_uid and str(t_uid).isdigit():
        if bot_key not in data: data[bot_key] = []
        if str(t_uid) not in data[bot_key]: data[bot_key].append(str(t_uid))
        
    elif action == "remove_member" and t_uid and str(t_uid).isdigit():
        if bot_key in data and str(t_uid) in data[bot_key]:
            data[bot_key].remove(str(t_uid))
            
    elif action == "set_leader" and t_uid:
        pass 

    try:
        with open(TEAM_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving team: {e}")

async def execute_solo_logic(bot):
    from bot.core.manager import send_online_packet 
    
    if getattr(bot, 'is_magic_mode', False):
        bot.is_magic_mode = False
        
    bot.is_locked = False
    bot.is_creating_lobby = False
    bot.joined_look_done = False
    
    if bot.is_in_team:
        leave_pkt = await team_packets.create_leave_team_packet(bot.my_uid, bot.key, bot.iv)
        await send_online_packet(bot, leave_pkt)
        bot.is_in_team = False
    
    await asyncio.sleep(0.5)
    await bot._close_chat_connection()   
    
    bot.team_chat_authed = False
    bot.current_chat_code = None
    bot.current_chat_owner = None
    bot.team_uids = []
    
    # 🟢 কাস্টম রুমের সেভ করা ডাটা ও সেশন ক্লিয়ার করে দিবে
    try:
        delete_bot_room_state(bot.my_uid)
        bot.room_id = None
        bot.room_secret_code = None
        bot.is_in_room = False
        bot.is_joining_room = False
    except Exception as e:
        print(f"[{getattr(bot, 'bot_name', 'Bot')}] ⚠️ Room state clear error: {e}")
    
    await manage_team_file(bot, "clear")
    print(f"[{getattr(bot, 'bot_name', 'Bot')}] 🔄 Execute Solo: Left Team, Room State Cleared & Chat connection closed.")
