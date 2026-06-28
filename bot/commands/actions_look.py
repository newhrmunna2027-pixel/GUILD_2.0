# bot/commands/actions_look.py

import asyncio
import random
import json
import os
from bot.packets import team_packets

# 🟢 পরম পাথ (Absolute Path) জেনারেটর যা ডিরেক্টরি অমিল এড়াতে সাহায্য করে
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'auto_look.json')
DELAYS_FILE = os.path.join(BASE_DIR, 'config', 'bundle_delays.json')

# ডাইনামিক ক্যাশিং ভেরিয়েবলসমূহ
_delays_cache = {}
_delays_last_mtime = 0

def load_auto_look_config():
    if not os.path.exists(os.path.dirname(CONFIG_FILE)):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_auto_look_status(uid, status):
    data = load_auto_look_config()
    data[str(uid)] = status
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except: pass

def load_bundle_delays():
    """
    এম-টাইম মেমরি ক্যাশিং মেথড:
    রানটাইমে জেসন ফাইলটি পরিবর্তিত হলে কেবল তখনই ক্যাশ রিলোড করবে, 
    অন্যথায় সরাসরি মেমরি ক্যাশ থেকে ডাটা প্রদান করবে।
    """
    global _delays_cache, _delays_last_mtime
    
    default_delays = {
        "rampage": 4.0,
        "cannibal": 3.5,
        "devil": 4.5,
        "scorpio": 5.0,
        "frostfire": 4.0,
        "paradox": 4.2,
        "naruto": 4.0,
        "aurora": 3.8,
        "midnight": 4.5,
        "itachi": 4.0,
        "dreamspace": 4.5,
        "Eclipse": 3.9
    }
    
    if not os.path.exists(os.path.dirname(DELAYS_FILE)):
        os.makedirs(os.path.dirname(DELAYS_FILE), exist_ok=True)
        
    if not os.path.exists(DELAYS_FILE):
        try:
            with open(DELAYS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_delays, f, indent=4)
            _delays_cache = default_delays
            _delays_last_mtime = os.path.getmtime(DELAYS_FILE)
        except:
            return default_delays
        return default_delays
        
    # এম-টাইম ট্র্যাকিং এবং ক্যাশ আপডেট লুপ
    try:
        current_mtime = os.path.getmtime(DELAYS_FILE)
        if current_mtime != _delays_last_mtime or not _delays_cache:
            with open(DELAYS_FILE, 'r', encoding='utf-8') as f:
                _delays_cache = json.load(f)
            _delays_last_mtime = current_mtime
    except Exception:
        if not _delays_cache:
            _delays_cache = default_delays
            
    return _delays_cache

BUNDLE_MAP = {
    "rampage": 914000002, "cannibal": 914000003, "devil": 914038001,
    "scorpio": 914039001, "frostfire": 914042001, "paradox": 914044001,
    "naruto": 914047001, "aurora": 914047002, "midnight": 914048001,
    "itachi": 914050001, "dreamspace": 914051001, "Eclipse": 914053001
}

async def _apply_bundle(client, bundle_id, bundle_name, ctx):
    try:
        pkt = await team_packets.create_bundle_packet(bundle_id, client.key, client.iv, client.region)
        await client.send_online_packet(pkt)
        if ctx: 
            await client.send_chat_message(f"[B][C][00FF00]Equipped: {bundle_name.title()}", ctx)
        client.current_bundle_id = bundle_id
    except: pass

