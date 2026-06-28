# -*- coding: utf-8 -*-
# bot/commands/actions_info.py

import asyncio
import json
import os
import aiohttp
import re
from datetime import datetime
import time
import aiosqlite
from bot.commands.bomber_task import trigger_all_bombs
from utils.helpers import (
    format_uid_for_chat, resolve_uids, get_pet_default_name,
    add_uids_to_list, remove_uids_from_list, load_saved_uids         
)

from utils import admin_manager
from utils.api_client import fetch_player_info 
from utils.translations import t

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRANSLATIONS_FILE = os.path.join(BASE_DIR, 'config', 'translations.json')

HELP_MENU_STATES = {}

def get_clean_bio_lines(text):
    if not text or text == "N/A": return ["N/A"]
    clean_text = re.sub(r'(?i)\[c\]', '', text)
    raw_lines =[line.strip() for line in clean_text.split('\n') if line.strip()]
    if not raw_lines: return ["N/A"]

    SECOND_LINE_LIMIT = 25
    processed_lines =[]
    overflow_lines =[] 
    current_color = "" 
    
    for i, line in enumerate(raw_lines):
        if not re.match(r'^\[[0-9a-fA-F]{6}\]', line):
            formatted_line = current_color + line
        else:
            formatted_line = line
            
        colors = re.findall(r'\[[0-9a-fA-F]{6}\]', formatted_line)
        if colors: current_color = colors[-1]

        if i == 1:
            visible_text = re.sub(r'\[[a-zA-Z0-9]+\]', '', formatted_line)
            if len(visible_text) > SECOND_LINE_LIMIT:
                tags = re.findall(r'\[[a-zA-Z0-9]+\]', formatted_line)
                tag_len = sum(len(t) for t in tags)
                actual_limit = SECOND_LINE_LIMIT + tag_len
                split_idx = formatted_line.rfind(' ', 0, actual_limit)
                if split_idx == -1 or split_idx < 10: split_idx = actual_limit
                    
                part1 = formatted_line[:split_idx]
                part2 = formatted_line[split_idx:].strip()
                processed_lines.append(part1) 
                
                if part2:
                    p1_colors = re.findall(r'\[[0-9a-fA-F]{6}\]', part1)
                    part2_color = p1_colors[-1] if p1_colors else current_color
                    if not re.match(r'^\[[0-9a-fA-F]{6}\]', part2):
                        overflow_lines.append(part2_color + part2)
                    else:
                        overflow_lines.append(part2)
            else:
                processed_lines.append(formatted_line)
        else:
            processed_lines.append(formatted_line)
            
    processed_lines.extend(overflow_lines)
    return processed_lines

def format_number_with_stone(num):
    try:
        if isinstance(num, str) and not num.isdigit(): return num
        return "{:,}".format(int(num)).replace(",", "🗿")
    except: return str(num)

def ts_to_date(ts):
    if ts is None: return "N/A"
    ts_str = str(ts).strip()
    if not ts_str or ts_str.lower() in["0", "none", "n/a", ""]: return "N/A"
    try:
        digits = ''.join(filter(str.isdigit, ts_str))
        if not digits: return "N/A"
        if len(digits) >= 10: ts_int = int(digits[:10])
        else: ts_int = int(digits)
        if ts_int == 0: return "N/A"
        dt = datetime.fromtimestamp(ts_int)
        return f"{dt.day:02d}⚡/{dt.month:02d}⚡/{str(dt.year)[-2:]}  {dt.hour:02d}⚡:{dt.minute:02d}⚡:{dt.second:02d}"
    except: return "N/A"

async def handle_lang_en(client, ctx, args):
    uid = str(ctx['uid'])
    if not (admin_manager.is_owner(uid) or uid in admin_manager.get_admins(client.my_uid)):
        await client.send_chat_message(t(client, 'no_permission'), ctx)
        return
    client.lang = "en"
    admin_manager.save_bot_lang(client.my_uid, "en")
    await client.send_chat_message(t(client, 'lang_en'), ctx)

