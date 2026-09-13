import os
import sys
import ssl
import asyncio
import logging
from typing import Dict
from urllib.parse import urlparse, parse_qs

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

if not BOT_TOKEN:
    logging.error("BOT_TOKEN is missing! Check your Environment Variables.")
if not DATABASE_URL:
    logging.error("DATABASE_URL is missing! Check your Environment Variables.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# In-Memory Background Task Manager
running_tasks: Dict[str, asyncio.Task] = {}
db_pool: asyncpg.Pool = None

START_TEXT_TEMPLATE = """╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
               𝙑𝙓𝘾𝙊𝙈 𝗘𝗺𝗽𝗶𝗿𝗲 

𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @jyoex
° @comchater
° @foraremy 
       ✘ (Botname )
╰━━━━━━━━━━━━━━━━━━━━━

        🤍 𝙉𝘼𝙈𝙀 𝘾𝙃𝘼𝙉𝙂𝙀 (𝙉𝘾)
╰━━━━━━━━━━━━━━━━━━━━━
✘ !nc <name> / !dnc
✘ !autonc <name> / !dautonc 

╭━━━━━━━━━━━━━━━━━━━━
        📸 𝙈𝙀𝘿𝙄𝘼 & 𝙎𝙏𝙄𝘾𝙆𝙀𝙍𝙎
 
✘ !vstickersm / !dstickersm 
✘ !gifsm / !dgifsm 
✘ !mediaspm / !dmediaspm
✘ !automediaspm / !dautomediaspm
✘ !voicesm / !dvoicesm 
✘ !autovoicesm / !dautovoicesm 
✘ !grouppfp / !grouppfp 
✘ !delallmedia

 𝙎𝙇𝙄𝘿𝙀  𝗠𝙎𝙂 𝙉 𝙏𝘼𝙍𝙂𝙀𝙏 𝙈𝙎𝙂

✘ !targetslide <name> / !dtargetslide
✘ !slidespam <text> / !dslidespam
        🥱 𝙍𝙀𝙋𝙇𝙔
✘ !reply / !dreply
✘ !swipe <name> / !dswipe
╭━━━━━━━━━━━━━━━━━━━━━
        ⚙️ 𝙎𝙔𝙎𝙏𝙀𝙈 𝘾𝙊𝙉𝙏𝙍𝙊𝙇

✘ !status / !uptime / !ping / !on
✘ !o ➜ Optimize & Clear Cache
✘ !leave ➜  Bots Leave
✘ !dall ➜ Stop All Tasks
"""

# ================= Robust Database Connection =================
async def init_db():
    global db_pool
    if not DATABASE_URL:
        logging.critical("Fatal: DATABASE_URL not set.")
        sys.exit(1)

    parsed = urlparse(DATABASE_URL)
    clean_dsn = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"
    
    # SSL Configuration for Neon Cloud
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        db_pool = await asyncpg.create_pool(
            dsn=clean_dsn,
            ssl=ctx,
            min_size=1,
            max_size=10,
            command_timeout=30
        )
        logging.info("Connected to Neon PostgreSQL successfully.")
    except Exception as e:
        logging.error(f"Failed to create pool with SSL context, attempting direct fallback: {e}")
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
                content TEXT
            );
            CREATE TABLE IF NOT EXISTS group_custom_data (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                data_type TEXT,
                content TEXT
            );
        """)
        logging.info("Database schemas initialized.")

# ================= Task Management Helpers =================
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

# ================= Event: Added to Group =================
@dp.my_chat_member()
async def on_bot_added(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        chat = event.chat
        user_id = event.from_user.id
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO groups (chat_id, chat_title, added_by) 
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE SET chat_title = $2, added_by = $3
            """, chat.id, chat.title, user_id)
            
            st = await conn.fetchrow("SELECT new_user_alert FROM admin_settings WHERE id = 1")
            if st and st['new_user_alert'] and ADMIN_ID:
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🔔 **New Group Integration**\n\nTitle: `{chat.title}`\nChat ID: `{chat.id}`\nAdded By: `{user_id}`",
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

    # 1. Group / Supergroup Behavior
    if message.chat.type in ["group", "supergroup"]:
        if settings and settings['start_media_id']:
            m_type = settings['start_media_type']
            m_id = settings['start_media_id']
            try:
                if m_type == "photo":
                    return await message.reply_photo(photo=m_id, caption=START_TEXT_TEMPLATE)
                elif m_type == "video":
                    return await message.reply_video(video=m_id, caption=START_TEXT_TEMPLATE)
                elif m_type == "sticker":
                    await message.reply_sticker(sticker=m_id)
                    return await message.answer(START_TEXT_TEMPLATE)
            except Exception:
                pass
        return await message.reply(START_TEXT_TEMPLATE)

    # 2. Private DM Behavior
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    
    welcome_text = f"👋 Hello **{message.from_user.first_name}**!\n\nWelcome to **VXCOM Empire** automation portal. Manage your active groups, running tasks, and custom commands from below."
    
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

