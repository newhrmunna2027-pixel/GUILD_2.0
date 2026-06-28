# filepath: bot/core/handlers.py
# bot/core/handlers.py

import json
import asyncio
import time
from bot.packets import team_packets, chat_packets, base_handler
from bot.status_parser import parse_status_response
from utils.helpers import (
    format_uid_for_chat, sync_team_to_saved_uids, add_uids_to_list, 
    remove_single_saved_uid, save_saved_uids, save_bot_room_state, load_bot_room_state
)
from bot.commands.actions_look import equip_random_bundle
from bot.core.logic import manage_team_file, load_saved_guild_members, execute_solo_logic
from utils import admin_manager
from utils.api_client import fetch_player_info
from utils.team_logger import log_team_info
from utils.packet_logger import log_packet
import random

def get_val(data_dict, key, default=None):
    if not isinstance(data_dict, dict): 
        return default
    # স্ট্রিং এবং ইন্টিজার উভয় ধরনের কী সাপোর্ট করার জন্য ডাবল চেক লজিক
    val = data_dict.get(str(key))
    if val is None:
        try:
            val = data_dict.get(int(key))
        except:
            pass
    if isinstance(val, dict):
        return val.get("data", default)
    return val if val is not None else default

async def handle_0400_roster(bot, hex_data):
    players = await team_packets.decode_team_update_packet(hex_data[10:], bot.key, bot.iv)
    current_team_uids = [int(p['uid']) for p in players if 'uid' in p and str(p['uid']).isdigit()]
    bot_uid_int = int(bot.my_uid)

    if not current_team_uids or bot_uid_int not in current_team_uids:
        if bot.is_in_team:
            bot.is_in_team = False
            # ROOM CHAT GHOSTING PROTECTION
            if not getattr(bot, 'is_magic_mode', False) and not getattr(bot, 'is_in_room', False) and not getattr(bot, 'is_joining_room', False):
                await manage_team_file(bot, "clear")
                await save_saved_uids(bot.my_uid, [])
        return

    bot.is_in_team = True
    bot.saved_uids = current_team_uids
    bot.team_uids = current_team_uids
    await manage_team_file(bot, "sync_full_team", t_uid=current_team_uids)
    await sync_team_to_saved_uids(bot.my_uid, current_team_uids)

async def handle_0f00_status(bot, data):
    from bot.core.manager import send_chat_message
    status = await parse_status_response(data)
    if not status: return
    
    target_uid = str(status['uid'])
    if target_uid in bot.status_requests:
        ctx = bot.status_requests[target_uid]
        
        t_name, t_clan = "N/A", "No Guild"
        t_info = await fetch_player_info(target_uid)
        if t_info:
            b1 = t_info.get('basicInfo') or t_info.get('basic_info') or {}
            c1 = t_info.get('clanBasicInfo') or t_info.get('clan_basic_info') or {}
            t_name = b1.get('nickname', 'N/A')
            t_clan = c1.get('clanName') or c1.get('clan_name') or 'No Guild'
            
        leader_uid = status.get('leader', 'N/A')
        l_name, l_clan = "N/A", "No Guild"
        has_leader = False
        
        if leader_uid.isdigit() and len(leader_uid) > 5:
            has_leader = True
            l_info = await fetch_player_info(leader_uid)
            if l_info:
                b2 = l_info.get('basicInfo') or l_info.get('basic_info') or {}
                c2 = l_info.get('clanBasicInfo') or l_info.get('clan_basic_info') or {}
                l_name = b2.get('nickname', 'N/A')
                l_clan = c2.get('clanName') or c2.get('clan_name') or 'No Guild'
        
        fmt_target = await format_uid_for_chat(target_uid)
        
        msg_lines = [
            f"[b][c][FFD700]╭━━━[FFFFFF] STATUS REPORT [FFD700]━━━╮",
            f"[b][c][FFD700]┣━━━━━━━━━━━━━┫",
            f"[b][C0C0C0]  🎯 PLAYER:",
            f"[b][FFFFFF]    Name: [00FFFF]{t_name}",
            f"[b][FFFFFF]    UID:  [00FFFF]{fmt_target}",
            f"[b][FFFFFF]    Guild:[00FFFF]{t_clan}",
            f"[b][C0C0C0]  ⚡ STATE: [00FF00]{status['status']}"
        ]
        
        if status['status'] == "IN ROOM":
            rid = status.get('room_id', 'N/A')
            if rid != 'N/A': 
                msg_lines.append(f"[b][C0C0C0]  🚪 Room ID: [FFFF00]{await format_uid_for_chat(rid)}")
                
        if has_leader:
            fmt_leader = await format_uid_for_chat(leader_uid)
            msg_lines.extend([
                f"[b][c][FFD700]┣━━━━━━━━━━━━━┫",
                f"[b][C0C0C0]  👑 LEADER:",
                f"[b][FFFFFF]    Name: [00FFFF]{l_name}",
                f"[b][FFFFFF]    UID:  [00FFFF]{fmt_leader}",
                f"[b][FFFFFF]    Guild:[00FFFF]{l_clan}",
                f"[b][C0C0C0]  👥 Team Size: [FFFFFF]{status.get('squad_size', '?')}"
            ])
            
        msg_lines.append(f"[b][c][FFD700]╰━━━━━━━━━━━━━╯")
        
        await send_chat_message(bot, "\n".join(msg_lines), ctx)
        del bot.status_requests[target_uid]