async def handle_lang_bn(client, ctx, args):
    uid = str(ctx['uid'])
    if not (admin_manager.is_owner(uid) or uid in admin_manager.get_admins(client.my_uid)):
        await client.send_chat_message(t(client, 'no_permission'), ctx)
        return
    client.lang = "bn"
    admin_manager.save_bot_lang(client.my_uid, "bn")
    await client.send_chat_message(t(client, 'lang_bn'), ctx)

async def handle_simple_replies(client, ctx):
    msg = ctx['msg'].lower().strip()
    uid = str(ctx['uid'])
    
    if msg in['hi', 'hello', 'hlo', 'hey'] or any(x in msg for x in['salam', 'assalamu', 'asw', 'slm']):
        sender_name = await format_uid_for_chat(uid) 
        try:
            player_data = await fetch_player_info(uid)
            if player_data:
                b_info = player_data.get('basicInfo') or player_data.get('basic_info') or {}
                if b_info.get('nickname'):
                    sender_name = b_info.get('nickname')
        except: pass 
            
        greeting = "Salam" if any(x in msg for x in['salam', 'assalamu', 'asw', 'slm']) else "Hello"
        text_msg = t(client, "greeting_msg", greeting=greeting, name=sender_name)
        
        await client.send_chat_message(text_msg, ctx)
        await asyncio.sleep(1.0)
        
        ascii_banner = (
            "[b][c][400C4C]✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿\n"
            "\n"
            "\n"
            "   [b][c][C0C0C0]     █▀█  █       █ ▀█▀   █▀█   █▀▀    █        █▀█    █    █   █   \n"
            "    [b][c][C0C0C0]    █▄█  ▀▄▄▀     █      █▄█   █▀        █▄▄ █▀█    ▀▄▀▄▀   \n"
            "\n"
            "\n"
            "[b][c][FF0000]☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯☯\n"
        )
        await client.send_chat_message(ascii_banner, ctx)
        return True

    if msg in['help', '/help', '/h']:
        await handle_help(client, ctx)
        return True
        
    return False

async def send_help_category(client, ctx, category_id):
    msg_key = f"help_cat_{category_id}"
    msg = t(client, msg_key)
    await client.send_chat_message(msg, ctx)

async def handle_help(client, ctx, args=None):
    uid = str(ctx['uid'])
    HELP_MENU_STATES[f"{client.my_uid}_{uid}"] = True
    
    await client.send_chat_message(t(client, 'help_menu_1'), ctx)
    await asyncio.sleep(0.5)
    
    await client.send_chat_message(t(client, 'help_menu_2'), ctx)
    
async def handle_add_uid(client, ctx, args):
    if len(args) < 2:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/add [uid1] [uid2]..."), ctx)
        return
    uids_to_add = args[1:]
    current_list, count = await add_uids_to_list(client.my_uid, uids_to_add)
    if count > 0:
        await client.send_chat_message(t(client, "add_uid_success", count=count, size=len(current_list)), ctx)
    else:
        await client.send_chat_message(t(client, "add_uid_fail"), ctx)

async def handle_remove_uid(client, ctx, args):
    if len(args) < 2:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/rev [number] or [uid]..."), ctx)
        return
    args_to_remove = args[1:]
    new_list, removed_uids = await remove_uids_from_list(client.my_uid, args_to_remove)
    
    if removed_uids:
        msg_body = ""
        for r_uid in removed_uids:
            f_uid = await format_uid_for_chat(r_uid)
            msg_body += f"[b][FFFFFF]   ❌ {f_uid}\n"
        await client.send_chat_message(t(client, "remove_uid_success", msg_body=msg_body, size=len(new_list)), ctx)
    else:
        await client.send_chat_message(t(client, "remove_uid_fail"), ctx)

async def handle_show_list(client, ctx, args):
    uids_list = await load_saved_uids(client.my_uid)
    if not uids_list:
        await client.send_chat_message(t(client, "saved_list_empty"), ctx)
        return
    list_body = ""
    for i, uid in enumerate(uids_list):
        fmt_uid = await format_uid_for_chat(uid)
        num_str = f"{i+1:02d}" 
        list_body += f"[b][FFFF00] {num_str}.[FFFFFF]{fmt_uid}\n"
    await client.send_chat_message(t(client, "saved_list_header", list_body=list_body), ctx)

