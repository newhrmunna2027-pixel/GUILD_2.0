# bot/packets/team_packets.py

import random
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from bot.packets.base_handler import GeneRaTePk, CrEaTe_ProTo, DEc_PacKeT, EnC_PacKeT, DecodE_HeX
from utils.helpers import xBunnEr

def Encrypt_Varint(number):
    number = int(number)
    encoded_bytes = []
    while True:
        byte = number & 0x7F
        number >>= 7
        if number:
            byte |= 0x80
        encoded_bytes.append(byte)
        if not number:
            break
    return bytes(encoded_bytes).hex()

def dec_to_hex(decimal):
    hex_str = hex(decimal)[2:]
    return hex_str.upper() if len(hex_str) % 2 == 0 else '0' + hex_str.upper()

async def encrypt_packet_manual(packet_hex, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    packet_bytes = bytes.fromhex(packet_hex)
    padded_packet = pad(packet_bytes, AES.block_size)
    encrypted = cipher.encrypt(padded_packet)
    return encrypted.hex()

async def create_status_check_packet(target_uid, key, iv):
    try:
        ida = Encrypt_Varint(target_uid)
        packet = f"080112090A05{ida}1005"
        encrypted_packet_hex = await encrypt_packet_manual(packet, key, iv)
        header_lenth = len(encrypted_packet_hex) // 2
        header_lenth_final = dec_to_hex(header_lenth)
        
        final_packet = ""
        if len(header_lenth_final) == 2: 
            final_packet = "0F15000000" + header_lenth_final + encrypted_packet_hex
        elif len(header_lenth_final) == 3: 
            final_packet = "0F1500000" + header_lenth_final + encrypted_packet_hex
        elif len(header_lenth_final) == 4: 
            final_packet = "0F150000" + header_lenth_final + encrypted_packet_hex
        else: 
            final_packet = "0F15000" + header_lenth_final + encrypted_packet_hex
            
        return bytes.fromhex(final_packet)
    except Exception as e: 
        print(f"[Status Packet Error] {e}")
        return None

async def create_team_packet(size, uid, key, iv, region, mode_id=62):
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    fields_open = {1: 1, 2: {2: "\u0001", 3: 1, 4: 1, 5: "en", 9: 1, 11: 1, 13: 1, 14: {2: 5756, 6: 11, 8: "1.126.1", 9: 2, 10: 4}}}
    open_sq_packet = await GeneRaTePk((await CrEaTe_ProTo(fields_open)).hex(), packet_id, key, iv)
    fields_change = {1: 17, 2: {1: int(uid), 2: 1, 3: int(size - 1), 4: 62, 5: "\u001a", 8: 5, 13: 329}}
    change_sq_packet = await GeneRaTePk((await CrEaTe_ProTo(fields_change)).hex(), packet_id, key, iv)
    return [open_sq_packet, change_sq_packet]

async def create_invite_packet(target_uid, team_size, key, iv, region):
    fields = {1: 2, 2: {1: int(target_uid), 2: region, 4: int(team_size), 9: {3: "DR Sycho", 11: 901048018, 12: await xBunnEr(), 14: 330, 49: {2: 8}}}}
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet_id, key, iv)

async def create_join_by_code_packet(team_code, key, iv):
    # 🟢 OB54 FULL MAPS (Bermuda, Purgatory, Kalahari, Alpine, NeXTerra, Craftland etc.) ইনজেক্ট করা হলো
    fields = {1: 4, 2: {4: bytes.fromhex("0107090a0b12191a20"), 5: str(team_code), 6: 6, 8: 1, 9: {2: 800, 6: 11, 8: "1.126.1", 9: 5, 10: 1}}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)

async def create_leave_team_packet(uid, key, iv):
    fields = {1: 7, 2: {1: uid}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)

async def create_emote_packet(sender_uid, target_uid, emote_id, key, iv, region):
    fields = {1: 21, 2: {1: 804266360, 2: 909000001, 5: {1: int(target_uid), 3: int(emote_id)}}}
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet_id, key, iv)

async def create_bundle_packet(bundle_id, key, iv, region):
    fields = {1: 88, 2: {1: {1: int(bundle_id), 2: 1}, 2: 2}}
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet_id, key, iv)

