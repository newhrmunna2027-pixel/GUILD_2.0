# filepath: bot/client.py
# bot/client.py

import asyncio
import traceback
from bot.core.bot_init import init_bot_state, initialize_bot_info
from bot.auth.orchestrator import perform_login
from bot.core.manager import (
    manage_chat_connection, 
    manage_online_connection, 
    heartbeat_loop, 
    guild_sync_loop,      # 🟢 Added import for background task
    send_online_packet, 
    send_chat_packet, 
    send_chat_message
)
from bot.core.logic import manage_team_file, execute_solo_logic

class GameBot:
    __slots__ = [
        'config', 'auth', 'server', 'key', 'iv', 'my_uid', 'region',
        'guild_id', 'guild_data', 'online_writer', 'chat_writer',
        'online_connected', 'chat_connected', 'is_in_team',
        'team_chat_authed', 'current_chat_code', 'current_chat_owner',
        'is_spamming', 'is_in_showcase', 'showcase_type', 'showcase_task',
        'is_blocking', 'block_task', 'is_magic_mode',
        'emote_mood', 'is_locked',
        'suppress_auto_actions', 'last_joined_team_code', 'status_requests',
        'last_look_change_ts', 'team_uids', 
        'bot_name', 
        'bot_display_name_from_manager', 
        'emote_book', 'auto_look_enabled', 'cached_ping_game', 'is_joining',
        'current_bundle_id', 'saved_uids',
        'chat_history', 'ignored_users', 
        'last_counter_emote_time', 'last_flex_time', 'lang',
        'is_running', 'online_retries', 
        'custom_showcases', 'loop_tasks', 'el_delay', 'el_attempts',
        'ef_delay', 'ef_attempts',
        'lx_burst_running',
        'force_reauth',
        'last_invite_leader',
        'last_invite_code',
        'last_lobby_session_id',
        'room_id', 'room_secret_code', 'is_in_room'
    ]

    def __init__(self, config, session_data, bot_display_name_from_manager: str):
        init_bot_state(self, config, session_data)
        self.bot_display_name_from_manager = bot_display_name_from_manager
        self.bot_name = bot_display_name_from_manager
        self.is_magic_mode = False
        self.emote_mood = None 
        self.is_locked = False 
        self.is_running = True
        self.online_retries = 0
        self.lx_burst_running = False 
        self.force_reauth = False

    async def stop(self):
        print(f"[{self.bot_name}] 🛑 Gracefully shutting down...")
        self.is_running = False 
        try:
            if getattr(self, 'is_in_team', False) and getattr(self, 'online_connected', False) and getattr(self, 'online_writer', None):
                from bot.packets import team_packets
                # 🟢 self.key and self.iv are used dynamically
                leave_pkt = await team_packets.create_leave_team_packet(self.my_uid, self.key, self.iv)
                self.online_writer.write(leave_pkt)
                await self.online_writer.drain()
        except: pass
        await self._close_online_connection()
        await self._close_chat_connection()

    async def connect(self):
        print(f"[*] Connecting {self.my_uid}...")
        await initialize_bot_info(self)
        
        while self.is_running:
            self.online_retries = 0
            self.force_reauth = False
            chat_task = asyncio.create_task(manage_chat_connection(self))
            online_task = asyncio.create_task(manage_online_connection(self))
            hb_task = asyncio.create_task(heartbeat_loop(self))
            guild_task = asyncio.create_task(guild_sync_loop(self))  # 🟢 Added task spawning
            
            try:
                await online_task 
            except asyncio.CancelledError: break
            except Exception as e:
                print(f"[{self.bot_name}] Main connection monitor error: {e}")
                
            if not self.is_running: break
            chat_task.cancel()
            hb_task.cancel()
            guild_task.cancel()  # 🟢 Added task canceling
            
            self.online_connected = False
            self.chat_connected = False
            
            print(f"[{self.bot_name}] 🔄 Online Disconnect Limit Reached! Fetching COMPLETELY FRESH login token...")
            await asyncio.sleep(2)
            
            try:
                new_session = await perform_login(self.config)
                if new_session:
                    self.auth = new_session['auth']
                    self.server = new_session['server']
                    self.key = self.auth.key
                    self.iv = self.auth.iv
                    print(f"[{self.bot_name}] ✅ Fresh login successful. Reconnecting to Game Servers...")
                else:
                    print(f"[{self.bot_name}] ❌ Fresh login failed. Rate limited. Retrying in 10s...")
                    for _ in range(10):
                        if not self.is_running: break
                        await asyncio.sleep(1)
            except Exception as e:
                print(f"[{self.bot_name}] ❌ Error during re-auth: {e}")
                for _ in range(5):
                    if not self.is_running: break
                    await asyncio.sleep(1)

    async def send_online_packet(self, packet): return await send_online_packet(self, packet)
    async def send_chat_packet(self, packet): return await send_chat_packet(self, packet)
    async def send_chat_message(self, msg, ctx): await send_chat_message(self, msg, ctx)
    async def manage_team_file(self, action, t_uid=None): await manage_team_file(self, action, t_uid)
    async def execute_solo_logic(self): await execute_solo_logic(self)

    async def _close_chat_connection(self):
        self.chat_connected = False
        if getattr(self, 'chat_writer', None):
            try:
                self.chat_writer.close()
                await self.chat_writer.wait_closed()
            except: pass
            self.chat_writer = None

    async def _close_online_connection(self):
        self.online_connected = False
        if getattr(self, 'online_writer', None):
            try:
                self.online_writer.close()
                await self.online_writer.wait_closed()
            except: pass
            self.online_writer = None