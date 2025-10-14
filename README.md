# VideoThumbnailBot (MongoDB) — Heroku-ready

This repository contains a Telegram bot (Pyrogram) that:
- Lets each user save a custom thumbnail by sending a photo.
- When the user sends a video, the bot resends it using the user's saved thumbnail.
- Commands:
  - `/start` - bot info
  - `/show_cover` - view saved thumbnail
  - `/del_cover` - delete saved thumbnail

## Required environment variables (Heroku Config Vars)
- `API_ID` - from my.telegram.org
- `API_HASH` - from my.telegram.org
- `BOT_TOKEN` - from BotFather
- `MONGO_URI` - MongoDB connection string (MongoDB Atlas recommended)
- `DB_NAME` (optional) - default `thumbnail_bot`

## Deploy on Heroku (quick)
1. Create GitHub repo and push these files.
2. Create a Heroku app.
3. In Heroku app settings → Config Vars, add `API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_URI`.
4. Connect GitHub repo to Heroku or push via `heroku git:remote -a <your-app>`.
5. In Heroku dashboard or CLI scale the worker: `heroku ps:scale worker=1`.
6. Monitor logs: `heroku logs --tail`.

## MongoDB Atlas quick
1. Create a free cluster at https://www.mongodb.com/cloud/atlas
2. Create database user and password.
3. Whitelist your IP or use `0.0.0.0/0` for testing.
4. Get connection string and replace `<username>`, `<password>`, `<dbname>` accordingly.
5. Set the connection string as `MONGO_URI` in Heroku config vars.

## Notes
- This bot stores the Telegram `file_id` of the saved thumbnail in MongoDB (small and efficient).
- If you want thumbnails stored as raw images in DB, ask and I will provide GridFS version.
- Keep `DB_NAME` optional; default collection `thumbnails` will be used.
