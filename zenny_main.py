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

# 4. Audio Settings
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

async def play_next(ctx):
    q = get_queue(ctx)
    query = q.next()
    
    if query:
        async with ctx.typing():
            try:
                video = None
                audio_url = None
                
                # Search or Direct Link
                if "youtube.com" not in query and "youtu.be" not in query:
                    s = Search(query)
                    video = s.results[0]
                else:
                    # Try 'WEB' client first - often bypasses data center blocks better than 'ANDROID'
                    try:
                        video = YouTube(query, client='WEB')
                        audio_url = video.streams.get_audio_only().url
                    except:
                        # Fallback to Mobile Web
                        video = YouTube(query, client='MWEB')
                        audio_url = video.streams.get_audio_only().url

                player = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
                ctx.voice_client.play(player, after=lambda e: bot.loop.create_task(play_next(ctx)))
                await ctx.send(f'🎵 Now Playing: **{video.title}**')
                
            except Exception as e:
                logger.error(f"Playback Error: {e}")
                await ctx.send(f"❌ YouTube Blocked this attempt (Bot Detection). Try again in a moment.")
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
    bot.run(os.getenv('TOKEN'))
