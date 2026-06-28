# -*- coding: utf-8 -*-
# app.py - Unified Garena Command Hub & Dual-App Web Panel Core (OB54 Synced)

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import sys
import json
import random
import time
import asyncio
import aiohttp
import aiosqlite
import threading
from functools import wraps
from contextlib import asynccontextmanager

# Garena imports linking
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import garena_api as bot_module

# 🟢 DYNAMIC ALIAS MAPPING
friend_list = bot_module
add_friend = bot_module
remove_friend = bot_module
pending_list = bot_module
accept_request = bot_module
reject_request = bot_module
guild_info = bot_module
member_list = bot_module
join_guild = bot_module
leave_guild = bot_module

import mongo_sync

app = Flask(__name__)
app.secret_key = 'super_secret_esports_bot_panel_key_2025_neon_chassis'

# REGISTER BLUEPRINT
from web import web_api
app.register_blueprint(web_api)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'config', 'database.db')

MANAGER_HOST = '127.0.0.1'
MANAGER_PORT = 50000

SYNCED_BOTS_SESSION = set()

try:
    print("[SYSTEM] Fetching latest data from MongoDB to SQLite...")
    mongo_sync.init_sqlite()
    mongo_sync.pull_all_from_mongo()
except Exception as e:
    print(f"[SYSTEM ERROR] SQLite Init/Pull failed: {e}")

@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH, timeout=30.0)
    try:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout = 30000;")
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()

def login_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'username' not in session: 
            return redirect(url_for('login'))
        return await f(*args, **kwargs)
    return decorated_function

async def is_authorized(bot_name):
    if session.get('role') == 'owner': return True
    async with get_db() as db:
        async with db.execute("SELECT folder FROM bots WHERE name=?", (bot_name,)) as cursor:
            row = await cursor.fetchone()
            if row and row['folder'] == session.get('username'): return True
    return False

async def get_bot_credentials(bot_name):
    async with get_db() as db:
        async with db.execute("SELECT login_uid, password FROM bots WHERE name=?", (bot_name,)) as cursor:
            row = await cursor.fetchone()
            if row: return row['login_uid'], row['password']
    return None, None

async def send_manager_command(payload):
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(MANAGER_HOST, MANAGER_PORT), timeout=20.0)
        writer.write(json.dumps(payload).encode('utf-8'))
        await writer.drain()
        data = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk: break
            data += chunk
        writer.close()
        await writer.wait_closed()
        if not data: return {"status": "error", "msg": "Manager closed connection without sending data."}
        return json.loads(data.decode('utf-8', errors='replace'))
    except Exception as e:
        return {"status": "error", "msg": f"Manager offline: {e}"}