async def start_room_chat_auth_sequence(bot, room_id, secret_code):
    print(f"[{bot.bot_name}] [🔄 ROOM AUTH] Initiating Room Chat Join Sequence...")
    
    wait_time = 0
    while (not bot.chat_connected or not bot.chat_writer) and wait_time < 60:
        print(f"[{bot.bot_name}] [🔄 ROOM AUTH] Waiting for Chat socket connection... ({wait_time*0.5}s)")
        await asyncio.sleep(0.5)
        wait_time += 1

    if not bot.chat_connected or not bot.chat_writer:
        print(f"[{bot.bot_name}] [❌ ROOM AUTH ERROR] Chat connection not ready after 30 seconds. Room Chat Auth aborted.")
        return

    try:
        print(f"[{bot.bot_name}] [🔄 ROOM AUTH] Chat socket is active! Re-Activating Lobby Chat Session (Secret: {secret_code})")
        
        print(f"[{bot.bot_name}] [🔄 ROOM AUTH] Sending Lobby Room Chat Join (120c, Action 3)...")
        auth_pkt1 = await team_packets.lobby_room_chat_join(room_id, secret_code, bot.key, bot.iv)
        bot.chat_writer.write(auth_pkt1)
        await bot.chat_writer.drain()
        await asyncio.sleep(1.0)
        
        print(f"[{bot.bot_name}] [🔄 ROOM AUTH] Sending Chat Room Join/Bind (120c, Action 1)...")
        auth_pkt2 = await team_packets.chat_room_join(room_id, bot.my_uid, bot.key, bot.iv)
        bot.chat_writer.write(auth_pkt2)
        await bot.chat_writer.drain()
        print(f"[{bot.bot_name}] [✅ ROOM AUTH SUCCESS] Ghost room chat authentication completed successfully!")
        
        print(f"[{bot.bot_name}] [🔄 ROOM AUTH] Sending Welcome message to room chat channel...")
        welcome_pkt = await team_packets.send_captured_room_msg("GET Ready! Its Show Time\n Mo✅ther ✅f✅u✅c✅ker ", room_id, bot.key, bot.iv)
        bot.chat_writer.write(welcome_pkt)
        await welcome_pkt.drain()
        print(f"[{bot.bot_name}] [✅ ROOM AUTH SUCCESS] Welcome message sent to Room {room_id}!")
        
    except Exception as e:
        print(f"[{bot.bot_name}] [❌ ROOM AUTH ERROR] Room Auth Sequence failed: {e}")