async def decode_team_update_packet(hex_data, key, iv):
    decrypted_hex = await DEc_PacKeT(hex_data, key, iv)
    if not decrypted_hex: return []
    players = []
    try:
        i = 0
        while i < len(decrypted_hex) - 2:
            if decrypted_hex[i:i+2] == '08':
                i += 2
                uid = 0; shift = 0
                while True:
                    if i + 2 > len(decrypted_hex): break
                    byte_val = int(decrypted_hex[i:i+2], 16)
                    i += 2
                    uid |= (byte_val & 0x7F) << shift
                    if not (byte_val & 0x80): break
                    shift += 7
                if uid > 100000: players.append({'uid': uid})
            else: i += 2
    except: pass
    return players

async def create_accept_invite_packet(sender_uid, invite_code, key, iv, region):
    fields = {
        1: 4, 
        2: {
            1: int(sender_uid), 
            3: int(sender_uid), 
            8: 1, 
            9: {2: 161, 4: "y[WW", 6: 11, 8: "1.126.1", 9: 3, 10: 1}, 
            10: str(invite_code)
        }
    }
    
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
        
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet_id, key, iv)
    
async def create_transfer_leader_packet(target_uid, key, iv, region):
    fields = {1: 3, 2: {1: int(target_uid)}}
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet_id, key, iv)

async def create_ready_packet(bot_uid, key, iv, region):
    fields = {1: 15, 2: {1: int(bot_uid)}}
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet_id, key, iv)

async def animation_packet(bundle_id, key, iv):
    fields = {
        1: 88,
        2: {
            1: {
                1: int(bundle_id),
            }
        }
    }

    proto_bytes = await CrEaTe_ProTo(fields)
    packet_hex = proto_bytes.hex()

    encrypted_packet = await EnC_PacKeT(packet_hex, key, iv)

    packet_length = len(encrypted_packet) // 2
    packet_length_hex = await DecodE_HeX(packet_length)

    if len(packet_length_hex) == 2:
        header = "0515000000"
    elif len(packet_length_hex) == 3:
        header = "051500000"
    elif len(packet_length_hex) == 4:
        header = "05150000"
    elif len(packet_length_hex) == 5:
        header = "0515000"
    else:
        header = "0515000000"

    final_packet = header + packet_length_hex + encrypted_packet

    return bytes.fromhex(final_packet)

async def ghost_packet(bot_uid, leader_uid, secret_code, key, iv, region):
    fields = {
        1: int(bot_uid), 
        2: {
            1: int(leader_uid), 
            2: 1159,
            3: f"[B][C][FF0000]OUT OF LAW",
            5: 12,
            6: 15,
            7: 1,
            8: {2: 1, 3: 1},
            9: 1,
        },
        3: str(secret_code), 
    }
    proto_hex = (await CrEaTe_ProTo(fields)).hex()
    if region.lower() == "ind":
        pkt_type = "0514"
    elif region.lower() == "bd":
        pkt_type = "0519"
    else:
        pkt_type = "0515"
    return await GeneRaTePk(proto_hex, pkt_type, key, iv)

async def create_change_team_size_packet(size, uid, key, iv, region):
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    fields_change = {1: 17, 2: {1: int(uid), 2: 1, 3: int(size - 1), 4: 62, 5: "\u001a", 8: 5, 13: 329}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields_change)).hex(), packet_id, key, iv)

async def create_transfer_flag_packet(bot_uid, old_leader_uid, key, iv, region):
    fields = {
        1: 57,  
        2: {
            1: int(bot_uid),
            2: int(old_leader_uid)
        }
    }
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet_id, key, iv)

# OB54 GAME SERVER KEEP-ALIVE GENERATOR (Action 99)
async def create_keep_alive_packet(key, iv, region):
    """গেম সার্ভারের আসল কীপ-অ্যালাইভ (Action 99) প্যাকেট জেনারেটর"""
    import time
    fields_keep = {1: 99, 2: {1: int(time.time()), 2: 1}}
    proto_hex = (await CrEaTe_ProTo(fields_keep)).hex()
    
    packet_id = "0515"
    if region:
        if region.lower() == "bd": packet_id = "0519"
        elif region.lower() == "ind": packet_id = "0514"
        
    return await GeneRaTePk(proto_hex, packet_id, key, iv)

