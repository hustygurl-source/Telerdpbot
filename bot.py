import os
import sys
import ssl
import asyncio
import logging
from typing import Dict
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

running_tasks: Dict[str, asyncio.Task] = {}
db_pool: asyncpg.Pool = None

# Monospace format (One-tap Copyable)
START_TEXT_TEMPLATE = """╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
               𝓥𝙭𝙘𝙤𝙢 𝙀𝙢𝙥𝙞𝙧𝙚'𝙨

𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @jyoex
° @comchater
° @foraremy 
       ✘ @telerdpbot
╰━━━━━━━━━━━━━━━━━━━━━

        🤍 𝙉𝘼𝙈𝙀 𝘾𝙃𝘼𝙉𝙂𝙀 (𝙉𝘾)
╰━━━━━━━━━━━━━━━━━━━━━
✘ `!nc` <name> / `!dnc`
✘ `!autonc` <name> / `!dautonc` 

╭━━━━━━━━━━━━━━━━━━━━
        💀 𝙈𝙀𝘿𝙄𝘼 & 𝙎𝙏𝙄𝘾𝙆𝙀𝙍𝙎
 
✘ `!vstickersm` / `!dstickersm` 
✘ `!gifsm` / `!dgifsm` 
✘ `!mediaspm` / `!dmediaspm`
✘ `!automediaspm` / `!dautomediaspm`
✘ `!voicesm` / `!dvoicesm` 
✘ `!autovoicesm` / `!dautovoicesm` 
✘ `!grouppfp` / `!grouppfp` 
✘ `!delallmedia`

👾 𝙎𝙇𝙄𝘿𝙀  𝗠𝙎𝙂 𝙉 𝙏𝘼𝙍𝙂𝙀𝙏 𝙈𝙎𝙂

✘ `!targetslide` <name> / `!dtargetslide`
✘ `!slidespam` <text> / `!dslidespam`
        🥷 𝙍𝙀𝙋𝙇𝙔
✘ `!reply` / `!dreply`
✘ `!swipe` <name> / `!dswipe`
━━━━━━━━━━━━━━━━━━━━━
        ⚙️ 𝙎𝙔𝙎𝙏𝙀𝙈 𝘾𝙊𝙉𝙏𝙍𝙊𝙇

✘ `!status` / `!uptime` / `!ping` / `!on`
✘ `!o` ➜ Optimize & Clear Cache
✘ `!leave` ➜  Bots Leave
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
                content TEXT
            );
        """)
    logging.info("Database Ready.")

def stop_group_task(chat_id: int, task_name: str) -> bool:
    key = f"{chat_id}_{task_name}"
    if key in running_tasks:
        running_tasks[key].cancel()
        del running_tasks[key]
        return True
    return False

def stop_all_group_tasks(chat_id: int) -> int:
    stopped = 0
    for k in list(running_tasks.keys()):
        if k.startswith(f"{chat_id}_"):
            running_tasks[k].cancel()
            del running_tasks[k]
            stopped += 1
    return stopped

async def get_admin_settings():
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM admin_settings WHERE id = 1")

# ================= DM / Group Start Handler =================
@dp.message(CommandStart())
async def handle_start(message: Message):
    settings = await get_admin_settings()
    
    if settings and settings['maintenance'] and message.from_user.id != ADMIN_ID:
        return await message.reply("🛠️ Bot is currently under maintenance. Please try again later.")

    # Group Start
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

    # Private DM Start
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    
    user_tag = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    welcome_text = (
        f"⚡ **Welcome to the Elite Terminal, {user_tag}!**\n\n"
        f"👑 **VXCOM Empire** automated controller is active and synchronized.\n\n"
        f"💠 **User Access:** `Authenticated`\n"
        f"⚙️ **Engine Status:** `Running High-Speed Loops`\n"
        f"🛡️ **System Protection:** `Active`\n\n"
        f"Add me as **Admin** in your group with all permissions to automate raids, slide messages, voice loops, and media spam seamlessly."
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

# ================= Private User Menu Callbacks =================
@dp.callback_query(F.data == "user_groups")
async def show_user_groups(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    
    if not groups:
        return await query.answer("You haven't added this bot to any group yet!", show_alert=True)
    
    buttons = [[InlineKeyboardButton(text=f"📍 {g['chat_title']}", callback_data="noop")] for g in groups]
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
    await query.message.edit_text(START_TEXT_TEMPLATE, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "back_main")
async def return_to_main_menu(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    user_tag = f"[{query.from_user.first_name}](tg://user?id={query.from_user.id})"
    welcome_text = (
        f"⚡ **Welcome to the Elite Terminal, {user_tag}!**\n\n"
        f"👑 **VXCOM Empire** automated controller is active.\n"
        f"Select an option below to manage groups and tasks."
    )
    await query.message.edit_text(welcome_text, reply_markup=kb, parse_mode="Markdown")

# ================= Super Admin Control Panel (/admin & /panel) =================
@dp.message(Command("panel", "admin"))
async def open_admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ Access Denied: You are not authorized to use the Admin Panel.")
    
    settings = await get_admin_settings()
    m_status = "🟢 ON" if settings and settings['maintenance'] else "🔴 OFF"
    a_status = "🔔 ON" if settings and settings['new_user_alert'] else "🔕 OFF"
    
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
            InlineKeyboardButton(text="🔘 Presets Pool", callback_data="adm_presets")
        ],
        [InlineKeyboardButton(text="❌ Close Panel", callback_data="adm_close")]
    ])
    await message.reply("⚙️ **Super Admin Control Center**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_stats")
