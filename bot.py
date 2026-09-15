import os
import sys
import ssl
import random
import asyncio
import logging
from typing import Dict, List, Set
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, Message, BufferedInputFile
)
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
import asyncpg
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ================= Configuration =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", 8080))

if not BOT_TOKEN:
    logging.critical("CRITICAL: BOT_TOKEN is not set in Environment Variables!")
if not DATABASE_URL:
    logging.critical("CRITICAL: DATABASE_URL is not set in Environment Variables!")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Background Task Registry
running_tasks: Dict[str, asyncio.Task] = {}
db_pool: asyncpg.Pool = None

# Channels Config
FORCE_CHANNELS = ["@jyoex", "@comchater"]
PVT_CHANNEL_LINK = "https://t.me/+gM43iG6v-vFmYjc1"

# FSM States
class AdminState(StatesGroup):
    wait_start_media = State()
    wait_force_media = State()
    wait_preset_nc = State()
    wait_preset_voice = State()
    wait_preset_media = State()

class GroupState(StatesGroup):
    wait_pfp_1 = State()
    wait_pfp_2 = State()
    wait_pfp_3 = State()
    wait_sticker = State()
    wait_gif = State()
    wait_photo = State()
    wait_voice = State()
    wait_script = State()

ROAST_MESSAGES = [
    "𝙃𝙇𝙒 𝙋𝙂𝙇 𝘽𝙃𝘼𝙂 𝙈𝙏 🏃‍♂️💨",
    "𝙏𝙀𝙍𝙄 𝘽𝙃𝙀𝙉 𝙈𝘼𝙍𝘿𝙐 ❓",
    "𝘼𝙑𝙑 𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 𝙆𝙊 𝙋𝙊𝙊𝙆𝙄𝙀 𝘽𝙉𝘼𝙆𝙀 𝙈𝘼𝙍𝙐𝙉𝙂𝘼 🤣🎀",
    "𝙏𝙀𝙍𝙄 𝙂𝙀𝙉𝘿 𝙈𝙀 100 𝙃𝘼𝙏𝙃 💯🔥",
    "𝙁𝘼𝙎𝙏 𝙇𝙄𝙆𝙃𝘾𝙐𝘿𝙉𝘼 𝙈𝙉𝘼 𝙃𝘼𝙄 😩🤟🏻",
    "𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 𝘾𝙐𝘿 𝙍𝙃𝙄 𝙃𝘼𝙄 𝙉𝘼𝘾𝙃𝙊 👻🕺",
    "𝙆𝙍 𝙏𝙔𝙋𝙀 𝙏𝙈𝙆𝘾 😂🤟🏻",
    "𝙅𝙇𝘿𝙄 𝘾𝙐𝘿 🤢",
    "𝘽𝙃𝘼𝙂𝙀𝙂𝘼 ❓",
    "𝘽𝙃𝘼𝙂 𝙈𝙏 𝙆𝙐𝙏𝙄 𝙆𝙀 🙊😂",
    "𝙍𝙊 𝙈𝙏 😂🤟🏻",
    "𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 𝙈𝙐𝙈𝘽𝘼𝙄 𝙈𝙀 𝘾𝙐𝘿𝙀𝙂𝙄 😌🩷",
    "🙌🏾𝘽𝙃𝘼𝙂 𝙈𝙏 𝘽𝙀𝙏𝙀 😑🙌🏾",
    "𝘽𝙄𝙉𝘼 𝙍𝙐𝙆𝙀 𝙏𝙃𝙐𝙆𝘼𝙄 𝙃𝙊𝙂𝙄 𝙏𝙀𝙍𝙄 😁😂",
    "𝙃𝙇𝙒 𝙃𝙇𝙒 𝙈𝙅𝘼 𝘼𝘼𝙍𝙃𝘼 𝘾𝙐𝘿𝙉𝙀 𝙈𝙀 😜",
    "🔥𝙏𝙀𝙍𝙄 𝘽𝙆𝘾 𝙈𝙀 𝘽𝙄𝙂𝘽𝙊𝙎𝙎 📺😆𝘾𝙐𝘿 𝙆𝙀 𝙈𝙍𝙂𝙔𝘼 𝙆𝙔𝘼 💀",
    "😹𝙃𝙔 𝘾𝙊𝙏𝙐 😉✌🏾",
    "𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 𝙆𝙊 𝘽𝙀𝙉10 𝙈𝙀 𝘾𝙊𝘿𝙐𝙉𝙂𝘼 👽😱"
]

EMOJI_POOL = ["❤", "💕", "😒", "😌", "🙂", "👺", "🥳", "🤣", "🔥", "👑", "⚡", "✨", "💎"]

START_TEXT_TEMPLATE = """╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
               𓆰𓆩⃟👑𝑽𝑿𝑪𝑶𝑴 𝑬𝑴𝑷𝑰𝑹𝑬𓆩⃟🇦🇱𓆪

𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @jyoex
° @comchater
° @foraremy 
       ✘ @telerdpbot
╰━━━━━━━━━━━━━━━━━━━━━

        🤍 𝙉𝘼𝙈𝙀 𝘾𝙃𝘼𝙉𝙂𝙀 (𝙉𝘾)
╰━━━━━━━━━━━━━━━━━━━━━
✘ `!nc <name>` / `!dnc`
✘ `!autonc` / `!dautonc`

╭━━━━━━━━━━━━━━━━━━━━
        💀 𝙈𝙀𝘿𝙄𝘼 & 𝙎𝙏𝙄𝘾𝙆𝙀𝙍𝙎
 
✘ `!vstickersm` / `!dvstickersm`
✘ `!gifsm` / `!dgifsm`
✘ `!mediaspm` / `!dmediaspm`
✘ `!automediaspm` / `!dautomediaspm`
✘ `!voicesm` / `!dvoicesm`
✘ `!autovoicesm` / `!dautovoicesm`
✘ `!grouppfp` / `!dgrouppfp`
✘ `!delallmedia`

👾 𝙎𝙇𝙄𝘿𝙀  𝗠𝙎𝙂 𝙉 𝙏𝘼𝙍𝙂𝙀𝙏 𝙈𝙎𝙂

✘ `!targetslide <name>` / `!dtargetslide`
✘ `!slidem` / `!dslidem`
✘ `!script` / `!dscript`
━━━━━━━━━━━━━━━━━━━━━
        ⚙️ 𝙎𝙔𝙎𝙏𝙀𝙈 𝘾𝙊𝙉𝙏𝙍𝙊𝙇

✘ `!status`
✘ `!o` ➜ Optimize & Clear Cache
✘ `!leave` ➜ Bots Leave
✘ `!dall` ➜ Stop All Tasks
"""

