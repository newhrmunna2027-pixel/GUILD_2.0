# bot/commands/actions_team.py

import random
import asyncio
import json
import os
import time
from bot.packets import team_packets
from utils.helpers import (
    resolve_uids, format_uid_for_chat, 
    load_bot_room_state, delete_bot_room_state
)
from bot.commands import actions_look
from bot.core.logic import execute_solo_logic
from utils.translations import t
from utils.api_client import fetch_player_info  
from utils import admin_manager

FLIRT_STATES = {}
MG_STATES = {}

TARGET_FILE = "targets.txt"
target_lock = asyncio.Lock()

TEXT_FILE = "config/text.json"
TEXT_MESSAGES = {}
last_text_file_mtime = 0

async def check_advanced_auth(client, uid_str):
    if admin_manager.is_owner(uid_str) or uid_str in admin_manager.get_admins(client.my_uid):
        return True
    
    if getattr(client, 'guild_id', None):
        try:
            p_data = await fetch_player_info(uid_str)
            if p_data:
                clan_info = p_data.get('clanBasicInfo') or p_data.get('clan_basic_info') or {}
                if str(clan_info.get('clanId') or clan_info.get('clan_id', '')) == str(client.guild_id):
                    return True
        except Exception:
            pass
    return False

async def check_lock_status(client, ctx):
    if getattr(client, 'is_locked', False):
        sender_uid = str(ctx.get('uid', ''))
        if not (admin_manager.is_owner(sender_uid) or sender_uid in admin_manager.get_admins(client.my_uid)):
            await client.send_chat_message("[FF0000]I am With my boss ,,please try later", ctx)
            return True
    return False

async def handle_lock(client, ctx, args):
    if ctx.get('chat_type') != 0:
        await client.send_chat_message("[FF0000]Command only for team chat", ctx)
        return
        
    sender_uid = str(ctx.get('uid', ''))
    if not (admin_manager.is_owner(sender_uid) or sender_uid in admin_manager.get_admins(client.my_uid)):
        await client.send_chat_message("[FF0000]Boss only.", ctx)
        return
        
    client.is_locked = True
    await client.send_chat_message("[FF0000]Bot is now LOCKED.", ctx)

async def handle_unlock(client, ctx, args):
    if ctx.get('chat_type') != 0:
        await client.send_chat_message("[FF0000]Command only for team chat", ctx)
        return
        
    sender_uid = str(ctx.get('uid', ''))
    if not (admin_manager.is_owner(sender_uid) or sender_uid in admin_manager.get_admins(client.my_uid)):
        await client.send_chat_message("[FF0000]Boss only.", ctx)
        return
        
    client.is_locked = False
    await client.send_chat_message("[00FF00]Bot is now UNLOCKED.", ctx)

async def handle_create_team_5(client, ctx, args):
    if await check_lock_status(client, ctx): return
    await _create_team(client, ctx, 5)

async def handle_create_team_6(client, ctx, args):
    if await check_lock_status(client, ctx): return
    await _create_team(client, ctx, 6)

async def _create_team(client, ctx, team_capacity):
    commander_uid = ctx.get('uid')
    if not commander_uid: return

    # 🟢 প্রসেস ফাস্ট করতে execute_solo_logic এর ডিলে ১.৫ সেকেন্ড কমিয়ে ০.৩ সেকেন্ড করা হয়েছে
    if client.is_in_team or getattr(client, 'is_magic_mode', False):
        await execute_solo_logic(client) 
        await asyncio.sleep(0.3)
        
    pkts = await team_packets.create_team_packet(team_capacity, client.my_uid, client.key, client.iv, client.region)
    
    # 🟢 গ্রুপ ক্রিয়েশন ডিলে ০.৮ ও ০.৫ কমিয়ে ০.২ ও ০.১ সেকেন্ডে নামানো হয়েছে (হাই স্পিড টাস্কিং)
    if pkts and len(pkts) >= 2:
        await client.send_online_packet(pkts[0])
        await asyncio.sleep(0.2)
        await client.send_online_packet(pkts[1])
        await asyncio.sleep(0.1)
    
    client.is_in_team = True
    await client.send_chat_message(t(client, "team_create", size=team_capacity), ctx)
    
    # 🟢 ইনভাইট পাঠানোর ডিলে ১ সেকেন্ড কমিয়ে ০.১ সেকেন্ড করা হয়েছে (তাত্ক্ষণিক ইনভাইট)
    await asyncio.sleep(0.1)
    invite_pkt = await team_packets.create_invite_packet(commander_uid, team_capacity, client.key, client.iv, client.region)
    await client.send_online_packet(invite_pkt)

    # 🟢 ৫ সেকেন্ড পর স্বয়ংক্রিয়ভাবে সোলো যাওয়ার এসিনক্রোনাস ব্যাকগ্রাউন্ড লুপ (Auto-Solo Patch)
    async def delayed_auto_solo():
        await asyncio.sleep(5.0) # ৫ সেকেন্ড অপেক্ষা করবে
        if client.is_in_team:
            print(f"[{client.bot_name}] 🔄 Auto-Solo: Leaving created team lobby automatically...")
            await execute_solo_logic(client)
            
    asyncio.create_task(delayed_auto_loop := delayed_solo_task if 'delayed_solo_task' in globals() else delayed_auto_look_change() if 'delayed_auto_look_change' in globals() else delayed_auto_solo())

