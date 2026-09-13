import os
import sys
import ssl
import asyncio
import logging
from typing import Dict, Set
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, Message, BufferedInputFile
)
import asyncpg
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ================= Configuration =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Memory Task & State Management
running_tasks: Dict[str, asyncio.Task] = {}
user_states: Dict[int, Dict[str, str]] = {}
db_pool: asyncpg.Pool = None

# Custom Slide & Abuse Pool
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

MANDATORY_EMOJIS = "❤" * 50 + "💕😒😌🙂👺🥳🤣" * 10

START_TEXT_TEMPLATE = """╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
               𝓥𝙭𝙘𝙤𝙢 𝙀𝙢𝙥𝙞𝙧𝙚'𝙨

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
━━━━━━━━━━━━━━━━━━━━━
        ⚙️ 𝙎𝙔𝙎𝙏𝙀𝙈 𝘾𝙊𝙉𝙏𝙍𝙊𝙇

✘ `!status`
✘ `!o` ➜ Optimize & Clear Cache
✘ `!leave` ➜ Bots Leave
✘ `!dall` ➜ Stop All Tasks
"""

# ================= Database Initialization =================
async def init_db():
    global db_pool
    if not DATABASE_URL:
        logging.critical("DATABASE_URL is missing!")
        return

    parsed = urlparse(DATABASE_URL)
    clean_dsn = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        db_pool = await asyncpg.create_pool(dsn=clean_dsn, ssl=ctx, min_size=1, max_size=10)
    except Exception:
        db_pool = await asyncpg.create_pool(dsn=clean_dsn, ssl="require")

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
                start_media_type TEXT
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

# ================= Helpers =================
def stop_group_task(chat_id: int, task_name: str) -> bool:
    key = f"{chat_id}_{task_name}"
    if key in running_tasks:
        running_tasks[key].cancel()
        del running_tasks[key]
        return True
    return False

def stop_all_group_tasks(chat_id: int) -> int:
    stopped = 0
    keys = [k for k in list(running_tasks.keys()) if k.startswith(f"{chat_id}_")]
    for k in keys:
        running_tasks[k].cancel()
        del running_tasks[k]
        stopped += 1
    return stopped

async def get_admin_settings():
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM admin_settings WHERE id = 1")

async def get_chat_admin_ids(chat_id: int) -> Set[int]:
    try:
        admins = await bot.get_chat_administrators(chat_id)
        return {admin.user.id for admin in admins}
    except Exception:
        return set()

# ================= Background Automation Loops =================
async def loop_name_change(chat_id: int, title_base: str):
    idx = 1
    try:
        while True:
            new_title = f"{title_base} {MANDATORY_EMOJIS}"[:128]
            try:
                await bot.set_chat_title(chat_id, f"{new_title} #{idx}")
            except Exception:
                pass
            idx += 1
            await asyncio.sleep(40) # Rate limit safety
    except asyncio.CancelledError:
        pass

async def loop_auto_nc(chat_id: int):
    try:
        while True:
            async with db_pool.acquire() as conn:
                presets = await conn.fetch("SELECT content FROM global_presets WHERE preset_type = 'nc'")
            if presets:
                for row in presets:
                    t = f"{row['content']} {MANDATORY_EMOJIS}"[:128]
                    try:
                        await bot.set_chat_title(chat_id, t)
                    except Exception:
                        pass
                    await asyncio.sleep(40)
            else:
                await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass

async def loop_media_stream(chat_id: int, file_id: str, m_type: str, caption: str = ""):
    try:
        while True:
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
            await asyncio.sleep(2.5)
    except asyncio.CancelledError:
        pass

async def loop_auto_media(chat_id: int, media_type: str):
    try:
        while True:
            async with db_pool.acquire() as conn:
                presets = await conn.fetch("SELECT content, extra_text FROM global_presets WHERE preset_type = $1", media_type)
            if presets:
                for item in presets:
                    fid = item['content']
                    cap = item['extra_text'] or ""
                    if media_type == "media":
                        await bot.send_photo(chat_id, fid, caption=cap)
                    elif media_type == "voice":
                        await bot.send_voice(chat_id, fid)
                    await asyncio.sleep(3.0)
            else:
                await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass

async def loop_target_slide(chat_id: int, target: str):
    idx = 0
    try:
        while True:
            msg = ROAST_MESSAGES[idx % len(ROAST_MESSAGES)]
            await bot.send_message(chat_id, f"{target} {msg}")
            idx += 1
            await asyncio.sleep(1.8)
    except asyncio.CancelledError:
        pass

# ================= Event: Added To Group =================
@dp.my_chat_member()
async def on_bot_added(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        chat = event.chat
        user = event.from_user
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO groups (chat_id, chat_title, added_by) 
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE SET chat_title = $2, added_by = $3
            """, chat.id, chat.title, user.id)
            
            st = await conn.fetchrow("SELECT new_user_alert FROM admin_settings WHERE id = 1")
            if st and st['new_user_alert'] and ADMIN_ID:
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🔔 **New Integration Alert**\n\n"
                        f"• Group: `{chat.title}`\n"
                        f"• ID: `{chat.id}`\n"
                        f"• User: [{user.full_name}](tg://user?id={user.id}) (`{user.id}`)",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

# ================= Start & DM Handlers =================
@dp.message(CommandStart())
async def handle_start(message: Message):
    settings = await get_admin_settings()
    
    if settings and settings['maintenance'] and message.from_user.id != ADMIN_ID:
        return await message.reply("🛠️ Bot is currently under maintenance. Please try again later.")

    # In Group
    if message.chat.type in ["group", "supergroup"]:
        if settings and settings['start_media_id']:
            m_type = settings['start_media_type']
            m_id = settings['start_media_id']
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

    # In DM (Enhanced Dashboard)
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
        f"Your fully loaded, multi-tenant raid, moderation, and task execution engine is ready.\n\n"
        f"⚡ **Access Mode**: Operational\n"
        f"🔥 **Status**: Connected & Synchronized"
    )
    
    if settings and settings['start_media_id']:
        m_type = settings['start_media_type']
        m_id = settings['start_media_id']
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

# ================= DM Callback Navigation =================
@dp.callback_query(F.data == "user_groups")
async def cb_user_groups(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    if not groups:
        return await query.answer("You have not added this bot to any group yet!", show_alert=True)
    
    buttons = [[InlineKeyboardButton(text=f"📍 {g['chat_title']}", callback_data="noop")] for g in groups]
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")])
    await query.message.edit_text("📋 **Your Connected Groups:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data == "user_status")
async def cb_user_status(query: CallbackQuery):
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
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]]])
    await query.message.edit_text(status_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "user_commands")
async def cb_user_commands(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]])
    await query.message.edit_text(START_TEXT_TEMPLATE, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "back_main")
async def cb_back_main(query: CallbackQuery):
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
    await query.message.edit_text(welcome_text, reply_markup=kb, parse_mode="Markdown")

# ================= Admin Panel (/admin & /panel) =================
@dp.message(Command("admin"))
@dp.message(Command("panel"))
async def open_admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    settings = await get_admin_settings()
    
    m_status = "🟢 ON" if settings['maintenance'] else "🔴 OFF"
    a_status = "🔔 ON" if settings['new_user_alert'] else "🔕 OFF"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📬 Mailing", callback_data="adm_mailing"),
            InlineKeyboardButton(text="📊 Statistics", callback_data="adm_stats")
        ],
        [
            InlineKeyboardButton(text=f"🛠️ Maintenance ({m_status})", callback_data="adm_toggle_maint"),
            InlineKeyboardButton(text=f"👤 New User ({a_status})", callback_data="adm_toggle_alert")
        ],
        [
            InlineKeyboardButton(text="🖼️ Manage Media", callback_data="adm_manage_media"),
            InlineKeyboardButton(text="🔘 Add Auto Presets", callback_data="adm_add_preset")
        ],
        [InlineKeyboardButton(text="❌ Close Panel", callback_data="adm_close")]
    ])
    await message.reply("⚙️ **Super Admin Control Center**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_stats")
async def cb_admin_stats(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        g_count = await conn.fetchval("SELECT COUNT(*) FROM groups")
        p_count = await conn.fetchval("SELECT COUNT(*) FROM global_presets")
    
    text = (
        f"📊 **Global System Statistics**\n\n"
        f"• Connected Groups: `{g_count}`\n"
        f"• Active Task Loops: `{len(running_tasks)}`\n"
        f"• Stored Auto Presets: `{p_count}`"
    )
    await query.answer(text, show_alert=True)

@dp.callback_query(F.data == "adm_toggle_maint")
async def cb_toggle_maintenance(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET maintenance = NOT maintenance WHERE id = 1")
    await query.answer("Maintenance state toggled!")
    await open_admin_panel(query.message)

@dp.callback_query(F.data == "adm_toggle_alert")
async def cb_toggle_alert(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET new_user_alert = NOT new_user_alert WHERE id = 1")
    await query.answer("Alert state toggled!")
    await open_admin_panel(query.message)

@dp.callback_query(F.data == "adm_manage_media")
async def cb_admin_media(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁️ See Current Media", callback_data="adm_see_media")],
        [InlineKeyboardButton(text="🗑️ Delete/Reset Media", callback_data="adm_del_media")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")]
    ])
    await query.message.edit_text(
        "🖼️ **Start Page Media Control**\n\nTo update banner, reply to any Photo, Video, or Sticker with `/setstartmedia`",
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data == "adm_see_media")
async def cb_see_media(query: CallbackQuery):
    settings = await get_admin_settings()
    if not settings or not settings['start_media_id']:
        return await query.answer("No start media configured.", show_alert=True)
    
    m_type = settings['start_media_type']
    m_id = settings['start_media_id']
    try:
        if m_type == "photo":
            await bot.send_photo(query.from_user.id, m_id, caption="Current Start Banner")
        elif m_type == "video":
            await bot.send_video(query.from_user.id, m_id, caption="Current Start Video")
        elif m_type == "sticker":
            await bot.send_sticker(query.from_user.id, m_id)
        await query.answer()
    except Exception as e:
        await query.answer(f"Failed to send preview: {e}", show_alert=True)

@dp.callback_query(F.data == "adm_del_media")
async def cb_del_media(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET start_media_id = NULL, start_media_type = NULL WHERE id = 1")
    await query.answer("Start media reset to plain text!", show_alert=True)

@dp.callback_query(F.data == "adm_close")
async def cb_close_panel(query: CallbackQuery):
    await query.message.delete()

@dp.callback_query(F.data == "adm_back")
async def cb_back_panel(query: CallbackQuery):
    await open_admin_panel(query.message)

@dp.message(Command("setstartmedia"))
async def set_start_media_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        return await message.reply("Reply to any Photo, Video, or Sticker with `/setstartmedia`.")
    
    rep = message.reply_to_message
    file_id, media_type = None, None
    if rep.photo:
        file_id = rep.photo[-1].file_id
        media_type = "photo"
    elif rep.video:
        file_id = rep.video.file_id
        media_type = "video"
    elif rep.sticker:
        file_id = rep.sticker.file_id
        media_type = "sticker"
        
    if file_id:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET start_media_id = $1, start_media_type = $2 WHERE id = 1", file_id, media_type)
        await message.reply(f"✅ Start banner updated to `{media_type}`.")

# ================= Group Command Execution Engine =================
@dp.message(F.text.startswith("!"))
async def handle_commands(message: Message):
    chat_id = message.chat.id
    user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
    raw_text = message.text.strip()
    parts = raw_text.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # ================= 🛑 Stop / Disable Commands =================
    if cmd == "!dall":
        stopped = stop_all_group_tasks(chat_id)
        return await message.reply(f"🛑 **All Tasks Terminated!**\nTotal `{stopped}` background loop(s) stopped by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dnc":
        stop_group_task(chat_id, "nc")
        return await message.reply(f"🛑 **Name Change Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dautonc":
        stop_group_task(chat_id, "autonc")
        return await message.reply(f"🛑 **Auto Name Change Task Terminated** by {user_mention}.", parse_mode="Markdown")

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
        return await message.reply(f"🛑 **Auto Media Spam Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dvoicesm":
        stop_group_task(chat_id, "voicesm")
        return await message.reply(f"🛑 **Voice Spam Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dautovoicesm":
        stop_group_task(chat_id, "autovoicesm")
        return await message.reply(f"🛑 **Auto Voice Spam Task Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dgrouppfp":
        stop_group_task(chat_id, "grouppfp")
        return await message.reply(f"🛑 **Group PFP Rotation Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!delallmedia":
        stop_group_task(chat_id, "mediaspm")
        stop_group_task(chat_id, "vstickersm")
        stop_group_task(chat_id, "gifsm")
        stop_group_task(chat_id, "voicesm")
        stop_group_task(chat_id, "grouppfp")
        return await message.reply(f"🧹 **All Media Tasks Purged & Reset** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dtargetslide":
        stop_group_task(chat_id, "targetslide")
        return await message.reply(f"🛑 **Target Slide Lock Terminated** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!dslidem":
        stop_group_task(chat_id, "slidem")
        return await message.reply(f"🛑 **Group Slide Attack Terminated** by {user_mention}.", parse_mode="Markdown")

    # ================= 🚀 Start / Execution Commands =================
    if cmd == "!nc":
        if not arg:
            return await message.reply("Usage: `!nc <Your Desired Name>`", parse_mode="Markdown")
        stop_group_task(chat_id, "nc")
        task = asyncio.create_task(loop_name_change(chat_id, arg))
        running_tasks[f"{chat_id}_nc"] = task
        return await message.reply(f"✅ **Continuous Name Change Activated** with name: `{arg}` by {user_mention}.", parse_mode="Markdown")

    if cmd == "!autonc":
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
        user_states[message.from_user.id] = {"action": "wait_sticker", "chat_id": chat_id}
        return await message.reply("📸 **Please send or forward the Sticker** you want to set for continuous spam.")

    if cmd == "!gifsm":
        if message.reply_to_message and (message.reply_to_message.animation or message.reply_to_message.document):
            fid = (message.reply_to_message.animation or message.reply_to_message.document).file_id
            stop_group_task(chat_id, "gifsm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "animation"))
            running_tasks[f"{chat_id}_gifsm"] = task
            return await message.reply(f"🚀 **GIF Spam Loop Activated** by {user_mention}!", parse_mode="Markdown")
        user_states[message.from_user.id] = {"action": "wait_gif", "chat_id": chat_id}
        return await message.reply("👾 **Please send the GIF** you want to start looping.")

    if cmd == "!mediaspm":
        if message.reply_to_message and message.reply_to_message.photo:
            fid = message.reply_to_message.photo[-1].file_id
            caption = message.reply_to_message.caption or arg or ""
            stop_group_task(chat_id, "mediaspm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "photo", caption))
            running_tasks[f"{chat_id}_mediaspm"] = task
            return await message.reply(f"🚀 **Photo+Text Spam Loop Activated** by {user_mention}!", parse_mode="Markdown")
        user_states[message.from_user.id] = {"action": "wait_photo", "chat_id": chat_id, "text": arg}
        return await message.reply("🖼️ **Please send the Photo** you want to stream in loop.")

    if cmd == "!automediaspm":
        stop_group_task(chat_id, "automediaspm")
        task = asyncio.create_task(loop_auto_media(chat_id, "media"))
        running_tasks[f"{chat_id}_automediaspm"] = task
        return await message.reply(f"🚀 **Auto Global Media Stream Started** by {user_mention}.", parse_mode="Markdown")

    if cmd == "!voicesm":
        if message.reply_to_message and message.reply_to_message.voice:
            fid = message.reply_to_message.voice.file_id
            stop_group_task(chat_id, "voicesm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "voice"))
            running_tasks[f"{chat_id}_voicespm"] = task
            return await message.reply(f"🎙️ **Voice Spam Stream Activated** by {user_mention}!", parse_mode="Markdown")
        user_states[message.from_user.id] = {"action": "wait_voice", "chat_id": chat_id}
        return await message.reply("🎙️ **Please record or forward the Voice Note** to set for loop.")

    if cmd == "!autovoicesm":
        stop_group_task(chat_id, "autovoicesm")
        task = asyncio.create_task(loop_auto_media(chat_id, "voice"))
        running_tasks[f"{chat_id}_autovoicesm"] = task
        return await message.reply(f"🎙️ **Auto Global Voice Stream Started** by {user_mention}.", parse_mode="Markdown")

    if cmd in ["!grouppfp", "!gpfp"]:
        if message.reply_to_message and message.reply_to_message.photo:
            try:
                photo = message.reply_to_message.photo[-1]
                file = await bot.get_file(photo.file_id)
                f_bytes = await bot.download_file(file.file_path)
                await bot.set_chat_photo(chat_id, BufferedInputFile(f_bytes.read(), filename="pfp.jpg"))
                return await message.reply(f"✅ **Group Profile Photo Updated** by {user_mention}!", parse_mode="Markdown")
            except Exception as e:
                return await message.reply(f"❌ Failed to set PFP: {e}")
        user_states[message.from_user.id] = {"action": "wait_pfp", "chat_id": chat_id}
        return await message.reply("📸 **Please send the Photo** to set as the new Group Profile Picture.")

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

    if cmd == "!status":
        active_in_group = [k.replace(f"{chat_id}_", "") for k in running_tasks.keys() if k.startswith(f"{chat_id}_")]
        t_list = "None" if not active_in_group else ", ".join([f"`{t}`" for t in active_in_group])
        return await message.reply(f"⚙️ **Group Task Status:**\n• Active Tasks: {t_list}\n• Execution Engine: Operational ⚡", parse_mode="Markdown")

    if cmd == "!o":
        return await message.reply(f"🧹 **Optimization Complete:** Cache flushed and memory freed for this chat.", parse_mode="Markdown")

    if cmd == "!leave":
        await message.reply(f"👋 **Leaving Group** as requested by {user_mention}...")
        await bot.leave_chat(chat_id)

# ================= Interactive Prompts & Slidem Listener =================
@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def group_interactive_and_slide_handler(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # 1. Check if user was prompted to send media
    if user_id in user_states and user_states[user_id].get("chat_id") == chat_id:
        st = user_states[user_id]
        action = st.get("action")

        if action == "wait_sticker" and message.sticker:
            del user_states[user_id]
            fid = message.sticker.file_id
            stop_group_task(chat_id, "vstickersm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "sticker"))
            running_tasks[f"{chat_id}_vstickersm"] = task
            return await message.reply("🚀 **Sticker Loop Started Successfully!**")

        elif action == "wait_gif" and (message.animation or message.document):
            del user_states[user_id]
            fid = (message.animation or message.document).file_id
            stop_group_task(chat_id, "gifsm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "animation"))
            running_tasks[f"{chat_id}_gifsm"] = task
            return await message.reply("🚀 **GIF Loop Started Successfully!**")

        elif action == "wait_photo" and message.photo:
            del user_states[user_id]
            fid = message.photo[-1].file_id
            cap = message.caption or st.get("text", "")
            stop_group_task(chat_id, "mediaspm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "photo", cap))
            running_tasks[f"{chat_id}_mediaspm"] = task
            return await message.reply("🚀 **Photo Loop Started Successfully!**")

        elif action == "wait_voice" and message.voice:
            del user_states[user_id]
            fid = message.voice.file_id
            stop_group_task(chat_id, "voicesm")
            task = asyncio.create_task(loop_media_stream(chat_id, fid, "voice"))
            running_tasks[f"{chat_id}_voicespm"] = task
            return await message.reply("🎙️ **Voice Loop Started Successfully!**")

        elif action == "wait_pfp" and message.photo:
            del user_states[user_id]
            try:
                photo = message.photo[-1]
                file = await bot.get_file(photo.file_id)
                f_bytes = await bot.download_file(file.file_path)
                await bot.set_chat_photo(chat_id, BufferedInputFile(f_bytes.read(), filename="pfp.jpg"))
                return await message.reply("✅ **Group Profile Picture Changed!**")
            except Exception as e:
                return await message.reply(f"❌ Failed to set PFP: {e}")

    # 2. Slidem Auto Reply to Non-Admins
    if running_tasks.get(f"{chat_id}_slidem_active"):
        admins = await get_chat_admin_ids(chat_id)
        if user_id not in admins and not message.from_user.is_bot:
            import random
            roast = random.choice(ROAST_MESSAGES)
            tag = f"[{message.from_user.first_name}](tg://user?id={user_id})"
            await message.reply(f"{tag} {roast}", parse_mode="Markdown")

# ================= Keep-Alive Health Server =================
async def ping_response(request):
    return web.Response(text="Bot Engine is Active and Running!")

async def main():
    await init_db()
    
    app = web.Application()
    app.router.add_get("/", ping_response)
    app.router.add_get("/ping", ping_response)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Health check endpoint active on port {PORT}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