async def handle_status_check(client, ctx, args):
    target_uids = await resolve_uids(client, args[1:], ctx)
    if not target_uids:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/status [uid/me/all]"), ctx)
        return
    await client.send_chat_message(t(client, "checking_status", count=len(target_uids)), ctx)
    from bot.packets import team_packets

    # 🟢 sequential execution background task with 10s delay if multiple uids are present
    async def process_sequential_status():
        for index, uid in enumerate(target_uids):
            if index > 0:
                await asyncio.sleep(10.0)
            client.status_requests[str(uid)] = ctx
            pkt = await team_packets.create_status_check_packet(uid, client.key, client.iv)
            await client.send_online_packet(pkt)

    asyncio.create_task(process_sequential_status())

async def handle_info(client, ctx, args):
    target_uids = await resolve_uids(client, args[1:], ctx, exclude_self=True)
    if not target_uids:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/info [uid]"), ctx)
        return

    await client.send_chat_message(t(client, "fetching_info", count=len(target_uids)), ctx)

    async def fetch_and_send(uid):
        try:
            data = await fetch_player_info(uid)
            if not data:
                await client.send_chat_message(t(client, "fetch_info_fail", uid=uid), ctx)
                return
            
            b_info = data.get('basicInfo') or data.get('basic_info') or {}
            c_info = data.get('creditScoreInfo') or data.get('credit_score_info') or {}
            s_info = data.get('socialInfo') or data.get('social_info') or {}
            cl_info = data.get('clanBasicInfo') or data.get('clan_basic_info') or {}
            cap_info = data.get('captainBasicInfo') or data.get('captain_basic_info') or {}
            p_info = data.get('petInfo') or data.get('pet_info') or {}
            
            p_pet_name = p_info.get('name')
            p_pet_id = p_info.get('id')
            if p_pet_name: final_pet_name = p_pet_name
            elif p_pet_id: final_pet_name = get_pet_default_name(p_pet_id)
            else: final_pet_name = "No Pet"

            p_name = b_info.get('nickname', 'N/A')
            raw_uid = b_info.get('accountId') or b_info.get('account_id') or uid
            p_uid = await format_uid_for_chat(raw_uid)
            raw_lvl = b_info.get('level', 0)
            p_lvl = str(raw_lvl)
            p_exp = format_number_with_stone(b_info.get('exp', 'N/A'))
            raw_likes = b_info.get('liked', 0)
            p_likes = format_number_with_stone(raw_likes)
            p_honor = c_info.get('creditScore') or c_info.get('credit_score') or 'N/A'
            
            raw_login = b_info.get('lastLoginAt') or b_info.get('last_login_at')
            raw_create = b_info.get('createAt') or b_info.get('create_at')
            
            if not raw_login:
                for k, v in b_info.items():
                    if 'login' in k.lower() and any(c.isdigit() for c in str(v)):
                        raw_login = v; break
            if not raw_create:
                for k, v in b_info.items():
                    if 'create' in k.lower() and any(c.isdigit() for c in str(v)):
                        raw_create = v; break

            p_login = ts_to_date(raw_login)
            p_create = ts_to_date(raw_create)
            
            bio_lines = get_clean_bio_lines(s_info.get('signature', 'N/A'))
            bio_display = "[b][c][FF0000]╭━[FFFFFF]Signature[FF0000]━━━━╮\n"
            for line in bio_lines: bio_display += f"[b][FFFFFF]{line}\n"

            g_name = cl_info.get('clanName') or cl_info.get('clan_name') or 'No Guild'
            l_name = cap_info.get('nickname', 'N/A')
            raw_l_uid = cl_info.get('captainId') or cl_info.get('captain_id') or 'N/A'
            l_uid = await format_uid_for_chat(raw_l_uid) if raw_l_uid != 'N/A' else 'N/A'
            mem_num = cl_info.get('memberNum') or cl_info.get('member_num') or '?'
            capacity = cl_info.get('capacity', '?')
            g_size = f"{mem_num}/{capacity}"

            msg_part1 = t(client, "info_basic_template", name=p_name, uid=p_uid, level=p_lvl, exp=p_exp, likes=p_likes)
            msg_part2 = t(client, "info_data_template", honor=p_honor, pet_name=final_pet_name, login=p_login, create=p_create, bio_display=bio_display)
            msg_part3 = t(client, "info_guild_template", guild_name=g_name, leader_name=l_name, leader_uid=l_uid, size=g_size)
            
            await client.send_chat_message(msg_part1, ctx)
            await asyncio.sleep(1.2)
            await client.send_chat_message(msg_part2, ctx)
            await asyncio.sleep(1.2)
            await client.send_chat_message(msg_part3, ctx)
            
        except Exception as e:
            print(f"[INFO-API] ❌ Python Exception: {e}")
            await client.send_chat_message(t(client, 'sys_error', error=str(e)), ctx)

    tasks =[fetch_and_send(uid) for uid in target_uids]
    await asyncio.gather(*tasks)