async def handle_0e00_room_join(bot, hex_data):
    print(f"[{bot.bot_name}] [0e00 INTERCEPT] Garena custom room join packet detected!")
    if len(hex_data) < 100: 
        print(f"[{bot.bot_name}] [0e00 INTERCEPT] Packet too short ({len(hex_data)} chars). Aborted.")
        return
        
    try:
        decoded_msg = await base_handler.DeCode_PackEt(bytes.fromhex(hex_data[10:]).hex())
        if not decoded_msg or decoded_msg == "{}": 
            print(f"[{bot.bot_name}] [0e00 INTERCEPT] ❌ Protobuf DeCode failed or returned empty JSON!")
            return
            
        parsed_json = json.loads(decoded_msg)
        print(f"[{bot.bot_name}] [0e00 INTERCEPT] ✅ Decoded JSON successfully!")
        
        room_data = get_val(parsed_json, "5", {})
        if isinstance(room_data, dict):
            nested_2 = get_val(room_data, "2", {})
            if isinstance(nested_2, dict):
                room_id = get_val(nested_2, "1")
                secret_code = get_val(nested_2, "36") or get_val(nested_2, "40") or get_val(nested_2, "17")
                
                if room_id and secret_code:
                    print(f"[{bot.bot_name}] [0e00 INTERCEPT] 👑 Room ID Captured: {room_id} | Secret Code: {secret_code}")
                    
                    old_state = load_bot_room_state(bot.my_uid)
                    if old_state and old_state.get("room_id") and str(old_state.get("room_id")) != str(room_id):
                        try:
                            old_leave_pkt = await team_packets.physical_room_leave(old_state.get("room_id"), bot.key, bot.iv)
                            bot.online_writer.write(old_leave_pkt)
                            await bot.online_writer.drain()
                            await asyncio.sleep(0.5)
                        except: pass
                    
                    save_bot_room_state(bot.my_uid, room_id, secret_code)
                    
                    bot.is_joining_room = False
                    bot.room_id = room_id
                    bot.room_secret_code = secret_code
                    bot.is_in_room = True
                    
                    asyncio.create_task(start_room_chat_auth_sequence(bot, room_id, secret_code))
                else:
                    print(f"[{bot.bot_name}] [0e00 INTERCEPT] ❌ Failed to extract room_id or secret_code from nest_2!")
            else:
                print(f"[{bot.bot_name}] [0e00 INTERCEPT] ❌ nest_2 is not a dict or missing!")
        else:
            print(f"[{bot.bot_name}] [0e00 INTERCEPT] ❌ Field 5 is missing inside parsed json!")
            
    except Exception as e:
        print(f"[{bot.bot_name}] [0e00 INTERCEPT] ❌ Error inside handle_0e00_room_join: {e}")

