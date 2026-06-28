# filepath: web.py
# -*- coding: utf-8 -*-
# web.py - Garena REST API Proxy & Stateless Endpoints Blueprint

from flask import Blueprint, request, jsonify, session
from functools import wraps
import os
import sys
import time
import jwt
import asyncio
import aiosqlite
import json
import threading

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import garena_api as bot_module

web_api = Blueprint('web_api', __name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'config', 'database.db')

def bp_login_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({"success": False, "msg": "Unauthorized access. Session expired."}), 401
        return await f(*args, **kwargs)
    return decorated_function

# 🟢 BULLETPROOF SMART TOKEN FETCHER (MULTI-BOT FIXED)
async def get_bot_token_smart(bot_name):
    """
    ১. জেসন ফাইল থেকে টোকেন চেক করবে।
    ২. টোকেন না থাকলে বা এক্সপায়ার হলে, SQLite ডাটাবেজ থেকে আসল পাসওয়ার্ড রিড করে পুনরায় টোকেন আনবে।
    """
    if not bot_name:
        return None, "No bot selected in active session."
        
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
    
    # টোকেন এক্সপায়ার বা ফাইল মিসিং হলে ডাটাবেজ ফ্যালব্যাক
    if not uid or not password:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT login_uid, password FROM bots WHERE name=?", (bot_name,)) as cur:
                row = await cur.fetchone()
                if row:
                    uid, password = row[0], row[1]
                else:
                    return None, f"Credentials for '{bot_name}' not found in Database."
    
    # নতুন টোকেন জেনারেট এবং সেভ করা
    new_token, err = bot_module.get_token_from_uid_password(uid, password)
    if err:
        return None, f"Garena Auth Failed: {err}"
        
    bot_module.save_session({"uid": uid, "password": password, "token": new_token}, bot_name)
    return new_token, None

# 🟢 INSTANT FRIEND ACTION TO ADMIN FILE BACKGROUND SYNCHRONIZER
def trigger_instant_friend_sync(bot_name, token):
    """
    ফ্রেন্ড রিমুভ, রিকোয়েস্ট এক্সেপ্ট বা রিজেক্ট হওয়ার সাথে সাথে বটের এডমিন ফাইলটি
    প্যানেল চালু থাকা অবস্থায় ব্যাকগ্রাউন্ডে ইনস্ট্যান্ট সিঙ্ক করে নেওয়ার মেকানিজম।
    """
    try:
        from app import sync_friends_to_bot_admins, SYNCED_BOTS_SESSION
        # পোলিং লিস্ট থেকে বট সাময়িকভাবে ডিসকার্ড করা হচ্ছে যাতে পোলও সিঙ্ক করতে পারে
        SYNCED_BOTS_SESSION.discard(bot_name)
        
        async def run_bg_sync():
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT ingame_uid FROM bots WHERE name=?", (bot_name,)) as cur:
                    row = await cur.fetchone()
                    if row and row[0]:
                        await sync_friends_to_bot_admins(bot_name, row[0], token)
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(run_bg_sync())
        except RuntimeError:
            asyncio.run(run_bg_sync())
    except Exception as e:
        print(f"[Friend Action Sync] Error triggering background sync: {e}")


# ==================== GARENA NATIVE API PROXY ROUTS ====================

@web_api.route('/api/bot/profile')
@bp_login_required
async def api_bot_profile_direct():
    bot_name = session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
        
    author_uid = bot_module.decode_author_uid(token)
    res_raw = bot_module.get_player_info_detailed(author_uid, token)
    
    if res_raw.get("success"):
        return jsonify({
            "success": True,
            "profile": {
                "uid": res_raw["uid"],
                "nickname": res_raw["nickname"],
                "level": res_raw["level"],
                "clan_id": res_raw["clan_id"],
                "clan_name": res_raw["clan_name"],
                "region": res_raw["region"],
                "likes": res_raw["likes"],
                "signature": res_raw["signature"],
                "last_login": res_raw["last_login"],
                "created_at": res_raw["created_at"]
            },
            "json_data": res_raw["json_data"],
            "name_json_data": res_raw["name_json_data"]
        })
    return jsonify({"success": False, "msg": "Failed to sync Garena Bot Profile."})

