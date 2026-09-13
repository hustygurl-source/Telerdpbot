# ⚡ Multi-Group Management & Automation Telegram Bot

Powerful Multi-Tenant Telegram Group Automation Bot with Super Admin Control Panel, User Dashboards, and PostgreSQL database support.

---

## 🚀 Features

* **Multi-Group Isolation:** Har group ka data aur task independent save hota hai.
* **Super Admin Control Center (`/panel`):**
  * Global Mailing/Broadcast
  * Start Banner Media Customization (Photo/Video/Sticker)
  * Bot Maintenance Mode & Alert System
  * Global Presets Manager for Auto Commands
* **Private User Dashboard (`/start` in DM):**
  * Added Groups list
  * Live status of running background tasks
  * Complete interactive Command Guide
* **Reply & Argument Command Parser:**
  * Direct execution: `!nc <name>`, `!slidespam <text>`
  * Contextual reply execution: `!mediaspm`, `!vstickersm`, `!voicesm`, `!grouppfp`
* **Task Management:** Individual task stop toggles (`!dnc`, `!dslidespam`) and global group kill switch (`!dall`).
* **Keep-Alive Server:** Built-in Aiohttp Web Server for 24/7 UptimeRobot monitoring on Render.

---

## 🛠️ Environment Variables

Render Dashboard me in variables ko configure karein:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Telegram Bot Token from @BotFather | `123456:ABC-DEF...` |
| `DATABASE_URL` | Neon PostgreSQL Connection URI | `postgresql://user:pass@ep-xyz.aws.neon.tech/neondb?sslmode=require` |
| `ADMIN_ID` | Super Admin Numeric Telegram User ID | `123456789` |
| `PORT` | Web Service Port (Render default) | `8080` |

---

## 📋 Group Commands Cheatsheet

### 🤍 Name Change (NC)
* `!nc <name>` ➜ Change group title instantly
* `!dnc` ➜ Stop/reset name change task
* `!autonc` ➜ Start name change loop from global presets
* `!dautonc` ➜ Stop auto name change

### 📸 Media & Stickers
* `!mediaspm` ➜ Reply to photo/video to start spam loop
* `!dmediaspm` ➜ Stop media spam loop
* `!vstickersm` ➜ Reply to sticker to start sticker loop
* `!dstickersm` ➜ Stop sticker loop
* `!voicesm` ➜ Reply to voice note to start loop
* `!dvoicesm` ➜ Stop voice loop
* `!grouppfp` / `!gpfp` ➜ Reply to photo to change group icon
* `!delallmedia` ➜ Delete saved media cache

### 💦 Slide & Target Spam
* `!targetslide <name>` ➜ Target specific user in chat
* `!dtargetslide` ➜ Stop target slide
* `!slidespam <text>` ➜ Start continuous text loop
* `!dslidespam` ➜ Stop text loop

### ⚙️ System Controls
* `!status` / `!ping` ➜ Check bot latency & health
* `!o` ➜ Clear cache and optimize memory
* `!leave` ➜ Bot leaves the current group
* `!dall` ➜ Force kill all active background tasks in the group

---

## 📦 Deployment Steps

1. **Database:** Create a database on [Neon.tech](https://neon.tech) and copy the PostgreSQL URI.
2. **Repository:** Push `bot.py`, `requirements.txt`, and `README.md` to a GitHub repository.
3. **Render Web Service:**
   * Link GitHub Repo.
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python bot.py`
   * Add Environment Variables (`BOT_TOKEN`, `DATABASE_URL`, `ADMIN_ID`, `PORT`).
4. **24/7 Uptime:** Setup an HTTP monitor on [UptimeRobot](https://uptimerobot.com) pointing to `https://your-app.onrender.com/ping` (5-minute interval).
