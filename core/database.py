# --- START OF FILE core/database.py ---

import os
import sqlite3
import aiosqlite
import json
import asyncio
from threading import Thread

# 🟢 টার্মাক্স ও অ্যান্ড্রয়েডের জন্য DNS প্যাচ (etc/resolv.conf এরর দূর করার জন্য)
import dns.resolver
try:
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
except Exception as e:
    pass

from pymongo import MongoClient

# --- Config & Setup ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://newhrmunna2027_db_user:munna2288@cluster0.xoaeyib.mongodb.net/?appName=Cluster0")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'database.db')

# 🟢 ডাটাবেসে লেখার জন্য গ্লোবাল Async Lock তৈরি করা হলো যাতে একবারে একজনই লিখতে পারে
db_lock = asyncio.Lock()

# --- MongoDB Client Setup ---
mongo_client = None
db = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = mongo_client['Esports_Bot_Panel_2']
    except Exception as e:
        print(f"[MONGO DB] Warning: Could not connect to MongoDB. Sync will be disabled. Error: {e}")
        mongo_client = None

def _push_to_mongo_background(collection_name, primary_key, key_value, data_dict):
    if not mongo_client or not db:
        return
    try:
        collection = db[collection_name]
        clean_data = {k: v for k, v in data_dict.items() if not isinstance(v, (sqlite3.Row))}
        collection.update_one({primary_key: key_value}, {"$set": clean_data}, upsert=True)
    except Exception as e:
        print(f"[Mongo Push Error] Failed to sync {collection_name}: {e}")

