# bot/commands/actions_emote.py

import asyncio
import json
import random
import uuid
from bot.packets import team_packets
from utils.helpers import resolve_uids, parse_and_resolve_emotes, find_emote_id_in_book, load_saved_uids 
from bot import responses
from utils import admin_manager
from utils.api_client import fetch_player_info

EVO_SHOWCASE_LIST = [
    909000063, 909000068, 909000075, 909000081, 909000085, 
    909000090, 909000098, 909033001, 909035007, 909035012, 
    909037011, 909038010, 909038012, 909039011, 909040010, 
    909042008, 909045001, 909049010, 909051003, 909033002, 
    909041005
]

async def stop_all_tasks(client):
    if getattr(client, 'is_in_showcase', False):
        if getattr(client, 'showcase_task', None) and not client.showcase_task.done():
            client.showcase_task.cancel()
        client.is_in_showcase = False
        client.showcase_type = None

    if hasattr(client, 'custom_showcases'):
        for tid, data in list(client.custom_showcases.items()):
            if 'task' in data and not data['task'].done(): data['task'].cancel()
        client.custom_showcases.clear()

    if hasattr(client, 'loop_tasks'):
        for uid, task in list(client.loop_tasks.items()):
            if not task.done(): task.cancel()
        client.loop_tasks.clear()

def steal_uids_from_showcases(client, target_uids):
    if not hasattr(client, 'custom_showcases'): return
    to_delete = []
    for tid, data in client.custom_showcases.items():
        data['uids'].difference_update(set(target_uids))
        if not data['uids']:
            if 'task' in data and not data['task'].done(): data['task'].cancel()
            to_delete.append(tid)
    for tid in to_delete:
        del client.custom_showcases[tid]

async def run_custom_showcase(client, task_id, emote_ids):
    try:
        client.suppress_auto_actions = True
        for emote_code in emote_ids:
            if task_id not in client.custom_showcases: break
            uids = client.custom_showcases[task_id]['uids']
            if not uids: break
            
            tasks = [
                client.send_online_packet(
                    await team_packets.create_emote_packet(client.my_uid, uid, emote_code, client.key, client.iv, client.region)
                ) 
                for uid in uids
            ]
            if tasks: await asyncio.gather(*tasks)
            await asyncio.sleep(10.0)
    except asyncio.CancelledError:
        pass
    finally:
        if task_id in client.custom_showcases:
            del client.custom_showcases[task_id]
        asyncio.create_task(restore_auto_look(client, 1.0))

async def run_emote_loop(client, targets, emote_code, delay, attempts, task_id=None):
    try:
        client.suppress_auto_actions = True
        for i in range(attempts):
            uids = targets
            if task_id and task_id in client.custom_showcases:
                uids = client.custom_showcases[task_id]['uids']
            if not uids: break

            tasks = [
                client.send_online_packet(
                    await team_packets.create_emote_packet(client.my_uid, uid, emote_code, client.key, client.iv, client.region)
                ) for uid in uids
            ]
            if tasks: await asyncio.gather(*tasks)
            
            if i < attempts - 1:
                await asyncio.sleep(delay)
    except asyncio.CancelledError:
        pass
    finally:
        if task_id and task_id in client.custom_showcases:
            del client.custom_showcases[task_id]
        if hasattr(client, 'loop_tasks') and isinstance(targets, set) and next(iter(targets), None) in client.loop_tasks:
             del client.loop_tasks[next(iter(targets))]
        asyncio.create_task(restore_auto_look(client, 1.0))

async def restore_auto_look(client, delay=4.0):
    await asyncio.sleep(delay)
    is_running = False
    if hasattr(client, 'custom_showcases') and client.custom_showcases: is_running = True
    if hasattr(client, 'loop_tasks') and client.loop_tasks: is_running = True
    if getattr(client, 'is_in_showcase', False): is_running = True
    
    if not is_running:
        client.suppress_auto_actions = False

async def check_advanced_auth(client, uid_str):
    if admin_manager.is_owner(uid_str) or uid_str in admin_manager.get_admins(client.my_uid): return True
    if getattr(client, 'guild_id', None):
        try:
            p_data = await fetch_player_info(uid_str)
            if p_data:
                clan_info = p_data.get('clanBasicInfo') or p_data.get('clan_basic_info') or {}
                if str(clan_info.get('clanId') or clan_info.get('clan_id', '')) == str(client.guild_id):
                    return True
        except: pass
    return False

