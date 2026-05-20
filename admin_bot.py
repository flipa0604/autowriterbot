import logging
import re
from datetime import date

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import ADMIN_BOT_TOKEN, ADMIN_TELEGRAM_ID
import database as db
import userbot
import scheduler

log = logging.getLogger("admin_bot")

bot = Bot(token=ADMIN_BOT_TOKEN)
dp = Dispatcher()


# ---------- admin filter ----------

@dp.message(F.from_user.id != ADMIN_TELEGRAM_ID)
async def deny(message: Message):
    await message.answer("⛔ Bu bot faqat admin uchun.")


# ---------- helpers ----------

VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def parse_workdays(text: str) -> str | None:
    parts = [p.strip().lower() for p in text.split(",")]
    if not all(p in VALID_DAYS for p in parts) or not parts:
        return None
    return ",".join(parts)


def is_valid_identifier(s: str) -> bool:
    if s.startswith("@") and len(s) > 1:
        return bool(re.fullmatch(r"@[A-Za-z0-9_]{4,}", s))
    if s.startswith("+") and len(s) > 5:
        return bool(re.fullmatch(r"\+\d{6,15}", s))
    return False


def is_valid_time(s: str) -> bool:
    return bool(re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", s))


def parse_iso_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


# ---------- commands ----------

HELP_TEXT = """
<b>📋 Komandalar:</b>

<b>Xodimlar</b>
/add @username Ism — xodim qo'shish
/add +998901234567 Ism — telefon orqali
/list — xodimlar ro'yxati
/remove @username — xodimni o'chirish
/remove 5 — id bo'yicha o'chirish
/off @username — xodimni vaqtincha o'chirish
/on @username — qaytadan yoqish

<b>Xabar va vaqt</b>
/message — joriy xabarni ko'rish
/set_message — yangi xabar (keyingi qatorda, {ism} qo'llaniladi)
/time — joriy vaqt
/set_time 17:00 — yuborish vaqtini o'zgartirish
/workdays — joriy ish kunlari
/set_workdays mon,tue,wed,thu,fri — ish kunlarini sozlash
  (mon,tue,wed,thu,fri,sat,sun)

<b>Boshqaruv</b>
/pause — butun yuborishni to'xtatish
/resume — qaytadan ishga tushirish
/test — hozir hammaga yuborish (test)
/test @username — bittaga yuborish
/status — umumiy holat
/log — oxirgi 10 ta urinish

<b>Ta'til (sana oralig'i)</b>
/skip 2026-05-25 2026-06-05 — oraliqni qo'shish
/skips — barcha oraliqlar
/unskip 3 — id bo'yicha oraliqni o'chirish
"""


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Salom! Auto-writer bot ishga tushdi. /help — komandalar ro'yxati.",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")


# ---- employees ----

@dp.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject):
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Foydalanish: <code>/add @username Ism</code> yoki "
            "<code>/add +998901234567 Ism</code>",
            parse_mode="HTML",
        )
        return

    identifier, ism = args[0], args[1].strip()
    if not is_valid_identifier(identifier):
        await message.answer("Identifier noto'g'ri. @username yoki +99890... ko'rinishida bo'lsin.")
        return

    if db.find_employee(identifier):
        await message.answer(f"⚠️ {identifier} allaqachon ro'yxatda.")
        return

    await message.answer(f"🔍 Telegram'dan {identifier} tekshirilmoqda...")
    entity = await userbot.resolve_entity(identifier)
    if not entity:
        await message.answer(
            f"❌ {identifier} topilmadi. Username noto'g'ri, "
            "yoki telefon kontaktda yo'q."
        )
        return

    emp_id = db.add_employee(identifier, ism)
    await message.answer(
        f"✅ Qo'shildi (id={emp_id}): {identifier} → <b>{ism}</b>",
        parse_mode="HTML",
    )


