import os
import asyncio
import logging
from typing import Dict, List
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, Message, FSInputFile
)
import asyncpg
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# ================= Configuration =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@host/db?sslmode=require")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789")) # Replace with your Telegram User ID
PORT = int(os.getenv("PORT", 8080))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "") # E.g., https://your-app.onrender.com

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Memory Task Manager for Async Background Loops
running_tasks: Dict[str, asyncio.Task] = {}
db_pool: asyncpg.Pool = None

START_TEXT_TEMPLATE = """╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
               𝙑𝙓𝘾𝙊𝙈 𝗘𝗺𝗽𝗶𝗿𝗲 

𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @jyoex
° @comchater
° @foraremy 
       ✘ (Botname)
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

# ================= Database Initialization =================
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
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

# ================= Helper Functions =================
async def get_admin_settings():
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM admin_settings WHERE id = 1")

def stop_group_task(chat_id: int, task_name: str):
    key = f"{chat_id}_{task_name}"
    if key in running_tasks:
        running_tasks[key].cancel()
        del running_tasks[key]
        return True
    return False

def stop_all_group_tasks(chat_id: int):
    stopped = 0
    keys = [k for k in running_tasks.keys() if k.startswith(f"{chat_id}_")]
    for k in keys:
        running_tasks[k].cancel()
        del running_tasks[k]
        stopped += 1
    return stopped

# ================= Group Tracking Middleware =================
@dp.my_chat_member()
async def on_bot_added_to_group(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        chat = event.chat
        user_id = event.from_user.id
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO groups (chat_id, chat_title, added_by) 
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE SET chat_title = $2, added_by = $3
            """, chat.id, chat.title, user_id)
            settings = await conn.fetchrow("SELECT new_user_alert FROM admin_settings WHERE id = 1")
            if settings and settings['new_user_alert']:
                await bot.send_message(
                    ADMIN_ID, 
                    f"🔔 **New Group Alert**\nTitle: {chat.title}\nID: `{chat.id}`\nAdded By: `{user_id}`",
                    parse_mode="Markdown"
                )

# ================= /start Command Handlers =================
@dp.message(CommandStart())
async def handle_start(message: Message):
    settings = await get_admin_settings()
    
    # Check Maintenance
    if settings['maintenance'] and message.from_user.id != ADMIN_ID:
        return await message.reply("🛠️ Bot is currently under maintenance. Please try again later.")
    
    # 1. Start in Group Chat
    if message.chat.type in ["group", "supergroup"]:
        if settings['start_media_id']:
            m_type = settings['start_media_type']
            if m_type == "photo":
                return await message.reply_photo(photo=settings['start_media_id'], caption=START_TEXT_TEMPLATE)
            elif m_type == "video":
                return await message.reply_video(video=settings['start_media_id'], caption=START_TEXT_TEMPLATE)
            elif m_type == "sticker":
                await message.reply_sticker(sticker=settings['start_media_id'])
                return await message.answer(START_TEXT_TEMPLATE)
        return await message.reply(START_TEXT_TEMPLATE)

    # 2. Start in Private DM Chat
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    
    welcome_dm = f"👋 Hello **{message.from_user.first_name}**!\nManage your integrated groups and commands from this control dashboard."
    
    if settings['start_media_id']:
        m_type = settings['start_media_type']
        if m_type == "photo":
            return await message.answer_photo(photo=settings['start_media_id'], caption=welcome_dm, reply_markup=kb, parse_mode="Markdown")
        elif m_type == "video":
            return await message.answer_video(video=settings['start_media_id'], caption=welcome_dm, reply_markup=kb, parse_mode="Markdown")
        elif m_type == "sticker":
            await message.answer_sticker(sticker=settings['start_media_id'])
            return await message.answer(welcome_dm, reply_markup=kb, parse_mode="Markdown")
            
    await message.answer(welcome_dm, reply_markup=kb, parse_mode="Markdown")

