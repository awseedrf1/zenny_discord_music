import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# อ่าน Channel ID ที่อนุญาตให้ใช้คำสั่ง (รองรับหลาย channel คั่นด้วย ,)
ALLOWED_CHANNEL_IDS = set()
_channel_env = os.getenv('ALLOWED_CHANNEL_IDS', '').strip()
if _channel_env:
    for cid in _channel_env.split(','):
        cid = cid.strip()
        if cid.isdigit():
            ALLOWED_CHANNEL_IDS.add(int(cid))

# เก็บคิวเพลงของแต่ละ server (guild)
queues = {}


@bot.check
async def restrict_to_allowed_channel(ctx):
    """จำกัดให้ใช้คำสั่งได้เฉพาะ text channel ที่กำหนดเท่านั้น"""
    # ถ้าไม่ได้ตั้งค่า ALLOWED_CHANNEL_IDS ให้ใช้ได้ทุก channel
    if not ALLOWED_CHANNEL_IDS:
        return True
    if ctx.channel.id in ALLOWED_CHANNEL_IDS:
        return True
    # แจ้งเตือนแบบเบาๆ (ลบทิ้งใน 5 วินาที) ว่า channel นี้ใช้ไม่ได้
    try:
        allowed_mentions = ", ".join(f"<#{cid}>" for cid in ALLOWED_CHANNEL_IDS)
        msg = await ctx.send(
            f"❌ คำสั่งนี้ใช้ได้เฉพาะใน {allowed_mentions} เท่านั้น",
            delete_after=5
        )
    except Exception:
        pass
    return False

# ตั้งค่า yt-dlp
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


def get_queue(guild_id):
    """ดึงคิวของ server นั้นๆ ถ้าไม่มีให้สร้างใหม่"""
    if guild_id not in queues:
        queues[guild_id] = deque()
    return queues[guild_id]


async def search_song(query):
    """ค้นหาเพลงจาก YouTube"""
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(query, download=False)
        )
        # ถ้าเป็นผลค้นหา จะมี entries
        if 'entries' in data:
            data = data['entries'][0]
        return {
            'url': data['url'],
            'title': data['title'],
            'duration': data.get('duration', 0),
            'webpage_url': data.get('webpage_url', ''),
            'thumbnail': data.get('thumbnail', '')
        }
    except Exception as e:
        print(f"Error searching song: {e}")
        return None


async def play_next(ctx):
    """เล่นเพลงถัดไปในคิว"""
    queue = get_queue(ctx.guild.id)

    if len(queue) == 0:
        return

    song = queue.popleft()
    voice_client = ctx.voice_client

    if voice_client is None:
        return

    try:
        source = discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS)
        voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(ctx), bot.loop
            ).result() if not e else print(f"Player error: {e}")
        )

        embed = discord.Embed(
            title="🎵 กำลังเล่น",
            description=f"**[{song['title']}]({song['webpage_url']})**",
            color=discord.Color.green()
        )
        if song.get('thumbnail'):
            embed.set_thumbnail(url=song['thumbnail'])
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")
        if len(queue) > 0:
            await play_next(ctx)


@bot.event
async def on_ready():
    print(f'✅ Bot ออนไลน์: {bot.user}')
    print(f'📡 อยู่ใน {len(bot.guilds)} servers')
    if ALLOWED_CHANNEL_IDS:
        print(f'🔒 จำกัดคำสั่งเฉพาะ channel: {", ".join(str(c) for c in ALLOWED_CHANNEL_IDS)}')
    else:
        print('🌐 อนุญาตทุก channel (ไม่ได้ตั้ง ALLOWED_CHANNEL_IDS)')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!play <เพลง>"
        )
    )


@bot.command(name='play', aliases=['p'])
async def play(ctx, *, query: str = None):
    """เล่นเพลงจาก YouTube"""
    if query is None:
        await ctx.send("❌ กรุณาระบุชื่อเพลงหรือลิงก์ YouTube\nตัวอย่าง: `!play despacito`")
        return

    # ตรวจสอบว่าผู้ใช้อยู่ใน voice channel หรือไม่
    if ctx.author.voice is None:
        await ctx.send("❌ คุณต้องเข้า voice channel ก่อน")
        return

    voice_channel = ctx.author.voice.channel

    # เชื่อมต่อกับ voice channel
    if ctx.voice_client is None:
        try:
            await voice_channel.connect()
        except Exception as e:
            await ctx.send(f"❌ ไม่สามารถเชื่อมต่อกับ voice channel: {str(e)}")
            return
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    # ค้นหาเพลง
    async with ctx.typing():
        await ctx.send(f"🔍 กำลังค้นหา: `{query}`...")
        song = await search_song(query)

        if song is None:
            await ctx.send("❌ ไม่พบเพลงที่ค้นหา")
            return

        queue = get_queue(ctx.guild.id)
        queue.append(song)

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            embed = discord.Embed(
                title="➕ เพิ่มเพลงในคิว",
                description=f"**[{song['title']}]({song['webpage_url']})**\nลำดับที่: `{len(queue)}`",
                color=discord.Color.blue()
            )
            if song.get('thumbnail'):
                embed.set_thumbnail(url=song['thumbnail'])
            await ctx.send(embed=embed)
        else:
            await play_next(ctx)


