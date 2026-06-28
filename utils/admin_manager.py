# -*- coding: utf-8 -*-
# utils/admin_manager.py

import json
import os
import sqlite3
import time
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'config', 'database.db')
OWNER_FILE = os.path.join(BASE_DIR, 'config', 'owner.json')
MOOD_FILE = os.path.join(BASE_DIR, 'config', 'bot_moods.json')
LANG_FILE = os.path.join(BASE_DIR, 'config', 'bot_lang.json')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def _execute_with_retry(func, *args, retries=5, delay=0.5):
    for attempt in range(retries):
        try:
            return func(*args)
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < retries - 1:
                time.sleep(delay)
            else:
                raise e

def _get_bot_name_raw(bot_uid):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM bots WHERE ingame_uid=? OR login_uid=? OR name=?", (str(bot_uid), str(bot_uid), str(bot_uid)))
        row = cursor.fetchone()
        return row[0] if row else str(bot_uid)
    finally:
        conn.close()

def _get_bot_name(bot_uid):
    try:
        return _execute_with_retry(_get_bot_name_raw, bot_uid)
    except:
        return str(bot_uid)

def init_bot(bot_uid, bot_name, guild_id):
    if not os.path.exists(os.path.dirname(OWNER_FILE)):
        os.makedirs(os.path.dirname(OWNER_FILE), exist_ok=True)
    if not os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, 'w', encoding='utf-8') as f:
            json.dump({"Owners": ["784579784"]}, f, indent=4)

    # প্রতিটি বটের নিজস্ব UID অনুযায়ী এডমিন ফাইল ইনিশিয়ালাইজ করা হচ্ছে
    dir_path = os.path.join(BASE_DIR, 'config', 'admins')
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{bot_uid}.json")
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"Admins": []}, f, indent=4)

def is_owner(uid):
    uid_str = "".join(c for c in str(uid) if c.isdigit())
    try:
        with open(OWNER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            owners = ["".join(c for c in str(o) if c.isdigit()) for o in data.get("Owners", [])]
            if uid_str in owners: return True
    except: pass
    return False

def get_admins(bot_uid):
    uid_str = "".join(c for c in str(bot_uid) if c.isdigit())
    file_path = os.path.join(BASE_DIR, 'config', 'admins', f"{uid_str}.json")
    
    admins_list = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                admins_list = ["".join(c for c in str(u) if c.isdigit()) for u in data.get("Admins", [])]
        except: pass
        
    # 🟢 ডাটাবেস ও ফাইলের সমতা বজায় রাখতে এবং এপিআই কল সচল রাখতে SQL ব্যাকআপ সিঙ্ক
    if not admins_list:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM bots WHERE ingame_uid=?", (uid_str,))
            row = cursor.fetchone()
            if row:
                bot_name = row['name']
                cursor.execute("SELECT data FROM admins WHERE bot_name=?", (bot_name,))
                arow = cursor.fetchone()
                if arow:
                    admin_data = json.loads(arow['data'])
                    admins_list = ["".join(c for c in str(u) if c.isdigit()) for u in admin_data.get("Admins", [])]
                    
                    # ডাটাবেস থেকে পাওয়া এডমিন ফাইল সেভ করা হচ্ছে
                    dir_path = os.path.join(BASE_DIR, 'config', 'admins')
                    os.makedirs(dir_path, exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump({"Admins": admins_list}, f, indent=4)
            conn.close()
        except Exception as e:
            print(f"[Admin Manager] SQLite Sync Fallback Error: {e}")
            
    return admins_list

def add_admin(bot_uid, admin_uids):
    uid_str = "".join(c for c in str(bot_uid) if c.isdigit())
    dir_path = os.path.join(BASE_DIR, 'config', 'admins')
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{uid_str}.json")
    
    current_admins = get_admins(uid_str)
    added = 0
    for uid in admin_uids:
        s_uid = "".join(c for c in str(uid) if c.isdigit())
        if s_uid and s_uid not in current_admins:
            current_admins.append(s_uid)
            added += 1
            
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"Admins": current_admins}, f, indent=4)
    except Exception as e:
        print(f"[Admin Manager] Error writing admins JSON file: {e}")
    return added

def remove_admin(bot_uid, admin_uids):
    uid_str = "".join(c for c in str(bot_uid) if c.isdigit())
    dir_path = os.path.join(BASE_DIR, 'config', 'admins')
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{uid_str}.json")
    
    current_admins = get_admins(uid_str)
    removed = 0
    for uid in admin_uids:
        s_uid = "".join(c for c in str(uid) if c.isdigit())
        if s_uid in current_admins:
            current_admins.remove(s_uid)
            removed += 1
            
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"Admins": current_admins}, f, indent=4)
    except Exception as e:
        print(f"[Admin Manager] Error writing admins JSON file: {e}")
    return removed

def can_auto_join(bot_uid, inviter_uid):
    i_uid = "".join(c for c in str(inviter_uid) if c.isdigit())
    if is_owner(i_uid): return True
    if i_uid in get_admins(bot_uid): return True
    return False

def add_guild_member(bot_uid, member_uid, guild_id, player_name):
    # 🟢 ওল্ড প্রজেক্টের গিল্ড মেম্বার হ্যান্ডলার মিসিং ফিক্স:
    # গিল্ড মেম্বাররা ইনভাইট দিলে যাতে AttributeError না খেয়ে তা লোকাল জেসনে অটো সেভ হতে পারে
    uid_str = "".join(c for c in str(bot_uid) if c.isdigit())
    file_path = os.path.join(BASE_DIR, 'config', 'guild_members', f"{uid_str}.json")
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        data = {"members": []}
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        members = [str(u) for u in data.get("members", [])]
        m_uid = "".join(c for c in str(member_uid) if c.isdigit())
        if m_uid not in members:
            members.append(m_uid)
        data["members"] = members
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[Admin Manager] Error adding guild member: {e}")

def load_bot_mood(bot_uid):
    if not os.path.exists(MOOD_FILE): return "normal"
    try:
        with open(MOOD_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(str(bot_uid), "normal")
    except: return "normal"

def save_bot_mood(bot_uid, mood):
    data = {}
    if os.path.exists(MOOD_FILE):
        try:
            with open(MOOD_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        except: pass
    data[str(bot_uid)] = mood
    try:
        with open(MOOD_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
    except: pass

def load_bot_lang(bot_uid):
    if not os.path.exists(LANG_FILE): return "en"
    try:
        with open(LANG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(str(bot_uid), "en")
    except: return "en"

def save_bot_lang(bot_uid, lang):
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        except: pass
    data[str(bot_uid)] = lang
    try:
        with open(LANG_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
    except: pass