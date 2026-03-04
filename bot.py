import os
import logging
import json
import time
import re
import threading
from flask import Flask
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

# ============================================
# ЗАГРУЗКА ПЕРЕМЕННЫХ ИЗ .env ФАЙЛА
# ============================================
load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

if not TOKEN:
    raise ValueError("❌ ОШИБКА: Токен не найден! Создай файл .env с BOT_TOKEN=...")

if not ADMIN_ID:
    raise ValueError("❌ ОШИБКА: ADMIN_ID не найден! Создай файл .env с ADMIN_ID=...")

try:
    ADMIN_ID = int(ADMIN_ID)
except:
    raise ValueError("❌ ОШИБКА: ADMIN_ID должен быть числом!")

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ============================================
# НАСТРОЙКИ ФИЛЬТРОВ
# ============================================
SETTINGS_FILE = 'bot_settings.json'
sticker_tracker = defaultdict(list)

# База данных чатов (только группы!)
chat_data = {}

def load_chat_data():
    """Загружает данные о чатах"""
    global chat_data
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            print(f"✅ Загружено {len(chat_data)} чатов")
        except:
            chat_data = {}
    else:
        chat_data = {}

def save_chat_data():
    """Сохраняет данные о чатах"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

# Загружаем данные при старте
load_chat_data()

# ============================================
# СПИСОК МАТОВ
# ============================================
BAD_WORDS = [
    'хуй', 'пизд', 'ебл', 'еба', 'ёб', 'бля', 'блять', 'сука', 'пиздец',
    'нахер', 'нафиг', 'похер', 'хер', 'мудак', 'гандон', 'пидор', 'педик',
    'шлюх', 'далбаеб', 'долбоеб', 'ебан', 'ебну', 'fuck', 'shit', 'asshole'
]

# ============================================
# ФУНКЦИИ ПРОВЕРКИ
# ============================================
def has_tg_link(text):
    """Проверяет ссылки на Telegram"""
    if not text:
        return False
    return 't.me/' in text.lower()

def is_18_sticker(sticker):
    """Проверяет 18+ стикеры"""
    if not sticker or not sticker.set_name:
        return False
    
    name = sticker.set_name.lower()
    bad = ['nsfw', '18+', 'sex', 'porn', 'adult', 'hentai', 'xxx']
    return any(word in name for word in bad)

def is_caps(text, limit=50):
    """Проверяет капс"""
    if not text or len(text) < 5:
        return False
    
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    
    caps = sum(1 for c in letters if c.isupper())
    percent = (caps / len(letters)) * 100
    return percent > limit

def has_swear(text):
    """Проверяет маты"""
    if not text:
        return False
    
    text = text.lower()
    for word in BAD_WORDS:
        if word in text:
            return True
    return False

def is_flood(user_id, chat_id, limit=5):
    """Проверяет флуд стикерами"""
    key = f"{user_id}:{chat_id}"
    now = time.time()
    
    # Очищаем старые записи (старше 60 секунд)
    sticker_tracker[key] = [t for t in sticker_tracker.get(key, []) if now - t < 60]
    
    # Добавляем новый стикер
    if key not in sticker_tracker:
        sticker_tracker[key] = []
    sticker_tracker[key].append(now)
    
    return len(sticker_tracker[key]) > limit

# ============================================
# ПРОВЕРКА ПРАВ
# ============================================
def is_chat_admin(chat_id, user_id):
    """Проверяет, является ли пользователь админом в этом чате"""
    chat = chat_data.get(str(chat_id), {})
    
    # Главный админ бота
    if user_id == ADMIN_ID:
        return True
    
    # Тот, кто добавил бота
    if chat.get('creator') == user_id:
        return True
    
    # Дополнительные админы
    if user_id in chat.get('admins', []):
        return True
    
    return False

# ============================================
# КОМАНДЫ
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"╔════════════════════════╗\n"
        f"║   ДОБРО ПОЖАЛОВАТЬ!   ║\n"
        f"║      👋 {user.first_name}      ║\n"
        f"╚════════════════════════╝\n\n"
        f"Я антиспам бот. Защищаю группы от:\n"
        f"• 🔗 Ссылок на Telegram\n"
        f"• 🔞 18+ стикеров\n"
        f"• 🔠 КАПСА\n"
        f"• 🎭 Флуда стикерами\n"
        f"• 🤬 Матов\n\n"
        f"Команды:\n"
        f"/help - помощь\n"
        f"/admin - управление админами\n"
        f"/status - статус"
    )
    await update.message.reply_text(text)

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"Как использовать:\n"
        f"1. Добавь бота в группу\n"
        f"2. Сделай его администратором\n"
        f"3. Настройки через /admin\n\n"
        f"Админы бота не проверяются!"
    )
    await update.message.reply_text(text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not chat_data:
        await update.message.reply_text("❌ Бот не добавлен ни в одну группу")
        return
    
    text = "📊 СТАТУС:\n\n"
    for chat_id, data in chat_data.items():
        try:
            chat = await context.bot.get_chat(int(chat_id))
            name = chat.title or "Группа"
            text += f"• {name}\n"
            text += f"  Админов: {len(data.get('admins', []))}\n"
        except:
            pass
    
    await update.message.reply_text(text)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление админами"""
    user = update.effective_user
    
    # Показываем только группы, где пользователь админ
    buttons = []
    for chat_id, data in chat_data.items():
        if is_chat_admin(chat_id, user.id):
            try:
                chat = await context.bot.get_chat(int(chat_id))
                name = chat.title or "Группа"
                buttons.append([InlineKeyboardButton(f"👑 {name}", callback_data=f"admin_{chat_id}")])
            except:
                pass
    
    if not buttons:
        await update.message.reply_text("❌ Нет доступных групп")
        return
    
    await update.message.reply_text(
        "Выбери группу:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ============================================
# ОБРАБОТКА КНОПОК
# ============================================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith("admin_"):
        chat_id = data.replace("admin_", "")
        
        if not is_chat_admin(chat_id, user_id):
            await query.edit_message_text("❌ Нет прав")
            return
        
        chat = chat_data.get(chat_id, {})
        admins = chat.get('admins', [])
        
        text = f"👑 Админы:\n\n"
        text += f"• Создатель: {chat.get('creator', '?')}\n"
        if admins:
            text += "\nДополнительные:\n"
            for a in admins:
                text += f"• {a}\n"
        else:
            text += "\nНет дополнительных админов"
        
        buttons = [
            [InlineKeyboardButton("➕ Добавить", callback_data=f"add_{chat_id}")],
            [InlineKeyboardButton("➖ Удалить", callback_data=f"remove_{chat_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif data.startswith("add_"):
        chat_id = data.replace("add_", "")
        context.user_data['waiting_for'] = ('add_admin', chat_id)
        await query.edit_message_text(
            "Отправь ID пользователя:"
        )
    
    elif data.startswith("remove_"):
        chat_id = data.replace("remove_", "")
        chat = chat_data.get(chat_id, {})
        admins = chat.get('admins', [])
        
        if not admins:
            await query.edit_message_text("❌ Нет админов для удаления")
            return
        
        buttons = []
        for a in admins:
            buttons.append([InlineKeyboardButton(f"❌ {a}", callback_data=f"del_{chat_id}_{a}")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"admin_{chat_id}")])
        
        await query.edit_message_text(
            "Выбери админа:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif data.startswith("del_"):
        parts = data.split("_")
        chat_id = parts[1]
        admin_id = int(parts[2])
        
        if chat_id in chat_data:
            if admin_id in chat_data[chat_id].get('admins', []):
                chat_data[chat_id]['admins'].remove(admin_id)
                save_chat_data()
                await query.edit_message_text(f"✅ Админ {admin_id} удален")
        
        # Возврат
        new_query = update
        new_query.callback_query.data = f"admin_{chat_id}"
        await button(new_query, context)
    
    elif data == "back":
        await admin(update, context)

# ============================================
# ОБРАБОТКА ТЕКСТА (ДЛЯ ДОБАВЛЕНИЯ АДМИНОВ)
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текст только в ЛС для добавления админов"""
    
    if update.effective_chat.type != "private":
        return
    
    if 'waiting_for' not in context.user_data:
        return
    
    action, chat_id = context.user_data['waiting_for']
    user_id = update.effective_user.id
    
    if action == 'add_admin' and is_chat_admin(chat_id, user_id):
        try:
            new_admin = int(update.message.text.strip())
            
            if chat_id not in chat_data:
                chat_data[chat_id] = {'admins': []}
            if 'admins' not in chat_data[chat_id]:
                chat_data[chat_id]['admins'] = []
            
            if new_admin in chat_data[chat_id]['admins']:
                await update.message.reply_text("❌ Уже админ")
            else:
                chat_data[chat_id]['admins'].append(new_admin)
                save_chat_data()
                await update.message.reply_text(f"✅ Админ {new_admin} добавлен")
        
        except:
            await update.message.reply_text("❌ Нужно отправить число")
        
        del context.user_data['waiting_for']

# ============================================
# ПРОВЕРКА СООБЩЕНИЙ В ГРУППАХ
# ============================================
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет сообщения в группах"""
    
    if update.effective_chat.type == "private":
        return
    
    msg = update.message
    if not msg:
        return
    
    user = msg.from_user
    chat = msg.chat
    
    if user.is_bot:
        return
    
    # Пропускаем админов
    if is_chat_admin(chat.id, user.id):
        return
    
    # Пропускаем админов Telegram
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    # Получаем настройки чата (пока все по умолчанию)
    settings = chat_data.get(str(chat.id), {})
    
    # Проверка стикеров
    if msg.sticker:
        # Флуд
        if is_flood(user.id, chat.id):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} не флуди стикерами!")
            except:
                pass
            return
        
        # 18+
        if is_18_sticker(msg.sticker):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} 18+ стикеры запрещены!")
            except:
                pass
            return
    
    # Проверка текста
    text = msg.text or msg.caption
    if text:
        # Ссылки
        if has_tg_link(text):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ссылки на Telegram запрещены!")
            except:
                pass
            return
        
        # Маты
        if has_swear(text):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} маты запрещены!")
            except:
                pass
            return
        
        # Капс
        if is_caps(text):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} не кричи!")
            except:
                pass
            return

