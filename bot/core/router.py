# bot/core/router.py

import asyncio
from bot.packets import chat_packets
from bot.commands import handler as command_handler

async def listen_online(bot, reader):
    """গ্যারেনা অনলাইন গেটওয়ের মার্জড প্যাকেট (0500, 0e00, 0f00, 0400) আলাদা করার জন্য TCP Framing লুপ (5-byte Header ফিক্সড)"""
    from bot.core.handlers import handle_0f00_status, handle_0400_roster, handle_0500_events, handle_0e00_room_join
    try:
        while bot.online_connected:
            data = await reader.read(8192)
            if not data: 
                print(f"[{bot.bot_name}] Online Disconnected by Server (EOF)")
                break
            
            hex_data = data.hex()
            i = 0
            
            # গ্যারেনা অনলাইন গেটওয়ের ৫-বাইটের হেডার ডিটেকশন লুপ
            while i < len(hex_data):
                # অনলাইন পোর্টের ৫-বাইটের হেডার ডিটেকশন এবং ৩-বাইট (৬-ক্যারেক্টার) লেন্থ প্যারামিটার ডিটেকশন
                # 🟢 FIXED: Length Check ফিক্সড করে "00" করা হয়েছে (৬৫,৫৩৫ বাইট পর্যন্ত বড় কাস্টম রুম প্যাকেট রিড করতে সক্ষম)
                if (i + 10 <= len(hex_data) and 
                    hex_data[i:i+4] in ["0500", "0e00", "0400", "0f00"] and 
                    hex_data[i+4:i+6] == "00"):
                    
                    pid = hex_data[i:i+4]
                    length_hex = hex_data[i+4:i+10] # ৩-বাইট (৬-ক্যারেক্টার) লেন্থ এক্সট্রাক্টর
                    length = int(length_hex, 16)
                    
                    start_payload = i + 10
                    end_payload = start_payload + (length * 2)
                    
                    if end_payload <= len(hex_data):
                        full_packet_hex = hex_data[i:end_payload]
                        
                        try:
                            # 🟢 TERMINAL PRINT: রুম জয়েন প্যাকেট ডিটেক্ট করার লাইভ লগ
                            if pid == '0e00':
                                print(f"\n[{bot.bot_name}] [0e00 DETECTED] Garena Custom Room packet found! Total Length: {length} bytes.")
                            
                            if pid == '0f00':
                                await handle_0f00_status(bot, data[i // 2 : end_payload // 2])
                            elif pid == '0400':
                                await handle_0400_roster(bot, full_packet_hex)
                            elif pid == '0500':
                                await handle_0500_events(bot, full_packet_hex)
                            elif pid == '0e00':
                                await handle_0e00_room_join(bot, full_packet_hex)
                        except Exception as parse_err:
                            print(f"[{bot.bot_name}] ⚠️ Error routing pid {pid}: {parse_err}")
                            
                        i = end_payload
                    else:
                        break
                else:
                    i += 2
                        
    except Exception as e:
        print(f"[{bot.bot_name}] Online Listen Loop Error: {e}")
    finally:
        await bot._close_online_connection()

async def listen_chat(bot, reader):
    """গ্যারেনার স্ট্যান্ডার্ড ও কাস্টম চ্যাট (1201, 120c, 1200) রিড করার জন্য ডাইনামিক TCP Framing লুপ (5-byte Header ফিক্সড)"""
    try:
        while bot.chat_connected:
            data = await reader.read(8192)
            if not data: 
                print(f"[{bot.bot_name}] ❌ Chat Disconnected by Server (EOF)")
                break
            
            try:
                hex_data = data.hex()
                i = 0
                
                while i < len(hex_data):
                    # চ্যাট পোর্টের ৫-বাইটের হেডার ডিটেকশন এবং ৩-বাইট (৬-ক্যারেক্টার) লেন্থ প্যারামিটার ডিটেকশন
                    # 🟢 FIXED: Length Check ফিক্সড করে "00" করা হয়েছে (বড় আকারের মেসেজ বা কমান্ড রিড করতে সক্ষম)
                    if (i + 10 <= len(hex_data) and 
                        hex_data[i:i+2] == "12" and 
                        hex_data[i+4:i+6] == "00"):
                        
                        length_hex = hex_data[i+4:i+10]
                        length = int(length_hex, 16)
                        
                        start_payload = i + 10
                        end_payload = start_payload + (length * 2)
                        
                        if end_payload <= len(hex_data):
                            payload_hex = hex_data[start_payload:end_payload]
                            msg = await chat_packets.DecodeWhisperMessage(payload_hex)
                            
                            if msg and msg.Data and msg.Data.msg:
                                chat_type = msg.Data.chat_type
                                sender_uid = msg.Data.uid
                                msg_text = msg.Data.msg.strip()
                                
                                type_str = "Room Chat (Type 3)" if chat_type == 3 else "Squad/Lobby Chat (Type 0)" if chat_type == 0 else f"Private/Clan Chat (Type {chat_type})"
                                
                                print(f"[{bot.bot_name}] [📥 MSG RECEIVE] From: {sender_uid} | Message: '{msg_text}' | Type: {type_str}")
                                
                                ctx = {
                                    'uid': sender_uid, 
                                    'msg': msg_text, 
                                    'chat_type': chat_type, 
                                    'chat_id': msg.Data.Chat_ID
                                }
                                if ctx['chat_type'] == 1: 
                                    ctx['chat_id'] = bot.guild_id
                                    
                                if ctx['uid'] != bot.my_uid: 
                                    print(f"[{bot.bot_name}] [⚙️ PROCESSING] Routing command '{msg_text}' to handler...")
                                    asyncio.create_task(command_handler.handle_command(bot, ctx))
                                    
                            i = end_payload
                        else:
                            break
                    else:
                        i += 2
                            
            except Exception as parse_err:
                print(f"[{bot.bot_name}] ⚠️ Error parsing chat packet: {parse_err}")
                pass 
                    
    except Exception as e:
        print(f"[{bot.bot_name}] Chat Listen Error: {e}")
    finally:
        await bot._close_chat_connection()