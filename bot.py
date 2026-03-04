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
# ЗАГРУЗКА ПЕРЕМЕННЫХ ИЗ .env
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
SETTINGS_FILE = 'bot_settings.json'
sticker_tracker = defaultdict(list)

# ============================================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ============================================
DEFAULT_SETTINGS = {
    'filter_links': True,
    'filter_stickers': True,
    'filter_caps': True,
    'filter_flood': True,
    'filter_swear': True,
    'caps_limit': 50,
    'flood_limit': 5,
    'chat_creator': 0,
    'custom_admins': [],
    'chat_title': '',
    'added_date': ''
}

# Загружаем настройки
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_settings, f, ensure_ascii=False, indent=2)
        print("💾 Настройки сохранены")
    except:
        pass

chat_settings = load_settings()

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
    """Проверяет капс (больше 50% заглавных)"""
    if not text or len(text) < 5:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    caps = sum(1 for c in letters if c.isupper())
    return (caps / len(letters)) * 100 > limit

def has_swear(text):
    """Проверяет маты"""
    if not text:
        return False
    text = text.lower()
    bad_words = ['хуй', 'пизд', 'ебл', 'бля', 'сука', 'fuck', 'shit']
    return any(word in text for word in bad_words)

def is_flood(user_id, chat_id, limit=5):
    """Проверяет флуд стикерами"""
    key = f"{user_id}:{chat_id}"
    now = time.time()
    if key not in sticker_tracker:
        sticker_tracker[key] = []
    sticker_tracker[key] = [t for t in sticker_tracker[key] if now - t < 60]
    sticker_tracker[key].append(now)
    return len(sticker_tracker[key]) > limit

# ============================================
# ПРОВЕРКА АДМИНА
# ============================================
def is_admin(chat_id, user_id):
    """Проверяет, является ли пользователь админом бота"""
    chat = chat_settings.get(str(chat_id), {})
    if user_id == ADMIN_ID:
        return True
    if chat.get('chat_creator') == user_id:
        return True
    if user_id in chat.get('custom_admins', []):
        return True
    return False

# ============================================
# КОМАНДА START (ТВОЙ СТИЛЬ)
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"╔════════════════════════╗\n"
        f"║   *ДОБРО ПОЖАЛОВАТЬ*   ║\n"
        f"║      👤 {user.first_name}      ║\n"
        f"╚════════════════════════╝\n\n"
        f"*🤖 ANTISPAM БОТ*\n"
        f"Я защищаю группы от спама\n\n"
        f"*🔍 ЧТО ПРОВЕРЯЮ:*\n"
        f"• 🔗 Ссылки на Telegram\n"
        f"• 🔞 18+ стикеры\n"
        f"• 📢 Сообщения КАПСОМ\n"
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

# ============================================
# КОМАНДА HELP
# ============================================
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

# ============================================
# КОМАНДА STATUS
# ============================================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"╔════════════════╗\n║   *📊 СТАТУС*   ║\n╚════════════════╝\n\n"
    
    found_chats = False
    for chat_id_str, settings in chat_settings.items():
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
            text += f"• 📢 Капс: {'✅' if settings.get('filter_caps', True) else '❌'} ({settings.get('caps_limit', 50)}%)\n"
            text += f"• 🎭 Флуд: {'✅' if settings.get('filter_flood', True) else '❌'} (макс. {settings.get('flood_limit', 5)})\n"
            text += f"• 🤬 Маты: {'✅' if settings.get('filter_swear', True) else '❌'}\n\n"
            found_chats = True
        except:
            pass
    
    if not found_chats:
        text += "❌ Бот еще не добавлен ни в один чат!"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ============================================
