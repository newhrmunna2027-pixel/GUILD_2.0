# -*- coding: utf-8 -*-
# bot/packets/chat_packets.py - Central Chat Protocol Mapper (OB54 Patched)

import time
import random
from datetime import datetime
from Pb2 import DEcwHisPErMsG_pb2
from utils.helpers import xBunnEr, EnC_Uid
from bot.packets.base_handler import GeneRaTePk, CrEaTe_ProTo, DeCode_PackEt

async def DecodeWhisperMessage(hex_packet):
    """ ইনকামিং হুইসপার বা চ্যাট মেসেজ ডিকোড করার মূল ডিকোডার """
    try:
        packet = bytes.fromhex(hex_packet)
        proto = DEcwHisPErMsG_pb2.DecodeWhisper()
        proto.ParseFromString(packet)
        return proto
    except:
        return None

async def create_chat_message_packet(message, chat_info, key, iv):
    """ সকল চ্যাট টাইপের (Whisper, Squad, Guild, Room) মেসেজ জেনারেটর """
    chat_type = int(chat_info.get('chat_type', 0))
    uid = int(chat_info.get('uid', 0))          # মেসেজ টাইপ করা কমান্ডদাতার ইউআইডি
    chat_id = int(chat_info.get('chat_id', 0))  # টার্গেট ইউআইডি অথবা রুম আইডি
    bot_uid = int(chat_info.get('bot_uid', uid)) # বটের নিজের আসল ইউআইডি
    
    # গ্যারেনার ভুল ব্রডকাস্ট রুম আইডি এড়াতে ডাইনামিকালি ইনজেক্টেড রুম আইডি নেওয়া হচ্ছে
    room_id = int(chat_info.get('room_id', chat_id)) 

    # 🟢 ROOM CHAT MESSAGE GENERATOR (chat_type == 3) - NO "080112" ENVELOPE WRAPPER
    if chat_type == 3:
        fields = {
            1: 1, 
            2: {
                1: int(bot_uid), # বটের নিজের আসল ইউআইডি
                2: int(room_id), # মেমরি ও জেসন থেকে লোড হওয়া সঠিক রুম আইডি
                3: 3, # Room Chat Type
                4: str(message), 
                5: int(time.time()), 
                7: 6,
                9: {
                    1: "RIZER", 
                    2: random.choice([902048021, 901048020, 901048021, 902048022, 909000024]), 
                    4: 330, 
                    5: 909000024, 
                    7: 2, 
                    10: 1, 
                    11: 1, 
                    12: 0, 
                    13: {1: 2}, 
                    14: {
                        1: int(bot_uid), 
                        2: 8, 
                        3: b"\x10\x15\x08\n\x0b\x13\x0c\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"
                    }
                },
                10: "tr", 
                13: {3: 1}, 
                14: ""
            }
        }
        # 🟢 কাস্টম রুম চ্যাটের (120c) জন্য কোনো লবি হুইসপার মোড়ক বা হেডার ছাড়াই সরাসরি বাইনারি প্যাকেট পাঠানো হবে
        Pk = (await CrEaTo(fields) if 'CrEaTo' in globals() else await CrEaTe_ProTo(fields)).hex()
        return await GeneRaTePk(Pk, '120c', key, iv)

    # LOBBY TEAM CHAT 3D BUBBLE & REGION BANNER (chat_type == 0)
    if chat_type == 0:
        fields = {
            1: chat_id,       # Field 1 এ লিডারের আইডি (যার মাথার উপরে মেসেজ দেখাবে)
            2: chat_id,       # Field 2 তেও লিডারের আইডি
            4: str(message),  # আপনার পাঠানো মেসেজ
            5: 1756580149,    # ম্যাজিক টাইমস্ট্যাম্প
            8: 904990072,     # Title ID
            9: {
                1: "xBe4!sTo - C4", 
                2: int(await xBunnEr()), 
                4: 330, 
                5: 1001000001, 
                8: "xBe4!sTo - C4", 
                10: 1, 
                11: 1, 
                13: {1: 2}, 
                14: {
                    1: 1158053040, 
                    2: 8, 
                    3: b"\x10\x15\x08\x0A\x0B\x15\x0C\x0F\x11\x04\x07\x02\x03\x0D\x0E\x12\x01\x05\x06"
                }
            }, 
            10: "en", 
            13: {2: 2, 3: 1},
            
            # Weapon Glory Region Title (বড় ব্যানারের জন্য)
            14: {
                1: {
                    1: random.choice([1, 4]),          
                    2: 1,                              
                    3: random.randint(1, 180),         
                    4: 1,                              
                    5: int(datetime.now().timestamp()), 
                    6: "IND"
                }
            }
        }
        
        Pk = (await CrEaTo(fields) if 'CrEaTo' in globals() else await CrEaTe_ProTo(fields)).hex()
        Pk = "080112" + await EnC_Uid(len(Pk) // 2, 'Uid') + Pk
        return await GeneRaTePk(Pk, '1201', key, iv)

    # GUILD (1) or PRIVATE WHISPER (2) CHAT MESSAGE GENERATOR
    else:
        target_id = int(chat_id) if chat_type == 1 else int(uid)
        fields = {
            1: target_id, 
            2: target_id, 
            3: chat_type, 
            4: str(message), 
            5: int(time.time()), 
            7: 2,
            9: {
                1: "[FFFFFF]SychoBot", 
                2: int(await xBunnEr()), 
                3: 901048018, 
                4: 330, 
                5: 909034009, 
                8: "Sycho-Clan", 
                10: 1, 
                11: 1, 
                13: {1: 2}, 
                14: {1: 12484827014, 2: 8, 3: b"\x10\x15\x08\n\x0b\x13\x0c\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"}, 
                12: 0
            },
            10: "en",
            13: {3: 1}
        }
        Pk = (await CrEaTo(fields) if 'CrEaTo' in globals() else await CrEaTe_ProTo(fields)).hex()
        Pk = "080112" + await EnC_Uid(len(Pk) // 2, 'Uid') + Pk
        return await GeneRaTePk(Pk, '1201', key, iv)

async def AuthClan(CLan_Uid, AuTh, K, V):
    """ গিল্ড চ্যাট মেম্বারশিপ অথোরাইজার """
    if CLan_Uid is None:
        print("[AuthClan] Error: CLan_Uid is None. Cannot authenticate.")
        return None
    fields = {1: 3, 2: {1: int(CLan_Uid), 2: 1, 4: str(AuTh)}}
    return await GeneRaTePk((await CrEaTo(fields) if 'CrEaTo' in globals() else await CrEaTe_ProTo(fields)).hex(), '1201', K, V)

async def AuthTeam(Owner_Uid, AuTh_Code, K, V):
    """ লবি স্কোয়াড চ্যাট চ্যানেল অথোরাইজার """
    if Owner_Uid is None or AuTh_Code is None:
        print("[AuthTeam] Error: Owner_Uid or AuTh_Code is None. Cannot authenticate.")
        return None
    fields = {
        1: 3, 
        2: {
            1: int(Owner_Uid), 
            3: "en", 
            4: str(AuTh_Code)
        }
    }
    return await GeneRaTePk((await CrEaTo(fields) if 'CrEaTo' in globals() else await CrEaTe_ProTo(fields)).hex(), '1215', K, V)