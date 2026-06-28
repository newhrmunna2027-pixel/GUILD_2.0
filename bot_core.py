# -*- coding: utf-8 -*-
# bot_core.py - Garena Low-Level Cryptography, Protobuf Mappers & Constants

import os
import jwt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ==========================================
# CONSTANTS & CONFIGURATIONS
# ==========================================
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

DEV = {
    "os": "Android OS 13 / API-33",
    "os_ver_only": "Android 13",
    "operator": "Banglalink",
    "width": 1440,
    "height": 3216,
    "dpi": "520",
    "cpu_long": "Qualcomm Snapdragon 888 | 8 cores",
    "ram": 12288,
    "gpu": "Adreno (TM) 660",
    "opengl": "OpenGL ES 3.2 V@512.0"
}

BASE_URLS = {
    "IND": "https://client.ind.freefiremobile.com/",
    "ID": "https://clientbp.ggpolarbear.com/",
    "BR": "https://client.us.freefiremobile.com/",
    "ME": "https://clientbp.ggpolarbear.com/",
    "VN": "https://clientbp.ggpolarbear.com/",
    "TH": "https://clientbp.ggpolarbear.com/",
    "CIS": "https://clientbp.ggpolarbear.com/",
    "BD": "https://clientbp.ggpolarbear.com/",
    "PK": "https://clientbp.ggpolarbear.com/",
    "SG": "https://clientbp.ggpolarbear.com/",
    "SAC": "https://client.us.freefiremobile.com/",
    "TW": "https://clientbp.ggpolarbear.com/",
    "US": "https://client.na.freefiremobile.com/",
    "NA": "https://client.na.freefiremobile.com/"
}

DEC_LIST = ['80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '8a', '8b', '8c', '8d', '8e', '8f', '90', '91', '92', '93', '94', '95', '96', '97', '98', '99', '9a', '9b', '9c', '9d', '9e', '9f', 'a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9', 'aa', 'ab', 'ac', 'ad', 'ae', 'af', 'b0', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8', 'b9', 'ba', 'bb', 'bc', 'bd', 'be', 'bf', 'c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9', 'ca', 'cb', 'cc', 'cd', 'ce', 'cf', 'd0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8', 'd9', 'da', 'db', 'dc', 'dd', 'de', 'df', 'e0', 'e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8', 'e9', 'ea', 'eb', 'ec', 'ed', 'ee', 'ef', 'f0', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'fa', 'fb', 'fc', 'fd', 'fe', 'ff']
XXX_LIST = ['1','01', '02', '03', '04', '05', '06', '07', '08', '09', '0a', '0b', '0c', '0d', '0e', '0f', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '1a', '1b', '1c', '1d', '1e', '1f', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '2a', '2b', '2c', '2d', '2e', '2f', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '3a', '3b', '3c', '3d', '3e', '3f', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '4a', '4b', '4c', '4d', '4e', '4f', '50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '5a', '5b', '5c', '5d', '5e', '5f', '60', '61', '62', '63', '64', '65', '66', '67', '68', '69', '6a', '6b', '6c', '6d', '6e', '6f', '70', '71', '72', '73', '74', '75', '76', '77', '78', '79', '7a', '7b', '7c', '7d', '7e', '7f']

TAG_MAPPINGS = {
    "Player": {
        1: "account_uid", 3: "nickname", 5: "region", 6: "level", 7: "experience",
        11: "banner_id", 12: "head_pic_id", 14: "br_rank", 15: "ranking_points",
        18: "badge_count", 21: "likes", 24: "last_login_ts", 29: "guild_name", 
        41: "guild_metadata", 44: "create_ts", 63: "guild_id"
    },
    "Friend": {
        1: "account_uid", 2: "role_status", 3: "nickname", 6: "region", 8: "level",       
        9: "experience", 29: "guild_name", 57: "game_version", 63: "guild_id"
    },
    "Guild": {
        1: "clan_id", 2: "clan_name", 3: "created_at_ts", 4: "leader_uid", 5: "level", 
        6: "max_members", 7: "total_members", 12: "welcome_message", 13: "region", 
        15: "officers_list", 16: "past_glory", 23: "acting_leader_uid",
        36: "total_glory", 37: "recent_glory"
    },
    "Duo": {
        1: "partner_uid", 3: "score", 4: "formed_on_ts", 5: "active_days", 6: "status_code"
    }
}

# ==========================================
# CORE ENCRYPTION / DECRYPTION
# ==========================================
def E_AEs(pc):
    Z = bytes.fromhex(pc)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(Z, AES.block_size))

def encrypt_message(data_bytes):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(data_bytes, AES.block_size))

def encrypt_message_hex(data_bytes):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    encrypted = cipher.encrypt(pad(data_bytes, AES.block_size))
    return encrypted.hex()

def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
    return cipher_text.hex()

def YOuR_FaThER(uid):
    n = int(uid)
    res = bytearray()
    while n >= 0x80:
        res.append((n & 0x7f) | 0x80)
        n >>= 7
    res.append(n)
    payload_bytes = b"\x08" + bytes(res)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(payload_bytes, 16))

