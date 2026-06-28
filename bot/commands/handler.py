# -*- coding: utf-8 -*-
# bot/commands/handler.py

import traceback
import time
import asyncio
import uuid

from bot.commands import actions_team, actions_emote, actions_info, actions_look
from bot.commands.actions_info import HELP_MENU_STATES
from bot.commands.actions_team import FLIRT_STATES, MG_STATES 
from utils import admin_manager
from utils.helpers import parse_and_resolve_emotes, resolve_uids
from bot.packets import team_packets
from utils.api_client import fetch_player_info  

COMMANDS = {
    '/a': actions_emote.handle_single_emote,
    '/b': actions_emote.handle_stealth_single_emote,
    '/v': actions_emote.handle_normal_evo_showcase,
    '/st': actions_emote.handle_stop_showcase,
    '/e': actions_emote.handle_emote_list,
    
    '/ea': actions_emote.handle_emote_mood,
    '/es': actions_emote.handle_emote_mood,
    '/el': actions_emote.handle_emote_mood,
    '/ef': actions_emote.handle_emote_mood,
    '/end': actions_emote.handle_emote_mood, 
    
    '/block': actions_emote.handle_block, 
    '/off': actions_emote.handle_off,     
    
    '/5': actions_team.handle_create_team_5,
    '/6': actions_team.handle_create_team_6,
    '/j': actions_team.handle_join_team,
    '/magic': actions_team.handle_magic, 
    '/inv': actions_team.handle_invite,
    '/s': actions_team.handle_solo,
    '/law': actions_team.handle_law,   
    '/stop': actions_team.handle_stop_spam,
    
    '/lock': actions_team.handle_lock,
    '/unlock': actions_team.handle_unlock,
    '/lag': actions_team.handle_lag, 
    '/ghost': actions_team.handle_ghost_cmd,
    '/rm': actions_team.handle_room_join,
    '/leave': actions_team.handle_room_leave,
    '/rs': actions_team.handle_rs, # 🟢 নতুন রুম রি-অথোরাইজেশন কমান্ড ম্যাপিং

    '/gali': actions_team.handle_gali,
    '/mg': actions_team.handle_mg, 
    '/love': actions_team.handle_love,  
    '/flirt': actions_team.handle_flirt,
    '/jj': actions_team.handle_jj,
    
    '/h': actions_info.handle_help,
    '/help': actions_info.handle_help,
    '/add': actions_info.handle_add_uid,
    '/rev': actions_info.handle_remove_uid,
    '/list': actions_info.handle_show_list,
    '/status': actions_info.handle_status_check,
    '/info': actions_info.handle_info,
    '/duo': actions_info.handle_duo,
    
    '/like': actions_info.handle_like,
    '/boom': actions_info.handle_boom,
    '/admin_add': actions_info.handle_admin_add,
    '/admin_rev': actions_info.handle_admin_rev,
    '/admin_list': actions_info.handle_admin_list_cmd,
    
    '/l': actions_look.handle_look_change,
    '/look': actions_look.handle_look_change,
    '/ani': actions_look.handle_animation,
    '/look_on': actions_look.handle_look_on,
    '/look_off': actions_look.handle_look_off,
    
    '/en': actions_info.handle_lang_en, 
    '/bn': actions_info.handle_lang_bn
}

ALLOWED_NORMAL = [
    '/a', '/s', '/h', '/help', '/e', '/add', '/rev', '/list', 
    '/status', '/info', '/st', '/admin_add', '/admin_rev', '/admin_list', '/like',
    '/en', '/bn', '/flirt', '/mg', '/block', '/off', '/stop', '/magic', '/lock', '/unlock',
    '/ea', '/es', '/el', '/ef', '/end', '/lag', '/ani', '/ghost', '/duo', '/rm', '/leave', '/rs'
]

