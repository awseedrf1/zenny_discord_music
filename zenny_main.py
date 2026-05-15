import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from zenny_server import keep_alive

# ดึงข้อมูลจาก Environment Variable (Secrets ใน Replit)
TOKEN = os.environ.get('TOKEN')

# ดึง ID ของ Channel จาก Environment Variable (เช่น "123456789,987654321")
raw_channels = os.environ.get('ALLOWED_CHANNEL_IDS', '')
if raw_channels:
    try:
        # แปลงข้อความ "123,456" เป็น List ของตัวเลข [123, 456]
        ALLOWED_CHANNEL_IDS = [int(id.strip()) for id in raw_channels.split(',') if id.strip()]
    except ValueError:
        print("!!! ข้อผิดพลาด: ALLOWED_CHANNEL_IDS ใน Secrets รูปแบบไม่ถูกต้อง (ต้องเป็นตัวเลขคั่นด้วยคอมม่า) !!!")
        ALLOWED_CHANNEL_IDS = []
else:
    ALLOWED_CHANNEL_IDS = []

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.check
async def is_in_allowed_channel(ctx):
    if not ALLOWED_CHANNEL_IDS or ctx.channel.id in ALLOWED_CHANNEL_IDS:
        return True
    return False

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
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    print('Bot is ready on Replit!')

@bot.command()
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("คุณต้องเข้าห้องเสียงก่อน!")
        return
    channel = ctx.message.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()

@bot.command()
async def play(ctx, *, url):
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
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 บายครับ!")

# รันระบบ Keep Alive เพื่อไม่ให้ Replit หลับ
keep_alive()

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("!!! ไม่พบ TOKEN ใน Secrets (Environment Variables) !!!")