@web_api.route('/api/bot/refresh', methods=['POST'])
@bp_login_required
async def api_bot_refresh_direct():
    bot_name = session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
        
    author_uid = bot_module.decode_author_uid(token)
    res_raw = bot_module.get_player_info_detailed(author_uid, token)
    
    if res_raw.get("success"):
        bot_module.refresh_self_profile_cache(token, bot_name)
        return jsonify({
            "success": True,
            "profile": {
                "uid": res_raw["uid"],
                "nickname": res_raw["nickname"],
                "level": res_raw["level"],
                "clan_id": res_raw["clan_id"],
                "clan_name": res_raw["clan_name"],
                "region": res_raw["region"],
                "likes": res_raw["likes"],
                "signature": res_raw["signature"],
                "last_login": res_raw["last_login"],
                "created_at": res_raw["created_at"]
            },
            "json_data": res_raw["json_data"],
            "name_json_data": res_raw["name_json_data"],
            "msg": "Bot portrait refreshed dynamically!"
        })
    return jsonify({"success": False, "msg": "Live Garena Gateway handshake timeout."})

@web_api.route('/api/friends/list')
@bp_login_required
async def api_friends_list_direct():
    bot_name = session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    
    res = bot_module.get_active_friend_list(token)
    if res.get("success"):
        raw_proto_parsed = bot_module.parse_proto_bytes(res.get("friends_raw_bytes", b""))
        serializable_json = bot_module.make_serializable(raw_proto_parsed)
        return jsonify({
            "success": True,
            "friends": res["friends"],
            "json_data": serializable_json,
            "name_json_data": bot_module.map_proto_to_named(serializable_json, "Friend")
        })
    return jsonify(res)

@web_api.route('/api/friends/pending')
@bp_login_required
async def api_friends_pending_direct():
    bot_name = session.get('current_manage_bot') or request.args.get("bot_name")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    
    res = bot_module.get_pending_request_list(token)
    if res.get("success"):
        enriched_requests = []
        for r in res["requests"]:
            p_res = bot_module.get_player_info_detailed(r["uid"], token)
            if p_res.get("success"):
                r["guild_name"] = p_res.get("clan_name", "No Guild")
                r["level"] = p_res.get("level", r["level"])
                avatar_id = p_res["json_data"]["1"]["12"] if (p_res.get("json_data") and "1" in p_res["json_data"]) else "902000003"
                r["avatar_id"] = str(avatar_id)
            enriched_requests.append(r)

        raw_proto_parsed = bot_module.parse_proto_bytes(res.get("pending_raw_bytes", b""))
        serializable_json = bot_module.make_serializable(raw_proto_parsed)
        return jsonify({
            "success": True,
            "requests": enriched_requests,
            "json_data": serializable_json,
            "name_json_data": bot_module.map_proto_to_named(serializable_json, "Player")
        })
    return jsonify(res)

@web_api.route('/api/friends/add', methods=['POST'])
@bp_login_required
async def api_friends_add_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    if not uid: return jsonify({"success": False, "msg": "Missing UID"}), 400
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.add_target_friend(token, uid)
    if success:
        trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success, "msg": "Friend Request successfully queued!" if success else "Handshake rejected."})

@web_api.route('/api/friends/remove', methods=['POST'])
@bp_login_required
async def api_friends_remove_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.delete_active_friend(token, uid)
    if success:
        trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success})

@web_api.route('/api/friends/accept', methods=['POST'])
@bp_login_required
async def api_friends_accept_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.accept_friend_request(token, uid)
    if success:
        trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success})

@web_api.route('/api/friends/reject', methods=['POST'])
@bp_login_required
async def api_friends_reject_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    success = bot_module.reject_friend_request(token, uid)
    if success:
        trigger_instant_friend_sync(bot_name, token)
    return jsonify({"success": success})

