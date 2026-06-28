# -*- coding: utf-8 -*-
# garena_api.py - High-Level Garena REST API Proxy Module (OB54 Synced)

import os
import json
import random
import requests
import jwt
import urllib3
import secrets
import hmac       
import hashlib    
from datetime import datetime
from bot_core import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# SESSION MANAGEMENT (DYNAMIC DIR SYNC)
# ==========================================
def load_session(username=None):
    path = f"config/garena_sessions/{username}_url.json" if username else "config/garena_sessions/url.json"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_session(data, username=None):
    path = f"config/garena_sessions/{username}_url.json" if username else "config/garena_sessions/url.json"
    try:
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except:
        pass

def get_active_token(username=None):
    session = load_session(username)
    uid = session.get("uid")
    password = session.get("password")
    token = session.get("token")
    
    if not uid or not password:
        return None, "No active session found"
        
    if token:
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp = decoded.get("exp", 0)
            if exp > datetime.utcnow().timestamp() + 300:
                return token, None
        except:
            pass
            
    new_token, error = get_token_from_uid_password(uid, password)
    if error:
        return None, f"Dynamic login failed: {error}"
        
    session["token"] = new_token
    session["uid"] = str(uid)
    save_session(session, username)
    return new_token, None

# ==========================================
# AUTHENTICATION APIs
# ==========================================
def get_token_from_uid_password(uid, password):
    try:
        oauth_url = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
        parsed_uid = int(uid) if str(uid).isdigit() else uid
        
        payload = {
            "client_id": 100067,
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_type": 2,
            "password": password,
            "response_type": "token",
            "uid": parsed_uid
        }
        
        body_json = json.dumps(payload, separators=(',', ':'))
        key_bytes = bytes.fromhex("2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3")
        signature = hmac.new(key_bytes, body_json.encode('utf-8'), hashlib.sha256).hexdigest()

        headers = {
            "Authorization": f"Signature {signature}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Connection": "Keep-Alive",
            "Host": "100067.connect.garena.com"
        }

        oauth_response = requests.post(oauth_url, data=body_json, headers=headers, timeout=10, verify=False)
        if oauth_response.status_code != 200:
            return None, f"OAuth failed: {oauth_response.status_code}"
            
        oauth_data = oauth_response.json()
        if oauth_data.get('code') != 0:
            return None, f"Garena API Error: {oauth_data}"

        access_token = oauth_data['data']['access_token']
        open_id = oauth_data['data'].get('open_id', '')
        
        platforms = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        for platform_type in platforms:
            result = try_platform_login(open_id, access_token, platform_type)
            if result and result.get('token'):
                return result['token'], None
        
        return None, "Login successful but JWT generation failed on all platforms"
    except Exception as e:
        return None, str(e)