async def handle_like(client, ctx, args):
    if len(args) < 3:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/like [region] [uid]"), ctx)
        return
        
    region = args[1].lower()
    target_uids = await resolve_uids(client, args[2:], ctx)
    
    if not target_uids:
        await client.send_chat_message("[FF0000]Invalid UID provided.", ctx)
        return

    uid = target_uids[0]
    f_uid = await format_uid_for_chat(uid)
    await client.send_chat_message(t(client, "processing_like", uid=f_uid, region=region.upper()), ctx)
    
    api_url = f"https://crownx64-like.vercel.app/like?uid={uid}&server_name={region}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        p_name = data.get("PlayerNickname", "Unknown")
                        past_likes = format_number_with_stone(data.get("LikesbeforeCommand", 0))
                        new_likes_added = format_number_with_stone(data.get("LikesGivenByAPI", 0))
                        total_likes = format_number_with_stone(data.get("LikesafterCommand", 0))
                        
                        msg = t(client, "like_success_template", name=p_name, uid=f_uid, past=past_likes, added=new_likes_added, total=total_likes)
                        await client.send_chat_message(msg, ctx)
                    except Exception:
                        await client.send_chat_message(f"[FF0000]JSON Error: Failed to parse API response.", ctx)
                else:
                    await client.send_chat_message(f"[FF0000]API Error: Status {resp.status}", ctx)
    except Exception as e:
        print(f"[LIKE-API] Exception: {e}")
        await client.send_chat_message("[FF0000]Failed to connect to Like API.", ctx)

async def handle_admin_add(client, ctx, args):
    if not admin_manager.is_owner(ctx['uid']):
        await client.send_chat_message(t(client, 'no_permission'), ctx)
        return
    uids_to_add = args[1:]
    if not uids_to_add:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/admin_add [uid1] [uid2]"), ctx)
        return
    added = admin_manager.add_admin(client.my_uid, uids_to_add)
    await client.send_chat_message(t(client, "admin_add_success", added=added), ctx)

async def handle_admin_rev(client, ctx, args):
    if not admin_manager.is_owner(ctx['uid']):
        await client.send_chat_message(t(client, 'no_permission'), ctx)
        return
    uids_to_remove = args[1:]
    if not uids_to_remove:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/admin_rev [uid1] [uid2]"), ctx)
        return
    removed = admin_manager.remove_admin(client.my_uid, uids_to_remove)
    await client.send_chat_message(t(client, "admin_rev_success", removed=removed), ctx)

async def handle_admin_list_cmd(client, ctx, args):
    admins = admin_manager.get_admins(client.my_uid)
    if not admins:
        await client.send_chat_message(t(client, "admin_list_empty"), ctx)
        return
    list_body = ""
    for i, uid in enumerate(admins):
        fmt = await format_uid_for_chat(uid)
        list_body += f"[FFFFFF]{i+1}. {fmt}\n"
    await client.send_chat_message(t(client, "admin_list_header", list_body=list_body), ctx)

