# bot/auth/decoders.py

from Pb2 import MajoRLoGinrEs_pb2, PorTs_pb2

async def decode_major_login(data):
    try:
        proto = MajoRLoGinrEs_pb2.MajorLoginRes()
        proto.ParseFromString(data)
        return proto
    except: return None

async def decode_server_list(data):
    try:
        proto = PorTs_pb2.GetLoginData()
        proto.ParseFromString(data)
        return proto
    except: return None