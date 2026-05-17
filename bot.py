import discord
from discord.ext import commands
import wavelink
import asyncio
import os
from dotenv import load_dotenv
from flask import request
from keep_alive import app, keep_alive
import concurrent.futures

load_dotenv()

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
bot.help_command = None

# อ่าน Channel ID ที่อนุญาตให้ใช้คำสั่ง (รองรับหลาย channel คั่นด้วย ,)
ALLOWED_CHANNEL_IDS = set()
_channel_env = os.getenv('ALLOWED_CHANNEL_IDS', '').strip()
if _channel_env:
    for cid in _channel_env.split(','):
        cid = cid.strip()
        if cid.isdigit():
            ALLOWED_CHANNEL_IDS.add(int(cid))

# Lavalink server config (required from Render environment)
LAVALINK_HOST = os.getenv('LAVALINK_HOST')
LAVALINK_PORT = os.getenv('LAVALINK_PORT')
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD')
LAVALINK_SECURE = os.getenv('LAVALINK_SECURE', 'false').lower() == 'true'

if not LAVALINK_HOST or not LAVALINK_PORT or not LAVALINK_PASSWORD:
    print('❌ Missing Lavalink configuration. Set LAVALINK_HOST, LAVALINK_PORT, and LAVALINK_PASSWORD in Render environment variables.')
    exit(1)

try:
    LAVALINK_PORT = int(LAVALINK_PORT)
except ValueError:
    print('❌ Invalid LAVALINK_PORT. It must be a number.')
    exit(1)


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


def format_duration(ms: int) -> str:
    """แปลงมิลลิวินาทีเป็นรูปแบบเวลา เช่น 3:45 หรือ 1:23:45"""
    if not ms:
        return "—"
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def build_now_playing_embed(track, requester=None, queue_size=0, playlist_info=None):
    """สร้าง embed สำหรับเพลงที่กำลังเล่น"""
    embed = discord.Embed(
        title="🎵 กำลังเล่น",
        description=f"**[{track.title}]({track.uri})**",
        color=discord.Color.green()
    )
    if track.author:
        embed.add_field(name="ศิลปิน", value=track.author, inline=True)
    if track.length:
        embed.add_field(name="ความยาว", value=format_duration(track.length), inline=True)
    if queue_size > 0:
        embed.add_field(name="ในคิว", value=f"`{queue_size}` เพลง", inline=True)
    if playlist_info:
        embed.add_field(name="📂 Playlist", value=playlist_info, inline=False)
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    if requester:
        embed.set_footer(
            text=f"ขอโดย {requester.display_name}",
            icon_url=requester.display_avatar.url
        )
    return embed


COMMAND_RESPONSE_DELAY = 1.5

async def send_embed_and_wait(ctx, embed):
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(COMMAND_RESPONSE_DELAY)
    return msg

async def edit_embed_and_wait(message, embed):
    msg = await message.edit(embed=embed)
    await asyncio.sleep(COMMAND_RESPONSE_DELAY)
    return msg


async def connect_voice(ctx, channel: discord.VoiceChannel = None):
    """เชื่อมต่อบอทเข้า voice channel ถ้ายังไม่ได้อยู่"""
    player: wavelink.Player = ctx.voice_client
    if player is not None and player.channel is not None:
        return player

    if channel is None:
        if ctx.author.voice is None:
            return None
        channel = ctx.author.voice.channel

    try:
        player = await channel.connect(cls=wavelink.Player, self_deaf=True)
        return player
    except Exception as e:
        raise RuntimeError(f"voice connect failed: {e}") from e