async def handle_0500_events(bot, hex_data):
    try:
        packet_str = await base_handler.DeCode_PackEt(bytes.fromhex(hex_data[10:]).hex())
        if not packet_str or packet_str == "{}": return
        packet_json = json.loads(packet_str)
        if not isinstance(packet_json, dict): return
        
        recruit_id = get_val(packet_json, "14") or get_val(packet_json, "8")
        if recruit_id and isinstance(recruit_id, str) and "_" in recruit_id:
            bot.last_invite_code = recruit_id
            print(f"[{bot.bot_name}] 🟢 Parsed Secret Token (Recruit): {recruit_id}")
            
        session_id = get_val(packet_json, "17")
        if session_id:
            bot.last_lobby_session_id = str(session_id)
            print(f"[{bot.bot_name}] 🟢 Parsed Lobby Session ID: {session_id}")
            
        team_code_val = get_val(packet_json, "11")
        if team_code_val and isinstance(team_code_val, str) and team_code_val.isdigit():
            bot.last_joined_team_code = team_code_val
            print(f"[{bot.bot_name}] 🟢 Parsed Roster Team Code: {team_code_val}")
            
        nested_5 = get_val(packet_json, "5", {})
        if isinstance(nested_5, dict):
            leader_val = get_val(nested_5, "1")
            if leader_val:
                bot.last_invite_leader = str(leader_val)
                print(f"[{bot.bot_name}] 🟢 Parsed Lobby Leader UID: {leader_val}")

                event_action = get_val(packet_json, "4")
                nested_data = get_val(packet_json, "5", {})

                if not isinstance(nested_data, dict): return

                if '17' in nested_data and '1' in nested_data:
                    await _on_chat_code_update(bot, nested_data)
                    
                has_leader = ('1' in nested_data or 1 in nested_data)
                has_invite = ('8' in nested_data or 8 in nested_data)
                if has_leader and has_invite:
                    await _on_team_invite(bot, nested_data)

                if event_action == 3: 
                    await _on_leader_change(bot, nested_data)
                elif event_action in [6, 22]: 
                    await _on_member_add(bot, nested_data)
                elif event_action in [8, 9]: 
                    await _on_member_leave(bot, nested_data)
                elif event_action == 10:
                    # 🔴 EMOTE PACKET ID FIELD MARKER (event_action = 10)
                    # ইমোট দিলে কোন মেম্বার এড/রিমুভ হয় না, তাই লুক চেঞ্জ হবে না।
                    pass
                    
    except Exception:
        pass 

async def delayed_graceful_exit(bot):
    if getattr(bot, 'is_in_room', False) or getattr(bot, 'is_joining_room', False):
        return
        
    print(f"[{bot.bot_name}] 🛠️ Upgrading team size to 5 members before leaving...")
    try:
        pkts = await team_packets.create_team_packet(5, bot.my_uid, bot.key, bot.iv, bot.region)
        if pkts and len(pkts) >= 2:
            if bot.online_connected and getattr(bot, 'online_writer', None):
                bot.online_writer.write(pkts[0])
                await bot.online_writer.drain()
                await asyncio.sleep(0.4)
                bot.online_writer.write(pkts[1])
                await bot.online_writer.drain()
                await asyncio.sleep(0.5)
    except Exception as e:
        print(f"[{bot.bot_name}] ❌ Team upgrade error before solo: {e}")

    print(f"[{bot.bot_name}] 👋 Going solo now...")
    await execute_solo_logic(bot)

async def auto_lobby_upgrade_and_transfer(bot, old_leader):
    try:
        from bot.core.manager import send_online_packet
        print(f"[{bot.bot_name}] 👑 Leader Flag received by Bot! Upgrading lobby size to 5 using /5 command logic...")
        
        pkts = await team_packets.create_team_packet(5, bot.my_uid, bot.key, bot.iv, bot.region)
        if pkts and len(pkts) >= 2:
            await send_online_packet(bot, pkts[0])
            await asyncio.sleep(0.8) 
            await send_online_packet(bot, pkts[1])
            await asyncio.sleep(0.5) 
            
        print(f"[{bot.bot_name}] 🔄 Transferring leader flag back to original leader: {old_leader}...")
        transfer_pkt = await team_packets.create_transfer_flag_packet(
            bot.my_uid, old_leader, bot.key, bot.iv, bot.region
        )
        await send_online_packet(bot, transfer_pkt)
        
    except Exception as e:
        print(f"[{bot.bot_name}] ❌ Auto lobby upgrade/transfer error: {e}")