async def handle_emote_mood(client, ctx, args):
    cmd = args[0].lower()
    await stop_all_tasks(client)
    
    if cmd == '/ea':
        client.emote_mood = 'ea'
        await client.send_chat_message("[00FF00]Emote Mood: ALL (Targets saved list, 1 loop)", ctx)
    elif cmd == '/es':
        client.emote_mood = 'es'
        await client.send_chat_message("[00FF00]Emote Mood: SENDER (Targets you, 1 loop)", ctx)
    elif cmd == '/el':
        client.emote_mood = 'el'
        client.el_delay = float(args[1]) if len(args) > 1 and args[1].replace('.', '', 1).isdigit() else 10.0
        client.el_attempts = int(args[2]) if len(args) > 2 and args[2].isdigit() else 10
        await client.send_chat_message(f"[00FF00]Emote Loop Active ({client.el_delay}s delay, {client.el_attempts} attempts). To change, use: /el [delay] [attempts]", ctx)
    elif cmd == '/ef':
        client.emote_mood = 'ef'
        client.ef_delay = float(args[1]) if len(args) > 1 and args[1].replace('.', '', 1).isdigit() else 10.0
        client.ef_attempts = int(args[2]) if len(args) > 2 and args[2].isdigit() else 10
        await client.send_chat_message(f"[00FF00]Emote Loop for ALL Active ({client.ef_delay}s delay, {client.ef_attempts} attempts). To change, use: /ef [delay] [attempts]", ctx)
    elif cmd == '/end':
        client.emote_mood = None
        await client.send_chat_message("[FF0000]Emote Moods & Tasks: OFF", ctx)

async def handle_single_emote(client, ctx, args):
    if len(args) < 2:
        await client.send_chat_message("[FF0000]Usage: /a [uids...] [emotes] OR /a [emotes]", ctx)
        return
        
    raw_args = args[1:]
    target_args = []
    emote_start_idx = -1

    for idx, arg in enumerate(raw_args):
        arg_lower = arg.lower().strip()
        is_target = (arg_lower in ['me', 'bot', 'all']) or (arg_lower.isdigit() and len(arg_lower) >= 5)
        if is_target:
            target_args.append(arg_lower)
        else:
            emote_start_idx = idx
            break

    if emote_start_idx != -1:
        emote_input = " ".join(raw_args[emote_start_idx:]).strip()
    else:
        emote_input = ""

    # 🟢 ৪৪০, ৪৪১, ৪৪২ এবং ৪৫৮ স্পেশাল টিম/গ্রুপ ইমোট ডিস্ট্রিবিউটর লজিক
    if emote_input in ["440", "441", "442", "458"]:
        client.suppress_auto_actions = True
        try:
            if emote_input in ["440", "441", "442"]:
                # ৪-প্লেয়ার টিম ইমোট জেনারেটর ম্যাপিং
                group_emote_map = {
                    "440": [909053005, 909053013, 909053014, 909053015],
                    "441": [909051002, 909051018, 909051019, 909051020],
                    "442": [909052013, 909052014, 909052015, 909052016]
                }
                ids_list = group_emote_map[emote_input]
                
                # ১. কাস্টম ইউআইডি যদি ইউজার ইনপুট দিয়ে থাকে তা বের করা
                resolved_manual = await resolve_uids(client, target_args, ctx, exclude_self=True)
                seen_manual = set()
                unique_manual = [x for x in resolved_manual if not (x in seen_manual or seen_manual.add(x))]
                
                # ২. বাকী স্লটগুলোর জন্য লবি মেম্বার বা সেভ লিস্ট ব্যাকআপ কালেকশন
                saved_uids = await load_saved_uids(client.my_uid)
                fallback_pool = []
                if client.team_uids:
                    fallback_pool.extend([int(x) for x in client.team_uids])
                fallback_pool.extend([int(x) for x in saved_uids])
                fallback_pool.append(int(client.my_uid))
                fallback_pool.append(int(ctx.get('uid', 0)))
                
                # কাস্টম ইউআইডি এর সাথে ব্যাকআপ মিশিয়ে ৪টি সম্পন্ন করা
                final_uids = list(unique_manual)
                for uid in fallback_pool:
                    if len(final_uids) >= 4:
                        break
                    if uid not in final_uids:
                        final_uids.append(uid)
                        
                final_uids = final_uids[:4]
                
                # একই সাথে ভিন্ন ভিন্ন পোজের ইমোট টাস্ক ফায়ার করা
                tasks = []
                for i, uid_to_perf in enumerate(final_uids):
                    if i < len(ids_list):
                        tasks.append(
                            client.send_online_packet(
                                await team_packets.create_emote_packet(client.my_uid, uid_to_perf, ids_list[i], client.key, client.iv, client.region)
                            )
                        )
                if tasks:
                    await asyncio.gather(*tasks)
                
                emote_names = {
                    "440": "Reverse Penalty!",
                    "441": "Gather Around",
                    "442": "King of Gold"
                }
                await client.send_chat_message(f"[b][c][00FF00]Performing Group Emote: {emote_names[emote_input]} on {len(final_uids)} players!", ctx)
                
            elif emote_input == "458":
                # ২-প্লেয়ার ডুও ইমোট (বট এবং কমান্ড দাতা নিজেই)
                bot_uid = int(client.my_uid)
                commander_uid = int(ctx.get('uid', 0))
                
                tasks = [
                    client.send_online_packet(await team_packets.create_emote_packet(client.my_uid, bot_uid, 909054005, client.key, client.iv, client.region)),
                    client.send_online_packet(await team_packets.create_emote_packet(client.my_uid, commander_uid, 909054020, client.key, client.iv, client.region))
                ]
                await asyncio.gather(*tasks)
                await client.send_chat_message(f"[b][c][00FF00]Performing Duo Emote: Anniversary Parade!", ctx)
        except Exception as e:
            await client.send_chat_message(f"[FF0000]Group Emote Error: {str(e)}", ctx)
        finally:
            asyncio.create_task(restore_auto_look(client, 4.0))
        return

    targets = await resolve_uids(client, target_args, ctx, exclude_self=True)
    if not targets:
        await client.send_chat_message("[FF0000]No targets found.", ctx)
        return

    parts = [p.strip() for p in emote_input.split(',')]
    emote_ids = []
    error = None

    for part in parts:
        if not part: continue
        if '=' in part:
            subparts = part.split('=')
            if len(subparts) == 2 and subparts[0].isdigit() and subparts[1].isdigit():
                start, end = int(subparts[0]), int(subparts[1])
                if start > end: start, end = end, start
                for i in range(start, end + 1):
                    eid, err = await find_emote_id_in_book(client, str(i))
                    if eid: emote_ids.append(eid)
                    elif not error: error = err
            else:
                eid, err = await find_emote_id_in_book(client, part)
                if eid: emote_ids.append(eid)
                elif not error: error = err
        else:
            eid, err = await find_emote_id_in_book(client, part)
            if eid: emote_ids.append(eid)
            elif not error: error = err

    if error and not emote_ids:
        await client.send_chat_message(error, ctx)
        return

    if not emote_ids:
        await client.send_chat_message("[FF0000]No valid emotes found.", ctx)
        return

    if not hasattr(client, 'custom_showcases'): client.custom_showcases = {}
    steal_uids_from_showcases(client, targets)

    task_id = str(uuid.uuid4())
    task = asyncio.create_task(run_custom_showcase(client, task_id, emote_ids))
    client.custom_showcases[task_id] = {"uids": set(targets), "task": task}