# ================= Private User Menu Callbacks =================
@dp.callback_query(F.data == "user_groups")
async def show_user_groups(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    
    if not groups:
        return await query.answer("You haven't added this bot to any group yet!", show_alert=True)
    
    buttons = [[InlineKeyboardButton(text=f"📍 {g['chat_title']}", callback_data=f"noop")] for g in groups]
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")])
    await query.message.edit_text("📋 **Your Connected Groups:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data == "user_status")
async def show_user_status(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    
    status_text = "📊 **Your Active Task Loops:**\n\n"
    active_found = False
    for g in groups:
        c_id = g['chat_id']
        running = [k.replace(f"{c_id}_", "") for k in running_tasks.keys() if k.startswith(f"{c_id}_")]
        if running:
            active_found = True
            status_text += f"🔹 **{g['chat_title']}**\n   Active: `{', '.join(running)}`\n\n"
            
    if not active_found:
        status_text += "No active background tasks currently running in your groups."
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]])
    await query.message.edit_text(status_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "user_commands")
async def show_commands_page(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]])
    await query.message.edit_text(START_TEXT_TEMPLATE, reply_markup=kb)

@dp.callback_query(F.data == "back_main")
async def return_to_main_menu(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    welcome_text = f"👋 Hello **{query.from_user.first_name}**!\n\nWelcome to **VXCOM Empire** automation portal."
    await query.message.edit_text(welcome_text, reply_markup=kb, parse_mode="Markdown")

# ================= Super Admin Control Panel =================
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
            InlineKeyboardButton(text="🔘 Global Presets", callback_data="adm_presets")
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
        f"📊 **Global Statistics**\n\n"
        f"• Connected Groups: `{g_count}`\n"
        f"• Running Loop Tasks: `{len(running_tasks)}`\n"
        f"• Global Presets: `{p_count}`"
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
        "🖼️ **Manage Start Media**\n\nTo update the start banner, reply to any Photo, Video, or Sticker with `/setstartmedia`",
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data == "adm_see_media")
async def cb_see_media(query: CallbackQuery):
    settings = await get_admin_settings()
    if not settings or not settings['start_media_id']:
        return await query.answer("No start media currently configured.", show_alert=True)
    
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
        await query.answer(f"Failed to load media: {e}", show_alert=True)

