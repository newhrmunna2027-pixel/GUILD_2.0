# filepath: app/routes_bots.py
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import json
import os
import threading
import aiohttp
import bot_core as bot_module
import mongo_sync
from app.database import get_db
from app.decorators import login_required
from app.helpers import (
    is_authorized, get_bot_credentials, send_manager_command,
    format_ff_data, sync_friends_to_bot_admins, sync_guild_members_local,
    fetch_profile_native, SYNCED_BOTS_SESSION
)

bots_bp = Blueprint('bots_bp', __name__)

@bots_bp.route('/manager/<bot_name>')
@login_required
async def bot_manager_view(bot_name):
    if not await is_authorized(bot_name, session.get('username'), session.get('role')):
        return redirect(url_for('auth_bp.index'))
        
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

@bots_bp.route('/api/bots', methods=['GET'])
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

                        # 🟢 [OFF -> ON Transition Trigger]
                        # যখনই কোনো বটের স্ট্যাটাস OFF থেকে ON হবে, মেমোরি ডিটেক্ট করে ইনস্ট্যান্টলি ডাটা সিঙ্ক করবে
                        # filepath: app/routes_bots.py
# (app/routes_bots.py ফাইলের get_bots ফাংশনের ভেতর OFF -> ON ব্লকের কোডটুকু পরিবর্তন করুন)

                        # 🟢 [নন-ব্লকিং সিকোয়েনশিয়াল কিউ টাস্ক]
                        # বটের স্ট্যাটাস OFF থেকে ON হলে আমরা await দিয়ে ওয়েব প্যানেলকে ব্লক করব না।
                        # আমরা কেবল ব্যাকগ্রাউন্ডে sequential_first_time_sync টাস্কটি পুশ করে দেব।
                        if mgr_info.get('state') == 'ON':
                            if bot['name'] not in SYNCED_BOTS_SESSION:
                                garena_token, t_err = bot_module.get_active_token(bot['name'])
                                if garena_token:
                                    from app.helpers import sequential_first_time_sync
                                    # এপিআই রিকোয়েস্ট ব্যাকগ্রাউন্ড কিউতে ছেড়ে দেওয়া হলো (ব্রাউজার মুহূর্তেই রেন্ডার হবে)
                                    asyncio.create_task(sequential_first_time_sync(bot['name'], current_ingame_uid, garena_token))
                                    SYNCED_BOTS_SESSION.add(bot['name'])
                        else:
                            SYNCED_BOTS_SESSION.discard(bot['name'])

                bot_list.append({
                    "name": bot['name'], "login_uid": bot['login_uid'], "login_pass": bot['password'],
                    "ingame_uid": current_ingame_uid or "", "state": mgr_info.get('state', 'OFF'), 
                    "number": bot['bot_number'], "profile": profile_data or {}, "owner": bot['owner'], "folder": bot['folder']
                })

        return jsonify({"status": "success", "bots": bot_list, "currentUser": my_uname, "role": my_role, "system_users": system_users})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"API Error: {str(e)}"})

@bots_bp.route('/api/save_bot', methods=['POST'])
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
        
        # 🟢 [Onboarding Pipeline]
        # নতুন বট রেজিস্ট্রেশনের নিশ্চিত করার সাথে সাথেই ফ্রেন্ড ও মেম্বারদের কাঁচা লিস্ট এপিআই দিয়ে ফাইলে সেভ করে নেবে
        bot_module.save_session({"uid": login_uid, "password": password, "token": token}, name)
        bot_module.refresh_self_profile_cache(token, name)
        
        await sync_friends_to_bot_admins(name, ingame_uid, token)
        await sync_guild_members_local(name, ingame_uid, token)
        
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

@bots_bp.route('/api/edit_bot', methods=['POST'])
@login_required
async def edit_bot():
    try:
        if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Only Owners can edit configs."})
        data = request.json
        edit_type, bot_name = data.get('edit_type'), data.get('bot_name')
        if not await is_authorized(bot_name, session.get('username'), session.get('role')): return jsonify({"status": "error", "msg": "Access Denied."})

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

@bots_bp.route('/api/control', methods=['POST'])
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
        if not await is_authorized(target, session.get('username'), session.get('role')): return jsonify({"status": "error", "msg": "Access Denied."})
        return jsonify(await send_manager_command(data))
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@bots_bp.route('/api/action/change_name', methods=['POST'])
@login_required
async def change_name():
    try:
        data = request.json
        bot_name, new_nickname, ingame_uid = data.get('bot_name'), data.get('new_nickname'), data.get('ingame_uid')
        if not await is_authorized(bot_name, session.get('username'), session.get('role')): return jsonify({"status": "error", "msg": "Access Denied!"})
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

@bots_bp.route('/api/action/change_bio', methods=['POST'])
@login_required
async def change_bio():
    try:
        data = request.json
        bot_name, ingame_uid = data.get('bot_name'), data.get('ingame_uid')
        if not await is_authorized(bot_name, session.get('username'), session.get('role')): return jsonify({"status": "error", "msg": "Access Denied!"})
        
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

@bots_bp.route('/api/fetch_profile', methods=['GET', 'POST'])
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

@bots_bp.route('/api/admin', methods=['GET'])
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
                async with db.execute("SELECT data FROM admins WHERE bot_name=?", (bot_name,)) as cur:
                    arow = await cur.fetchone()
                    if arow: return jsonify({"status": "success", "data": json.loads(arow['data'])})
                    
        default_data = {"Bot_Name": bot_name or "Unknown", "Guild_ID": "", "Admins": []}
        return jsonify({"status": "success", "data": default_data})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@bots_bp.route('/api/admin/action', methods=['POST'])
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

        if not await is_authorized(bot_name, session.get('username'), session.get('role')): 
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