def format_ff_data(api_data):
    if not api_data: return {}
    
    # 🟢 FIXED: Internal Native API structure mapper
    if "nickname" in api_data and "level" in api_data:
        try:
            head_pic = api_data.get("json_data", {}).get("1", {}).get("12", 902000003)
            banner_id = api_data.get("json_data", {}).get("1", {}).get("11", 901000001)
        except:
            head_pic = 902000003
            banner_id = 901000001
            
        return {
            "basicInfo": {
                "nickname": api_data.get("nickname", "Unknown"),
                "level": api_data.get("level", 0),
                "headPic": head_pic,
                "bannerId": banner_id,
                "region": api_data.get("region", "BD"),
                "liked": api_data.get("likes", 0),
                "createAt": str(api_data.get("created_at", "0")),
                "lastLoginAt": str(api_data.get("last_login", "0"))
            },
            "clanBasicInfo": {
                "clanName": api_data.get("clan_name", "No Guild"),
                "clanId": str(api_data.get("clan_id", "N/A")),
                "captainId": str(api_data.get("leader_uid", "N/A"))
            },
            "socialInfo": {"signature": api_data.get("signature", "No Signature")}
        }

    # Fallback mapping
    def safe_get(dictionary, key, default_value):
        if not isinstance(dictionary, dict): return default_value
        val = dictionary.get(key)
        if val is None or str(val).strip() == "" or str(val).strip().lower() == "none": return default_value
        return val

    b_info = api_data.get("basicInfo") or api_data.get("basic_info") or {}
    p_info = api_data.get("profileInfo") or api_data.get("profile_info") or {}
    c_info = api_data.get("clanBasicInfo") or api_data.get("clan_basic_info") or {}
    cap_info = api_data.get("captainBasicInfo") or api_data.get("captain_basic_info") or {}
    s_info = api_data.get("socialInfo") or api_data.get("social_info") or {}
    
    head_pic = safe_get(p_info, "avatarId", None) or safe_get(p_info, "avatar_id", None) or safe_get(cap_info, "headPic", None) or safe_get(b_info, "headPic", None) or 902000003
    banner_id = safe_get(cap_info, "bannerId", None) or safe_get(b_info, "bannerId", None) or 901000001
    
    raw_login = b_info.get('lastLoginAt') or b_info.get('last_login_at')
    if not raw_login:
        for k, v in b_info.items():
            if 'login' in k.lower(): raw_login = v; break
            
    raw_create = b_info.get('createAt') or b_info.get('create_at')
    if not raw_create:
        for k, v in b_info.items():
            if 'create' in k.lower(): raw_create = v; break

    return {
        "basicInfo": {
            "nickname": safe_get(b_info, "nickname", "Unknown"),
            "level": safe_get(b_info, "level", 0),
            "headPic": head_pic,
            "bannerId": banner_id,
            "region": safe_get(b_info, "region", "BD"),
            "liked": safe_get(b_info, "liked", 0),
            "createAt": str(raw_create or 0),
            "lastLoginAt": str(raw_login or 0)
        },
        "clanBasicInfo": {
            "clanName": safe_get(c_info, "clan_name", "No Guild") if safe_get(c_info, "clan_name", "No Guild") != "No Guild" else safe_get(c_info, "clanName", "No Guild"),
            "clanId": str(safe_get(c_info, "clan_id", "N/A") if safe_get(c_info, "clan_id", "N/A") != "N/A" else safe_get(c_info, "clanId", "N/A")),
            "captainId": str(safe_get(c_info, "captain_id", "N/A") if safe_get(c_info, "captain_id", "N/A") != "N/A" else safe_get(c_info, "captainId", "N/A"))
        },
        "socialInfo": {"signature": safe_get(s_info, "signature", "No Signature")}
    }

# 🟢 DYNAMIC FRIEND-TO-ADMIN AUTO OVERWRITE SYNC SYSTEM (WITH INDIVIDUAL FILE SYNC)
async def sync_friends_to_bot_admins(bot_name, ingame_uid, token):
    if not ingame_uid or not token:
        return False
    try:
        res = bot_module.get_active_friend_list(token)
        if not res.get("success") or "friends" not in res:
            print(f"[ADMIN AUTO-SYNC] ⚠️ Friendlist fetch failed or empty for Bot '{bot_name}'.")
            return False
        
        friend_uids = [str(f["uid"]).strip() for f in res["friends"] if f.get("uid") and str(f["uid"]) != str(ingame_uid)]
        
        async with get_db() as db:
            async with db.execute("SELECT data FROM profiles WHERE ingame_uid=?", (ingame_uid,)) as cur:
                prow = await cur.fetchone()
                clan_id = ""
                bot_display_name = bot_name
                if prow:
                    pdata = json.loads(prow['data'])
                    clan_id = pdata.get('clanBasicInfo', {}).get('clanId', '')
                    bot_display_name = pdata.get('basicInfo', {}).get('nickname', bot_name)
            
            admin_data = {
                "Bot_Name": bot_display_name,
                "Guild_ID": str(clan_id),
                "Admins": friend_uids 
            }
            
            await db.execute("INSERT OR REPLACE INTO admins (bot_name, guild_id, data) VALUES (?, ?, ?)",
                             (bot_name, str(clan_id), json.dumps(admin_data)))
            await db.commit()
            
        # 🟢 প্রতিটি বটের নিজস্ব এডমিন JSON ফাইলে সিঙ্ক করার প্রসেস (বিনা ডাটাবেস লকিংয়ে ব্যবহারের জন্য)
        try:
            dir_path = os.path.join(BASE_DIR, 'config', 'admins')
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, f"{ingame_uid}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({"Admins": friend_uids}, f, indent=4)
            print(f"[ADMIN AUTO-SYNC] 🔄 Saved {len(friend_uids)} admins to separate JSON file: {file_path}")
        except Exception as file_err:
            print(f"[ADMIN AUTO-SYNC] Error saving separate admin file: {file_err}")

        try:
            threading.Thread(target=mongo_sync.push_admin_to_mongo, args=(bot_name, admin_data)).start()
        except Exception as m_err:
            print(f"[ADMIN AUTO-SYNC] MongoDB Push Error: {m_err}")
            
        print(f"[ADMIN AUTO-SYNC] ✅ Successfully overwritten {len(friend_uids)} friends as admins for Bot '{bot_name}'.")
        return True
    except Exception as e:
        print(f"[ADMIN AUTO-SYNC ERROR] Failed to overwrite admins for bot {bot_name}: {e}")
        return False

