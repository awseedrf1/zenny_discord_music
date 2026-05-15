import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import os

from zenny_server import keep_alive  # นำเข้า Flask app จากไฟล์ zenny_server.py

# ==========================================
# ใส่ ID ของ Channel ที่ต้องการให้บอททำงาน
# ถ้าอยากให้บอททำงานได้ทุก Channel ให้เว้น ALLOWED_CHANNEL_IDS ว่างไว้
# วิธีเอา ID: เปิด Discord Settings > Advanced > เปิด Developer Mode
# แล้วคลิกขวาที่ชื่อ Channel เลือก "Copy Channel ID"
# ==========================================

def parse_allowed_channel_ids(value):
    ids = []
    for item in value.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError:
            continue
    return ids

ALLOWED_CHANNEL_IDS = parse_allowed_channel_ids(os.getenv('ALLOWED_CHANNEL_IDS', ''))

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ฟังก์ชันตรวจสอบ Channel (Global Check)
@bot.check
async def is_in_allowed_channel(ctx):
    if not ALLOWED_CHANNEL_IDS or ctx.channel.id in ALLOWED_CHANNEL_IDS:
        return True
    # ถ้าพิมพ์ผิด Channel บอทจะไม่ตอบโต้ (หรือจะให้ส่งข้อความเตือนก็ได้)
    return False

# ตั้งค่า yt-dlp สำหรับการสตรีมเสียง
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # ใช้ผลลัพธ์แรกจากการค้นหา
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    print('Bot is ready to play music! Use !play <song name/url>')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        if ALLOWED_CHANNEL_IDS:
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะใน Channel ที่กำหนดเท่านั้นครับ")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ โปรดระบุชื่อเพลงหรือ URL ด้วย เช่น `!play <song name/url>`")
        return
    raise error

@bot.command()
async def join(ctx):
    """ให้ Bot เข้ามาใน Voice Channel ที่คุณอยู่"""
    if not ctx.message.author.voice:
        await ctx.send("คุณต้องเข้าไปใน Voice Channel ก่อนครับ!")
        return
    
    channel = ctx.message.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()

@bot.command()
async def play(ctx, *, url):
    """เล่นเพลงจาก URL หรือชื่อเพลง (เช่น !play รักติดไซเรน)"""
    if not ctx.voice_client:
        await ctx.invoke(join)

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
            await ctx.send(f'🎵 กำลังเล่น: **{player.title}**')
        except Exception as e:
            await ctx.send(f"❌ เกิดข้อผิดพลาด: {e}")

@bot.command()
async def pause(ctx):
    """หยุดเพลงชั่วคราว"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ หยุดเพลงชั่วคราวแล้วครับ")

@bot.command()
async def resume(ctx):
    """เล่นเพลงต่อ"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ เล่นเพลงต่อแล้วครับ")

@bot.command()
async def skip(ctx):
    """ข้ามเพลงที่กำลังเล่นอยู่"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ ข้ามเพลงเรียบร้อยครับ")

@bot.command()
async def stop(ctx):
    """หยุดเล่นและเตะ Bot ออกจากห้อง"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 ออกจากห้องเรียบร้อยครับ ขอบคุณที่ใช้บริการ zenny-music!")

if __name__ == "__main__":
    keep_alive()  # เรียกใช้ฟังก์ชันเพื่อเริ่ม Flask server
    token = os.getenv('TOKEN')
    if not token:
        raise RuntimeError('TOKEN environment variable is not set. โปรดตั้งค่า TOKEN ให้เรียบร้อยก่อนรันบอท')
    bot.run(token)
