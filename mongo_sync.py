# filepath: mongo_sync.py
# -*- coding: utf-8 -*-
# START OF FILE mongo_sync.py
import asyncio
import os
import json
import sqlite3
import random
import threading
import time
import uuid
import ssl
import sys
import re
from datetime import datetime

# পরম পাথ (Absolute Path) ও ডিরেক্টরি রেজোলিউশন প্যাচ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 🟢 টার্মাক্স এবং অ্যান্ড্রয়েড এনভায়রনমেন্ট ডিএনএস প্যাচ (resolv.conf ক্র্যাশ এড়াতে)
import dns.resolver
try:
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
except Exception as e:
    pass

# Safe PyMono Import
try:
    from pymongo import MongoClient
except ImportError:
    print("[!] 'pymongo' is not installed. Please run 'pip install pymongo'")

# Safe Crypto Import for Garena Handshakes
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    import certifi
    import aiohttp
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("[!] Cryptographic libraries are missing. Run 'pip install pycryptodome aiohttp certifi'")

# 🟢 Garena API ইমপোর্ট লিঙ্ক এবং ফলব্যাক হ্যান্ডলার
try:
    import garena_api as bot_module
except ImportError:
    print("[!] 'garena_api.py' not found in same folder. Local imports might be restricted.")

# MongoDB Connection String Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://newhrmunna2027_db_user:munna2288@cluster0.xoaeyib.mongodb.net/?appName=Cluster0")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db_mongo = client['Esports_Bot_Panel_2']
    col_system = db_mongo['system_configs']  
    col_accounts = db_mongo['bot_accounts']  
    col_admins = db_mongo['bot_admins']
    col_friends = db_mongo['bot_friends']
    col_guild_members = db_mongo['guild_members']
except Exception as e:
    print(f"[MONGO ERROR] Connection Failed: {e}")

DB_PATH = os.path.join(BASE_DIR, 'config', 'database.db')

# ==========================================
# SQLITE INTERACTIVE FUNCTIONS
# ==========================================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

