# bot/auth/orchestrator.py

from bot.auth import http_client, payload_builder, decoders

async def perform_login(config):
    account = config.get('account', {})
    uid = account.get('uid')
    password = account.get('password')
    
    if not uid or not password:
        print("[Auth] Missing UID/Password in config")
        return None

    print(f"[*] Authenticating UID: {uid} (User-Agent Less Mode enabled)...")
    
    # ১. গেস্ট টোকেন রিকোয়েস্ট (User-Agent ছাড়া)
    oid, token = await http_client.request_guest_token(uid, password)
    if not oid: 
        print("[Auth] Failed to get Guest Token")
        return None
    
    # ২. মেজর লগইন পেলোড তৈরি
    payload = await payload_builder.create_major_login_payload(config, oid, token)
    
    # ৩. মেজর লগইন রিকোয়েস্ট (User-Agent ছাড়া)
    ml_resp = await http_client.post_request("https://loginbp.ggblueshark.com/MajorLogin", payload)
    if not ml_resp: 
        print("[Auth] MajorLogin Request Failed")
        return None
    
    auth_data = await decoders.decode_major_login(ml_resp)
    if not auth_data: 
        print("[Auth] Failed to decode MajorLogin response")
        return None
    
    # ৪. সার্ভার লিস্ট আইপি রিকোয়েস্ট (User-Agent ছাড়া)
    sl_resp = await http_client.post_request(f"{auth_data.url}/GetLoginData", payload, auth_data.token)
    if not sl_resp: 
        print("[Auth] GetLoginData Request Failed")
        return None
    
    login_data = await decoders.decode_server_list(sl_resp)
    if not login_data:
        print("[Auth] Failed to decode LoginData")
        return None
        
    print(f"[Auth] Success! Region: {login_data.Region} | UID: {auth_data.account_uid}")

    return {
        "auth": auth_data,
        "server": login_data
    }