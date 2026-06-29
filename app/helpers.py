# filepath: app/helpers.py
# -*- coding: utf-8 -*-

import os
import json
import time
import jwt
import asyncio
import aiosqlite
import threading
import bot_core as bot_module
from app.database import get_db

MANAGER_HOST = '127.0.0.1'
MANAGER_PORT = 50000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
DB_PATH = os.path.join(ROOT_DIR, 'config', 'database.db')

SYNCED_BOTS_SESSION = set()

async def is_authorized(bot_name, username, role):
    if role == 'owner': return True
    async with get_db() as db:
        async with db.execute("SELECT folder FROM bots WHERE name=?", (bot_name,)) as cursor:
            row = await cursor.fetchone()
            if row and row['folder'] == username: return True
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
            if 'login' in k.lower() and any(c.isdigit() for c in str(v)):
                raw_login = v; break
            
    raw_create = b_info.get('createAt') or b_info.get('create_at')
    if not raw_create:
        for k, v in b_info.items():
            if 'create' in k.lower() and any(c.isdigit() for c in str(v)):
                raw_create = v; break

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

async def sync_friends_to_bot_admins(bot_name, ingame_uid, token):
    if not ingame_uid or not token:
        return False
    try:
        res = bot_module.get_active_friend_list(token)
        if not res.get("success") or "friends" not in res:
            print(f"[ADMIN AUTO-SYNC] ⚠️ Friendlist fetch failed or empty for Bot '{bot_name}'.")
            return False
        
        friend_uids = [str(f["uid"]).strip() for f in res["friends"] if f.get("uid") and str(f["uid"]) != str(ingame_uid)]
        
        raw_proto_parsed = bot_module.parse_proto_bytes(res.get("friends_raw_bytes", b""))
        serializable_json = bot_module.make_serializable(raw_proto_parsed)
        name_json_data = bot_module.map_proto_to_named(serializable_json, "Friend")

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
            
        try:
            dir_path = os.path.join(ROOT_DIR, 'config', 'admins')
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, f"{ingame_uid}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "Admins": friend_uids,
                    "friends": res["friends"],
                    "json_data": serializable_json,
                    "name_json_data": name_json_data
                }, f, indent=4)
            print(f"[ADMIN AUTO-SYNC] 🔄 Saved {len(friend_uids)} admins with structure to separate JSON file: {file_path}")
        except Exception as file_err:
            print(f"[ADMIN AUTO-SYNC] Error saving separate admin file: {file_err}")

        try:
            import mongo_sync
            threading.Thread(target=mongo_sync.push_admin_to_mongo, args=(bot_name, admin_data)).start()
        except Exception as m_err:
            print(f"[ADMIN AUTO-SYNC] MongoDB Push Error: {m_err}")
            
        print(f"[ADMIN AUTO-SYNC] ✅ Successfully overwritten {len(friend_uids)} friends as admins for Bot '{bot_name}'.")
        return True
    except Exception as e:
        print(f"[ADMIN AUTO-SYNC ERROR] Failed to overwrite admins for bot {bot_name}: {e}")
        return False

