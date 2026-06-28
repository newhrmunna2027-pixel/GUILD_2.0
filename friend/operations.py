# filepath: friend/operations.py
# -*- coding: utf-8 -*-

import bot_core
import requests
import gzip
from datetime import datetime

def get_active_friend_list(token):
    try:
        author_uid = bot_core.decode_author_uid(token)
        if not author_uid:
            return {"success": False, "message": "Failed to decode account token"}

        protobuf_data = bot_core.create_proto_sync({1: int(author_uid)})
        encrypted_bytes = bot_core.encrypt_message(protobuf_data)

        region = bot_core.get_server_from_token(token)
        endpoint = bot_core.get_base_url(region) + "GetFriend"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=15, verify=False)
        if res.status_code != 200:
            return {"success": False, "message": f"Server status code: {res.status_code}"}
            
        content = res.content
        if content.startswith(b'\x1f\x8b'):
            content = gzip.decompress(content)

        parsed_outer = bot_core.parse_proto_bytes(content)
        friends_list = []
        
        def parse_single_friend(item_bytes):
            try:
                if not isinstance(item_bytes, bytes):
                    return None
                
                item_parsed = bot_core.parse_proto_bytes(item_bytes)
                uid_val = bot_core.decode_field_int(item_parsed.get(1), 0)
                if not uid_val:
                    return None
                    
                if str(uid_val) == str(author_uid):
                    return None
                    
                nickname = bot_core.decode_field_str(item_parsed.get(3))
                reg = bot_core.decode_field_str(item_parsed.get(6))
                level_val = bot_core.decode_field_int(item_parsed.get(8), 1)
                
                avatar_id = bot_core.decode_field_int(item_parsed.get(28), 0)
                if avatar_id == 0:
                    avatar_id = bot_core.decode_field_int(item_parsed.get(32), 902000003)
                
                g_name = bot_core.decode_field_str(item_parsed.get(29))
                guild_id_val = bot_core.decode_field_str(item_parsed.get(63))
                ver = bot_core.decode_field_str(item_parsed.get(57))
                
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
            except Exception:
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
                inner_1 = bot_core.parse_proto_bytes(items_1)
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

def add_target_friend(token, target_uid):
    try:
        author_uid = bot_core.decode_author_uid(token)
        if not author_uid:
            return False

        my_uid_int = int(author_uid)
        target_uid_int = int(target_uid)

        proto_bytes = bot_core.create_proto_sync({
            1: my_uid_int,
            2: target_uid_int,
            3: 1
        })
        
        encrypted_payload = bot_core.encrypt_api(proto_bytes.hex())

        region = bot_core.get_server_from_token(token)
        endpoint = bot_core.get_base_url(region) + "RequestAddingFriend"

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
        author_uid = bot_core.decode_author_uid(token)
        if not author_uid: return False

        msg_fields = {1: int(author_uid), 2: int(target_uid)}
        encrypted_bytes = bot_core.encrypt_message(bot_core.create_proto_sync(msg_fields))
        region = bot_core.get_server_from_token(token)
        endpoint = bot_core.get_base_url(region) + "RemoveFriend"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=10, verify=False)
        return res.status_code == 200
    except Exception: return False

