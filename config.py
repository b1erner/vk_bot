import os
from dataclasses import dataclass

@dataclass
class Config:
    vk_token: str
    owner_id: int
    database_path: str
    group_id: int

    @staticmethod
    def from_env():
        token = os.getenv("VK_TOKEN") or os.getenv("TOKEN") or None
        if not token:
            raise RuntimeError("VK_TOKEN environment variable is required")

        owner = os.getenv("OWNER_ID") or "0"
        db = os.getenv("DATABASE_PATH", "/data/bot.db")
        group = os.getenv("GROUP_ID") or os.getenv("GROUP") or "0"

        try:
            owner_id = int(owner)
        except Exception:
            raise RuntimeError("OWNER_ID must be an integer")

        try:
            group_id = int(group) if group else 0
        except Exception:
            group_id = 0

        return Config(
            vk_token=token,
            owner_id=owner_id,
            database_path=db,
            group_id=group_id
        )
