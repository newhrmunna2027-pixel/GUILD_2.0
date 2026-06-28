# utils/helpers.py

import json
import os
import random
import re
from fuzzywuzzy import process

SAVED_UIDS_FILE = 'config/saved_uids.json'

# প্রজেক্টের অ্যাবসলিউট পাথ জেনারেটর (Directory lock এড়ানোর জন্য)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOM_DIR = os.path.join(BASE_DIR, 'config', 'room')

PET_ID_MAP = {
    1300000001: "Kitty", 1300000011: "Mechanical Pup", 1300000021: "Night Panther",
    1300000031: "Detective Panda", 1300000041: "Shiba", 1300000051: "Spirit Fox",
    1300000061: "Robo", 1300000071: "Poring", 1300000081: "Ottero", 1300000091: "Falco",
    1300000101: "Mr Waggor", 1300000111: "Rockie", 1300000112: "Beaston",
    1300000113: "Dreki", 1300000114: "Moony", 1300000115: "Dr Beanie",
    1300000116: "Sensei Tig", 1300000117: "Agent Hop", 1300000118: "Yeti",
    1300000119: "Flash", 1300000120: "Zasil", 1300000121: "Finn",
    1300000122: "Hoot", 1300000123: "Fang", 1300000124: "Arvon",
    1300000125: "Kactus", 1300000126: "Pug", 1300000127: "Agumon"
}

def get_pet_default_name(pet_id):
    try:
        pid = int(pet_id)
        if pid in PET_ID_MAP: return PET_ID_MAP[pid]
        return f"Pet ID {pid}" 
    except: return "Unknown"

def get_chat_type_name(chat_type_id):
    types = {0: "Squad", 1: "Clan", 2: "Private"}
    return types.get(chat_type_id, "Unknown")

async def DecodE_HeX(val):
    if val is None: return ''
    h = hex(val)[2:]
    return '0' * (len(h) % 2) + h

async def xBunnEr():
    bN = [902000306, 902000305, 902000003, 902000016, 902000017, 902031010, 902043025]
    return random.choice(bN)

async def format_uid_for_chat(uid_str):
    s = str(uid_str)
    if len(s) < 3:
        return s
        
    formatted = ""
    for i, char in enumerate(s):
        formatted += char
        if (i + 1) % 2 == 0 and (i + 1) != len(s):
            if (i + 1) % 4 == 0:
                formatted += "🗿"
            else:
                formatted += "🗿"
                
    return formatted

async def load_saved_uids(bot_uid):
    try:
        if os.path.exists(SAVED_UIDS_FILE):
            with open(SAVED_UIDS_FILE, 'r') as f:
                data = json.load(f)
                raw_list = data.get(str(bot_uid), [])
                
                clean_list = []
                for x in raw_list:
                    if str(x).isdigit():
                        val = int(x)
                        if val not in clean_list:
                            clean_list.append(val)
                return clean_list
    except: pass
    return []

async def save_saved_uids(bot_uid, uids):
    data = {}
    if os.path.exists(SAVED_UIDS_FILE):
        try:
            with open(SAVED_UIDS_FILE, 'r') as f: data = json.load(f)
        except: pass
    
    clean_uids = []
    for uid in uids:
        if uid not in clean_uids:
            clean_uids.append(uid)
            
    data[str(bot_uid)] = clean_uids
    if not os.path.exists('config'): os.makedirs('config')
    with open(SAVED_UIDS_FILE, 'w') as f: json.dump(data, f, indent=4)

async def get_saved_list_for_bot(bot_uid):
    return await load_saved_uids(bot_uid)

async def add_uids_to_list(bot_uid, new_uids):
    current = await load_saved_uids(bot_uid)
    added_count = 0
    for uid in new_uids:
        s_uid = str(uid).strip()
        if s_uid.isdigit():
            uid_int = int(s_uid)
            if uid_int not in current:
                current.append(uid_int)
                added_count += 1
    if len(current) > 10: current = current[-10:]
    await save_saved_uids(bot_uid, current)
    return current, added_count

async def remove_uids_from_list(bot_uid, args_to_remove):
    current = await load_saved_uids(bot_uid)
    if not current: return [], []
    uids_to_purge = set()
    for arg in args_to_remove:
        s_arg = str(arg).strip()
        if s_arg.isdigit():
            val = int(s_arg)
            if 1 <= val <= 10 and val <= len(current):
                uids_to_purge.add(current[val - 1])
            elif len(s_arg) > 5:
                if val in current: uids_to_purge.add(val)
    removed_list = list(uids_to_purge)
    new_list = [uid for uid in current if uid not in uids_to_purge]
    await save_saved_uids(bot_uid, new_list)
    return new_list, removed_list

async def sync_team_to_saved_uids(bot_uid, team_uids):
    current_list = await load_saved_uids(bot_uid)
    current_list = [uid for uid in current_list if uid not in team_uids]
    new_list = team_uids + current_list
    new_list = list(dict.fromkeys(new_list))
    if len(new_list) > 10:
        new_list = new_list[:10]
    await save_saved_uids(bot_uid, new_list)

async def remove_single_saved_uid(bot_uid, target_uid):
    current = await load_saved_uids(bot_uid)
    try:
        target = int(target_uid)
        if target in current:
            current.remove(target)
            await save_saved_uids(bot_uid, current)
    except: pass

