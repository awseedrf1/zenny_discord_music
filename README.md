# 🎵 Discord Music Bot

Discord bot สำหรับเล่นเพลงจาก YouTube พร้อม deploy บน Render.com

## ✨ ฟีเจอร์

- 🎵 เล่นเพลงจาก YouTube (ทั้งชื่อเพลงและลิงก์)
- 📜 จัดการคิวเพลง
- ⏭️ ข้ามเพลง / หยุดชั่วคราว / เล่นต่อ
- 👋 ออกจาก voice channel

## 📋 คำสั่งทั้งหมด

| คำสั่ง | คำอธิบาย |
|--------|----------|
| `!play [เพลง/Link]` | เล่นเพลงจาก YouTube |
| `!queue` | ดูคิวเพลง |
| `!skip` | ข้ามเพลงปัจจุบัน |
| `!stop` | หยุดเล่นและเคลียร์คิว |
| `!pause` | หยุดเพลงชั่วคราว |
| `!resume` | เล่นเพลงต่อ |
| `!kick` | เตะบอทออกจาก channel |
| `!help` | แสดงคำสั่งทั้งหมด |

---

## 🚀 ขั้นตอนการ Deploy บน Render.com

### ขั้นที่ 1: สร้าง Discord Bot

1. ไปที่ https://discord.com/developers/applications
2. คลิก **"New Application"** ตั้งชื่อบอท
3. ไปที่เมนู **"Bot"** → คลิก **"Reset Token"** → คัดลอก token เก็บไว้
4. เปิด Intents ทั้ง 3 ตัว:
   - ✅ **PRESENCE INTENT**
   - ✅ **SERVER MEMBERS INTENT**
   - ✅ **MESSAGE CONTENT INTENT**
5. ไปที่ **"OAuth2"** → **"URL Generator"**
   - Scopes: ติ๊ก `bot` และ `applications.commands`
   - Bot Permissions: ติ๊ก
     - `Send Messages`
     - `Embed Links`
     - `Read Message History`
     - `Connect`
     - `Speak`
     - `Use Voice Activity`
6. คัดลอก URL ด้านล่างไปเชิญบอทเข้า server

### ขั้นที่ 2: Push Code ขึ้น GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```

### ขั้นที่ 3: Deploy บน Render.com

1. ไปที่ https://render.com แล้ว Sign in ด้วย GitHub
2. คลิก **"New +"** → เลือก **"Web Service"**
3. เลือก repository ที่เพิ่ง push ขึ้นไป
4. ตั้งค่าดังนี้:
   - **Name**: `discord-music-bot` (หรืออะไรก็ได้)
   - **Region**: เลือกใกล้ที่สุด (Singapore สำหรับไทย)
   - **Branch**: `main`
   - **Runtime**: **Docker** (สำคัญ! ต้องเลือก Docker เพราะต้องใช้ FFmpeg)
   - **Instance Type**: `Free`

5. ไปที่หัวข้อ **Environment Variables** เพิ่ม:
   - Key: `TOKEN`
   - Value: token ที่คัดลอกมาจาก Discord Developer Portal
   - Key: `ALLOWED_CHANNEL_IDS` *(ไม่บังคับ)*
   - Value: Channel ID ที่จะอนุญาตให้ใช้คำสั่ง (เช่น `123456789012345678`) ถ้าต้องการหลาย channel ให้คั่นด้วย `,` เช่น `111,222,333` ถ้าเว้นว่าง = ใช้ได้ทุก channel

   **วิธีหา Channel ID**: เปิด Discord → Settings → Advanced → เปิด Developer Mode → คลิกขวาที่ text channel ที่ต้องการ → Copy Channel ID

6. คลิก **"Create Web Service"** รอประมาณ 5-10 นาที

### ขั้นที่ 4: ป้องกัน Render Sleep (สำคัญ!)

Render Free Plan จะ sleep บอทหลังไม่มี traffic 15 นาที วิธีแก้:

1. คัดลอก URL ของบอทจาก Render (เช่น `https://discord-music-bot.onrender.com`)
2. ไปที่ https://uptimerobot.com (ฟรี) สมัครและ login
3. คลิก **"+ Add New Monitor"**:
   - Monitor Type: `HTTP(s)`
   - Friendly Name: `Discord Bot`
   - URL: URL ของบอทจาก Render
   - Monitoring Interval: `5 minutes`
4. คลิก **"Create Monitor"**

ตอนนี้บอทจะออนไลน์ 24/7 แล้วครับ! 🎉

---

## 💻 รันในเครื่อง (Local Development)

```bash
# ติดตั้ง FFmpeg
# Windows: ดาวน์โหลดจาก https://ffmpeg.org/download.html
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg

# Clone และติดตั้ง
git clone <repo-url>
cd discord-music-bot
pip install -r requirements.txt

# สร้าง .env file
cp .env.example .env
# แล้วใส่ TOKEN ของคุณ

# รันบอท
python bot.py
```

---

## ⚠️ ข้อจำกัดของ Render Free Plan

- 750 ชั่วโมง/เดือน (พอใช้ตลอด 24/7 ถ้าใช้แค่ 1 service)
- RAM 512 MB
- จะ sleep หลัง 15 นาทีถ้าไม่มี traffic (แก้ด้วย UptimeRobot)

ถ้าบอทใช้งานหนัก แนะนำให้อัพเกรดเป็น Starter Plan ($7/เดือน)

## 🐛 Troubleshooting

**บอทไม่ได้พูด/เล่นเพลง**
- ตรวจสอบว่าเลือก Runtime เป็น **Docker** บน Render (ไม่ใช่ Python)
- ตรวจสอบ permissions ของบอทใน Discord (ต้องมี Connect และ Speak)

**บอทไม่ตอบคำสั่ง**
- ตรวจสอบว่าเปิด **MESSAGE CONTENT INTENT** แล้ว
- ตรวจสอบว่า TOKEN ถูกต้อง
- ถ้าตั้ง `ALLOWED_CHANNEL_IDS` ไว้ ตรวจสอบว่าพิมพ์คำสั่งใน channel ที่ถูกต้อง

**Error: ffmpeg not found**
- ใช้ Docker (มี FFmpeg อยู่แล้ว) ไม่ใช่ Native Python runtime
