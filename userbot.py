import asyncio
import logging
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UserPrivacyRestrictedError,
    UsernameNotOccupiedError,
    PeerFloodError,
)

from config import API_ID, API_HASH, PHONE, SESSION_PATH, SEND_DELAY_SECONDS
import database as db

log = logging.getLogger("userbot")

client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)


async def start_userbot():
    await client.start(phone=PHONE)
    me = await client.get_me()
    log.info("Userbot logged in as: %s (id=%s)", me.username or me.first_name, me.id)


async def stop_userbot():
    await client.disconnect()


def _render_message(template: str, ism: str) -> str:
    try:
        return template.format(ism=ism)
    except (KeyError, IndexError):
        return template


async def send_one(identifier: str, ism: str, template: str) -> tuple[bool, Optional[str]]:
    """Bitta xodimga xabar yuboradi. Return: (success, error_message)."""
    text = _render_message(template, ism)
    try:
        await client.send_message(identifier, text)
        log.info("Sent to %s (%s)", identifier, ism)
        return True, None
    except FloodWaitError as e:
        log.warning("FloodWait: %s soniya kutish kerak", e.seconds)
        return False, f"FloodWait {e.seconds}s"
    except UserPrivacyRestrictedError:
        return False, "User privacy: yozish mumkin emas"
    except UsernameNotOccupiedError:
        return False, "Bunday username yo'q"
    except PeerFloodError:
        return False, "PeerFlood: hisobot juda ko'p — biroz kuting"
    except ValueError as e:
        return False, f"Topilmadi: {e}"
    except Exception as e:
        log.exception("Send error to %s", identifier)
        return False, str(e)


async def send_to_all(template: str) -> dict:
    """Faol xodimlarning hammasiga yuboradi. Return: statistika."""
    employees = db.list_employees(only_active=True)
    stats = {"total": len(employees), "ok": 0, "fail": 0, "errors": []}

    for emp in employees:
        ok, err = await send_one(emp["identifier"], emp["ism"], template)
        if ok:
            stats["ok"] += 1
            db.log_send(emp["id"], emp["identifier"], "ok")
        else:
            stats["fail"] += 1
            stats["errors"].append(f"{emp['identifier']}: {err}")
            db.log_send(emp["id"], emp["identifier"], "error", err)

        await asyncio.sleep(SEND_DELAY_SECONDS)

    return stats


async def resolve_entity(identifier: str) -> Optional[dict]:
    """Username/telefon Telegram'da mavjudligini tekshirish (qo'shishdan oldin)."""
    try:
        entity = await client.get_entity(identifier)
        return {
            "id": entity.id,
            "username": getattr(entity, "username", None),
            "first_name": getattr(entity, "first_name", None),
        }
    except Exception as e:
        log.warning("resolve_entity failed for %s: %s", identifier, e)
        return None