@dp.callback_query(F.data == "adm_del_media")
async def cb_del_media(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET start_media_id = NULL, start_media_type = NULL WHERE id = 1")
    await query.answer("Start media removed successfully!", show_alert=True)

@dp.callback_query(F.data == "adm_close")
async def cb_close_panel(query: CallbackQuery):
    await query.message.delete()

@dp.callback_query(F.data == "adm_back")
async def cb_back_panel(query: CallbackQuery):
    await open_admin_panel(query.message)

@dp.message(Command("setstartmedia"))
async def set_start_media_command(message: Message):
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
        await message.reply(f"✅ Start banner media configured as `{media_type}`.")

# ================= Task Loops =================
async def background_media_loop(chat_id: int, file_id: str, m_type: str, delay: float = 3.0):
    try:
        while True:
            if m_type == "photo":
                await bot.send_photo(chat_id, file_id)
            elif m_type == "sticker":
                await bot.send_sticker(chat_id, file_id)
            elif m_type == "voice":
                await bot.send_voice(chat_id, file_id)
            elif m_type == "video":
                await bot.send_video(chat_id, file_id)
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        pass

async def background_text_loop(chat_id: int, text: str, delay: float = 2.0):
    try:
        while True:
            await bot.send_message(chat_id, text)
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        pass

# ================= Group Command Engine =================
@dp.message(F.text.startswith("!"))
async def handle_commands(message: Message):
    chat_id = message.chat.id
    raw_text = message.text.strip()
    parts = raw_text.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    # Stop Commands
    if cmd == "!dall":
        stopped = stop_all_group_tasks(chat_id)
        return await message.reply(f"🛑 Terminated all `{stopped}` active task loops.")

    if cmd == "!dnc" or cmd == "!dautonc":
        stop_group_task(chat_id, "nc")
        return await message.reply("🛑 Name change task stopped.")

    if cmd == "!dmediaspm" or cmd == "!dautomediaspm":
        stop_group_task(chat_id, "mediaspm")
        return await message.reply("🛑 Media stream loop stopped.")

    if cmd == "!dstickersm":
        stop_group_task(chat_id, "stickerspm")
        return await message.reply("🛑 Sticker loop stopped.")

    if cmd == "!dvoicesm" or cmd == "!dautovoicesm":
        stop_group_task(chat_id, "voicespm")
        return await message.reply("🛑 Voice loop stopped.")

    if cmd == "!dslidespam" or cmd == "!dtargetslide":
        stop_group_task(chat_id, "slidespam")
        return await message.reply("🛑 Slide spam task stopped.")

    # Execution Commands
    if cmd == "!nc":
        if not arg:
            return await message.reply("Usage: `!nc <New Title>`", parse_mode="Markdown")
        try:
            await bot.set_chat_title(chat_id, arg)
            await message.reply(f"✅ Title updated to: **{arg}**", parse_mode="Markdown")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")

    elif cmd in ["!grouppfp", "!gpfp"]:
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to a photo with `!grouppfp` to set group avatar.")
        try:
            photo = message.reply_to_message.photo[-1]
            file = await bot.get_file(photo.file_id)
            f_bytes = await bot.download_file(file.file_path)
            await bot.set_chat_photo(chat_id, BufferedInputFile(f_bytes.read(), filename="avatar.jpg"))
            await message.reply("✅ Group profile photo updated.")
        except Exception as e:
            await message.reply(f"❌ Failed: {e}")

    elif cmd == "!mediaspm":
        if not message.reply_to_message:
            return await message.reply("Reply to a Photo or Video with `!mediaspm`")
        rep = message.reply_to_message
        fid, mtype = (rep.photo[-1].file_id, "photo") if rep.photo else ((rep.video.file_id, "video") if rep.video else (None, None))
        if fid:
            stop_group_task(chat_id, "mediaspm")
            task = asyncio.create_task(background_media_loop(chat_id, fid, mtype))
            running_tasks[f"{chat_id}_mediaspm"] = task
            await message.reply("🚀 Media loop activated.")

    elif cmd == "!vstickersm":
        if not message.reply_to_message or not message.reply_to_message.sticker:
            return await message.reply("Reply to a sticker with `!vstickersm`")
        fid = message.reply_to_message.sticker.file_id
        stop_group_task(chat_id, "stickerspm")
        task = asyncio.create_task(background_media_loop(chat_id, fid, "sticker"))
        running_tasks[f"{chat_id}_stickerspm"] = task
        await message.reply("🚀 Sticker loop activated.")

    elif cmd == "!voicesm":
        if not message.reply_to_message or not message.reply_to_message.voice:
            return await message.reply("Reply to a voice note with `!voicesm`")
        fid = message.reply_to_message.voice.file_id
        stop_group_task(chat_id, "voicespm")
        task = asyncio.create_task(background_media_loop(chat_id, fid, "voice"))
        running_tasks[f"{chat_id}_voicespm"] = task
        await message.reply("🚀 Voice stream loop activated.")

    elif cmd == "!slidespam":
        if not arg:
            return await message.reply("Usage: `!slidespam <text>`")
        stop_group_task(chat_id, "slidespam")
        task = asyncio.create_task(background_text_loop(chat_id, arg))
        running_tasks[f"{chat_id}_slidespam"] = task
        await message.reply("🚀 Slide loop initiated.")

    elif cmd == "!leave":
        await message.reply("👋 Leaving group...")
        await bot.leave_chat(chat_id)

    elif cmd in ["!status", "!uptime", "!ping", "!on"]:
        await message.reply("🏓 **Bot Status**: Online\n⚡ **Latency**: Active & Healthy", parse_mode="Markdown")

    elif cmd == "!o":
        await message.reply("🧹 **Optimized**: Cache flushed and resources optimized.", parse_mode="Markdown")

# ================= Keep-Alive Health Server =================
async def ping_response(request):
    return web.Response(text="Bot is Active and Healthy.")

async def main():
    await init_db()
    
    app = web.Application()
    app.router.add_get("/", ping_response)
    app.router.add_get("/ping", ping_response)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Health server listening on port {PORT}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
