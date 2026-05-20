import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TIMEZONE
import database as db
import userbot

log = logging.getLogger("scheduler")

scheduler = AsyncIOScheduler(timezone=TIMEZONE)
JOB_ID = "daily_send"


def _today_local() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).date().isoformat()


async def _daily_job():
    if db.get_setting("paused") == "1":
        log.info("Paused — yuborilmadi")
        return

    today = _today_local()
    paused_range = db.find_pause_for_date(today)
    if paused_range:
        log.info(
            "Bugun (%s) pause oralig'ida: %s — %s — yuborilmadi",
            today, paused_range["start_date"], paused_range["end_date"],
        )
        return

    template = db.get_setting("message") or ""
    if not template.strip():
        log.warning("Xabar matni bo'sh — yuborilmadi")
        return

    log.info("Daily job started")
    stats = await userbot.send_to_all(template)
    log.info("Daily job done: %s", stats)


def _build_trigger() -> CronTrigger:
    send_time = db.get_setting("send_time") or "17:00"
    workdays = db.get_setting("workdays") or "mon,tue,wed,thu,fri"
    hour, minute = send_time.split(":")
    return CronTrigger(
        hour=int(hour),
        minute=int(minute),
        day_of_week=workdays,
        timezone=TIMEZONE,
    )


def start_scheduler():
    scheduler.add_job(
        _daily_job,
        trigger=_build_trigger(),
        id=JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    log.info("Scheduler started. Next run: %s", scheduler.get_job(JOB_ID).next_run_time)


def reschedule():
    """Admin sozlamani o'zgartirgandan keyin chaqiriladi."""
    scheduler.reschedule_job(JOB_ID, trigger=_build_trigger())
    log.info("Rescheduled. Next run: %s", scheduler.get_job(JOB_ID).next_run_time)


def next_run_time():
    job = scheduler.get_job(JOB_ID)
    return job.next_run_time if job else None