async def handle_stealth_single_emote(client, ctx, args):
    if len(args) < 3:
        await client.send_chat_message("[FF0000]Usage: /b [uids...] [emotes] [teamcode] OR /b [emotes] [teamcode]", ctx)
        return

    team_code = args[-1]
    emote_input, uid_args = "", []
    for i, arg in enumerate(args[1:-1]):
        if not arg.isdigit() and arg.lower() not in ['me', 'all', 'bot']:
            emote_input = " ".join(args[i+1:-1])
            break
        uid_args.append(arg)

    if not emote_input and uid_args:
        emote_input = " ".join(uid_args)
        uid_args = []

    emote_ids, error = await parse_and_resolve_emotes(client, emote_input)
    if error:
        await client.send_chat_message(error, ctx)
        return
        
    targets = await resolve_uids(client, uid_args, ctx, exclude_self=True)
    if not targets:
        await client.send_chat_message("[FF0000]No targets found.", ctx)
        return

    client.suppress_auto_actions = True
    try:
        if client.is_in_team:
            await client.send_online_packet(await team_packets.create_leave_team_packet(client.my_uid, client.key, client.iv))
        await asyncio.sleep(0.5)
        await client.send_online_packet(await team_packets.create_join_by_code_packet(team_code, client.key, client.iv))
        await asyncio.sleep(0.5)
        
        for emote_code in emote_ids:
            tasks = [
                client.send_online_packet(
                    await team_packets.create_emote_packet(client.my_uid, uid, emote_code, client.key, client.iv, client.region)
                ) for uid in targets
            ]
            if tasks: await asyncio.gather(*tasks)
            await asyncio.sleep(10.0)
        
        await client.send_online_packet(await team_packets.create_leave_team_packet(client.my_uid, client.key, client.iv))
        client.is_in_team = False
        await client.send_chat_message(f"[00FF00]Stealth Emote Done.", ctx)
    finally:
        asyncio.create_task(restore_auto_look(client, 4.0))

