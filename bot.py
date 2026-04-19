import os
import telebot
from pymongo import MongoClient

# Environment Variables मिळवणे
API_TOKEN = os.getenv('API_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

bot = telebot.TeleBot(API_TOKEN)

# MongoDB जोडणी (Connection)
client = MongoClient(MONGO_URI)
db = client['broadcast_db']
channels_col = db['channels']

# चॅनेल ॲड करण्याची कमांड
@bot.message_handler(commands=['add'])
def add_channel(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "📖 वापर: /add -100xxxxxxxx")
            return
            
        chat_id = args[1].strip()
        if channels_col.find_one({'chat_id': chat_id}):
            bot.reply_to(message, "⚠️ हा चॅनेल आधीच लिस्टमध्ये आहे.")
        else:
            channels_col.insert_one({'chat_id': chat_id})
            bot.reply_to(message, f"✅ यशस्वीरित्या ॲड झाला: {chat_id}")
    except Exception as e:
        bot.reply_to(message, f"❌ एरर: {e}")

# चॅनेल्सची लिस्ट बघणे
@bot.message_handler(commands=['list'])
def list_channels(message):
    channels = list(channels_col.find())
    if not channels:
        bot.reply_to(message, "📪 अजून एकही चॅनेल ॲड केलेला नाही.")
        return
    
    msg = "📋 तुमचे चॅनेल्स:\n\n"
    for i, c in enumerate(channels, 1):
        msg += f"{i}. {c['chat_id']}\n"
    bot.reply_to(message, msg)

# मेसेज फॉरवर्ड करणे (Broadcast)
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'])
def broadcast(message):
    if message.text and message.text.startswith('/'):
        return

    all_channels = list(channels_col.find())
    for c in all_channels:
        try:
            bot.copy_message(c['chat_id'], message.chat.id, message.message_id)
        except:
            pass