@web_api.route('/api/guild/info/<clan_id>')
@bp_login_required
async def api_guild_info_direct(clan_id):
    bot_name = session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, bot_module.get_clan_info_by_id, token, clan_id)
    if res.get("success"):
        g = res["guild_info"]
        mapped_data = {
            "GuildId": g["clan_id"],
            "GuildName": g["clan_name"],
            "GuildLevel": g["level"],
            "CurrentMembers": g["total_members"],
            "MaxMembers": g["max_members"],
            "TotalActivityPoints": g["total_glory"],
            "GuildRegion": g["region"],
            "GuildSlogan": g["welcome_message"],
            "GuildLeader": {
                "Uid": g["leader_uid"],
                "Name": "Click to View",
                "Level": "--"
            }
        }
        return jsonify({"status": "success", "data": mapped_data})
    return jsonify({"status": "error", "msg": res.get("message", "Guild scan failed.")})

@web_api.route('/api/guild/members/<clan_id>')
@bp_login_required
async def api_guild_members_direct(clan_id):
    bot_name = session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, bot_module.get_guild_member_list, token, clan_id)
    if res.get("success"):
        safe_res = {
            "success": True,
            "leader": res.get("leader"),
            "acting_leader": res.get("acting_leader"),
            "officers": res.get("officers"),
            "members": res.get("members"),
            "total_members": res.get("total_members")
        }
        raw_proto_parsed = bot_module.parse_proto_bytes(res.get("members_raw_bytes", b""))
        serializable_json = bot_module.make_serializable(raw_proto_parsed)
        safe_res["json_data"] = serializable_json
        safe_res["name_json_data"] = bot_module.map_proto_to_named(serializable_json, "Guild")
        return jsonify(safe_res)
    return jsonify(res)

@web_api.route('/api/guild/join', methods=['POST'])
@bp_login_required
async def api_guild_join_direct():
    bot_name = session.get('current_manage_bot')
    clan_id = request.json.get("clan_id")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, bot_module.request_join_clan, token, clan_id)
    return jsonify({"success": success})

@web_api.route('/api/guild/leave', methods=['POST'])
@bp_login_required
async def api_guild_leave_direct():
    bot_name = session.get('current_manage_bot')
    clan_id = request.json.get("clan_id")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, bot_module.quit_current_clan, token, clan_id)
    return jsonify({"success": success})

@web_api.route('/api/bot/nickname', methods=['POST'])
@bp_login_required
async def api_bot_nickname_direct():
    bot_name = session.get('current_manage_bot')
    new_nick = request.json.get("nickname")
    if not new_nick: return jsonify({"success": False, "msg": "Nickname required."}), 400
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    res = bot_module.change_nickname_native(token, new_nick)
    return jsonify(res)

@web_api.route('/api/bot/bio', methods=['POST'])
@bp_login_required
async def api_bot_bio_direct():
    bot_name = session.get('current_manage_bot')
    new_bio = request.json.get("bio")
    if not new_bio: return jsonify({"success": False, "msg": "Bio required."}), 400
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    res = bot_module.update_bio_native(token, new_bio)
    return jsonify(res)

@web_api.route('/api/bot/duo', methods=['POST'])
@bp_login_required
async def api_bot_duo_direct():
    bot_name = session.get('current_manage_bot')
    uid = request.json.get("uid")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"success": False, "msg": err}), 401
    
    res = bot_module.check_duo_native(token, uid)
    if res.get("success"):
        partner_uid = res.get("partner_uid")
        target_profile = bot_module.get_player_info_detailed(uid, token)
        partner_profile = bot_module.get_player_info_detailed(partner_uid, token) if partner_uid else None
        res_data = {
            "success": True,
            "partner_uid": partner_uid,
            "level": res.get("level"),
            "score": res.get("score"),
            "days_active": res.get("days_active"),
            "formed_on": res.get("formed_on"),
            "status": res.get("status"),
            "target_profile": target_profile,
            "partner_profile": partner_profile
        }
        return jsonify(res_data)
    return jsonify(res)

# ==================== DYNAMIC COMPATIBILITY PROXY ROUTES ====================

