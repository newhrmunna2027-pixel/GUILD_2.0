# -*- coding: utf-8 -*-
# bot_manager.py - Unified Garena Command Hub & Dual-App Web Panel Core (OB54 Synced)

import os
import sys
import io
import subprocess
import asyncio
import json
import sqlite3
import re
import shutil
from datetime import datetime, timedelta
import threading

# 🟢 Superfast CPU Event Loop (Linux Only)
try:
    import uvloop
    if sys.platform != 'win32':
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

import mongo_sync
from main import run_bot, stop_bot_instance 
from app import app as flask_web_app

if sys.platform == 'win32':
    if sys.stdout: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr: sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'config', 'database.db')
PYTHON_EXECUTABLE = sys.executable or "python3"
HOST = '127.0.0.1'  
PORT = 50000     

active_tasks = {}
disabled_bots = set()
bot_ingame_uids = {}  
law_process = None 
ping_process = None  # 🟢 ping.py প্রসেস ট্র্যাকিংয়ের গ্লোবাল ভ্যারিয়েবল
shared_emotes = {}

is_resting = False
start_time = datetime.now()

def get_ts(): 
    return datetime.now().strftime('%H:%M:%S')

def get_all_bots_from_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM bots WHERE name IS NOT NULL AND name != '' AND name != 'null' AND name != 'undefined'")
        bots = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("DELETE FROM bots WHERE name IS NULL OR name = '' OR name = 'null' OR name = 'undefined'")
        conn.commit()
        conn.close()
        return bots
    except Exception as e:
        print(f"[{get_ts()}] [DB ERROR] Failed to get bots from DB: {e}")
        return []

async def start_bot_task(bot_name):
    if not bot_name or is_resting or bot_name in active_tasks or bot_name in disabled_bots: 
        return
    
    print(f"[{get_ts()}] [MANAGER] Starting Async Task for {bot_name}...")
    task = asyncio.create_task(run_bot(bot_name, shared_emotes, bot_ingame_uids))
    
    def task_done_callback(t, name=bot_name):
        if name in active_tasks: 
            del active_tasks[name]
        if name in bot_ingame_uids: 
            del bot_ingame_uids[name]
        try:
            exc = t.exception()
            if exc: 
                print(f"[{get_ts()}] [CRASH] Bot {name} disconnected: {exc}")
        except asyncio.CancelledError: 
            pass 
        
    task.add_done_callback(task_done_callback)
    active_tasks[bot_name] = task

async def stop_bot_task(bot_name):
    if bot_name in active_tasks:
        print(f"[{get_ts()}] [MANAGER] Stopping Async Task for {bot_name}...")
        await stop_bot_instance(bot_name)
        await asyncio.sleep(0.5) 
        active_tasks[bot_name].cancel() 

async def stop_all_bots():
    print(f"[{get_ts()}] [SYSTEM] Stopping all bots...")
    for name, task in list(active_tasks.items()): 
        await stop_bot_instance(name)
        await asyncio.sleep(0.1)
        task.cancel()

async def handle_client_command(reader, writer):
    global law_process, ping_process
    try:
        data = await reader.read(4096)
        if not data: return
        message = json.loads(data.decode('utf-8', errors='replace'))
        command = message.get('command')
        target = message.get('target') 

        if command == "hard_restart":
            writer.write(json.dumps({"status": "success", "msg": "Hard Restart Initiated"}).encode('utf-8'))
            await writer.drain()
            writer.close()
            
            print(f"[{get_ts()}] [SYSTEM] Hard Restart Triggered. Cleaning up all child processes...")
            await stop_all_bots() 
            
            if law_process:
                try: law_process.terminate()
                except: pass

            if ping_process:
                try: ping_process.terminate()
                except: pass
            
            os._exit(1) 

        response = {"status": "success"}
        
        if command == "status":
            bot_status = {}
            for bot_name_from_db in get_all_bots_from_db(): 
                state = "OFF"
                if bot_name_from_db not in disabled_bots:
                    state = "ON" if bot_name_from_db in active_tasks else "OFF"
                bot_status[bot_name_from_db] = {"state": state, "ingame_uid": bot_ingame_uids.get(bot_name_from_db)}
            response['data'] = bot_status
        
        elif command == "stop":
            targets = get_all_bots_from_db() if target == "all" else [target]
            for t_name in targets:
                if t_name: 
                    disabled_bots.add(t_name) 
                    await stop_bot_task(t_name) 
        
        elif command == "start":
            targets = get_all_bots_from_db() if target == "all" else [target]
            for t_name in targets:
                if t_name: 
                    if t_name in disabled_bots: 
                        disabled_bots.remove(t_name) 
                    if t_name not in active_tasks:
                        await start_bot_task(t_name)
                        # 🟢 FIX: বটগুলো এক সাথে স্টার্ট না হয়ে ২ সেকেন্ড গ্যাপে স্টার্ট হবে
                        await asyncio.sleep(2.0)
        
        elif command == "restart":
            targets = get_all_bots_from_db() if target == "all" else [target]
            for t_name in targets:
                if t_name: 
                    if t_name in disabled_bots: 
                        disabled_bots.remove(t_name)
                    await stop_bot_task(t_name) 
            await asyncio.sleep(2)
            
            for t_name in targets:
                if t_name:
                    await start_bot_task(t_name)
                    # 🟢 FIX: রিস্টার্টের সময়ও ২ সেকেন্ড গ্যাপে স্টার্ট হবে
                    await asyncio.sleep(2.0)
        
        elif command == "delete":
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bots WHERE name=?", (target,))
            cursor.execute("DELETE FROM admins WHERE bot_name=?", (target,))
            conn.commit()
            conn.close()

            if target in active_tasks: await stop_bot_task(target)
            if target in disabled_bots: disabled_bots.remove(target)

            response = {"status": "success", "msg": f"Bot '{target}' deleted and perfectly stopped."}

        writer.write(json.dumps(response).encode('utf-8'))
        await writer.drain()
    except Exception as e: 
        try:
            writer.write(json.dumps({"status": "error", "msg": str(e)}).encode('utf-8'))
            await writer.drain()
        except: pass
    finally: 
        writer.close()

