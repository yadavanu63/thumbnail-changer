import os
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# Environment variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "thumbnail_bot")

if not (API_ID and API_HASH and BOT_TOKEN and MONGO_URI):
    raise RuntimeError("Missing one of required env vars: API_ID, API_HASH, BOT_TOKEN, MONGO_URI")

app = Client("video_thumbnail_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Mongo client & collection
mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]
thumbs = db.thumbnails
thumbs.create_index("user_id", unique=True)

def save_thumb_fileid(user_id: int, file_id: str):
    thumbs.update_one(
        {"user_id": user_id},
        {"$set": {"file_id": file_id, "saved_at": datetime.utcnow()}},
        upsert=True
    )

def get_thumb(user_id: int):
    return thumbs.find_one({"user_id": user_id})

def del_thumb(user_id: int):
    res = thumbs.delete_one({"user_id": user_id})
    return res.deleted_count

@app.on_message(filters.private & filters.command("start"))
async def start_cmd(c: Client, m: Message):
    txt = (
        f"Hi {m.from_user.first_name}!\n\n"
        "Welcome to 🎬 VideoThumbnailBot.\n\n"
        "How it works:\n"
        "1. Send a photo to set it as your thumbnail.\n"
        "2. Send a video and the bot will resend it with your saved thumbnail.\n\n"
        "Commands:\n"
        "/show_cover - View your saved thumbnail\n"
        "/del_cover - Delete your saved thumbnail"
    )
    await m.reply_text(txt)

@app.on_message(filters.private & filters.command("show_cover"))
async def show_cover(c: Client, m: Message):
    row = get_thumb(m.from_user.id)
    if not row:
        await m.reply_text("You don't have a saved cover. Send a photo to save one.")
        return
    try:
        await c.send_photo(m.chat.id, row["file_id"], caption="🖼️ Your saved thumbnail")
    except Exception:
        await m.reply_text("Couldn't send your saved thumbnail. Try sending a new one.")

@app.on_message(filters.private & filters.command("del_cover"))
async def delete_cover(c: Client, m: Message):
    removed = del_thumb(m.from_user.id)
    if removed:
        await m.reply_text("✅ Thumbnail deleted.")
    else:
        await m.reply_text("No thumbnail found.")

@app.on_message(filters.private & filters.photo)
async def photo_handler(c: Client, m: Message):
    # Pyrogram v2: m.photo is now a single Photo object (not a list)
    file_id = m.photo.file_id
    save_thumb_fileid(m.from_user.id, file_id)
    await m.reply_text("✅ Cover/Thumbnail saved successfully.")

@app.on_message(filters.private & (filters.video | filters.document))
async def video_handler(c: Client, m: Message):
    vid = None
    if m.video:
        vid = m.video
        video_file_id = vid.file_id
    elif m.document and m.document.mime_type and m.document.mime_type.startswith("video"):
        vid = m.document
        video_file_id = vid.file_id
    else:
        return

    row = get_thumb(m.from_user.id)
    if not row:
        await m.reply_text("You don't have a saved thumbnail. Send a photo first.")
        return

    thumb_file_id = row["file_id"]

    try:
        await c.send_video(
            chat_id=m.chat.id,
            video=video_file_id,
            thumb=thumb_file_id,
            caption="🎬 Here's your video with the applied thumbnail!",
            supports_streaming=True
        )
        return
    except Exception:
        # fallback: download and reupload
        await m.reply_text("Direct send failed — trying fallback (will take longer)...")
        tmp_path = None
        try:
            tmp_path = await c.download_media(m)
            await c.send_video(
                chat_id=m.chat.id,
                video=tmp_path,
                thumb=thumb_file_id,
                caption="🎬 Here's your video with the applied thumbnail!",
                supports_streaming=True
            )
        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except:
                pass

if __name__ == '__main__':
    print("Bot starting...")
    app.run()