@web_api.route('/api/guild/info')
@bp_login_required
async def api_guild_info_query():
    guild_id = request.args.get("guild_id") or request.args.get("clan_id")
    if not guild_id: return jsonify({"status": "error", "msg": "Missing Guild ID."})
    bot_name = session.get('current_manage_bot') or request.args.get("bot_name")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, bot_module.get_clan_info_by_id, token, guild_id)
    if res.get("success"):
        # Map values back to javascript-expected casing keys
        g = res["guild_info"]
        mapped_data = {
            "GuildId": g["clan_id"],
            "GuildName": g["clan_name"],
            "GuildLevel": g["level"],
            "CurrentMembers": g["total_members"],
            "MaxMembers": g["max_members"],
            "TotalActivityPoints": g["total_glory"],
            "GuildRegion": g["region"],
            "GuildSlogan": g["welcome_message"],
            "GuildLeader": {
                "Uid": g["leader_uid"],
                "Name": "Click to View",
                "Level": "--"
            }
        }
        return jsonify({"status": "success", "data": mapped_data})
    return jsonify({"status": "error", "msg": res.get("message", "Guild scan handshake rejected.")})

@web_api.route('/api/guild/fetch')
@bp_login_required
async def api_guild_fetch_members():
    clan_id = request.args.get("guild_id") or request.args.get("clan_id")
    if not clan_id: return jsonify({"status": "error", "msg": "Missing Guild ID."})
    bot_name = session.get('current_manage_bot') or request.args.get("bot_name")
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, bot_module.get_guild_member_list, token, clan_id)
    if res.get("success"):
        all_m = []
        if res.get("leader"):
            l = res.get("leader").copy()
            l["Role"] = "Leader"
            l["Nickname"] = l.get("name", "Unknown")
            l["Uid"] = l.get("uid")
            l["Level"] = l.get("level")
            l["AvatarId"] = l.get("avatar_id")
            all_m.append(l)
        if res.get("acting_leader"):
            al = res.get("acting_leader").copy()
            al["Role"] = "ActingLeader"
            al["Nickname"] = al.get("name", "Unknown")
            al["Uid"] = al.get("uid")
            al["Level"] = al.get("level")
            al["AvatarId"] = al.get("avatar_id")
            all_m.append(al)
        for off in res.get("officers", []):
            o = off.copy()
            o["Role"] = "Officer"
            o["Nickname"] = o.get("name", "Unknown")
            o["Uid"] = o.get("uid")
            o["Level"] = o.get("level")
            o["AvatarId"] = o.get("avatar_id")
            all_m.append(o)
        for mem in res.get("members", []):
            m = mem.copy()
            m["Role"] = "Member"
            m["Nickname"] = m.get("name", "Unknown")
            m["Uid"] = m.get("uid")
            m["Level"] = m.get("level")
            m["AvatarId"] = m.get("avatar_id")
            all_m.append(m)
            
        return jsonify({
            "status": "success",
            "data": {
                "members": all_m
            }
        })
    return jsonify({"status": "error", "msg": res.get("message", "Failed to compile member rosters.")})

@web_api.route('/api/friends/fetch')
@bp_login_required
async def api_friends_fetch():
    bot_name = request.args.get("bot_name") or session.get('current_manage_bot')
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, bot_module.get_active_friend_list, token)
    if res.get("success"):
        mapped_friends = []
        for f in res["friends"]:
            mapped_friends.append({
                "uid": f["uid"],
                "nickname": f["nickname"],
                "level": f["level"],
                "avatar_id": f["avatar_id"],
                "avatarId": f["avatar_id"]
            })
        return jsonify({
            "status": "success",
            "data": {
                "friends": mapped_friends,
                "total_friends": len(mapped_friends)
            }
        })
    return jsonify({"status": "error", "msg": res.get("message", "Failed to fetch friends directory.")})

@web_api.route('/api/friends/action', methods=['POST'])
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
    msg = "Action failed."
    
    if action == "remove":
        success = await loop.run_in_executor(None, bot_module.delete_active_friend, token, friend_uid)
        msg = "Friend successfully removed." if success else "Failed to remove friend."
    elif action == "accept":
        success = await loop.run_in_executor(None, bot_module.accept_friend_request, token, friend_uid)
        msg = "Friend request accepted!" if success else "Failed to accept friend request."
    elif action == "reject":
        success = await loop.run_in_executor(None, bot_module.reject_friend_request, token, friend_uid)
        msg = "Friend request rejected." if success else "Failed to reject friend request."
        
    if success:
        # 🟢 ফ্রেন্ড ডিলিট, এক্সেপ্ট বা রিজেক্ট হওয়ার সাথে সাথে ইনস্ট্যান্টলি এডমিন ফাইল ব্যাকগ্রাউন্ডে সিঙ্ক করা হচ্ছে
        trigger_instant_friend_sync(bot_name, token)
        return jsonify({"status": "success", "success": True, "msg": msg})
    return jsonify({"status": "error", "success": False, "msg": msg})