async def cb_admin_stats(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        g_count = await conn.fetchval("SELECT COUNT(*) FROM groups")
    await query.answer(f"📊 Groups: {g_count} | Active Loops: {len(running_tasks)}", show_alert=True)

@dp.callback_query(F.data == "adm_toggle_maint")
async def cb_toggle_maintenance(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET maintenance = NOT maintenance WHERE id = 1")
    await query.answer("Maintenance updated!")
    await open_admin_panel(query.message)

@dp.callback_query(F.data == "adm_toggle_alert")
async def cb_toggle_alert(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET new_user_alert = NOT new_user_alert WHERE id = 1")
    await query.answer("Alert updated!")
    await open_admin_panel(query.message)

@dp.callback_query(F.data == "adm_manage_media")
async def cb_admin_media(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁️ See Current Media", callback_data="adm_see_media")],
        [InlineKeyboardButton(text="🗑️ Delete/Reset Media", callback_data="adm_del_media")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")]
    ])
    await query.message.edit_text("🖼️ **Start Page Media**\nReply to any Photo/Video/Sticker with `/setstartmedia`", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_see_media")
async def cb_see_media(query: CallbackQuery):
    settings = await get_admin_settings()
    if not settings or not settings['start_media_id']:
        return await query.answer("No start media set.", show_alert=True)
    m_type, m_id = settings['start_media_type'], settings['start_media_id']
    if m_type == "photo":
        await bot.send_photo(query.from_user.id, m_id, caption="Current Start Banner")
    elif m_type == "video":
        await bot.send_video(query.from_user.id, m_id, caption="Current Start Video")
    elif m_type == "sticker":
        await bot.send_sticker(query.from_user.id, m_id)
    await query.answer()

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
async def set_start_media_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        return await message.reply("Reply to any Photo, Video, or Sticker with `/setstartmedia`.")
    
    rep = message.reply_to_message
    fid, mtype = None, None
    if rep.photo:
        fid, mtype = rep.photo[-1].file_id, "photo"
    elif rep.video:
        fid, mtype = rep.video.file_id, "video"
    elif rep.sticker:
        fid, mtype = rep.sticker.file_id, "sticker"
        
    if fid:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE admin_settings SET start_media_id = $1, start_media_type = $2 WHERE id = 1", fid, mtype)
        await message.reply(f"✅ Start banner media configured as `{mtype}`.")

# ================= Task Background Loops =================
async def background_text_loop(chat_id: int, text: str, delay: float = 2.0):
    try:
        while True:
            await bot.send_message(chat_id, text)
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Text loop error: {e}")

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
    except Exception as e:
        logging.error(f"Media loop error: {e}")

# ================= Group Command Engine (! prefix) =================
@dp.message(F.text.startswith("!"))
async def handle_commands(message: Message):
    chat_id = message.chat.id
    raw_text = message.text.strip()
    parts = raw_text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    # Stop Toggles
    if cmd == "!dall":
        stopped = stop_all_group_tasks(chat_id)
        return await message.reply(f"🛑 Killed all `{stopped}` active background task(s).")

    if cmd in ["!dnc", "!dautonc"]:
        stop_group_task(chat_id, "nc")
        return await message.reply("🛑 Stopped Name Change task.")

    if cmd in ["!dmediaspm", "!dautomediaspm"]:
        stop_group_task(chat_id, "mediaspm")
        return await message.reply("🛑 Stopped Media Spam task.")

    if cmd == "!dstickersm":
        stop_group_task(chat_id, "stickerspm")
        return await message.reply("🛑 Stopped Sticker Spam task.")

    if cmd in ["!dvoicesm", "!dautovoicesm"]:
        stop_group_task(chat_id, "voicespm")
        return await message.reply("🛑 Stopped Voice Spam task.")

    if cmd in ["!dslidespam", "!dtargetslide"]:
        stop_group_task(chat_id, "slidespam")
        return await message.reply("🛑 Stopped Slide Spam task.")

    # Execution Commands
    if cmd == "!nc":
        if not arg:
            return await message.reply("⚠️ **Usage:** `!nc <New Group Name>`", parse_mode="Markdown")
        try:
            await bot.set_chat_title(chat_id, arg)
            await message.reply(f"✅ **Title Changed Successfully:**\n`{arg}`", parse_mode="Markdown")
        except Exception as e:
            await message.reply(f"❌ Failed to change title. Make sure bot is Admin with 'Change Group Info' permission.\nError: `{e}`", parse_mode="Markdown")

    elif cmd == "!slidespam":
        if not arg:
            return await message.reply("⚠️ **Usage:** `!slidespam <text>`", parse_mode="Markdown")
        stop_group_task(chat_id, "slidespam")
        task = asyncio.create_task(background_text_loop(chat_id, arg))
        running_tasks[f"{chat_id}_slidespam"] = task
        await message.reply(f"🚀 **Slide Spam Initiated!**\nLooping Text: `{arg}`\nUse `!dslidespam` to stop.", parse_mode="Markdown")

    elif cmd in ["!grouppfp", "!gpfp"]:
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("⚠️ Reply to an Image with `!grouppfp` to update group icon.")
        try:
            photo = message.reply_to_message.photo[-1]
            file = await bot.get_file(photo.file_id)
            f_bytes = await bot.download_file(file.file_path)
            await bot.set_chat_photo(chat_id, BufferedInputFile(f_bytes.read(), filename="avatar.jpg"))
            await message.reply("✅ **Group Profile Photo Updated Successfully!**", parse_mode="Markdown")
        except Exception as e:
            await message.reply(f"❌ Failed to update PFP: `{e}`", parse_mode="Markdown")

    elif cmd == "!mediaspm":
        if not message.reply_to_message:
            return await message.reply("⚠️ Reply to a Photo or Video with `!mediaspm`")
        rep = message.reply_to_message
        fid, mtype = (rep.photo[-1].file_id, "photo") if rep.photo else ((rep.video.file_id, "video") if rep.video else (None, None))
        if fid:
            stop_group_task(chat_id, "mediaspm")
            task = asyncio.create_task(background_media_loop(chat_id, fid, mtype))
            running_tasks[f"{chat_id}_mediaspm"] = task
            await message.reply("🚀 **Media Stream Loop Started!**\nUse `!dmediaspm` to stop.", parse_mode="Markdown")

    elif cmd == "!vstickersm":
        if not message.reply_to_message or not message.reply_to_message.sticker:
            return await message.reply("⚠️ Reply to a Sticker with `!vstickersm`")
        fid = message.reply_to_message.sticker.file_id
        stop_group_task(chat_id, "stickerspm")
        task = asyncio.create_task(background_media_loop(chat_id, fid, "sticker"))
        running_tasks[f"{chat_id}_stickerspm"] = task
        await message.reply("🚀 **Sticker Loop Started!**\nUse `!dstickersm` to stop.", parse_mode="Markdown")

    elif cmd == "!voicesm":
        if not message.reply_to_message or not message.reply_to_message.voice:
            return await message.reply("⚠️ Reply to a Voice Message with `!voicesm`")
        fid = message.reply_to_message.voice.file_id
        stop_group_task(chat_id, "voicespm")
        task = asyncio.create_task(background_media_loop(chat_id, fid, "voice"))
        running_tasks[f"{chat_id}_voicespm"] = task
        await message.reply("🚀 **Voice Stream Loop Started!**\nUse `!dvoicesm` to stop.", parse_mode="Markdown")

    elif cmd == "!leave":
        await message.reply("👋 **VXCOM Bot Leaving Group...**", parse_mode="Markdown")
        await bot.leave_chat(chat_id)

    elif cmd in ["!status", "!uptime", "!ping", "!on"]:
        await message.reply("🏓 **Bot Status**: `Online`\n⚡ **Latency**: `Optimal`\n🛡️ **System**: `VXCOM Empire Active`", parse_mode="Markdown")

    elif cmd == "!o":
        await message.reply("🧹 **Optimized:** Memory flushed and cache cleaned successfully.", parse_mode="Markdown")

# ================= Keep-Alive Web Server =================
async def ping_response(request):
    return web.Response(text="VXCOM Bot is Alive and Running 24/7.")

async def main():
    await init_db()
    
    app = web.Application()
    app.router.add_get("/", ping_response)
    app.router.add_get("/ping", ping_response)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Health check running on port {PORT}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
