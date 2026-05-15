import discord
from discord.ext import commands
import youtube_dl
import asyncio
import os
import logging
from collections import deque
from dotenv import load_dotenv
from zenny_server import keep_alive

# 1. Config & Logging
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s: %(message)s')
logger = logging.getLogger('zenny_bot')

# 2. Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 3. Queue System
queues = {}

class MusicQueue:
    def __init__(self):
        self.items = deque()
    def add(self, url): self.items.append(url)
    def next(self): return self.items.popleft() if self.items else None
    def clear(self): self.items.clear()

def get_queue(ctx):
    if ctx.guild.id not in queues: queues[ctx.guild.id] = MusicQueue()
    return queues[ctx.guild.id]

# 4. youtube-dl Options (Stealth & Bypass)
YDL_OPTIONS = {
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
    # Use a high-trust User-Agent (Voucher-style)
    'user_agent': 'Super-Idol-Music-Bot/1.0 (Zenny-Bot; YouTube-Bypass-Active)',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(YDL_OPTIONS)

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
            return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)
        except Exception as e:
            logger.error(f"youtube-dl Error: {e}")
            raise

async def play_next(ctx):
    q = get_queue(ctx)
    query = q.next()
    
    if query:
        async with ctx.typing():
            try:
                player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: bot.loop.create_task(play_next(ctx)))
                await ctx.send(f'🎵 Now Playing: **{player.title}**')
            except Exception as e:
                logger.error(f"Playback Error: {e}")
                await ctx.send(f"❌ Error playing: {e}")
                bot.loop.create_task(play_next(ctx))

# 5. Commands
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')

@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice:
        return await ctx.send("❌ Join a Voice Channel first!")

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    elif ctx.voice_client.channel != ctx.author.voice.channel:
        await ctx.voice_client.move_to(ctx.author.voice.channel)

    q = get_queue(ctx)
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        q.add(query)
        await ctx.send(f"➕ Added to queue (Position: {len(q.items)})")
    else:
        q.add(query)
        await play_next(ctx)

@bot.command()
async def stop(ctx):
    get_queue(ctx).clear()
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Disconnected.")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped!")

if __name__ == "__main__":
    keep_alive()
    token = os.getenv('TOKEN')
    if token:
        bot.run(token)
    else:
        logger.error("TOKEN MISSING!")
