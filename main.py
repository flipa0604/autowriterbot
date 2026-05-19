import asyncio
import logging
import sys

import config
import database as db
import userbot
import scheduler
from admin_bot import start_admin_bot


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("main")


async def main():
    config.validate()
    db.init_db()
    log.info("Database ready: %s", config.DB_PATH)

    await userbot.start_userbot()

    scheduler.start_scheduler()

    try:
        await start_admin_bot()
    finally:
        await userbot.stop_userbot()
        log.info("Stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Interrupted by user")
