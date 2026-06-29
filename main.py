# filepath: main.py
# -*- coding: utf-8 -*-

import asyncio
import sys
import json
import os
import sqlite3

try:
    import uvloop
    if sys.platform != 'win32':
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from bot.auth.orchestrator import perform_login
from bot.client import GameBot
from utils.device_manager import get_or_create_device_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'config', 'database.db')

ACTIVE_BOT_INSTANCES = {}

async def stop_bot_instance(bot_name):
    bot = ACTIVE_BOT_INSTANCES.get(bot_name)
    if bot:
        await bot.stop()
        del ACTIVE_BOT_INSTANCES[bot_name]

def get_bot_credentials(bot_name):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        cursor.execute("SELECT login_uid, password FROM bots WHERE name=?", (bot_name,))
        row = cursor.fetchone()
        conn.close()
        if row: return {"account": {"uid": row[0], "password": row[1]}}
        return None
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None

async def run_bot(bot_name_from_manager, shared_emote_book=None, active_uid_map=None):
    if not bot_name_from_manager or str(bot_name_from_manager).strip().lower() in ['none', 'null', 'undefined', '']:
        print("[ERROR] Attempted to start a bot with an invalid or None name.")
        return

    config = {}
    bot_display_name = bot_name_from_manager 

    try:
        if bot_name_from_manager.endswith('.json') and os.path.exists(bot_name_from_manager):
            config = get_or_create_device_config(bot_name_from_manager)
            if not isinstance(config, dict): 
                with open(bot_name_from_manager, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            bot_display_name = os.path.basename(bot_name_from_manager).replace('.json', '') 
        else:
            loop = asyncio.get_event_loop()
            credentials = await loop.run_in_executor(None, get_bot_credentials, bot_name_from_manager)
            
            if not credentials:
                print(f"[ERROR] No credentials found for: {bot_name_from_manager}")
                return
                
            login_uid = credentials["account"]["uid"]
            device_config_path = os.path.join(BASE_DIR, 'config', 'devices', f"{login_uid}.json")
            old_device_config_path = os.path.join(BASE_DIR, 'config', 'devices', f"{bot_name_from_manager}.json")
            
            os.makedirs(os.path.dirname(device_config_path), exist_ok=True)
            
            if os.path.exists(old_device_config_path) and not os.path.exists(device_config_path):
                try:
                    os.rename(old_device_config_path, device_config_path)
                except Exception:
                    pass
            
            if not os.path.exists(device_config_path):
                with open(device_config_path, 'w', encoding='utf-8') as f: json.dump({}, f)
                    
            config = get_or_create_device_config(device_config_path)
            if not isinstance(config, dict): config = {}
            config.update(credentials)

        print(f"[*] Starting Auth for {bot_display_name}...")
        
        session = await perform_login(config)
        if not session:
            print(f"[FAIL] Login failed for {bot_display_name}. Rate Limited or Bad Pass.")
            return

        try:
            import bot_core
            jwt_token = None
            auth_obj = session.get('auth') if isinstance(session, dict) else getattr(session, 'auth', None)
            
            if auth_obj:
                for attr in ['access_token', 'token', 'jwt', 'jwt_token', '_token']:
                    val = getattr(auth_obj, attr, None) or (auth_obj.get(attr) if isinstance(auth_obj, dict) else None)
                    if val and isinstance(val, str) and len(val) > 50:
                        jwt_token = val
                        break
            
            if jwt_token:
                bot_core.save_session({
                    "uid": str(config["account"]["uid"]),
                    "password": config["account"]["password"],
                    "token": jwt_token
                }, bot_display_name)
                print(f"[✓] {bot_display_name} JWT Token successfully written to session JSON by main.py")
        except Exception as t_err:
            print(f"[!] Warning: Failed to cache JWT in main.py: {t_err}")

        if active_uid_map is not None:
            active_uid_map[bot_display_name] = str(session['auth'].account_uid) 

        bot = GameBot(config, session, bot_display_name) 
        if shared_emote_book is not None:
            bot.emote_book = shared_emote_book
            
        ACTIVE_BOT_INSTANCES[bot_display_name] = bot
            
        print(f"[SUCCESS] {bot_display_name} Authenticated! Starting connection...")
        await bot.connect() 
        
    except asyncio.CancelledError:
        print(f"[STOPPED] Bot {bot_display_name} has been cancelled.")
        raise 
    except Exception as e:
        print(f"[ERROR] {bot_display_name} Fatal Exception: {e}")
        raise
    finally:
        if bot_display_name in ACTIVE_BOT_INSTANCES:
            del ACTIVE_BOT_INSTANCES[bot_display_name]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <bot_name_or_temp_json_path>")
        sys.exit()
    arg_input = sys.argv[1]
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(run_bot(arg_input))
    except KeyboardInterrupt:
        print("\n[STOP] Bot stopped by user.")
