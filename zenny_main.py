import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
import logging
from collections import deque
from dotenv import load_dotenv
from zenny_server import keep_alive

# Load environment variables
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('zenny_bot')

def parse_allowed_channel_ids(value):
    if not value:
        return []
    return [int(item.strip()) for item in value.split(',') if item.strip().isdigit()]

ALLOWED_CHANNEL_IDS = parse_allowed_channel_ids(os.getenv('ALLOWED_CHANNEL_IDS', ''))

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Music Queue System
song_queue = deque()

# yt-dlp options for high performance and reliability
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
    'source_address': '0.0.0.0',
    'extract_flat': 'in_playlist',  # Faster extraction
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
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in data:
                data = data['entries'][0]
            
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            logger.error(f"Error extracting info: {e}")
            raise

@bot.check
async def is_in_allowed_channel(ctx):
    if not ALLOWED_CHANNEL_IDS or ctx.channel.id in ALLOWED_CHANNEL_IDS:
        return True
    return False

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('Zenny Bot is ready!')

async def play_next(ctx):
    if len(song_queue) > 0:
        url = song_queue.popleft()
        async with ctx.typing():
            try:
                player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: bot.loop.create_task(play_next(ctx)))
                await ctx.send(f'🎵 กำลังเล่น: **{player.title}**')
            except Exception as e:
                await ctx.send(f"❌ เกิดข้อผิดพลาด: {e}")
                bot.loop.create_task(play_next(ctx))
    else:
        # Optional: auto disconnect after some time
        pass

@bot.command()
async def play(ctx, *, url):
    """เล่นเพลงจาก URL หรือชื่อเพลง"""
    if not ctx.message.author.voice:
        return await ctx.send("คุณต้องเข้าไปใน Voice Channel ก่อนครับ!")

    if not ctx.voice_client:
        await ctx.message.author.voice.channel.connect()

    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        song_queue.append(url)
        await ctx.send(f"➕ เพิ่มเพลงเข้าคิวแล้ว (ลำดับที่ {len(song_queue)})")
    else:
        song_queue.append(url)
        await play_next(ctx)

@bot.command()
async def skip(ctx):
    """ข้ามเพลง"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ ข้ามเพลงเรียบร้อยครับ")

@bot.command()
async def pause(ctx):
    """หยุดชั่วคราว"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ หยุดเพลงแล้ว")

@bot.command()
async def resume(ctx):
    """เล่นต่อ"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ เล่นเพลงต่อ")

@bot.command()
async def stop(ctx):
    """หยุดและออกจากห้อง"""
    song_queue.clear()
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 บ๊ายบาย!")

if __name__ == "__main__":
    keep_alive()
    token = os.getenv('TOKEN')
    if not token:
        logger.error("TOKEN NOT FOUND")
        exit(1)
    bot.run(token)