async def queue_track(player: wavelink.Player, status_channel: discord.TextChannel, query: str, requester=None):
    """ค้นหาเพลง, เพิ่มคิว, แล้วเล่นถ้าไม่มีเพลงกำลังเล่น"""
    searching_embed = discord.Embed(
        description=f"🔍 กำลังค้นหา: `{query}`",
        color=discord.Color.light_grey()
    )
    status_msg = await status_channel.send(embed=searching_embed)

    player.autoplay = wavelink.AutoPlayMode.disabled
    player.home_channel = status_channel
    if not player.playing:
        player._pending_status_msg = status_msg
        player._pending_status_requester = requester

    old_task = getattr(player, '_idle_task', None)
    if old_task and not old_task.done():
        old_task.cancel()

    try:
        tracks: wavelink.Search = await wavelink.Playable.search(query)
    except Exception as e:
        embed = discord.Embed(
            title="❌ ค้นหาไม่สำเร็จ",
            description=f"```{str(e)[:300]}```",
            color=discord.Color.red()
        )
        await status_msg.edit(embed=embed)
        return None

    if not tracks:
        embed = discord.Embed(
            description="❌ ไม่พบเพลงที่ค้นหา",
            color=discord.Color.red()
        )
        await status_msg.edit(embed=embed)
        return None

    if isinstance(tracks, wavelink.Playlist):
        added = await player.queue.put_wait(tracks)
        if not player.playing:
            next_track = player.queue.get()
            await player.play(next_track)
            embed = build_now_playing_embed(
                next_track,
                requester,
                queue_size=len(player.queue),
                playlist_info=f"เพิ่ม `{added}` เพลงจาก playlist **{tracks.name}**"
            )
        else:
            embed = discord.Embed(
                title="➕ เพิ่ม Playlist ในคิว",
                description=f"**{tracks.name}**\nจำนวน: `{added}` เพลง\nคิวรวม: `{len(player.queue)}` เพลง",
                color=discord.Color.blue()
            )
            embed.set_footer(
                text=f"ขอโดย {requester.display_name if requester else 'ระบบ'}",
                icon_url=requester.display_avatar.url if requester else None
            )
        await status_msg.edit(embed=embed)
        return True

    track = tracks[0]
    await player.queue.put_wait(track)

    if player.playing:
        embed = discord.Embed(
            title="➕ เพิ่มเพลงในคิว",
            description=f"**[{track.title}]({track.uri})**",
            color=discord.Color.blue()
        )
        embed.add_field(name="ลำดับในคิว", value=f"`#{len(player.queue)}`", inline=True)
        if track.length:
            embed.add_field(name="ความยาว", value=format_duration(track.length), inline=True)
        if track.author:
            embed.add_field(name="ศิลปิน", value=track.author, inline=True)
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        embed.set_footer(
            text=f"ขอโดย {requester.display_name if requester else 'ระบบ'}",
            icon_url=requester.display_avatar.url if requester else None
        )
        await status_msg.edit(embed=embed)
        return True

    next_track = player.queue.get()
    await player.play(next_track)
    embed = build_now_playing_embed(
        next_track,
        requester,
        queue_size=len(player.queue)
    )
    await status_msg.edit(embed=embed)
    return True


async def http_play_command(guild_id: int, text_channel_id: int, voice_channel_id: int, query: str):
    guild = bot.get_guild(guild_id)
    if guild is None:
        return {"error": "guild not found"}, 404

    text_channel = bot.get_channel(text_channel_id)
    if text_channel is None:
        try:
            text_channel = await bot.fetch_channel(text_channel_id)
        except Exception:
            text_channel = None
    if text_channel is None or not isinstance(text_channel, discord.abc.Messageable):
        return {"error": "text channel not found"}, 404

    voice_channel = bot.get_channel(voice_channel_id)
    if voice_channel is None:
        try:
            voice_channel = await bot.fetch_channel(voice_channel_id)
        except Exception:
            voice_channel = None
    if voice_channel is None or not isinstance(voice_channel, discord.VoiceChannel):
        return {"error": "voice channel not found"}, 404

    player = guild.voice_client
    if player is None:
        try:
            player = await voice_channel.connect(cls=wavelink.Player, self_deaf=True)
        except Exception as e:
            return {"error": f"connect failed: {e}"}, 500
    elif player.channel != voice_channel:
        try:
            await player.move_to(voice_channel)
        except Exception as e:
            return {"error": f"move_to failed: {e}"}, 500

    result = await queue_track(player, text_channel, query)
    if result is None:
        return {"error": "failed to enqueue or play track"}, 500

    return {"status": "ok", "message": "เพลงถูกเพิ่ม/เล่นแล้ว"}, 200