# ================= Private User Callbacks =================
@dp.callback_query(F.data == "user_groups")
async def show_user_groups(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    if not groups:
        return await query.answer("You haven't added this bot to any group yet!", show_alert=True)
    
    buttons = [[InlineKeyboardButton(text=f"📍 {g['chat_title']}", callback_data=f"grpinfo_{g['chat_id']}")] for g in groups]
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main")])
    await query.message.edit_text("📋 **Your Connected Groups:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data == "user_status")
async def show_user_status(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        groups = await conn.fetch("SELECT chat_id, chat_title FROM groups WHERE added_by = $1", query.from_user.id)
    
    status_text = "📊 **Your Active Tasks:**\n\n"
    active_found = False
    for g in groups:
        c_id = g['chat_id']
        active_in_group = [k.replace(f"{c_id}_", "") for k in running_tasks.keys() if k.startswith(f"{c_id}_")]
        if active_in_group:
            active_found = True
            status_text += f"🔹 **{g['chat_title']}**\n   Tasks: `{', '.join(active_in_group)}`\n"
            
    if not active_found:
        status_text += "No background tasks currently running in your groups."
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main")]])
    await query.message.edit_text(status_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "user_commands")
async def show_user_commands(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main")]])
    await query.message.edit_text(START_TEXT_TEMPLATE, reply_markup=kb)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Groups", callback_data="user_groups"),
            InlineKeyboardButton(text="📊 Status", callback_data="user_status")
        ],
        [InlineKeyboardButton(text="📜 Commands", callback_data="user_commands")]
    ])
    welcome_dm = f"👋 Hello **{query.from_user.first_name}**!\nManage your integrated groups and commands from this control dashboard."
    await query.message.edit_text(welcome_dm, reply_markup=kb, parse_mode="Markdown")

# ================= Super Admin Panel =================
@dp.message(Command("panel"))
async def open_admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    settings = await get_admin_settings()
    
    m_status = "🟢 ON" if settings['maintenance'] else "🔴 OFF"
    a_status = "🔔 ON" if settings['new_user_alert'] else "🔕 OFF"
    
    panel_kb = InlineKeyboardMarkup(inline_keyboard=[
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
    await message.reply("⚙️ **Super Admin Control Center**", reply_markup=panel_kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_stats")
async def admin_stats(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        g_count = await conn.fetchval("SELECT COUNT(*) FROM groups")
        p_count = await conn.fetchval("SELECT COUNT(*) FROM global_presets")
    active_loops = len(running_tasks)
    
    text = (
        f"📊 **Global Statistics**\n\n"
        f"• Total Groups: `{g_count}`\n"
        f"• Active Task Loops: `{active_loops}`\n"
        f"• Global Presets Loaded: `{p_count}`"
    )
    await query.answer(text, show_alert=True)

@dp.callback_query(F.data == "adm_toggle_maint")
async def toggle_maintenance(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET maintenance = NOT maintenance WHERE id = 1")
    await query.answer("Maintenance status toggled!")
    await open_admin_panel(query.message)

@dp.callback_query(F.data == "adm_toggle_alert")
async def toggle_alerts(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET new_user_alert = NOT new_user_alert WHERE id = 1")
    await query.answer("Alert status toggled!")
    await open_admin_panel(query.message)

@dp.callback_query(F.data == "adm_manage_media")
async def admin_media_manage(query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁️ See Current Media", callback_data="adm_see_media")],
        [InlineKeyboardButton(text="🗑️ Delete/Reset Media", callback_data="adm_del_media")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")]
    ])
    await query.message.edit_text(
        "🖼️ **Start Page Media Settings**\nTo change media, reply to any Photo/Video/Sticker with `/setstartmedia`", 
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data == "adm_see_media")
async def see_start_media(query: CallbackQuery):
    settings = await get_admin_settings()
    if not settings['start_media_id']:
        return await query.answer("No custom media set for Start Page!", show_alert=True)
    
    m_type = settings['start_media_type']
    if m_type == "photo":
        await bot.send_photo(query.from_user.id, settings['start_media_id'], caption="Current Start Banner")
    elif m_type == "video":
        await bot.send_video(query.from_user.id, settings['start_media_id'], caption="Current Start Video")
    elif m_type == "sticker":
        await bot.send_sticker(query.from_user.id, settings['start_media_id'])
    await query.answer()

@dp.callback_query(F.data == "adm_del_media")
async def delete_start_media(query: CallbackQuery):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admin_settings SET start_media_id = NULL, start_media_type = NULL WHERE id = 1")
    await query.answer("Start page media reset to plain text!", show_alert=True)

@dp.callback_query(F.data == "adm_close")
async def close_admin_panel(query: CallbackQuery):
    await query.message.delete()

@dp.callback_query(F.data == "adm_back")
async def back_to_admin_panel(query: CallbackQuery):
    await open_admin_panel(query.message)

@dp.message(Command("setstartmedia"))
async def set_start_media_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        return await message.reply("Reply to a photo, video, or sticker with `/setstartmedia`")
    
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
        await message.reply(f"✅ Start page media successfully updated as `{media_type}`!")

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

# ================= Command Engine =================
@dp.message(F.text.startswith("!"))
async def handle_prefixed_commands(message: Message):
    chat_id = message.chat.id
    raw_text = message.text.strip()
    parts = raw_text.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    
    # 1. Stop Handlers
    if cmd == "!dall":
        stopped = stop_all_group_tasks(chat_id)
        return await message.reply(f"🛑 Killed all `{stopped}` active background task(s).")
    
    if cmd == "!dnc":
        stop_group_task(chat_id, "nc")
        return await message.reply("🛑 Stopped Name Change task.")

    if cmd == "!dmediaspm":
        stop_group_task(chat_id, "mediaspm")
        return await message.reply("🛑 Stopped Media Spam task.")

    if cmd == "!dstickersm":
        stop_group_task(chat_id, "stickerspm")
        return await message.reply("🛑 Stopped Sticker Spam task.")

    if cmd == "!dvoicesm":
        stop_group_task(chat_id, "voicespm")
        return await message.reply("🛑 Stopped Voice Spam task.")

    if cmd == "!dslidespam":
        stop_group_task(chat_id, "slidespam")
        return await message.reply("🛑 Stopped Slide Spam task.")

    # 2. Execution Handlers
    if cmd == "!nc":
        if not arg:
            return await message.reply("Usage: `!nc <New Title>`", parse_mode="Markdown")
        try:
            await bot.set_chat_title(chat_id, arg)
            await message.reply(f"✅ Title changed to: **{arg}**", parse_mode="Markdown")
        except Exception as e:
            await message.reply(f"❌ Failed: {e}")

    elif cmd == "!grouppfp" or cmd == "!gpfp":
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to a photo with `!grouppfp`")
        try:
            photo = message.reply_to_message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_path = file.file_path
            f_bytes = await bot.download_file(file_path)
            await bot.set_chat_photo(chat_id, types.BufferedInputFile(f_bytes.read(), filename="pfp.jpg"))
            await message.reply("✅ Group PFP updated successfully!")
        except Exception as e:
            await message.reply(f"❌ Failed: {e}")

    elif cmd == "!mediaspm":
        if not message.reply_to_message:
            return await message.reply("Reply to any media with `!mediaspm`")
        rep = message.reply_to_message
        fid, mtype = None, None
        if rep.photo:
            fid, mtype = rep.photo[-1].file_id, "photo"
        elif rep.video:
            fid, mtype = rep.video.file_id, "video"
            
        if fid:
            stop_group_task(chat_id, "mediaspm")
            task = asyncio.create_task(background_media_loop(chat_id, fid, mtype))
            running_tasks[f"{chat_id}_mediaspm"] = task
            await message.reply("🚀 Media stream spam started!")

    elif cmd == "!vstickersm":
        if not message.reply_to_message or not message.reply_to_message.sticker:
            return await message.reply("Reply to a sticker with `!vstickersm`")
        fid = message.reply_to_message.sticker.file_id
        stop_group_task(chat_id, "stickerspm")
        task = asyncio.create_task(background_media_loop(chat_id, fid, "sticker"))
        running_tasks[f"{chat_id}_stickerspm"] = task
        await message.reply("🚀 Sticker loop initiated!")

    elif cmd == "!voicesm":
        if not message.reply_to_message or not message.reply_to_message.voice:
            return await message.reply("Reply to a voice message with `!voicesm`")
        fid = message.reply_to_message.voice.file_id
        stop_group_task(chat_id, "voicespm")
        task = asyncio.create_task(background_media_loop(chat_id, fid, "voice"))
        running_tasks[f"{chat_id}_voicespm"] = task
        await message.reply("🚀 Voice loop initiated!")

    elif cmd == "!slidespam":
        if not arg:
            return await message.reply("Usage: `!slidespam <text>`")
        stop_group_task(chat_id, "slidespam")
        task = asyncio.create_task(background_text_loop(chat_id, arg))
        running_tasks[f"{chat_id}_slidespam"] = task
        await message.reply("🚀 Slide spam task active!")

    elif cmd == "!leave":
        await message.reply("👋 Leaving group...")
        await bot.leave_chat(chat_id)

    elif cmd == "!ping" or cmd == "!status":
        await message.reply("🏓 **Bot Status**: Online\n⚡ **Latency**: Optimal", parse_mode="Markdown")

# ================= Aiohttp Webhook & Keep-Alive Server =================
async def ping_handler(request):
    return web.Response(text="Bot is Alive and Running!")

async def main():
    await init_db()
    
    app = web.Application()
    app.router.add_get("/", ping_handler)
    app.router.add_get("/ping", ping_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Health server listening on port {PORT}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