@dp.message(Command("list"))
async def cmd_list(message: Message):
    employees = db.list_employees()
    if not employees:
        await message.answer("Hech kim qo'shilmagan. /add bilan qo'shing.")
        return

    lines = ["<b>Xodimlar:</b>"]
    for e in employees:
        mark = "✅" if e["active"] else "⏸"
        lines.append(f"{mark} <code>{e['id']}</code>. {e['identifier']} — {e['ism']}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("remove"))
async def cmd_remove(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Foydalanish: <code>/remove @username</code> yoki <code>/remove 5</code>", parse_mode="HTML")
        return

    deleted = db.remove_employee(arg)
    if deleted:
        await message.answer(f"🗑 O'chirildi: {arg}")
    else:
        await message.answer(f"❌ Topilmadi: {arg}")


@dp.message(Command("on"))
async def cmd_on(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Foydalanish: /on @username")
        return
    if db.set_employee_active(arg, True):
        await message.answer(f"✅ Yoqildi: {arg}")
    else:
        await message.answer(f"❌ Topilmadi: {arg}")


@dp.message(Command("off"))
async def cmd_off(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Foydalanish: /off @username")
        return
    if db.set_employee_active(arg, False):
        await message.answer(f"⏸ O'chirildi: {arg}")
    else:
        await message.answer(f"❌ Topilmadi: {arg}")


# ---- message ----

@dp.message(Command("message"))
async def cmd_message(message: Message):
    text = db.get_setting("message") or "(bo'sh)"
    await message.answer(f"<b>Joriy xabar:</b>\n\n<pre>{text}</pre>", parse_mode="HTML")


@dp.message(Command("set_message"))
async def cmd_set_message(message: Message, command: CommandObject):
    text = (command.args or "").strip()
    if not text:
        await message.answer(
            "Xabar matnini komanda bilan birga yuboring.\n\n"
            "Misol:\n<code>/set_message Salom {ism}, hisobotingizni yuboring</code>\n\n"
            "{ism} — har bir xodim uchun ismi bilan almashtiriladi.",
            parse_mode="HTML",
        )
        return
    db.set_setting("message", text)
    await message.answer(f"✅ Xabar yangilandi:\n\n<pre>{text}</pre>", parse_mode="HTML")


# ---- time ----

@dp.message(Command("time"))
async def cmd_time(message: Message):
    t = db.get_setting("send_time")
    nxt = scheduler.next_run_time()
    await message.answer(
        f"⏰ Vaqt: <b>{t}</b>\nKeyingi yuborish: <b>{nxt}</b>",
        parse_mode="HTML",
    )


@dp.message(Command("set_time"))
async def cmd_set_time(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    if not is_valid_time(arg):
        await message.answer("Format: <code>/set_time 17:00</code>", parse_mode="HTML")
        return
    db.set_setting("send_time", arg)
    scheduler.reschedule()
    nxt = scheduler.next_run_time()
    await message.answer(f"✅ Vaqt {arg} ga o'zgartirildi.\nKeyingi: {nxt}")


# ---- workdays ----

@dp.message(Command("workdays"))
async def cmd_workdays(message: Message):
    w = db.get_setting("workdays")
    await message.answer(f"📅 Ish kunlari: <b>{w}</b>", parse_mode="HTML")


@dp.message(Command("set_workdays"))
async def cmd_set_workdays(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    parsed = parse_workdays(arg)
    if not parsed:
        await message.answer(
            "Format: <code>/set_workdays mon,tue,wed,thu,fri</code>\n"
            "Mumkin: mon, tue, wed, thu, fri, sat, sun",
            parse_mode="HTML",
        )
        return
    db.set_setting("workdays", parsed)
    scheduler.reschedule()
    nxt = scheduler.next_run_time()
    await message.answer(f"✅ Ish kunlari: {parsed}\nKeyingi: {nxt}")


# ---- pause/resume ----

@dp.message(Command("pause"))
async def cmd_pause(message: Message):
    db.set_setting("paused", "1")
    await message.answer("⏸ Yuborish to'xtatildi. /resume — qaytarish.")


@dp.message(Command("resume"))
async def cmd_resume(message: Message):
    db.set_setting("paused", "0")
    await message.answer("▶️ Yuborish davom etadi.")


# ---- test ----

@dp.message(Command("test"))
async def cmd_test(message: Message, command: CommandObject):
    template = db.get_setting("message") or ""
    if not template.strip():
        await message.answer("Avval /set_message bilan xabar matnini belgilang.")
        return

    arg = (command.args or "").strip()

    if arg:
        emp = db.find_employee(arg)
        if not emp:
            await message.answer(f"❌ Bunday xodim yo'q: {arg}")
            return
        await message.answer(f"🚀 {arg} ga test yuborilmoqda...")
        ok, err = await userbot.send_one(emp["identifier"], emp["ism"], template)
        db.log_send(emp["id"], emp["identifier"], "ok" if ok else "error", err)
        if ok:
            await message.answer("✅ Yuborildi")
        else:
            await message.answer(f"❌ Xato: {err}")
        return

    employees = db.list_employees(only_active=True)
    if not employees:
        await message.answer("Faol xodim yo'q.")
        return

    await message.answer(f"🚀 {len(employees)} ta xodimga test yuborilmoqda...")
    stats = await userbot.send_to_all(template)
    text = f"Natija: ✅ {stats['ok']} / ❌ {stats['fail']} (jami {stats['total']})"
    if stats["errors"]:
        text += "\n\nXatolar:\n" + "\n".join(stats["errors"][:10])
    await message.answer(text)


# ---- skip date ranges ----

@dp.message(Command("skip"))
async def cmd_skip(message: Message, command: CommandObject):
    args = (command.args or "").strip().split()
    if len(args) != 2:
        await message.answer(
            "Format: <code>/skip 2026-05-25 2026-06-05</code>\n"
            "Boshlanish va tugash sanalari (ikkalasi ham kiritilgan kunlar pauza).",
            parse_mode="HTML",
        )
        return

    start = parse_iso_date(args[0])
    end = parse_iso_date(args[1])
    if not start or not end:
        await message.answer("Sana formati noto'g'ri. YYYY-MM-DD bo'lsin (masalan 2026-05-25).")
        return
    if start > end:
        await message.answer("Boshlanish sanasi tugashdan kech bo'lmasligi kerak.")
        return

    range_id = db.add_pause_range(start.isoformat(), end.isoformat())
    await message.answer(
        f"✅ Oraliq qo'shildi (id={range_id}): <b>{start} — {end}</b>\n"
        f"Shu oraliqdagi har bir kun xabar yuborilmaydi.",
        parse_mode="HTML",
    )


@dp.message(Command("skips"))
async def cmd_skips(message: Message):
    ranges = db.list_pause_ranges()
    if not ranges:
        await message.answer("Hech qanday ta'til oralig'i yo'q.")
        return

    today = date.today().isoformat()
    lines = ["<b>Ta'til oraliqlari:</b>"]
    for r in ranges:
        mark = "🔴" if r["start_date"] <= today <= r["end_date"] else "⚪"
        lines.append(
            f"{mark} <code>{r['id']}</code>. {r['start_date']} — {r['end_date']}"
        )
    lines.append("\n🔴 = bugun shu oraliq ichida")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("unskip"))
async def cmd_unskip(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Format: <code>/unskip 3</code> (id raqami)", parse_mode="HTML")
        return
    if db.remove_pause_range(int(arg)):
        await message.answer(f"🗑 Oraliq #{arg} o'chirildi.")
    else:
        await message.answer(f"❌ #{arg} topilmadi.")


# ---- status & log ----

@dp.message(Command("status"))
async def cmd_status(message: Message):
    employees = db.list_employees()
    active = sum(1 for e in employees if e["active"])
    paused = db.get_setting("paused") == "1"
    nxt = scheduler.next_run_time()

    today = date.today().isoformat()
    active_range = db.find_pause_for_date(today)
    range_line = (
        f"\n⏸ Ta'til: <b>{active_range['start_date']} — {active_range['end_date']}</b>"
        if active_range else ""
    )

    text = (
        f"<b>📊 Holat</b>\n\n"
        f"Xodimlar: <b>{active}</b> faol / {len(employees)} jami\n"
        f"Vaqt: <b>{db.get_setting('send_time')}</b>\n"
        f"Ish kunlari: <b>{db.get_setting('workdays')}</b>\n"
        f"Holat: <b>{'⏸ Pauza' if paused else '▶️ Faol'}</b>{range_line}\n"
        f"Keyingi yuborish: <b>{nxt}</b>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("log"))
async def cmd_log(message: Message):
    logs = db.recent_logs(10)
    if not logs:
        await message.answer("Hali yuborilmagan.")
        return

    lines = ["<b>Oxirgi 10 ta:</b>"]
    for l in logs:
        mark = "✅" if l["status"] == "ok" else "❌"
        when = l["sent_at"].split(".")[0].replace("T", " ")
        line = f"{mark} {when} {l['identifier']}"
        if l["error"]:
            line += f" — {l['error']}"
        lines.append(line)
    await message.answer("\n".join(lines), parse_mode="HTML")


async def start_admin_bot():
    log.info("Admin bot starting...")
    await dp.start_polling(bot, handle_signals=False)