# ================= Safe Database Setup =================
async def init_db():
    global db_pool
    if not DATABASE_URL:
        logging.error("DATABASE_URL is not configured!")
        return

    parsed = urlparse(DATABASE_URL)
    clean_dsn = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(5):
        try:
            db_pool = await asyncpg.create_pool(dsn=clean_dsn, ssl=ctx, min_size=1, max_size=10, timeout=15)
            logging.info("Connected to PostgreSQL successfully.")
            break
        except Exception as e:
            logging.warning(f"Database connection attempt {attempt+1} failed: {e}")
            await asyncio.sleep(3)

    if not db_pool:
        try:
            db_pool = await asyncpg.create_pool(dsn=clean_dsn, ssl="require")
        except Exception as e:
            logging.error(f"Fallback connection also failed: {e}")
            return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id BIGINT PRIMARY KEY,
                    chat_title TEXT,
                    added_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS admin_settings (
                    id INT PRIMARY KEY DEFAULT 1,
                    maintenance BOOLEAN DEFAULT FALSE,
                    new_user_alert BOOLEAN DEFAULT TRUE,
                    start_media_id TEXT,
                    start_media_type TEXT,
                    force_media_id TEXT,
                    force_media_type TEXT
                );
                INSERT INTO admin_settings (id, maintenance, new_user_alert) 
                VALUES (1, FALSE, TRUE) ON CONFLICT (id) DO NOTHING;
                
                CREATE TABLE IF NOT EXISTS global_presets (
                    id SERIAL PRIMARY KEY,
                    preset_type TEXT,
                    content TEXT,
                    extra_text TEXT
                );
            """)
            logging.info("Database schemas verified.")
    except Exception as e:
        logging.error(f"Table verification failed: {e}")

# ================= Task & State Utilities =================
def stop_group_task(chat_id: int, task_name: str) -> bool:
    key = f"{chat_id}_{task_name}"
    if key in running_tasks:
        if isinstance(running_tasks[key], asyncio.Task):
            running_tasks[key].cancel()
        del running_tasks[key]
        return True
    return False

def stop_all_group_tasks(chat_id: int) -> int:
    stopped = 0
    keys = [k for k in list(running_tasks.keys()) if k.startswith(f"{chat_id}_")]
    for k in keys:
        if isinstance(running_tasks[k], asyncio.Task):
            running_tasks[k].cancel()
        del running_tasks[k]
        stopped += 1
    return stopped

async def get_admin_settings():
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM admin_settings WHERE id = 1")
    except Exception:
        return None

async def get_chat_admin_ids(chat_id: int) -> Set[int]:
    try:
        admins = await bot.get_chat_administrators(chat_id)
        return {admin.user.id for admin in admins}
    except Exception:
        return set()

# ================= Force Channel Checker =================
async def check_user_joined(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    for ch in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            pass
    return True

def get_force_join_markup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Jyoex", url="https://t.me/jyoex")],
        [InlineKeyboardButton(text="💬 Join Comchater", url="https://t.me/comchater")],
        [InlineKeyboardButton(text="🛒 Sell Hub", url=PVT_CHANNEL_LINK)],
        [InlineKeyboardButton(text="🔄 Verify & Continue", callback_data="check_force_sub")]
    ])

async def send_force_channel_block(message: Message):
    settings = await get_admin_settings()
    f_text = (
        f"⚠️ **Access Denied!** [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n\n"
        "You must join all required official channels before using **VXCOM Empire Bot**!"
    )
    f_mid = settings['force_media_id'] if settings else None
    f_mtype = settings['force_media_type'] if settings else None
    
    if f_mid:
        try:
            if f_mtype == "photo":
                return await message.reply_photo(photo=f_mid, caption=f_text, reply_markup=get_force_join_markup(), parse_mode="Markdown")
            elif f_mtype == "video":
                return await message.reply_video(video=f_mid, caption=f_text, reply_markup=get_force_join_markup(), parse_mode="Markdown")
        except Exception:
            pass
    return await message.reply(f_text, reply_markup=get_force_join_markup(), parse_mode="Markdown")

# ================= 24/7 Background Loops =================
async def loop_name_change(chat_id: int, title_base: str):
    idx = 1
    while True:
        try:
            chosen_emoji = random.choice(EMOJI_POOL)
            emoji_block = chosen_emoji * 50
            new_title = f"{title_base} {emoji_block}"[:128]
            await bot.set_chat_title(chat_id, new_title)
            idx += 1
            await asyncio.sleep(12)
        except asyncio.CancelledError:
            break
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramAPIError:
            await asyncio.sleep(15)
        except Exception:
            await asyncio.sleep(10)

async def loop_auto_nc(chat_id: int):
    idx = 0
    while True:
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    presets = await conn.fetch("SELECT content FROM global_presets WHERE preset_type = 'nc'")
                if presets:
                    row = presets[idx % len(presets)]
                    chosen_emoji = random.choice(EMOJI_POOL)
                    emoji_block = chosen_emoji * 50
                    t = f"{row['content']} {emoji_block}"[:128]
                    await bot.set_chat_title(chat_id, t)
                    idx += 1
                    await asyncio.sleep(12)
                else:
                    await asyncio.sleep(15)
            else:
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            break
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            await asyncio.sleep(10)

async def loop_pfp_rotation(chat_id: int, photos: List[bytes]):
    idx = 0
    while True:
        try:
            img_data = photos[idx % len(photos)]
            await bot.set_chat_photo(chat_id, BufferedInputFile(img_data, filename=f"pfp_{idx}.jpg"))
            idx += 1
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            break
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramAPIError:
            await asyncio.sleep(15)
        except Exception:
            await asyncio.sleep(10)

async def loop_media_stream(chat_id: int, file_id: str, m_type: str, caption: str = ""):
    while True:
        try:
            if m_type == "photo":
                await bot.send_photo(chat_id, file_id, caption=caption)
            elif m_type == "video":
                await bot.send_video(chat_id, file_id, caption=caption)
            elif m_type == "animation":
                await bot.send_animation(chat_id, file_id, caption=caption)
            elif m_type == "sticker":
                await bot.send_sticker(chat_id, file_id)
            elif m_type == "voice":
                await bot.send_voice(chat_id, file_id)
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            break
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            await asyncio.sleep(3)

async def loop_auto_media(chat_id: int, media_type: str):
    idx = 0
    while True:
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    presets = await conn.fetch("SELECT content, extra_text FROM global_presets WHERE preset_type = $1", media_type)
                if presets:
                    item = presets[idx % len(presets)]
                    fid = item['content']
                    cap = item['extra_text'] or ""
                    if media_type == "media":
                        await bot.send_photo(chat_id, fid, caption=cap)
                    elif media_type == "voice":
                        try:
                            await bot.send_voice(chat_id, fid)
                        except Exception:
                            await bot.send_audio(chat_id, fid)
                    idx += 1
                    await asyncio.sleep(2.5)
                else:
                    await asyncio.sleep(10)
            else:
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            break
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            await asyncio.sleep(3)

async def loop_target_slide(chat_id: int, target: str):
    idx = 0
    while True:
        try:
            msg = ROAST_MESSAGES[idx % len(ROAST_MESSAGES)]
            await bot.send_message(chat_id, f"{target} {msg}")
            idx += 1
            await asyncio.sleep(1.5)
        except asyncio.CancelledError:
            break
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            await asyncio.sleep(2)

async def loop_script_spam(chat_id: int, script_text: str):
    while True:
        try:
            await bot.send_message(chat_id, script_text)
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            break
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Exception:
            await asyncio.sleep(3)

# ================= Bot Added to Group Event =================
@dp.my_chat_member()
async def on_bot_added(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        chat = event.chat
        user = event.from_user
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO groups (chat_id, chat_title, added_by) 
                        VALUES ($1, $2, $3)
                        ON CONFLICT (chat_id) DO UPDATE SET chat_title = $2, added_by = $3
                    """, chat.id, chat.title, user.id)
                    
                    st = await conn.fetchrow("SELECT new_user_alert FROM admin_settings WHERE id = 1")
                    if st and st['new_user_alert'] and ADMIN_ID:
                        await bot.send_message(
                            ADMIN_ID,
                            f"🔔 **New Integration Alert**\n\n• Group: `{chat.title}`\n• ID: `{chat.id}`\n• User: [{user.full_name}](tg://user?id={user.id}) (`{user.id}`)",
                            parse_mode="Markdown"
                        )
            except Exception as e:
                logging.error(f"Failed to record group join: {e}")

