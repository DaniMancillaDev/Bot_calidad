import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

async def test():
    load_dotenv()
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
    print(dir(bot))
    # We don't have a message ID to react to right now, but we can check if set_reaction exists
    print("set_message_reaction" in dir(bot))

asyncio.run(test())
