# filepath: app/routes_garena.py
# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify, session
import os
import time
import jwt
import asyncio
import aiosqlite
import json
import threading
import bot_core as bot_module
from app.decorators import bp_login_required

garena_bp = Blueprint('garena_bp', __name__)
BASE_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR_LOCAL, '..'))
DB_PATH_LOCAL = os.path.join(ROOT_DIR, 'config', 'database.db')

async def get_bot_token_smart(bot_name):
    session_data = bot_module.load_session(bot_name)
    token = session_data.get("token")
    uid = session_data.get("uid")
    password = session_data.get("password")
    
    if token:
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            if decoded.get("exp", 0) > time.time() + 300:
                return token, None
        except: pass
    
    if not uid or not password:
        async with aiosqlite.connect(DB_PATH_LOCAL) as db:
            async with db.execute("SELECT login_uid, password FROM bots WHERE name=?", (bot_name,)) as cur:
                row = await cur.fetchone()
                if row:
                    uid, password = row[0], row[1]
                else:
                    return None, f"Credentials for '{bot_name}' not found in Database."
    
    new_token, err = bot_module.get_token_from_uid_password(uid, password)
    if err: return None, f"Garena Auth Failed: {err}"
    bot_module.save_session({"uid": uid, "password": password, "token": new_token}, bot_name)
    return new_token, None

async def query_local_profile_cache(uid):
    async with aiosqlite.connect(DB_PATH_LOCAL) as db:
        async with db.execute("SELECT data FROM profiles WHERE ingame_uid=?", (str(uid),)) as cur:
            row = await cur.fetchone()
            if row:
                try: return json.loads(row[0])
                except: return None
    return None

@garena_bp.route('/api/bot/profile')
@bp_login_required
async def api_bot_profile_direct():
    bot_name = session.get('current_manage_bot')
    async with aiosqlite.connect(DB_PATH_LOCAL) as db:
        async with db.execute("SELECT ingame_uid FROM bots WHERE name=?", (bot_name,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                cached = await query_local_profile_cache(row[0])
                if cached:
                    return jsonify({
                        "success": True,
                        "profile": {
                            "uid": str(row[0]),
                            "nickname": cached.get("basicInfo", {}).get("nickname", bot_name),
                            "level": cached.get("basicInfo", {}).get("level", 0),
                            "clan_id": cached.get("clanBasicInfo", {}).get("clanId", "0"),
                            "clan_name": cached.get("clanBasicInfo", {}).get("clanName", "No Guild"),
                            "region": cached.get("basicInfo", {}).get("region", "BD"),
                            "likes": cached.get("basicInfo", {}).get("liked", 0),
                            "signature": cached.get("socialInfo", {}).get("signature", "No Signature"),
                            "last_login": cached.get("basicInfo", {}).get("lastLoginAt", "0"),
                            "created_at": cached.get("basicInfo", {}).get("createAt", "0")
                        }
                    })
    return jsonify({"success": False, "msg": "Failed to sync cached offline profile."})

@garena_bp.route('/api/bot/refresh', methods=['POST'])
@bp_login_required
async def api_bot_refresh_direct():
    bot_name = session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    author_uid = bot_module.decode_author_uid(token)
    res_raw = bot_module.get_player_info_detailed(author_uid, token)
    if res_raw.get("success"):
        bot_module.refresh_self_profile_cache(token, bot_name)
        return jsonify({"success": True, "msg": "Live Garena Cache Refreshed!"})
    return jsonify({"success": False, "msg": "Live Garena Gateway handshake timeout."})

# 🟢 [জাভাস্ক্রিপ্ট ক্র্যাশ প্রটেক্টেড ডাইনামিক ফ্রেন্ড লিস্ট]
@garena_bp.route('/api/friends/list')
@bp_login_required
async def api_friends_list_direct():
    bot_name = session.get('current_manage_bot')
    async with aiosqlite.connect(DB_PATH_LOCAL) as db:
        async with db.execute("SELECT ingame_uid FROM bots WHERE name=?", (bot_name,)) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return jsonify({"success": False, "msg": "Bot details not found."})
            ingame_uid = str(row[0])
            
    file_path = os.path.join(ROOT_DIR, 'config', 'admins', f"{ingame_uid}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get("friends"):
                return jsonify({
                    "success": True,
                    "friends": data.get("friends", []),
                    "json_data": data.get("json_data", {}),
                    "name_json_data": data.get("name_json_data", {})
                })
        except Exception as e: 
            print(f"Error reading friend offline cache: {e}")
            
    return jsonify({"success": False, "msg": "No offline friends cache available. Please wait for sync."})

@garena_bp.route('/api/friends/pending')
@bp_login_required
async def api_friends_pending_direct():
    bot_name = session.get('current_manage_bot') or request.args.get("bot_name")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    res = bot_module.get_pending_request_list(token)
    if res.get("success"):
        return jsonify({"success": True, "requests": res["requests"]})
    return jsonify(res)

@garena_bp.route('/api/friends/add', methods=['POST'])
@bp_login_required
async def api_friends_add_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.add_target_friend(token, uid)
    if success: trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success})

@garena_bp.route('/api/friends/remove', methods=['POST'])
@bp_login_required
async def api_friends_remove_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.delete_active_friend(token, uid)
    if success: trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success})