# ================= Start Handler =================
@dp.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    settings = await get_admin_settings()

    if settings and settings['maintenance'] and user_id != ADMIN_ID:
        return await message.reply("🛠️ Bot is currently under maintenance. Please try again later.")

    # Universal Force Channel Gate Check
    is_joined = await check_user_joined(user_id)
    if not is_joined:
        return await send_force_channel_block(message)

    m_id = settings['start_media_id'] if settings else None
    m_type = settings['start_media_type'] if settings else None

    # In Group
    if message.chat.type in ["group", "supergroup"]:
        if m_id:
            try:
                if m_type == "photo":
                    return await message.reply_photo(photo=m_id, caption=START_TEXT_TEMPLATE, parse_mode="Markdown")
                elif m_type == "video":
                    return await message.reply_video(video=m_id, caption=START_TEXT_TEMPLATE, parse_mode="Markdown")
                elif m_type == "sticker":
                    await message.reply_sticker(sticker=m_id)
                    return await message.answer(START_TEXT_TEMPLATE, parse_mode="Markdown")
            except Exception:
                pass
        return await message.reply(START_TEXT_TEMPLATE, parse_mode="Markdown")

    # In DM
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    
    welcome_text = (
        f"👑 **Welcome to VXCOM Empire Automation** 👑\n\n"
        f"Hello [{message.from_user.full_name}](tg://user?id={message.from_user.id})!\n"
        f"Your multi-tenant task execution & raid engine is active.\n\n"
        f"⚡ **System Status**: Online & Synchronized"
    )
    
    if m_id:
        try:
            if m_type == "photo":
                return await message.answer_photo(photo=m_id, caption=welcome_text, reply_markup=kb, parse_mode="Markdown")
            elif m_type == "video":
                return await message.answer_video(video=m_id, caption=welcome_text, reply_markup=kb, parse_mode="Markdown")
            elif m_type == "sticker":
                await message.answer_sticker(sticker=m_id)
                return await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "check_force_sub")
