# bot/status_parser.py

class SimpleProtobufDecoder:
    @staticmethod
    def parse(hex_data):
        if isinstance(hex_data, str):
            try: data = bytes.fromhex(hex_data)
            except: return {}
        else: data = hex_data
        return SimpleProtobufDecoder._parse_bytes(data)

    @staticmethod
    def _parse_bytes(data):
        results = {}
        idx = 0
        length = len(data)
        while idx < length:
            try:
                tag, idx = SimpleProtobufDecoder._read_varint(data, idx)
                field_number = str(tag >> 3)
                wire_type = tag & 0x07
                if wire_type == 0:
                    value, idx = SimpleProtobufDecoder._read_varint(data, idx)
                    results[field_number] = {"data": value}
                elif wire_type == 2:
                    chunk_len, idx = SimpleProtobufDecoder._read_varint(data, idx)
                    if idx + chunk_len > length: break
                    chunk = data[idx : idx + chunk_len]
                    idx += chunk_len
                    try:
                        nested = SimpleProtobufDecoder._parse_bytes(chunk)
                        if nested: results[field_number] = {"data": nested}
                        else: results[field_number] = {"data": chunk.decode('utf-8', errors='ignore')}
                    except: results[field_number] = {"data": chunk.decode('utf-8', errors='ignore')}
                else: return results 
            except: break
        return results

    @staticmethod
    def _read_varint(data, idx):
        result = 0; shift = 0
        while True:
            if idx >= len(data): raise IndexError
            b = data[idx]; idx += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80): return result, idx
            shift += 7

async def parse_status_response(packet_bytes):
    """Parses 0F00 Status Packet"""
    try:
        start_index = -1
        # Scan for Protobuf Start (0x08)
        for i in range(min(10, len(packet_bytes))):
            if packet_bytes[i] == 0x08:
                start_index = i
                break
        
        if start_index != -1: packet_body = packet_bytes[start_index:]
        else: packet_body = packet_bytes[5:]

        decoded = SimpleProtobufDecoder.parse(packet_body)
        if not decoded or "5" not in decoded: return None

        core_data = decoded["5"]["data"]["1"]["data"]
        
        target_uid = str(core_data.get("1", {}).get("data", "Unknown"))
        status_code = core_data.get("3", {}).get("data", 0)
        
        status_map = {1: "SOLO", 2: "IN SQUAD", 3: "PLAYING", 4: "IN ROOM", 5: "PLAYING", 6: "SOCIAL ISLAND", 7: "SOCIAL ISLAND"}
        status_str = status_map.get(status_code, "OFFLINE")
        
        leader_uid = str(core_data.get("8", {}).get("data", "N/A"))
        
        # [NEW] Room ID Logic
        room_id = "N/A"
        if status_code == 4: # IN ROOM
            # Usually Field 4 contains Room ID or Session ID
            room_id = str(core_data.get("4", {}).get("data", "N/A"))
        
        squad_size = "N/A"
        if "9" in core_data:
            curr = core_data["9"]["data"]
            if "10" in core_data:
                maxx = core_data["10"]["data"] + 1
                squad_size = f"{curr}/{maxx}"
            else: squad_size = f"{curr}"

        return {
            "uid": target_uid, 
            "status": status_str, 
            "leader": leader_uid, 
            "squad_size": squad_size,
            "room_id": room_id
        }
    except: return None