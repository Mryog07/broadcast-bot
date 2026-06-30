import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

# --- रेंडरला जिवंत ठेवण्यासाठी वेब सर्व्हर (सुधारित) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MTC Unified Bot is Running!")
        
    # GitHub Action च्या पिंगसाठी HEAD रिक्वेस्ट सपोर्ट
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

# --- सुधारीत मेमरी-फ्रेंडली ब्रॉडकास्ट फंक्शन (Batching) ---
async def scheduled_broadcast(chat_ids, reply_to_message, mode):
    sent_ids = []
    sent_count = 0
    
    # २-२ चॅनेल्सच्या बॅचेसमध्ये काम करणे
    for i in range(0, len(chat_ids), 2):
        batch = chat_ids[i:i+2]
        for c_id in batch:
            try:
                sent = await reply_to_message.copy(c_id)
                sent_ids.append([c_id, sent.id])
                sent_count += 1
            except: 
                continue
        # प्रत्येक बॅचनंतर ५ सेकंद विश्रांती (मेमरीसाठी अत्यंत महत्त्वाचे)
        await asyncio.sleep(5)
    
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    try: await reply_to_message.reply(f"✅ {sent_count} चॅनेल्सवर शेड्युल ब्रॉडकास्ट पूर्ण!")
    except: pass

@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    await message.reply_text("🚀 **MTC Unified Control Panel सुरु आहे!**")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["add_marathi", "add_hindi"]))
async def add_ch(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    if len(message.command) < 2: return await message.reply_text("❌ ID द्या!")
    try:
        c_id = int(message.command[1].strip())
        await col.update_one({"chat_id": c_id}, {"$set": {"chat_id": c_id}}, upsert=True)
        await message.reply_text(f"✅ चॅनेल {c_id} सेव्ह झाला!")
    except: await message.reply_text("❌ आयडी फक्त आकड्यांत द्या!")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["remove_marathi", "remove_hindi"]))
async def rem_ch(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    try:
        c_id = int(message.command[1].strip())
        await col.delete_one({"chat_id": c_id})
        await message.reply_text(f"🗑️ चॅनेल {c_id} काढला!")
    except: pass

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["stats_marathi", "stats_hindi"]))
async def show_stats(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    lang = "मराठी" if "marathi" in message.text else "हिंदी"
    count = await col.count_documents({})
    await message.reply_text(f"📊 सध्या {count} {lang} चॅनेल्स जोडलेले आहेत.")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["broadcast_marathi", "broadcast_hindi"]))
async def b_cast(client, message):
    if not message.reply_to_message: return await message.reply_text("❌ रिप्लाय द्या!")
    col = marathi_col if "marathi" in message.text else hindi_col
    channels = await col.find().to_list(length=300)
    
    chat_ids = [ch['chat_id'] for ch in channels]
    sent_ids = []
    sent_count = 0
    
    # मॅन्युअल ब्रॉडकास्टमध्येही बॅचिंग लावले आहे
    for i in range(0, len(chat_ids), 2):
        batch = chat_ids[i:i+2]
        for c_id in batch:
            try:
                sent = await message.reply_to_message.copy(c_id)
                sent_ids.append([c_id, sent.id])
                sent_count += 1
            except: 
                continue
        await asyncio.sleep(5)
        
    mode = "marathi" if "marathi" in message.text else "hindi"
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ {sent_count} चॅनेल्सवर ब्रॉडकास्ट पूर्ण!")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["schedule_marathi", "schedule_hindi"]))
async def schedule_cmd(client, message):
    if not message.reply_to_message or len(message.command) < 3: return await message.reply_text("❌ पद्धत: /schedule_marathi 10:05 AM")
    mode = "marathi" if "marathi" in message.text else "hindi"
    col = marathi_col if mode == "marathi" else hindi_col
    try:
        target_time = datetime.strptime(f"{datetime.now().date()} {message.command[1]} {message.command[2]}", "%Y-%m-%d %I:%M %p")
        run_date = target_time - timedelta(hours=5, minutes=30)
        channels = await col.find().to_list(length=300)
        chat_ids = [ch['chat_id'] for ch in channels]
        scheduler.add_job(scheduled_broadcast, 'date', run_date=run_date, args=[chat_ids, message.reply_to_message, mode])
        await message.reply_text(f"✅ पोस्ट {message.command[1]} {message.command[2]} ला शेड्युल झाली!")
    except Exception as e: await message.reply_text(f"❌ वेळ नीट द्या. Error: {e}")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["delete_marathi", "delete_hindi"]))
async def del_cast(client, message):
    mode = "marathi" if "marathi" in message.text else "hindi"
    data = await msg_col.find_one({"type": mode})
    if data:
        for c_id, m_id in data["sent_ids"]:
            try: await client.delete_messages(c_id, m_id)
            except: pass
        await msg_col.delete_one({"type": mode})
        await message.reply_text(f"🗑️ {mode} चॅनेलची पोस्ट डिलीट केली!")
    else: await message.reply_text("❌ डेटा नाही.")
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("test_error"))
async def test_err(client, message):
    if not message.reply_to_message: return await message.reply_text("❌ एखाद्या मेसेजला रिप्लाय देऊन ही कमांड द्या!")
    
    channels = await marathi_col.find().to_list(length=300)
    report = "📊 **टेस्ट रिपोर्ट:**\n\n"
    
    for ch in channels:
        c_id = ch['chat_id']
        try:
            await message.reply_to_message.copy(c_id)
            report += f"✅ `{c_id}` : यशस्वी\n"
        except Exception as e:
            report += f"❌ `{c_id}` : एरर - `{e}`\n"
        await asyncio.sleep(1)
        
    await message.reply_text(report)

async def main():
    scheduler.start()
    await app.start()
    print("MTC Unified Bot Started! 🚀")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