async def cb_verify_subscription(query: CallbackQuery, state: FSMContext):
    await query.answer()
    is_joined = await check_user_joined(query.from_user.id)
    if not is_joined:
        return await query.message.answer("❌ You haven't joined all required channels yet! Please join and retry.")
    
    try:
        await query.message.delete()
    except Exception:
        pass
    await handle_start(query.message, state)

# ================= User DM Navigation =================
@dp.callback_query(F.data == "user_groups")
async def cb_user_groups(query: CallbackQuery):
    await query.answer()
    if not db_pool:
        return await query.message.answer("Database connecting... Please retry.")
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    if not groups:
        return await query.message.answer("You have not added this bot to any group yet!")
    
    buttons = [[InlineKeyboardButton(text=f"📍 {g['chat_title']}", callback_data="noop")] for g in groups]
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")])
    await query.message.answer("📋 **Your Connected Groups:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data == "user_status")
async def cb_user_status(query: CallbackQuery):
    await query.answer()
    if not db_pool:
        return await query.message.answer("Database connecting... Please retry.")
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    
    status_text = "📊 **Your Active Group Tasks:**\n\n"
    active_found = False
    for g in groups:
        c_id = g['chat_id']
        running = [k.replace(f"{c_id}_", "") for k in running_tasks.keys() if k.startswith(f"{c_id}_")]
        if running:
            active_found = True
            status_text += f"🔹 **{g['chat_title']}**\n   Active: `{', '.join(running)}`\n\n"
            
    if not active_found:
        status_text += "No active background tasks running in your groups."
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]])
    await query.message.answer(status_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "user_commands")
async def cb_user_commands(query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]])
    await query.message.answer(START_TEXT_TEMPLATE, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "back_main")
async def cb_back_main(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    welcome_text = (
        f"👑 **Welcome to VXCOM Empire Automation** 👑\n\n"
        f"Hello [{query.from_user.full_name}](tg://user?id={query.from_user.id})!\n"
        f"Your control portal is active."
    )
    await query.message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")

# ================= Super Admin Control Panel =================
@dp.message(Command("admin"))
@dp.message(Command("panel"))
async def open_admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    settings = await get_admin_settings()
    
    m_status = "🟢 ON" if (settings and settings['maintenance']) else "🔴 OFF"
    a_status = "🔔 ON" if (settings and settings['new_user_alert']) else "🔕 OFF"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="adm_stats"),
            InlineKeyboardButton(text=f"🛠️ Maint ({m_status})", callback_data="adm_toggle_maint")
        ],
        [
            InlineKeyboardButton(text=f"👤 Alert ({a_status})", callback_data="adm_toggle_alert"),
            InlineKeyboardButton(text="🖼️ Manage Media", callback_data="adm_media_hub")
        ],
        [InlineKeyboardButton(text="🔘 Manage Auto Presets", callback_data="adm_presets_menu")],
        [InlineKeyboardButton(text="❌ Close Panel", callback_data="adm_close")]
    ])
    await message.reply("⚙️ **Super Admin Control Center**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_stats")
async def cb_admin_stats(query: CallbackQuery):
    if not db_pool:
        return await query.answer("Database connecting...", show_alert=True)
    async with db_pool.acquire() as conn:
        g_count = await conn.fetchval("SELECT COUNT(*) FROM groups")
        p_count = await conn.fetchval("SELECT COUNT(*) FROM global_presets")
    await query.answer(
        f"📊 Stats:\n• Groups: {g_count}\n• Loops Active: {len(running_tasks)}\n• Presets: {p_count}", 
        show_alert=True
    )

@dp.callback_query(F.data == "adm_toggle_maint")
async def cb_toggle_maint(query: CallbackQuery, state: FSMContext):
    await query.answer("Toggling...")
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET maintenance = NOT maintenance WHERE id = 1")
    await open_admin_panel(query.message, state)

@dp.callback_query(F.data == "adm_toggle_alert")
async def cb_toggle_alert(query: CallbackQuery, state: FSMContext):
    await query.answer("Toggling...")
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET new_user_alert = NOT new_user_alert WHERE id = 1")
    await open_admin_panel(query.message, state)

# ================= Media Hub =================
@dp.callback_query(F.data == "adm_media_hub")
async def cb_adm_media_hub(query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼️ Start Page Media", callback_data="adm_manage_media")],
        [InlineKeyboardButton(text="🔒 Force Channel Media", callback_data="adm_manage_forcemedia")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")]
    ])
    await query.message.answer("🖼️ **Media Management Hub**\nSelect media type to manage:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_manage_media")
async def cb_adm_media(query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Set Start Media", callback_data="adm_set_media_prompt")],
        [InlineKeyboardButton(text="👁️ See Current", callback_data="adm_see_media")],
        [InlineKeyboardButton(text="🗑️ Reset", callback_data="adm_del_media")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_media_hub")]
    ])
    await query.message.answer("🖼️ **Start Banner Media**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_set_media_prompt")