@app.route('/command')
def http_command():
    action = request.args.get('action') or request.args.get('cmd')
    query = request.args.get('query')
    guild_id = request.args.get('guild_id')
    text_channel_id = request.args.get('text_channel_id')
    voice_channel_id = request.args.get('voice_channel_id')

    if not action or not guild_id or not text_channel_id or not query:
        return {"error": "action, guild_id, text_channel_id, query are required"}, 400

    action = action.lstrip('!').lower()
    if action not in ('play', 'p'):
        return {"error": "unsupported action"}, 400

    try:
        guild_id = int(guild_id)
        text_channel_id = int(text_channel_id)
        voice_channel_id = int(voice_channel_id)
    except (TypeError, ValueError):
        return {"error": "guild_id, text_channel_id, voice_channel_id must be integers"}, 400

    future = asyncio.run_coroutine_threadsafe(
        http_play_command(guild_id, text_channel_id, voice_channel_id, query),
        bot.loop
    )
    try:
        result, status = future.result(timeout=30)
        return result, status
    except concurrent.futures.TimeoutError:
        return {"error": "request timed out"}, 504


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

    reason = getattr(payload, 'reason', 'unknown')
    reason_str = reason.value if hasattr(reason, 'value') else str(reason)
    print(f'🎵 เพลงจบ (reason: {reason_str}): {payload.track.title if payload.track else "?"}')

    # replaced = skip/play กำลังจัดการอยู่, cleanup = node ตัดการเชื่อมต่อ
    if reason_str.lower() in ('replaced', 'cleanup'):
        return

    # ป้องกัน duplicate: ถ้า player กำลังเล่นอยู่แล้วให้หยุด
    if player.playing:
        return

    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)

        channel = getattr(player, 'home_channel', None)
        if channel:
            try:
                embed = build_now_playing_embed(next_track, queue_size=len(player.queue))
                await channel.send(embed=embed)
            except Exception as e:
                print(f'Error sending now-playing message: {e}')
    else:
        # คิวว่าง → ยกเลิก task เดิม (ถ้ามี) แล้วเริ่มนับ idle ใหม่
        old_task = getattr(player, '_idle_task', None)
        if old_task and not old_task.done():
            old_task.cancel()
        player._idle_task = bot.loop.create_task(idle_disconnect(player))


@bot.event
async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload):
    """เมื่อเพลงเล่นไม่ได้ → ข้ามไปเพลงถัดไป"""
    player: wavelink.Player = payload.player
    track = payload.track
    exception = payload.exception

    err_msg = exception.get('message', 'Unknown error') if isinstance(exception, dict) else str(exception)
    print(f'❌ Track exception: {err_msg} | track: {track.title if track else "?"}')

    channel = getattr(player, 'home_channel', None)
    if channel:
        try:
            footer = "กำลังข้ามไปเพลงถัดไป..." if not player.queue.is_empty else "คิวว่างเปล่า"
            embed = discord.Embed(
                title="⚠️ เล่นเพลงไม่ได้",
                description=f"**{track.title if track else 'เพลง'}**\n```{err_msg[:200]}```",
                color=discord.Color.orange()
            )
            embed.set_footer(text=footer)

            pending_msg = getattr(player, '_pending_status_msg', None)
            if pending_msg:
                await pending_msg.edit(embed=embed)
            else:
                await channel.send(embed=embed)
        except Exception:
            pass
    # on_wavelink_track_end จะจัดการเล่นเพลงถัดไปเมื่อ Lavalink ส่ง loadFailed


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    """เมื่อเพลงเริ่มเล่น"""
    player: wavelink.Player = payload.player
    track = payload.track
    pending_msg = getattr(player, '_pending_status_msg', None)
    if pending_msg:
        try:
            requester = getattr(player, '_pending_status_requester', None)
            embed = build_now_playing_embed(
                track,
                requester=requester,
                queue_size=len(player.queue)
            )
            await pending_msg.edit(embed=embed)
        except Exception:
            pass
        finally:
            player._pending_status_msg = None
            player._pending_status_requester = None


