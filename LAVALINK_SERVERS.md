# 🎵 รายการ Lavalink Servers ฟรี

> ⚠️ **เซิร์ฟเวอร์ฟรีเหล่านี้อาจปิดได้ตลอดเวลา** ถ้าใช้ไม่ได้ ให้ลองตัวอื่นในรายการ หรือดู list ล่าสุดที่ลิงก์ด้านล่าง

## 📋 แหล่ง List ล่าสุด (อัพเดทตลอด)

### ⭐ แหล่งหลักที่แนะนำ

- **lavalink.darrennathanael.com** - https://lavalink.darrennathanael.com/NoSSL/lavalink-without-ssl
  - มี list อัพเดทอัตโนมัติ บอกสถานะ online/offline
  - มีทั้งแบบ SSL และ Non-SSL

- **lavalink-list.appujet.site** - https://lavalink-list.appujet.site/
  - หน้าเว็บดูสะดวก แสดง uptime และ ping

- **GitHub: appujet/lavalink-list** - https://github.com/appujet/lavalink-list
  - มี API ดึง list ได้ตรงๆ

## 🌐 ตัวอย่าง Server ที่ใช้ได้บ่อย (ลองทีละตัว)

> ค่าจริงในเซิร์ฟเวอร์ฟรีเปลี่ยนบ่อย — ใช้เป็นแค่ตัวอย่างวิธีกรอก ไม่การันตีว่ายังเปิดอยู่
> **แนะนำให้ไปดู list ล่าสุดจากลิงก์ด้านบนเสมอ**

### ตัวอย่างที่ 1 (Non-SSL)
```
LAVALINK_HOST=lavalink.jirayu.net
LAVALINK_PORT=13592
LAVALINK_PASSWORD=youshallnotpass
LAVALINK_SECURE=false
```

### ตัวอย่างที่ 2 (SSL)
```
LAVALINK_HOST=lava-v4.ajieblogs.eu.org
LAVALINK_PORT=443
LAVALINK_PASSWORD=https://dsc.gg/ajidevserver
LAVALINK_SECURE=true
```

### ตัวอย่างที่ 3
```
LAVALINK_HOST=lavalink-replit.kasi-kafa.repl.co
LAVALINK_PORT=443
LAVALINK_PASSWORD=https://dsc.gg/ajidevserver
LAVALINK_SECURE=true
```

## 🔧 วิธีหา server ที่ใช้งานได้

**ขั้นที่ 1:** เข้าไปที่ https://lavalink-list.appujet.site/

**ขั้นที่ 2:** มองหาเซิร์ฟเวอร์ที่:
- ✅ Status: **Online**
- ✅ Version: **v4** (สำคัญ! wavelink 3.x ต้องใช้ v4)
- ✅ Uptime สูง
- ✅ Ping ต่ำ (ใกล้เอเชียจะดี)

**ขั้นที่ 3:** คัดลอกค่ามาใส่ Environment Variables บน Render:
- `LAVALINK_HOST` - คือ Host
- `LAVALINK_PORT` - คือ Port
- `LAVALINK_PASSWORD` - คือ Password
- `LAVALINK_SECURE` - ใส่ `true` ถ้า SSL/HTTPS, `false` ถ้าไม่ใช่

**ขั้นที่ 4:** Render จะ auto-redeploy → ดู log ควรเห็น:
```
🔗 กำลังเชื่อมต่อ Lavalink: http://...
✅ เชื่อมต่อ Lavalink สำเร็จ
🎵 Lavalink Node "MAIN" พร้อมใช้งาน
```

## ⚠️ ถ้าเชื่อมต่อไม่ได้

1. ลองเซิร์ฟเวอร์อื่นในรายการ
2. เช็คว่าใช้ Lavalink **v4** (ไม่ใช่ v3)
3. ดู log ว่าขึ้น error อะไร เช่น:
   - `Authentication failed` → password ผิด
   - `Connection refused` → port ผิดหรือ server ปิด
   - `Timeout` → server ช้าหรือล่ม → เปลี่ยนตัว

## 💡 ทางเลือกอื่น

ถ้าทุก server ฟรีใช้ไม่ได้ หรืออยากเสถียร:

1. **โฮสต์ Lavalink เอง** บน Oracle Cloud Free Tier (ฟรีตลอด)
2. **ใช้ Railway** มี Lavalink template (เครดิตฟรี $5/เดือน)
3. **ใช้ replit + uptimerobot** (ฟรีแต่ไม่เสถียร)