# ==========================================
# CENTRAL ROUTING CONTROLLER
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        async with get_db() as db:
            async with db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)) as cursor:
                user = await cursor.fetchone()
                if user:
                    session['username'], session['role'] = user['username'], user['role']
                    return redirect(url_for('index'))
        return render_template('login.html', error="Invalid Username or Password!")
    if 'username' in session: return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
async def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
async def index():
    return render_template('index.html', username=session.get('username'), role=session.get('role'))

@app.route('/manager/<bot_name>')
@login_required
async def bot_manager_view(bot_name):
    if not await is_authorized(bot_name):
        return redirect(url_for('index'))
        
    session['current_manage_bot'] = bot_name
        
    async with get_db() as db:
        async with db.execute("SELECT ingame_uid, login_uid, password FROM bots WHERE name=?", (bot_name,)) as cursor:
            row = await cursor.fetchone()
            if row:
                ingame_uid = row['ingame_uid']
                login_uid = row['login_uid']
                password = row['password']
            else:
                ingame_uid, login_uid, password = None, None, None
            
    if login_uid and password:
        token, err = bot_module.get_token_from_uid_password(login_uid, password)
        if token:
            bot_module.save_session({"uid": login_uid, "password": password, "token": token}, bot_name)
            if ingame_uid:
                bot_module.refresh_self_profile_cache(token, bot_name)
        
    return render_template('manager.html', bot_name=bot_name, ingame_uid=ingame_uid, username=session.get('username'), role=session.get('role'))

@app.route('/api/users', methods=['GET'])
@login_required
async def get_users_list():
    try:
        if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Access Denied"})
        user_list = []
        async with get_db() as db:
            async with db.execute("SELECT * FROM users") as cursor:
                users = await cursor.fetchall()
            for u in users:
                async with db.execute("SELECT COUNT(*) FROM bots WHERE folder=?", (u['username'],)) as bcur:
                    bot_count = (await bcur.fetchone())[0]
                user_list.append({"username": u['username'], "password": u['password'], "role": u['role'], "uid": u['uid'], "bots": bot_count})
        return jsonify({"status": "success", "users": user_list})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/users/action', methods=['POST'])
@login_required
async def manage_users():
    try:
        if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Access Denied"})
        data = request.json
        action = data.get('action')
        async with get_db() as db:
            if action == 'add':
                uname = data.get('username')
                async with db.execute("SELECT username FROM users WHERE username=?", (uname,)) as cur:
                    if await cur.fetchone(): return jsonify({"status": "error", "msg": "User already exists!"})
                new_uid = str(random.randint(10000, 99999))
                await db.execute("INSERT INTO users (username, password, role, uid) VALUES (?, ?, ?, ?)", (uname, data.get('password'), data.get('role'), new_uid))
            elif action == 'edit':
                old_uname = data.get('old_username')
                new_uname = data.get('new_username')
                if old_uname != new_uname:
                    async with db.execute("SELECT username FROM users WHERE username=?", (new_uname,)) as cur:
                        if await cur.fetchone(): return jsonify({"status": "error", "msg": "Username already taken!"})
                    await db.execute("UPDATE users SET username=?, password=?, role=? WHERE username=?", (new_uname, data.get('password'), data.get('role'), old_uname))
                    await db.execute("UPDATE bots SET folder=?, owner=? WHERE folder=?", (new_uname, new_uname, old_uname))
                else:
                    await db.execute("UPDATE users SET password=?, role=? WHERE username=?", (data.get('password'), data.get('role'), old_uname))
            elif action == 'delete':
                uname = data.get('username')
                if uname == session.get('username'): return jsonify({"status": "error", "msg": "Cannot delete yourself!"})
                await db.execute("DELETE FROM users WHERE username=?", (uname,))
            await db.commit()
        
        threading.Thread(target=mongo_sync.push_user_to_mongo).start()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/bots', methods=['GET'])
