import os
import logging
import json
import time
import re
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
MY_ID = os.getenv('ADMIN_ID')

if not TOKEN:
    raise ValueError("❌ ОШИБКА: Токен не найден! Создай файл .env с BOT_TOKEN=...")

if not MY_ID:
    raise ValueError("❌ ОШИБКА: ADMIN_ID не найден! Создай файл .env с ADMIN_ID=...")

try:
    MY_ID = int(MY_ID)
except:
    raise ValueError("❌ ОШИБКА: ADMIN_ID должен быть числом!")

# ============================================
# НАСТРОЙКИ ФИЛЬТРОВ (ПО УМОЛЧАНИЮ)
# ============================================
DEFAULT_SETTINGS = {
    'filter_links': True,
    'filter_stickers': True,
    'filter_caps': True,
    'filter_sticker_flood': True,
    'filter_swear': True,
    'caps_limit': 50,
    'min_length': 5,
    'sticker_flood_limit': 5,
    'sticker_flood_time': 60,
    'chat_creator': 0,
    'custom_admins': [],
    'chat_title': 'Неизвестный чат',
    'added_date': '',
    'last_seen': '',
    'is_group': False  # Отличаем группы от личных чатов
}

SETTINGS_FILE = 'bot_settings.json'
sticker_tracker = defaultdict(list)

# ============================================
# СПИСОК МАТОВ
# ============================================
SWEAR_WORDS = [
    'хуй', 'пизд', 'ебл', 'еба', 'ёб', 'бля', 'блять', 'сука', 'пиздец',
    'нахер', 'нафиг', 'похер', 'хер', 'мудак', 'гандон', 'пидор', 'педик',
    'шлюх', 'простит', 'далбаеб', 'долбоеб', 'ебан', 'ебну', 'раком',
    'залуп', 'манда', 'сперм', 'мошонк', 'яичк', 'член', 'пенис', 'вагин',
    'трах', 'секс', 'fuck', 'shit', 'asshole', 'bitch', 'whore', 'slut',
]

# ============================================
# ЗАГРУЗКА НАСТРОЕК
# ============================================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки настроек: {e}")
            return {}
    return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        print("💾 Настройки сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения настроек: {e}")