@web_api.route('/api/guild/action', methods=['POST'])
@bp_login_required
async def api_guild_action_post():
    data = request.json
    bot_name = data.get("bot_name") or session.get('current_manage_bot')
    action = data.get("action")
    guild_id = data.get("guild_id") or data.get("clan_id")
    bot_ingame_uid = data.get("ingame_uid")
    
    token, err = await get_bot_token_smart(bot_name)
    if err: return jsonify({"status": "error", "msg": err}), 401
    
    loop = asyncio.get_running_loop()
    success = False
    msg = "Guild action failed."
    
    if action == "join":
        success = await loop.run_in_executor(None, bot_module.request_join_clan, token, guild_id)
        msg = "Join request successfully sent!" if success else "Failed to send join request."
    elif action == "leave":
        success = await loop.run_in_executor(None, bot_module.quit_current_clan, token, guild_id)
        msg = "Left the guild successfully." if success else "Failed to leave guild."
        
    if success:
        return jsonify({"status": "success", "success": True, "msg": msg})
    return jsonify({"status": "error", "success": False, "msg": msg})


# ==================== NEW POPUP AND OWNER.JSON EDIT APIs ====================

@web_api.route('/api/bot/saved_lists')
@bp_login_required
async def api_bot_saved_lists():
    """বটের সংরক্ষিত অফলাইন এডমিন এবং গিল্ড মেম্বার ফাইল লোড করার এন্ডপয়েন্ট"""
    uid = request.args.get("uid", "").strip()
    if not uid:
        return jsonify({"success": False, "msg": "Bot UID required."})
    
    # 🟢 [স্মার্ট ইন্সট্যান্ট গিল্ড সিঙ্ক প্যাচ]
    # ইউজার যখনই লিস্ট দেখতে চাবে, ডাটাবেজ থেকে বটনেম নিয়ে মেম্বার লিস্ট ফাইলটি ইন্সট্যান্টলি লাইভ সিঙ্ক করা হবে।
    try:
        bot_name = None
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM bots WHERE ingame_uid=?", (uid,)) as cur:
                row = await cur.fetchone()
                if row:
                    bot_name = row[0]
        
        if bot_name:
            token, err = await get_bot_token_smart(bot_name)
            if token:
                profile_res = await asyncio.get_event_loop().run_in_executor(None, bot_module.get_player_info_detailed, str(uid), token)
                if profile_res and profile_res.get("success"):
                    clan_id = profile_res.get("clan_id")
                    if clan_id and clan_id != "0" and clan_id != "N/A":
                        res_guild = await asyncio.get_event_loop().run_in_executor(None, bot_module.get_guild_member_list, token, str(clan_id))
                        if res_guild.get("success"):
                            all_uids = []
                            if res_guild.get("leader") and "uid" in res_guild["leader"]:
                                all_uids.append(str(res_guild["leader"]["uid"]))
                            if res_guild.get("acting_leader") and "uid" in res_guild["acting_leader"]:
                                all_uids.append(str(res_guild["acting_leader"]["uid"]))
                            for officer in res_guild.get("officers", []):
                                if "uid" in officer:
                                    all_uids.append(str(officer["uid"]))
                            for member in res_guild.get("members", []):
                                if "uid" in member:
                                    all_uids.append(str(member["uid"]))
                            
                            file_dir = os.path.join(BASE_DIR, 'config', 'guild_members')
                            os.makedirs(file_dir, exist_ok=True)
                            file_path = os.path.join(file_dir, f"{uid}.json")
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump({"members": all_uids}, f, indent=4)
    except Exception as e:
        print(f"[Saved Lists Endpoint Sync Error] {e}")

    # এডমিন ফাইল লোড করা হচ্ছে
    admins = []
    admin_path = os.path.join(BASE_DIR, 'config', 'admins', f"{uid}.json")
    if os.path.exists(admin_path):
        try:
            with open(admin_path, 'r', encoding='utf-8') as f:
                admins = json.load(f).get("Admins", [])
        except: pass
    else:
        try:
            from utils.admin_manager import get_admins
            admins = get_admins(uid)
        except: pass

    # মেম্বার ফাইল লোড করা হচ্ছে
    members = []
    members_path = os.path.join(BASE_DIR, 'config', 'guild_members', f"{uid}.json")
    if os.path.exists(members_path):
        try:
            with open(members_path, 'r', encoding='utf-8') as f:
                members = json.load(f).get("members", [])
        except: pass
    
    return jsonify({
        "success": True,
        "admins": admins,
        "members": members
    })

