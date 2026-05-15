# 🎵 Discord Music Bot (Lavalink Edition)

Discord music bot ที่ใช้ **Lavalink** แก้ปัญหา YouTube บล็อก IP ของ cloud hosting

## ✨ ข้อดีของเวอร์ชันนี้

- ✅ **ไม่โดน YouTube บล็อก** เพราะใช้ Lavalink server เป็นตัวกลาง
- ✅ **คุณภาพเสียงดีกว่า** yt-dlp
- ✅ **ไม่ต้องใช้ FFmpeg** บน Render ทำให้ deploy เร็วและกินทรัพยากรน้อยลง
- ✅ **รองรับ Playlist** ของ YouTube/SoundCloud

## 📋 คำสั่งทั้งหมด

| คำสั่ง | คำอธิบาย |
|--------|----------|
| `!play [เพลง/Link]` | เล่นเพลงจาก YouTube/SoundCloud |
| `!queue` | ดูคิวเพลง |
| `!skip` | ข้ามเพลงปัจจุบัน |
| `!stop` | หยุดเล่นและเคลียร์คิว |
| `!pause` | หยุดเพลงชั่วคราว |
| `!resume` | เล่นเพลงต่อ |
| `!kick` | เตะบอทออกจาก channel |
| `!help` | แสดงคำสั่งทั้งหมด |

---

## 🚀 ขั้นตอน Deploy บน Render.com

### ขั้นที่ 1: สร้าง Discord Bot (ถ้ายังไม่มี)

ทำตามขั้นตอนเดิมที่เคยทำ (เปิด MESSAGE CONTENT INTENT, สร้าง invite URL, เชิญบอท)

### ขั้นที่ 2: หา Lavalink Server ฟรี

📂 **ดูไฟล์ `LAVALINK_SERVERS.md`** มีรายการเซิร์ฟเวอร์ฟรีและวิธีหา

โดยสรุป: ไปที่ https://lavalink-list.appujet.site/ → เลือก server **v4** ที่ online → จดค่า Host, Port, Password ไว้

### ขั้นที่ 3: Push Code ขึ้น GitHub

อัพไฟล์ทั้งหมดในโฟลเดอร์นี้ขึ้น repo เดิม (หรือสร้างใหม่ก็ได้)

### ขั้นที่ 4: ตั้งค่า Environment Variables บน Render

ไปที่ service → แท็บ **Environment** เพิ่ม:

| Key | Value | คำอธิบาย |
|-----|-------|----------|
| `TOKEN` | `xxx` | Discord Bot Token |
| `ALLOWED_CHANNEL_IDS` | `123456...` | Channel ID ที่ใช้ได้ (เว้นว่าง = ทุก channel) |
| `LAVALINK_HOST` | `lavalink.xxx.net` | Host ของ Lavalink |
| `LAVALINK_PORT` | `2333` | Port ของ Lavalink |
| `LAVALINK_PASSWORD` | `youshallnotpass` | Password ของ Lavalink |
| `LAVALINK_SECURE` | `false` | `true` ถ้า SSL, `false` ถ้าไม่ใช่ |

### ขั้นที่ 5: รอ Deploy เสร็จ

Render จะ auto-redeploy ดู log ควรเห็น:
```
✅ Bot ออนไลน์: <ชื่อบอท>
🔗 กำลังเชื่อมต่อ Lavalink: http://...
✅ เชื่อมต่อ Lavalink สำเร็จ
🎵 Lavalink Node "MAIN" พร้อมใช้งาน
```

ถ้าเห็นทั้งหมดนี้ = พร้อมใช้งานแล้ว! ลอง `!play` ได้เลย

### ขั้นที่ 6: ตั้ง UptimeRobot (ป้องกัน Render sleep)

ทำตามวิธีเดิมที่เคยทำ → ตั้ง URL ของบอทใน UptimeRobot ping ทุก 5 นาที

---

## ⚠️ Troubleshooting

### ❌ Lavalink เชื่อมต่อไม่ได้

ดูใน log ว่าขึ้น error อะไร:

- **Authentication failed** → `LAVALINK_PASSWORD` ผิด
- **Connection refused** / **Timeout** → server ปิดแล้ว ลองตัวอื่น
- **SSL error** → ตั้ง `LAVALINK_SECURE` ไม่ตรงกับ server (ลองเปลี่ยน `true`↔`false`)

วิธีแก้: เปิดดู `LAVALINK_SERVERS.md` แล้วลองเซิร์ฟเวอร์อื่น

### ❌ ไม่พบเพลง

- ส่วนใหญ่เป็นเพราะ Lavalink server ไม่รองรับ YouTube → ลองตัวอื่น
- หรือลอง search keyword แทน link

### ❌ บอทไม่เข้า voice channel

- เช็ค bot permissions: Connect, Speak
- เช็คว่า Lavalink เชื่อมต่อสำเร็จก่อน (ดู log)

---

## 💻 รันในเครื่อง (Optional)

```bash
pip install -r requirements.txt
cp .env.example .env
# แก้ค่าใน .env
python bot.py
```