@login_required
async def get_bots():
    global SYNCED_BOTS_SESSION
    try:
        my_role = session.get('role')
        my_uname = session.get('username')

        manager_res = await send_manager_command({"command": "status"})
        if manager_res.get("status") != "success": 
            return jsonify({"status": "error", "msg": manager_res.get("msg", "Bot Manager is Offline!")})

        status_data = manager_res.get("data", {})
        bot_list = []
        system_users = []

        async with get_db() as db_conn:
            if my_role == 'owner':
                async with db_conn.execute("SELECT username FROM users") as cur:
                    system_users = [row['username'] for row in await cur.fetchall()]
            else: 
                system_users = [my_uname]

            async with db_conn.execute("SELECT * FROM bots") as cursor:
                bots = await cursor.fetchall()
                
            for bot in bots:
                if not bot['name'] or str(bot['name']).strip().lower() in ['null', 'undefined', '']:
                    await db_conn.execute("DELETE FROM bots WHERE name=?", (bot['name'],))
                    await db_conn.commit()
                    threading.Thread(target=mongo_sync.delete_bot_from_mongo, args=(bot['name'],)).start()
                    continue

                if my_role != 'owner' and bot['folder'] != my_uname: 
                    continue
                    
                mgr_info = status_data.get(bot['name'], {})
                current_ingame_uid = mgr_info.get('ingame_uid') or bot['ingame_uid']
                
                if mgr_info.get('ingame_uid') and mgr_info.get('ingame_uid') != bot['ingame_uid']:
                    await db_conn.execute("UPDATE bots SET ingame_uid=? WHERE name=?", (current_ingame_uid, bot['name']))
                    await db_conn.commit()

                profile_data = {}
                if current_ingame_uid:
                    async with db_conn.execute("SELECT data FROM profiles WHERE ingame_uid=?", (current_ingame_uid,)) as pcur:
                        prow = await pcur.fetchone()
                        if prow: 
                            profile_data = json.loads(prow['data'])
                            clan_id = profile_data.get('clanBasicInfo', {}).get('clanId', '')
                            bot_display_name = profile_data.get('basicInfo', {}).get('nickname', bot['name'])
                            
                            async with db_conn.execute("SELECT data FROM admins WHERE bot_name=?", (bot['name'],)) as acur:
                                arow = await acur.fetchone()
                                admin_data = json.loads(arow['data']) if arow else {"Bot_Name": bot_display_name, "Guild_ID": str(clan_id), "Admins":[]}
                                if str(admin_data.get('Guild_ID')) != str(clan_id) or admin_data.get('Bot_Name') != bot_display_name:
                                    admin_data['Guild_ID'] = str(clan_id)
                                    admin_data['Bot_Name'] = bot_display_name
                                    await db_conn.execute("INSERT OR REPLACE INTO admins (bot_name, guild_id, data) VALUES (?, ?, ?)", (bot['name'], str(clan_id), json.dumps(admin_data)))
                                    await db_conn.commit()
                                    threading.Thread(target=mongo_sync.push_admin_to_mongo, args=(bot['name'], admin_data)).start()

                    if bot['name'] not in SYNCED_BOTS_SESSION and mgr_info.get('state') == 'ON':
                        garena_token, t_err = bot_module.get_active_token(bot['name'])
                        if garena_token:
                            await sync_friends_to_bot_admins(bot['name'], current_ingame_uid, garena_token)
                            SYNCED_BOTS_SESSION.add(bot['name'])

                bot_list.append({
                    "name": bot['name'], "login_uid": bot['login_uid'], "login_pass": bot['password'],
                    "ingame_uid": current_ingame_uid or "", "state": mgr_info.get('state', 'OFF'), 
                    "number": bot['bot_number'], "profile": profile_data or {}, "owner": bot['owner'], "folder": bot['folder']
                })

        return jsonify({"status": "success", "bots": bot_list, "currentUser": my_uname, "role": my_role, "system_users": system_users})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"API Error: {str(e)}"})