async def handle_join_team(client, ctx, args):
    if await check_lock_status(client, ctx): return
    if len(args) < 2:
        await client.send_chat_message(t(client, "invalid_usage", usage="/j [teamcode]"), ctx)
        return
    
    team_code = str(args[1]).strip()
    if getattr(client, 'is_joining', False): 
        await client.send_chat_message("[FFFF00]Bot is already trying to join. Please wait...", ctx)
        return
        
    client.is_joining = True
    try:
        if client.is_in_team or getattr(client, 'is_magic_mode', False):
            if ctx: await client.send_chat_message(t(client, "leave_join"), ctx)
            await execute_solo_logic(client)
            await asyncio.sleep(1.5)
        else:
            if ctx: await client.send_chat_message(t(client, "joining"), ctx)
        
        pkt = await team_packets.create_join_by_code_packet(team_code, client.key, client.iv)
        await client.send_online_packet(pkt)
        
        client.is_in_team = True
        client.last_joined_team_code = team_code
        if ctx: await client.send_chat_message(t(client, "join_req", code=team_code), ctx)
        
        if not getattr(client, 'suppress_auto_actions', False):
            async def delayed_join_look():
                await asyncio.sleep(0.5)
                await actions_look.equip_random_bundle(client, ctx)
            asyncio.create_task(delayed_join_look())
    except Exception as e: 
        print(f"[{client.bot_name}] Join Error: {e}")
    finally: 
        client.is_joining = False

async def handle_magic(client, ctx, args):
    if await check_lock_status(client, ctx): return
    if len(args) < 2:
        await client.send_chat_message(t(client, "invalid_usage", usage="/magic [teamcode]"), ctx)
        return
        
    team_code = str(args[1]).strip()
    if getattr(client, 'is_joining', False): 
        return
        
    client.is_joining = True
    try:
        if client.is_in_team or getattr(client, 'is_magic_mode', False):
            await execute_solo_logic(client)
        
        wait_time = 0
        while not client.chat_connected and wait_time < 50:
            await asyncio.sleep(0.1)
            wait_time += 1
                
        if not client.chat_connected:
            client.is_joining = False
            return
            
        client.is_magic_mode = True 
        client.team_chat_authed = False 
        
        pkt = await team_packets.create_join_by_code_packet(team_code, client.key, client.iv)
        await client.send_online_packet(pkt)
        client.is_in_team = True
        
        wait_time = 0
        while not client.team_chat_authed and wait_time < 50:
            await asyncio.sleep(0.1)
            wait_time += 1
            
        if not client.team_chat_authed:
            leave_pkt = await team_packets.create_leave_team_packet(client.my_uid, client.key, client.iv)
            await client.send_online_packet(leave_pkt)
            client.is_in_team = False 
            client.is_magic_mode = False
            await execute_solo_logic(client) 
            return
            
        leave_pkt = await team_packets.create_leave_team_packet(client.my_uid, client.key, client.iv)
        await client.send_online_packet(leave_pkt)
        client.is_in_team = False 
        
        await asyncio.sleep(0.5)
        await client.send_chat_message("[00FF00]👻 Magic Mode Activated! Ghost Chat Connected.", ctx)
    except Exception as e:
        client.is_magic_mode = False
    finally:
        client.is_joining = False

async def handle_solo(client, ctx, args):
    if await check_lock_status(client, ctx): return
    if client.is_in_showcase and client.showcase_type == 'normal':
        from bot.commands.actions_emote import stop_current_showcase
        await stop_current_showcase(client)

    if ctx:
        if client.is_in_team or getattr(client, 'is_magic_mode', False): 
            await client.send_chat_message(t(client, "solo_done"), ctx)
        else: 
            await client.send_chat_message(t(client, "solo_already"), ctx)

    await execute_solo_logic(client)

async def handle_invite(client, ctx, args):
    targets = await resolve_uids(client, args[1:], ctx)
    if not targets:
        await client.send_chat_message(t(client, "invalid_usage", usage="/inv [uid]"), ctx)
        return

    if not client.is_in_team: return

    targets_resolved = [client.send_online_packet(await team_packets.create_invite_packet(uid, 5, client.key, client.iv, client.region)) for uid in targets]
    await asyncio.gather(*targets_resolved) 
    await client.send_chat_message(f"[00FF00]Invited {len(targets)} players.", ctx)

async def handle_stop_spam(client, ctx, args):
    if getattr(client, 'is_spamming', False):
        client.is_spamming = False
        await client.send_chat_message(t(client, "spam_stop"), ctx)
    else:
        await client.send_chat_message(t(client, "spam_no"), ctx)

