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

# Check for Voice Support
try:
    import nacl
    HAS_VOICE = True
except ImportError:
    HAS_VOICE = False
    logger.warning("PyNaCl is not installed. Voice support will not work!")

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

# yt-dlp options with "Voucher-style" custom identity bypass
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,  # Bypass SSL verification (like the PHP script)
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extract_flat': 'in_playlist',
    # Use high-trust clients
    'extractor_args': {
        'youtube': {
            'player_client': ['tvhtml5', 'android'],
            'skip': ['dash', 'hls']
        }
    },
    # Unique/Custom User-Agent to hide from simple bot-detectors
    'user_agent': 'Super-Idol-Music-Bot/1.0 (Zenny-Bot; YouTube-Bypass-Active)',
    'http_headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
    }
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
                logger.error(f"Error in play_next: {e}")
                await ctx.send(f"❌ เกิดข้อผิดพลาดในการเล่นเพลง: {e}")
                bot.loop.create_task(play_next(ctx))
    else:
        logger.info("Queue is empty.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งใน Channel นี้ครับ")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ โปรดระบุข้อมูลให้ครบถ้วน: {error.param.name}")
        return
    
    logger.error(f"Command Error: {error}")
    await ctx.send(f"❌ เกิดข้อผิดพลาด: {error}")

@bot.command()
async def join(ctx):
    """ให้ Bot เข้ามาใน Voice Channel"""
    if not ctx.author.voice:
        await ctx.send("❌ คุณต้องเข้าไปใน Voice Channel ก่อนครับ!")
        return
    
    channel = ctx.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    await ctx.send(f"✅ เข้าห้อง **{channel.name}** เรียบร้อย!")

@bot.command()
async def play(ctx, *, url):
    """เล่นเพลงจาก URL หรือชื่อเพลง"""
    if not ctx.author.voice:
        return await ctx.send("❌ คุณต้องเข้าไปใน Voice Channel ก่อนครับ!")

    channel = ctx.author.voice.channel
    
    # Permission checks
    permissions = channel.permissions_for(ctx.me)
    if not permissions.connect or not permissions.speak:
        return await ctx.send("❌ บอทไม่มีสิทธิ์ Connect หรือ Speak ใน Channel นี้ครับ!")

    if not ctx.voice_client:
        try:
            await channel.connect()
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return await ctx.send(f"❌ ไม่สามารถเข้า Voice Channel ได้: {e}")
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)

    # If it was paused, resume first (optional logic)
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()

    if ctx.voice_client.is_playing():
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