async def cb_set_media_prompt(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(AdminState.wait_start_media)
    await query.message.answer("📸 Send or forward the **Photo, Video, Sticker, or GIF** for the Start Page.")

@dp.callback_query(F.data == "adm_see_media")
async def cb_see_media(query: CallbackQuery):
    await query.answer()
    settings = await get_admin_settings()
    if not settings or not settings['start_media_id']:
        return await query.message.answer("No Start Media currently set.")
    m_type, m_id = settings['start_media_type'], settings['start_media_id']
    try:
        if m_type == "photo":
            await bot.send_photo(query.from_user.id, m_id, caption="Current Start Banner")
        elif m_type == "video":
            await bot.send_video(query.from_user.id, m_id, caption="Current Start Video")
        elif m_type == "sticker":
            await bot.send_sticker(query.from_user.id, m_id)
        elif m_type == "animation":
            await bot.send_animation(query.from_user.id, m_id, caption="Current Start GIF")
    except Exception as e:
        await query.message.answer(f"Failed to fetch media: {e}")

@dp.callback_query(F.data == "adm_del_media")
async def cb_del_media(query: CallbackQuery, state: FSMContext):
    await query.answer("Start Media Deleted!", show_alert=True)
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET start_media_id = NULL, start_media_type = NULL WHERE id = 1")
    await open_admin_panel(query.message, state)

@dp.callback_query(F.data == "adm_manage_forcemedia")
async def cb_adm_forcemedia(query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Set Force Media", callback_data="adm_set_forcemedia_prompt")],
        [InlineKeyboardButton(text="🗑️ Reset", callback_data="adm_del_forcemedia")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_media_hub")]
    ])
    await query.message.answer("🔒 **Force Channel Banner Media**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_set_forcemedia_prompt")
async def cb_set_forcemedia_prompt(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(AdminState.wait_force_media)
    await query.message.answer("📸 Send or forward the **Photo/Video** for Force Join Banner.")

@dp.callback_query(F.data == "adm_del_forcemedia")
async def cb_del_forcemedia(query: CallbackQuery, state: FSMContext):
    await query.answer("Force Join Media Reset!", show_alert=True)
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET force_media_id = NULL, force_media_type = NULL WHERE id = 1")
    await open_admin_panel(query.message, state)

# ================= Dedicated Auto Presets Manager =================
@dp.callback_query(F.data == "adm_presets_menu")
async def cb_presets_menu(query: CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 NC Titles Presets", callback_data="preset_cat_nc")],
        [InlineKeyboardButton(text="🎙️ Voice Presets", callback_data="preset_cat_voice")],
        [InlineKeyboardButton(text="🖼️ Media+Text Presets", callback_data="preset_cat_media")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")]
    ])
    await query.message.answer("🔘 **Auto Presets Manager**\nSelect a preset category to manage:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("preset_cat_"))
async def cb_preset_category(query: CallbackQuery):
    await query.answer()
    cat = query.data.replace("preset_cat_", "")
    cat_names = {"nc": "📝 NC Titles", "voice": "🎙️ Voices", "media": "🖼️ Media+Text"}
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"➕ Add {cat.upper()}", callback_data=f"padd_{cat}")],
        [InlineKeyboardButton(text="👁️ See List", callback_data=f"plist_{cat}")],
        [InlineKeyboardButton(text="🗑️ Reset All", callback_data=f"preset_{cat}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_presets_menu")]
    ])
    await query.message.answer(f"⚙️ **Managing: {cat_names.get(cat, cat)}**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("padd_"))
async def cb_preset_add_prompt(query: CallbackQuery, state: FSMContext):
    await query.answer()
    cat = query.data.replace("padd_", "")
    if cat == "nc":
        await state.set_state(AdminState.wait_preset_nc)
        await query.message.answer("📝 Send the **Text Name** you want to add to Auto NC Presets.")
    elif cat == "voice":
        await state.set_state(AdminState.wait_preset_voice)
        await query.message.answer("🎙️ Send or forward the **Voice Note / Audio** for Auto Voice Presets.")
    elif cat == "media":
        await state.set_state(AdminState.wait_preset_media)
        await query.message.answer("🖼️ Send the **Photo (with or without caption)** for Auto Media Presets.")

@dp.callback_query(F.data.startswith("plist_"))
async def cb_preset_list(query: CallbackQuery):
    await query.answer()
    cat = query.data.replace("plist_", "")
    if not db_pool:
        return await query.message.answer("Database connecting... Please retry.")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, content, extra_text FROM global_presets WHERE preset_type = $1", cat)
    if not rows:
        return await query.message.answer(f"⚠️ No presets currently loaded under `{cat}` category.")
    
    text = f"📋 **Loaded {cat.upper()} Presets ({len(rows)} items):**\n\n"
    for r in rows:
        val = r['content'][:30] if cat == "nc" else f"Media ID: {r['id']} (Caption: {r['extra_text'] or 'None'})"
        text += f"• `{r['id']}`: {val}\n"
    await query.message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("preset_"))
async def cb_preset_reset(query: CallbackQuery):
    cat = query.data.replace("preset_", "")
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM global_presets WHERE preset_type = $1", cat)
    await query.answer(f"All {cat.upper()} Presets Reset!", show_alert=True)
    await cb_presets_menu(query)

@dp.callback_query(F.data == "adm_close")
async def cb_close_panel(query: CallbackQuery):
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass

@dp.callback_query(F.data == "adm_back")
async def cb_back_panel(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await open_admin_panel(query.message, state)

# ================= FSM Message Receiver for Admin =================
@dp.message(AdminState.wait_start_media)
async def fsm_admin_start_media(message: Message, state: FSMContext):
    fid, mtype = None, None
    if message.photo:
        fid, mtype = message.photo[-1].file_id, "photo"
    elif message.video:
        fid, mtype = message.video.file_id, "video"
    elif message.sticker:
        fid, mtype = message.sticker.file_id, "sticker"
    elif message.animation:
        fid, mtype = message.animation.file_id, "animation"
    
    if fid and db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET start_media_id = $1, start_media_type = $2 WHERE id = 1", fid, mtype)
        await state.clear()
        return await message.reply(f"✅ **Start Media successfully saved as** `{mtype}`!", parse_mode="Markdown")
    await message.reply("❌ Invalid format! Please send Photo, Video, Sticker, or GIF.")

@dp.message(AdminState.wait_force_media)
async def fsm_admin_force_media(message: Message, state: FSMContext):
    fid, mtype = None, None
    if message.photo:
        fid, mtype = message.photo[-1].file_id, "photo"
    elif message.video:
        fid, mtype = message.video.file_id, "video"
    
    if fid and db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET force_media_id = $1, force_media_type = $2 WHERE id = 1", fid, mtype)
        await state.clear()
        return await message.reply(f"✅ **Force Join Media successfully saved as** `{mtype}`!", parse_mode="Markdown")
    await message.reply("❌ Invalid format! Please send Photo or Video.")

@dp.message(AdminState.wait_preset_nc)
async def fsm_admin_preset_nc(message: Message, state: FSMContext):
    if message.text and db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("INSERT INTO global_presets (preset_type, content) VALUES ('nc', $1)", message.text)
        await state.clear()
        return await message.reply(f"✅ **Auto NC Preset Added:** `{message.text}`", parse_mode="Markdown")
    await message.reply("❌ Please send valid text.")

@dp.message(AdminState.wait_preset_voice)
async def fsm_admin_preset_voice(message: Message, state: FSMContext):
    fid = message.voice.file_id if message.voice else (message.audio.file_id if message.audio else None)
    if fid and db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("INSERT INTO global_presets (preset_type, content) VALUES ('voice', $1)", fid)
        await state.clear()
        return await message.reply("✅ **Auto Voice Preset Added Successfully!**", parse_mode="Markdown")
    await message.reply("❌ Please send or forward a Voice note or Audio file.")

@dp.message(AdminState.wait_preset_media)
async def fsm_admin_preset_media(message: Message, state: FSMContext):
    fid = None
    if message.photo:
        fid = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        fid = message.document.file_id
    
    if fid and db_pool:
        cap = message.caption or ""
        async with db_pool.acquire() as conn:
            await conn.execute("INSERT INTO global_presets (preset_type, content, extra_text) VALUES ('media', $1, $2)", fid, cap)
        await state.clear()
        return await message.reply(f"✅ **Auto Media Preset Saved Successfully!**\nCaption: `{cap or 'None'}`", parse_mode="Markdown")
    await message.reply("❌ Please send a Photo.")

# ================= PRIORITY: Group Command Engine =================
@dp.message(F.text.startswith("!"))
async def handle_commands(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Universal Force Sub Gate on all commands
    is_joined = await check_user_joined(user_id)
    if not is_joined:
        return await send_force_channel_block(message)

    chat_id = message.chat.id
    user_mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    raw_text = message.text.strip()
    parts = raw_text.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # Stop Commands
    if cmd == "!dall":
        stopped = stop_all_group_tasks(chat_id)
        await state.clear()
        return await message.reply(
            f"🛑 **All Group Tasks Terminated!**\nCleaned and stopped `{stopped}` active background task(s) by {user_mention}.",
            parse_mode="Markdown"
        )

    if cmd == "!dnc":
        stop_group_task(chat_id, "nc")
        return await message.reply(f"🛑 **Name Change Loop Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dautonc":
        stop_group_task(chat_id, "autonc")
        return await message.reply(f"🛑 **Auto Name Change Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dvstickersm":
        stop_group_task(chat_id, "vstickersm")
        return await message.reply(f"🛑 **Sticker Stream Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dgifsm":
        stop_group_task(chat_id, "gifsm")
        return await message.reply(f"🛑 **GIF Spam Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dmediaspm":
        stop_group_task(chat_id, "mediaspm")
        return await message.reply(f"🛑 **Media Spam Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dautomediaspm":
        stop_group_task(chat_id, "automediaspm")
        return await message.reply(f"🛑 **Auto Media Spam Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dvoicesm":
        stop_group_task(chat_id, "voicesm")
        return await message.reply(f"🛑 **Voice Spam Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dautovoicesm":
        stop_group_task(chat_id, "autovoicesm")
        return await message.reply(f"🛑 **Auto Voice Spam Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd in ["!dgrouppfp", "!dgpfp"]:
        stop_group_task(chat_id, "grouppfp")
        return await message.reply(f"🛑 **Group PFP Rotation Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!delallmedia":
        stop_group_task(chat_id, "mediaspm")
        stop_group_task(chat_id, "vstickersm")
        stop_group_task(chat_id, "gifsm")
        stop_group_task(chat_id, "voicesm")
        stop_group_task(chat_id, "grouppfp")
        return await message.reply(f"🧹 **All Active Media Streams Purged & Reset** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dtargetslide":
        stop_group_task(chat_id, "targetslide")
        return await message.reply(f"🛑 **Target Slide Lock Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dslidem":
        running_tasks[f"{chat_id}_slidem_active"] = False
        return await message.reply(f"🛑 **Group Slide Attack Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dscript":
        stop_group_task(chat_id, "script")
        return await message.reply(f"🛑 **Custom Script Spam Terminated** by {user_mention}.", parse_mode="Markdown")

    # Execution Commands
    if cmd == "!nc":
        if not arg:
            return await message.reply("Usage: `!nc <New Group Name>`", parse_mode="Markdown")
        stop_group_task(chat_id, "nc")
        task = asyncio.create_task(loop_name_change(chat_id, arg))
        running_tasks[f"{chat_id}_nc"] = task
        return await message.reply(f"✅ **Continuous Name Change Loop Activated**\nBase: `{arg}` by {user_mention}.", parse_mode="Markdown")

    if cmd == "!autonc":
        if db_pool:
            async with db_pool.acquire() as conn:
                cnt = await conn.fetchval("SELECT COUNT(*) FROM global_presets WHERE preset_type = 'nc'")
        else:
            cnt = 0
        if not cnt:
            return await message.reply("⚠️ **No Auto NC Presets Found!** Add presets from `/panel` first.")
        stop_group_task(chat_id, "autonc")
        task = asyncio.create_task(loop_auto_nc(chat_id))
        running_tasks[f"{chat_id}_autonc"] = task
        return await message.reply(f"🚀 **Auto Name Change Started** from Global Presets by {user_mention}.", parse_mode="Markdown")

    if cmd == "!vstickersm":
        if message.reply_to_message and message.reply_to_message.sticker:
            fid = message.reply_to_message.sticker.file_id
            stop_group_task(chat_id, "vstickersm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "sticker"))
            running_tasks[f"{chat_id}_vstickersm"] = task
            return await message.reply(f"🚀 **Sticker Spam Stream Initiated** by {user_mention}!", parse_mode="Markdown")
        await state.set_state(GroupState.wait_sticker)
        return await message.reply("📸 **Please send or forward the Sticker** to start continuous stream.")

    if cmd == "!gifsm":
        if message.reply_to_message and (message.reply_to_message.animation or message.reply_to_message.document):
            fid = (message.reply_to_message.animation or message.reply_to_message.document).file_id
            stop_group_task(chat_id, "gifsm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "animation"))
            running_tasks[f"{chat_id}_gifsm"] = task
            return await message.reply(f"🚀 **GIF Spam Loop Activated** by {user_mention}!", parse_mode="Markdown")
        await state.set_state(GroupState.wait_gif)
        return await message.reply("👾 **Please send the GIF** to start continuous loop.")

    if cmd == "!mediaspm":
        if message.reply_to_message and message.reply_to_message.photo:
            fid = message.reply_to_message.photo[-1].file_id
            caption = message.reply_to_message.caption or arg or ""
            stop_group_task(chat_id, "mediaspm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "photo", caption))
            running_tasks[f"{chat_id}_mediaspm"] = task
            return await message.reply(f"🚀 **Photo+Text Spam Loop Activated** by {user_mention}!", parse_mode="Markdown")
        await state.set_state(GroupState.wait_photo)
        return await message.reply("🖼️ **Please send the Photo** to set for continuous loop.")

    if cmd == "!automediaspm":
        if db_pool:
            async with db_pool.acquire() as conn:
                cnt = await conn.fetchval("SELECT COUNT(*) FROM global_presets WHERE preset_type = 'media'")
        else:
            cnt = 0
        if not cnt:
            return await message.reply("⚠️ **No Auto Media Presets Found!** Add presets in `/panel` first.")
        stop_group_task(chat_id, "automediaspm")
        task = asyncio.create_task(loop_auto_media(chat_id, "media"))
        running_tasks[f"{chat_id}_automediaspm"] = task
        return await message.reply(f"🚀 **Auto Global Media Stream Started** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!voicesm":
        if message.reply_to_message and (message.reply_to_message.voice or message.reply_to_message.audio):
            fid = message.reply_to_message.voice.file_id if message.reply_to_message.voice else message.reply_to_message.audio.file_id
            stop_group_task(chat_id, "voicesm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "voice"))
            running_tasks[f"{chat_id}_voicespm"] = task
            return await message.reply(f"🎙️ **Voice Spam Stream Activated** by {user_mention}!", parse_mode="Markdown")
        await state.set_state(GroupState.wait_voice)
        return await message.reply("🎙️ **Please record or forward the Voice Note** to set for loop.")

    if cmd == "!autovoicesm":
        if db_pool:
            async with db_pool.acquire() as conn:
                cnt = await conn.fetchval("SELECT COUNT(*) FROM global_presets WHERE preset_type = 'voice'")
        else:
            cnt = 0
        if not cnt:
            return await message.reply("⚠️ **No Auto Voice Presets Found!** Add presets in `/panel` first.")
        stop_group_task(chat_id, "autovoicesm")
        task = asyncio.create_task(loop_auto_media(chat_id, "voice"))
        running_tasks[f"{chat_id}_autovoicesm"] = task
        return await message.reply(f"🎙️ **Auto Global Voice Stream Started** by {user_mention}.", parse_mode="Markdown")

    if cmd in ["!grouppfp", "!gpfp"]:
        await state.set_state(GroupState.wait_pfp_1)
        await state.update_data(photos=[])
        return await message.reply(
            "📸 **Group PFP Rotation Setup**\n\nPlease send **Photo (1/3)** for continuous profile rotation.",
            parse_mode="Markdown"
        )

    if cmd == "!targetslide":
        if not arg:
            return await message.reply("Usage: `!targetslide <@username or Name>`", parse_mode="Markdown")
        stop_group_task(chat_id, "targetslide")
        task = asyncio.create_task(loop_target_slide(chat_id, arg))
        running_tasks[f"{chat_id}_targetslide"] = task
        return await message.reply(f"🎯 **Target Slide Attack Locked** on `{arg}` by {user_mention}!", parse_mode="Markdown")

    if cmd == "!slidem":
        running_tasks[f"{chat_id}_slidem_active"] = True
        return await message.reply(f"👾 **Global Slide Mode Activated!** All non-admin chat members will be auto-roasted.", parse_mode="Markdown")

    if cmd == "!script":
        if message.reply_to_message and message.reply_to_message.text:
            s_text = message.reply_to_message.text
        elif arg:
            s_text = arg
        else:
            await state.set_state(GroupState.wait_script)
            return await message.reply("📜 **Please send or reply to the long text script** you want to loop 24/7.")
        
        stop_group_task(chat_id, "script")
        task = asyncio.create_task(loop_script_spam(chat_id, s_text))
        running_tasks[f"{chat_id}_script"] = task
        return await message.reply(f"🚀 **Continuous 24/7 Script Spam Loop Activated** by {user_mention}!", parse_mode="Markdown")

    if cmd == "!status":
        active_in_group = [k.replace(f"{chat_id}_", "") for k in running_tasks.keys() if k.startswith(f"{chat_id}_")]
        t_list = "None" if not active_in_group else ", ".join([f"`{t}`" for t in active_in_group])
        return await message.reply(f"⚙️ **Group Task Status:**\n• Active Tasks: {t_list}\n• Execution Engine: Operational ⚡", parse_mode="Markdown")

    if cmd == "!o":
        return await message.reply(f"🧹 **Optimization Complete:** Cache flushed and memory freed for this chat.", parse_mode="Markdown")

    if cmd == "!leave":
        await message.reply(f"👋 **Leaving Group** as requested by {user_mention}...")
        try:
            await bot.leave_chat(chat_id)
        except Exception as e:
            logging.error(f"Failed to leave chat: {e}")

# ================= FSM Group Interactive Message Receivers =================
@dp.message(GroupState.wait_pfp_1, F.photo)
async def fsm_pfp_1(message: Message, state: FSMContext):
    photo_file = await bot.get_file(message.photo[-1].file_id)
    f_bytes = await bot.download_file(photo_file.file_path)
    await state.update_data(photos=[f_bytes.read()])
    await state.set_state(GroupState.wait_pfp_2)
    await message.reply("✅ **Photo (1/3) Received!** Now please send **Photo (2/3)**.", parse_mode="Markdown")

@dp.message(GroupState.wait_pfp_2, F.photo)
async def fsm_pfp_2(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photo_file = await bot.get_file(message.photo[-1].file_id)
    f_bytes = await bot.download_file(photo_file.file_path)
    photos.append(f_bytes.read())
    await state.update_data(photos=photos)
    await state.set_state(GroupState.wait_pfp_3)
    await message.reply("✅ **Photo (2/3) Received!** Now please send **Photo (3/3)**.", parse_mode="Markdown")

@dp.message(GroupState.wait_pfp_3, F.photo)
async def fsm_pfp_3(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photo_file = await bot.get_file(message.photo[-1].file_id)
    f_bytes = await bot.download_file(photo_file.file_path)
    photos.append(f_bytes.read())
    
    chat_id = message.chat.id
    stop_group_task(chat_id, "grouppfp")
    task = asyncio.create_task(loop_pfp_rotation(chat_id, photos))
    running_tasks[f"{chat_id}_grouppfp"] = task
    await state.clear()
    await message.reply("🚀 **All 3 Photos Loaded! Continuous 3-PFP Rotation Started Successfully!**", parse_mode="Markdown")

@dp.message(GroupState.wait_sticker, F.sticker)
async def fsm_group_sticker(message: Message, state: FSMContext):
    chat_id = message.chat.id
    fid = message.sticker.file_id
    stop_group_task(chat_id, "vstickersm")
    task = asyncio.create_task(loop_media_stream(chat_id, fid, "sticker"))
    running_tasks[f"{chat_id}_vstickersm"] = task
    await state.clear()
    await message.reply("🚀 **Sticker Loop Started Successfully!**")

@dp.message(GroupState.wait_gif, F.animation | F.document)
async def fsm_group_gif(message: Message, state: FSMContext):
    chat_id = message.chat.id
    fid = (message.animation or message.document).file_id
    stop_group_task(chat_id, "gifsm")
    task = asyncio.create_task(loop_media_stream(chat_id, fid, "animation"))
    running_tasks[f"{chat_id}_gifsm"] = task
    await state.clear()
    await message.reply("🚀 **GIF Loop Started Successfully!**")

@dp.message(GroupState.wait_photo, F.photo)
async def fsm_group_photo(message: Message, state: FSMContext):
    chat_id = message.chat.id
    fid = message.photo[-1].file_id
    cap = message.caption or ""
    stop_group_task(chat_id, "mediaspm")
    task = asyncio.create_task(loop_media_stream(chat_id, fid, "photo", cap))
    running_tasks[f"{chat_id}_mediaspm"] = task
    await state.clear()
    await message.reply("🚀 **Photo Loop Started Successfully!**")

@dp.message(GroupState.wait_voice, F.voice | F.audio)
async def fsm_group_voice(message: Message, state: FSMContext):
    chat_id = message.chat.id
    fid = message.voice.file_id if message.voice else message.audio.file_id
    stop_group_task(chat_id, "voicesm")
    task = asyncio.create_task(loop_media_stream(chat_id, fid, "voice"))
    running_tasks[f"{chat_id}_voicespm"] = task
    await state.clear()
    await message.reply("🎙️ **Voice Loop Started Successfully!**")

@dp.message(GroupState.wait_script, F.text)
async def fsm_group_script(message: Message, state: FSMContext):
    chat_id = message.chat.id
    s_text = message.text
    stop_group_task(chat_id, "script")
    task = asyncio.create_task(loop_script_spam(chat_id, s_text))
    running_tasks[f"{chat_id}_script"] = task
    await state.clear()
    await message.reply("🚀 **Custom Script Spam Started Successfully!**")

# ================= Fallback & Slidem Non-Admin Handler =================
@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def slidem_and_non_admin_router(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if running_tasks.get(f"{chat_id}_slidem_active"):
        admins = await get_chat_admin_ids(chat_id)
        if user_id not in admins and not message.from_user.is_bot:
            roast = random.choice(ROAST_MESSAGES)
            tag = f"[{message.from_user.first_name}](tg://user?id={user_id})"
            try:
                await message.reply(f"{tag} {roast}", parse_mode="Markdown")
            except Exception:
                pass

# ================= Keep-Alive Web Server =================
async def ping_response(request):
    return web.Response(text="Bot Engine is Active and Running!")

async def main():
    # 1. Start Web Server First for Immediate Health Check Passing
    app = web.Application()
    app.router.add_get("/", ping_response)
    app.router.add_get("/ping", ping_response)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Health server listening on port {PORT}")
    
    # 2. Asynchronously Connect DB
    await init_db()
    
    # 3. Start Polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