# КОМАНДА SETTINGS
# ============================================
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id, user.id):
        await update.message.reply_text("❌ Только админы могут настраивать фильтры!")
        return
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
        save_settings()
    
    settings = chat_settings[chat_id]
    
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_links', True) else '❌'} 🔗 Ссылки", callback_data="toggle_links")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_stickers', True) else '❌'} 🔞 18+ стикеры", callback_data="toggle_stickers")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_caps', True) else '❌'} 📢 КАПС", callback_data="toggle_caps")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_flood', True) else '❌'} 🎭 Флуд", callback_data="toggle_flood")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_swear', True) else '❌'} 🤬 Маты", callback_data="toggle_swear")],
        [InlineKeyboardButton("📊 ЛИМИТ КАПСА", callback_data="caps_limit")],
        [InlineKeyboardButton("🎭 ЛИМИТ ФЛУДА", callback_data="flood_limit")]
    ]
    
    await update.message.reply_text(
        "⚙️ *НАСТРОЙКИ ФИЛЬТРОВ*\n\nНажми чтобы включить/выключить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# КОМАНДА ADMIN
# ============================================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id, user.id):
        await update.message.reply_text("❌ Только админы могут управлять админами!")
        return
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
        save_settings()
    
    settings = chat_settings[chat_id]
    admins = settings.get('custom_admins', [])
    
    text = f"👑 *АДМИНИСТРАТОРЫ*\n\n"
    text += f"👤 Главный админ: `{settings.get('chat_creator', 'неизвестен')}`\n"
    if admins:
        text += f"\n👥 Дополнительные:\n"
        for a in admins:
            text += f"• `{a}`\n"
    else:
        text += f"\n❌ Нет дополнительных админов"
    
    keyboard = [
        [InlineKeyboardButton("➕ ДОБАВИТЬ АДМИНА", callback_data="add_admin")],
        [InlineKeyboardButton("➖ УДАЛИТЬ АДМИНА", callback_data="remove_admin")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# КОМАНДА DELCHAT
# ============================================
async def delchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Только главный админ может удалять чаты!")
        return
    
    if not chat_settings:
        await update.message.reply_text("📭 Нет сохраненных чатов")
        return
    
    keyboard = []
    for chat_id, settings in chat_settings.items():
        title = settings.get('chat_title', 'Неизвестный чат')
        keyboard.append([InlineKeyboardButton(f"❌ {title}", callback_data=f"del_{chat_id}")])
    
    await update.message.reply_text(
        "🗑 *ВЫБЕРИ ЧАТ ДЛЯ УДАЛЕНИЯ:*",
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
    user = query.from_user
    chat_id = str(update.effective_chat.id)
    
    if chat_id not in chat_settings:
        chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
        save_settings()
    
    settings = chat_settings[chat_id]
    
    # Переключение фильтров
    if data == "toggle_links":
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        settings['filter_links'] = not settings.get('filter_links', True)
        save_settings()
    
    elif data == "toggle_stickers":
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        settings['filter_stickers'] = not settings.get('filter_stickers', True)
        save_settings()
    
    elif data == "toggle_caps":
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        settings['filter_caps'] = not settings.get('filter_caps', True)
        save_settings()
    
    elif data == "toggle_flood":
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        settings['filter_flood'] = not settings.get('filter_flood', True)
        save_settings()
    
    elif data == "toggle_swear":
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        settings['filter_swear'] = not settings.get('filter_swear', True)
        save_settings()
    
    elif data == "caps_limit":
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        keyboard = [
            [InlineKeyboardButton("30%", callback_data="set_caps_30")],
            [InlineKeyboardButton("50%", callback_data="set_caps_50")],
            [InlineKeyboardButton("70%", callback_data="set_caps_70")],
            [InlineKeyboardButton("80%", callback_data="set_caps_80")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_settings")]
        ]
        await query.edit_message_text(
            "📊 *ВЫБЕРИ ЛИМИТ КАПСА*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    elif data.startswith("set_caps_"):
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        limit = int(data.split("_")[2])
        settings['caps_limit'] = limit
        save_settings()
        await query.edit_message_text(f"✅ Лимит капса изменен на {limit}%")
    
    elif data == "flood_limit":
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        keyboard = [
            [InlineKeyboardButton("3 стикера", callback_data="set_flood_3")],
            [InlineKeyboardButton("5 стикеров", callback_data="set_flood_5")],
            [InlineKeyboardButton("7 стикеров", callback_data="set_flood_7")],
            [InlineKeyboardButton("10 стикеров", callback_data="set_flood_10")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_settings")]
        ]
        await query.edit_message_text(
            "🎭 *ВЫБЕРИ ЛИМИТ ФЛУДА*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    elif data.startswith("set_flood_"):
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        limit = int(data.split("_")[2])
        settings['flood_limit'] = limit
        save_settings()
        await query.edit_message_text(f"✅ Лимит флуда изменен на {limit}")
    
    elif data == "back_to_settings":
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_links', True) else '❌'} 🔗 Ссылки", callback_data="toggle_links")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_stickers', True) else '❌'} 🔞 18+ стикеры", callback_data="toggle_stickers")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_caps', True) else '❌'} 📢 КАПС", callback_data="toggle_caps")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_flood', True) else '❌'} 🎭 Флуд", callback_data="toggle_flood")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_swear', True) else '❌'} 🤬 Маты", callback_data="toggle_swear")],
            [InlineKeyboardButton("📊 ЛИМИТ КАПСА", callback_data="caps_limit")],
            [InlineKeyboardButton("🎭 ЛИМИТ ФЛУДА", callback_data="flood_limit")]
        ]
        await query.edit_message_text(
            "⚙️ *НАСТРОЙКИ ФИЛЬТРОВ*\n\nНажми чтобы включить/выключить:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    # Админы
    elif data == "add_admin":
        context.user_data['action'] = ('add_admin', chat_id)
        await query.edit_message_text(
            "📝 *ДОБАВЛЕНИЕ АДМИНА*\n\n"
            "Отправь ID пользователя:",
            parse_mode="Markdown"
        )
        return
    
    elif data == "remove_admin":
        admins = settings.get('custom_admins', [])
        if not admins:
            await query.edit_message_text("❌ Нет админов для удаления")
            return
        
        keyboard = []
        for a in admins:
            keyboard.append([InlineKeyboardButton(f"❌ {a}", callback_data=f"del_admin_{a}")])
        keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            "👥 *ВЫБЕРИ АДМИНА:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    elif data.startswith("del_admin_"):
        admin_id = int(data.replace("del_admin_", ""))
        if admin_id in settings.get('custom_admins', []):
            settings['custom_admins'].remove(admin_id)
            save_settings()
            await query.edit_message_text(f"✅ Админ {admin_id} удален!")
    
    elif data == "back_to_admin":
        admins = settings.get('custom_admins', [])
        text = f"👑 *АДМИНИСТРАТОРЫ*\n\n"
        text += f"👤 Главный админ: `{settings.get('chat_creator', 'неизвестен')}`\n"
        if admins:
            text += f"\n👥 Дополнительные:\n"
            for a in admins:
                text += f"• `{a}`\n"
        else:
            text += f"\n❌ Нет дополнительных админов"
        
        keyboard = [
            [InlineKeyboardButton("➕ ДОБАВИТЬ АДМИНА", callback_data="add_admin")],
            [InlineKeyboardButton("➖ УДАЛИТЬ АДМИНА", callback_data="remove_admin")]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    # Удаление чата
    elif data.startswith("del_"):
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Только главный админ может удалять чаты!")
            return
        
        del_chat_id = data.replace("del_", "")
        if del_chat_id in chat_settings:
            title = chat_settings[del_chat_id].get('chat_title', 'Неизвестный чат')
            del chat_settings[del_chat_id]
            save_settings()
            await query.edit_message_text(f"✅ Чат {title} удален!")
        return
    
    # Обновляем меню настроек если нужно
    if data in ["toggle_links", "toggle_stickers", "toggle_caps", "toggle_flood", "toggle_swear"]:
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_links', True) else '❌'} 🔗 Ссылки", callback_data="toggle_links")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_stickers', True) else '❌'} 🔞 18+ стикеры", callback_data="toggle_stickers")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_caps', True) else '❌'} 📢 КАПС", callback_data="toggle_caps")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_flood', True) else '❌'} 🎭 Флуд", callback_data="toggle_flood")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_swear', True) else '❌'} 🤬 Маты", callback_data="toggle_swear")],
            [InlineKeyboardButton("📊 ЛИМИТ КАПСА", callback_data="caps_limit")],
            [InlineKeyboardButton("🎭 ЛИМИТ ФЛУДА", callback_data="flood_limit")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# ОБРАБОТКА ТЕКСТА (ДЛЯ ДОБАВЛЕНИЯ АДМИНОВ)
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    if 'action' not in context.user_data:
        return
    
    action, chat_id = context.user_data['action']
    user_id = update.effective_user.id
    
    if action == 'add_admin' and is_admin(chat_id, user_id):
        try:
            new_admin = int(update.message.text.strip())
            
            if chat_id not in chat_settings:
                chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
            
            if 'custom_admins' not in chat_settings[chat_id]:
                chat_settings[chat_id]['custom_admins'] = []
            
            if new_admin in chat_settings[chat_id]['custom_admins']:
                await update.message.reply_text("❌ Уже админ!")
            elif new_admin == chat_settings[chat_id].get('chat_creator'):
                await update.message.reply_text("❌ Это создатель чата!")
            elif new_admin == ADMIN_ID:
                await update.message.reply_text("❌ Это главный админ!")
            else:
                chat_settings[chat_id]['custom_admins'].append(new_admin)
                save_settings()
                await update.message.reply_text(f"✅ Админ {new_admin} добавлен!")
        except:
            await update.message.reply_text("❌ Отправь ID числом!")
        
        del context.user_data['action']

# ============================================
# ПРОВЕРКА СООБЩЕНИЙ В ГРУППАХ
# ============================================
async def check_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return
    
    msg = update.message
    if not msg:
        return
    
    user = msg.from_user
    chat = msg.chat
    chat_id = str(chat.id)
    
    if user.is_bot:
        return
    
    # Сохраняем информацию о чате
    if chat_id not in chat_settings:
        chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
        chat_settings[chat_id]['chat_title'] = chat.title
        chat_settings[chat_id]['added_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_settings()
    
    # Проверка админов
    if is_admin(chat_id, user.id):
        return
    
    # Проверка админов Telegram
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    settings = chat_settings.get(chat_id, DEFAULT_SETTINGS.copy())
    
    # Проверка стикеров
    if msg.sticker:
        if settings.get('filter_flood', True):
            if is_flood(user.id, chat.id, settings.get('flood_limit', 5)):
                try:
                    await msg.delete()
                    await msg.reply_text(f"@{user.username} ❗ *НЕ ФЛУДИ СТИКЕРАМИ!*", parse_mode="Markdown")
                except:
                    pass
                return
        
        if settings.get('filter_stickers', True) and is_18_sticker(msg.sticker):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❗ *18+ СТИКЕРЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            except:
                pass
            return
    
    # Проверка текста
    text = msg.text or msg.caption
    if text:
        if settings.get('filter_links', True) and has_tg_link(text):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❗ *ССЫЛКИ НА TELEGRAM ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            except:
                pass
            return
        
        if settings.get('filter_swear', True) and has_swear(text):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❗ *МАТЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            except:
                pass
            return
        
        if settings.get('filter_caps', True) and is_caps(text, settings.get('caps_limit', 50)):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❗ *НЕ КРИЧИ! КАПС ЗАПРЕЩЕН*", parse_mode="Markdown")
            except:
                pass
            return

# ============================================
# НОВЫЙ ЧАТ
# ============================================
async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    
    if msg.chat.type == "private":
        return
    
    for member in msg.new_chat_members:
        if member.id == context.bot.id:
            chat_id = str(msg.chat.id)
            adder_id = msg.from_user.id
            
            if chat_id not in chat_settings:
                chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
                chat_settings[chat_id]['chat_creator'] = adder_id
                chat_settings[chat_id]['chat_title'] = msg.chat.title
                chat_settings[chat_id]['added_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                save_settings()
            
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"✅ Бот добавлен в группу!\n\n"
                    f"📌 Название: {msg.chat.title}\n"
                    f"🆔 ID: {chat_id}\n"
                    f"👤 Добавил: {adder_id}"
                )
            except:
                pass

# ============================================
# ЗАПУСК
# ============================================
def main():
    print("=" * 60)
    print("╔══════════════════════════╗")
    print("║   🤖 ANTISPAM БОТ       ║")
    print("║   ⚡ С ТВОИМ СТИЛЕМ     ║")
    print("╚══════════════════════════╝")
    print("=" * 60)
    print(f"👑 Твой ID: {ADMIN_ID}")
    print(f"📊 Чатов в базе: {len(chat_settings)}")
    print("=" * 60)
    print("📋 Доступные команды:")
    print("   📚 /help    - помощь")
    print("   📊 /status  - статус")
    print("   ⚙️ /settings - настройки")
    print("   👑 /admin   - админы")
    print("   🗑️ /delchat  - удалить чат")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("delchat", delchat_command))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Текст (для добавления админов)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        text_handler
    ))
    
    # Проверка сообщений в группах
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Sticker.ALL,
        check_group
    ))
    
    # Новые чаты
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        new_chat_member
    ))
    
    print("✅ Бот запущен! Нажми Ctrl+C для остановки")
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