@bot.command(name='queue', aliases=['q'])
async def show_queue(ctx):
    """แสดงคิวเพลง"""
    queue = get_queue(ctx.guild.id)

    if len(queue) == 0 and (ctx.voice_client is None or not ctx.voice_client.is_playing()):
        await ctx.send("📭 คิวว่างเปล่า")
        return

    embed = discord.Embed(
        title="📜 คิวเพลง",
        color=discord.Color.purple()
    )

    # แสดงเพลงที่กำลังเล่นอยู่
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        embed.add_field(
            name="🎵 กำลังเล่น",
            value="เพลงปัจจุบัน",
            inline=False
        )

    # แสดงคิว (สูงสุด 10 เพลง)
    if len(queue) > 0:
        queue_text = ""
        for i, song in enumerate(list(queue)[:10], 1):
            queue_text += f"`{i}.` [{song['title']}]({song['webpage_url']})\n"

        if len(queue) > 10:
            queue_text += f"\n... และอีก `{len(queue) - 10}` เพลง"

        embed.add_field(
            name=f"📋 ในคิว ({len(queue)} เพลง)",
            value=queue_text,
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    """ข้ามเพลงปัจจุบัน"""
    if ctx.voice_client is None or not ctx.voice_client.is_playing():
        await ctx.send("❌ ไม่มีเพลงที่กำลังเล่น")
        return

    ctx.voice_client.stop()
    await ctx.send("⏭️ ข้ามเพลง")


@bot.command(name='stop')
async def stop(ctx):
    """หยุดเล่นเพลงและเคลียร์คิว"""
    if ctx.voice_client is None:
        await ctx.send("❌ Bot ไม่ได้อยู่ใน voice channel")
        return

    queue = get_queue(ctx.guild.id)
    queue.clear()

    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        ctx.voice_client.stop()

    await ctx.send("⏹️ หยุดเล่นเพลงและเคลียร์คิวแล้ว")


@bot.command(name='kick', aliases=['leave', 'disconnect', 'dc'])
async def kick(ctx):
    """เตะบอทออกจาก voice channel"""
    if ctx.voice_client is None:
        await ctx.send("❌ Bot ไม่ได้อยู่ใน voice channel")
        return

    queue = get_queue(ctx.guild.id)
    queue.clear()

    await ctx.voice_client.disconnect()
    await ctx.send("👋 บอทออกจาก voice channel แล้ว")


@bot.command(name='pause')
async def pause(ctx):
    """หยุดเพลงชั่วคราว"""
    if ctx.voice_client is None or not ctx.voice_client.is_playing():
        await ctx.send("❌ ไม่มีเพลงที่กำลังเล่น")
        return

    ctx.voice_client.pause()
    await ctx.send("⏸️ หยุดเพลงชั่วคราว")


@bot.command(name='resume', aliases=['r'])
async def resume(ctx):
    """เล่นเพลงต่อ"""
    if ctx.voice_client is None:
        await ctx.send("❌ Bot ไม่ได้อยู่ใน voice channel")
        return

    if not ctx.voice_client.is_paused():
        await ctx.send("❌ เพลงไม่ได้ถูกหยุดอยู่")
        return

    ctx.voice_client.resume()
    await ctx.send("▶️ เล่นเพลงต่อ")


@bot.command(name='help', aliases=['h', 'commands'])
async def help_command(ctx):
    """แสดงรายการคำสั่ง"""
    embed = discord.Embed(
        title="🎵 Music Bot - คำสั่งทั้งหมด",
        color=discord.Color.gold()
    )
    commands_list = [
        ("!play [เพลง/Link]", "เล่นเพลงจาก YouTube"),
        ("!queue", "ดูคิวเพลง"),
        ("!skip", "ข้ามเพลงปัจจุบัน"),
        ("!stop", "หยุดเล่นและเคลียร์คิว"),
        ("!pause", "หยุดเพลงชั่วคราว"),
        ("!resume", "เล่นเพลงต่อ"),
        ("!kick", "เตะบอทออกจาก channel"),
    ]
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)

    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    """จัดการ error"""
    if isinstance(error, commands.CommandNotFound):
        return
    # check ล้มเหลว (เช่น ใช้ผิด channel) เราแจ้งเตือนแล้วใน check ไม่ต้องแจ้งซ้ำ
    if isinstance(error, commands.CheckFailure):
        return
    print(f"Error: {error}")
    await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(error)}")


# เริ่ม web server เพื่อให้ Render ไม่ปิดบอท
keep_alive()

# รันบอท
TOKEN = os.getenv('TOKEN')
if not TOKEN:
    print("❌ ไม่พบ TOKEN ใน environment variables")
    exit(1)

bot.run(TOKEN)
