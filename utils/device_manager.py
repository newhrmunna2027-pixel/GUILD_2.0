# utils/device_manager.py

import json
import random
import string
import os

# =========================================================================
# 🟢 VERIFIED DEVICE PROFILES (pass.json থেকে নেওয়া ৩টি নিখুঁত কনফিগ):
# গ্যারেনা যাতে কোনো অবস্থাতেই ডাটা অমিল সনাক্ত করতে না পারে, সেজন্য pass.json 
# এ সফলভাবে কাজ করা ফোনের জিপিইউ, র্যাম এবং স্ক্রিন ডেটা ম্যাচিং করে সাজানো হয়েছে।
# =========================================================================
DEVICE_MODELS = [
    {
        "model": "LE2123", "manuf": "OnePlus", "brand": "OnePlus",
        "board": "lahaina", "hardware": "qcom",
        "gpu": "Adreno (TM) 660", "gpu_ver": "OpenGL ES 3.2 V@512.0",
        "dpi": "520", "width": 1440, "height": 3216,
        "android_ver": "Android OS 13 / API-33",
        "memory": 12288
    },
    {
        "model": "SM-G991B", "manuf": "Samsung", "brand": "samsung",
        "board": "exynos2100", "hardware": "exynos",
        "gpu": "Mali-G78 MP14", "gpu_ver": "OpenGL ES 3.2 v1.r26p0",
        "dpi": "420", "width": 1080, "height": 2400,
        "android_ver": "Android OS 12 / API-31",
        "memory": 8192
    },
    {
        "model": "M2101K6G", "manuf": "Xiaomi", "brand": "Redmi",
        "board": "sweet", "hardware": "qcom",
        "gpu": "Adreno (TM) 618", "gpu_ver": "OpenGL ES 3.2 V@502.0",
        "dpi": "440", "width": 1080, "height": 2400,
        "android_ver": "Android OS 11 / API-30",
        "memory": 6144
    }
]

def generate_new_device_profile():
    # র্যান্ডমলি ১টি নিখুঁত ভেরিফাইড মডেল সিলেক্ট করা হচ্ছে
    base = random.choice(DEVICE_MODELS)
    
    unique_id = f"{base['brand']}|{base['model']}|{''.join(random.choices(string.ascii_uppercase + string.digits, k=16))}"
    
    # 🟢 শুধুমাত্র বটের ইউনিক আইডেন্টিফায়ার ডাটাগুলো র্যান্ডমলি জেনারেট হচ্ছে (User-Agent সম্পূর্ণ মুক্ত)
    return {
        "system_software": base['android_ver'],
        "system_hardware": base['hardware'],
        "telecom_operator": random.choice(["Grameenphone", "Robi", "Banglalink", "Teletalk"]),
        "network_type": "WIFI",
        "screen_width": base['width'],
        "screen_height": base['height'],
        "screen_dpi": base['dpi'],
        "processor_details": "AArch64 Processor rev 4 (aarch64)",
        "memory": base['memory'],
        "gpu_renderer": base['gpu'],
        "gpu_version": base['gpu_ver'],
        "unique_device_id": unique_id,
        "imei": str(random.randint(350000000000000, 359999999999999)),
        "android_id": ''.join(random.choices("0123456789abcdef", k=16)),
        "hidden_value": random.randint(50, 99)
    }

def get_or_create_device_config(config_path):
    if not os.path.exists(config_path): return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if 'device_info' in data: 
            # যদি আগে থেকে তৈরি ডিভাইস কনফিগে 'user_agent' থেকে থাকে, তবে তা স্বয়ংক্রিয়ভাবে মুছে দেওয়া হবে
            if 'user_agent' in data['device_info']:
                del data['device_info']['user_agent']
                with open(config_path, 'w', encoding='utf-8') as fw:
                    json.dump(data, fw, indent=4)
            return data
            
        print(f"[Device] Generating new profile for {os.path.basename(config_path)}")
        data['device_info'] = generate_new_device_profile()
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return data
    except Exception as e:
        print(f"[Config Error] {e}")
        return None