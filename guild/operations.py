# filepath: guild/operations.py
# -*- coding: utf-8 -*-

import bot_core
import requests
import gzip
from datetime import datetime

def get_clan_info_by_id(token, clan_id):
    try:
        region = bot_core.get_server_from_token(token)
        base_url = bot_core.get_base_url(region)
        
        serialized = bot_core.create_proto_sync({1: int(clan_id), 2: 1})
        encrypted = bot_core.E_AEs(serialized.hex())
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
            
        parsed = bot_core.parse_proto_bytes(content)
        
        id_val = bot_core.decode_field_int(parsed.get(1))
        name_val = bot_core.decode_field_str(parsed.get(2))
        ts_created = bot_core.decode_field_int(parsed.get(3))
        leader_uid = bot_core.decode_field_str(parsed.get(4))
        level_val = bot_core.decode_field_int(parsed.get(5))
        max_members = bot_core.decode_field_int(parsed.get(6))
        total_members = bot_core.decode_field_int(parsed.get(7))
        welcome_msg = bot_core.decode_field_str(parsed.get(12))
        region_val = bot_core.decode_field_str(parsed.get(13))
        
        officers_list = []
        off_val = parsed.get(15)
        if isinstance(off_val, list):
            for o in off_val: officers_list.append(str(o))
        elif off_val:
            officers_list.append(str(off_val))
            
        past_glory = bot_core.decode_field_int(parsed.get(16))
        acting_leader = bot_core.decode_field_str(parsed.get(23))
        total_glory = bot_core.decode_field_int(parsed.get(36))
        recent_glory = bot_core.decode_field_int(parsed.get(37))
        
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
        region = bot_core.get_server_from_token(token)
        base_url = bot_core.get_base_url(region)
        
        req_bytes = bot_core.create_proto_sync({1: int(clan_id)})
        encrypted = bot_core.E_AEs(req_bytes.hex())
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

        content = resp.content
        if content.startswith(b'\x1f\x8b'):
            content = gzip.decompress(content)

        parsed = bot_core.parse_proto_bytes(content)
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
            entry = bot_core.parse_proto_bytes(entry_bytes)
            
            info_bytes = entry.get(1)
            if not info_bytes or not isinstance(info_bytes, bytes): continue
            info = bot_core.parse_proto_bytes(info_bytes)
            
            uid_val = info.get(1, 0)
            name_val = decode_str(info.get(3, b"Unknown"))
            
            lvl_val = bot_core.decode_field_int(info.get(6), 1)
            avatar_id = bot_core.decode_field_int(info.get(12), 902000003)
            
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
        region = bot_core.get_server_from_token(token)
        base_url = bot_core.get_base_url(region)
        url = f"{base_url}RequestJoinClan"
        
        msg_payload = bot_core.create_proto_sync({1: int(clan_id)})
        encrypted_bytes = bot_core.E_AEs(msg_payload.hex())
        
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
        region = bot_core.get_server_from_token(token)
        base_url = bot_core.get_base_url(region)
        url = f"{base_url}QuitClan"
        
        msg_payload = bot_core.create_proto_sync({1: int(clan_id)})
        encrypted_bytes = bot_core.E_AEs(msg_payload.hex())
        
        headers = {
            "Accept-Encoding": "gzip", "Authorization": f"Bearer {token}",
            "Connection": "Keep-Alive", "Content-Type": "application/octet-stream",
            "Expect": "100-continue", "ReleaseVersion": "OB54",
            "X-GA": "v1 1", "X-Unity-Version": "2018.4.11f1"
        }
        
        resp = requests.post(url, headers=headers, data=encrypted_bytes, timeout=12, verify=False)
        return resp.status_code == 200
    except Exception: return False
