# -*- coding: utf-8 -*-
# bot/auth/payload_builder.py

import random
import uuid
from datetime import datetime
from Pb2 import MajoRLoGinrEq_pb2
from bot.packets.base_handler import encrypted_proto

async def create_major_login_payload(config, open_id, access_token):
    device = config.get('device_info', {})
    
    proto = MajoRLoGinrEq_pb2.MajorLogin()
    
    # --- OB54 FIXED CONSTANTS ---
    proto.event_time = str(datetime.now())[:-7]
    proto.game_name = "free fire"
    proto.platform_id = 2
    proto.client_version = "1.126.1"
    proto.client_using_version = "7428b253defc164018c604a1ebbfebdf" # OB54 এও সিগনেচার হ্যাশ অপরিবর্তিত রয়েছে
    proto.client_version_code = "2019120775" # OB54 (1.126.1) এর অফিশিয়াল ভার্সন কোড
    proto.release_channel = "android"
    
    # --- DEVICE SPECIFIC ---
    proto.system_software = str(device.get("system_software", "Android 10 / API-29"))
    proto.system_hardware = str(device.get("system_hardware", "mt6769t"))
    proto.telecom_operator = str(device.get("telecom_operator", "Grameenphone"))
    
    # 🟢 ডাইনামিক নেটওয়ার্ক টাইপ (WIFI, 4G, 5G)
    selected_network = random.choice(["WIFI", "4G", "5G"])
    proto.network_type = selected_network
    proto.network_type_a = selected_network
    proto.network_operator_a = proto.telecom_operator
    
    proto.screen_width = int(device.get("screen_width", 1080))
    proto.screen_height = int(device.get("screen_height", 2340))
    proto.screen_dpi = str(device.get("screen_dpi", "440"))
    proto.processor_details = str(device.get("processor_details", "AArch64 Processor rev 4 (aarch64)"))
    proto.memory = int(device.get("memory", 4096))
    proto.gpu_renderer = str(device.get("gpu_renderer", "Mali-G52 MC2"))
    proto.gpu_version = str(device.get("gpu_version", "OpenGL ES 3.2 v1.r14p0-01rel0"))
    
    # 🟢 ফুল ইউনিক গুগল ডিভাইস আইডি জেনারেটর
    proto.unique_device_id = str(device.get("unique_device_id", f"Google|{uuid.uuid4()}"))
    
    # --- AUTH & LOCATION ---
    proto.open_id = open_id
    proto.access_token = access_token
    proto.open_id_type = "4"
    proto.login_open_id_type = 4
    proto.device_type = "Handheld"
    
    # 🟢 র্যান্ডম আইপি অ্যাড্রেস
    proto.client_ip = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
    
    # --- STORAGE & EXTRAS (DYNAMIC CALCULATION) ---
    total_storage = random.randint(30000, 60000)
    avail_storage = random.randint(10000, 29000)
    total_internal = random.randint(2000, 4000)
    avail_internal = random.randint(500, 1500)
    avail_game_disk = random.randint(20000, 25000)
    total_game_disk = random.randint(25000, 28000)
    
    proto.external_storage_total = total_storage
    proto.external_storage_available = avail_storage
    proto.internal_storage_total = total_internal
    proto.internal_storage_available = avail_internal
    proto.game_disk_storage_available = avail_game_disk
    proto.game_disk_storage_total = total_game_disk
    proto.external_sdcard_avail_storage = avail_storage
    proto.external_sdcard_total_storage = total_storage
    
    proto.login_by = 3
    proto.library_path = "/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/lib/arm64"
    proto.reg_avatar = 1
    proto.library_token = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/base.apk"
    proto.channel_type = 3
    proto.cpu_type = 2
    proto.cpu_architecture = "64"
    proto.graphics_api = "OpenGLES2"
    proto.supported_astc_bitset = 16383
    proto.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWA0FUgsvA1snWlBaO1kFYg=="
    
    # 🟢 ডাইনামিক লোডিং টাইম (৮ থেকে ১৮ সেকেন্ড)
    proto.loading_time = random.randint(8000, 18000)
    
    proto.android_engine_init_flag = 110009
    proto.if_push = 2
    proto.is_vpn = 0
    proto.origin_platform_type = "4"
    proto.primary_platform_type = "4"
    
    # Hidden Values (Critical Dynamic)
    proto.memory_available.version = 55
    proto.memory_available.hidden_value = int(device.get("hidden_value", random.randint(70, 99)))
    
    # Final step: Serialize the object to a byte string
    serialized_payload = proto.SerializeToString()
    
    return await encrypted_proto(serialized_payload)