# 🟢 [স্ট্যান্ডার্ড গিল্ড ক্যাশ মেম্বার জেসন রাইটার]
async def sync_guild_members_local(bot_name, ingame_uid, token):
    if not ingame_uid or not token:
        return False
    try:
        profile_res = await asyncio.get_event_loop().run_in_executor(None, bot_module.get_player_info_detailed, str(ingame_uid), token)
        if not profile_res or not profile_res.get("success"):
            return False
            
        clan_id = profile_res.get("clan_id")
        if not clan_id or clan_id == "N/A" or str(clan_id) == "0":
            return False
            
        res_guild = await asyncio.get_event_loop().run_in_executor(None, bot_module.get_guild_member_list, token, str(clan_id))
        if res_guild.get("success"):
            raw_proto_parsed = bot_module.parse_proto_bytes(res_guild.get("members_raw_bytes", b""))
            serializable_json = bot_module.make_serializable(raw_proto_parsed)
            name_json_data = bot_module.map_proto_to_named(serializable_json, "Guild")

            # MongoDB এর জন্য লাইটওয়েট ইউআইডি তালিকা তৈরি
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
                dir_path = os.path.join(ROOT_DIR, 'config', 'guild_members')
                os.makedirs(dir_path, exist_ok=True)
                file_path = os.path.join(dir_path, f"{ingame_uid}.json")
                
                # সম্পূর্ণ স্ট্রাকচারাল গ্যারেনা জেসন ডাটা ফাইলে রাইট করা হচ্ছে
                file_data = {
                    "success": True,
                    "leader": res_guild.get("leader"),
                    "acting_leader": res_guild.get("acting_leader"),
                    "officers": res_guild.get("officers", []),
                    "members": res_guild.get("members", []),
                    "total_members": res_guild.get("total_members", 0),
                    "json_data": serializable_json,
                    "name_json_data": name_json_data
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(file_data, f, indent=4)
                    
                try:
                    import mongo_sync
                    mongo_sync.col_guild_members.update_one(
                        {'_id': bot_name},
                        {'$set': {'clan_id': str(clan_id), 'members': member_uids, 'last_update': time.time()}},
                        upsert=True
                    )
                except Exception: pass
                print(f"[GUILD AUTO-SYNC] ✅ Successfully cached {len(member_uids)} members with full structure to file: {file_path}")
                return True
    except Exception as e:
        print(f"[GUILD AUTO-SYNC ERROR] Failed: {e}")
    return False

async def fetch_profile_native(target_uid):
    token = None
    bot_name = None
    async with get_db() as db:
        async with db.execute("SELECT name FROM bots WHERE ingame_uid=?", (str(target_uid),)) as cur:
            row = await cur.fetchone()
            if row:
                bot_name = row['name']
                loop = asyncio.get_running_loop()
                token, _ = await loop.run_in_executor(None, bot_module.get_active_token, bot_name)
    
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
        loop = asyncio.get_running_loop()
        res_raw = await loop.run_in_executor(None, bot_module.get_player_info_detailed, target_uid, token)
        if res_raw and res_raw.get("success"):
            return {"success": True, "data": format_ff_data(res_raw)}
        return {"success": False, "msg": res_raw.get("message", "Garena API Handshake failed.")}
    except Exception as e:
        return {"success": False, "msg": f"Garena Connection Error: {str(e)}"}

async def get_bot_token_smart(bot_name):
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
    
    if not uid or not password:
        async with aiosqlite.connect(DB_PATH_LOCAL) as db:
            async with db.execute("SELECT login_uid, password FROM bots WHERE name=?", (bot_name,)) as cur:
                row = await cur.fetchone()
                if row:
                    uid, password = row[0], row[1]
                else:
                    return None, f"Credentials for '{bot_name}' not found in Database."
    
    new_token, err = bot_module.get_token_from_uid_password(uid, password)
    if err:
        return None, f"Garena Auth Failed: {err}"
        
    bot_module.save_session({"uid": uid, "password": password, "token": new_token}, bot_name)
    return new_token, None

def trigger_instant_friend_sync(bot_name, token):
    try:
        SYNCED_BOTS_SESSION.discard(bot_name)
        async def run_bg_sync():
            async with aiosqlite.connect(DB_PATH_LOCAL) as db:
                async with db.execute("SELECT ingame_uid FROM bots WHERE name=?", (bot_name,)) as cur:
                    row = await cur.fetchone()
                    if row and row[0]:
                        await sync_friends_to_bot_admins(bot_name, row[0], token)
                        await sync_guild_members_local(bot_name, row[0], token)
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(run_bg_sync())
        except RuntimeError:
            asyncio.run(run_bg_sync())
    except Exception as e:
        print(f"[Friend Action Sync] Error triggering background sync: {e}")