def try_platform_login(open_id, access_token, platform_type):
    try:
        fields = {
            3: "2024-12-05 18:15:32",
            4: "free fire",
            5: 1,
            7: "1.126.1", # OB54 Client Version
            8: f"{DEV['os']} ({DEV['os_ver_only']})",
            9: "Handheld",
            10: DEV["operator"],
            11: "WIFI",
            12: DEV["width"],
            13: DEV["height"],
            14: DEV["dpi"],
            15: DEV["cpu_long"],
            16: DEV["ram"],
            17: DEV["gpu"],
            18: DEV["opengl"],
            19: f"Google|{random.randint(10000000, 99999999)}-a7d5-4cb6-8d7e-3b0e448a0c57",
            20: "223.191.51.89",
            21: "en",
            22: open_id,
            29: access_token,
            24: int(platform_type),
            99: str(platform_type),
            100: str(platform_type)
        }
        
        serialized_data = create_proto_sync(fields)
        encrypted_data = E_AEs(serialized_data.hex())

        url = "https://loginbp.ggpolarbear.com/MajorLogin"
        headers = {
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/octet-stream",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54" # OB54 Release Version
        }
        
        response = requests.post(url, data=encrypted_data, headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
            parsed_res = parse_proto_bytes(response.content)
            token_bytes = parsed_res.get(8)
            if token_bytes:
                token_value = token_bytes.decode('utf-8', errors='ignore') if isinstance(token_bytes, bytes) else str(token_bytes)
                return {"token": token_value}
        return None
    except Exception:
        return None

# ==========================================
# PLAYER PROFILE APIs
# ==========================================
def get_player_info_detailed(target_uid, token):
    try:
        region = get_server_from_token(token)
        endpoint = get_base_url(region) + "GetPlayerPersonalShow"
        
        protobuf_data = create_proto_sync({1: int(target_uid), 2: 1})
        encrypted_data = encrypt_message_hex(protobuf_data)

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB54"
        }
        
        res = requests.post(endpoint, data=bytes.fromhex(encrypted_data), headers=headers, timeout=12, verify=False)
        if res.status_code != 200:
            return {"success": False, "message": f"HTTP Status {res.status_code}"}
            
        parsed_outer = parse_proto_bytes(res.content)
        basic_bytes = safe_get_bytes(parsed_outer.get(1))
        if not basic_bytes:
            return {"success": False, "message": "Player basic info segment not found."}
            
        parsed_basic = parse_proto_bytes(basic_bytes)
        
        uid_val = decode_field_int(parsed_basic.get(1))
        nickname = decode_field_str(parsed_basic.get(3))
        region_str = decode_field_str(parsed_basic.get(5))
        level_val = decode_field_int(parsed_basic.get(6))
        likes_val = decode_field_int(parsed_basic.get(21))
        last_login_ts = decode_field_str(parsed_basic.get(24))
        create_ts = decode_field_str(parsed_basic.get(44))

        clan_id = "0"
        clan_name = "No Guild"
        leader_uid = "N/A"
        
        clan_bytes = safe_get_bytes(parsed_outer.get(6))
        if clan_bytes:
            parsed_clan = parse_proto_bytes(clan_bytes)
            clan_id = decode_field_str(parsed_clan.get(1))
            clan_name = decode_field_str(parsed_clan.get(2))
            leader_uid = decode_field_str(parsed_clan.get(3))
            if not clan_id or clan_id == "": clan_id = "0"

        signature = "No Signature"
        social_bytes = safe_get_bytes(parsed_outer.get(9))
        if social_bytes:
            parsed_social = parse_proto_bytes(social_bytes)
            signature = decode_field_str(parsed_social.get(9))

        def format_unix(ts):
            try:
                if not ts or ts == "0" or ts == "": return "N/A"
                return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
            except: return "N/A"

        created_time = format_unix(create_ts)
        last_login_time = format_unix(last_login_ts)

        if clan_id != "0" and (clan_name == "N/A" or clan_name == "" or clan_name == "No Guild"):
            clan_name = get_clan_name_direct(token, clan_id)

        raw_json_tree = make_serializable(parsed_outer)

        return {
            "success": True,
            "uid": str(uid_val),
            "nickname": nickname.strip(),
            "level": level_val,
            "likes": likes_val,
            "region": region_str.strip(),
            "clan_id": clan_id,
            "clan_name": clan_name.strip() if clan_name else "No Guild",
            "leader_uid": leader_uid if leader_uid else "N/A",
            "signature": signature.strip() if signature else "No Signature",
            "created_at": created_time,
            "last_login": last_login_time,
            "raw_data": res.content.hex(), 
            "json_data": raw_json_tree,
            "name_json_data": map_proto_to_named(raw_json_tree, "Player")
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

# 🟢 গ্যারেনা নেম ডিরেক্টরি ক্র্যাশ এড়াতে গ্লোবাল ডিরেক্টরি ফাইন্ডার প্যাচ
def get_clan_name_direct(token, clan_id):
    try:
        res = get_clan_info_by_id(token, clan_id)
        if res.get("success"):
            return res["guild_info"]["clan_name"]
    except:
        pass
    return "No Guild"

def refresh_self_profile_cache(token, username=None):
    try:
        author_uid = decode_author_uid(token)
        if not author_uid: return None
        res = get_player_info_detailed(author_uid, token)
        if res.get("success"):
            profile_data = {
                "uid": res["uid"],
                "nickname": res["nickname"],
                "level": res["level"],
                "clan_id": res["clan_id"],
                "clan_name": res["clan_name"],
                "region": res["region"],
                "likes": res["likes"],
                "signature": res["signature"],
                "last_login": res["last_login"],
                "created_at": res["created_at"]
            }
            # 🟢 SYNCED PATH DIRECTORY FOR CACHING
            path = f"config/garena_sessions/{username}_data.json" if username else "config/garena_sessions/data.json"
            dir_name = os.path.dirname(path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=4, ensure_ascii=False)
            return profile_data
    except Exception as e:
        print(f"[*] Profile caching fault: {str(e)}")
    return None

def change_nickname_native(token, new_name):
    try:
        nickname_bytes = new_name.encode('utf-8')
        serialized = b''
        serialized += bytes([(1 << 3) | 2])
        serialized += enc_vr_sync(len(nickname_bytes))
        serialized += nickname_bytes
        serialized += bytes([(2 << 3) | 0])
        serialized += enc_vr_sync(secrets.randbits(32))
        
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        encrypted = cipher.encrypt(pad(serialized, AES.block_size))
        
        # 🟢 OB54 GGPOLARBEAR HOST FIXED
        url = "https://loginbp.ggpolarbear.com/MajorModifyNickname"
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Content-Type': "application/octet-stream",
            'Authorization': f"Bearer {token}",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB54"
        }
        
        res = requests.post(url, data=encrypted, headers=headers, timeout=12, verify=False)
        if res.status_code == 200:
            return {"success": True, "message": f"Nickname successfully modified to '{new_name}'"}
        else:
            try:
                err_msg = res.content.decode('utf-8').strip()
                return {"success": False, "message": err_msg if err_msg else f"HTTP Status: {res.status_code}"}
            except:
                return {"success": False, "message": f"HTTP Error {res.status_code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def update_bio_native(token, bio_text):
    try:
        region = get_server_from_token(token)
        base_url = get_base_url(region)
        url = f"{base_url}UpdateSocialBasicInfo"
        
        bio_bytes = bio_text.encode('utf-8')
        bio_len = len(bio_bytes)
        
        field_2 = b'\x10\x11'
        field_5 = b'\x2A\x00'
        field_6 = b'\x32\x00'
        field_8 = b'\x42' + enc_vr_sync(bio_len) + bio_bytes
        field_9 = b'\x48\x01'
        field_11 = b'\x5A\x00'
        field_12 = b'\x62\x00'
        
        proto_data = field_2 + field_5 + field_6 + field_8 + field_9 + field_11 + field_12
        encrypted = E_AEs(proto_data.hex())
        
        headers = {
            "Expect": "100-continue",
            "Authorization": f"Bearer {token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        
        res = requests.post(url, headers=headers, data=encrypted, timeout=12, verify=False)
        if res.status_code == 200:
            return {"success": True, "message": "Signature changed successfully!"}
        return {"success": False, "message": f"Server status: {res.status_code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def check_duo_native(token, target_uid):
    try:
        region = get_server_from_token(token)
        base_url = get_base_url(region)
        url = f"{base_url}GetSpecialFriendList"
        
        payload = YOuR_FaThER(target_uid)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Connection": "Keep-Alive"
        }
        
        res = requests.post(url, headers=headers, data=payload, timeout=12, verify=False)
        if res.status_code == 200:
            decrypted = UNknown(res.content)
            parsed_outer = parse_proto_bytes(decrypted)
            
            duo_bytes = parsed_outer.get(1)
            if not duo_bytes or not isinstance(duo_bytes, bytes):
                return {"success": False, "message": "No Dynamic Duo info found for this player."}
                
            duo_parsed = parse_proto_bytes(duo_bytes)
            partner_uid = duo_parsed.get(1, 0)
            score = duo_parsed.get(3, 0)
            creation_ts = duo_parsed.get(4, 0)
            days_active = duo_parsed.get(5, 0)
            status_code = duo_parsed.get(6, 0)
            
            lvl = 1
            if score >= 1201: lvl = 6
            elif score >= 801: lvl = 5
            elif score >= 501: lvl = 4
            elif score >= 301: lvl = 3
            elif score >= 101: lvl = 2
            
            status_str = "Active" if status_code == 2 else "Inactive"
            creation_time = datetime.fromtimestamp(creation_ts).strftime('%B %d, %Y')
            
            raw_tree = make_serializable(duo_parsed)
            
            return {
                "success": True,
                "partner_uid": str(partner_uid),
                "level": lvl,
                "score": score,
                "days_active": days_active,
                "formed_on": creation_time,
                "status": status_str,
                "raw_data": decrypted.hex(),
                "json_data": raw_tree,
                "name_json_data": map_proto_to_named(raw_tree, "Duo")
            }
        elif res.status_code == 500:
            return {"success": False, "message": "Private profile or invalid player UID."}
        return {"success": False, "message": f"Server returned error code: {res.status_code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ==========================================
# GUILD APIs WITH OB54 COMPRESSION PATCH
# ==========================================
def get_clan_info_by_id(token, clan_id):
    try:
        import gzip
        region = get_server_from_token(token)
        base_url = get_base_url(region)
        
        serialized = create_proto_sync({1: int(clan_id), 2: 1})
        encrypted = E_AEs(serialized.hex())
        url = base_url + "GetClanInfoByClanID"
        
        headers = {
            "Expect": "100-continue",
            "Authorization": f"Bearer {token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/octet-stream",
            "Host": base_url.split("//")[1].rstrip("/"),
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        
        resp_http = requests.post(url, headers=headers, data=encrypted, timeout=15, verify=False)
        if resp_http.status_code != 200:
            return {"success": False, "message": f"HTTP Response Status: {resp_http.status_code}"}
            
        content = resp_http.content
        if content.startswith(b'\x1f\x8b'):
            content = gzip.decompress(content)
            
        parsed = parse_proto_bytes(content)
        
        id_val = decode_field_int(parsed.get(1))
        name_val = decode_field_str(parsed.get(2))
        ts_created = decode_field_int(parsed.get(3))
        leader_uid = decode_field_str(parsed.get(4))
        level_val = decode_field_int(parsed.get(5))
        max_members = decode_field_int(parsed.get(6))
        total_members = decode_field_int(parsed.get(7))
        welcome_msg = decode_field_str(parsed.get(12))
        region_val = decode_field_str(parsed.get(13))
        
        officers_list = []
        off_val = parsed.get(15)
        if isinstance(off_val, list):
            for o in off_val: officers_list.append(str(o))
        elif off_val:
            officers_list.append(str(off_val))
            
        past_glory = decode_field_int(parsed.get(16))
        acting_leader = decode_field_str(parsed.get(23))
        total_glory = decode_field_int(parsed.get(36))
        recent_glory = decode_field_int(parsed.get(37))
        
        def format_ts(x):
            try:
                if not x: return "N/A"
                return datetime.fromtimestamp(int(x)).strftime('%Y-%m-%d %H:%M:%S')
            except: return "N/A"
                
        info_dict = {
            "clan_id": str(id_val),
            "clan_name": name_val.strip(),
            "created_at": format_ts(ts_created),
            "leader_uid": leader_uid if leader_uid else "N/A",
            "level": level_val,
            "max_members": max_members,
            "total_members": total_members,
            "welcome_message": welcome_msg.strip(),
            "region": region_val.strip() if region_val else region,
            "officer_uids": officers_list,
            "past_glory": past_glory,
            "acting_leader_uid": acting_leader if acting_leader else "N/A",
            "total_glory": total_glory,
            "recent_glory": recent_glory
        }
        return {"success": True, "guild_info": info_dict}
    except Exception as e:
        return {"success": False, "message": str(e)}

def get_guild_member_list(token, clan_id):
    try:
        import gzip
        region = get_server_from_token(token)
        base_url = get_base_url(region)
        
        req_bytes = create_proto_sync({1: int(clan_id)})
        encrypted = E_AEs(req_bytes.hex())
        url = base_url + "GetClanMembers"

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Unity-Version": "2022.3.47f1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": base_url.split("//")[1].rstrip("/"),
            "Accept-Encoding": "gzip, deflate",
            "X-GA": "v1 1",
        }

        resp = requests.post(url, headers=headers, data=encrypted, timeout=15, verify=False)
        if resp.status_code != 200:
            return {"success": False, "message": f"HTTP Status: {resp.status_code}"}

        # Gzip compressed binary response handling
        content = resp.content
        if content.startswith(b'\x1f\x8b'):
            content = gzip.decompress(content)

        parsed = parse_proto_bytes(content)
        entries_list = parsed.get(1, [])
        if not isinstance(entries_list, list):
            entries_list = [entries_list]
            
        leader = None
        acting_leader = None
        officers = []
        members = []
        
        def decode_str(b_data):
            if isinstance(b_data, bytes):
                return b_data.decode('utf-8', errors='ignore')
            return str(b_data)

        for entry_bytes in entries_list:
            if not isinstance(entry_bytes, bytes): continue
            entry = parse_proto_bytes(entry_bytes)
            
            info_bytes = entry.get(1)
            if not info_bytes or not isinstance(info_bytes, bytes): continue
            info = parse_proto_bytes(info_bytes)
            
            uid_val = info.get(1, 0)
            name_val = decode_str(info.get(3, b"Unknown"))
            
            lvl_val = decode_field_int(info.get(6), 1)
            avatar_id = decode_field_int(info.get(12), 902000003)
            
            role_code = entry.get(4, 0)
            
            total_glory = entry.get(11, 0)
            weekly_glory = entry.get(10, 0)
            
            member_data = {
                "uid": str(uid_val),
                "name": name_val.strip(),
                "level": int(lvl_val),
                "avatar_id": str(avatar_id),
                "total_glory": int(total_glory),
                "weekly_glory": int(weekly_glory),
                "role_code": int(role_code)
            }
            
            if role_code == 3:
                leader = member_data
            elif role_code == 4:
                acting_leader = member_data
            elif role_code == 2:
                officers.append(member_data)
            else:
                members.append(member_data)
                
        return {
            "success": True, "leader": leader, "acting_leader": acting_leader,
            "officers": officers, "members": members, "total_members": len(entries_list),
            "members_raw_bytes": content
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

def request_join_clan(token, clan_id):
    try:
        region = get_server_from_token(token)
        base_url = get_base_url(region)
        url = f"{base_url}RequestJoinClan"
        
        msg_payload = create_proto_sync({1: int(clan_id)})
        encrypted_bytes = E_AEs(msg_payload.hex())
        
        headers = {
            "Accept-Encoding": "gzip", "Authorization": f"Bearer {token}",
            "Connection": "Keep-Alive", "Content-Type": "application/octet-stream",
            "Expect": "100-continue", "ReleaseVersion": "OB54",
            "X-GA": "v1 1", "X-Unity-Version": "2018.4.11f1"
        }
        
        resp = requests.post(url, headers=headers, data=encrypted_bytes, timeout=12, verify=False)
        return resp.status_code == 200
    except Exception:
        return False

def quit_current_clan(token, clan_id):
    try:
        region = get_server_from_token(token)
        base_url = get_base_url(region)
        url = f"{base_url}QuitClan"
        
        msg_payload = create_proto_sync({1: int(clan_id)})
        encrypted_bytes = E_AEs(msg_payload.hex())
        
        headers = {
            "Accept-Encoding": "gzip", "Authorization": f"Bearer {token}",
            "Connection": "Keep-Alive", "Content-Type": "application/octet-stream",
            "Expect": "100-continue", "ReleaseVersion": "OB54",
            "X-GA": "v1 1", "X-Unity-Version": "2018.4.11f1"
        }
        
        resp = requests.post(url, headers=headers, data=encrypted_bytes, timeout=12, verify=False)
        return resp.status_code == 200
    except Exception: return False

# ==========================================
# FRIEND APIs WITH OB54 COMPRESSION PATCH
# ==========================================
def get_active_friend_list(token):
    try:
        author_uid = decode_author_uid(token)
        if not author_uid:
            return {"success": False, "message": "Failed to decode account token"}

        protobuf_data = create_proto_sync({1: int(author_uid)})
        encrypted_bytes = encrypt_message(protobuf_data)

        region = get_server_from_token(token)
        endpoint = get_base_url(region) + "GetFriend"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=15, verify=False)
        if res.status_code != 200:
            return {"success": False, "message": f"Server status code: {res.status_code}"}
            
        # 🟢 GZIP ডিকম্প্রেশন প্যাচ
        content = res.content
        if content.startswith(b'\x1f\x8b'):
            import gzip
            content = gzip.decompress(content)

        parsed_outer = parse_proto_bytes(content)
        friends_list = []
        
        def parse_single_friend(item_bytes):
            try:
                if not isinstance(item_bytes, bytes):
                    return None
                
                item_parsed = parse_proto_bytes(item_bytes)
                uid_val = decode_field_int(item_parsed.get(1), 0)
                if not uid_val:
                    return None
                    
                if str(uid_val) == str(author_uid):
                    return None
                    
                nickname = decode_field_str(item_parsed.get(3))
                reg = decode_field_str(item_parsed.get(6))
                level_val = decode_field_int(item_parsed.get(8), 1)
                
                avatar_id = decode_field_int(item_parsed.get(28), 0)
                if avatar_id == 0:
                    avatar_id = decode_field_int(item_parsed.get(32), 902000003)
                
                g_name = decode_field_str(item_parsed.get(29))
                guild_id_val = decode_field_str(item_parsed.get(63))
                ver = decode_field_str(item_parsed.get(57))
                
                return {
                    "uid": str(uid_val),
                    "nickname": nickname.strip() if nickname else "Unknown",
                    "region": reg.strip() if reg else "N/A",
                    "level": int(level_val),
                    "avatar_id": str(avatar_id),
                    "guild_name": g_name.strip() if g_name.strip() else "No Guild",
                    "guild_id": str(guild_id_val).strip(),
                    "version": ver.strip()
                }
            except Exception as ex:
                return None

        items_1 = parsed_outer.get(1)
        if not items_1:
            return {"success": True, "friends": [], "friends_raw_bytes": content}

        if isinstance(items_1, list):
            for item in items_1:
                parsed = parse_single_friend(item)
                if parsed:
                    friends_list.append(parsed)

        if len(friends_list) == 0:
            if isinstance(items_1, bytes):
                inner_1 = parse_proto_bytes(items_1)
                items_2 = inner_1.get(1)
                if isinstance(items_2, list):
                    for item in items_2:
                        parsed = parse_single_friend(item)
                        if parsed:
                            friends_list.append(parsed)
                elif isinstance(items_2, bytes):
                    parsed = parse_single_friend(items_2)
                    if parsed:
                        friends_list.append(parsed)

        return {"success": True, "friends": friends_list, "friends_raw_bytes": content}
    except Exception as e:
        return {"success": False, "message": str(e)}

# 🟢 DYNAMIC & BUG-FREE ADD FRIEND PROTOBUF GENERATOR
def add_target_friend(token, target_uid):
    try:
        author_uid = decode_author_uid(token)
        if not author_uid:
            return False

        my_uid_int = int(author_uid)
        target_uid_int = int(target_uid)

        # 🟢 OB54 DYNAMIC PROTOBUF PACKET GENERATOR (BUG FIXED)
        # Field 1: my_uid (varint)
        # Field 2: target_uid (varint)
        # Field 3: source (varint, e.g. 1)
        proto_bytes = create_proto_sync({
            1: my_uid_int,
            2: target_uid_int,
            3: 1
        })
        
        encrypted_payload = encrypt_api(proto_bytes.hex())

        region = get_server_from_token(token)
        endpoint = get_base_url(region) + "RequestAddingFriend"

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        res = requests.post(endpoint, data=bytes.fromhex(encrypted_payload), headers=headers, timeout=10, verify=False)
        return res.status_code == 200
    except Exception as e:
        print(f"[Add Friend API Error] {e}")
        return False

def delete_active_friend(token, target_uid):
    try:
        author_uid = decode_author_uid(token)
        if not author_uid: return False

        msg_fields = {1: int(author_uid), 2: int(target_uid)}
        encrypted_bytes = encrypt_message(create_proto_sync(msg_fields))
        region = get_server_from_token(token)
        endpoint = get_base_url(region) + "RemoveFriend"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=10, verify=False)
        return res.status_code == 200
    except Exception: return False

def get_pending_request_list(token):
    try:
        author_uid = decode_author_uid(token)
        if not author_uid: return {"success": False, "message": "Failed to decode account token"}

        protobuf_data = create_proto_sync({1: int(author_uid)})
        encrypted_bytes = encrypt_message(protobuf_data)

        region = get_server_from_token(token)
        endpoint = get_base_url(region) + "GetFriendRequestList"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=15, verify=False)
        if res.status_code != 200: return {"success": False, "message": f"Server status: {res.status_code}"}
            
        parsed_outer = parse_proto_bytes(res.content)
        outer_1 = parsed_outer.get(1)
        if not outer_1: return {"success": True, "requests": [], "pending_raw_bytes": res.content}

        if isinstance(outer_1, bytes): inner_1 = parse_proto_bytes(outer_1)
        elif isinstance(outer_1, list): inner_1 = parse_proto_bytes(outer_1[0])
        else: return {"success": True, "requests": [], "pending_raw_bytes": res.content}
            
        pending_items = inner_1.get(1)
        if not pending_items: return {"success": True, "requests": [], "pending_raw_bytes": res.content}

        requests_list = []
        def safe_date_convert(ts):
            try:
                if not ts or ts == 0: return "N/A"
                return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %I:%M %p')
            except: return "N/A"

        def parse_single_request(item_bytes):
            try:
                if not isinstance(item_bytes, bytes): return None
                item_parsed = parse_proto_bytes(item_bytes)
                uid_val = decode_field_int(item_parsed.get(1), 0)
                if not uid_val: return None
                    
                nickname = decode_field_str(item_parsed.get(3))
                reg = decode_field_str(item_parsed.get(5))
                level_val = decode_field_int(item_parsed.get(6), 1)
                avatar_id = decode_field_int(item_parsed.get(12), 902000003)
                
                exp_val = decode_field_int(item_parsed.get(7), 0)
                br_rank_val = decode_field_int(item_parsed.get(14), 0)
                ranking_points_val = decode_field_int(item_parsed.get(15), 0)
                badge_cnt_val = decode_field_int(item_parsed.get(18), 0)
                liked_val = decode_field_int(item_parsed.get(21), 0)
                
                request_ts = decode_field_int(item_parsed.get(24), 0)
                cs_rank_val = decode_field_int(item_parsed.get(30), 0)
                max_rank_val = decode_field_int(item_parsed.get(35), 0)
                cs_max_rank_val = decode_field_int(item_parsed.get(36), 0)
                create_ts = decode_field_int(item_parsed.get(44), 0)
                version_bytes = item_parsed.get(50, b"N/A")
                
                guild_name = decode_field_str(item_parsed.get(29)).strip()
                if not guild_name or guild_name == "No Guild" or guild_name == "":
                    tag_41_bytes = item_parsed.get(41)
                    if isinstance(tag_41_bytes, bytes):
                        tag_41_parsed = parse_proto_bytes(tag_41_bytes)
                        g_bytes = tag_41_parsed.get(5, b"No Guild")
                        guild_name = g_bytes.decode('utf-8', errors='ignore') if isinstance(g_bytes, bytes) else str(g_bytes)

                version = version_bytes.decode('utf-8', errors='ignore') if isinstance(version_bytes, bytes) else str(version_bytes)

                return {
                    "uid": str(uid_val), "nickname": nickname.strip() if nickname else "Unknown",
                    "region": reg.strip() if reg else "N/A", "level": int(level_val),
                    "avatar_id": str(avatar_id), "exp": int(exp_val), "br_rank": int(br_rank_val),
                    "br_points": int(ranking_points_val), "badge_count": int(badge_cnt_val),
                    "likes": int(liked_val), "request_time": safe_date_convert(request_ts),
                    "last_login_time": safe_date_convert(request_ts), "cs_rank": int(cs_rank_val),
                    "max_rank": int(max_rank_val), "cs_max_rank": int(cs_max_rank_val),
                    "created_time": safe_date_convert(create_ts), "version": version.strip(),
                    "guild_name": guild_name.strip() if guild_name else "No Guild"
                }
            except Exception: return None

        if isinstance(pending_items, list):
            for item in pending_items:
                res_obj = parse_single_request(item)
                if res_obj: requests_list.append(res_obj)
        elif isinstance(pending_items, bytes):
            res_obj = parse_single_request(pending_items)
            if res_obj: requests_list.append(res_obj)

        return {"success": True, "requests": requests_list, "pending_raw_bytes": res.content}
    except Exception as e: return {"success": False, "message": str(e)}

def accept_friend_request(token, target_uid):
    try:
        author_uid = decode_author_uid(token)
        if not author_uid: return False

        msg_fields = {1: int(target_uid)}
        encrypted_bytes = encrypt_message(create_proto_sync(msg_fields))
        region = get_server_from_token(token)
        endpoint = get_base_url(region) + "ConfirmFriendRequest"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=10, verify=False)
        return res.status_code == 200
    except Exception: return False

def reject_friend_request(token, target_uid):
    try:
        author_uid = decode_author_uid(token)
        if not author_uid: return False

        msg_fields = {1: int(target_uid)}
        encrypted_bytes = encrypt_message(create_proto_sync(msg_fields))
        region = get_server_from_token(token)
        endpoint = get_base_url(region) + "DeclineFriendRequest"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=10, verify=False)
        return res.status_code == 200
    except Exception: return False