async def handle_command(client, chat_context):
    try:
        msg = chat_context['msg'].strip()
        uid = str(chat_context['uid'])
        parts = msg.split()
        if not parts: return
        
        cmd = parts[0].lower()
        
        if cmd in ['/5', '/6', '/s', '/magic', '/block', '/st', '/lag', '/ani', '/ghost']: 
            await actions_emote.stop_all_tasks(client)

        is_owner = admin_manager.is_owner(uid)
        is_admin = uid in admin_manager.get_admins(client.my_uid)
        
        is_guild_member = False
        if getattr(client, 'guild_id', None):
            try:
                p_data = await fetch_player_info(uid)
                if p_data:
                    clan_info = p_data.get('clanBasicInfo') or p_data.get('clan_basic_info') or {}
                    if str(clan_info.get('clanId') or clan_info.get('clan_id', '')) == str(client.guild_id):
                        is_guild_member = True
            except:
                pass
                
        is_authorized = is_owner or is_admin or is_guild_member

        # 🟢 কাস্টম রুম চ্যাট (টাইপ ৩) অ্যাক্সেস কন্ট্রোল ফিল্টার
        if chat_context.get('chat_type') == 3:
            is_trying_command = cmd.startswith('/') or cmd in ['hi', 'hello', 'love', 'laga']
            if is_trying_command and not is_authorized:
                player_name = "Player"
                try:
                    p_data = await fetch_player_info(uid)
                    if p_data:
                        b_info = p_data.get('basicInfo') or p_data.get('basic_info') or {}
                        player_name = b_info.get('nickname', 'Player')
                except:
                    pass
                mock_msg = f"[b][c][FF0000]{player_name} ke tui tore cini na vag ekhan theke"
                await client.send_chat_message(mock_msg, chat_context)
                return

        # ওনার বা কমান্ড রেস্ট্রিকশন
        owner_only_cmds = ['/block', '/lag', '/el', '/ef', '/b']
        if cmd in owner_only_cmds:
            if not is_owner:
                await client.send_chat_message("[FF0000]Restriction: Only Owner can use this command.", chat_context)
                return

        if getattr(client, 'is_blocking', False) and cmd in ['/s', '/5', '/6', '/magic']:
            if not is_authorized and not await actions_emote.check_advanced_auth(client, uid):
                await client.send_chat_message("[FF0000]Restriction: Block is active. Only Boss or Guild Members can use this command.", chat_context)
                return

        try:
            if str(client.my_uid) in FLIRT_STATES and msg.lower() == 'love':
                flirt_data = FLIRT_STATES.pop(str(client.my_uid))
                await actions_team.execute_flirt_action(client, chat_context, flirt_data['target_name'])
                return
            if str(client.my_uid) in MG_STATES and msg.lower() == 'laga':
                mg_data = MG_STATES.pop(str(client.my_uid))
                await actions_team.execute_mg_action(client, chat_context, mg_data['target_name'])
                return

            state_key = f"{client.my_uid}_{uid}"
            if state_key in HELP_MENU_STATES:
                if cmd.startswith('/'): 
                    del HELP_MENU_STATES[state_key]
                elif cmd.isdigit() and 1 <= int(cmd) <= 10:
                    del HELP_MENU_STATES[state_key] 
                    await actions_info.send_help_category(client, chat_context, int(cmd))
                    return
        except KeyError: pass
        
        if await actions_info.handle_simple_replies(client, chat_context): return

        if cmd in COMMANDS:
            if getattr(client, 'is_in_showcase', False) and getattr(client, 'showcase_type', None) == 'normal' and cmd not in ALLOWED_NORMAL:
                await client.send_chat_message(f"[FF0000]Command disabled during Evo Showcase (/v).", chat_context)
                return
            await COMMANDS[cmd](client, chat_context, parts)
            return

        if getattr(client, 'emote_mood', None) is not None:
            emote_ids, error = await parse_and_resolve_emotes(client, msg.lower())
            if error and not emote_ids:
                await client.send_chat_message(error, chat_context)
                return

            if emote_ids:
                if not hasattr(client, 'custom_showcases'): client.custom_showcases = {}
                if not hasattr(client, 'loop_tasks'): client.loop_tasks = {}

                mood = client.emote_mood
                if mood == 'ea':
                    targets = await resolve_uids(client, [], chat_context, exclude_self=False)
                    if targets:
                        await actions_emote.stop_all_tasks(client)
                        client.emote_mood = 'ea' 
                        task_id = str(uuid.uuid4())
                        task = asyncio.create_task(actions_emote.run_custom_showcase(client, task_id, emote_ids))
                        client.custom_showcases[task_id] = {"uids": set(targets), "task": task}

                elif mood == 'es':
                    target = int(uid)
                    actions_emote.steal_uids_from_showcases(client, [target])
                    task_id = str(uuid.uuid4())
                    task = asyncio.create_task(actions_emote.run_custom_showcase(client, task_id, emote_ids))
                    client.custom_showcases[task_id] = {"uids": {target}, "task": task}
                    
                elif mood == 'el':
                    target = int(uid)
                    if target in client.loop_tasks and not client.loop_tasks[target].done():
                        client.loop_tasks[target].cancel()
                    delay = getattr(client, 'el_delay', 10.0)
                    attempts = getattr(client, 'el_attempts', 10)
                    task = asyncio.create_task(actions_emote.run_emote_loop(client, {target}, emote_ids[0], delay, attempts))
                    client.loop_tasks[target] = task
                
                elif mood == 'ef':
                    targets = await resolve_uids(client, [], chat_context, exclude_self=False)
                    if targets:
                        await actions_emote.stop_all_tasks(client)
                        client.emote_mood = 'ef' 
                        task_id = str(uuid.uuid4())
                        delay = getattr(client, 'ef_delay', 10.0)
                        attempts = getattr(client, 'ef_attempts', 10)
                        task = asyncio.create_task(actions_emote.run_emote_loop(client, set(targets), emote_ids[0], delay, attempts, task_id))
                        client.custom_showcases[task_id] = {"uids": set(targets), "task": task}
                return

    except Exception as e:
        traceback.print_exc()
        try: await client.send_chat_message(f"[FF0000]Sys Error: {str(e)}", chat_context)
        except: pass