import os
import threading
from flask import Flask
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

# --- 1. Flask वेब सर्व्हर (Keep Alive साठी) ---
web_app = Flask(__name__)

@web_app.route('/')
def keep_alive():
    return "Bot is Active and Running!", 200

def run_flask():
    # Render वर पोर्ट 10000 डिफाल्ट असतो
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# --- 2. Pyrogram क्लायंट सेटअप ---
app = Client(
    "mtc_unified_bot",
    api_id=30767171,
    api_hash="af363a055e5c68096847d64871c758c5",
    bot_token=os.environ.get("API_TOKEN")
)

# --- 3. MongoDB कनेक्शन ---
mongo_uri = os.environ.get("MONGO_URI")
mongo_client = AsyncIOMotorClient(mongo_uri)
db = mongo_client.mtc_unified_db
marathi_col = db.marathi_channels
hindi_col = db.hindi_channels
msg_col = db.messages

# --- 4. ब्रॉडकास्ट फंक्शन (Full Logic) ---
@app.on_message(filters.private & filters.command(["broadcast_marathi", "broadcast_hindi"]))
async def b_cast(client, message):
    admin_id = int(os.environ.get("ADMIN_ID"))
    if message.from_user.id != admin_id: return
    
    if not message.reply_to_message: 
        return await message.reply_text("❌ रिप्लाय द्या!")
    
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
    await message.reply_text(f"✅ पूर्ण झाले! {sent_count} चॅनेल्सवर मेसेज पाठवला.")

# --- 5. इतर कमांड्स ---
@app.on_message(filters.private & filters.command("start"))
async def start(c, m): await m.reply_text("🚀 MTC Unified Bot सक्रिय आहे!")

@app.on_message(filters.private & filters.command(["add_marathi", "add_hindi"]))
async def add_ch(c, m):
    col = marathi_col if "marathi" in m.text else hindi_col
    try:
        c_id = int(m.command[1].strip())
        await col.update_one({"chat_id": c_id}, {"$set": {"chat_id": c_id}}, upsert=True)
        await m.reply_text(f"✅ {c_id} सेव्ह झाला!")
    except: await m.reply_text("❌ फॉरमॅट चुकीचा आहे!")

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

# --- 6. Stats फंक्शन ---
@app.on_message(filters.private & filters.command(["stats_marathi", "stats_hindi"]))
async def show_stats(c, m):
    print("Stats command received!")
    col = marathi_col if "marathi" in m.text else hindi_col
    try:
        count = await col.count_documents({})
        await m.reply_text(f"📊 सध्या {count} चॅनेल्स डेटाबेसमध्ये नोंदणीकृत आहेत.")
    except Exception as e:
        print(f"Stats Error: {e}")
        await m.reply_text("❌ डेटाबेस एरर आला आहे!")

# --- 7. मुख्य एक्झिक्युशन (सर्वात महत्त्वाचं) ---
if __name__ == "__main__":
    # Flask ला बॅकग्राउंड थ्रेडमध्ये सुरू करा
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Pyrogram बॉटला रन करा
    print("Bot is Running...")
    app.run()
