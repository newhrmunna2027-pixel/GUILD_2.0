# -*- coding: utf-8 -*-
# utils/api_client.py - Native Garena API Wrapper (Fixed Circular Reference & Native Decoders)

import os
import sys
import asyncio
import sqlite3

# পরম পাথ (Absolute Path) জেনারেটর যা ডিরেক্টরি অমিল এড়াতে সাহায্য করে
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'config', 'database.db')

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import garena_api as bot_module

async def retrieve_active_bot_token():
    """ডাটাবেস থেকে সক্রিয় বোতের সেশন টোকেন রিট্রিভ করার জন্য মেথড (ডাবল-লেয়ার ফলব্যাক সহ)"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    try:
        # বটের নাম, লগইন ইউআইডি ও পাসওয়ার্ড সবগুলো রিড করা হলো ফলব্যাকের জন্য
        cursor.execute("SELECT name, login_uid, password FROM bots")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[API Client DB Error] {e}")
        rows = []
    finally:
        conn.close()

    for row in rows:
        bot_name, login_uid, password = row[0], row[1], row[2]
        loop = asyncio.get_running_loop()
        try:
            # ১. প্রথমে সক্রিয় সেশন ফাইল থেকে টোকেন চেক করবে (Extremely Fast)
            token, _ = await loop.run_in_executor(None, bot_module.get_active_token, bot_name)
            if token:
                return token
        except Exception as e:
            print(f"[API Client] Active token check error for {bot_name}: {e}")
            
        # ২. সেশন ফাইল মিসিং বা এক্সপায়ার হলে ডাটাবেজের ক্রিডেনশিয়ালস দিয়ে রিয়াল-টাইম টোকেন জেনারেট করবে
        if login_uid and password:
            try:
                token, _ = await loop.run_in_executor(None, bot_module.get_token_from_uid_password, login_uid, password)
                if token:
                    # নতুন সেশন টোকেনটি সেভ করে রাখা হলো
                    bot_module.save_session({"uid": login_uid, "password": password, "token": token}, bot_name)
                    return token
            except Exception as e:
                print(f"[API Client] Real-time fallback token generation failed for {bot_name}: {e}")
                
    return None

def map_garena_to_info_format(res):
    """garena_api এর কাঁচা জেসন ডাটাকে বটের ইনফো কমান্ডের উপযোগী ফরম্যাটে রূপান্তর"""
    if not res or not res.get("success"):
        return None
        
    json_data = res.get("json_data", {})
    if not isinstance(json_data, dict):
        json_data = {}
        
    def safe_get_dict(parent, key):
        val = parent.get(str(key))
        return val if isinstance(val, dict) else {}

    # গ্যারেনার বাইনারি টেক্সট (Bytes) এবং ইন্টিজার সেফটি ডিকোডার হেল্পার
    def decode_str(val):
        if isinstance(val, bytes):
            return val.decode('utf-8', errors='ignore')
        if isinstance(val, list) and len(val) > 0:
            first = val[0]
            return first.decode('utf-8', errors='ignore') if isinstance(first, bytes) else str(first)
        return str(val) if val is not None else ""

    def decode_int(val, default=0):
        if isinstance(val, int): return val
        if isinstance(val, list) and len(val) > 0:
            first = val[0]
            try: return int(first)
            except: return default
        try: return int(val)
        except: return default

    basic = safe_get_dict(json_data, 1)
    credit = safe_get_dict(json_data, 3)
    pet = safe_get_dict(json_data, 4)
    clan = safe_get_dict(json_data, 6)
    captain = safe_get_dict(json_data, 8)
    social = safe_get_dict(json_data, 9)

    # 🟢 FIXED: Re-wrote clean mapping without any undefined circular references
    basic_info = {
        "nickname": decode_str(basic.get("3")) or res.get("nickname") or "Unknown",
        "accountId": str(decode_int(basic.get("1")) or res.get("uid") or "0"),
        "account_id": str(decode_int(basic.get("1")) or res.get("uid") or "0"),
        "level": int(decode_int(basic.get("6")) or res.get("level") or 0),
        "exp": int(decode_int(basic.get("7")) or 0),
        "liked": int(decode_int(basic.get("21")) or res.get("likes") or 0),
        "createAt": str(decode_str(basic.get("44")) or res.get("created_at") or "0"),
        "create_at": str(decode_str(basic.get("44")) or res.get("created_at") or "0"),
        "lastLoginAt": str(decode_str(basic.get("24")) or res.get("last_login") or "0"),
        "last_login_at": str(decode_str(basic.get("24")) or res.get("last_login") or "0")
    }

    credit_info = {
        "creditScore": int(decode_int(credit.get("1")) or 100),
        "credit_score": int(decode_int(credit.get("1")) or 100)
    }

    social_info = {
        "signature": decode_str(social.get("9")) or res.get("signature") or "No Signature"
    }

    clan_info = {
        "clanName": decode_str(clan.get("2")) or res.get("clan_name") or "No Guild",
        "clan_name": decode_str(clan.get("2")) or res.get("clan_name") or "No Guild",
        "clanId": str(decode_str(clan.get("1")) or res.get("clan_id") or "N/A"),
        "clan_id": str(decode_str(clan.get("1")) or res.get("clan_id") or "N/A"),
        "captainId": str(decode_str(clan.get("3")) or res.get("leader_uid") or "N/A"),
        "captain_id": str(decode_str(clan.get("3")) or res.get("leader_uid") or "N/A"),
        "memberNum": int(decode_int(clan.get("4")) or 0),
        "member_num": int(decode_int(clan.get("4")) or 0),
        "capacity": int(decode_int(clan.get("5")) or 50)
    }

    captain_info = {
        "nickname": decode_str(captain.get("3")) or "Unknown"
    }

    pet_info = {
        "id": int(decode_int(pet.get("1")) or 0),
        "name": decode_str(pet.get("2")) or ""
    }

    return {
        "basicInfo": basic_info,
        "basic_info": basic_info,
        "creditScoreInfo": credit_info,
        "credit_score_info": credit_info,
        "socialInfo": social_info,
        "social_info": social_info,
        "clanBasicInfo": clan_info,
        "clan_basic_info": clan_info,
        "captainBasicInfo": captain_info,
        "captain_basic_info": captain_info,
        "petInfo": pet_info,
        "pet_info": pet_info
    }

async def fetch_player_info(uid, retries=3):
    """৩য় পক্ষের সার্ভারের সাহায্য ছাড়া সরাসরি গ্যারেনা গেটওয়ে থেকে প্লেয়ার ডাটা স্ক্যান"""
    if not uid:
        return None
        
    token = await retrieve_active_bot_token()
    if not token:
        print("[API Client Error] No active Garena Token found in database. Cannot scan player.")
        return None

    for attempt in range(retries):
        try:
            loop = asyncio.get_running_loop()
            # requests ব্লকিং এড়াতে থ্রেড পুল এক্সিকিউটর ব্যবহার করা হয়েছে
            res = await loop.run_in_executor(None, bot_module.get_player_info_detailed, str(uid), token)
            if res and res.get("success"):
                return map_garena_to_info_format(res)
        except Exception as e:
            if attempt == retries - 1:
                print(f"[API Client Error] Garena request failed for UID {uid}: {e}")
            else:
                await asyncio.sleep(1.0)
    return None
