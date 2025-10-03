import vk_api
from vk_api.utils import get_random_id
from typing import List, Dict, Any, Optional

class VKClient:
    def __init__(self, token: str):
        self.session = vk_api.VkApi(token=token)
        self.vk = self.session.get_api()

    def send_message(self, peer_id: int, message: str):
        try:
            self.vk.messages.send(peer_id=peer_id, random_id=get_random_id(), message=message)
        except Exception as e:
            print("VK send_message error:", e)

    def delete_message(self, peer_id: int, message_ids: List[int]):
        try:
            # messages.delete accepts list or single id depending on API wrapper
            return self.vk.messages.delete(peer_id=peer_id, message_ids=message_ids, delete_for_all=1)
        except Exception as e:
            # fallback: try deleting ids one by one
            try:
                for mid in message_ids:
                    self.vk.messages.delete(peer_id=peer_id, message_ids=mid, delete_for_all=1)
            except Exception as e2:
                print("VK delete_message error:", e, e2)
            return None

    def remove_user_from_chat(self, chat_id: int, user_id: int):
        peer_id = 2000000000 + int(chat_id)
        try:
            # try new method first
            try:
                return self.vk.messages.removeConversationUser(peer_id=peer_id, member_id=user_id)
            except Exception:
                pass
            # fallback
            try:
                return self.vk.messages.removeChatUser(chat_id=chat_id, member_id=user_id)
            except Exception as e:
                print("VK remove_user_from_chat error:", e)
        except Exception as e:
            print("VK remove_user_from_chat error:", e)

    def get_conversation_members(self, peer_id: int) -> Optional[Dict[str, Any]]:
        try:
            return self.vk.messages.getConversationMembers(peer_id=peer_id)
        except Exception as e:
            print("VK get_conversation_members error:", e)
            return None

    def is_chat_admin(self, chat_id: int, user_id: int) -> bool:
        try:
            peer_id = 2000000000 + int(chat_id)
            data = self.get_conversation_members(peer_id)
            if not data:
                return False
            items = data.get("items", [])
            for item in items:
                member = item.get("member_id")
                if member == user_id:
                    if item.get("is_admin") or item.get("is_owner"):
                        return True
            return False
        except Exception:
            return False

    def resolve_screen_name(self, screen_name: str) -> Optional[int]:
        try:
            if not screen_name:
                return None
            screen_name = screen_name.lstrip('@')
            res = self.vk.utils.resolveScreenName(screen_name=screen_name)
            if not res:
                return None
            if res.get('object_type') == 'user':
                return int(res.get('object_id'))
            return None
        except Exception as e:
            print("VK resolve_screen_name error:", e)
            return None
