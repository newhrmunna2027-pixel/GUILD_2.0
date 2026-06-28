# --- START OF FILE responses.py ---

def get_ebook_message(emote_data):
    """
    Shows available Ranks and Badges when just /e is typed.
    Sends a separate message for each Rank.
    """
    if not emote_data or not emote_data.get('ranks'):
        return ["[FF0000]Emote book is empty or could not be loaded."]

    messages_to_send = []
    
    for rank in emote_data.get('ranks', []):
        rank_name = rank.get('rank_name', 'Unknown')
        badge_names = [b.get('badge_name') for b in rank.get('badges', [])]
        badges_str = "[FFFFFF], ".join([f"[00FFFF]{name}" for name in badge_names])
        
        lines = [
            f"[FFD700]= Rank: {rank_name} =",
            "---------------------------------------",
            f"[00FF00]➤ Badges: {badges_str}",
            "---------------------------------------",
            "[FFFF00]Usage: /e [Rank] OR /e [Badge]"
        ]
        messages_to_send.append("\n".join(lines))

    return messages_to_send
    
def get_emote_category_details(emote_data, category_identifier):
    """
    Shows emotes inside a specific Rank or Badge based on user search.
    """
    search_term = category_identifier.lower()
    messages_to_send = []

    # Check if user searched for a Rank (e.g. /e RED)
    for rank in emote_data.get('ranks', []):
        if rank.get('rank_name', '').lower() == search_term:
            for badge in rank.get('badges', []):
                part_lines = [f"[FFD700]--- Rank: {rank['rank_name']} | Badge: {badge['badge_name']} ---"]
                for emp in badge.get('emotes', []):
                    # Format: 402, Gather Around
                    part_lines.append(f"[00FFFF]{emp['no']}[FFFFFF], [C0C0C0]{emp['name']}")
                messages_to_send.append("\n".join(part_lines))
            return messages_to_send

    # Check if user searched for a Badge (e.g. /e Evo)
    for rank in emote_data.get('ranks', []):
        for badge in rank.get('badges', []):
            if badge.get('badge_name', '').lower() == search_term:
                part_lines = [f"[FFD700]--- Badge: {badge['badge_name']} ---"]
                for emp in badge.get('emotes', []):
                    # Format: 402, Gather Around
                    part_lines.append(f"[00FFFF]{emp['no']}[FFFFFF], [C0C0C0]{emp['name']}")
                messages_to_send.append("\n".join(part_lines))
                return messages_to_send

    return ["[FF0000]Rank or Badge not found. Use /e to see the list."]

# --- END OF FILE responses.py ---