def run_flask_app(app, host, port):
    try:
        app.run(host=host, port=port, debug=False)
    except Exception as e:
        print(f"Failed to run Flask app on {host}:{port}. Error: {e}")

def start_external_servers():
    global law_process, ping_process
    print(f"[{get_ts()}] [SERVER] Starting Web Panel, Law, and Ping servers...")
    
    web_thread = threading.Thread(target=run_flask_app, args=(flask_web_app, '0.0.0.0', int(os.environ.get("PORT", 20881))), daemon=True)
    web_thread.start()
    
    try: 
        law_process = subprocess.Popen([PYTHON_EXECUTABLE, "-u", "law.py"], cwd=BASE_DIR)
    except Exception as e: 
        print(f"Failed to start law.py: {e}")

    try: 
        ping_process = subprocess.Popen([PYTHON_EXECUTABLE, "-u", "ping.py"], cwd=BASE_DIR)
        print(f"[{get_ts()}] [SERVER] ping.py started successfully.")
    except Exception as e: 
        print(f"Failed to start ping.py: {e}")

async def cleanup_cache_folders():
    try:
        count = 0
        for root, dirs, files in os.walk(BASE_DIR):
            if '__pycache__' in dirs: 
                shutil.rmtree(os.path.join(root, '__pycache__'))
                count += 1
        cache_dir = os.path.join(BASE_DIR, '.cache')
        if os.path.exists(cache_dir): 
            shutil.rmtree(cache_dir)
            count += 1
        if count > 0:
            print(f"[{get_ts()}] [SYSTEM] Instant Cache Cleanup Done.")
    except Exception as e: pass

    while True:
        await asyncio.sleep(3600)
        try:
            for root, dirs, files in os.walk(BASE_DIR):
                if '__pycache__' in dirs: shutil.rmtree(os.path.join(root, '__pycache__'))
            cache_dir = os.path.join(BASE_DIR, '.cache')
            if os.path.exists(cache_dir): shutil.rmtree(cache_dir)
        except Exception as e: pass

async def maintenance_loop():
    global start_time, is_resting, law_process, ping_process
    loop = asyncio.get_event_loop()
    while True:
        try:
            now = datetime.now()
            if now - start_time >= timedelta(hours=4):
                is_resting = True
                print(f"[{get_ts()}] [SYSTEM] 4 Hours Reached. Shutting down for 10 min rest...")
                await stop_all_bots()
                if law_process:
                    try: law_process.terminate()
                    except: pass
                if ping_process:
                    try: ping_process.terminate()
                    except: pass
                os._exit(2) 

            if not is_resting:
                db_bots = await loop.run_in_executor(None, get_all_bots_from_db) 
                currently_running_names = set(active_tasks.keys())
                
                for db_bot_name in db_bots:
                    if db_bot_name not in disabled_bots and db_bot_name not in active_tasks:
                        await start_bot_task(db_bot_name)
                        # 🟢 FIX: লুপের মাধ্যমে নতুন বট অটো স্টার্ট হলে ২ সেকেন্ড গ্যাপ নিবে
                        await asyncio.sleep(2.0)
                
                for running_bot_name in list(currently_running_names): 
                    if running_bot_name not in db_bots or active_tasks[running_bot_name].done():
                        await stop_bot_task(running_bot_name) 

        except Exception as e:
            print(f"[{get_ts()}] [MANAGEMENT LOOP ERROR] {e}")
        await asyncio.sleep(30) 

async def main():
    global shared_emotes
    print(f"[{get_ts()}] [SYSTEM] Initializing Data from Mongo...")
    
    asyncio.create_task(cleanup_cache_folders())
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, mongo_sync.init_sqlite)
    await loop.run_in_executor(None, mongo_sync.pull_all_from_mongo)
    await loop.run_in_executor(None, mongo_sync.start_change_stream)
    
    try:
        with open('config/emote_book.json', 'r', encoding='utf-8') as f: shared_emotes = json.load(f)
    except: shared_emotes = {}

    start_external_servers()
    
    await asyncio.sleep(1) 
    
    server = await asyncio.start_server(handle_client_command, HOST, PORT)
    async with server: 
        await asyncio.gather(server.serve_forever(), maintenance_loop())

if __name__ == "__main__":
    try:
        if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        for _, task in active_tasks.items(): task.cancel()
        if law_process: law_process.terminate()
        if ping_process: ping_process.terminate()
