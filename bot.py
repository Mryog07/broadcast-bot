import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

# --- वेब सर्व्हर (रेंडरसाठी) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MTC Unified Bot is Running!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# --- कॉन्फिग ---
BOT_TOKEN = os.environ.get("API_TOKEN")
MONGO_URL = os.environ.get("MONGO_URI")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
API_ID = 30767171  
API_HASH = "af363a055e5c68096847d64871c758c5"  

app = Client("mtc_unified_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.mtc_unified_db
marathi_col = db.marathi_channels
hindi_col = db.hindi_channels
msg_col = db.messages

scheduler = AsyncIOScheduler()

# --- ब्रॉडकास्ट फंक्शन (फिक्स केलेले) ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["broadcast_marathi", "broadcast_hindi"]))
async def b_cast(client, message):
    if not message.reply_to_message: return await message.reply_text("❌ रिप्लाय द्या!")
    
    col = marathi_col if "marathi" in message.text else hindi_col
    # प्रत्येक वेळी डेटाबेसवरून ताजी लिस्ट घेणे
    channels = await col.find({}).to_list(length=300)
    
    chat_ids = [ch['chat_id'] for ch in channels]
    sent_ids = []
    sent_count = 0
    
    # बॅचिंग करून पोस्ट करणे
    for i in range(0, len(chat_ids), 2):
        batch = chat_ids[i:i+2]
        for c_id in batch:
            try:
                sent = await message.reply_to_message.copy(c_id)
                sent_ids.append([c_id, sent.id])
                sent_count += 1
            except Exception as e:
                print(f"Error: {e}")
                continue
        await asyncio.sleep(5)
        
    mode = "marathi" if "marathi" in message.text else "hindi"
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ डेटाबेस तपासला! {sent_count} चॅनेल्सवर ब्रॉडकास्ट पूर्ण!")

# --- इतर कमांड्स ---
@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    await message.reply_text("🚀 **MTC Unified Bot सुरु आहे!**")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["add_marathi", "add_hindi"]))
async def add_ch(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    if len(message.command) < 2: return await message.reply_text("❌ ID द्या!")
    try:
        c_id = int(message.command[1].strip())
        await col.update_one({"chat_id": c_id}, {"$set": {"chat_id": c_id}}, upsert=True)
        await message.reply_text(f"✅ चॅनेल {c_id} सेव्ह झाला!")
    except: await message.reply_text("❌ आयडी आकड्यांत द्या!")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["delete_marathi", "delete_hindi"]))
async def del_cast(client, message):
    mode = "marathi" if "marathi" in message.text else "hindi"
    data = await msg_col.find_one({"type": mode})
    if data and "sent_ids" in data:
        for c_id, m_id in data["sent_ids"]:
            try: await client.delete_messages(c_id, m_id)
            except: pass
        await msg_col.delete_one({"type": mode})
        await message.reply_text(f"🗑️ पोस्ट डिलीट केली!")
    else: await message.reply_text("❌ डेटा नाही.")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["stats_marathi", "stats_hindi"]))
async def show_stats(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    count = await col.count_documents({})
    await message.reply_text(f"📊 {count} चॅनेल्स जोडलेले आहेत.")

async def main():
    scheduler.start()
    await app.start()
    print("MTC Unified Bot Ready! 🚀")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