async def _on_leader_change(bot, data):
    if getattr(bot, 'is_in_room', False) or getattr(bot, 'is_joining_room', False):
        return

    f2 = get_val(data, "2", {})
    leader_uid = get_val(f2, "1")
    
    if leader_uid and str(leader_uid).lower() not in["none", "null", ""]:
        await manage_team_file(bot, "set_leader", t_uid=leader_uid)
        
        if str(leader_uid) == str(bot.my_uid):
            print(f"[{bot.bot_name}] 👑 Leader Crown received! Upgrading to 5-member & Going solo instantly...")
            asyncio.create_task(delayed_graceful_exit(bot))

async def _on_member_add(bot, data):
    f6 = get_val(data, "6", {})
    member_uid = get_val(f6, "1")
    if not member_uid: member_uid = get_val(data, "1")

    if member_uid and str(member_uid).lower() not in ["none", "null", ""]:
        member_uid_int = int(member_uid)
        
        is_new_member = member_uid_int not in bot.team_uids
        
        if is_new_member:
            bot.team_uids.append(member_uid_int)
            await manage_team_file(bot, "add_member", t_uid=member_uid)
            await add_uids_to_list(bot.my_uid, [member_uid_int])

            # 🟢 টিমে অন্য মেম্বার জয়েন করলে বটের লুক চেঞ্জ হবে
            if getattr(bot, 'auto_look_enabled', True) and not bot.suppress_auto_actions:
                asyncio.create_task(equip_random_bundle(bot, None))

async def _on_member_leave(bot, data):
    f6 = get_val(data, "6", {})
    left_uid = get_val(f6, "1")
    if not left_uid or str(left_uid).lower() in ["none", "null", ""]:
        left_uid = get_val(data, "1")

    if not left_uid or str(left_uid).lower() in["none", "null", ""]: return
    left_uid_str = str(left_uid)

    if left_uid_str == str(bot.my_uid):
        bot.is_in_team = False
        bot.team_uids = []
        
        # 🟢 বট নিজে লিভ নিলেও যাতে সাথে সাথে বটের লুক চেঞ্জ হয় তার ফিক্স
        if getattr(bot, 'auto_look_enabled', True) and not bot.suppress_auto_actions:
            asyncio.create_task(equip_random_bundle(bot, None))

        if not getattr(bot, 'is_magic_mode', False) and not getattr(bot, 'is_in_room', False) and not getattr(bot, 'is_joining_room', False):
            bot.team_chat_authed = False
            await manage_team_file(bot, "clear")
            await bot._close_chat_connection()
        return

    left_uid_int = int(left_uid_str)
    is_member_leaving = left_uid_int in bot.team_uids
    
    if is_member_leaving:
        bot.team_uids.remove(left_uid_int)
        await manage_team_file(bot, "remove_member", t_uid=left_uid_str)
        await remove_single_saved_uid(bot.my_uid, left_uid_str)

        if not getattr(bot, 'is_magic_mode', False) and not getattr(bot, 'is_in_room', False) and not getattr(bot, 'is_joining_room', False):
            bot.team_chat_authed = False
            await bot._close_chat_connection()

        if left_uid_str == str(bot.current_chat_owner):
            bot.current_chat_owner = None
            bot.current_chat_code = None
            bot.team_chat_authed = False
            if not getattr(bot, 'is_magic_mode', False) and not getattr(bot, 'is_in_room', False) and not getattr(bot, 'is_joining_room', False):
                await bot._close_chat_connection()

        # 🟢 টিমের অন্য মেম্বার লিভ নিলে বটের লুক চেঞ্জ হবে
        if getattr(bot, 'auto_look_enabled', True) and not bot.suppress_auto_actions:
            asyncio.create_task(equip_random_bundle(bot, None))

