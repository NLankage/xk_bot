import asyncio
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.dispatcher.middlewares.base import BaseMiddleware

# FSM imports
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
PHOTO_URL = os.getenv("PHOTO_URL")
CLEAR_CACHE_PASSWORD = os.getenv("CLEAR_CACHE_PASSWORD")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found!")
if not CHANNEL_LINK:
    raise ValueError("❌ CHANNEL_LINK not found")
if not CLEAR_CACHE_PASSWORD:
    print("⚠️ Warning: CLEAR_CACHE_PASSWORD not set → /clearcache disabled")

# Rate limiting settings
MAX_REQUESTS_PER_MINUTE = 5
WARNING_THRESHOLD = 4
BLOCK_DURATION_MINUTES = 3

# In-memory storage
user_data = {}

# FSM States
class ClearCacheStates(StatesGroup):
    waiting_for_password = State()

class AntiSpamMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not isinstance(event, types.Message):
            return await handler(event, data)
        
        user_id = event.from_user.id
        now = datetime.now()
        
        blocked, _ = await is_blocked(user_id)
        if blocked:
            return  # Silent ignore
        
        return await handler(event, data)

async def is_blocked(user_id: int) -> tuple[bool, datetime | None]:
    now = datetime.now()
    data = user_data.get(user_id, {"requests": [], "blocked_until": None})
    
    if data["blocked_until"] and now > data["blocked_until"]:
        data["blocked_until"] = None
        data["requests"] = []
    
    return data["blocked_until"] is not None, data["blocked_until"]

async def record_request(user_id: int):
    now = datetime.now()
    one_minute_ago = now - timedelta(minutes=1)
    
    data = user_data.get(user_id, {"requests": [], "blocked_until": None})
    data["requests"] = [t for t in data["requests"] if t > one_minute_ago]
    data["requests"].append(now)
    user_data[user_id] = data

async def start(message: types.Message):
    user_id = message.from_user.id
    await record_request(user_id)
    
    data = user_data[user_id]
    request_count = len(data["requests"])

    if request_count > WARNING_THRESHOLD and request_count <= MAX_REQUESTS_PER_MINUTE:
        await message.answer("⚠Warning️! You're sending too many requests.")

    if request_count > MAX_REQUESTS_PER_MINUTE:
        block_until = datetime.now() + timedelta(minutes=BLOCK_DURATION_MINUTES)
        user_data[user_id]["blocked_until"] = block_until
        await message.answer(f"🚫Too many requests! You Blocked for {BLOCK_DURATION_MINUTES} minutes.")
        return

    caption = """
🔥 <b>Python Masters Channel</b> 🔥
Daily Python tutorials, projects, tips & tricks!
10k+ developers already learning 🚀
Join කරලා level up වෙන්න! 👇
    """

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Join Channel Now", url=CHANNEL_LINK)]
        ]
    )

    if PHOTO_URL:
        await message.answer_photo(
            photo=PHOTO_URL,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    else:
        await message.answer(
            text=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

# Password protected clear cache
async def cmd_clearcache(message: types.Message, state: FSMContext):
    await message.answer("🔐Enter the password to clear cache:")
    await state.set_state(ClearCacheStates.waiting_for_password)

async def process_clear_password(message: types.Message, state: FSMContext):
    if message.text == CLEAR_CACHE_PASSWORD:
        global user_data
        user_data = {}
        await message.answer("🧹Cache cleared successfully!\nAll rate limits and blocks reset.")
    else:
        await message.answer("❌Wrong password!")
    
    await state.clear()

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.middleware(AntiSpamMiddleware())

    dp.message.register(start, CommandStart())
    
    dp.message.register(cmd_clearcache, Command("clearcache"))
    dp.message.register(process_clear_password, ClearCacheStates.waiting_for_password)

    print("Bot started successfully!")
    print("Anti-spam active + password protected /clearcache")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())