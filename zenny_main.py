import discord
from discord.ext import commands
from pytubefix import YouTube, Search
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

# 4. Audio Source Implementation (pytubefix)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

async def play_next(ctx):
    q = get_queue(ctx)
    url = q.next()
    
    if url:
        async with ctx.typing():
            try:
                # Use pytubefix to get the best audio stream
                # We use use_oauth=False to avoid needing a login, 
                # but it uses InnerTube API by default for bypass.
                if "youtube.com" not in url and "youtu.be" not in url:
                    # If it's a search query
                    s = Search(url)
                    video = s.results[0]
                else:
                    video = YouTube(url, client='ANDROID_TESTSUITE') # Stealth client

                audio_stream = video.streams.get_audio_only()
                source_url = audio_stream.url
                
                player = discord.FFmpegPCMAudio(source_url, **FFMPEG_OPTIONS)
                ctx.voice_client.play(player, after=lambda e: bot.loop.create_task(play_next(ctx)))
                
                await ctx.send(f'🎵 Now Playing: **{video.title}**')
                logger.info(f"Playing: {video.title}")
                
            except Exception as e:
                logger.error(f"Pytube Error: {e}")
                await ctx.send(f"❌ Playback Error: {e}")
                bot.loop.create_task(play_next(ctx))
    else:
        logger.info(f"Queue empty for {ctx.guild.name}")

# 5. Commands
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')

@bot.command()
async def play(ctx, *, query):
    """Play song (No yt-dlp version)"""
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
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped!")

@bot.command()
async def stop(ctx):
    get_queue(ctx).clear()
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Disconnected.")

@bot.event
async def on_command_error(ctx, error):
    if not isinstance(error, commands.CommandNotFound):
        logger.error(f"Error: {error}")
        await ctx.send(f"❌ Error: {error}")

if __name__ == "__main__":
    keep_alive()
    token = os.getenv('TOKEN')
    if token:
        bot.run(token)
    else:
        logger.error("TOKEN MISSING!")