@bot.event
async def on_wavelink_track_stuck(payload: wavelink.TrackStuckEventPayload):
    """เมื่อเพลงค้าง (streaming stuck) → ข้ามไปเพลงถัดไป"""
    player: wavelink.Player = payload.player
    track = payload.track
    print(f'⚠️ Track stuck: {track.title if track else "?"} (threshold: {payload.threshold}ms)')

    channel = getattr(player, 'home_channel', None)
    if channel:
        try:
            embed = discord.Embed(
                description=f"⚠️ เพลง **{track.title if track else '?'}** ค้าง กำลังข้าม...",
                color=discord.Color.orange()
            )
            await channel.send(embed=embed)
        except Exception:
            pass
    # on_wavelink_track_end จะจัดการเล่นเพลงถัดไปเมื่อ Lavalink ส่ง stopped


async def idle_disconnect(player: wavelink.Player, timeout: int = 300):
    """ถ้าคิวว่างและไม่มีอะไรเล่นเกินกำหนด → เตะออกอัตโนมัติ"""
    await asyncio.sleep(timeout)
    if player and player.connected and player.queue.is_empty and not player.playing:
        channel = getattr(player, 'home_channel', None)
        if channel:
            try:
                embed = discord.Embed(
                    description=f"💤 ไม่มีเพลงนาน {timeout // 60} นาที — บอทออกจาก voice แล้ว",
                    color=discord.Color.greyple()
                )
                await channel.send(embed=embed)
            except Exception:
                pass
        try:
            await player.disconnect()
        except Exception:
            pass