def _delete_from_mongo_background(collection_name, primary_key, key_value):
    if not mongo_client or not db:
        return
    try:
        collection = db[collection_name]
        collection.delete_one({primary_key: key_value})
    except Exception as e:
        print(f"[Mongo Delete Error] Failed to delete from {collection_name}: {e}")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, uid TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bots (name TEXT PRIMARY KEY, login_uid TEXT, password TEXT, ingame_uid TEXT, owner TEXT, folder TEXT, bot_number INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS profiles (ingame_uid TEXT PRIMARY KEY, data TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (bot_name TEXT PRIMARY KEY, guild_id TEXT, data TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS panel_users (username TEXT PRIMARY KEY, password TEXT NOT NULL, role TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS global_owners (uid TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bot_configs (bot_uid TEXT PRIMARY KEY, bot_name TEXT, guild_id TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bot_admins (bot_uid TEXT NOT NULL, admin_uid TEXT NOT NULL, UNIQUE(bot_uid, admin_uid))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bot_temp_members (bot_uid TEXT NOT NULL, member_uid TEXT NOT NULL, player_name TEXT, guild_id TEXT, expires_at INTEGER, UNIQUE(bot_uid, member_uid))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved_uids (id INTEGER PRIMARY KEY AUTOINCREMENT, bot_uid TEXT NOT NULL, saved_uid TEXT NOT NULL, UNIQUE(bot_uid, saved_uid))''')
    
    conn.commit()
    conn.close()

def sync_save_bot(bot_name, login_uid, login_pass, creator, folder, bot_number=0):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO bots (name, login_uid, password, owner, folder, bot_number) VALUES (?, ?, ?, ?, ?, ?)''', 
                   (bot_name, login_uid, login_pass, creator, folder, bot_number))
    conn.commit()
    conn.close()
    data_dict = {"name": bot_name, "account": {"uid": login_uid, "password": login_pass}}
    Thread(target=_push_to_mongo_background, args=('bot_accounts', '_id', bot_name, data_dict)).start()

def sync_delete_bot(bot_name):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bots WHERE name = ?", (bot_name,))
    conn.commit()
    conn.close()
    Thread(target=_delete_from_mongo_background, args=('bot_accounts', '_id', bot_name)).start()

def sync_save_profile(uid, profile_data):
    if not uid: return
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO profiles (ingame_uid, data) VALUES (?, ?)", (str(uid), json.dumps(profile_data)))
    conn.commit()
    conn.close()

def sync_get_all_bots():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bots")
    columns = [col[0] for col in cursor.description]
    bots = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return bots

def sync_add_saved_uid(bot_uid, saved_uid):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO saved_uids (bot_uid, saved_uid) VALUES (?, ?)", (str(bot_uid), str(saved_uid)))
    conn.commit()
    conn.close()

def sync_get_saved_uids(bot_uid):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    cursor.execute("SELECT saved_uid FROM saved_uids WHERE bot_uid = ? ORDER BY id ASC LIMIT 10", (str(bot_uid),))
    uids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return uids

def sync_remove_saved_uid(bot_uid, saved_uid):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_uids WHERE bot_uid = ? AND saved_uid = ?", (str(bot_uid), str(saved_uid)))
    conn.commit()
    conn.close()

def sync_clear_saved_uids(bot_uid):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_uids WHERE bot_uid = ?", (str(bot_uid),))
    conn.commit()
    conn.close()

def sync_add_global_owner(uid):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO global_owners (uid) VALUES (?)", (str(uid),))
    conn.commit()
    conn.close()

def sync_is_global_owner(uid):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM global_owners WHERE uid = ?", (str(uid),))
    res = cursor.fetchone()
    conn.close()
    return bool(res)

async def async_get_all_bots():
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bots") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def async_save_bot(bot_name, login_uid, login_pass, creator, folder, bot_number=0):
    async with db_lock:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute('''INSERT OR REPLACE INTO bots (name, login_uid, password, owner, folder, bot_number) VALUES (?, ?, ?, ?, ?, ?)''', 
                             (bot_name, login_uid, login_pass, creator, folder, bot_number))
            await db.commit()
    data_dict = {"name": bot_name, "account": {"uid": login_uid, "password": login_pass}}
    Thread(target=_push_to_mongo_background, args=('bot_accounts', '_id', bot_name, data_dict)).start()

async def async_delete_bot(bot_name):
    async with db_lock:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute("DELETE FROM bots WHERE name = ?", (bot_name,))
            await db.commit()
    Thread(target=_delete_from_mongo_background, args=('bot_accounts', '_id', bot_name)).start()

async def async_save_profile(uid, profile_data):
    if not uid: return
    async with db_lock:
        try:
            async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                await db.execute("PRAGMA busy_timeout=30000;")
                await db.execute("INSERT OR REPLACE INTO profiles (ingame_uid, data) VALUES (?, ?)", (str(uid), json.dumps(profile_data)))
                await db.commit()
        except Exception as e:
            print(f"[Async DB Error] Save Profile Failed: {e}")

async def async_get_profile(uid):
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        async with db.execute("SELECT data FROM profiles WHERE ingame_uid = ?", (str(uid),)) as cursor:
            row = await cursor.fetchone()
            if row: return json.loads(row[0])
    return None

async def async_add_saved_uid(bot_uid, saved_uid):
    async with db_lock:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute("INSERT OR IGNORE INTO saved_uids (bot_uid, saved_uid) VALUES (?, ?)", (str(bot_uid), str(saved_uid)))
            await db.commit()

async def async_get_saved_uids(bot_uid):
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        async with db.execute("SELECT saved_uid FROM saved_uids WHERE bot_uid = ? ORDER BY id ASC LIMIT 10", (str(bot_uid),)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def async_remove_saved_uid(bot_uid, saved_uid):
    async with db_lock:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute("DELETE FROM saved_uids WHERE bot_uid = ? AND saved_uid = ?", (str(bot_uid), str(saved_uid)))
            await db.commit()

async def async_clear_saved_uids(bot_uid):
    async with db_lock:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute("DELETE FROM saved_uids WHERE bot_uid = ?", (str(bot_uid),))
            await db.commit()

async def async_is_global_owner(uid):
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        async with db.execute("SELECT 1 FROM global_owners WHERE uid = ?", (str(uid),)) as cursor:
            res = await cursor.fetchone()
            return bool(res)

async def async_add_temp_member(bot_uid, member_uid, player_name, guild_id, expires_at):
    async with db_lock:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute('''INSERT OR REPLACE INTO bot_temp_members (bot_uid, member_uid, player_name, guild_id, expires_at) 
                                VALUES (?, ?, ?, ?, ?)''', (str(bot_uid), str(member_uid), player_name, str(guild_id), int(expires_at)))
            await db.commit()

async def async_get_valid_temp_members(bot_uid, current_timestamp):
    async with db_lock:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=30000;")
            await db.execute("DELETE FROM bot_temp_members WHERE bot_uid = ? AND expires_at < ?", (str(bot_uid), int(current_timestamp)))
            await db.commit()
            
            async with db.execute("SELECT member_uid FROM bot_temp_members WHERE bot_uid = ?", (str(bot_uid),)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

init_db()

# --- END OF FILE core/database.py ---