@garena_bp.route('/api/friends/accept', methods=['POST'])
@bp_login_required
async def api_friends_accept_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.accept_friend_request(token, uid)
    if success: trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success})

@garena_bp.route('/api/friends/reject', methods=['POST'])
@bp_login_required
async def api_friends_reject_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.reject_friend_request(token, uid)
    if success: trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success})

@garena_bp.route('/api/guild/info/<clan_id>')
@bp_login_required
async def api_guild_info_direct(clan_id):
    bot_name = session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, bot_module.get_clan_info_by_id, token, clan_id)
    if res.get("success"):
        g = res["guild_info"]
        return jsonify({"status": "success", "data": {
            "GuildId": g["clan_id"], "GuildName": g["clan_name"], "GuildLevel": g["level"],
            "CurrentMembers": g["total_members"], "MaxMembers": g["max_members"],
            "TotalActivityPoints": g["total_glory"], "GuildRegion": g["region"],
            "GuildSlogan": g["welcome_message"]
        }})
    return jsonify({"status": "error", "msg": res.get("message")})

# 🟢 [জাভাস্ক্রিপ্ট ক্র্যাশ প্রটেক্টেড গিল্ড মেম্বার রেন্ডারিং]
@garena_bp.route('/api/guild/members/<clan_id>')
@bp_login_required
async def api_guild_members_direct(clan_id):
    bot_name = session.get('current_manage_bot')
    async with aiosqlite.connect(DB_PATH_LOCAL) as db:
        async with db.execute("SELECT ingame_uid FROM bots WHERE name=?", (bot_name,)) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return jsonify({"success": False, "msg": "Bot details not found."})
            ingame_uid = str(row[0])
            
    file_path = os.path.join(ROOT_DIR, 'config', 'guild_members', f"{ingame_uid}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # ডাইনামিকালি ফুল মেম্বার জেসন ম্যাপড ডাটা রিটার্ন করা হচ্ছে
            if data.get("success"):
                return jsonify(data)
        except Exception as e: 
            print(f"Error reading guild offline cache: {e}")
        
    return jsonify({"success": False, "msg": "No offline guild member cache available. Please wait for sync."})

@garena_bp.route('/api/guild/join', methods=['POST'])
@bp_login_required
async def api_guild_join_direct():
    bot_name = session.get('current_manage_bot')
    clan_id = request.json.get("clan_id")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, bot_module.request_join_clan, token, clan_id)
    return jsonify({"success": success})

@garena_bp.route('/api/guild/leave', methods=['POST'])
@bp_login_required
async def api_guild_leave_direct():
    bot_name = session.get('current_manage_bot')
    clan_id = request.json.get("clan_id")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, bot_module.quit_current_clan, token, clan_id)
    return jsonify({"success": success})

@garena_bp.route('/api/bot/nickname', methods=['POST'])
@bp_login_required
async def api_bot_nickname_direct():
    bot_name = session.get('current_manage_bot')
    new_nick = request.json.get("nickname")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    res = bot_module.change_nickname_native(token, new_nick)
    return jsonify(res)

@garena_bp.route('/api/bot/bio', methods=['POST'])
@bp_login_required
async def api_bot_bio_direct():
    bot_name = session.get('current_manage_bot')
    new_bio = request.json.get("bio")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    res = bot_module.update_bio_native(token, new_bio)
    return jsonify(res)