def init_sqlite():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, uid TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS bots (name TEXT PRIMARY KEY, login_uid TEXT, password TEXT, ingame_uid TEXT, owner TEXT, folder TEXT, bot_number INTEGER)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS profiles (ingame_uid TEXT PRIMARY KEY, data TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS admins (bot_name TEXT PRIMARY KEY, guild_id TEXT, data TEXT)""")
    conn.commit()
    conn.close()

def get_all_active_bots_local():
    init_sqlite()
    conn = get_db_connection()
    cursor = conn.cursor()
    # 🟢 ইন-গেম ইউআইডি ওভাররাইটার সেফটি কলাম যুক্ত করা হয়েছে
    cursor.execute("SELECT name, login_uid, password, ingame_uid FROM bots WHERE login_uid IS NOT NULL AND login_uid != ''")
    rows = cursor.fetchall()
    conn.close()
    return [{"name": r[0], "uid": r[1], "password": r[2], "ingame_uid": r[3]} for r in rows]

# ========================================================
# 🚀 CORE GARENA API SYNC JOBS (NATIVE INTEGRATION WITH garena_api)
# ========================================================
async def fetch_bot_guild_members(name, bot_uid, bot_pass, ingame_uid=None):
    """গিল্ড মেম্বারদের লিস্ট সংগ্রহ করে ক্লাউড মঙ্গোডিবি এবং লোকাল ফাইলে সিঙ্ক করার ফাংশন"""
    try:
        loop = asyncio.get_event_loop()
        
        # ১. সচল টোকেন সংগ্রহ করা
        token, err = await loop.run_in_executor(None, bot_module.get_token_from_uid_password, bot_uid, bot_pass)
        if not token:
            print(f"[!] Guild Sync Failed for {name}: Garena Auth failed: {err}")
            return
            
        # ২. বটের গেম প্রোফাইল থেকে কারেন্ট গিল্ড আইডি বের করা
        profile_res = await loop.run_in_executor(None, bot_module.get_player_info_detailed, str(bot_uid), token)
        if not profile_res or not profile_res.get("success"):
            print(f"[!] Guild Sync Failed for {name}: Could not fetch bot profile.")
            return
            
        clan_id = profile_res.get("clan_id")
        if not clan_id or clan_id == "N/A" or str(clan_id) == "0":
            return
            
        # ৩. গিল্ডের সমস্ত মেম্বারদের ডাটা ফেচ করা
        res_guild = await loop.run_in_executor(None, bot_module.get_guild_member_list, token, str(clan_id))
        if res_guild.get("success"):
            member_uids = []
            if res_guild.get("leader") and "uid" in res_guild["leader"]:
                member_uids.append(str(res_guild["leader"]["uid"]))
            if res_guild.get("acting_leader") and "uid" in res_guild["acting_leader"]:
                member_uids.append(str(res_guild["acting_leader"]["uid"]))
            for officer in res_guild.get("officers", []):
                if "uid" in officer:
                    member_uids.append(str(officer["uid"]))
            for member in res_guild.get("members", []):
                if "uid" in member:
                    member_uids.append(str(member["uid"]))
                
            if member_uids:
                # মঙ্গোডিবি ক্লাউড আপডেট
                col_guild_members.update_one(
                    {'_id': name},
                    {'$set': {'clan_id': str(clan_id), 'members': member_uids, 'last_update': time.time()}},
                    upsert=True
                )
                print(f"[✓] Guild members synced to MongoDB for {name}. Total: {len(member_uids)}")
                
                # 🟢 লোকাল মেম্বার ফাইল ফুল ওভাররাইট/রিপ্লেস সেফটি প্যাচ
                try:
                    file_dir = os.path.join(BASE_DIR, 'config', 'guild_members')
                    os.makedirs(file_dir, exist_ok=True)
                    
                    resolved_uid = ingame_uid or profile_res.get("uid") or bot_uid
                    clean_uid = "".join(c for c in str(resolved_uid) if c.isdigit())
                    file_path = os.path.join(file_dir, f"{clean_uid}.json")
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump({"members": member_uids}, f, indent=4)
                    print(f"[✓] Guild members saved locally for {name} ({clean_uid}.json). Total: {len(member_uids)}")
                except Exception as file_err:
                    print(f"[!] Local file write error in mongo_sync for {name}: {file_err}")
    except Exception as e:
        print(f"[!] Guild Sync Exception for {name}: {e}")

async def sync_bot_friends_list(name, bot_uid, bot_pass):
    """ফ্রেন্ডলিস্ট সংগ্রহ করে ক্লাউড মঙ্গোডিবিতে সিঙ্ক করার ফাংশন"""
    try:
        loop = asyncio.get_event_loop()
        
        # ১. সচল টোকেন সংগ্রহ করা
        token, err = await loop.run_in_executor(None, bot_module.get_token_from_uid_password, bot_uid, bot_pass)
        if not token:
            print(f"[!] Friends Sync Failed for {name}: Garena Auth failed: {err}")
            return
            
        # ২. ফ্রেন্ডলিস্ট ফেচ এবং মঙ্গোডিবি সিঙ্ক করা
        res_friends = await loop.run_in_executor(None, bot_module.get_active_friend_list, token)
        if res_friends.get("success"):
            friend_uids = [str(f["uid"]) for f in res_friends["friends"]]
            
            if friend_uids:
                col_friends.update_one(
                    {'_id': name},
                    {'$set': {'friends': friend_uids, 'last_update': time.time()}},
                    upsert=True
                )
                print(f"[✓] Friends list synced for {name}. Total: {len(friend_uids)}")
    except Exception as e:
        print(f"[!] Friends Sync Exception for {name}: {e}")

# ==========================================
# DYNAMIC BACKGROUND SYNC SCHEDULER
# ==========================================
async def sync_all_bots_data_loop():
    """সকল রানিং বোতের ফ্রেন্ড এবং গিল্ড ডাটা ডাটাবেজে সিঙ্ক করার লুপ"""
    bots = get_all_active_bots_local()
    if not bots:
        return
        
    print(f"\n[*] Executing Scheduled Data Sync for {len(bots)} Bots...")
    for b in bots:
        try:
            # 1. Sync Friends List
            await sync_bot_friends_list(b['name'], b['uid'], b['password'])
            await asyncio.sleep(1.0)
            
            # 2. Sync Guild Members (লোকাল ডাইনামিক ইন-গেম ইউআইডি ওভাররাইটার সহ)
            await fetch_bot_guild_members(b['name'], b['uid'], b['password'], b.get('ingame_uid'))
            await asyncio.sleep(1.0)
        except Exception as e:
            print(f"[!] Sync error on bot {b['name']}: {e}")

def run_sync_all_bots():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(sync_all_bots_data_loop())
    loop.close()

def start_auto_sync_scheduler():
    """১০ মিনিট অন্তর সিঙ্ক করার ব্যাকগ্রাউন্ড শিডিউলার থ্রেড"""
    def run_schedule():
        print("[MONGO] Scheduled Sync Daemon Active (10m interval)")
        while True:
            try:
                run_sync_all_bots()
            except Exception as e:
                print(f"[!] Scheduler error: {e}")
            time.sleep(600) # Sleep 10 minutes
            
    threading.Thread(target=run_schedule, daemon=True).start()

# ==========================================
# STANDARD CO-ORDINATOR MIGRATION CODES
# ==========================================
def pull_all_from_mongo():
    try:
        init_sqlite()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        bot_owners = {}
        bot_numbers = {}
        
        for doc in col_system.find():
            filename = doc['_id']
            data = doc.get('data', {})
            if filename == 'users.json':
                for uname, udata in data.items():
                    cursor.execute("INSERT OR IGNORE INTO users (username, password, role, uid) VALUES (?, ?, ?, ?)", (uname, udata.get('password'), udata.get('role'), udata.get('uid')))
            elif filename == 'profile.json':
                for ingame_uid, pdata in data.items():
                    cursor.execute("INSERT OR REPLACE INTO profiles (ingame_uid, data) VALUES (?, ?)", (ingame_uid, json.dumps(pdata)))
            elif filename == 'bot_owners.json': bot_owners = data
            elif filename == 'bot_numbers.json': bot_numbers = data

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, password, role, uid) VALUES (?, ?, ?, ?)", ("owner", "owner", "owner", str(random.randint(10000, 99999))))

        # MongoDB থেকে সক্রিয় বোতের তালিকা সিঙ্ক এবং ফ্যান্টম বট ক্লিয়ারেন্স লুপ
        for doc in col_accounts.find():
            name = doc['_id']
            
            if not name or str(name).strip().lower() in ['none', 'null', 'undefined', '']:
                try:
                    col_accounts.delete_one({'_id': name})
                    col_admins.delete_one({'_id': name})
                except Exception: pass
                continue 

            data = doc.get('data', {})
            acc = data.get('account', {})
            owner_info = bot_owners.get(name, {})
            creator = owner_info.get("creator", "owner") if isinstance(owner_info, dict) else owner_info
            folder = owner_info.get("folder", creator) if isinstance(owner_info, dict) else creator
            b_num = bot_numbers.get(name, 0)
            
            cursor.execute("SELECT ingame_uid FROM bots WHERE name=?", (name,))
            row = cursor.fetchone()
            existing_uid = row[0] if row else None
            
            cursor.execute("""INSERT OR REPLACE INTO bots (name, login_uid, password, ingame_uid, owner, folder, bot_number) VALUES (?, ?, ?, ?, ?, ?, ?)""", (name, acc.get('uid'), acc.get('password'), existing_uid, creator, folder, b_num))
                
        for doc in col_admins.find():
            name = doc['_id']
            if not name or str(name).strip().lower() in ['none', 'null', 'undefined', '']:
                try: col_admins.delete_one({'_id': name})
                except: pass
                continue
                
            data = doc.get('data', {})
            cursor.execute("INSERT OR REPLACE INTO admins (bot_name, guild_id, data) VALUES (?, ?, ?)", (name, str(data.get('Guild_ID', '')), json.dumps(data)))
            
        cursor.execute("DELETE FROM bots WHERE name IS NULL OR name = '' OR name = 'null' OR name = 'None' OR name = 'undefined'")
                           
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SYNC ERROR] {e}")

def start_change_stream():
    def watch_db():
        print("[MONGO] Live Sync Started. Listening for changes...")
        while True:
            try:
                pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "replace", "delete"]}}}]
                with client.watch(pipeline) as stream:
                    for change in stream:
                        print("[MONGO] Change detected in Web Panel! Syncing Local DB...")
                        pull_all_from_mongo()
            except Exception as e:
                print(f"[MONGO] Sync Stream Disconnected, reconnecting in 5s... Error: {e}")
                time.sleep(5)
                
    threading.Thread(target=watch_db, daemon=True).start()

def push_user_to_mongo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, password, role, uid FROM users")
    users_data = {row[0]: {"password": row[1], "role": row[2], "uid": row[3]} for row in cursor.fetchall()}
    conn.close()
    try: col_system.update_one({'_id': 'users.json'}, {'$set': {'data': users_data}}, upsert=True)
    except: pass

def push_profile_to_mongo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ingame_uid, data FROM profiles")
    profiles_data = {row[0]: json.loads(row[1]) for row in cursor.fetchall()}
    conn.close()
    try: col_system.update_one({'_id': 'profile.json'}, {'$set': {'data': profiles_data}}, upsert=True)
    except: pass

def push_bot_to_mongo(name, login_uid, password, owner, folder, bot_number):
    if not name or str(name).strip().lower() in ['none', 'null', 'undefined', '']: return
    try:
        col_accounts.update_one({'_id': name}, {'$set': {'data': {"account": {"uid": login_uid, "password": password}}}}, upsert=True)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, owner, folder FROM bots WHERE name IS NOT NULL AND name != ''")
        owners_data = {row[0]: {"creator": row[1], "folder": row[2]} for row in cursor.fetchall()}
        col_system.update_one({'_id': 'bot_owners.json'}, {'$set': {'data': owners_data}}, upsert=True)
        
        cursor.execute("SELECT name, bot_number FROM bots WHERE name IS NOT NULL AND name != ''")
        numbers_data = {row[0]: row[1] for row in cursor.fetchall()}
        col_system.update_one({'_id': 'bot_numbers.json'}, {'$set': {'data': numbers_data}}, upsert=True)
        conn.close()
    except: pass

def push_admin_to_mongo(name, admin_data):
    if not name or str(name).strip().lower() in ['none', 'null', 'undefined', '']: return
    try: col_admins.update_one({'_id': name}, {'$set': {'data': admin_data}}, upsert=True)
    except Exception as e: print(f"[MONGO ERROR] {e}")

def delete_bot_from_mongo(name):
    try: 
        col_accounts.delete_one({'_id': name})
        col_admins.delete_one({'_id': name})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, owner, folder FROM bots WHERE name IS NOT NULL AND name != ''")
        owners_data = {row[0]: {"creator": row[1], "folder": row[2]} for row in cursor.fetchall()}
        col_system.update_one({'_id': 'bot_owners.json'}, {'$set': {'data': owners_data}}, upsert=True)
        cursor.execute("SELECT name, bot_number FROM bots WHERE name IS NOT NULL AND name != ''")
        numbers_data = {row[0]: row[1] for row in cursor.fetchall()}
        col_system.update_one({'_id': 'bot_numbers.json'}, {'$set': {'data': numbers_data}}, upsert=True)
        conn.close()
    except: pass

def rename_bot_in_mongo(old_name, new_name):
    if not new_name or str(new_name).strip().lower() in ['none', 'null', 'undefined', '']: return
    try:
        doc = col_accounts.find_one({'_id': old_name})
        if doc:
            col_accounts.insert_one({'_id': new_name, 'data': doc['data']})
            col_accounts.delete_one({'_id': old_name})
        admin_doc = col_admins.find_one({'_id': old_name})
        if admin_doc:
            col_admins.insert_one({'_id': new_name, 'data': admin_doc['data']})
            col_admins.delete_one({'_id': old_name})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, owner, folder FROM bots WHERE name IS NOT NULL AND name != ''")
        owners_data = {row[0]: {"creator": row[1], "folder": row[2]} for row in cursor.fetchall()}
        col_system.update_one({'_id': 'bot_owners.json'}, {'$set': {'data': owners_data}}, upsert=True)
        cursor.execute("SELECT name, bot_number FROM bots WHERE name IS NOT NULL AND name != ''")
        numbers_data = {row[0]: row[1] for row in cursor.fetchall()}
        col_system.update_one({'_id': 'bot_numbers.json'}, {'$set': {'data': numbers_data}}, upsert=True)
        conn.close()
    except: pass

# Automatically sync on startup
pull_all_from_mongo()
start_change_stream()
start_auto_sync_scheduler()

# END OF FILE mongo_sync.py