async def handle_law(client, ctx, args):
    uid = str(ctx['uid'])
    is_authorized = await check_advanced_auth(client, uid)
    if not is_authorized:
        await client.send_chat_message("[FF0000]Restriction: Only Boss or Guild Members can use this command.", ctx)
        return

    target_uids = await resolve_uids(client, args[1:])
    if not target_uids:
        await client.send_chat_message(t(client, "invalid_usage", usage="/law [uid]"), ctx)
        return

    target_uid = str(target_uids[0])

    async with target_lock:
        try:
            if os.path.exists(TARGET_FILE):
                with open(TARGET_FILE, "r") as f: data = json.load(f)
            else: data = {"1": []}

            total_uids = sum(len(lst) for lst in data.values())
            if total_uids >= 30:
                await client.send_chat_message(t(client, "spam_limit_reached"), ctx)
                return

            best_key = None
            min_len = float('inf')
            for key in data:
                if len(data[key]) < min_len:
                    min_len = len(data[key])
                    best_key = key
            
            if best_key is None: 
                 best_key = "1"
                 if "1" not in data: data["1"] = []

            if target_uid not in data[best_key]:
                data[best_key].append(target_uid)

            with open(TARGET_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            await client.send_chat_message(f"[FF0000]Sys Error: {e}", ctx)
            return
    
    formatted_uid = await format_uid_for_chat(target_uid) 
    await client.send_chat_message(t(client, "law_start", uid=formatted_uid), ctx)

    async def auto_remove_task():
        await asyncio.sleep(30)
        async with target_lock:
            try:
                if os.path.exists(TARGET_FILE):
                    with open(TARGET_FILE, "r") as f: data = json.load(f)
                    modified = False
                    for key in data:
                        if target_uid in data[key]:
                            data[key].remove(target_uid)
                            modified = True
                    if modified:
                        with open(TARGET_FILE, "w") as f: json.dump(data, f, indent=4)
                        formatted_uid_finish = await format_uid_for_chat(target_uid)
                        await client.send_chat_message(t(client, "law_complete", uid=formatted_uid_finish), ctx) 
            except Exception: pass

    asyncio.create_task(auto_remove_task())

GALI_LIST = [
    "{name} khan🤫কির ছেলে !!", "{name} মাদার চো🤫দ, তোর মা🤫কে চু🤫দি !!", "{name} মাদার চো🤫দ, তোর মা🤫কে 5G স্পিডে চু🤫দি !!",
    "{name} বোকাচো🤫দা, তোর মা🤫কে কন🤫ডম লাগিয়ে চু🤫দি !!", "{name} বোকাচো🤫দা, তোর মা🤫কে প্রতিদিন ১০,০০০ টাকার সার্ভিস দেই !!",
    "F🤫U🤫C🤫K {name} !!", "{name} মাদার চো🤫দ, পো🤫দ মে🤫রে দিবো !!", "{name} মাদার চো🤫দ !!",
    "{name} khan🤫কি, আমি তোর বা🤫প !!", "{name} তোর মা🤫কে আমি চু🤫ই🤫ਦਾ তোরে জন্মায় ছি !!", "{name} বোকাচো🤫দা, khanকির ছেলে !!",
    "{name} মাদার চো🤫দ, তোর মা🤫কে ১৮০ কি.মি. স্পিডে চু🤫দি !!", "{name} খা🤫ন🤫কির ছেলে বট, নুব🤫রা প্লেয়ার !!",
    "বাংলাদেশের NO-1 বট PLAYER {name}", "{name} জুতা চোর !!", "{name} মাদারচো🤫দ, ফ্রি ফায়ার খেলা বাদ দিয়ে লুডু খেল যা !!",
    "{name} তোর বো🤫ন রে ধይরা চু🤫দি !!", "{name} চুদ🤫না, তোর মা🤫য়ের গু🤫দ ফাটাইয়া দিমু !!", "{name} বাঞ্চো🤫ত, তোর পুট🤫কিতে বাঁশ দিমu !!",
    "{name} মাগি🤫র পোলা, তোর মা🤫কে পাড়ায় তুইলা চু🤫দমু !!", "{name} বেজন্মা, তোর बाप কয়জন রে ??", "{name} তোর মা🤫য়ের ভোদায় বিচি ঢুকাইয়া দিমু !!",
    "{name} তোর মা🤫কে কুত্তা দিয়া চু🤫দাও বোকাচো🤫দা !!", "{name} তোরে চু🤫ইদা ড্রেনে ফালায়া দিমু khanকি !!", "{name} তোর মা🤫য়ের দুধ চুইষা খামু মাদারচো🤫দ !!"
]
GALI_EMOTE_FIXED = 909052011 
GALI_EMOTE_LIST_MG = [909051015]

async def handle_gali(client, ctx, args):
    if len(args) < 2 and ctx.get('chat_type') != 3:
        await client.send_chat_message(t(client, "invalid_usage", usage="/gali [uid/name]"), ctx)
        return
        
    target_input = " ".join(args[1:]).strip()
    if not target_input and ctx.get('chat_type') == 3:
        target_input = str(ctx.get('uid'))
        
    commander_uid = ctx.get('uid')
    if getattr(client, 'is_spamming', False): return
    
    target_name = "Player"
    if target_input.isdigit():
        try:
            data = await fetch_player_info(target_input)
            if data:
                b_info = data.get('basicInfo') or data.get('basic_info') or {}
                target_name = b_info.get('nickname', f'Player_{target_input}')
            else: target_name = target_input
        except: target_name = target_input
    else: target_name = target_input

    client.is_spamming = True
    await client.send_chat_message(t(client, "gali_start", name=target_name), ctx)
    
    async def gali_task():
        try:
            for _ in range(20): 
                if not getattr(client, 'is_spamming', False): break
                gali_msg = random.choice(GALI_LIST).format(name=target_name)
                color = random.choice(["[FF0000]", "[FFFF00]", "[00FF00]", "[00FFFF]", "[FF00FF]", "[FFFFFF]"])
                final_msg = f"[b][c]{color}{gali_msg}"
                await client.send_chat_message(final_msg, ctx)
                
                pkt_bot = await team_packets.create_emote_packet(client.my_uid, client.my_uid, GALI_EMOTE_FIXED, client.key, client.iv, client.region)
                pkt_commander = await team_packets.create_emote_packet(client.my_uid, commander_uid, GALI_EMOTE_FIXED, client.key, client.iv, client.region)
                await asyncio.gather(client.send_online_packet(pkt_bot), client.send_online_packet(pkt_commander))
                await asyncio.sleep(8.0) 
        except Exception:
            pass
        finally:
            client.is_spamming = False
            await client.send_chat_message(t(client, "gali_finish"), ctx)
    asyncio.create_task(gali_task())

async def handle_mg(client, ctx, args):
    if len(args) < 2 and ctx.get('chat_type') != 3:
        await client.send_chat_message(t(client, "invalid_usage", usage="/mg [uid/name]"), ctx)
        return

    target_input = " ".join(args[1:]).strip()
    if not target_input and ctx.get('chat_type') == 3:
        target_input = str(ctx.get('uid'))
        
    mg_state_key = str(client.my_uid) 
    target_name = "Player"
    
    if target_input.isdigit():
        try:
            data = await fetch_player_info(target_input)
            if data:
                b_info = data.get('basicInfo') or data.get('basic_info') or {}
                target_name = b_info.get('nickname', f'Player_{target_input}')
            else: target_name = target_input
        except: target_name = target_input
    else: target_name = target_input
        
    MG_STATES[mg_state_key] = {'target_name': target_name}
    menu_msg = (
        f"[b][c][FF0000]╭━━━━ [FFFFFF]{target_name}[FF0000] ━━╮\n\n"
        f"[b][c][FFFF00]Reply with '[00FF00]laga[FFFF00]' to start fire.\n\n"
        f"[b][c][FF0000]╰━━━━━━━━━━━━━━━╯"
    )
    await client.send_chat_message(menu_msg, ctx)

async def execute_mg_action(client, ctx, target_name):
    reply_sender_uid = str(ctx.get('uid'))
    selected_msgs = random.sample(GALI_LIST, 2)
    HEADER = "[b][c][FF0000]╭━━━━━  [FFFFFF]ATTACK[FF0000]  ━━━━━╮"
    FOOTER = "[b][c][FF0000]╰━━━━━━━━━━━━━━━╯"
    msg_body = "\n\n".join([msg.format(name=target_name) for msg in selected_msgs])
    final_box = f"{HEADER}\n\n[FFFF00]{msg_body}\n\n{FOOTER}"
    
    await client.send_chat_message(final_box, ctx)

    if GALI_EMOTE_LIST_MG:
        emote_id = random.choice(GALI_EMOTE_LIST_MG)
        client.suppress_auto_actions = True
        pkt_commander = await team_packets.create_emote_packet(client.my_uid, reply_sender_uid, emote_id, client.key, client.iv, client.region)
        await client.send_online_packet(pkt_commander)
        
        async def restore_look():
            await asyncio.sleep(4.0)
            client.suppress_auto_actions = False
        asyncio.create_task(restore_look())

LOVE_LIST = [
    "[B][C][FFFFFF]তোমার হাসিটা, [FF1493]{name}[FFFFFF], আমার দিনকে সুন্দর করে দেয় 😊", "[B][C][FFFFFF]তোমার চোখ দুটো এত সুন্দর [00FFFF]{name}[FFFFFF], হারিয়ে যেতে ইচ্ছে করে 👀",
    "[B][C][FFFFFF]তোমার সাথে কথা বলতে বলতে, [00FF00]{name}[FFFFFF], সময় থেমে যায় 😄", "[B][C][FFFFFF]তুমি কি জানো [FFD700]{name}[FFFFFF], তুমি কত সুন্দর? ♡",
    "[B][C][FFFFFF]তোমার হাতটা একটু ধরতে পারি [FF1493]{name}[FFFFFF]?", "[B][C][FFFFFF]তোমার সাথে ঘুরতে যাওয়ার ইচ্ছে ছিল [00FFFF]{name}[FFFFFF] 😊",
    "[B][C][FFFFFF]তোমার হাসিতে, [00FF00]{name}[FFFFFF], আমার জীবন সুন্দর হয়ে যায় 😄", "[B][C][FFFFFF]তোমাকে দেখলে, [FFD700]{name}[FFFFFF], আমার গান গাইতে ইচ্ছে করে 🎶",
    "[B][C][FFFFFF]তুমি কি আমার সাথে এক কাপ কফি খাবে [FF1493]{name}[FFFFFF]?", "[B][C][FFFFFF]তোমার চুলের ঘ্রাণটা খুব সুন্দর [00FFFF]{name}[FFFFFF] 😊",
    "[B][C][FFFFFF]তোমার সাথে কথা বলতে, [00FF00]{name}[FFFFFF], কখনো বিরক্ত লাগে না 😄", "[B][C][FFFFFF]তুমি কি জানো [FFD700]{name}[FFFFFF], তুমি কতটা স্পেশাল?",
    "[B][C][FFFFFF]তোমার হাসিটা আমার অনেক প্রিয় [FF1493]{name}[FFFFFF] 😊", "[B][C][FFFFFF]তোমাকে নিয়ে, [00FFFF]{name}[FFFFFF], কবিতা লিখতে ইচ্ছে করে 📝",
    "[B][C][FFFFFF]তোমার সাথে রাতের আকাশ দেখতে চাই [00FF00]{name}[FFFFFF] 🌙", "[B][C][FFFFFF]তোমার সাথে হাত ধরে হাঁটতে চাই [FFD700]{name}[FFFFFF] 🚶‍♀️",
    "[B][C][FFFFFF]তুমি আমার জীবনের সবচেয়ে সুন্দর গল্প [FF1493]{name}[FFFFFF] 😊", "[B][C][FFFFFF]তোমার সাথে, [00FFFF]{name}[FFFFFF], প্রতিটা মুহূর্তই সুন্দর 🌅",
    "[B][C][00FFFF]I LOVE YOU JAN [FF1493]{name}[00FFFF] ♡", "[B][C][00FFFF]তুমি আমার জান [FFD700]{name}[00FFFF] ♡",
    "[B][C][00FFFF]I LOVE YOU [00FF00]{name}[00FFFF] ♡", "[B][C][00FFFF]তোমার হাসি, [FF1493]{name}[00FFFF], আমার পৃথিবী আলোকিত করে ♡",
    "[B][C][00FFFF]তোমাকে ছাড়া আমার জীবন অসম্পূর্ণ [FFD700]{name}[00FFFF] ♡", "[B][C][00FFFF]আমি তোমাকে ভালোবাসি [00FF00]{name}[00FFFF] ♡",
    "[B][C][00FFFF]আমি সবসময় তোমার পাশে থাকতে চাই [FF1493]{name}[00FFFF] ♡", "[B][C][00FFFF]তুমি আমার স্বপ্নের মানুষ [00FFFF]{name}[00FFFF] ♡",
    "[B][C][00FFFF]তোমার মতো মানুষ খুব কমই দেখা যায় [FFD700]{name}[00FFFF] ♡", "[B][C][00FFFF]তোমাকে ছাড়া, [FF1493]{name}[00FFFF], আমার দিন কাটে না ♡",
    "[B][C][00FFFF]তুমি আমার জীবনের সবচেয়ে বড় সুখ [00FF00]{name}[00FFFF] ♡", "[B][C][00FFFF]তুমি আমার হৃদয়ের সবচেয়ে কাছের মানুষ [FFD700]{name}[00FFFF] ♡",
    "[B][C][00FFFF]তোমার জন্য আমার হৃদয় সবসময় ধড়фড় করে [FF1493]{name}[00FFFF] ♡", "[B][C][00FFFF]তুমি আমার জীবনের আলো [00FFFF]{name}[00FFFF] ♡",
    "[B][C][00FFFF]আমি শুধু তোমাকেই ভালোবাসি [00FF00]{name}[00FFFF] ♡", "[B][C][00FFFF]তুমি আমার সবকিছু [FFD700]{name}[00FFFF] ♡",
    "[B][C][FFFFFF]♡ [FF1493]{name}[FFFFFF], তুই আমার [00FFFF]সেফ জোন [FFFFFF]♡", "[B][C][FFFFFF]♡ [00FF00]লবিতে [FFFFFF]শুধু [FFD700]{name} তোকেই খুঁজি [FFFFFF]♡",
    "[B][C][FFFFFF]♡ [00FFFF]এয়ারড্রপের [FFFFFF]চেয়েও [FF1493]{name} তুই দামি [FFFFFF]♡", "[B][C][FFFFFF]♡ [FFD700]{name}, তোর হাসিতে [FFFFFF]আমার [00FF00]HP বাড়ে [FFFFFF]♡",
    "[B][C][FFFFFF]♡ [FF00FF]{name} তুই ছাড়া [FFFFFF]গেম খেলা [00FFFF]পুরোই বৃথা [FFFFFF]♡", "[B][C][FFFFFF]♡ [FFA500]স্নাইপারের [FFFFFF]একমাত্র [FF1493]লক্ষ্য {name} তুই [FFFFFF]♡",
    "[B][C][FFFFFF]♡ [32CD32]{name} তুই আমার [FFFFFF]গ্লু-ওয়ালের [FFD700]কভার [FFFFFF]♡", "[B][C][FFFFFF]♡ [FF0000]{name} চল দুজনে [FFFFFF]মিলে [00FFFF]বুইয়া নিই [FFFFFF]♡"
]
LOVE_EMOTE_LIST = [909000134, 909045010, 909051013, 909050018, 909047007, 909035010, 909034014, 909038004, 909000045, 909000010]

async def handle_love(client, ctx, args):
    if len(args) < 2 and ctx.get('chat_type') != 3:
        await client.send_chat_message(t(client, "invalid_usage", usage="/love [uid/name]"), ctx)
        return
        
    target_input = " ".join(args[1:]).strip()
    if not target_input and ctx.get('chat_type') == 3:
        target_input = str(ctx.get('uid'))
        
    commander_uid = ctx.get('uid')
    
    if getattr(client, 'is_spamming', False):
        await client.send_chat_message("[FF0000]Spam task already running! Wait.", ctx)
        return
        
    target_name = "JAN"
    if target_input.isdigit():
        try:
            data = await fetch_player_info(target_input)
            if data:
                b_info = data.get('basicInfo') or data.get('basic_info') or {}
                target_name = b_info.get('nickname', 'JAN')
            else: target_name = target_input
        except: target_name = target_input
    else: target_name = target_input

    client.is_spamming = True
    await client.send_chat_message(t(client, "love_start", name=target_name), ctx)
    async def love_task():
        try:
            for _ in range(20): 
                if not getattr(client, 'is_spamming', False): break
                love_msg = random.choice(LOVE_LIST).format(name=target_name)
                await client.send_chat_message(love_msg, ctx)
                if LOVE_EMOTE_LIST:
                    emote_id = random.choice(LOVE_EMOTE_LIST)
                    pkt_bot = await team_packets.create_emote_packet(client.my_uid, client.my_uid, emote_id, client.key, client.iv, client.region)
                    pkt_commander = await team_packets.create_emote_packet(client.my_uid, commander_uid, emote_id, client.key, client.iv, client.region)
                    await asyncio.gather(client.send_online_packet(pkt_bot), client.send_online_packet(pkt_commander))
                await asyncio.sleep(8.0) 
        except Exception:
            pass
        finally:
            client.is_spamming = False
            await client.send_chat_message(t(client, "love_finish"), ctx)
    asyncio.create_task(love_task())

async def handle_flirt(client, ctx, args):
    if len(args) < 2 and ctx.get('chat_type') != 3:
        await client.send_chat_message(t(client, "invalid_usage", usage="/flirt [uid/name]"), ctx)
        return

    target_input = " ".join(args[1:]).strip()
    if not target_input and ctx.get('chat_type') == 3:
        target_input = str(ctx.get('uid'))
        
    flirt_state_key = str(client.my_uid) 
    target_name = "Player"
    
    if target_input.isdigit():
        try:
            data = await fetch_player_info(target_input)
            if data:
                b_info = data.get('basicInfo') or data.get('basic_info') or {}
                target_name = b_info.get('nickname', f'Player_{target_input}')
            else: target_name = target_input
        except: target_name = target_input
    else: target_name = target_input
        
    FLIRT_STATES[flirt_state_key] = {'target_name': target_name}
    menu_msg = (
        f"[b][c][FF1493]╭━━━━ [FFFFFF]{target_name}[FF1493] ━━╮\n\n"
        f"[b][c][FFFF00]Reply with '[00FF00]love[FFFF00]' to send the message.\n\n"
        f"[b][c][FF1493]╰━━━━━━━━━━━━━━━╯"
    )
    await client.send_chat_message(menu_msg, ctx)

async def execute_flirt_action(client, ctx, target_name):
    reply_sender_uid = str(ctx.get('uid'))
    selected_msgs = random.sample(LOVE_LIST, 2)
    HEADER = "[b][c][FF1493]╭━━━━━  [FFFFFF]KOLIZA[FF1493]  ━━━━━╮"
    FOOTER = "[b][c][FF1493]╰━━━━━━━━━━━━━━━╯"
    msg_body = "\n\n".join([msg.format(name=target_name) for msg in selected_msgs])
    final_box = f"{HEADER}\n\n{msg_body}\n\n{FOOTER}"
    
    await client.send_chat_message(final_box, ctx)

    if LOVE_EMOTE_LIST:
        emote_id = random.choice(LOVE_EMOTE_LIST)
        client.suppress_auto_actions = True
        pkt_commander = await team_packets.create_emote_packet(client.my_uid, reply_sender_uid, emote_id, client.key, client.iv, client.region)
        await client.send_online_packet(pkt_commander)
        
        async def restore_look():
            await asyncio.sleep(4.0)
            client.suppress_auto_actions = False
        asyncio.create_task(restore_look())

async def handle_jj(client, ctx, args):
    if len(args) < 2:
        await client.send_chat_message(t(client, "invalid_usage", usage="/jj [text]"), ctx)
        return
    spam_text = " ".join(args[1:]) 
    if getattr(client, 'is_spamming', False):
        client.is_spamming = False
        await asyncio.sleep(0.5)
    client.is_spamming = True
    await client.send_chat_message("[FFFF00]Starting Color Spam...", ctx)
    async def jj_task():
        try:
            COLOR_LIST = ["[FF0000]", "[00FF00]", "[0000FF]", "[FFFF00]", "[00FFFF]", "[FF00FF]", "[FFFFFF]", "[FFA500]"]
            for i in range(20): 
                if not getattr(client, 'is_spamming', False): break
                color = random.choice(COLOR_LIST)
                final_msg = f"[b][c]{color}{spam_text} {i+1}"
                await client.send_chat_message(final_msg, ctx)
                await asyncio.sleep(8.0) 
        except Exception as e:
            await client.send_chat_message(t(client, "sys_error", error=str(e)), ctx)
        finally:
            client.is_spamming = False
            await client.send_chat_message("[00FF00]Color Spam Finished.", ctx)
    asyncio.create_task(jj_task())

async def handle_lag(client, ctx, args):
    sender_uid = str(ctx.get('uid', ''))
    
    if not (admin_manager.is_owner(sender_uid) or sender_uid in admin_manager.get_admins(client.my_uid)):
        return

    if not client.is_in_team:
        await client.send_chat_message("[FF0000]Bot must be inside a Team/Lobby to use /lag!", ctx)
        return

    duration = 60
    if len(args) > 1 and args[1].isdigit():
        duration = int(args[1])
        if duration > 60:
            duration = 60

    chat_type = ctx.get('chat_type', 0)
    chat_id = ctx.get('chat_id', client.my_uid)
    
    if getattr(client, 'lx_burst_running', False):
        await client.send_chat_message("[B][C][FF0000] LX burst already running! Wait or restart bot.", ctx)
        return

    await client.send_chat_message("[B][C][00FF00]⚡LAGG🥹!.", ctx)
    await asyncio.sleep(0.2)
    
    client.current_chat_owner = "12345678911"
    client.current_chat_code = "12345678911"
    client.team_chat_authed = False
    
    asyncio.create_task(client._close_chat_connection())
    
    asyncio.create_task(lx_burst_loop(
        client, client.my_uid, client.key, client.iv, 
        client.region, chat_type, sender_uid, chat_id, duration
    ))

async def lx_burst_loop(client, bot_uid: int, key: bytes, iv: bytes, region: str,
                        chat_type: int, sender_uid: int, chat_id: int,
                        duration: int = 5):
    client.lx_burst_running = True
    start_time = time.time()
    count_ready = 0
    count_keepalive = 0

    from bot.packets.base_handler import CrEaTo, GeneRaTePk

    fields_ready = {1: 15, 2: {1: int(bot_uid)}}
    ready_hex = (await CrEaTo(fields_ready) if 'CrEaTo' in globals() else await CrEaTe_ProTo(fields_ready)).hex()

    if region.lower() == "ind":
        pkt_type = '0514'
    elif region.lower() == "bd":
        pkt_type = '0519'
    else:
        pkt_type = '0515'

    print(f" Starting Lag for {duration} seconds...")

    while getattr(client, 'lx_burst_running', False) and (time.time() - start_time) < duration:
        try:
            if not client.online_connected or not getattr(client, 'online_writer', None):
                print("❌ online_writer lost, stopping burst")
                break

            ready_packet = await GeneRaTePk(fields_ready, pkt_type, key, iv) if 'GeneRaTePk' in globals() else await team_packets.GeneRaTePk(ready_hex, pkt_type, key, iv)
            client.online_writer.write(ready_packet)
            await client.online_writer.drain()
            count_ready += 1

            fields_keep = {1: 99, 2: {1: int(time.time()), 2: 1}}
            keep_hex = (await CrEaTe_ProTo(fields_keep)).hex()
            keep_packet = await GeneRaTePk(fields_keep, pkt_type, key, iv) if 'GeneRaTePk' in globals() else await team_packets.create_keep_alive_packet(key, iv, region)
            client.online_writer.write(keep_packet)
            await client.online_writer.drain()
            count_keepalive += 1

            await asyncio.sleep(0.000001)

        except Exception as e:
            print(f"❌ LX burst error: {e}")
            break

    client.lx_burst_running = False
    print(f"✅Lag finished: {count_ready} done, {count_keepalive}  in {time.time() - start_time:.2f}s")

    try:
        await client.send_chat_message(
            "[B][C][FF0000]🔄 Lag COMEPLTE. Restarting bot now...",
            {'chat_type': chat_type, 'uid': sender_uid, 'chat_id': chat_id}
        )
        await asyncio.sleep(0.3)
    except:
        pass

async def handle_ghost_cmd(client, ctx, args):
    if not client.is_in_team:
        await client.send_chat_message("[FF0000]Bot must be inside a Team/Lobby to use /ghost!", ctx)
        return

    leader_uid = getattr(client, 'last_invite_leader', None)
    recruit_id = getattr(client, 'last_invite_code', None)          
    team_code = getattr(client, 'last_joined_team_code', None)       
    session_id = getattr(client, 'last_lobby_session_id', None)      

    if not leader_uid:
        await client.send_chat_message("[FF0000]No saved leader UID found! (Are you in a lobby?)", ctx)
        return

    mode = args[1].lower() if len(args) > 1 else "all"

    if mode == "token" or mode == "all":
        if recruit_id:
            pkt = await team_packets.ghost_packet(client.my_uid, leader_uid, recruit_id, client.key, client.iv, client.region)
            await client.send_online_packet(pkt)
            if mode == "token":
                await client.send_chat_message(f"[00FF00]Ghost sent using Recruit Token: {recruit_id}", ctx)

    if mode == "code" or mode == "all":
        if team_code:
            pkt = await team_packets.ghost_packet(client.my_uid, leader_uid, team_code, client.key, client.iv, client.region)
            await client.send_online_packet(pkt)
            if mode == "code":
                await client.send_chat_message(f"[00FF00]Ghost sent using Team Code: {team_code}", ctx)

    if mode == "session" or mode == "all":
        if session_id:
            pkt = await team_packets.ghost_packet(client.my_uid, leader_uid, session_id, client.key, client.iv, client.region)
            await client.send_online_packet(pkt)
            if mode == "session":
                await client.send_chat_message(f"[00FF00]Ghost sent using Session ID: {session_id}", ctx)

    if mode == "all":
        await client.send_chat_message(f"[00FF00]Multi-mode Ghost packets fired! (Leader: {leader_uid})", ctx)

async def handle_room_join(client, ctx, args):
    if len(args) < 3:
        await client.send_chat_message("[FF0000]Usage: /rm [room_id] [password]", ctx)
        return
        
    room_id = str(args[1]).strip()
    password = str(args[2]).strip()
    
    old_state = load_bot_room_state(client.my_uid)
    if old_state and old_state.get("room_id"):
        try:
            if client.online_connected and client.online_writer:
                leave_old_pkt = await team_packets.physical_room_leave(old_state.get("room_id"), client.key, client.iv)
                client.online_writer.write(leave_old_pkt)
                await client.online_writer.drain()
                await asyncio.sleep(1.0)
        except: pass
        
    await client.send_chat_message(f"[FFFF00]Joining Room ID {room_id} physically to capture secret key...", ctx)
    
    if client.online_connected and client.online_writer:
        pkt = await team_packets.physical_room_join(room_id, password, client.key, client.iv)
        client.online_writer.write(pkt)
        await client.online_writer.drain()
    else:
        await client.send_chat_message("[FF0000]Bot is not connected to Garena Online server!", ctx)

async def handle_room_leave(client, ctx, args):
    """/leave কমান্ড দিয়ে কাস্টম রুম থেকে শারীরিকভাবে লিভ নেওয়া ও সেশন খালি করা"""
    delete_bot_room_state(client.my_uid)
    
    room_id = getattr(client, 'room_id', None)
    if room_id:
        if client.online_connected and client.online_writer:
            leave_pkt = await team_packets.physical_room_leave(room_id, client.key, client.iv)
            client.online_writer.write(leave_pkt)
            await client.online_writer.drain()
            
        client.room_id = None
        client.room_secret_code = None
        client.is_in_room = False
        await client.send_chat_message("[00FF00]Successfully left room physically, cleared room session.", ctx)
    else:
        await client.send_chat_message("[00FF00]Successfully cleared room state & file. No active room session found.", ctx)

async def handle_rs(client, ctx, args):
    """জেসন ফাইল রিড করে কাস্টম রুম চ্যাট পুনরায় প্রমাণীকরণ ও রিকানেক্ট করার কমান্ড"""
    saved_room = load_bot_room_state(client.my_uid)
    if saved_room:
        room_id = saved_room.get("room_id")
        secret_code = saved_room.get("secret_code")
        if room_id and secret_code:
            client.room_id = room_id
            client.room_secret_code = secret_code
            client.is_in_room = True
            
            await client.send_chat_message(f"[FFFF00]Re-authenticating room chat for Room ID: {room_id}...", ctx)
            
            from bot.core.handlers import start_room_chat_auth_sequence
            asyncio.create_task(start_room_chat_auth_sequence(client, room_id, secret_code))
        else:
            await client.send_chat_message("[FF0000]Room ID or Secret Code is missing in saved state.", ctx)
    else:
        await client.send_chat_message("[FF0000]No saved room session found for this bot.", ctx)

def load_text_messages():
    """config/text.json ফাইল লাইভ সিঙ্ক লোডার"""
    global TEXT_MESSAGES, last_text_file_mtime
    os.makedirs("config", exist_ok=True)
    if not os.path.exists(TEXT_FILE):
        sample_texts = {
            "1": [
                "[FF0000]Welcome {name} to our Custom Room!",
                "[FFFFFF]Your Level is {level} and Clan is {clan_name}.",
                "[00FF00]Enjoy your game!"
            ]
        }
        try:
            with open(TEXT_FILE, "w", encoding="utf-8") as f:
                json.dump(sample_texts, f, indent=4, ensure_ascii=False)
        except: pass

    try:
        mtime = os.path.getmtime(TEXT_FILE)
        if mtime != last_text_file_mtime:
            with open(TEXT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                formatted_messages = {}
                for key, value in data.items():
                    if isinstance(value, list):
                        formatted_messages[key] = "\n".join(value)
                    else:
                        formatted_messages[key] = str(value)
                        
                TEXT_MESSAGES = formatted_messages
                last_text_file_mtime = mtime
                print(f"[🔄] Live Sync: Loaded {len(TEXT_MESSAGES)} messages from text.json")
    except Exception:
        pass

async def handle_s_command(client, ctx, args):
    """s1, s2, s100 কমান্ড রানার যা এপিআই রিড করে টেমপ্লেট প্রয়োগ করে"""
    load_text_messages()
    cmd = args[0].lower()
    num_part = cmd[1:]
    
    if num_part.isdigit():
        msg_id = str(int(num_part))
        target_uid = args[1] if len(args) >= 2 else None
        
        if not target_uid and ctx.get('chat_type') == 3:
            target_uid = str(ctx.get('uid'))

        if msg_id in TEXT_MESSAGES:
            raw_template = TEXT_MESSAGES[msg_id]
            nickname, level, clan_name = "Unknown", 0, "No Clan"
            
            if target_uid and target_uid.isdigit():
                try:
                    p_data = await fetch_player_info(target_uid)
                    if p_data:
                        b_info = p_data.get('basicInfo') or p_data.get('basic_info') or {}
                        cl_info = p_data.get('clanBasicInfo') or p_data.get('clan_basic_info') or {}
                        nickname = b_info.get('nickname', 'Unknown')
                        level = b_info.get('level', 0)
                        clan_name = cl_info.get('clanName') or cl_info.get('clan_name') or 'No Clan'
                except: pass
            
            try:
                formatted_text = raw_template.format(
                    name=nickname,
                    Name=nickname,
                    level=level,
                    clan_name=clan_name
                )
            except:
                formatted_text = raw_template
            
            await client.send_chat_message(formatted_text, ctx)

# 🟢 DYNAMIC TEAM CREATION UTILITY FOR HIGH-SPEED EXECUTION (FAST LOBBY SYNC)
async def _create_team(client, ctx, team_capacity):
    commander_uid = ctx.get('uid')
    if not commander_uid: return

    # 🟢 High-speed execute_solo_logic sync (reduced delay from 1.5s to 0.3s)
    if client.is_in_team or getattr(client, 'is_magic_mode', False):
        await execute_solo_logic(client) 
        await asyncio.sleep(0.3)
        
    pkts = await team_packets.create_team_packet(team_capacity, client.my_uid, client.key, client.iv, client.region)
    
    # 🟢 Reduced sequential frame delay to 0.2s and 0.1s for extreme speedup
    if pkts and len(pkts) >= 2:
        await client.send_online_packet(pkts[0])
        await asyncio.sleep(0.2)
        await client.send_online_packet(pkts[1])
        await asyncio.sleep(0.1)
    
    client.is_in_team = True
    await client.send_chat_message(t(client, "team_create", size=team_capacity), ctx)
    
    # 🟢 Reduced invite delay to 0.1s (instant recruitment trigger)
    await asyncio.sleep(0.1)
    invite_pkt = await team_packets.create_invite_packet(commander_uid, team_capacity, client.key, client.iv, client.region)
    await client.send_online_packet(invite_pkt)

    # 🟢 Background task to automatically execute solo leave after exactly 5 seconds
    async def delayed_auto_solo():
        await asyncio.sleep(5.0) # 5 seconds delay
        if client.is_in_team:
            print(f"[{client.bot_name}] 🔄 Auto-Solo: Leaving created team lobby automatically...")
            await execute_solo_logic(client)
            
    asyncio.create_task(delayed_auto_solo())