@garena_bp.route('/api/bot/duo', methods=['POST'])
@bp_login_required
async def api_bot_duo_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    res = bot_module.check_duo_native(token, uid)
    return jsonify(res)

@garena_bp.route('/api/guild/info')
@bp_login_required
async def api_guild_info_query():
    guild_id = request.args.get("guild_id") or request.args.get("clan_id")
    bot_name = session.get('current_manage_bot') or request.args.get("bot_name")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, bot_module.get_clan_info_by_id, token, guild_id)
    if res.get("success"):
        g = res["guild_info"]
        return jsonify({"status": "success", "data": {
            "GuildId": g["clan_id"], "GuildName": g["clan_name"], "GuildLevel": g["level"],
            "CurrentMembers": g["total_members"], "MaxMembers": g["max_members"],
            "TotalActivityPoints": g["total_glory"], "GuildRegion": g["region"],
            "GuildSlogan": g["welcome_message"]
        }})
    return jsonify({"status": "error", "msg": "Guild scan rejected."})

# 🟢 [স্ট্যান্ডার্ড গিল্ড ক্যাশ মেম্বার প্রক্সি রেন্ডারিং]
@garena_bp.route('/api/guild/fetch')
@bp_login_required
async def api_guild_fetch_members():
    bot_name = request.args.get("bot_name") or session.get('current_manage_bot')
    async with aiosqlite.connect(DB_PATH_LOCAL) as db:
        async with db.execute("SELECT ingame_uid FROM bots WHERE name=?", (bot_name,)) as cur:
            row = await cur.fetchone()
            if not row or not row[0]: return jsonify({"status": "error", "msg": "Bot not found."})
            ingame_uid = str(row[0])
            
    file_path = os.path.join(ROOT_DIR, 'config', 'guild_members', f"{ingame_uid}.json")
    members_list = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Leader, Officers, Members মেম্বারদের একক ক্যাশ লিস্টে মার্জ করা হচ্ছে
            all_source_members = []
            if data.get("leader"): all_source_members.append(data.get("leader"))
            if data.get("acting_leader"): all_source_members.append(data.get("acting_leader"))
            for off in data.get("officers", []): all_source_members.append(off)
            for mem in data.get("members", []): all_source_members.append(mem)
                
            for m in all_source_members:
                members_list.append({
                    "Role": "Member" if m.get("role_code") != 3 else "Leader",
                    "Nickname": m.get("name", f"Member {m.get('uid')}"),
                    "Uid": str(m.get("uid")), 
                    "Level": m.get("level", "--"),
                    "AvatarId": str(m.get("avatar_id", "902000003"))
                })
        except Exception: pass
    return jsonify({"status": "success", "data": {"members": members_list}})

@garena_bp.route('/api/friends/fetch')
@bp_login_required
async def api_friends_fetch():
    bot_name = request.args.get("bot_name") or session.get('current_manage_bot')
    async with aiosqlite.connect(DB_PATH_LOCAL) as db:
        async with db.execute("SELECT ingame_uid FROM bots WHERE name=?", (bot_name,)) as cur:
            row = await cur.fetchone()
            if not row or not row[0]: return jsonify({"status": "error", "msg": "Bot not found."})
            ingame_uid = str(row[0])
            
    file_path = os.path.join(ROOT_DIR, 'config', 'admins', f"{ingame_uid}.json")
    friends_list = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for f_obj in data.get("friends", []):
                friends_list.append({
                    "uid": str(f_obj.get("uid")),
                    "nickname": f_obj.get("nickname", f"User {f_obj.get('uid')}"),
                    "level": f_obj.get("level", "--"),
                    "avatarId": str(f_obj.get("avatar_id", "902000003"))
                })
        except Exception: pass
    return jsonify({"status": "success", "data": {"friends": friends_list, "total_friends": len(friends_list)}})

