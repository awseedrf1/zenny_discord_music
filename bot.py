import discord
from discord.ext import commands
import wavelink
import asyncio
import os
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

# Lavalink server config
LAVALINK_HOST = os.getenv('LAVALINK_HOST', 'lavalink.jirayu.net')
LAVALINK_PORT = int(os.getenv('LAVALINK_PORT', '13592'))
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
LAVALINK_SECURE = os.getenv('LAVALINK_SECURE', 'false').lower() == 'true'


@bot.check
async def restrict_to_allowed_channel(ctx):
    """จำกัดให้ใช้คำสั่งได้เฉพาะ text channel ที่กำหนด"""
    if not ALLOWED_CHANNEL_IDS:
        return True
    if ctx.channel.id in ALLOWED_CHANNEL_IDS:
        return True
    try:
        allowed_mentions = ", ".join(f"<#{cid}>" for cid in ALLOWED_CHANNEL_IDS)
        await ctx.send(
            f"❌ คำสั่งนี้ใช้ได้เฉพาะใน {allowed_mentions} เท่านั้น",
            delete_after=5
        )
    except Exception:
        pass
    return False


async def connect_lavalink():
    """เชื่อมต่อกับ Lavalink server"""
    scheme = 'https' if LAVALINK_SECURE else 'http'
    uri = f'{scheme}://{LAVALINK_HOST}:{LAVALINK_PORT}'
    print(f'🔗 กำลังเชื่อมต่อ Lavalink: {uri}')

    node = wavelink.Node(
        identifier='MAIN',
        uri=uri,
        password=LAVALINK_PASSWORD,
    )
    try:
        await wavelink.Pool.connect(client=bot, nodes=[node])
        print('✅ เชื่อมต่อ Lavalink สำเร็จ')
    except Exception as e:
        print(f'❌ เชื่อมต่อ Lavalink ล้มเหลว: {e}')
        print(f'💡 ลองเปลี่ยน LAVALINK_HOST/PORT/PASSWORD ใน environment variables')


@bot.event
async def on_ready():
    print(f'✅ Bot ออนไลน์: {bot.user}')
    print(f'📡 อยู่ใน {len(bot.guilds)} servers')
    if ALLOWED_CHANNEL_IDS:
        print(f'🔒 จำกัดคำสั่งเฉพาะ channel: {", ".join(str(c) for c in ALLOWED_CHANNEL_IDS)}')
    else:
        print('🌐 อนุญาตทุก channel (ไม่ได้ตั้ง ALLOWED_CHANNEL_IDS)')

    # เคลียร์ voice connection ค้างเก่า (แก้ error 4006)
    for vc in list(bot.voice_clients):
        try:
            await vc.disconnect(force=True)
        except Exception:
            pass

    await connect_lavalink()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!play <เพลง>"
        )
    )


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    print(f'🎵 Lavalink Node "{payload.node.identifier}" พร้อมใช้งาน (resumed: {payload.resumed})')


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """เล่นเพลงถัดไปในคิวเมื่อเพลงปัจจุบันจบ"""
    player: wavelink.Player = payload.player
    if player is None:
        return

    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)

        # ส่งข้อความแจ้งใน channel ที่ผูกไว้
        channel = getattr(player, 'home_channel', None)
        if channel:
            try:
                embed = discord.Embed(
                    title="🎵 กำลังเล่น",
                    description=f"**[{next_track.title}]({next_track.uri})**",
                    color=discord.Color.green()
                )
                if next_track.artwork:
                    embed.set_thumbnail(url=next_track.artwork)
                await channel.send(embed=embed)
            except Exception as e:
                print(f'Error sending now-playing message: {e}')


@bot.command(name='play', aliases=['p'])
async def play(ctx, *, query: str = None):
    """เล่นเพลงจาก YouTube/SoundCloud"""
    if query is None:
        await ctx.send("❌ กรุณาระบุชื่อเพลงหรือลิงก์\nตัวอย่าง: `!play despacito`")
        return

    if ctx.author.voice is None:
        await ctx.send("❌ คุณต้องเข้า voice channel ก่อน")
        return

    voice_channel = ctx.author.voice.channel

    # เชื่อมต่อ voice channel
    player: wavelink.Player = ctx.voice_client
    if player is None:
        try:
            player = await voice_channel.connect(cls=wavelink.Player, self_deaf=True)
        except Exception as e:
            await ctx.send(f"❌ ไม่สามารถเชื่อมต่อ voice channel: {str(e)[:200]}")
            return
    elif player.channel != voice_channel:
        await player.move_to(voice_channel)

    # ผูก channel ไว้กับ player เพื่อใช้ส่งข้อความ
    player.home_channel = ctx.channel

    # ค้นหาเพลง
    async with ctx.typing():
        await ctx.send(f"🔍 กำลังค้นหา: `{query}`")
        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)
        except Exception as e:
            await ctx.send(f"❌ เกิดข้อผิดพลาดในการค้นหา\n```{str(e)[:300]}```")
            return

        if not tracks:
            await ctx.send("❌ ไม่พบเพลงที่ค้นหา")
            return

        # ถ้าเป็น playlist ใส่ทั้งหมด, ถ้าเป็นเพลงเดียวใส่อันแรก
        if isinstance(tracks, wavelink.Playlist):
            added = await player.queue.put_wait(tracks)
            await ctx.send(f"➕ เพิ่ม `{added}` เพลงจาก playlist **{tracks.name}** ลงคิว")
        else:
            track = tracks[0]
            await player.queue.put_wait(track)

            if player.playing:
                embed = discord.Embed(
                    title="➕ เพิ่มเพลงในคิว",
                    description=f"**[{track.title}]({track.uri})**\nลำดับที่: `{len(player.queue)}`",
                    color=discord.Color.blue()
                )
                if track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                await ctx.send(embed=embed)

        # ถ้าไม่ได้เล่นอะไรอยู่ ให้เริ่มเล่น
        if not player.playing:
            next_track = player.queue.get()
            await player.play(next_track)
            embed = discord.Embed(
                title="🎵 กำลังเล่น",
                description=f"**[{next_track.title}]({next_track.uri})**",
                color=discord.Color.green()
            )
            if next_track.artwork:
                embed.set_thumbnail(url=next_track.artwork)
            await ctx.send(embed=embed)