def UNknown(d):
    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        return unpad(cipher.decrypt(d), 16)
    except:
        return d

# ==========================================
# PROTOBUF ENCODING / DECODING
# ==========================================
def enc_vr_sync(N):
    if N < 0: return b''
    H = []
    while True:
        byte = N & 0x7F
        N >>= 7
        if N: byte |= 0x80
        H.append(byte)
        if not N: break
    return bytes(H)

def create_variant_sync(field_number, value):
    return enc_vr_sync((field_number << 3) | 0) + enc_vr_sync(value)

def create_length_sync(field_number, value):
    encoded_value = value.encode('utf-8') if isinstance(value, str) else bytes(value)
    return enc_vr_sync((field_number << 3) | 2) + enc_vr_sync(len(encoded_value)) + encoded_value

def create_proto_sync(fields):
    packet = bytearray()
    for field in sorted(fields.keys()):
        value = fields[field]
        if isinstance(value, dict):
            nested = create_proto_sync(value)
            packet.extend(create_length_sync(field, nested))
        elif isinstance(value, int):
            packet.extend(create_variant_sync(field, value))
        elif isinstance(value, str) or isinstance(value, bytes):
            packet.extend(create_length_sync(field, value))
    return bytes(packet)

def decode_varint(buf, pos):
    result = 0
    shift = 0
    while pos < len(buf):
        byte = buf[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not (byte & 0x80): break
        shift += 7
    return result, pos

def parse_proto_bytes(data: bytes):
    result = {}
    pos = 0
    while pos < len(data):
        try:
            tag, pos = decode_varint(data, pos)
        except IndexError: break
        
        field_number = tag >> 3
        wire_type = tag & 0x07
        
        val = None
        if wire_type == 0:
            val, pos = decode_varint(data, pos)
        elif wire_type == 1:
            val = int.from_bytes(data[pos:pos+8], 'little')
            pos += 8
        elif wire_type == 2:
            length, pos = decode_varint(data, pos)
            val = data[pos:pos+length]
            pos += length
        elif wire_type == 5:
            val = int.from_bytes(data[pos:pos+4], 'little')
            pos += 4
        else:
            break
            
        if val is not None:
            if field_number in result:
                if isinstance(result[field_number], list):
                    result[field_number].append(val)
                else:
                    result[field_number] = [result[field_number], val]
            else:
                result[field_number] = val
    return result

# ==========================================
# DATA FORMATTING & MAPPING HELPERS
# ==========================================
def map_proto_to_named(parsed_dict, schema_type):
    mapping = TAG_MAPPINGS.get(schema_type, {})
    named_dict = {}
    if not isinstance(parsed_dict, dict):
        return parsed_dict
        
    for k, v in parsed_dict.items():
        try:
            tag_num = int(k)
            field_name = mapping.get(tag_num, f"tag_{tag_num}")
            if isinstance(v, dict):
                named_dict[field_name] = map_proto_to_named(v, schema_type)
            elif isinstance(v, list):
                named_dict[field_name] = [map_proto_to_named(item, schema_type) if isinstance(item, dict) else item for item in v]
            else:
                named_dict[field_name] = v
        except:
            named_dict[str(k)] = v
    return named_dict

def safe_get_bytes(val):
    if not val: return None
    if isinstance(val, list):
        for item in val:
            if isinstance(item, bytes): return item
    if isinstance(val, bytes): return val
    return None

def decode_field_str(val):
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='ignore')
    if isinstance(val, list) and len(val) > 0:
        first = val[0]
        return first.decode('utf-8', errors='ignore') if isinstance(first, bytes) else str(first)
    return str(val) if val is not None else ""

def decode_field_int(val, default=0):
    if isinstance(val, int): return val
    if isinstance(val, list) and len(val) > 0:
        first = val[0]
        try: return int(first)
        except: return default
    try: return int(val)
    except: return default

def is_printable_text(b):
    try:
        if len(b) < 150:
            decoded = b.decode('utf-8')
            printable_count = sum(1 for c in decoded if c.isprintable() or c in "\r\n\t")
            if printable_count / len(decoded) > 0.75: return True
    except: pass
    return False

def make_serializable(d):
    if isinstance(d, dict):
        return {str(k): make_serializable(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [make_serializable(x) for x in d]
    elif isinstance(d, bytes):
        if is_printable_text(d):
            return d.decode('utf-8', errors='ignore')
        try:
            parsed = parse_proto_bytes(d)
            if parsed: return make_serializable(parsed)
        except: pass
        try: return d.decode('utf-8', errors='ignore')
        except: return d.hex()
    return d

def get_base_url(region):
    return BASE_URLS.get(region.upper(), "https://clientbp.ggpolarbear.com/")

def decode_author_uid(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return str(decoded.get("account_id") or decoded.get("sub"))
    except:
        return None

def get_server_from_token(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded.get("lock_region", "BD").upper()
    except:
        return "BD"