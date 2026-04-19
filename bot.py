import os
import telebot
import threading
import time
from flask import Flask
from pymongo import MongoClient

# Environment Variables
API_TOKEN = os.getenv('API_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

bot = telebot.TeleBot(API_TOKEN)

# MongoDB Connection
client = MongoClient(MONGO_URI)
db = client['broadcast_db']
channels_col = db['channels']

# --- डमी वेब सर्व्हर (रेंडरसाठी) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- चॅनेल ॲड करा ---
@bot.message_handler(commands=['add'])
def add_channel(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "📖 वापर: `/add -100xxxxxxxx`", parse_mode="Markdown")
            return
        chat_id = args[1].strip()
        if channels_col.find_one({'chat_id': chat_id}):
            bot.reply_to(message, "⚠️ हा चॅनेल आधीच लिस्टमध्ये आहे.")
        else:
            channels_col.insert_one({'chat_id': chat_id})
            bot.reply_to(message, f"✅ यशस्वीरित्या ॲड झाला: `{chat_id}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ एरर: {e}")

# --- लिस्ट बघा ---
@bot.message_handler(commands=['list'])
def list_channels(message):
    channels = list(channels_col.find())
    if not channels:
        bot.reply_to(message, "📪 अजून एकही चॅनेल ॲड केलेला नाही.")
        return
    msg = "📋 **तुमचे चॅनेल्स:**\n\n"
    for i, c in enumerate(channels, 1):
        msg += f"{i}. `{c['chat_id']}`\n"
    bot.reply_to(message, msg, parse_mode="Markdown")

# --- मेसेज ब्रॉडकास्ट ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'])
def broadcast(message):
    if message.text and message.text.startswith('/'):
        return
    all_channels = list(channels_col.find())
    if not all_channels:
        bot.reply_to(message, "❌ आधी चॅनेल ॲड करा! (/add)")
        return
    success = 0
    for c in all_channels:
        try:
            bot.copy_message(c['chat_id'], message.chat.id, message.message_id)
            success += 1
        except:
            pass
    bot.reply_to(message, f"✅ {success} चॅनेलवर मेसेज पाठवला!")

if __name__ == "__main__":
    # ४०९ एरर कायमचा घालवण्यासाठी: जुने कनेक्शन्स तोडा
    try:
        bot.remove_webhook()
        time.sleep(2)
    except:
        pass

    # वेब सर्व्हर सुरू करा
    threading.Thread(target=run_server).start()
    
    # बॉट सुरू करा (जुने अडकलेले मेसेज सोडून द्या)
    bot.infinity_polling(skip_pending=True)