@bot.command(name='queue', aliases=['q'])
async def show_queue(ctx):
    """แสดงคิวเพลง"""
    player: wavelink.Player = ctx.voice_client
    if player is None:
        await ctx.send("📭 บอทไม่ได้อยู่ใน voice channel")
        return

    if not player.playing and player.queue.is_empty:
        await ctx.send("📭 คิวว่างเปล่า")
        return

    embed = discord.Embed(title="📜 คิวเพลง", color=discord.Color.purple())

    if player.current:
        embed.add_field(
            name="🎵 กำลังเล่น",
            value=f"[{player.current.title}]({player.current.uri})",
            inline=False
        )

    if not player.queue.is_empty:
        queue_list = list(player.queue)[:10]
        queue_text = ""
        for i, track in enumerate(queue_list, 1):
            queue_text += f"`{i}.` [{track.title}]({track.uri})\n"

        if len(player.queue) > 10:
            queue_text += f"\n... และอีก `{len(player.queue) - 10}` เพลง"

        embed.add_field(
            name=f"📋 ในคิว ({len(player.queue)} เพลง)",
            value=queue_text,
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    """ข้ามเพลงปัจจุบัน"""
    player: wavelink.Player = ctx.voice_client
    if player is None or not player.playing:
        await ctx.send("❌ ไม่มีเพลงที่กำลังเล่น")
        return

    await player.skip(force=True)
    await ctx.send("⏭️ ข้ามเพลง")


@bot.command(name='stop')
async def stop(ctx):
    """หยุดเล่นและเคลียร์คิว"""
    player: wavelink.Player = ctx.voice_client
    if player is None:
        await ctx.send("❌ บอทไม่ได้อยู่ใน voice channel")
        return

    player.queue.clear()
    await player.stop()
    await ctx.send("⏹️ หยุดเล่นและเคลียร์คิวแล้ว")


@bot.command(name='kick', aliases=['leave', 'disconnect', 'dc'])
async def kick(ctx):
    """เตะบอทออกจาก voice channel"""
    player: wavelink.Player = ctx.voice_client
    if player is None:
        await ctx.send("❌ บอทไม่ได้อยู่ใน voice channel")
        return

    player.queue.clear()
    await player.disconnect()
    await ctx.send("👋 บอทออกจาก voice channel แล้ว")


@bot.command(name='pause')
async def pause(ctx):
    """หยุดเพลงชั่วคราว"""
    player: wavelink.Player = ctx.voice_client
    if player is None or not player.playing:
        await ctx.send("❌ ไม่มีเพลงที่กำลังเล่น")
        return

    if player.paused:
        await ctx.send("❌ เพลงถูกหยุดอยู่แล้ว ใช้ `!resume` เพื่อเล่นต่อ")
        return

    await player.pause(True)
    await ctx.send("⏸️ หยุดเพลงชั่วคราว")


@bot.command(name='resume', aliases=['r'])
async def resume(ctx):
    """เล่นเพลงต่อ"""
    player: wavelink.Player = ctx.voice_client
    if player is None:
        await ctx.send("❌ บอทไม่ได้อยู่ใน voice channel")
        return

    if not player.paused:
        await ctx.send("❌ เพลงไม่ได้ถูกหยุดอยู่")
        return

    await player.pause(False)
    await ctx.send("▶️ เล่นเพลงต่อ")


@bot.command(name='help', aliases=['h', 'commands'])
async def help_command(ctx):
    """แสดงรายการคำสั่ง"""
    embed = discord.Embed(
        title="🎵 Music Bot - คำสั่งทั้งหมด",
        color=discord.Color.gold()
    )
    commands_list = [
        ("!play [เพลง/Link]", "เล่นเพลงจาก YouTube/SoundCloud"),
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
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CheckFailure):
        return
    print(f"Error: {type(error).__name__}: {error}")
    try:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(error)[:300]}")
    except Exception:
        pass


# เริ่ม web server เพื่อให้ Render ไม่ปิดบอท
keep_alive()

# รันบอท
TOKEN = os.getenv('TOKEN')
if not TOKEN:
    print("❌ ไม่พบ TOKEN ใน environment variables")
    exit(1)

bot.run(TOKEN)
