import os
import asyncio
import threading
from flask import Flask
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient

# Flask सर्व्हर 
web_app = Flask(__name__)
@web_app.route('/')
def keep_alive(): return "Bot is alive!", 200

# Pyrogram क्लायंट
app = Client(
    "mtc_unified_bot", 
    api_id=30767171, 
    api_hash="af363a055e5c68096847d64871c758c5", 
    bot_token=os.environ.get("API_TOKEN")
)

# डेटाबेस
mongo_client = AsyncIOMotorClient(os.environ.get("MONGO_URI"))
db = mongo_client.mtc_unified_db
marathi_col, hindi_col, msg_col = db.marathi_channels, db.hindi_channels, db.messages

# --- ब्रॉडकास्ट आणि इतर फंक्शन्स (हे जसेच्या तसे ठेव) ---
@app.on_message(filters.private & filters.user(int(os.environ.get("ADMIN_ID"))) & filters.command(["broadcast_marathi", "broadcast_hindi"]))
async def b_cast(client, message):
    if not message.reply_to_message: return await message.reply_text("❌ रिप्लाय द्या!")
    col = marathi_col if "marathi" in message.text else hindi_col
    mode = "marathi" if "marathi" in message.text else "hindi"
    sent_ids = []
    sent_count = 0
    async for ch in col.find({}):
        try:
            sent = await message.reply_to_message.copy(ch['chat_id'])
            sent_ids.append([ch['chat_id'], sent.id])
            sent_count += 1
            await asyncio.sleep(2) 
        except Exception as e: print(e); continue
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ पूर्ण झाले! {sent_count} चॅनेल्स.")

@app.on_message(filters.private & filters.command("start"))
async def start(c, m): await m.reply_text("🚀 MTC Unified Bot सक्रिय आहे!")

# --- Main Entry Point ---
async def main():
    await app.start()
    print("Bot is Running...")
    # बॉटला जिवंत ठेवा
    await asyncio.Event().wait()

if __name__ == "__main__":
    # Flask ला पोर्टवर लाँच करा
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=port), daemon=True).start()
    # बॉट सुरू करा
    asyncio.run(main())