async def _on_chat_code_update(bot, data):
    if getattr(bot, 'is_in_room', False) or getattr(bot, 'is_joining_room', False):
        return

    from bot.core.manager import send_chat_packet
    
    new_owner_uid = str(get_val(data, '1', ''))
    new_chat_code = str(get_val(data, '17', ''))

    if new_owner_uid.lower() in["none", "null", ""] or new_chat_code.lower() in ["none", "null", ""]: 
        return

    if new_owner_uid == str(bot.my_uid):
        print(f"[{bot.bot_name}] 👑 Bot became leader via Chat Code update! Upgrading and going solo...")
        asyncio.create_task(delayed_graceful_exit(bot))
        return

    is_new_chat = (bot.current_chat_code != new_chat_code)

    bot.current_chat_owner = new_owner_uid
    bot.current_chat_code = new_chat_code
    
    if is_new_chat:
        bot.team_chat_authed = False 
        
        async def auth_and_welcome():
            for _ in range(20): 
                if bot.chat_connected: break
                await asyncio.sleep(0.5)
            
            if bot.chat_connected and not bot.team_chat_authed and bot.current_chat_owner and bot.current_chat_code:
                auth_pkt = await chat_packets.AuthTeam(bot.current_chat_owner, bot.current_chat_code, bot.key, bot.iv)
                if auth_pkt and await send_chat_packet(bot, auth_pkt): 
                    bot.team_chat_authed = True
                            
        asyncio.create_task(auth_and_welcome())
    else:
        if bot.is_in_team and not bot.team_chat_authed and bot.chat_connected and bot.current_chat_owner and bot.current_chat_code: 
            auth_pkt = await chat_packets.AuthTeam(bot.current_chat_owner, bot.current_chat_code, bot.key, bot.iv)
            if auth_pkt and await send_chat_packet(bot, auth_pkt): 
                bot.team_chat_authed = True

async def _on_team_invite(bot, data):
    if getattr(bot, 'is_in_room', False) or getattr(bot, 'is_joining_room', False):
        return

    from bot.core.manager import send_online_packet
    
    leader_val = get_val(data, '1', '')
    leader_uid = "".join(c for c in str(leader_val) if c.isdigit())
    invite_code = str(get_val(data, '8', '')).strip()
    if not invite_code or "_" not in invite_code:
        invite_code = getattr(bot, 'last_invite_code', '').strip()
        
    raw_inviter = get_val(data, '3')
    if not raw_inviter or str(raw_inviter).strip() in ["", "0", "None"]:
        raw_inviter = leader_uid
    inviter_uid = "".join(c for c in str(raw_inviter) if c.isdigit())
    
    if getattr(bot, 'is_locked', False):
        if not (admin_manager.is_owner(inviter_uid) or inviter_uid in admin_manager.get_admins(bot.my_uid)):
            return 
        else:
            bot.is_locked = False 
    
    potential_uids = []
    for k in ['1', '2', '3', '4', '5', '6']:
        val = get_val(data, k)
        if str(val).isdigit():
            potential_uids.append(str(val))
            
    should_join = False
    
    for uid in potential_uids:
        if admin_manager.can_auto_join(bot.my_uid, uid):
            should_join = True
            break
            
    if not should_join:
        try:
            saved_members = load_saved_guild_members(bot.my_uid)
            if inviter_uid in saved_members:
                should_join = True
        except Exception: pass

    if should_join:
        if not getattr(bot, 'is_magic_mode', False):
            await bot._close_chat_connection()
            
        bot.last_invite_leader = leader_uid
        bot.last_invite_code = invite_code
            
        accept_pkt = await team_packets.create_accept_invite_packet(leader_uid, invite_code, bot.key, bot.iv, bot.region)
        await bot.send_online_packet(accept_pkt)
        bot.is_in_team = True
        bot.team_chat_authed = False 
        
        # 🟢 বট সাকসেসফুলি টিমে ঢোকার সাথে সাথে একবার ইনস্ট্যান্ট লুক চেঞ্জ করবে
        async def delayed_look_change():
            await asyncio.sleep(0.5)
            if getattr(bot, 'auto_look_enabled', True) and not bot.suppress_auto_actions:
                await equip_random_bundle(bot, None)
        asyncio.create_task(delayed_look_change())