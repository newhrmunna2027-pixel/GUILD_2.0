# bot/auth/http_client.py

import ssl
import aiohttp
import certifi
import asyncio
import os
import json

HEADERS_DIR = "config/headers"
ACTIVE_HEADERS_FILE = os.path.join(HEADERS_DIR, "active_headers.json")

def load_dynamic_headers():
    default_headers = {
        "Connection": "close",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54" # OB54 রিলিজ হেডার সেট করা হলো
    }
    
    if not os.path.exists(HEADERS_DIR):
        os.makedirs(HEADERS_DIR, exist_ok=True)
        
    if not os.path.exists(ACTIVE_HEADERS_FILE):
        try:
            with open(ACTIVE_HEADERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_headers, f, indent=4)
            headers = default_headers
        except:
            headers = default_headers
    else:
        try:
            with open(ACTIVE_HEADERS_FILE, 'r', encoding='utf-8') as f:
                headers = json.load(f)
        except Exception:
            headers = default_headers
            
    # মেমরি বা জেসন ফাইলে যদি ভুলবশত User-Agent থাকে, তবে তা পুরোপুরি ডিলিট করে দেওয়া হবে
    if "User-Agent" in headers:
        del headers["User-Agent"]
        
    return headers

ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def request_guest_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_id": "100067",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
    }
    
    headers = load_dynamic_headers()
    
    connector = aiohttp.TCPConnector(ssl=ssl_context, limit_per_host=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(url, headers=headers, data=data, timeout=15) as response:
                if response.status != 200:
                    print(f"[Auth] Token Grant Error: {response.status}")
                    return None, None
                j = await response.json()
                return j.get("open_id"), j.get("access_token")
        except asyncio.TimeoutError:
            print(f"[Auth] Token Grant Request Timed Out for UID: {uid}")
            return None, None
        except Exception as e:
            print(f"[Auth] Connection Error for UID: {uid} : {e}")
            return None, None

async def post_request(url, data, auth_token=None):
    headers = load_dynamic_headers()
    
    if auth_token:
        headers['Authorization'] = f"Bearer {auth_token}"
    
    connector = aiohttp.TCPConnector(ssl=ssl_context, limit_per_host=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(url, data=data, headers=headers, timeout=20) as response:
                if response.status == 200:
                    return await response.read()
                print(f"[Auth] Request Failed: {url} | Status: {response.status}")
                return None
        except asyncio.TimeoutError:
            print(f"[Auth] Request Timed Out for URL: {url}")
            return None
        except Exception as e:
            print(f"[Auth] Request Error for URL: {url} : {e}")
            return None