def get_pending_request_list(token):
    try:
        author_uid = bot_core.decode_author_uid(token)
        if not author_uid: return {"success": False, "message": "Failed to decode account token"}

        protobuf_data = bot_core.create_proto_sync({1: int(author_uid)})
        encrypted_bytes = bot_core.encrypt_message(protobuf_data)

        region = bot_core.get_server_from_token(token)
        endpoint = bot_core.get_base_url(region) + "GetFriendRequestList"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=15, verify=False)
        if res.status_code != 200: return {"success": False, "message": f"Server status: {res.status_code}"}
            
        parsed_outer = bot_core.parse_proto_bytes(res.content)
        outer_1 = parsed_outer.get(1)
        if not outer_1: return {"success": True, "requests": [], "pending_raw_bytes": res.content}

        if isinstance(outer_1, bytes): inner_1 = bot_core.parse_proto_bytes(outer_1)
        elif isinstance(outer_1, list): inner_1 = bot_core.parse_proto_bytes(outer_1[0])
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
                item_parsed = bot_core.parse_proto_bytes(item_bytes)
                uid_val = bot_core.decode_field_int(item_parsed.get(1), 0)
                if not uid_val: return None
                    
                nickname = bot_core.decode_field_str(item_parsed.get(3))
                reg = bot_core.decode_field_str(item_parsed.get(5))
                level_val = bot_core.decode_field_int(item_parsed.get(6), 1)
                avatar_id = bot_core.decode_field_int(item_parsed.get(12), 902000003)
                
                exp_val = bot_core.decode_field_int(item_parsed.get(7), 0)
                br_rank_val = bot_core.decode_field_int(item_parsed.get(14), 0)
                ranking_points_val = bot_core.decode_field_int(item_parsed.get(15), 0)
                badge_cnt_val = bot_core.decode_field_int(item_parsed.get(18), 0)
                liked_val = bot_core.decode_field_int(item_parsed.get(21), 0)
                
                request_ts = bot_core.decode_field_int(item_parsed.get(24), 0)
                cs_rank_val = bot_core.decode_field_int(item_parsed.get(30), 0)
                max_rank_val = bot_core.decode_field_int(item_parsed.get(35), 0)
                cs_max_rank_val = bot_core.decode_field_int(item_parsed.get(36), 0)
                create_ts = bot_core.decode_field_int(item_parsed.get(44), 0)
                version_bytes = item_parsed.get(50, b"N/A")
                
                guild_name = bot_core.decode_field_str(item_parsed.get(29)).strip()
                if not guild_name or guild_name == "No Guild" or guild_name == "":
                    tag_41_bytes = item_parsed.get(41)
                    if isinstance(tag_41_bytes, bytes):
                        tag_41_parsed = bot_core.parse_proto_bytes(tag_41_bytes)
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
        author_uid = bot_core.decode_author_uid(token)
        if not author_uid: return False

        msg_fields = {1: int(target_uid)}
        encrypted_bytes = bot_core.encrypt_message(bot_core.create_proto_sync(msg_fields))
        region = bot_core.get_server_from_token(token)
        endpoint = bot_core.get_base_url(region) + "ConfirmFriendRequest"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=10, verify=False)
        return res.status_code == 200
    except Exception: return False

def reject_friend_request(token, target_uid):
    try:
        author_uid = bot_core.decode_author_uid(token)
        if not author_uid: return False

        msg_fields = {1: int(target_uid)}
        encrypted_bytes = bot_core.encrypt_message(bot_core.create_proto_sync(msg_fields))
        region = bot_core.get_server_from_token(token)
        endpoint = bot_core.get_base_url(region) + "DeclineFriendRequest"

        headers = {
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1", 'X-GA': "v1 1", 'ReleaseVersion': "OB54"
        }
        res = requests.post(endpoint, data=encrypted_bytes, headers=headers, timeout=10, verify=False)
        return res.status_code == 200
    except Exception: return False

def check_duo_native(token, target_uid):
    try:
        region = bot_core.get_server_from_token(token)
        base_url = bot_core.get_base_url(region)
        url = f"{base_url}GetSpecialFriendList"
        
        payload = bot_core.YOuR_FaThER(target_uid)
        
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
            decrypted = bot_core.UNknown(res.content)
            parsed_outer = bot_core.parse_proto_bytes(decrypted)
            
            duo_bytes = parsed_outer.get(1)
            if not duo_bytes or not isinstance(duo_bytes, bytes):
                return {"success": False, "message": "No Dynamic Duo info found for this player."}
                
            duo_parsed = bot_core.parse_proto_bytes(duo_bytes)
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
            
            raw_tree = bot_core.make_serializable(duo_parsed)
            
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
                "name_json_data": bot_core.map_proto_to_named(raw_tree, "Duo")
            }
        elif res.status_code == 500:
            return {"success": False, "message": "Private profile or invalid player UID."}
        return {"success": False, "message": f"Server returned error code: {res.status_code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