# 🟢 PHYSICAL CUSTOM ROOM JOIN (0E15 - Action 3)
async def physical_room_join(room_id, password, key, iv):
    """কাস্টম রুমে ফিজিক্যালি জয়েন করার প্যাকেট জেনারেটর"""
    fields = {
        1: 3, 
        2: {
            1: int(room_id), 
            2: str(password),
            8: {1: "IDC3", 2: 149, 3: "IND"},
            9: b"\x01\x03\x04\x07\x09\x0a\x0b\x12\x0e\x16\x19\x20\x1d",
            10: 1, 12: {}, 13: 1, 14: 1, 16: "en", 22: {1: 21}
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0e15', key, iv)

# 🟢 PHYSICAL CUSTOM ROOM LEAVE (0E15 - Action 6)
async def physical_room_leave(room_id, key, iv):
    """কাস্টম রুম থেকে ফিজিক্যালি বের হওয়ার প্যাকেট জেনারেটর"""
    fields = {
        1: 6,
        2: {
            1: int(room_id)
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0e15', key, iv)

# 🟢 LOBBY ROOM CHAT AUTHENTICATE SEQUENCE (120C - Action 3)
async def lobby_room_chat_join(room_id, secret_code, key, iv):
    """রুমের চ্যাট চ্যানেলে প্রথম সিক্রেট কোড দিয়ে সেশন অথোরাইজ করার প্যাকেট"""
    fields = {
        1: 3, 
        2: {
            1: int(room_id), 
            2: 3, 
            3: "tr", 
            4: str(secret_code)
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '120c', key, iv)

# 🟢 ACTIVE ROOM CHAT PORT BIND (120C - Action 1)
async def chat_room_join(room_id, bot_uid, key, iv):
    """রুম চ্যাটের পোর্ট বাইন্ডিং ও একটিভ সেশন তৈরির প্রোটোকল প্যাকেট"""
    fields = {
        1: 1, 
        2: {
            1: int(bot_uid), 
            2: int(room_id), 
            3: 3, # Chat Type: 3 (Room Chat)
            4: "", 
            5: int(time.time()), 
            7: 6,
            9: {
                1: "RIZER", 
                2: random.choice([902048021, 901048020, 901048021, 902048022, 909000024]), 
                4: 330, 
                5: 909000024, 
                7: 2, 
                10: 1, 11: 1, 12: 0, 13: {1: 2}, 
                14: {1: int(bot_uid), 2: 8, 3: b"\x10\x15\x08\n\x0b\x13\x0c\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"}
            },
            10: "tr", 
            13: {3: 1}, 
            14: ""
        }
    }
    return await GeneRaTePk((await CrEaTo(fields) if 'CrEaTo' in globals() else await CrEaTe_ProTo(fields)).hex(), '120c', key, iv)

# 🟢 SEND CAPTURED ROOM MESSAGE (120C - Type 3)
async def send_captured_room_msg(Msg, room_id, key, iv):
    """রুম চ্যাটের টাইপ ৩ ব্যবহার করে চ্যাট গেটওয়ে ১২০সি-তে সরাসরি মেসেজ পাঠানোর জেনারেটর"""
    chat_msg_payload = {
        1: 1, 
        2: {
            1: 11825435633, # Static bot placeholder fallback UID
            2: int(room_id), 
            3: 3, # Chat Type: 3 (Room Chat)
            4: str(Msg), 
            5: int(time.time()), 
            7: 6,
            9: {
                1: "RIZER", 
                2: random.choice([902048021, 901048020, 901048021, 902048022, 909000024]), 
                4: 330, 
                5: 909000024, 
                7: 2, 
                10: 1, 11: 1, 12: 0, 13: {1: 2}, 
                14: {1: 11825435633, 2: 8, 3: b"\x10\x15\x08\n\x0b\x13\x0c\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"}
            },
            10: "tr", 
            13: {3: 1}, 
            14: ""
        }
    }
    return await GeneRaTePk((await CrEaTo(chat_msg_payload) if 'CrEaTo' in globals() else await CrEaTe_ProTo(chat_msg_payload)).hex(), '120c', key, iv)