@web_api.route('/api/owner', methods=['GET'])
@bp_login_required
async def api_get_owners():
    """owner.json ফাইলের ডাটা রিড করার এন্ডপয়েন্ট"""
    owner_path = os.path.join(BASE_DIR, 'config', 'owner.json')
    owners = []
    if os.path.exists(owner_path):
        try:
            with open(owner_path, 'r', encoding='utf-8') as f:
                owners = json.load(f).get("Owners", [])
        except: pass
    return jsonify({"success": True, "owners": owners})

@web_api.route('/api/owner/action', methods=['POST'])
@bp_login_required
async def api_owner_action():
    """owner.json ফাইলে ওনার আইডি যুক্ত বা রিমুভ করার এবং মঙ্গোতে পুশ করার এন্ডপয়েন্ট"""
    if session.get('role') != 'owner':
        return jsonify({"success": False, "msg": "Access Denied."}), 403
        
    data = request.json
    action = data.get("action")
    target_uid = str(data.get("uid", "")).strip()
    
    if not target_uid or not action:
        return jsonify({"success": False, "msg": "Missing parameters."})
        
    owner_path = os.path.join(BASE_DIR, 'config', 'owner.json')
    owners_data = {"Owners": []}
    if os.path.exists(owner_path):
        try:
            with open(owner_path, 'r', encoding='utf-8') as f:
                owners_data = json.load(f)
        except: pass
    
    if "Owners" not in owners_data:
        owners_data["Owners"] = []
        
    current_owners = [str(o).strip() for o in owners_data["Owners"]]
    
    if action == "add":
        if target_uid not in current_owners:
            current_owners.append(target_uid)
    elif action == "remove":
        if target_uid in current_owners:
            current_owners.remove(target_uid)
            
    owners_data["Owners"] = current_owners
    
    try:
        os.makedirs(os.path.dirname(owner_path), exist_ok=True)
        with open(owner_path, 'w', encoding='utf-8') as f:
            json.dump(owners_data, f, indent=4)
        
        # মঙ্গোডিবিতে ব্যাকগ্রাউন্ডে ওনার ফাইল পুশ করা হচ্ছে
        try:
            import mongo_sync
            import threading
            threading.Thread(target=mongo_sync.push_owner_to_mongo).start()
        except: pass
        
        return jsonify({"success": True, "owners": current_owners})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Failed to save owners file: {e}"})


# ==================== STATELESS PUBLIC DIRECT APIs ====================
def authenticate_direct_bot():
    uid = request.args.get("uid", "").strip()
    password = request.args.get("password", "").strip()
    if not uid or not password:
        return None, "Error: Missing bot query parameters."
    token, err = bot_module.get_token_from_uid_password(uid, password)
    return token, err

@web_api.route('/api/direct/profile')
async def api_direct_profile():
    token, err = authenticate_direct_bot()
    if err: return jsonify({"success": False, "msg": err}), 401
    target_uid = request.args.get("target", "").strip()
    if not target_uid: target_uid = bot_module.decode_author_uid(token)
    res = bot_module.get_player_info_detailed(target_uid, token)
    return jsonify({
        "success": res.get("success", False),
        "profile": {
            "uid": res.get("uid"),
            "nickname": res.get("nickname"),
            "level": res.get("level"),
            "clan_id": res.get("clan_id"),
            "clan_name": res.get("clan_name"),
            "region": res.get("region"),
            "likes": res.get("likes"),
            "signature": res.get("signature"),
            "last_login": res.get("last_login"),
            "created_at": res.get("created_at")
        } if res.get("success") else None,
        "json_data": res.get("json_data"),
        "name_json_data": res.get("name_json_data")
    })