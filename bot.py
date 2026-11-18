import asyncio
import logging
import os  # <--- Добавь эту строчку
import sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

TOKEN = os.getenv("9102657407:AAG9Ibro7GVrJuJlnLZvCzCDkEsvJSoRshg")

logging.basicConfig(level=logging.INFO)
router = Router()

# --- БАЗА ДАННЫХ ---
DB_NAME = "bot_database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER PRIMARY KEY,
            prefix_left TEXT DEFAULT '🥀',
            prefix_right TEXT DEFAULT '༄ 🩸',
            divider TEXT DEFAULT '—1—2—3—4—5—6—',
            captain_text TEXT DEFAULT 'Чурка @waoxspolss',
            player_marker TEXT DEFAULT '→',
            media_file_id TEXT DEFAULT '',
            poll_options TEXT DEFAULT 'Участвую|Не участвую|На замене'
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            chat_id INTEGER,
            user_id INTEGER,
            full_name TEXT,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_lists (
            chat_id INTEGER PRIMARY KEY,
            message_id INTEGER
        )
    """)
  conn.commit()
  conn.close()


init_db()


def get_settings(chat_id: int):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT prefix_left, prefix_right, divider, captain_text,"
      " player_marker, media_file_id, poll_options FROM settings WHERE chat_id"
      " = ?",
      (chat_id,),
  )
  row = cursor.fetchone()
  if not row:
    default = (
        "🥀",
        "༄ 🩸",
        "—1—2—3—4—5—6—",
        "Чурка @waoxspolss",
        "→",
        "",
        "Участвую|Не участвую|На замене",
    )
    cursor.execute(
        "INSERT OR IGNORE INTO settings (chat_id, prefix_left, prefix_right,"
        " divider, captain_text, player_marker, media_file_id, poll_options)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id,) + default,
    )
    conn.commit()
    conn.close()
    return default
  conn.close()
  return row


def update_single_setting(chat_id: int, column: str, value: str):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  allowed_columns = {
      "prefix_left",
      "prefix_right",
      "divider",
      "captain_text",
      "player_marker",
      "media_file_id",
      "poll_options",
  }
  if column in allowed_columns:
    cursor.execute(
        f"UPDATE settings SET {column} = ? WHERE chat_id = ?", (value, chat_id)
    )
    conn.commit()
  conn.close()


def clean_user_name(name: str, prefix_left: str, prefix_right: str) -> str:
  clean = name.strip()
  pl = prefix_left.strip() if prefix_left else ""
  pr = prefix_right.strip() if prefix_right else ""

  if pl and clean.startswith(pl):
    clean = clean[len(pl) :].strip()
  if pr and clean.endswith(pr):
    clean = clean[: -len(pr)].strip()
  return clean


def has_required_prefix(name: str, prefix_left: str, prefix_right: str) -> bool:
  clean = name.strip()
  pl = prefix_left.strip() if prefix_left else ""
  pr = prefix_right.strip() if prefix_right else ""

  if not pl and not pr:
    return True

  has_pl = pl and pl in clean
  has_pr = pr and pr in clean

  return has_pl or has_pr


# --- 1. ТЕКСТ РЕГИСТРАЦИИ (ссылка охватывает приставки и ник целиком) ---
def build_registration_text(chat_id: int):
  prefix_left, prefix_right, _, _, _, _, _ = get_settings(chat_id)

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT user_id, full_name FROM participants WHERE chat_id = ?", (chat_id,)
  )
  users = cursor.fetchall()
  conn.close()

  players_lines = []
  for idx, (uid, name) in enumerate(users, start=1):
    clean_name = clean_user_name(name, prefix_left, prefix_right)
    safe_name = (
        clean_name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    pl = f"{prefix_left} " if prefix_left else ""
    pr = f" {prefix_right}" if prefix_right else ""

    # Ссылка оборачивает весь блок целиком: и приставки, и имя
    full_line_content = f"{pl}{safe_name}{pr}".strip()
    linked_block = f'<a href="tg://user?id={uid}">{full_line_content}</a>'

    players_lines.append(f"{idx}. {linked_block}")

  parts = [
      "❗️ <b>Ведётся регистрация на турнир</b>\n",
      "Зарегестрировалось:",
  ]

  if players_lines:
    parts.extend(players_lines)

  parts.append("")
  parts.append(f"Всего {len(users)} чел.")

  return "\n".join(parts)


# --- 2. ТЕКСТ ФИНАЛЬНОГО СПИСКА (ссылка охватывает приставки и ник целиком) ---
def build_final_list_text(chat_id: int):
  prefix_left, prefix_right, divider, captain_text, player_marker, _, _ = (
      get_settings(chat_id)
  )

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT user_id, full_name FROM participants WHERE chat_id = ?", (chat_id,)
  )
  users = cursor.fetchall()
  conn.close()

  players_lines = []
  for idx, (uid, name) in enumerate(users, start=1):
    clean_name = clean_user_name(name, prefix_left, prefix_right)
    safe_name = (
        clean_name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    marker_part = f"{player_marker} " if player_marker else ""
    pl = f"{prefix_left} " if prefix_left else ""
    pr = f" {prefix_right}" if prefix_right else ""

    # Ссылка оборачивает приставки и ник целиком (маркер идет перед ссылкой)
    full_line_content = f"{pl}{safe_name}{pr}".strip()
    linked_block = f'<a href="tg://user?id={uid}">{full_line_content}</a>'

    players_lines.append(f"{marker_part}{linked_block}")

  parts = []
  if captain_text:
    parts.append(captain_text)
  if divider:
    parts.append(divider)

  if players_lines:
    parts.extend(players_lines)
  else:
    parts.append("Список пока пуст.")

  return "\n".join(parts)


def get_reg_keyboard():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="👍🏻", callback_data="reg_join"),
              InlineKeyboardButton(text="👎🏻", callback_data="reg_leave"),
          ],
          [
              InlineKeyboardButton(
                  text="📋 Список", callback_data="show_list_media"
              )
          ],
      ]
  )


async def update_active_list_message(bot_instance: Bot, chat_id: int):
  try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT message_id FROM active_lists WHERE chat_id = ?", (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
      return
    message_id = row[0]
    new_text = build_registration_text(chat_id)
    keyboard = get_reg_keyboard()

    await bot_instance.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=new_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
  except Exception as e:
    logging.info(f"Не удалось обновить сообщение регистрации: {e}")


async def is_user_admin(message_or_callback) -> bool:
  chat = (
      message_or_callback.chat
      if hasattr(message_or_callback, "chat")
      else message_or_callback.message.chat
  )
  user = message_or_callback.from_user
  if chat.type == "private":
    return True
  try:
    member = await message_or_callback.bot.get_chat_member(chat.id, user.id)
    return member.status in ("creator", "administrator")
  except Exception:
    return False


# --- КОМАНДЫ БОТА ---


@router.message(CommandStart(deep_link=True))
async def cmd_start_deep(message: Message):
  text_parts = message.text.split()
  if len(text_parts) > 1 and text_parts[1].startswith("settings_"):
    try:
      group_chat_id = int(text_parts[1].replace("settings_", ""))
      member = await message.bot.get_chat_member(
          group_chat_id, message.from_user.id
      )
      if member.status in ("creator", "administrator"):
        await send_settings_panel(
            message.bot, message.from_user.id, group_chat_id
        )
      else:
        await message.answer(
            "❌ У вас нет прав администратора в этой группе для изменения"
            " настроек."
        )
    except Exception as e:
      logging.error(f"Ошибка обработки deep link настроек: {e}")


@router.message(CommandStart())
async def cmd_start(message: Message):
  try:
    await message.delete()
  except Exception:
    pass

  text = (
      "👋 Привет! Я турнирный бот.\n\n"
      "📋 Доступные команды:\n"
      "• `/list` — открыть регистрацию на турнир и закрепить сообщение в чате\n"
      "• `/clear` — очистить текущий список участников\n"
      "• `/settings` — открыть панель настроек бота\n"
      "• `/poll` Текст опроса — создать опрос с готовыми вариантами\n"
      "• `!ник` — получить свой ник с приставкой в ответ на сообщение"
  )
  await message.answer(text, parse_mode="Markdown")


@router.message(Command("list"))
async def cmd_list(message: Message):
  try:
    await message.delete()
  except Exception:
    pass

  if not await is_user_admin(message):
    msg = await message.answer(
        "❌ Эта команда доступна только администраторам чата!"
    )
    await asyncio.sleep(4)
    try:
      await msg.delete()
    except Exception:
      pass
    return

  try:
    chat_id = message.chat.id
    text = build_registration_text(chat_id)
    keyboard = get_reg_keyboard()

    sent_msg = await message.answer(
        text=text, reply_markup=keyboard, parse_mode="HTML"
    )

    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT OR REPLACE INTO active_lists (chat_id, message_id) VALUES (?,"
        " ?)",
        (chat_id, sent_msg.message_id),
    )
    conn.commit()
    conn.close()

    try:
      await message.bot.pin_chat_message(
          chat_id=chat_id, message_id=sent_msg.message_id
      )
    except Exception as e:
      logging.info(f"Не удалось закрепить сообщение: {e}")
  except Exception as e:
    logging.error(f"Ошибка в /list: {e}")
    await message.answer(f"⚠️ Ошибка выполнения /list: {e}")


@router.message(Command("clear"))
async def cmd_clear(message: Message):
  try:
    await message.delete()
  except Exception:
    pass

  if not await is_user_admin(message):
    msg = await message.answer(
        "❌ Эта команда доступна только администраторам чата!"
    )
    await asyncio.sleep(4)
    try:
      await msg.delete()
    except Exception:
      pass
    return

  try:
    chat_id = message.chat.id
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM participants WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

    await update_active_list_message(message.bot, chat_id)
    msg = await message.answer("🧹 Список участников успешно очищен!")
    await asyncio.sleep(3)
    try:
      await msg.delete()
    except Exception:
      pass
  except Exception as e:
    logging.error(f"Ошибка в /clear: {e}")


@router.message(Command("settings"))
async def cmd_settings(message: Message):
  try:
    await message.delete()
  except Exception:
    pass

  if not await is_user_admin(message):
    msg = await message.answer(
        "❌ Эта команда доступна только администраторам чата!"
    )
    await asyncio.sleep(4)
    try:
      await msg.delete()
    except Exception:
      pass
    return

  user_id = message.from_user.id
  bot_info = await message.bot.get_me()
  bot_username = bot_info.username

  if message.chat.type != "private":
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="⚙️ Открыть настройки в ЛС",
                url=f"https://t.me/{bot_username}?start=settings_{message.chat.id}",
            )
        ]]
    )
    msg = await message.answer(
        "⚙️ Нажмите на кнопку ниже, чтобы открыть настройки в личных сообщениях:",
        reply_markup=keyboard,
    )
    await asyncio.sleep(8)
    try:
      await msg.delete()
    except Exception:
      pass
    return

  await send_settings_panel(message.bot, user_id, message.chat.id)


async def send_settings_panel(
    bot: Bot, user_id: int, target_group_chat_id: int
):
  prefix_left, prefix_right, divider, captain_text, player_marker, media_file_id, poll_options = get_settings(
      target_group_chat_id
  )

  text = (
      f"⚙️ **Панель настроек бота** (Чат ID: `{target_group_chat_id}`):\n\n"
      f"🔸 Левая приставка: `{prefix_left}`\n"
      f"🔸 Правая приставка: `{prefix_right}`\n"
      f"🔸 Разделитель (в списке): `{divider}`\n"
      f"🔸 Строка капитана (в списке): `{captain_text}`\n"
      f"🔸 Маркер игрока (в списке): `{player_marker}`\n"
      f"🔸 Media ID (в списке): `{media_file_id if media_file_id else 'не установлено'}`\n"
      f"🔸 Варианты опроса: `{poll_options}`\n\n"
      "💡 *Как узнать Media ID картинки:* отправьте любую картинку или гифку"
      " мне сюда в личку!\n\n"
      "Нажмите на кнопку ниже, чтобы изменить нужный параметр:"
  )

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="✏️ Приставки",
                  callback_data=f"set_pref_{target_group_chat_id}",
              ),
              InlineKeyboardButton(
                  text="✏️ Строку кэпа",
                  callback_data=f"set_cap_{target_group_chat_id}",
              ),
          ],
          [
              InlineKeyboardButton(
                  text="✏️ Разделитель",
                  callback_data=f"set_div_{target_group_chat_id}",
              ),
              InlineKeyboardButton(
                  text="✏️ Маркер",
                  callback_data=f"set_mark_{target_group_chat_id}",
              ),
          ],
          [
              InlineKeyboardButton(
                  text="🖼 Media ID",
                  callback_data=f"set_med_{target_group_chat_id}",
              )
          ],
          [
              InlineKeyboardButton(
                  text="📊 Варианты опроса",
                  callback_data=f"set_poll_{target_group_chat_id}",
              )
          ],
      ]
  )
  await bot.send_message(
      user_id, text, reply_markup=keyboard, parse_mode="Markdown"
  )


@router.callback_query(F.data.startswith("set_"))
async def settings_callback_handler(callback: CallbackQuery):
  data_parts = callback.data.split("_")
  action_type = data_parts[1]
  target_chat_id = int(data_parts[2])

  action_map = {
      "pref": "set_prefixes",
      "cap": "set_captain",
      "div": "set_divider",
      "mark": "set_marker",
      "med": "set_media",
      "poll": "set_poll_opts",
  }
  real_action = action_map.get(action_type)

  prompts = {
      "set_prefixes": (
          "Отправьте новые приставки в формате: Левая | Правая (например: 🥀 |"
          " ༄ 🩸)"
      ),
      "set_captain": "Отправьте новую строку капитана (например: Чурка @name):",
      "set_divider": "Отправьте новый текст разделителя/полоски:",
      "set_marker": "Отправьте новый маркер игрока для списка (например: →):",
      "set_media": (
          "Отправьте новый File ID картинки (или отправьте слово удалить, чтобы"
          " убрать медиа):"
      ),
      "set_poll_opts": (
          "Отправьте новые варианты для опроса через черту (например: Да | Нет"
          " | На замене):"
      ),
  }

  global pending_settings
  if "pending_settings" not in globals():
    pending_settings = {}
  pending_settings[callback.from_user.id] = (real_action, target_chat_id)

  await callback.message.answer(prompts[real_action])
  await callback.answer()


@router.message(
    F.text
    & (F.chat.type == "private")
    & ~F.text.startswith("/")
    & ~F.text.startswith("!")
)
async def catch_setting_input(message: Message):
  global pending_settings
  if "pending_settings" not in globals():
    return
  user_id = message.from_user.id
  if user_id not in pending_settings:
    return

  action, chat_id = pending_settings.pop(user_id)
  text = message.text.strip()

  if action == "set_prefixes":
    parts = text.split("|")
    if len(parts) == 2:
      update_single_setting(chat_id, "prefix_left", parts[0].strip())
      update_single_setting(chat_id, "prefix_right", parts[1].strip())
      await message.answer(
          f"✅ Приставки успешно обновлены (Чат ID: {chat_id})!"
      )
      await update_active_list_message(message.bot, chat_id)
    else:
      await message.answer(
          "❌ Ошибка формата. Используйте знак | между левой и правой"
          " приставкой."
      )
  elif action == "set_captain":
    update_single_setting(chat_id, "captain_text", text)
    await message.answer("✅ Строка капитана обновлена!")
    await update_active_list_message(message.bot, chat_id)
  elif action == "set_divider":
    update_single_setting(chat_id, "divider", text)
    await message.answer("✅ Разделитель обновлен!")
    await update_active_list_message(message.bot, chat_id)
  elif action == "set_marker":
    update_single_setting(chat_id, "player_marker", text)
    await message.answer("✅ Маркер игрока обновлен!")
    await update_active_list_message(message.bot, chat_id)
  elif action == "set_media":
    if text.lower() == "удалить":
      update_single_setting(chat_id, "media_file_id", "")
      await message.answer("🗑 Медиафайл успешно удален из настроек!")
    else:
      update_single_setting(chat_id, "media_file_id", text)
      await message.answer("✅ Media ID успешно обновлен!")
    await update_active_list_message(message.bot, chat_id)
  elif action == "set_poll_opts":
    update_single_setting(chat_id, "poll_options", text)
    await message.answer("✅ Варианты для опросов обновлены!")


# --- ОБРАБОТКА КНОПКИ "📋 СПИСОК" (HTML-формат) ---
@router.callback_query(F.data == "show_list_media")
async def show_list_media_callback(callback: CallbackQuery):
  if not await is_user_admin(callback):
    await callback.answer(
        "❌ Просмотр списка доступен только администраторам!", show_alert=True
    )
    return

  chat_id = callback.message.chat.id
  text = build_final_list_text(chat_id)
  _, _, _, _, _, media_file_id, _ = get_settings(chat_id)

  if media_file_id and media_file_id.strip():
    try:
      await callback.message.answer_photo(
          photo=media_file_id.strip(), caption=text, parse_mode="HTML"
      )
    except Exception:
      try:
        await callback.message.answer_animation(
            animation=media_file_id.strip(), caption=text, parse_mode="HTML"
        )
      except Exception:
        await callback.message.answer(text=text, parse_mode="HTML")
  else:
    await callback.message.answer(text=text, parse_mode="HTML")
  await callback.answer("📋 Список отправлен!")


@router.message(Command("poll"))
async def cmd_poll(message: Message):
  try:
    await message.delete()
  except Exception:
    pass

  if not await is_user_admin(message):
    msg = await message.answer(
        "❌ Эта команда доступна только администраторам чата!"
    )
    await asyncio.sleep(4)
    try:
      await msg.delete()
    except Exception:
      pass
    return

  try:
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)
    question = args[1] if len(args) > 1 else "Опрос"

    _, _, _, _, _, _, poll_options = get_settings(chat_id)
    options = [opt.strip() for opt in poll_options.split("|") if opt.strip()]
    if not options or len(options) < 2:
      options = ["Участвую", "Не участвую"]

    await message.answer_poll(
        question=question,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=False,
        is_closed=False,
    )
  except Exception as e:
    logging.error(f"Ошибка в /poll: {e}")
    await message.answer(f"⚠️ Ошибка создания опроса: {e}")


@router.callback_query(F.data.in_({"reg_join", "reg_leave"}))
async def process_reg_callback(callback: CallbackQuery):
  try:
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    full_name = callback.from_user.first_name
    prefix_left, prefix_right, _, _, _, _, _ = get_settings(chat_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if callback.data == "reg_join":
      if not has_required_prefix(full_name, prefix_left, prefix_right):
        conn.close()
        await callback.answer("Отсутсвует ник❌", show_alert=True)
        return

      cursor.execute(
          "INSERT OR REPLACE INTO participants (chat_id, user_id, full_name)"
          " VALUES (?, ?, ?)",
          (chat_id, user_id, full_name),
      )
      conn.commit()
      await callback.answer("Вы зарегистрированы! 👍🏻")
    elif callback.data == "reg_leave":
      cursor.execute(
          "DELETE FROM participants WHERE chat_id = ? AND user_id = ?",
          (chat_id, user_id),
      )
      conn.commit()
      await callback.answer("Вы убраны из регистрации. 👎🏻")

    conn.close()
    await update_active_list_message(callback.bot, chat_id)
  except Exception as e:
    logging.error(f"Ошибка в кнопках регистрации: {e}")


@router.message(F.photo | F.animation | F.document)
async def get_file_id_handler(message: Message):
  if message.chat.type == "private":
    file_id = ""
    if message.photo:
      file_id = message.photo[-1].file_id
    elif message.animation:
      file_id = message.animation.file_id
    elif message.document:
      file_id = message.document.file_id

    await message.answer(
        f"🖼 Вот твой **File ID** (нажми, чтобы скопировать):\n\n`{file_id}`",
        parse_mode="Markdown",
    )


@router.message(F.text.lower().startswith("!ник"))
async def cmd_nick_reply(message: Message):
  try:
    await message.delete()
  except Exception:
    pass

  try:
    chat_id = message.chat.id
    prefix_left, prefix_right, _, _, _, _, _ = get_settings(chat_id)

    clean_name = clean_user_name(
        message.from_user.first_name, prefix_left, prefix_right
    )
    formatted_nick = f"`{prefix_left} {clean_name} {prefix_right}`"

    if message.reply_to_message:
      await message.reply_to_message.reply(
          formatted_nick, parse_mode="Markdown"
      )
    else:
      await message.answer(formatted_nick, parse_mode="Markdown")
  except Exception as e:
    logging.error(f"Ошибка в !ник: {e}")


async def web_server():
  from aiohttp import web

  app = web.Application()
  app.add_routes([web.get("/", lambda r: web.Response(text="I am alive!"))])
  runner = web.AppRunner(app)
  await runner.setup()
  port = int(os.getenv("PORT", 8080))
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()


async def main():
  # Запускаем фоновый веб-сервер для Render, чтобы бот не засыпал
  asyncio.create_task(web_server())

  bot = Bot(token=TOKEN)
  dp = Dispatcher()
  dp.include_router(router)

  logging.info("Бот запущен и готов к работе в облаке!")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())