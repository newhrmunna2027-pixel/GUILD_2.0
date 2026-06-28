# bot/core/bot_init.py

import json
import os
import asyncio
import aiosqlite
import random
from utils import admin_manager
from utils.api_client import fetch_player_info
from bot.commands.actions_look import load_auto_look_config
from core.database import async_save_profile

def init_bot_state(bot, config, session_data):
    bot.config = config
    bot.auth = session_data['auth']
    bot.server = session_data['server']
    bot.key = bot.auth.key
    bot.iv = bot.auth.iv
    bot.my_uid = bot.auth.account_uid
    bot.region = bot.server.Region
    
    bot.guild_id = getattr(bot.server, 'Clan_ID', None)
    bot.guild_data = getattr(bot.server, 'Clan_Compiled_Data', None)
    
    bot.online_writer, bot.chat_writer = None, None
    bot.online_connected, bot.chat_connected = False, False
    
    bot.is_in_team, bot.team_chat_authed = False, False
    bot.current_chat_code, bot.current_chat_owner = None, None
    bot.is_spamming, bot.is_in_showcase = False, False
    bot.showcase_type, bot.showcase_task = None, None
    bot.is_blocking, bot.block_task = False, None
    bot.is_magic_mode, bot.emote_mood = False, None
    bot.is_locked, bot.suppress_auto_actions = False, False
    bot.last_joined_team_code, bot.status_requests = None, {}
    bot.last_look_change_ts, bot.team_uids = 0, []
    
    bot.last_invite_leader = None
    bot.last_invite_code = None
    bot.last_lobby_session_id = None 
    
    # 🟢 রুম সেশন স্টেট ভ্যারিয়েবল ইনিশিয়ালাইজেশন
    bot.room_id = None
    bot.room_secret_code = None
    bot.is_in_room = False
    
    bot.bot_name = f"Bot_{bot.my_uid}"
    
    bot.cached_ping_game, bot.is_joining = None, False
    bot.current_bundle_id, bot.saved_uids = None, []
    bot.lang = admin_manager.load_bot_lang(bot.my_uid)
    bot.chat_history, bot.ignored_users = {}, set()
    bot.last_counter_emote_time, bot.last_flex_time = 0, 0
    
    bot.custom_showcases, bot.loop_tasks = {}, {}
    bot.el_delay, bot.el_attempts = 10.0, 10
    bot.ef_delay, bot.ef_attempts = 10.0, 10
    
    if not hasattr(bot, 'emote_book') or not bot.emote_book:
        try:
            with open('config/emote_book.json', 'r', encoding='utf-8') as f: 
                bot.emote_book = json.load(f)
        except: bot.emote_book = {}

    auto_look_data = load_auto_look_config()
    bot.auto_look_enabled = auto_look_data.get(str(bot.my_uid), True)

async def initialize_bot_info(bot):
    print(f"[{bot.my_uid}] Automatically Fetching Bot Info via Local API...")
    try:
        data = await fetch_player_info(bot.my_uid)
        if data:
            basic_info = data.get('basic_info') or data.get('basicInfo') or {}
            if basic_info.get('nickname'): bot.bot_name = basic_info.get('nickname')
            clan_info = data.get('clan_basic_info') or data.get('clanBasicInfo') or {}
            clan_id = clan_info.get('clan_id') or clan_info.get('clanId')
            if clan_id: bot.guild_id = str(clan_id)
            else: print(f"[{bot.my_uid}] ⚠️ Bot is not in any guild.")
            
            await async_save_profile(bot.my_uid, data)
            
            try:
                DB_PATH = os.path.join('config', 'database.db')
                async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                    await db.execute("PRAGMA journal_mode=WAL;")
                    await db.execute("PRAGMA busy_timeout=30000;")
                    
                    await db.execute("UPDATE bots SET ingame_uid=? WHERE name=?", (str(bot.my_uid), bot.bot_display_name_from_manager))
                    await db.commit()
            except Exception as dberr: 
                print(f"[{bot.my_uid}] DB Update Error: {dberr}")
                
        admin_manager.init_bot(bot.my_uid, bot.bot_name, bot.guild_id)
        print(f"[{bot.my_uid}] Ready! Name: {bot.bot_name}")
        
    except Exception as e:
        print(f"[{bot.my_uid}] Info Init Error (Ignored): {e}")
        admin_manager.init_bot(bot.my_uid, bot.bot_name, bot.guild_id)