import os
import logging
import json
import threading
from flask import Flask
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
# ФАЙЛ ДЛЯ ХРАНЕНИЯ НАСТРОЕК
# ============================================
SETTINGS_FILE = 'filters_settings.json'

# Настройки по умолчанию для каждого чата
DEFAULT_FILTERS = {
    'links': True,      # ссылки
    'stickers': True,   # 18+ стикеры
    'caps': True,       # капс
    'swear': True,      # маты
    'flood': True       # флуд стикерами
}

# Загружаем настройки
def load_filters():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_filters(filters):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(filters, f, ensure_ascii=False, indent=2)

# Глобальная переменная с настройками
chat_filters = load_filters()
print(f"✅ Загружены настройки для {len(chat_filters)} чатов")

# ============================================
# ПОЛУЧИТЬ НАСТРОЙКИ ЧАТА
# ============================================
def get_chat_filters(chat_id):
    chat_id = str(chat_id)
    if chat_id not in chat_filters:
        chat_filters[chat_id] = DEFAULT_FILTERS.copy()
        save_filters(chat_filters)
    return chat_filters[chat_id]

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

def is_caps(text):
    """Проверяет капс (больше 50% заглавных)"""
    if not text or len(text) < 5:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    caps = sum(1 for c in letters if c.isupper())
    return (caps / len(letters)) > 0.5

def has_swear(text):
    """Проверяет маты"""
    if not text:
        return False
    text = text.lower()
    bad_words = ['хуй', 'пизд', 'ебл', 'бля', 'сука', 'fuck', 'shit']
    return any(word in text for word in bad_words)

# ============================================
# ПРОВЕРКА ПРАВ
# ============================================
async def is_user_admin(update, context):
    """Проверяет, является ли пользователь админом"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Главный админ бота
    if user.id == ADMIN_ID:
        return True
    
    # Админ в чате
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ['administrator', 'creator']
    except:
        return False

# ============================================
# КОМАНДА /FILTERS - НАСТРОЙКА ФИЛЬТРОВ
# ============================================
async def filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настройки фильтров"""
    
    # Проверяем, что команда в группе и пользователь админ
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    if not await is_user_admin(update, context):
        await update.message.reply_text("❌ Только админы могут настраивать фильтры!")
        return
    
    chat_id = str(update.effective_chat.id)
    filters = get_chat_filters(chat_id)
    
    # Создаем кнопки с текущим статусом
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if filters['links'] else '❌'} 🔗 Ссылки на Telegram",
            callback_data="toggle_links"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['stickers'] else '❌'} 🔞 18+ стикеры",
            callback_data="toggle_stickers"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['caps'] else '❌'} 🔠 КАПС",
            callback_data="toggle_caps"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['swear'] else '❌'} 🤬 Маты",
            callback_data="toggle_swear"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['flood'] else '❌'} 🎭 Флуд стикерами",
            callback_data="toggle_flood"
        )]
    ]
    
    await update.message.reply_text(
        "⚙️ *НАСТРОЙКИ ФИЛЬТРОВ*\n\nНажми на фильтр, чтобы включить/выключить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# ОБРАБОТКА НАЖАТИЙ НА КНОПКИ
# ============================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_chat.id)
    filters = get_chat_filters(chat_id)
    
    # Переключаем фильтр
    if query.data == "toggle_links":
        filters['links'] = not filters['links']
    elif query.data == "toggle_stickers":
        filters['stickers'] = not filters['stickers']
    elif query.data == "toggle_caps":
        filters['caps'] = not filters['caps']
    elif query.data == "toggle_swear":
        filters['swear'] = not filters['swear']
    elif query.data == "toggle_flood":
        filters['flood'] = not filters['flood']
    
    # Сохраняем изменения
    save_filters(chat_filters)
    print(f"💾 Настройки сохранены для чата {chat_id}: {filters}")
    
    # Обновляем клавиатуру
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if filters['links'] else '❌'} 🔗 Ссылки на Telegram",
            callback_data="toggle_links"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['stickers'] else '❌'} 🔞 18+ стикеры",
            callback_data="toggle_stickers"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['caps'] else '❌'} 🔠 КАПС",
            callback_data="toggle_caps"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['swear'] else '❌'} 🤬 Маты",
            callback_data="toggle_swear"
        )],
        [InlineKeyboardButton(
            f"{'✅' if filters['flood'] else '❌'} 🎭 Флуд стикерами",
            callback_data="toggle_flood"
        )]
    ]
    
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# ПРОВЕРКА СООБЩЕНИЙ В ГРУППАХ
# ============================================
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет сообщения в группах"""
    
    # Работаем только в группах
    if update.effective_chat.type == "private":
        return
    
    message = update.message
    if not message:
        return
    
    user = message.from_user
    chat = message.chat
    
    # Пропускаем ботов
    if user.is_bot:
        return
    
    # Пропускаем главного админа
    if user.id == ADMIN_ID:
        return
    
    # Пропускаем админов чата
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    # Получаем настройки для этого чата
    filters = get_chat_filters(chat.id)
    print(f"🔍 Проверка сообщения в чате {chat.id}, настройки: {filters}")
    
    # Проверка стикеров
    if message.sticker:
        if filters['flood']:
            # Здесь можно добавить проверку флуда
            pass
        
        if filters['stickers'] and is_18_sticker(message.sticker):
            try:
                await message.delete()
                await message.reply_text(f"@{user.username} 🔞 18+ стикеры запрещены!")
                print(f"🚫 Удален 18+ стикер")
            except:
                pass
            return
    
    # Проверка текста
    text = message.text or message.caption
    if text:
        if filters['links'] and has_tg_link(text):
            try:
                await message.delete()
                await message.reply_text(f"@{user.username} 🔗 Ссылки на Telegram запрещены!")
                print(f"🚫 Удалена ссылка")
            except:
                pass
            return
        
        if filters['swear'] and has_swear(text):
            try:
                await message.delete()
                await message.reply_text(f"@{user.username} 🤬 Маты запрещены!")
                print(f"🚫 Удалены маты")
            except:
                pass
            return
        
        if filters['caps'] and is_caps(text):
            try:
                await message.delete()
                await message.reply_text(f"@{user.username} 🔠 Не кричи! КАПС запрещен!")
                print(f"🚫 Удален капс")
            except:
                pass
            return

# ============================================
# КОМАНДА START
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"Я антиспам бот. Добавь меня в группу и сделай админом.\n"
        f"В группе используй /filters для настройки."
    )

# ============================================
# ЗАПУСК
# ============================================
def main():
    print("=" * 60)
    print("🤖 ANTISPAM БОТ С ФИЛЬТРАМИ")
    print("=" * 60)
    print(f"✅ Твой ID: {ADMIN_ID}")
    print(f"✅ Загружено настроек: {len(chat_filters)}")
    print("=" * 60)
    print("📋 Команды:")
    print("   /filters - настройка фильтров (в группе)")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("filters", filters_command))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Проверка сообщений
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Sticker.ALL,
        check_message
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