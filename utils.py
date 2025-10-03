\
import re
from typing import Optional, Union, Tuple

# Matches [id123|name], id123, vk.com/id123, @screen_name
ID_RE = re.compile(r"\[id(\d+)\|[^\]]+\]|id(\d+)|https?://vk\.com/id(\d+)|@([A-Za-z0-9_.]+)", re.IGNORECASE)

def extract_user_identifier(text: str) -> Optional[Union[int, str]]:
    """
    Extract numeric id or screen_name (without @) from text.
    """
    if not text:
        return None
    m = ID_RE.search(text)
    if m:
        for i in range(1,4):
            if m.group(i):
                try:
                    return int(m.group(i))
                except Exception:
                    return None
        if m.group(4):
            return m.group(4).lstrip('@')
    # fallback: plain @username or numeric
    txt = text.strip()
    if txt.startswith('@'):
        return txt[1:]
    try:
        return int(txt)
    except Exception:
        return None

def parse_command(text: str) -> Tuple[str, str]:
    text = (text or '').strip()
    if not text.startswith('/'):
        return '', ''
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ''
    return cmd, arg