# ============================================
# НОВЫЙ ЧАТ
# ============================================
async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Когда бота добавляют в новый чат"""
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    
    # Только группы
    if msg.chat.type == "private":
        return
    
    for member in msg.new_chat_members:
        if member.id == context.bot.id:
            chat_id = str(msg.chat.id)
            adder_id = msg.from_user.id
            
            # Сохраняем информацию о чате
            chat_data[chat_id] = {
                'creator': adder_id,
                'admins': [],
                'added': datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            save_chat_data()
            
            # Уведомляем админа
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"✅ Бот добавлен в группу!\n"
                    f"Название: {msg.chat.title}\n"
                    f"ID: {chat_id}\n"
                    f"Добавил: {adder_id}"
                )
            except:
                pass

# ============================================
# ЗАПУСК
# ============================================
def main():
    print("=" * 60)
    print("╔══════════════════════════╗")
    print("║     ANTISPAM БОТ         ║")
    print("╚══════════════════════════╝")
    print("=" * 60)
    print(f"✅ Твой ID: {ADMIN_ID}")
    print(f"✅ Групп в базе: {len(chat_data)}")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("admin", admin))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button))
    
    # Текст (только для ЛС)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        text_handler
    ))
    
    # Проверка сообщений в группах
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Sticker.ALL) & filters.ChatType.GROUPS,
        check
    ))
    
    # Новые чаты
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        new_chat
    ))
    
    print("✅ Бот запущен!")
    print("=" * 60)
    
    app.run_polling()

if __name__ == '__main__':
    main()
    # ============================================
# ЗАСТАВЛЯЕМ RENDER ЗАТКНУТЬСЯ
# ============================================
import os
import threading
from flask import Flask

# Создаём простой веб-сервер
web_app = Flask(__name__)

@web_app.route('/')
@web_app.route('/health')
@web_app.route('/healthz')
def health_check():
    return "Bot is alive!", 200

def run_web_server():
    """Запускаем сервер на порту, который требует Render"""
    port = int(os.environ.get('PORT', 10000))
    web_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Запускаем сервер в отдельном потоке
threading.Thread(target=run_web_server, daemon=True).start()
print("✅ Веб-сервер для Render запущен на порту", os.environ.get('PORT', 10000))