async def handle_normal_evo_showcase(client, ctx, args):
    raw_uid_args = args[1:]
    targets = await resolve_uids(client, raw_uid_args, ctx)
    if not targets: return
    
    is_custom_running = False
    if hasattr(client, 'custom_showcases') and client.custom_showcases: is_custom_running = True
    if hasattr(client, 'loop_tasks') and client.loop_tasks: is_custom_running = True
    if is_custom_running:
        await client.send_chat_message("[FF0000]Custom Showcase or Loop is running! Stop it using /st first.", ctx)
        return

    client.is_in_showcase = True
    client.showcase_type = 'normal'
    client.suppress_auto_actions = True 
    await client.send_chat_message(f"[00BFFF]Started Evo Showcase (Listed Emotes).", ctx)

    async def task():
        try:
            emotes = random.sample(EVO_SHOWCASE_LIST, len(EVO_SHOWCASE_LIST))
            for emote_code in emotes:
                if not client.is_in_showcase: break
                tasks = [
                    client.send_online_packet(
                        await team_packets.create_emote_packet(client.my_uid, uid, emote_code, client.key, client.iv, client.region)
                    ) for uid in targets
                ]
                if tasks: await asyncio.gather(*tasks)
                await asyncio.sleep(10.0) 
            if client.is_in_showcase:
                await client.send_chat_message("[00FF00]Showcase Finished.", ctx)
        except asyncio.CancelledError: pass
        finally:
            client.is_in_showcase = False
            client.showcase_type = None
            client.suppress_auto_actions = False
    client.showcase_task = asyncio.create_task(task())

async def handle_stop_showcase(client, ctx, args):
    await stop_all_tasks(client) 
    await client.send_chat_message("[FFFF00]All Showcases and Loops Stopped.", ctx)

async def handle_block(client, ctx, args):
    sender_uid = str(ctx.get('uid', ''))
    if not await check_advanced_auth(client, sender_uid):
        await client.send_chat_message("[FF0000]Restriction: Only Boss or Guild Members can use this command.", ctx)
        return

    dynamic_mode = len(args) == 1
    targets = await resolve_uids(client, args[1:], ctx, exclude_self=True)
    if not targets and not dynamic_mode:
        await client.send_chat_message("[FF0000]No valid targets found to block.", ctx)
        return

    if getattr(client, 'is_blocking', False):
        if getattr(client, 'block_task', None) and not client.block_task.done():
            client.block_task.cancel()
        await asyncio.sleep(0.2)

    client.is_blocking = True
    await client.send_chat_message(f"[FFFF00]Block activated! (Paused while Solo) 🚀", ctx)

    async def _block_loop():
        try:
            emote_id = 909000085
            iteration = 0
            current_targets = targets
            while getattr(client, 'is_blocking', False):
                if not getattr(client, 'is_in_team', False):
                    await asyncio.sleep(1.0)
                    continue
                
                if dynamic_mode and iteration % 15 == 0:
                    current_targets = list(dict.fromkeys(await load_saved_uids(client.my_uid)))
                    current_targets = [t for t in current_targets if str(t) != str(client.my_uid)]

                if current_targets:
                    tasks = [
                        client.send_online_packet(
                            await team_packets.create_emote_packet(client.my_uid, uid, emote_id, client.key, client.iv, client.region)
                        ) for uid in current_targets
                    ]
                    if tasks: await asyncio.gather(*tasks)
                await asyncio.sleep(0.05) 
                iteration += 1
        except asyncio.CancelledError: pass
        finally: client.is_blocking = False
    client.block_task = asyncio.create_task(_block_loop())

async def handle_off(client, ctx, args):
    if not await check_advanced_auth(client, str(ctx.get('uid', ''))):
        await client.send_chat_message("[FF0000]Restriction: Only Boss or Guild Members can use this command.", ctx)
        return

    if getattr(client, 'is_blocking', False):
        if getattr(client, 'block_task', None) and not client.block_task.done():
            client.block_task.cancel()
        await client.send_chat_message("[00FF00]Block task stopped completely.", ctx)
    else:
        await client.send_chat_message("[FF0000]No block task is running.", ctx)

async def handle_emote_list(client, ctx, args):
    if not hasattr(client, 'emote_book') or not client.emote_book:
        try:
            with open('config/emote_book.json', 'r', encoding='utf-8') as f:
                client.emote_book = json.load(f)
        except Exception as e:
            await client.send_chat_message(f"[FF0000]Error loading emote_book: {e}", ctx)
            return

    if len(args) == 1:
        message_parts = responses.get_ebook_message(client.emote_book)
    else:
        cat_id = " ".join(args[1:])
        message_parts = responses.get_emote_category_details(client.emote_book, cat_id)
    
    for part in message_parts:
        await client.send_chat_message(part, ctx)
        await asyncio.sleep(0.5)