async def handle_boom(client, ctx, args):
    uid = str(ctx['uid'])
    is_owner = admin_manager.is_owner(uid)
    is_admin = uid in admin_manager.get_admins(client.my_uid)
    
    if not (is_owner or is_admin):
        await client.send_chat_message(t(client, 'no_permission'), ctx)
        return

    if len(args) < 2:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/boom [11-digit-number]"), ctx)
        return
        
    target_number = str(args[1]).strip()
    if len(target_number) != 11 or not target_number.isdigit():
        await client.send_chat_message(t(client, "boom_invalid_num"), ctx)
        return

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'database.db')
    current_time = int(time.time())
    limit_hours = 24  
    time_limit = current_time - (limit_hours * 3600) 
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS boom_logs (phone TEXT, timestamp INTEGER)")
        await db.commit()
        await db.execute("DELETE FROM boom_logs WHERE timestamp < ?", (time_limit,))
        await db.commit()
        
        async with db.execute("SELECT timestamp FROM boom_logs WHERE phone = ? ORDER BY timestamp ASC", (target_number,)) as cursor:
            logs = await cursor.fetchall()
            
        if len(logs) >= 2:
            oldest_timestamp = logs[0][0] 
            unlock_time = oldest_timestamp + (limit_hours * 3600)
            remaining_seconds = unlock_time - current_time
            hours = remaining_seconds // 3600
            minutes = (remaining_seconds % 3600) // 60
            
            if hours > 0: time_str = f"{int(hours):02d}⚡H⚡{int(minutes):02d}⚡M"
            else: time_str = f"{int(minutes):02d}⚡M"
                
            await client.send_chat_message(t(client, "boom_attempts_complete", time_str=time_str), ctx)
            return
            
        await db.execute("INSERT INTO boom_logs (phone, timestamp) VALUES (?, ?)", (target_number, current_time))
        await db.commit()

    formatted_number = "⚡".join(list(target_number))
    await client.send_chat_message(t(client, "boom_start", phone=formatted_number), ctx)

    async def boom_background_task():
        await trigger_all_bombs(target_number)
        await asyncio.sleep(1.0)
        await client.send_chat_message(t(client, "boom_complete", phone=formatted_number), ctx)

    asyncio.create_task(boom_background_task())

# ==================== DYNAMIC DUO CONTROLLER EMBED ====================
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from bot.status_parser import SimpleProtobufDecoder

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

BASE_URLS = {
    "IND": "https://client.ind.freefiremobile.com/",
    "ID": "https://clientbp.ggpolarbear.com/",
    "BR": "https://client.us.freefiremobile.com/",
    "ME": "https://clientbp.ggpolarbear.com/",
    "VN": "https://clientbp.ggpolarbear.com/",
    "TH": "https://clientbp.ggpolarbear.com/",
    "CIS": "https://clientbp.ggpolarbear.com/",
    "BD": "https://clientbp.ggpolarbear.com/",
    "PK": "https://clientbp.ggpolarbear.com/",
    "SG": "https://clientbp.ggpolarbear.com/",
    "SAC": "https://client.us.freefiremobile.com/",
    "TW": "https://clientbp.ggpolarbear.com/",
    "US": "https://client.na.freefiremobile.com/",
    "NA": "https://client.na.freefiremobile.com/"
}

def encrypt_duo_payload(uid):
    n = int(uid)
    res = bytearray()
    while n >= 0x80:
        res.append((n & 0x7f) | 0x80)
        n >>= 7
    res.append(n)
    payload_bytes = b"\x08" + bytes(res)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(payload_bytes, 16))

def decrypt_duo_response(d):
    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        return unpad(cipher.decrypt(d), 16)
    except:
        return d