@bot.command(name='play', aliases=['p'])
async def play(ctx, *, query: str = None):
    """เล่นเพลงจาก YouTube/SoundCloud"""
    if query is None:
        embed = discord.Embed(
            title="❌ ใช้คำสั่งไม่ถูกต้อง",
            description="กรุณาระบุชื่อเพลงหรือลิงก์\nตัวอย่าง: `!play despacito`",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    if query is None or query.strip() == "":
        embed = discord.Embed(
            title="❌ ใช้คำสั่งไม่ถูกต้อง",
            description="กรุณาระบุชื่อเพลงหรือลิงก์\nตัวอย่าง: `!play despacito`",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    # ถ้าบอทยังไม่อยู่ใน voice ให้เข้าห้องของผู้ใช้งานก่อน
    voice_channel = ctx.author.voice.channel if ctx.author.voice is not None else None

    player: wavelink.Player = ctx.voice_client
    if player is None:
        if voice_channel is None:
            embed = discord.Embed(
                description="❌ คุณต้องเข้า voice channel หรือให้บอทอยู่ใน voice ก่อน",
                color=discord.Color.red()
            )
            await send_embed_and_wait(ctx, embed)
            return

        try:
            player = await connect_voice(ctx, voice_channel)
        except Exception as e:
            embed = discord.Embed(
                title="❌ เชื่อมต่อ voice channel ไม่ได้",
                description=f"บอทไม่สามารถเข้าห้องเสียงได้\n```{str(e)[:240]}```",
                color=discord.Color.red()
            )
            await send_embed_and_wait(ctx, embed)
            return
    elif voice_channel is not None and player.channel != voice_channel:
        try:
            await player.move_to(voice_channel)
        except Exception:
            embed = discord.Embed(
                title="❌ เชื่อมต่อ voice channel ไม่ได้",
                description="บอทไม่สามารถย้ายเข้า voice channel ที่ระบุได้",
                color=discord.Color.red()
            )
            await send_embed_and_wait(ctx, embed)
            return

    # ส่ง embed ค้นหาก่อน แล้วค่อย edit
    searching_embed = discord.Embed(
        description=f"🔍 กำลังค้นหา: `{query}`",
        color=discord.Color.light_grey()
    )
    status_msg = await ctx.send(embed=searching_embed)

    player.autoplay = wavelink.AutoPlayMode.disabled
    player.home_channel = ctx.channel
    if not player.playing:
        player._pending_status_msg = status_msg
        player._pending_status_requester = ctx.author

    # ยกเลิก idle timer ถ้ามีอยู่ (ป้องกันบอทถูกเตะขณะกำลังเล่น)
    old_task = getattr(player, '_idle_task', None)
    if old_task and not old_task.done():
        old_task.cancel()

    # ค้นหาเพลง
    try:
        tracks: wavelink.Search = await wavelink.Playable.search(query)
    except Exception as e:
        embed = discord.Embed(
            title="❌ ค้นหาไม่สำเร็จ",
            description=f"```{str(e)[:300]}```",
            color=discord.Color.red()
        )
        await edit_embed_and_wait(status_msg, embed)
        return

    if not tracks:
        embed = discord.Embed(
            description="❌ ไม่พบเพลงที่ค้นหา",
            color=discord.Color.red()
        )
        await edit_embed_and_wait(status_msg, embed)
        return

    # ถ้าเป็น playlist ใส่ทั้งหมด, ถ้าเป็นเพลงเดียวใส่อันแรก
    if isinstance(tracks, wavelink.Playlist):
        added = await player.queue.put_wait(tracks)
        # ถ้าไม่มีอะไรเล่นอยู่ เริ่มเล่นเลย
        if not player.playing:
            next_track = player.queue.get()
            await player.play(next_track)
            embed = build_now_playing_embed(
                next_track,
                ctx.author,
                queue_size=len(player.queue),
                playlist_info=f"เพิ่ม `{added}` เพลงจาก playlist **{tracks.name}**"
            )
        else:
            embed = discord.Embed(
                title="➕ เพิ่ม Playlist ในคิว",
                description=f"**{tracks.name}**\nจำนวน: `{added}` เพลง\nคิวรวม: `{len(player.queue)}` เพลง",
                color=discord.Color.blue()
            )
            embed.set_footer(
                text=f"ขอโดย {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url
            )
        await edit_embed_and_wait(status_msg, embed)
    else:
        track = tracks[0]
        await player.queue.put_wait(track)

        if player.playing:
            # มีเพลงเล่นอยู่ → เพิ่มในคิว
            embed = discord.Embed(
                title="➕ เพิ่มเพลงในคิว",
                description=f"**[{track.title}]({track.uri})**",
                color=discord.Color.blue()
            )
            embed.add_field(name="ลำดับในคิว", value=f"`#{len(player.queue)}`", inline=True)
            if track.length:
                embed.add_field(name="ความยาว", value=format_duration(track.length), inline=True)
            if track.author:
                embed.add_field(name="ศิลปิน", value=track.author, inline=True)
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            embed.set_footer(
                text=f"ขอโดย {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url
            )
            await edit_embed_and_wait(status_msg, embed)
        else:
            # ไม่มีอะไรเล่นอยู่ → เริ่มเล่น
            next_track = player.queue.get()
            await player.play(next_track)
            embed = build_now_playing_embed(
                next_track,
                ctx.author,
                queue_size=len(player.queue)
            )
            await edit_embed_and_wait(status_msg, embed)


class QueueView(discord.ui.View):
    """Paginated queue viewer with ◀ ▶ buttons."""

    PER_PAGE = 10

    def __init__(self, ctx, player, *, timeout=60):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.player = player
        self.page = 0
        self._update_buttons()

    def _total_pages(self):
        return max(1, -(-len(self.player.queue) // self.PER_PAGE))

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self._total_pages() - 1

    def build_embed(self):
        tracks = list(self.player.queue)
        total_pages = self._total_pages()
        start = self.page * self.PER_PAGE
        page_tracks = tracks[start:start + self.PER_PAGE]

        embed = discord.Embed(
            title="📜 คิวเพลง",
            color=discord.Color.purple()
        )

        if self.player.current:
            current = self.player.current
            current_text = f"**[{current.title}]({current.uri})**"
            if current.author:
                current_text += f"\nโดย: {current.author}"
            if current.length:
                current_text += f" • `{format_duration(current.length)}`"
            embed.add_field(name="🎵 กำลังเล่น", value=current_text[:1024], inline=False)
            if current.artwork:
                embed.set_thumbnail(url=current.artwork)

        if page_tracks:
            queue_text = ""
            for i, track in enumerate(page_tracks, start + 1):
                duration_str = f" `{format_duration(track.length)}`" if track.length else ""
                title = track.title[:60] + "…" if len(track.title) > 60 else track.title
                line = f"`{i}.` [{title}]({track.uri}){duration_str}\n"
                if len(queue_text) + len(line) > 1000:
                    break
                queue_text += line

            embed.add_field(
                name=f"📋 ในคิว ({len(tracks)} เพลง)",
                value=queue_text or "—",
                inline=False
            )

        total_duration = sum(t.length for t in tracks if t.length)
        footer = f"หน้า {self.page + 1}/{total_pages}"
        if total_duration:
            footer += f"  •  ⏱️ รวม: {format_duration(total_duration)}"
        embed.set_footer(text=footer)
        return embed

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.page = min(self._total_pages() - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            msg = getattr(self, 'message', None)
            if msg:
                await msg.edit(view=self)
        except Exception:
            pass


@bot.command(name='queue', aliases=['q'])
async def show_queue(ctx):
    """แสดงคิวเพลง"""
    player: wavelink.Player = ctx.voice_client
    if player is None:
        embed = discord.Embed(
            description="📭 บอทไม่ได้อยู่ใน voice channel",
            color=discord.Color.light_grey()
        )
        await send_embed_and_wait(ctx, embed)
        return

    if not player.playing and player.queue.is_empty:
        embed = discord.Embed(
            description="📭 คิวว่างเปล่า",
            color=discord.Color.light_grey()
        )
        await send_embed_and_wait(ctx, embed)
        return

    view = QueueView(ctx, player)
    msg = await ctx.send(embed=view.build_embed(), view=view)
    view.message = msg


@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    """ข้ามเพลงปัจจุบัน"""
    player: wavelink.Player = ctx.voice_client
    if player is None or not player.playing:
        embed = discord.Embed(
            description="❌ ไม่มีเพลงที่กำลังเล่น",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    current_title = player.current.title if player.current else "เพลง"

    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)  # fires 'replaced' → track_end ignores it
        embed = discord.Embed(
            title="⏭️ ข้ามเพลง",
            description=f"ข้าม **{current_title}**\n\n▶️ กำลังเล่น: **[{next_track.title}]({next_track.uri})**",
            color=discord.Color.orange()
        )
    else:
        await player.stop()  # queue ว่าง → หยุดเล่น, track_end จะ idle_disconnect
        embed = discord.Embed(
            description=f"⏭️ ข้าม **{current_title}** — คิวว่างเปล่าแล้ว",
            color=discord.Color.orange()
        )

    embed.set_footer(
        text=f"ขอโดย {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )
    await send_embed_and_wait(ctx, embed)


@bot.command(name='stop', aliases=['st'])
async def stop(ctx):
    """หยุดเล่นและเคลียร์คิว"""
    player: wavelink.Player = ctx.voice_client
    if player is None:
        embed = discord.Embed(
            description="❌ บอทไม่ได้อยู่ใน voice channel",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    queue_count = len(player.queue)
    player.queue.clear()
    await player.stop()
    embed = discord.Embed(
        title="⏹️ หยุดเล่น",
        description=f"เคลียร์คิว `{queue_count}` เพลงแล้ว",
        color=discord.Color.red()
    )
    embed.set_footer(
        text=f"ขอโดย {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )
    await send_embed_and_wait(ctx, embed)


@bot.command(name='join', aliases=['j'])
async def join(ctx, *, channel: discord.VoiceChannel = None):
    """สั่งบอทเข้าห้อง voice channel"""
    if channel is None:
        if ctx.author.voice is None:
            embed = discord.Embed(
                description="❌ คุณต้องอยู่ใน voice channel หรือระบุชื่อห้องเสียง",
                color=discord.Color.red()
            )
            await send_embed_and_wait(ctx, embed)
            return
        channel = ctx.author.voice.channel

    player: wavelink.Player = ctx.voice_client
    if player is not None and player.channel == channel:
        embed = discord.Embed(
            description=f"✅ บอทอยู่ในห้องเสียง `{channel.name}` แล้ว",
            color=discord.Color.green()
        )
        await send_embed_and_wait(ctx, embed)
        return

    try:
        if player is not None:
            try:
                await player.move_to(channel)
            except Exception as e:
                raise
        else:
            await channel.connect(cls=wavelink.Player, self_deaf=True)
        embed = discord.Embed(
            description=f"✅ เข้าห้องเสียง `{channel.name}` แล้ว",
            color=discord.Color.green()
        )
    except Exception as e:
        embed = discord.Embed(
            title="❌ เข้าห้องเสียงไม่ได้",
            description=f"```{str(e)[:200]}```",
            color=discord.Color.red()
        )
    await send_embed_and_wait(ctx, embed)


@bot.command(name='kick', aliases=['leave', 'disconnect', 'dc'])
async def kick(ctx):
    """หยุดเพลงชั่วคราว"""
    player: wavelink.Player = ctx.voice_client
    if player is None or not player.playing:
        embed = discord.Embed(
            description="❌ ไม่มีเพลงที่กำลังเล่น",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    if player.paused:
        embed = discord.Embed(
            description="⚠️ เพลงถูกหยุดอยู่แล้ว ใช้ `!resume` เพื่อเล่นต่อ",
            color=discord.Color.yellow()
        )
        await send_embed_and_wait(ctx, embed)
        return

    await player.pause(True)
    embed = discord.Embed(
        description="⏸️ หยุดเพลงชั่วคราว",
        color=discord.Color.yellow()
    )
    embed.set_footer(
        text=f"ขอโดย {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )
    await send_embed_and_wait(ctx, embed)


@bot.command(name='resume', aliases=['r'])
async def resume(ctx):
    """เล่นเพลงต่อ"""
    player: wavelink.Player = ctx.voice_client
    if player is None:
        embed = discord.Embed(
            description="❌ บอทไม่ได้อยู่ใน voice channel",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    if not player.paused:
        embed = discord.Embed(
            description="⚠️ เพลงไม่ได้ถูกหยุดอยู่",
            color=discord.Color.yellow()
        )
        await send_embed_and_wait(ctx, embed)
        return

    await player.pause(False)
    embed = discord.Embed(
        description="▶️ เล่นเพลงต่อ",
        color=discord.Color.green()
    )
    embed.set_footer(
        text=f"ขอโดย {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )
    await send_embed_and_wait(ctx, embed)


@bot.command(name='mute', aliases=['m'])
async def mute(ctx):
    """ปิดเสียงบอทใน voice channel"""
    player: wavelink.Player = ctx.voice_client
    if player is None or player.channel is None:
        embed = discord.Embed(
            description="❌ บอทไม่ได้อยู่ใน voice channel",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    voice_state = ctx.guild.me.voice if ctx.guild and ctx.guild.me else None
    if voice_state and voice_state.self_mute:
        embed = discord.Embed(
            description="⚠️ บอทถูกปิดเสียงอยู่แล้ว",
            color=discord.Color.yellow()
        )
        await send_embed_and_wait(ctx, embed)
        return

    try:
        await ctx.guild.change_voice_state(channel=player.channel, self_mute=True, self_deaf=True)
        embed = discord.Embed(
            description="🔇 บอทถูกปิดเสียงแล้ว",
            color=discord.Color.dark_grey()
        )
        embed.set_footer(
            text=f"ขอโดย {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )
        await send_embed_and_wait(ctx, embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ ไม่สามารถปิดเสียงบอทได้",
            description=f"```{str(e)[:200]}```",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)


@bot.command(name='unmute', aliases=['um'])
async def unmute(ctx):
    """เปิดเสียงบอทใน voice channel"""
    player: wavelink.Player = ctx.voice_client
    if player is None or player.channel is None:
        embed = discord.Embed(
            description="❌ บอทไม่ได้อยู่ใน voice channel",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
        return

    voice_state = ctx.guild.me.voice if ctx.guild and ctx.guild.me else None
    if voice_state and not voice_state.self_mute:
        embed = discord.Embed(
            description="⚠️ บอทยังไม่ถูกปิดเสียง",
            color=discord.Color.yellow()
        )
        await send_embed_and_wait(ctx, embed)
        return

    try:
        await ctx.guild.change_voice_state(channel=player.channel, self_mute=False, self_deaf=True)
        embed = discord.Embed(
            description="🔊 บอทเปิดเสียงแล้ว",
            color=discord.Color.green()
        )
        embed.set_footer(
            text=f"ขอโดย {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )
        await send_embed_and_wait(ctx, embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ ไม่สามารถเปิดเสียงบอทได้",
            description=f"```{str(e)[:200]}```",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)


@bot.command(name='help', aliases=['h', 'commands'])
async def help_command(ctx):
    """แสดงรายการคำสั่ง"""
    embed = discord.Embed(
        title="🎵 Music Bot",
        description="คำสั่งทั้งหมดของบอท",
        color=discord.Color.gold()
    )
    embed.add_field(name="🎶 `!play` / `!p`", value="เล่นเพลงจาก YouTube/SoundCloud หรือ URL แล้วบอทจะเข้าห้องเสียงของคนสั่ง ถ้าใช้ใน Discord", inline=False)
    embed.add_field(name="▶️ `!join` / `!j`", value="สั่งบอทเข้าห้องเสียง (ถ้าไม่ได้อยู่ voice)", inline=False)
    embed.add_field(name="📜 `!queue` / `!q`", value="ดูคิวเพลง (มีปุ่มพลิกหน้า)", inline=True)
    embed.add_field(name="⏭️ `!skip` / `!s`", value="ข้ามเพลง", inline=True)
    embed.add_field(name="⏹️ `!stop` / `!st`", value="หยุดและเคลียร์คิว", inline=True)
    embed.add_field(name="⏸️ `!pause` / `!ps`", value="หยุดชั่วคราว", inline=True)
    embed.add_field(name="▶️ `!resume` / `!r`", value="เล่นต่อ", inline=True)
    embed.add_field(name="🔇 `!mute` / `!m`", value="ปิดเสียงบอทใน voice", inline=True)
    embed.add_field(name="🔊 `!unmute` / `!um`", value="เปิดเสียงบอทใน voice", inline=True)
    embed.add_field(name="👋 `!kick` / `!dc`", value="เตะบอทออก", inline=True)
    embed.set_footer(text="ใช้ ! นำหน้าทุกคำสั่ง • ตัวย่ออยู่หลัง /")
    await send_embed_and_wait(ctx, embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CheckFailure):
        return
    print(f"Error: {type(error).__name__}: {error}")
    try:
        embed = discord.Embed(
            title="❌ เกิดข้อผิดพลาด",
            description=f"```{str(error)[:300]}```",
            color=discord.Color.red()
        )
        await send_embed_and_wait(ctx, embed)
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
