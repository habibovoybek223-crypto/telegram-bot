import telebot
from telebot import types
import sqlite3
import threading
import time
import random

# ================== SOZLAMALAR ==================
TOKEN = "8345432903:AAFPxhG5ixBSynS9XS2oPWlRStcxF8JA5gY"
ADMIN_ID = 6898636523  # O'zingizning telegram ID (int)
# ===============================================

bot = telebot.TeleBot(TOKEN)

# ================== GLOBAL ==================
auto_post_interval = 0

# ================== DATABASE ==================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price TEXT,
    photo TEXT,
    likes INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY
)
""")

conn.commit()

# ================== START ==================
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "📊 Admin panel:\n\n"
            "/add - Mahsulot qo'shish\n"
            "/delete - Mahsulot o‘chirish\n"
            "/autopost - Auto post vaqtini belgilash"
        )
    else:
        bot.send_message(message.chat.id, "📦 Mahsulot nomini yozing.")

# ================== MAHSULOT QO‘SHISH ==================
@bot.message_handler(commands=['add'])
def add_product(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Mahsulot nomini kiriting:")
    bot.register_next_step_handler(msg, get_name)

def get_name(message):
    name = message.text
    msg = bot.send_message(message.chat.id, "Narxini kiriting:")
    bot.register_next_step_handler(msg, get_price, name)

def get_price(message, name):
    price = message.text
    msg = bot.send_message(message.chat.id, "Rasm yuboring:")
    bot.register_next_step_handler(msg, get_photo, name, price)

def get_photo(message, name, price):
    if message.photo:
        photo_id = message.photo[-1].file_id
        cursor.execute(
            "INSERT INTO products (name, price, photo) VALUES (?, ?, ?)",
            (name, price, photo_id)
        )
        conn.commit()
        bot.send_message(message.chat.id, "✅ Mahsulot saqlandi")
    else:
        bot.send_message(message.chat.id, "❌ Rasm yuboring!")

# ================== MAHSULOT O‘CHIRISH ==================
@bot.message_handler(commands=['delete'])
def delete_product(message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT id, name FROM products")
    products = cursor.fetchall()

    if not products:
        bot.send_message(message.chat.id, "❌ Mahsulotlar yo‘q")
        return

    markup = types.InlineKeyboardMarkup()

    for product in products:
        btn = types.InlineKeyboardButton(
            product[1],
            callback_data=f"delete_{product[0]}"
        )
        markup.add(btn)

    bot.send_message(
        message.chat.id,
        "🗑 O‘chirmoqchi bo‘lgan mahsulotni tanlang:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def confirm_delete(call):

    if call.from_user.id != ADMIN_ID:
        return

    product_id = call.data.split("_")[1]

    cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()

    bot.edit_message_text(
        "✅ Mahsulot o‘chirildi",
        call.message.chat.id,
        call.message.message_id
    )

# ================== GURUH ID SAQLASH + QIDIRUV ==================
@bot.message_handler(func=lambda message: message.chat.type in ["group", "supergroup"])
def group_handler(message):

    cursor.execute("INSERT OR IGNORE INTO groups (id) VALUES (?)", (message.chat.id,))
    conn.commit()

    if not message.text:
        return

    cursor.execute(
        "SELECT * FROM products WHERE name LIKE ?",
        ('%' + message.text + '%',)
    )
    product = cursor.fetchone()

    if product:
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(
            f"❤️ {product[4]}",
            callback_data=f"like_{product[0]}"
        )
        markup.add(btn)

        bot.send_photo(
            message.chat.id,
            product[3],
            caption=f"📦 {product[1]}\n💰 {product[2]}",
            reply_markup=markup
        )

# ================== LIKE ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("like_"))
def like_product(call):

    product_id = call.data.split("_")[1]

    cursor.execute(
        "UPDATE products SET likes = likes + 1 WHERE id=?",
        (product_id,)
    )
    conn.commit()

    cursor.execute("SELECT likes FROM products WHERE id=?", (product_id,))
    likes = cursor.fetchone()[0]

    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(
        f"❤️ {likes}",
        callback_data=f"like_{product_id}"
    )
    markup.add(btn)

    bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ================== AUTOPOST ==================
@bot.message_handler(commands=['autopost'])
def autopost_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Necha minutda auto post qilinsin?")
    bot.register_next_step_handler(msg, set_autopost)

def set_autopost(message):
    global auto_post_interval
    try:
        minutes = int(message.text)
        auto_post_interval = minutes * 60
        bot.send_message(
            message.chat.id,
            f"✅ Har {minutes} minutda auto post ishlaydi"
        )
    except:
        bot.send_message(message.chat.id, "❌ Faqat raqam kiriting")

def auto_post():
    global auto_post_interval
    while True:
        if auto_post_interval > 0:
            time.sleep(auto_post_interval)

            cursor.execute("SELECT * FROM products")
            products = cursor.fetchall()

            if not products:
                continue

            product = random.choice(products)

            cursor.execute("SELECT id FROM groups")
            groups = cursor.fetchall()

            for group in groups:
                chat_id = group[0]

                markup = types.InlineKeyboardMarkup()
                btn = types.InlineKeyboardButton(
                    f"❤️ {product[4]}",
                    callback_data=f"like_{product[0]}"
                )
                markup.add(btn)

                try:
                    bot.send_photo(
                        chat_id,
                        product[3],
                        caption=f"🔥 Auto Post\n\n📦 {product[1]}\n💰 {product[2]}",
                        reply_markup=markup
                    )
                except:
                    pass
        else:
            time.sleep(5)

# ================== THREAD START ==================
threading.Thread(target=auto_post, daemon=True).start()

print("Bot ishga tushdi...")
bot.polling(none_stop=True)