async def handle_duo(client, ctx, args):
    target_uids = await resolve_uids(client, args[1:], ctx, exclude_self=True)
    if not target_uids:
        await client.send_chat_message(t(client, 'invalid_usage', usage="/duo [uid]"), ctx)
        return

    target_uid = target_uids[0]
    await client.send_chat_message(f"[FFFF00]Scanning Duo Partner for UID {target_uid}...", ctx)

    base_url = BASE_URLS.get(client.region.upper(), "https://clientbp.ggpolarbear.com/")
    url = f"{base_url}GetSpecialFriendList"

    payload = encrypt_duo_payload(target_uid)
    headers = {
        "Authorization": f"Bearer {client.auth.token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54",
        "Connection": "Keep-Alive"
    }

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, data=payload, timeout=12) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    decrypted = decrypt_duo_response(content)
                    parsed_outer = SimpleProtobufDecoder.parse(decrypted)
                    
                    duo_parsed = parsed_outer.get("1", {}).get("data") if parsed_outer else None
                    if not duo_parsed or not isinstance(duo_parsed, dict):
                        await client.send_chat_message("[FF0000]No Dynamic Duo found or private profile.", ctx)
                        return

                    partner_uid = str(duo_parsed.get("1", {}).get("data", 0))
                    score = int(duo_parsed.get("3", {}).get("data", 0))
                    creation_ts = int(duo_parsed.get("4", {}).get("data", 0))
                    days_active = int(duo_parsed.get("5", {}).get("data", 0))
                    status_code = int(duo_parsed.get("6", {}).get("data", 0))

                    lvl = 1
                    if score >= 1201: lvl = 6
                    elif score >= 801: lvl = 5
                    elif score >= 501: lvl = 4
                    elif score >= 301: lvl = 3
                    elif score >= 101: lvl = 2

                    status_str = "Active" if status_code == 2 else "Inactive"
                    creation_time = datetime.fromtimestamp(creation_ts).strftime('%B %d, %Y') if creation_ts else "N/A"

                    # Initiator এবং Partner এর প্রোফাইল ইনফো রিট্রিভ করা
                    p1_name, p1_clan = "N/A", "No Guild"
                    p2_name, p2_clan = "N/A", "No Guild"

                    p1 = await fetch_player_info(target_uid)
                    if p1:
                        b1 = p1.get('basicInfo') or p1.get('basic_info') or {}
                        c1 = p1.get('clanBasicInfo') or p1.get('clan_basic_info') or {}
                        p1_name = b1.get('nickname', 'N/A')
                        p1_clan = c1.get('clanName') or c1.get('clan_name') or 'No Guild'

                    if partner_uid != "0":
                        p2 = await fetch_player_info(partner_uid)
                        if p2:
                            b2 = p2.get('basicInfo') or p2.get('basic_info') or {}
                            c2 = p2.get('clanBasicInfo') or p2.get('clan_basic_info') or {}
                            p2_name = b2.get('nickname', 'N/A')
                            p2_clan = c2.get('clanName') or c2.get('clan_name') or 'No Guild'

                    fmt_target = await format_uid_for_chat(target_uid)
                    fmt_partner = await format_uid_for_chat(partner_uid) if partner_uid != "0" else "N/A"

                    # ৩ডি বাবল চ্যাট কার্ড ফরম্যাটিং
                    msg_lines = [
                        f"[b][c][FF1493]╭━━━[FFFFFF] DYNAMIC DUO [FF1493]━━━╮",
                        f"[b][c][FF1493]┣━━━━━━━━━━━━━┫",
                        f"[b][C0C0C0]  Level: [00FF00]{lvl} [C0C0C0] | Score: [FFFF00]{score}",
                        f"[b][C0C0C0]  Active Days: [FFFFFF]{days_active} Days",
                        f"[b][C0C0C0]  Formed: [FFFFFF]{creation_time}",
                        f"[b][C0C0C0]  Status: [00FF00]{status_str}",
                        f"[b][c][FF1493]┣━━━━━[FFFFFF] PROFILES [FF1493]━━━━━┫",
                        f"[b][FFD700]  👑 INITIATOR:",
                        f"[b][FFFFFF]    Name: [00FFFF]{p1_name}",
                        f"[b][FFFFFF]    UID:  [00FFFF]{fmt_target}",
                        f"[b][FFFFFF]    Guild:[00FFFF]{p1_clan}",
                        f"[b][FFD700]  💝 PARTNER:",
                        f"[b][FFFFFF]    Name: [00FFFF]{p2_name}",
                        f"[b][FFFFFF]    UID:  [00FFFF]{fmt_partner}",
                        f"[b][FFFFFF]    Guild:[00FFFF]{p2_clan}",
                        f"[b][c][FF1493]╰━━━━━━━━━━━━━╯"
                    ]
                    await client.send_chat_message("\n".join(msg_lines), ctx)
                else:
                    await client.send_chat_message(f"[FF0000]Duo fetch failed. Garena HTTP Error {resp.status}", ctx)
    except Exception as e:
        await client.send_chat_message(f"[FF0000]Duo Scraper Error: {e}", ctx)