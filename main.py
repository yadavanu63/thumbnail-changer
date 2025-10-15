import os
import asyncio
from pathlib import Path
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# --- CONFIG: use env vars (set these in Heroku Config Vars) ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# --- Client ---
app = Client("thumb_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# temp storage dir
TMP_DIR = Path("./tmp")
TMP_DIR.mkdir(exist_ok=True)

# per-user thumbnail state: user_id -> {"path": str}
thumbs = {}

START_TEXT = """Hi {name} 👋
Send me a photo first (this will be used as thumbnail), then send the video/file and I'll apply it as the video's thumbnail — I will keep the original caption unchanged.
"""

START_BUTTON = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Source (example)", url="https://github.com/soebb/thumb-change-bot")]]
)

# helper: convert image to JPG and ensure size < 200 KB
def prepare_thumb(in_path: Path) -> Path:
    # convert to jpg path
    jpg_path = in_path.with_suffix(".jpg")
    img = Image.open(in_path).convert("RGB")
    # Save with initial quality
    quality = 90
    img.save(jpg_path, "JPEG", quality=quality)
    # reduce until <200 KB (Telegram requires <= 200 KB for video thumbnails)
    max_bytes = 200 * 1024
    while jpg_path.stat().st_size > max_bytes and quality > 20:
        quality -= 10
        img.save(jpg_path, "JPEG", quality=quality)
    # remove source if different
    try:
        if in_path.exists() and in_path != jpg_path:
            in_path.unlink(missing_ok=True)
    except Exception:
        pass
    return jpg_path

# cleanup helper
async def safe_remove(path: Path):
    try:
        if path and path.exists():
            path.unlink()
    except Exception:
        pass

# /start or /thumb
@app.on_message(filters.private & filters.command(["start", "thumb"]))
async def cmd_start(c: Client, m: Message):
    text = START_TEXT.format(name=m.from_user.first_name or "there")
    await m.reply_text(text, reply_markup=START_BUTTON)

# handle photos (thumbnail from user)
@app.on_message(filters.private & filters.photo)
async def photo_handler(c: Client, m: Message):
    user_id = m.from_user.id
    msg = await m.reply_text("✅ Received photo. Saving thumbnail...")
    # download photo
    path = await c.download_media(m.photo, file_name=str(TMP_DIR / f"{user_id}_thumb"))
    if not path:
        await msg.edit("❌ Failed to download photo. Try again.")
        return
    # convert/prepare
    jpg_path = prepare_thumb(Path(path))
    # store
    thumbs[user_id] = {"path": str(jpg_path)}
    await msg.edit("✅ Thumbnail saved. Now send the video/file and I'll apply it.")

# handle videos/documents
@app.on_message(filters.private & (filters.video | filters.document))
async def video_handler(c: Client, m: Message):
    user_id = m.from_user.id

    # check if user has a saved thumb
    info = thumbs.get(user_id)
    if not info or not info.get("path"):
        await m.reply_text("You don't have a saved thumbnail. Send a photo first.")
        return

    thumb_path = Path(info["path"])
    # Ensure thumb file exists
    if not thumb_path.exists():
        await m.reply_text("Thumbnail file not found on server. Please resend the photo.")
        thumbs.pop(user_id, None)
        return

    status = await m.reply_text("🔁 Applying thumbnail — please wait...")

    # get video meta
    video_obj = m.video if m.video else m.document
    video_caption = m.caption if m.caption else None

    # Try fast/direct send: send video by file_id but with local thumb path
    try:
        # Pyrogram will accept video=file_id and thumb=local_path
        await c.send_video(
            chat_id=m.chat.id,
            video=video_obj.file_id,
            thumb=str(thumb_path),
            caption=video_caption,
            supports_streaming=True
        )
        await status.edit("✅ Video sent successfully with custom thumbnail!")
        # cleanup thumbnail: keep for next use (user may want to reuse). If you want one-time use, remove it here.
        return
    except Exception as e:
        # Direct method failed — fallback to download+reupload
        await status.edit(f"Direct send failed — trying fallback (may take longer)...")
        try:
            # download video to temp
            video_tmp = Path(await c.download_media(m, file_name=str(TMP_DIR / f"{user_id}_video")))
            # send by local paths
            await c.send_video(
                chat_id=m.chat.id,
                video=str(video_tmp),
                thumb=str(thumb_path),
                caption=video_caption,
                supports_streaming=True
            )
            await status.edit("✅ Video sent successfully with custom thumbnail!")
        except Exception as e2:
            await status.edit("❌ Failed to send video with thumbnail. Try smaller files or resend.")
        finally:
            # cleanup downloaded video
            try:
                if 'video_tmp' in locals() and video_tmp.exists():
                    await safe_remove(video_tmp)
            except Exception:
                pass

# optional: delete thumb command
@app.on_message(filters.private & filters.command("del_cover"))
async def del_cover_cmd(c: Client, m: Message):
    user_id = m.from_user.id
    info = thumbs.pop(user_id, None)
    if info and info.get("path"):
        try:
            await safe_remove(Path(info["path"]))
        except:
            pass
        await m.reply_text("✅ Your saved thumbnail was deleted.")
    else:
        await m.reply_text("You have no saved thumbnail.")

# optional: show cover
@app.on_message(filters.private & filters.command("show_cover"))
async def show_cover_cmd(c: Client, m: Message):
    user_id = m.from_user.id
    info = thumbs.get(user_id)
    if not info or not info.get("path") or not Path(info["path"]).exists():
        await m.reply_text("You don't have a saved cover.")
        return
    await c.send_photo(m.chat.id, info["path"], caption="🖼️ Your saved cover")

# cleanup all tmp files on shutdown (best-effort)
def cleanup_temp():
    try:
        for p in TMP_DIR.glob("*"):
            try:
                p.unlink()
            except:
                pass
    except:
        pass

if name == "main":
    print("Bot starting...")
    app.run()
