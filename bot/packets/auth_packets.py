import jwt
from utils.helpers import DecodE_HeX
from bot.packets.base_handler import EnC_PacKeT

async def create_tcp_auth_packet(target_uid, token, timestamp, key, iv):
    """
    TCP কানেকশনের জন্য প্রথম হ্যান্ডশেক প্যাকেট।
    """
    # 🟢 FIX: আগের স্প্যাম বটের মতো JWT থেকে account_id বের করা হলো
    try:
        acc_id = jwt.decode(token, options={"verify_signature": False}).get("account_id", target_uid)
    except:
        acc_id = target_uid
        
    uid_hex = hex(int(acc_id))[2:]
    uid_len = len(uid_hex)

    # টাইমস্ট্যাম্প এনকোড
    ts_hex = await DecodE_HeX(int(timestamp))

    # টোকেন এনক্রিপ্ট
    token_enc = await EnC_PacKeT(token.encode().hex(), key, iv)
    token_len = hex(len(token_enc) // 2)[2:]
    
    if len(token_len) == 1:
        token_len = "0" + token_len

    # 🟢 FIX: আগের স্প্যাম বটের হুবহু প্যাডিং লজিক
    padding = '000000'
    if uid_len == 8: padding = '00000000'
    elif uid_len == 9: padding = '0000000'

    # ফাইনাল প্যাকেট
    packet = f"0115{padding}{uid_hex}{ts_hex}00000{token_len}{token_enc}"
    return packet