async def handle_look(client, ctx, args=None):
    if not client.is_in_team:
        await client.send_chat_message("[FF0000]Bot must be in a team.", ctx)
        return

    if args is None: 
        msg_parts = ctx['msg'].split()
    else: 
        msg_parts = args if isinstance(args, list) else ctx['msg'].split()

    if len(msg_parts) < 2:
        b_map = list(BUNDLE_MAP.keys())
        bundle_list_str = "\n".join([f"• {i+1} = {name}" for i, name in enumerate(b_map)])
        await client.send_chat_message(f"[B][C][00FF00]AVAILABLE BUNDLES\n[FFFFFF]{bundle_list_str}", ctx)
        return

    user_input = msg_parts[1].lower()
    bundle_id, final_bundle_name = None, user_input
    
    current_map = list(BUNDLE_MAP.keys())
    
    if user_input.isdigit():
        try:
            index = int(user_input) - 1
            if 0 <= index < len(current_map):
                final_bundle_name = current_map[index]
                bundle_id = BUNDLE_MAP[final_bundle_name]
        except: pass
    elif user_input == "random":
        final_bundle_name = random.choice(current_map)
        bundle_id = BUNDLE_MAP[final_bundle_name]
    else:
        if user_input in current_map:
            bundle_id = BUNDLE_MAP.get(user_input)
            final_bundle_name = user_input
    
    if not bundle_id:
        await client.send_chat_message(f"[FF0000]Bundle '{user_input}' not available!", ctx)
        return

    if getattr(client, 'suppress_auto_actions', False) or getattr(client, 'is_in_showcase', False):
        await client.send_chat_message("[FFFF00]Bot is currently busy. Try again in a few seconds.", ctx)
        return

    last_team_code = client.last_joined_team_code
    
    # লাইভ ক্যাশ জেসন ডিলে লোড করা হচ্ছে
    bundle_delays = load_bundle_delays()
    selected_delay = bundle_delays.get(final_bundle_name, 4.0)

    if not last_team_code:
        anim_pkt = await team_packets.animation_packet(bundle_id, client.key, client.iv)
        await client.send_online_packet(anim_pkt)
        
        await asyncio.sleep(selected_delay) 
        
        await _apply_bundle(client, bundle_id, final_bundle_name, ctx)
        return

    await client.send_chat_message("[FFFF00]Refreshing look...", ctx)
    await client.send_online_packet(await team_packets.create_leave_team_packet(client.my_uid, client.key, client.iv))
    client.is_in_team = False
    await asyncio.sleep(1.5)
    
    await client.send_online_packet(await team_packets.create_join_by_code_packet(last_team_code, client.key, client.iv))
    client.is_in_team = True
    await asyncio.sleep(1.0)
    
    anim_pkt = await team_packets.animation_packet(bundle_id, client.key, client.iv)
    await client.send_online_packet(anim_pkt)
    
    await asyncio.sleep(selected_delay)
    
    await _apply_bundle(client, bundle_id, final_bundle_name, ctx)

async def handle_animation(client, ctx, args=None):
    if not client.is_in_team:
        await client.send_chat_message("[FF0000]Bot must be in a team.", ctx)
        return

    if args is None: 
        msg_parts = ctx['msg'].split()
    else: 
        msg_parts = args if isinstance(args, list) else ctx['msg'].split()

    if len(msg_parts) < 2:
        b_map = list(BUNDLE_MAP.keys())
        bundle_list_str = "\n".join([f"• {i+1} = {name}" for i, name in enumerate(b_map)])
        await client.send_chat_message(f"[B][C][00FF00]AVAILABLE ANIMATIONS\n[FFFFFF]{bundle_list_str}", ctx)
        return

    user_input = msg_parts[1].lower()
    bundle_id, final_bundle_name = None, user_input
    
    current_map = list(BUNDLE_MAP.keys())
    
    if user_input.isdigit():
        try:
            index = int(user_input) - 1
            if 0 <= index < len(current_map):
                final_bundle_name = current_map[index]
                bundle_id = BUNDLE_MAP[final_bundle_name]
        except: pass
    else:
        if user_input in current_map:
            bundle_id = BUNDLE_MAP.get(user_input)
            final_bundle_name = user_input
    
    if not bundle_id:
        await client.send_chat_message(f"[FF0000]Animation '{user_input}' not found!", ctx)
        return

    if getattr(client, 'suppress_auto_actions', False) or getattr(client, 'is_in_showcase', False):
        await client.send_chat_message("[FFFF00]Bot is currently busy. Try again in a few seconds.", ctx)
        return

    anim_pkt = await team_packets.animation_packet(bundle_id, client.key, client.iv)
    await client.send_online_packet(anim_pkt)
    
    if ctx:
        await client.send_chat_message(f"[B][C][00FF00]Playing Animation: {final_bundle_name.title()}", ctx)

async def handle_look_on(client, ctx, args):
    client.auto_look_enabled = True
    save_auto_look_status(client.my_uid, True)
    await client.send_chat_message("[00FF00]Auto Look Changer: [ON]", ctx)

async def handle_look_off(client, ctx, args):
    client.auto_look_enabled = False
    save_auto_look_status(client.my_uid, False)
    await client.send_chat_message("[FF0000]Auto Look Changer: [OFF]", ctx)

async def equip_random_bundle(client, ctx=None):
    if getattr(client, 'suppress_auto_actions', False): return
    if getattr(client, 'is_in_showcase', False): return
    if not getattr(client, 'auto_look_enabled', True): return

    b_list = list(BUNDLE_MAP.keys())
    final_bundle_name = random.choice(b_list)
    bundle_id = BUNDLE_MAP[final_bundle_name]
    await _apply_bundle(client, bundle_id, final_bundle_name, ctx)

async def equip_random_bundle_2x(client, ctx=None):
    await equip_random_bundle(client, ctx)

async def equip_random_bundle_3x(client, ctx=None):
    await equip_random_bundle(client, ctx)

handle_look_change = handle_look

# 🟢 মডিউল ইমপোর্ট হওয়ামাত্র ব্যাকগ্রাউন্ডে স্বয়ংক্রিয় ফাইল তৈরির ট্রিগার
load_bundle_delays()