async def resolve_uids(client, raw_uids, ctx=None, exclude_self=False):
    final_uids = []
    if not raw_uids:
        saved = await load_saved_uids(client.my_uid)
        final_uids.extend(saved)
        if not exclude_self: final_uids.append(int(client.my_uid))
        if ctx and ctx.get('uid'): final_uids.append(int(ctx.get('uid')))
        return list(dict.fromkeys(final_uids))

    for arg in raw_uids:
        arg_str = str(arg).lower().strip()
        if arg_str == 'all':
            saved = await load_saved_uids(client.my_uid)
            final_uids.extend(saved)
            if not exclude_self: final_uids.append(int(client.my_uid))
            if ctx and ctx.get('uid'): final_uids.append(int(ctx.get('uid')))
        elif arg_str == 'me':
            if ctx and ctx.get('uid'): final_uids.append(int(ctx.get('uid')))
        elif arg_str == 'bot': final_uids.append(int(client.my_uid))
        elif arg_str.isdigit() and len(arg_str) > 5: final_uids.append(int(arg_str))
            
    return list(dict.fromkeys(final_uids))

async def find_emote_id_in_book(client, identifier):
    identifier = str(identifier).lower()
    
    if identifier.isdigit():
        if len(identifier) > 6: return int(identifier), None
        
    if not hasattr(client, 'emote_book') or not client.emote_book:
        try:
            with open('config/emote_book.json', 'r', encoding='utf-8') as f:
                client.emote_book = json.load(f)
        except: return (int(identifier), None) if identifier.isdigit() else (None, "Emote book not found.")

    all_emotes = []
    for rank in client.emote_book.get('ranks', []):
        for badge in rank.get('badges', []):
            for emote in badge.get('emotes', []):
                all_emotes.append(emote)
    
    for emote in all_emotes:
        if str(emote.get('no', '')) == identifier: return int(emote.get('id')), None
        if str(emote.get('id', '')) == identifier: return int(emote.get('id')), None

    normalized_input = re.sub(r'[\s-]', '', identifier)
    for emote in all_emotes:
        normalized_name = re.sub(r'[\s-]', '', emote.get('name', '').lower())
        if normalized_name == normalized_input:
            return int(emote.get('id')), None

    emote_names = [e['name'] for e in all_emotes]
    matches = process.extract(identifier, emote_names, limit=3)
    hints = []
    for match in matches:
        if match[1] > 60:
            matched_name = match[0]
            for e in all_emotes:
                if e.get('name') == matched_name:
                    hints.append(f"• [00FF00]No. {e.get('no')}[FFFFFF] - {matched_name}")
                    break
    
    if hints:
        hint_msg = f"[FF0000]No emote found for: '{identifier}'\n[FFFF00]Did you mean?\n" + "\n".join(hints)
        return None, hint_msg
        
    return None, f"[FF0000]Emote '{identifier}' not found. No suggestions available."

async def parse_and_resolve_emotes(client, text):
    parts = [p.strip() for p in text.split(',') if p.strip()]
    emote_ids = []
    error = None

    for part in parts:
        if '=' in part:
            subparts = part.split('=')
            if len(subparts) == 2 and subparts[0].isdigit() and subparts[1].isdigit():
                start, end = int(subparts[0]), int(subparts[1])
                if start > end: start, end = end, start
                for i in range(start, end + 1):
                    eid, err = await find_emote_id_in_book(client, str(i))
                    if eid: emote_ids.append(eid)
                    elif not error: error = err
            else:
                eid, err = await find_emote_id_in_book(client, part)
                if eid: emote_ids.append(eid)
                elif not error: error = err
        else:
            eid, err = await find_emote_id_in_book(client, part)
            if eid: emote_ids.append(eid)
            elif not error: error = err

    return list(dict.fromkeys(emote_ids)), error

async def EnC_Uid(H, Tp):
    e, H = [], int(H)
    while H:
        e.append((H & 0x7F) | (0x80 if H > 0x7F else 0))
        H >>= 7
    return bytes(e).hex() if Tp == 'Uid' else None

# 🟢 BOT-SPECIFIC ROOM SESSION STATE CONTROLLER (ABSOLUTE PATH FIX)
def save_bot_room_state(bot_uid, room_id, secret_code):
    """প্রতিটি বটের ইউআইডি অনুযায়ী রুম সেশন ডাটা সেভ করে (Absolute Path)"""
    if not bot_uid:
        print("[Room State] Error: bot_uid is None or empty!")
        return
    os.makedirs(ROOM_DIR, exist_ok=True)
    filepath = os.path.join(ROOM_DIR, f"{str(bot_uid)}.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "room_id": str(room_id), 
                "secret_code": str(secret_code)
            }, f, indent=4)
        print(f"[Room State] Saved session for Bot {bot_uid} inside {filepath}")
    except Exception as e:
        print(f"[Room State] Error saving for Bot {bot_uid}: {e}")

def load_bot_room_state(bot_uid):
    """ইউআইডি দিয়ে বটের সংরক্ষিত রুম সেশন রিড করে (Absolute Path)"""
    if not bot_uid: return None
    filepath = os.path.join(ROOM_DIR, f"{str(bot_uid)}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("room_id") and data.get("secret_code"):
                    return data
        except:
            pass
    return None

def delete_bot_room_state(bot_uid):
    """বটের রুম সেশন ফাইলটি গ্লোবালি মুছে ফেলে (Absolute Path)"""
    if not bot_uid: return
    filepath = os.path.join(ROOM_DIR, f"{str(bot_uid)}.json")
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"[Room State] Cleared session file for Bot {bot_uid}")
        except Exception as e:
            print(f"[Room State] Error clearing file for Bot {bot_uid}: {e}")