@garena_bp.route('/api/friends/action', methods=['POST'])
@bp_login_required
async def api_friends_action_post():
    data = request.json
    bot_name = data.get("bot_name") or session.get('current_manage_bot')
    action = data.get("action")
    friend_uid = data.get("friend_uid") or data.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    
    loop = asyncio.get_running_loop()
    success = False
    if action == "remove":
        success = await loop.run_in_executor(None, bot_module.delete_active_friend, token, friend_uid)
    elif action == "accept":
        success = await loop.run_in_executor(None, bot_module.accept_friend_request, token, friend_uid)
    elif action == "reject":
        success = await loop.run_in_executor(None, bot_module.reject_friend_request, token, friend_uid)
        
    if success: trigger_instant_friend_sync(bot_name, token)
    return jsonify({"status": "success", "success": success})

@garena_bp.route('/api/guild/action', methods=['POST'])
@bp_login_required
async def api_guild_action_post():
    data = request.json
    bot_name = data.get("bot_name") or session.get('current_manage_bot')
    action = data.get("action")
    guild_id = data.get("guild_id") or data.get("clan_id")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    
    loop = asyncio.get_running_loop()
    success = False
    if action == "join":
        success = await loop.run_in_executor(None, bot_module.request_join_clan, token, guild_id)
    elif action == "leave":
        success = await loop.run_in_executor(None, bot_module.quit_current_clan, token, guild_id)
    return jsonify({"status": "success", "success": success})

@garena_bp.route('/api/bot/saved_lists')
@bp_login_required
async def api_bot_saved_lists():
    uid = request.args.get("uid", "").strip()
    if not uid: return jsonify({"success": False, "msg": "Bot UID required."})
    
    admins = []
    admin_path = os.path.join(ROOT_DIR, 'config', 'admins', f"{uid}.json")
    if os.path.exists(admin_path):
        try:
            with open(admin_path, 'r', encoding='utf-8') as f:
                admins = json.load(f).get("Admins", [])
        except: pass

    members = []
    members_path = os.path.join(ROOT_DIR, 'config', 'guild_members', f"{uid}.json")
    if os.path.exists(members_path):
        try:
            with open(members_path, 'r', encoding='utf-8') as f:
                members_list_raw = json.load(f).get("members", [])
                # যদি ফুল রেসপন্স জেসন থাকে, তবে তার 'members' ডিকশনারি থেকে uids বের করবে
                if isinstance(members_list_raw, list):
                    for m in members_list_raw:
                        if isinstance(m, dict):
                            members.append(str(m.get("uid")))
                        else:
                            members.append(str(m))
        except: pass
    
    return jsonify({"success": True, "admins": admins, "members": members})

@garena_bp.route('/api/owner', methods=['GET'])
@bp_login_required
async def api_get_owners():
    owner_path = os.path.join(ROOT_DIR, 'config', 'owner.json')
    owners = []
    if os.path.exists(owner_path):
        try:
            with open(owner_path, 'r', encoding='utf-8') as f:
                owners = json.load(f).get("Owners", [])
        except: pass
    return jsonify({"success": True, "owners": owners})

@garena_bp.route('/api/owner/action', methods=['POST'])
@bp_login_required
async def api_owner_action():
    if session.get('role') != 'owner': return jsonify({"success": False, "msg": "Access Denied."}), 403
    data = request.json
    action = data.get("action")
    target_uid = str(data.get("uid", "")).strip()
    if not target_uid or not action: return jsonify({"success": False, "msg": "Missing parameters."})
    
    owner_path = os.path.join(ROOT_DIR, 'config', 'owner.json')
    owners_data = {"Owners": []}
    if os.path.exists(owner_path):
        try:
            with open(owner_path, 'r', encoding='utf-8') as f: owners_data = json.load(f)
        except: pass
    
    if "Owners" not in owners_data: owners_data["Owners"] = []
    current_owners = [str(o).strip() for o in owners_data["Owners"]]
    if action == "add" and target_uid not in current_owners: current_owners.append(target_uid)
    elif action == "remove" and target_uid in current_owners: current_owners.remove(target_uid)
    owners_data["Owners"] = current_owners
    
    try:
        os.makedirs(os.path.dirname(owner_path), exist_ok=True)
        with open(owner_path, 'w', encoding='utf-8') as f: json.dump(owners_data, f, indent=4)
        try:
            import mongo_sync
            threading.Thread(target=mongo_sync.push_owner_to_mongo).start()
        except: pass
        return jsonify({"success": True, "owners": current_owners})
    except Exception as e: return jsonify({"success": False, "msg": str(e)})
