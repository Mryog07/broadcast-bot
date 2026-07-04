import os
import asyncio
import threading
from flask import Flask
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient

# --- Flask वेब सर्व्हर (Keep Alive) ---
web_app = Flask(__name__)

@web_app.route('/')
def keep_alive():
    return "Bot is alive!", 200

def run_web():
    # Render ने दिलेल्या पोर्टवर सर्व्हर चालू करा
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- Pyrogram क्लायंट ---
app = Client(
    "mtc_unified_bot", 
    api_id=30767171, 
    api_hash="af363a055e5c68096847d64871c758c5", 
    bot_token=os.environ.get("API_TOKEN")
)

# --- डेटाबेस सेटिंग्ज ---
mongo_client = AsyncIOMotorClient(os.environ.get("MONGO_URI"))
db = mongo_client.mtc_unified_db
marathi_col, hindi_col, msg_col = db.marathi_channels, db.hindi_channels, db.messages

# --- ब्रॉडकास्ट फंक्शन ---
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
        except Exception as e:
            print(f"Error: {e}")
            continue
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ पूर्ण झाले! {sent_count} चॅनेल्स.")

# --- कमांड्स ---
@app.on_message(filters.private & filters.command("start"))
async def start(c, m): await m.reply_text("🚀 MTC Unified Bot सक्रिय आहे!")

# (इतर कमांड्स जशाच्या तशा ठेवल्या आहेत)
@app.on_message(filters.private & filters.command(["add_marathi", "add_hindi"]))
async def add_ch(c, m):
    col = marathi_col if "marathi" in m.text else hindi_col
    try:
        c_id = int(m.command[1].strip())
        await col.update_one({"chat_id": c_id}, {"$set": {"chat_id": c_id}}, upsert=True)
        await m.reply_text(f"✅ {c_id} सेव्ह झाला!")
    except: await m.reply_text("❌ आयडी चुकीचा आहे!")

@app.on_message(filters.private & filters.command(["delete_marathi", "delete_hindi"]))
async def del_cast(c, m):
    mode = "marathi" if "marathi" in m.text else "hindi"
    data = await msg_col.find_one({"type": mode})
    if data:
        for c_id, m_id in data["sent_ids"]:
            try: await c.delete_messages(c_id, m_id)
            except: pass
        await msg_col.delete_one({"type": mode})
        await m.reply_text("🗑️ पोस्ट डिलीट केली!")

@app.on_message(filters.private & filters.command(["stats_marathi", "stats_hindi"]))
async def show_stats(c, m):
    col = marathi_col if "marathi" in m.text else hindi_col
    count = await col.count_documents({})
    await m.reply_text(f"📊 {count} चॅनेल्स नोंदणीकृत.")

# --- सुधारित मेन लूप ---
async def main():
    await app.start()
    print("Bot is Running...")
    # Event().wait() ऐवजी, बॉट थांबणार नाही याची खात्री करण्यासाठी हे सोपे लॉजिक
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # १. Flask सर्व्हर थ्रेडमध्ये सुरू करा
    threading.Thread(target=run_web, daemon=True).start()
    # २. बॉट रन करा
    asyncio.run(main())
