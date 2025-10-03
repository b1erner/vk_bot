from __future__ import annotations
import time
from typing import Optional

from vk_client import VKClient
from config import Config
from db import DB
from permissions import can_use_moderation, is_owner
from constants import SYSTEM_PEER_BASE
from utils import extract_user_identifier, parse_command

class Handlers:
    def __init__(self, vk: VKClient, db: DB, config: Config):
        self.vk = vk
        self.db = db
        self.config = config

    def handle_message(self, peer_id: int, from_id: int, text: str, message_id: Optional[int] = None):
        """Process an incoming message: moderation checks + command processing"""
        # If in chat, derive chat_id and register
        chat_id = None
        if peer_id and peer_id >= SYSTEM_PEER_BASE:
            chat_id = peer_id - SYSTEM_PEER_BASE
            try:
                self.db.register_chat(chat_id)
            except Exception:
                pass

        # Lazy cleanup: clear expired mutes
        try:
            expired = self.db.list_expired_mutes()
            for cid, uid in expired:
                self.db.unset_muted(cid, uid)
                try:
                    self.vk.send_message(SYSTEM_PEER_BASE + int(cid), f"✅ Мут с пользователя id{uid} снят (время истекло).")
                except Exception:
                    pass
        except Exception:
            pass

        # Auto-delete messages from muted users
        if chat_id is not None:
            try:
                if self.db.is_muted(chat_id, from_id):
                    until = self.db.get_mute_until(chat_id, from_id)
                    if message_id is not None:
                        try:
                            self.vk.delete_message(peer_id, [message_id])
                        except Exception:
                            pass
                    until_str = "неограничено" if until == 0 else time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(until))
                    try:
                        self.vk.send_message(peer_id, f"⛔ Сообщение от id{from_id} удалено (мут до {until_str}).")
                    except Exception:
                        pass
                    return
            except Exception:
                pass

        # Command parsing
        cmd, arg = parse_command(text)
        if not cmd:
            return

        # Only owner or chat admins can use moderation commands
        if cmd in ("/kick", "/ban", "/muta", "/unmuta"):
            if not can_use_moderation(from_id, chat_id, self.vk, self.config):
                self.vk.send_message(peer_id, "Команда доступна только владельцу бота и администраторам беседы.")
                return

        if cmd == "/kick":
            self._cmd_kick(peer_id, chat_id, arg, from_id)
        elif cmd == "/ban":
            self._cmd_ban(peer_id, chat_id, arg, from_id)
        elif cmd == "/muta":
            self._cmd_mute(peer_id, chat_id, arg, from_id)
        elif cmd == "/unmuta":
            self._cmd_unmute(peer_id, chat_id, arg, from_id)

    def handle_event(self, peer_id: int, event_type: str, user_id: int, actor_id: Optional[int] = None):
        """Handle chat events like user leave/kick — trigger autokick across known chats"""
        chat_id = None
        if peer_id and peer_id >= SYSTEM_PEER_BASE:
            chat_id = peer_id - SYSTEM_PEER_BASE

        if event_type in ("user_kicked", "user_left"):
            try:
                self._autokick_user_across_chats(user_id, origin_chat_id=chat_id)
            except Exception:
                pass

    def _resolve_identifier_to_id(self, identifier) -> Optional[int]:
        if identifier is None:
            return None
        if isinstance(identifier, int):
            return identifier
        if isinstance(identifier, str):
            return self.vk.resolve_screen_name(identifier)
        return None

    def _parse_target(self, arg: str) -> Optional[int]:
        ident = extract_user_identifier(arg)
        return self._resolve_identifier_to_id(ident)

    def _cmd_kick(self, peer_id: int, chat_id: Optional[int], arg: str, issuer_id: int):
        if chat_id is None:
            self.vk.send_message(peer_id, "Команда /kick доступна только в беседе.")
            return
        target_id = self._parse_target(arg)
        if not target_id:
            self.vk.send_message(peer_id, "Не могу определить пользователя. Укажите @имя или id.")
            return
        if int(target_id) == int(self.config.owner_id):
            self.vk.send_message(peer_id, "Нельзя кикать владельца бота.")
            return
        if self.vk.is_chat_admin(chat_id, target_id):
            self.vk.send_message(peer_id, "Нельзя кикать администратора беседы.")
            return
        try:
            self.vk.remove_user_from_chat(chat_id, target_id)
            self.vk.send_message(peer_id, f"Пользователь id{target_id} кикнут из беседы.")
            # autokick across other chats
            try:
                self._autokick_user_across_chats(target_id, origin_chat_id=chat_id)
            except Exception:
                pass
        except Exception:
            self.vk.send_message(peer_id, "Не удалось кикнуть пользователя (возможно прав недостаточно).")

    def _cmd_ban(self, peer_id: int, chat_id: Optional[int], arg: str, issuer_id: int):
        target_id = self._parse_target(arg)
        if not target_id:
            self.vk.send_message(peer_id, "Не могу определить пользователя. Укажите @имя или id.")
            return
        if int(target_id) == int(self.config.owner_id):
            self.vk.send_message(peer_id, "Нельзя банить владельца бота.")
            return
        self.db.add_banned(target_id, reason=f"banned_by:{issuer_id}")
        chats = self.db.list_chats()
        removed = 0
        for cid in chats:
            try:
                if self.vk.is_chat_admin(cid, target_id):
                    continue
                self.vk.remove_user_from_chat(cid, target_id)
                removed += 1
                try:
                    self.vk.send_message(SYSTEM_PEER_BASE+cid, f"🚷 Пользователь id{target_id} исключён из сетки чатов (бан)." )
                except Exception:
                    pass
            except Exception:
                pass
        self.vk.send_message(peer_id, f"Пользователь id{target_id} заблокирован ботом и удалён из {removed} бесед (если возможно).")

    def _cmd_mute(self, peer_id: int, chat_id: Optional[int], arg: str, issuer_id: int):
        if chat_id is None:
            self.vk.send_message(peer_id, "Команда /muta доступна только в беседе.")
            return
        parts = arg.split()
        target_part = parts[0] if parts else ''
        t_minutes = 0
        if len(parts) > 1:
            try:
                t_minutes = int(parts[1])
            except Exception:
                t_minutes = 0
        target_id = self._parse_target(target_part)
        if not target_id:
            self.vk.send_message(peer_id, "Не могу определить пользователя. Укажите @имя или id.")
            return
        if int(target_id) == int(self.config.owner_id):
            self.vk.send_message(peer_id, "Нельзя мутить владельца бота.")
            return
        if self.vk.is_chat_admin(chat_id, target_id):
            self.vk.send_message(peer_id, "Нельзя мутить администратора беседы.")
            return
        until_ts = 0
        if t_minutes > 0:
            until_ts = int(time.time()) + int(t_minutes) * 60
        self.db.set_muted(chat_id, target_id, until_ts)
        until_str = "неограничено" if until_ts == 0 else time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(until_ts))
        self.vk.send_message(peer_id, f"🔇 Пользователь id{target_id} заглушен в этой беседе (до {until_str}).")

    def _cmd_unmute(self, peer_id: int, chat_id: Optional[int], arg: str, issuer_id: int):
        if chat_id is None:
            self.vk.send_message(peer_id, "Команда /unmuta доступна только в беседе.")
            return
        target_id = self._parse_target(arg)
        if not target_id:
            self.vk.send_message(peer_id, "Не могу определить пользователя.")
            return
        self.db.unset_muted(chat_id, target_id)
        self.vk.send_message(peer_id, f"✅ Пользователь id{target_id} разоглушён.")
