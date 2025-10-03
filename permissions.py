def is_owner(user_id: int, config) -> bool:
    try:
        return int(user_id) == int(config.owner_id)
    except Exception:
        return False

def can_use_moderation(user_id: int, chat_id: int, vk_client, config) -> bool:
    """
    Returns True if the user is the bot owner or a chat admin.
    """
    if is_owner(user_id, config):
        return True
    try:
        return vk_client.is_chat_admin(chat_id, user_id)
    except Exception:
        return False