@app.route('/api/save_bot', methods=['POST'])
@login_required
async def save_bot():
    try:
        data = request.json
        name = data.get('name').strip()
        login_uid = data.get('uid').strip()
        password = data.get('password').strip()
        folder_name = data.get('folder', session.get('username')).strip() or session.get('username')
        if session.get('role') != 'owner': folder_name = session.get('username')

        async with get_db() as db:
            async with db.execute("SELECT name FROM bots WHERE name=?", (name,)) as cur:
                if await cur.fetchone(): return jsonify({"status": "error", "msg": "Bot name already exists!"})
            async with db.execute("SELECT name FROM bots WHERE login_uid=?", (login_uid,)) as cur:
                if await cur.fetchone(): return jsonify({"status": "error", "msg": "Login UID is already in use!"})
            async with db.execute("SELECT MAX(bot_number) FROM bots") as cur:
                max_num = (await cur.fetchone())[0] or 0
                new_num = max_num + 1

        token, err = bot_module.get_token_from_uid_password(login_uid, password)
        if err:
            return jsonify({"status": "error", "msg": f"Garena auth failed: {err}. Please check UID and Password."})
            
        author_uid = bot_module.decode_author_uid(token)
        if not author_uid:
            return jsonify({"status": "error", "msg": "Failed to decode Garena UID from token."})
            
        res_raw = bot_module.get_player_info_detailed(author_uid, token)
        if not res_raw.get("success"):
            return jsonify({"status": "error", "msg": f"Handshake success, but profile fetch failed: {res_raw.get('message')}"})
            
        formatted_profile = format_ff_data(res_raw)
        ingame_uid = str(author_uid)
        
        bot_module.save_session({"uid": login_uid, "password": password, "token": token}, name)
        bot_module.refresh_self_profile_cache(token, name)
        
        async with get_db() as db:
            await db.execute("""INSERT INTO bots (name, login_uid, password, ingame_uid, owner, folder, bot_number) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                             (name, login_uid, password, ingame_uid, session.get('username'), folder_name, new_num))
            
            await db.execute("INSERT OR REPLACE INTO profiles (ingame_uid, data) VALUES (?, ?)", 
                             (ingame_uid, json.dumps(formatted_profile)))
            await db.commit()

        threading.Thread(target=mongo_sync.push_bot_to_mongo, args=(name, login_uid, password, session.get('username'), folder_name, new_num)).start()
        threading.Thread(target=mongo_sync.push_profile_to_mongo).start()
        
        return jsonify({
            "status": "success",
            "profile": formatted_profile,
            "ingame_uid": ingame_uid
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": f"System Error: {str(e)}"})

@app.route('/api/edit_bot', methods=['POST'])
@login_required
async def edit_bot():
    try:
        if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Only Owners can edit configs."})
        data = request.json
        edit_type, bot_name = data.get('edit_type'), data.get('bot_name')
        if not await is_authorized(bot_name): return jsonify({"status": "error", "msg": "Access Denied."})

        async with get_db() as db:
            if edit_type == 'filename':
                new_name = data.get('new_name')
                if bot_name == new_name: return jsonify({"status": "success"})
                async with db.execute("SELECT name FROM bots WHERE name=?", (new_name,)) as cur:
                    if await cur.fetchone(): return jsonify({"status": "error", "msg": "Name already exists!"})
                await send_manager_command({"command": "stop", "target": bot_name})
                await db.execute("UPDATE bots SET name=? WHERE name=?", (new_name, bot_name))
                await db.execute("UPDATE admins SET bot_name=? WHERE bot_name=?", (new_name, bot_name))
                await db.commit()
                
                old_path = f"config/garena_sessions/{bot_name}_url.json"
                new_path = f"config/garena_sessions/{new_name}_url.json"
                if os.path.exists(old_path): os.rename(old_path, new_path)
                
                threading.Thread(target=mongo_sync.rename_bot_in_mongo, args=(bot_name, new_name)).start()
                await send_manager_command({"command": "restart", "target": new_name})
            elif edit_type == 'credentials':
                uid, password = data.get('uid'), data.get('password')
                async with db.execute("SELECT name FROM bots WHERE login_uid=? AND name!=?", (uid, bot_name)) as cur:
                    if await cur.fetchone(): return jsonify({"status": "error", "msg": "Login UID in use!"})
                if password: await db.execute("UPDATE bots SET login_uid=?, password=? WHERE name=?", (uid, password, bot_name))
                else: await db.execute("UPDATE bots SET login_uid=? WHERE name=?", (uid, bot_name))
                await db.commit()
                async with db.execute("SELECT login_uid, password, owner, folder, bot_number FROM bots WHERE name=?", (bot_name,)) as cur:
                    row = await cur.fetchone()
                    threading.Thread(target=mongo_sync.push_bot_to_mongo, args=(bot_name, row['login_uid'], row['password'], row['owner'], row['folder'], row['bot_number'])).start()
                
                old_path = f"config/garena_sessions/{bot_name}_url.json"
                if os.path.exists(old_path): os.remove(old_path)
                
                await send_manager_command({"command": "restart", "target": bot_name})
            elif edit_type == 'folder':
                new_folder = data.get('folder', session.get('username')).strip() or session.get('username')
                await db.execute("UPDATE bots SET folder=? WHERE name=?", (new_folder, bot_name))
                await db.commit()
                async with db.execute("SELECT login_uid, password, owner, folder, bot_number FROM bots WHERE name=?", (bot_name,)) as cur:
                    row = await cur.fetchone()
                    threading.Thread(target=mongo_sync.push_bot_to_mongo, args=(bot_name, row['login_uid'], row['password'], row['owner'], row['folder'], row['bot_number'])).start()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/control', methods=['POST'])
@login_required
async def control_bot():
    try:
        data = request.json
        command, target = data.get('command'), data.get('target')
        
        if command == 'hard_restart':
            if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Access Denied."})
            return jsonify(await send_manager_command({"command": "hard_restart"}))
        if command == 'delete':
            if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Only Owners can delete bots."})
            async with get_db() as db:
                await db.execute("DELETE FROM bots WHERE name=?", (target,))
                await db.execute("DELETE FROM admins WHERE bot_name=?", (target,))
                await db.commit()
            
            file_path = f"config/garena_sessions/{target}_url.json"
            if os.path.exists(file_path): os.remove(file_path)
            
            threading.Thread(target=mongo_sync.delete_bot_from_mongo, args=(target,)).start()
            return jsonify(await send_manager_command(data))
        if str(target).startswith('folder:'):
            folder_name = target.split('folder:')[1]
            if session.get('role') != 'owner' and folder_name != session.get('username'): return jsonify({"status": "error", "msg": "Access Denied."})
            async with get_db() as db:
                async with db.execute("SELECT name FROM bots WHERE folder=?", (folder_name,)) as cur:
                    bots = await cur.fetchall()
                    for b in bots: await send_manager_command({"command": command, "target": b['name']})
            return jsonify({"status": "success", "msg": f"Command sent to folder: {folder_name}"})
        if target == 'all':
            if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Access Denied."})
            return jsonify(await send_manager_command(data))
        if not await is_authorized(target): return jsonify({"status": "error", "msg": "Access Denied."})
        return jsonify(await send_manager_command(data))
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/action/change_name', methods=['POST'])
@login_required
async def change_name():
    try:
        data = request.json
        bot_name, new_nickname, ingame_uid = data.get('bot_name'), data.get('new_nickname'), data.get('ingame_uid')
        if not await is_authorized(bot_name): return jsonify({"status": "error", "msg": "Access Denied!"})
        login_uid, login_pass = await get_bot_credentials(bot_name)
        if not login_uid: return jsonify({"status": "error", "msg": "Bot config not found!"})
        
        api_url = "https://out-of-law-name-change.vercel.app/change-name"
        payload = {"uid": login_uid, "password": login_pass, "nickname": new_nickname}
        async with aiohttp.ClientSession() as hs:
            async with hs.get(api_url, params=payload, timeout=45) as resp:
                result = await resp.json()
                if result.get("success"):
                    if ingame_uid:
                        async with get_db() as db:
                            async with db.execute("SELECT data FROM profiles WHERE ingame_uid=?", (ingame_uid,)) as cur:
                                row = await cur.fetchone()
                                if row:
                                    pdata = json.loads(row['data'])
                                    pdata['basicInfo']['nickname'] = new_nickname
                                    await db.execute("UPDATE profiles SET data=? WHERE ingame_uid=?", (json.dumps(pdata), ingame_uid))
                                    await db.commit()
                                    threading.Thread(target=mongo_sync.push_profile_to_mongo).start()
                    return jsonify({"status": "success", "msg": result.get("message", f"Nickname changed to {new_nickname}")})
                return jsonify({"status": "error", "msg": result.get("message", "Failed to change nickname.")})
    except Exception as e: 
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/action/change_bio', methods=['POST'])
@login_required
async def change_bio():
    try:
        data = request.json
        bot_name, ingame_uid = data.get('bot_name'), data.get('ingame_uid')
        if not await is_authorized(bot_name): return jsonify({"status": "error", "msg": "Access Denied!"})
        
        login_uid, login_pass = await get_bot_credentials(bot_name)
        if not login_uid: return jsonify({"status": "error", "msg": "Bot config not found!"})
        
        payload = {"bio1": data.get('bio1', ''), "bio2": data.get('bio2', ''), "bio3": data.get('bio3', ''), "bot_id": str(login_uid), "bot_pass": str(login_pass)}
        async with aiohttp.ClientSession() as hs:
            async with hs.post("https://long-bio-one.vercel.app/run-bio", json=payload, timeout=60) as resp:
                if resp.status == 200:
                    if ingame_uid:
                        api_res = await fetch_profile_native(ingame_uid)
                        if api_res["success"]:
                            async with get_db() as db:
                                await db.execute("INSERT OR REPLACE INTO profiles (ingame_uid, data) VALUES (?, ?)", (ingame_uid, json.dumps(api_res["data"])))
                                await db.commit()
                            threading.Thread(target=mongo_sync.push_profile_to_mongo).start()
                    return jsonify({"status": "success", "msg": "Signature updated successfully!"})
                return jsonify({"status": "error", "msg": f"Bio API Error: {await resp.text()}"})
    except Exception as e: 
        return jsonify({"status": "error", "msg": str(e)})

# 🟢 NATIVE JWT-BASED PROFILE SCANNERS
async def fetch_profile_native(target_uid):
    token = None
    bot_name = None
    
    # ১. টার্গেট ইউআইডি যদি আমাদের নিজের বটের হয়ে থাকে, তবে তার সেশন টোকেন লোড করা হবে
    async with get_db() as db:
        async with db.execute("SELECT name FROM bots WHERE ingame_uid=?", (str(target_uid),)) as cur:
            row = await cur.fetchone()
            if row:
                bot_name = row['name']
                # requests ব্লকিং এড়াতে থ্রেড পুল এক্সিকিউটর ব্যবহার করা হয়েছে
                loop = asyncio.get_running_loop()
                token, _ = await loop.run_in_executor(None, bot_module.get_active_token, bot_name)
    
    # ২. সেশন টোকেন না পাওয়া গেলে, যেকোনো সক্রিয় বটের JWT টোকেন র্যান্ডমাইজ করা হবে
    if not token:
        async with get_db() as db:
            async with db.execute("SELECT name FROM bots") as cur:
                rows = await cur.fetchall()
                for r in rows:
                    loop = asyncio.get_running_loop()
                    t, _ = await loop.run_in_executor(None, bot_module.get_active_token, r['name'])
                    if t:
                        token = t
                        bot_name = r['name']
                        break
                        
    if not token:
        return {"success": False, "msg": "No active Garena bot JWT Token found. Please add or start a bot first."}
        
    try:
        # requests ব্লকিং এড়াতে থ্রেড পুল এক্সিকিউটর ব্যবহার করা হয়েছে
        loop = asyncio.get_running_loop()
        res_raw = await loop.run_in_executor(None, bot_module.get_player_info_detailed, target_uid, token)
        if res_raw and res_raw.get("success"):
            return {"success": True, "data": format_ff_data(res_raw)}
        return {"success": False, "msg": res_raw.get("message", "Garena API Handshake failed.")}
    except Exception as e:
        return {"success": False, "msg": f"Garena Connection Error: {str(e)}"}

@app.route('/api/fetch_profile', methods=['GET', 'POST'])
@login_required
async def fetch_profile():
    try:
        if request.method == 'POST':
            data = request.get_json(force=True)
            uid, save_param, force_refresh = str(data.get('uid')).strip(), data.get('save', True), data.get('force', False)
        else:
            uid = request.args.get('uid', '').strip()
            save_param = request.args.get('save', 'true') != 'false'
            force_refresh = request.args.get('force', 'false') == 'true'
        
        if not uid or uid == 'undefined' or uid == 'null':
            return jsonify({"status": "error", "msg": "Invalid UID provided.", "success": False})

        async with get_db() as db:
            if not force_refresh:
                async with db.execute("SELECT data FROM profiles WHERE ingame_uid=?", (uid,)) as cur:
                    row = await cur.fetchone()
                    if row: 
                        return jsonify({"status": "success", "success": True, "data": json.loads(row['data'])})
                        
        # 🟢 Prioritize native Garena API with bot JWT Token first
        api_res = await fetch_profile_native(uid)
            
        if api_res["success"]:
            if save_param:
                async with get_db() as db:
                    await db.execute("INSERT OR REPLACE INTO profiles (ingame_uid, data) VALUES (?, ?)", (uid, json.dumps(api_res["data"])))
                    await db.commit()
                threading.Thread(target=mongo_sync.push_profile_to_mongo).start()
            return jsonify({"status": "success", "data": api_res["data"], "success": True})
            
        return jsonify({"status": "error", "msg": api_res["msg"], "success": False})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e), "success": False})

@app.route('/api/admin', methods=['GET'])
@login_required
async def get_admin():
    try:
        uid = request.args.get('uid') 
        bot_name = None
        async with get_db() as db:
            async with db.execute("SELECT name FROM bots WHERE ingame_uid=?", (uid,)) as cur:
                row = await cur.fetchone()
                if row: bot_name = row['name']
            if bot_name:
                async with get_db() as db:
                    async with db.execute("SELECT data FROM admins WHERE bot_name=?", (bot_name,)) as cur:
                        arow = await cur.fetchone()
                        if arow: return jsonify({"status": "success", "data": json.loads(arow['data'])})
                    
        default_data = {"Bot_Name": bot_name or "Unknown", "Guild_ID": "", "Admins": []}
        return jsonify({"status": "success", "data": default_data})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/admin/action', methods=['POST'])
@login_required
async def admin_action():
    try:
        data = request.json
        action = data.get('action')
        bot_name = data.get('bot_name')
        admin_uid = str(data.get('admin_uid') or data.get('adminId') or data.get('uid') or '').strip()

        if not bot_name:
            b_uid = data.get('bot_uid') or data.get('ingame_uid') or data.get('uid')
            if b_uid:
                async with get_db() as db:
                    async with db.execute("SELECT name FROM bots WHERE ingame_uid=? OR login_uid=? OR name=?", (str(b_uid), str(b_uid), str(b_uid))) as cur:
                        row = await cur.fetchone()
                        if row: bot_name = row['name']

        if not bot_name or not admin_uid:
            return jsonify({"status": "error", "msg": "Missing Data. Require bot_name and admin_uid."})

        if not await is_authorized(bot_name): 
            return jsonify({"status": "error", "msg": "Access Denied."})
            
        async with get_db() as db:
            async with db.execute("SELECT guild_id, data FROM admins WHERE bot_name=?", (bot_name,)) as cur:
                row = await cur.fetchone()
                guild_id = row['guild_id'] if row else ""
                admin_data = json.loads(row['data']) if row else {"Bot_Name": bot_name, "Guild_ID": guild_id, "Admins": []}
                
            if 'Admins' not in admin_data: admin_data['Admins'] = []
            current_admins = [str(uid).strip() for uid in admin_data['Admins']]
                
            if action == 'add' and admin_uid not in current_admins:
                current_admins.append(admin_uid)
            elif action == 'remove' and admin_uid in current_admins:
                current_admins.remove(admin_uid)
                    
            admin_data['Admins'] = current_admins
                
            await db.execute("INSERT OR REPLACE INTO admins (bot_name, guild_id, data) VALUES (?, ?, ?)", 
                             (bot_name, guild_id, json.dumps(admin_data)))
            await db.commit()
            
        try: threading.Thread(target=mongo_sync.push_admin_to_mongo, args=(bot_name, admin_data)).start()
        except: pass

        return jsonify({"status": "success", "data": admin_data})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 20881))
    app.run(host='0.0.0.0', port=port, debug=False)