chat_settings = load_settings()

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def get_chat_settings(chat_id):
    chat_id_str = str(chat_id)
    if chat_id_str not in chat_settings:
        chat_settings[chat_id_str] = DEFAULT_SETTINGS.copy()
        chat_settings[chat_id_str]['added_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_settings(chat_settings)
    return chat_settings[chat_id_str]

def is_admin(chat_id, user_id):
    """Проверяет, является ли пользователь админом бота в этом чате"""
    settings = get_chat_settings(chat_id)
    
    # Создатель чата
    if settings.get('chat_creator') == user_id:
        return True
    
    # Главный админ
    if user_id == MY_ID:
        return True
    
    # Дополнительные админы
    if user_id in settings.get('custom_admins', []):
        return True
    
    return False

# ============================================
# ФУНКЦИИ ПРОВЕРКИ
# ============================================
def is_tg_link(text):
    if not text:
        return False
    return 't.me/' in text.lower()

def is_bad_sticker(sticker):
    if not sticker or not sticker.set_name:
        return False
    
    name = sticker.set_name.lower()
    bad_words = ['nsfw', '18+', 'sex', 'porn', 'adult', 'hentai', 'xxx']
    
    for word in bad_words:
        if word in name:
            return True
    return False

def is_too_many_caps(text, limit=50, min_length=5):
    if not text or len(text) < min_length:
        return False
    
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    
    caps = sum(1 for c in letters if c.isupper())
    percent = (caps / len(letters)) * 100
    
    return percent > limit

def contains_swear(text):
    if not text:
        return False
    
    text_lower = text.lower()
    for word in SWEAR_WORDS:
        if word in text_lower:
            return True
    return False

def check_sticker_flood(user_id, chat_id, limit=5, time_window=60):
    key = f"{user_id}:{chat_id}"
    current_time = time.time()
    
    sticker_tracker[key] = [t for t in sticker_tracker[key] if current_time - t < time_window]
    sticker_tracker[key].append(current_time)
    
    return len(sticker_tracker[key]) > limit

# ============================================
# КОМАНДЫ
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"╔════════════════════════╗\n"
        f"║   *ДОБРО ПОЖАЛОВАТЬ*   ║\n"
        f"║      👋 {user.first_name}      ║\n"
        f"╚════════════════════════╝\n\n"
        f"*🤖 ANTISPAM БОТ*\n"
        f"Я защищаю группы от спама\n\n"
        f"*🔍 ЧТО ПРОВЕРЯЮ:*\n"
        f"• 🔗 Ссылки на Telegram\n"
        f"• 🔞 18+ стикеры\n"
        f"• 🔠 Сообщения КАПСОМ\n"
        f"• 🎭 Флуд стикерами\n"
        f"• 🤬 Нецензурная лексика\n\n"
        f"*📋 КОМАНДЫ:*\n"
        f"╔══════════════════╗\n"
        f"║  📚 /help        ║\n"
        f"║  📊 /status      ║\n"
        f"║  ⚙️ /settings    ║\n"
        f"║  👑 /admin       ║\n"
        f"║  🗑️ /delchat     ║\n"
        f"╚══════════════════╝"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"╔════════════════╗\n"
        f"║   *📚 ПОМОЩЬ*   ║\n"
        f"╚════════════════╝\n\n"
        f"*КАК ИСПОЛЬЗОВАТЬ:*\n"
        f"1️⃣ Добавь бота в группу\n"
        f"2️⃣ Сделай его администратором\n"
        f"3️⃣ Настрой фильтры через /settings\n\n"
        f"*👑 АДМИНЫ БОТА:*\n"
        f"• /admin - управление админами\n"
        f"• Тот, кто добавил бота - главный админ\n"
        f"• Можно добавлять других админов\n"
        f"• Админы не проверяются\n\n"
        f"*🗑️ УДАЛЕНИЕ ЧАТОВ:*\n"
        f"• /delchat - удалить чат из настроек"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"╔════════════════╗\n║   *📊 СТАТУС*   ║\n╚════════════════╝\n\n"
    
    found_chats = False
    for chat_id_str, settings in chat_settings.items():
        # Пропускаем личные чаты в статусе
        if not settings.get('is_group', False):
            continue
            
        try:
            chat = await context.bot.get_chat(int(chat_id_str))
            chat_title = chat.title or "Личный чат"
            creator_id = settings.get('chat_creator', 0)
            admins_count = len(settings.get('custom_admins', []))
            added_date = settings.get('added_date', 'неизвестно')
            
            text += f"*📌 {chat_title}*\n"
            text += f"🆔 ID: `{chat_id_str}`\n"
            text += f"👑 Создатель: {creator_id}\n"
            text += f"👥 Доп. админы: {admins_count}\n"
            text += f"📅 Добавлен: {added_date}\n"
            text += f"• 🔗 Ссылки: {'✅' if settings.get('filter_links', True) else '❌'}\n"
            text += f"• 🔞 18+ стикеры: {'✅' if settings.get('filter_stickers', True) else '❌'}\n"
            text += f"• 🔠 Капс: {'✅' if settings.get('filter_caps', True) else '❌'} ({settings.get('caps_limit', 50)}%)\n"
            text += f"• 🎭 Флуд: {'✅' if settings.get('filter_sticker_flood', True) else '❌'} (макс. {settings.get('sticker_flood_limit', 5)})\n"
            text += f"• 🤬 Маты: {'✅' if settings.get('filter_swear', True) else '❌'}\n\n"
            found_chats = True
        except Exception as e:
            chat_title = settings.get('chat_title', 'Неизвестный чат')
            text += f"*📌 {chat_title} (недоступен)*\n"
            text += f"🆔 ID: `{chat_id_str}`\n"
            text += f"• 🔗 Ссылки: {'✅' if settings.get('filter_links', True) else '❌'}\n"
            text += f"• 🔞 18+ стикеры: {'✅' if settings.get('filter_stickers', True) else '❌'}\n"
            text += f"• 🔠 Капс: {'✅' if settings.get('filter_caps', True) else '❌'} ({settings.get('caps_limit', 50)}%)\n"
            text += f"• 🎭 Флуд: {'✅' if settings.get('filter_sticker_flood', True) else '❌'} (макс. {settings.get('sticker_flood_limit', 5)})\n"
            text += f"• 🤬 Маты: {'✅' if settings.get('filter_swear', True) else '❌'}\n\n"
            found_chats = True
    
    if not found_chats:
        text += "❌ Бот еще не добавлен в группы."
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для управления админами бота"""
    user = update.effective_user
    
    # Показываем список чатов, где пользователь админ (только группы)
    keyboard = []
    for chat_id_str, settings in chat_settings.items():
        if not settings.get('is_group', False):
            continue
        if is_admin(chat_id_str, user.id):
            try:
                chat = await context.bot.get_chat(int(chat_id_str))
                chat_title = chat.title or "Группа"
                keyboard.append([InlineKeyboardButton(f"👑 {chat_title}", callback_data=f"admin_{chat_id_str}")])
            except:
                chat_title = settings.get('chat_title', 'Неизвестная группа')
                keyboard.append([InlineKeyboardButton(f"👑 {chat_title}", callback_data=f"admin_{chat_id_str}")])
    
    if not keyboard:
        await update.message.reply_text("❌ У тебя нет прав админа ни в одной группе!")
        return
    
    await update.message.reply_text(
        "👑 *УПРАВЛЕНИЕ АДМИНАМИ*\n\nВыбери группу:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for chat_id_str, settings in chat_settings.items():
        if not settings.get('is_group', False):
            continue
        try:
            chat = await context.bot.get_chat(int(chat_id_str))
            chat_title = chat.title or "Группа"
            keyboard.append([InlineKeyboardButton(f"⚙️ {chat_title}", callback_data=f"chat_{chat_id_str}")])
        except:
            chat_title = settings.get('chat_title', 'Неизвестная группа')
            keyboard.append([InlineKeyboardButton(f"⚙️ {chat_title}", callback_data=f"chat_{chat_id_str}")])
    
    if not keyboard:
        await update.message.reply_text("❌ Бот еще не добавлен ни в одну группу!", parse_mode="Markdown")
        return
    
    await update.message.reply_text(
        "⚙️ *НАСТРОЙКИ*\n\nВыбери группу:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def delchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != MY_ID:
        await update.message.reply_text("❌ Эта команда только для главного админа!")
        return
    
    if not chat_settings:
        await update.message.reply_text("📭 Нет сохраненных чатов.")
        return
    
    keyboard = []
    for chat_id_str, settings in list(chat_settings.items()):
        if not settings.get('is_group', False):
            continue
        try:
            chat = await context.bot.get_chat(int(chat_id_str))
            chat_title = chat.title or "Группа"
            keyboard.append([InlineKeyboardButton(f"❌ {chat_title}", callback_data=f"delchat_{chat_id_str}")])
        except:
            chat_title = settings.get('chat_title', 'Неизвестная группа')
            keyboard.append([InlineKeyboardButton(f"❌ {chat_title}", callback_data=f"delchat_{chat_id_str}")])
    
    keyboard.append([InlineKeyboardButton("🔙 ОТМЕНА", callback_data="delchat_cancel")])
    
    await update.message.reply_text(
        "🗑 *Выбери группу для удаления:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# ОБРАБОТКА КНОПОК
# ============================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith("admin_"):
        chat_id = data.replace("admin_", "")
        if not is_admin(chat_id, user_id):
            await query.edit_message_text("❌ У тебя нет прав в этой группе!")
            return
        
        settings = get_chat_settings(chat_id)
        admins_list = settings.get('custom_admins', [])
        
        try:
            chat = await context.bot.get_chat(int(chat_id))
            chat_title = chat.title or "Группа"
        except:
            chat_title = settings.get('chat_title', 'Неизвестная группа')
        
        text = f"👑 *Админы группы: {chat_title}*\n\n"
        text += f"👑 Главный админ: ID `{settings.get('chat_creator', 'неизвестен')}`\n\n"
        text += "*Дополнительные админы:*\n"
        
        if admins_list:
            for admin_id in admins_list:
                text += f"• ID: `{admin_id}`\n"
        else:
            text += "• Нет дополнительных админов\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ ДОБАВИТЬ АДМИНА", callback_data=f"addadmin_{chat_id}")],
            [InlineKeyboardButton("➖ УДАЛИТЬ АДМИНА", callback_data=f"removeadmin_{chat_id}")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_admin")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("addadmin_"):
        chat_id = data.replace("addadmin_", "")
        if not is_admin(chat_id, user_id):
            await query.edit_message_text("❌ У тебя нет прав в этой группе!")
            return
        
        await query.edit_message_text(
            "📝 *ДОБАВЛЕНИЕ АДМИНА*\n\n"
            "Отправь мне ID пользователя, которого хочешь сделать админом.\n\n"
            "🔍 *Как узнать ID?*\n"
            "1. Напиши @userinfobot\n"
            "2. Перешли любое сообщение от пользователя\n"
            "3. Отправь полученный ID сюда\n\n"
            "❗️ Отправь только число!",
            parse_mode="Markdown"
        )
        context.user_data['adding_admin_for'] = chat_id
    
    elif data.startswith("removeadmin_"):
        chat_id = data.replace("removeadmin_", "")
        if not is_admin(chat_id, user_id):
            await query.edit_message_text("❌ У тебя нет прав в этой группе!")
            return
        
        settings = get_chat_settings(chat_id)
        admins_list = settings.get('custom_admins', [])
        
        if not admins_list:
            await query.edit_message_text("❌ Нет админов для удаления!")
            return
        
        keyboard = []
        for admin_id in admins_list:
            keyboard.append([InlineKeyboardButton(f"❌ ID: {admin_id}", callback_data=f"deladmin_{chat_id}_{admin_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data=f"admin_{chat_id}")])
        
        await query.edit_message_text(
            "👑 *Выбери админа для удаления:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("deladmin_"):
        parts = data.split("_")
        chat_id = parts[1]
        admin_id = int(parts[2])
        
        if not is_admin(chat_id, user_id):
            await query.edit_message_text("❌ У тебя нет прав в этой группе!")
            return
        
        settings = get_chat_settings(chat_id)
        if admin_id in settings.get('custom_admins', []):
            settings['custom_admins'].remove(admin_id)
            save_settings(chat_settings)
            await query.edit_message_text(f"✅ Админ {admin_id} удален!")
            time.sleep(1)
            new_query = update
            new_query.callback_query.data = f"admin_{chat_id}"
            await button_handler(new_query, context)
    
    elif data == "back_to_admin":
        keyboard = []
        for chat_id_str, settings in chat_settings.items():
            if not settings.get('is_group', False):
                continue
            if is_admin(chat_id_str, user_id):
                try:
                    chat = await context.bot.get_chat(int(chat_id_str))
                    chat_title = chat.title or "Группа"
                    keyboard.append([InlineKeyboardButton(f"👑 {chat_title}", callback_data=f"admin_{chat_id_str}")])
                except:
                    chat_title = settings.get('chat_title', 'Неизвестная группа')
                    keyboard.append([InlineKeyboardButton(f"👑 {chat_title}", callback_data=f"admin_{chat_id_str}")])
        
        await query.edit_message_text(
            "👑 *УПРАВЛЕНИЕ АДМИНАМИ*\n\nВыбери группу:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("chat_"):
        chat_id = data.replace("chat_", "")
        settings = get_chat_settings(chat_id)
        
        try:
            chat = await context.bot.get_chat(int(chat_id))
            chat_title = chat.title or "Группа"
        except:
            chat_title = settings.get('chat_title', 'Неизвестная группа')
        
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_links', True) else '❌'} 🔗 Ссылки", callback_data=f"toggle_links_{chat_id}")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_stickers', True) else '❌'} 🔞 18+ стикеры", callback_data=f"toggle_stickers_{chat_id}")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_caps', True) else '❌'} 🔠 Капс ({settings.get('caps_limit', 50)}%)", callback_data=f"toggle_caps_{chat_id}")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_sticker_flood', True) else '❌'} 🎭 Флуд (макс. {settings.get('sticker_flood_limit', 5)})", callback_data=f"toggle_flood_{chat_id}")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_swear', True) else '❌'} 🤬 Маты", callback_data=f"toggle_swear_{chat_id}")],
            [InlineKeyboardButton("📊 ЛИМИТ КАПСА", callback_data=f"caps_limit_{chat_id}")],
            [InlineKeyboardButton("🎭 ЛИМИТ ФЛУДА", callback_data=f"flood_limit_{chat_id}")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_settings")]
        ]
        
        await query.edit_message_text(
            f"⚙️ *{chat_title}*\n\nНажми для включения/выключения:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data == "back_to_settings":
        keyboard = []
        for chat_id_str, settings in chat_settings.items():
            if not settings.get('is_group', False):
                continue
            try:
                chat = await context.bot.get_chat(int(chat_id_str))
                chat_title = chat.title or "Группа"
                keyboard.append([InlineKeyboardButton(f"⚙️ {chat_title}", callback_data=f"chat_{chat_id_str}")])
            except:
                chat_title = settings.get('chat_title', 'Неизвестная группа')
                keyboard.append([InlineKeyboardButton(f"⚙️ {chat_title}", callback_data=f"chat_{chat_id_str}")])
        
        await query.edit_message_text(
            "⚙️ *НАСТРОЙКИ*\n\nВыбери группу:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("toggle_"):
        parts = data.split("_")
        action = parts[1]
        chat_id = parts[2]
        settings = get_chat_settings(chat_id)
        
        if action == "links":
            settings['filter_links'] = not settings.get('filter_links', True)
        elif action == "stickers":
            settings['filter_stickers'] = not settings.get('filter_stickers', True)
        elif action == "caps":
            settings['filter_caps'] = not settings.get('filter_caps', True)
        elif action == "flood":
            settings['filter_sticker_flood'] = not settings.get('filter_sticker_flood', True)
        elif action == "swear":
            settings['filter_swear'] = not settings.get('filter_swear', True)
        
        save_settings(chat_settings)
        
        new_query = update
        new_query.callback_query.data = f"chat_{chat_id}"
        await button_handler(new_query, context)
    
    elif data.startswith("caps_limit_"):
        chat_id = data.replace("caps_limit_", "")
        keyboard = [
            [InlineKeyboardButton("30%", callback_data=f"set_caps_{chat_id}_30")],
            [InlineKeyboardButton("50%", callback_data=f"set_caps_{chat_id}_50")],
            [InlineKeyboardButton("70%", callback_data=f"set_caps_{chat_id}_70")],
            [InlineKeyboardButton("80%", callback_data=f"set_caps_{chat_id}_80")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data=f"chat_{chat_id}")]
        ]
        await query.edit_message_text(
            "📊 *ВЫБЕРИ ЛИМИТ КАПСА*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("flood_limit_"):
        chat_id = data.replace("flood_limit_", "")
        keyboard = [
            [InlineKeyboardButton("3 стикера", callback_data=f"set_flood_{chat_id}_3")],
            [InlineKeyboardButton("5 стикеров", callback_data=f"set_flood_{chat_id}_5")],
            [InlineKeyboardButton("7 стикеров", callback_data=f"set_flood_{chat_id}_7")],
            [InlineKeyboardButton("10 стикеров", callback_data=f"set_flood_{chat_id}_10")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data=f"chat_{chat_id}")]
        ]
        await query.edit_message_text(
            "🎭 *ВЫБЕРИ ЛИМИТ ФЛУДА*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("set_caps_"):
        parts = data.split("_")
        chat_id = parts[2]
        limit = int(parts[3])
        settings = get_chat_settings(chat_id)
        settings['caps_limit'] = limit
        save_settings(chat_settings)
        await query.edit_message_text(f"✅ Лимит капса изменен на {limit}%")
        time.sleep(1)
        new_query = update
        new_query.callback_query.data = f"chat_{chat_id}"
        await button_handler(new_query, context)
    
    elif data.startswith("set_flood_"):
        parts = data.split("_")
        chat_id = parts[2]
        limit = int(parts[3])
        settings = get_chat_settings(chat_id)
        settings['sticker_flood_limit'] = limit
        save_settings(chat_settings)
        await query.edit_message_text(f"✅ Лимит флуда изменен на {limit}")
        time.sleep(1)
        new_query = update
        new_query.callback_query.data = f"chat_{chat_id}"
        await button_handler(new_query, context)
    
    elif data == "delchat_cancel":
        await query.edit_message_text("❌ Удаление отменено.")
    
    elif data.startswith("delchat_"):
        chat_id = data.replace("delchat_", "")
        if chat_id in chat_settings:
            chat_title = chat_settings[chat_id].get('chat_title', 'Неизвестная группа')
            del chat_settings[chat_id]
            save_settings(chat_settings)
            await query.edit_message_text(f"✅ Группа {chat_title} удалена из настроек!")

# ============================================
# ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ (ТОЛЬКО ДЛЯ ЛИЧКИ!)
# ============================================
async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения только в личных чатах"""
    
    # Проверяем, что это личный чат
    if update.effective_chat.type != "private":
        return
    
    # Проверяем, ждем ли мы ID для добавления админа
    if 'adding_admin_for' not in context.user_data:
        return
    
    chat_id = context.user_data['adding_admin_for']
    user_id = update.effective_user.id
    
    if not is_admin(chat_id, user_id):
        await update.message.reply_text("❌ У тебя нет прав!")
        del context.user_data['adding_admin_for']
        return
    
    try:
        new_admin_id = int(update.message.text.strip())
        settings = get_chat_settings(chat_id)
        
        if 'custom_admins' not in settings:
            settings['custom_admins'] = []
        
        if new_admin_id in settings['custom_admins']:
            await update.message.reply_text("❌ Этот пользователь уже админ!")
        elif new_admin_id == settings.get('chat_creator'):
            await update.message.reply_text("❌ Это создатель чата, он уже админ!")
        elif new_admin_id == MY_ID:
            await update.message.reply_text("❌ Это главный админ бота!")
        else:
            settings['custom_admins'].append(new_admin_id)
            save_settings(chat_settings)
            await update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен в админы!")
        
        del context.user_data['adding_admin_for']
        
    except ValueError:
        await update.message.reply_text("❌ Это не ID! Отправь число.")

# ============================================
# ПРОВЕРКА СООБЩЕНИЙ В ГРУППАХ
# ============================================
async def check_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет сообщения только в группах"""
    
    # Работаем только в группах
    if update.effective_chat.type == "private":
        return
    
    message = update.message
    if not message:
        return
    
    user = message.from_user
    chat = message.chat
    
    if user.is_bot:
        return
    
    settings = get_chat_settings(chat.id)
    settings['chat_title'] = chat.title or "Группа"
    settings['is_group'] = True
    settings['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_settings(chat_settings)
    
    # Пропускаем админов
    if user.id == MY_ID:
        return
    
    if settings.get('chat_creator') == user.id:
        return
    
    if user.id in settings.get('custom_admins', []):
        return
    
    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    # Проверка стикеров
    if message.sticker:
        if settings.get('filter_sticker_flood', True):
            if check_sticker_flood(user.id, chat.id, settings.get('sticker_flood_limit', 5)):
                await message.delete()
                await message.reply_text(f"@{user.username} ❗ *НЕ ФЛУДИ СТИКЕРАМИ!*", parse_mode="Markdown")
                return
        
        if settings.get('filter_stickers', True) and is_bad_sticker(message.sticker):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *18+ СТИКЕРЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
    
    # Проверка текста
    if message.text:
        if settings.get('filter_links', True) and is_tg_link(message.text):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *ССЫЛКИ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_swear', True) and contains_swear(message.text):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *МАТЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_caps', True) and is_too_many_caps(message.text, settings.get('caps_limit', 50)):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *НЕ КРИЧИ!*", parse_mode="Markdown")
            return
    
    # Проверка подписей
    if message.caption:
        if settings.get('filter_links', True) and is_tg_link(message.caption):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *ССЫЛКИ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_swear', True) and contains_swear(message.caption):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *МАТЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_caps', True) and is_too_many_caps(message.caption, settings.get('caps_limit', 50)):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *НЕ КРИЧИ!*", parse_mode="Markdown")
            return

# ============================================
# НОВЫЙ ЧАТ
# ============================================
async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Когда бота добавляют в новый чат"""
    message = update.message
    if not message or not message.new_chat_members:
        return
    
    # Игнорируем личные чаты
    if message.chat.type == "private":
        return
    
    for member in message.new_chat_members:
        if member.id == context.bot.id:
            chat_id = str(message.chat.id)
            adder_id = message.from_user.id
            chat_title = message.chat.title or "Группа"
            
            if chat_id not in chat_settings:
                settings = DEFAULT_SETTINGS.copy()
                settings['chat_creator'] = adder_id
                settings['chat_title'] = chat_title
                settings['is_group'] = True
                settings['added_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                settings['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                chat_settings[chat_id] = settings
                save_settings(chat_settings)
                
                try:
                    await context.bot.send_message(
                        MY_ID,
                        f"✅ Бот добавлен в группу!\n\n"
                        f"📌 Название: {chat_title}\n"
                        f"🆔 ID: {chat_id}\n"
                        f"👑 Добавил: {adder_id}"
                    )
                except:
                    pass

# ============================================
# ЗАПУСК
# ============================================
def main():
    print("=" * 60)
    print("╔══════════════════════════╗")
    print("║  ANTISPAM БОТ ЗАПУЩЕН   ║")
    print("╚══════════════════════════╝")
    print("=" * 60)
    print(f"📌 Токен загружен из .env")
    print(f"📌 Твой ID: {MY_ID}")
    
    # Подсчет только групп
    groups_count = sum(1 for s in chat_settings.values() if s.get('is_group', False))
    print(f"📌 Групп в настройках: {groups_count}")
    print("=" * 60)
    print("📋 Доступные команды:")
    print("   🚀 /start  - Приветствие")
    print("   📚 /help   - Помощь")
    print("   📊 /status - Статус")
    print("   ⚙️ /settings - Настройки")
    print("   👑 /admin  - Управление админами")
    print("   🗑️ /delchat - Удалить группу")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("delchat", delchat_command))
    
    # Обработчики кнопок
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик текста ТОЛЬКО для личных сообщений
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
        handle_private_text
    ))
    
    # Обработчик сообщений в группах
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Sticker.ALL) & filters.ChatType.GROUPS,
        check_group
    ))
    
    # Обработчик добавления в новые чаты
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        new_chat_member
    ))
    
    print("✅ Бот работает! Нажми Ctrl+C для остановки")
    print("=" * 60)
    
    app.run_polling()

if __name__ == '__main__':
    main()