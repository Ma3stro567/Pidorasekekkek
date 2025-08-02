import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import random

TOKEN = "8485294244:AAEE1ZuJhk6QfgjFVP6XO8Iibh52WrK-7n8"  # ← ВСТАВЬ СВОЙ ТОКЕН
ADMIN_IDS = {5083696616}  # <-- сюда вставь свои Telegram ID админов (числа без кавычек)

games = {}
known_users = set()        # пользователи, написавшие /start в ЛС
active_chats = set()       # чаты, где бот запускался

# ===== Команды =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    known_users.add(user_id)
    await update.message.reply_text("✅ Теперь ты можешь участвовать в играх! Вернись в группу и жми /startgame.")

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    active_chats.add(chat_id)

    game = games.get(chat_id, {"players": set(), "spy": None, "votes": {}, "task": None})
    players = list(game["players"])

    if len(players) < 3:
        await update.message.reply_text("❌ Нужно минимум 3 игрока.")
        return

    not_ready = [uid for uid in players if uid not in known_users]
    if not_ready:
        text = "❗ Эти игроки не написали боту в ЛС (напишите /start):\n"
        for uid in not_ready:
            text += f"• [игрок](tg://user?id={uid})\n"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    spy = random.choice(players)

    for uid in players:
        try:
            if uid == spy:
                await context.bot.send_message(uid, "🕵️ Ты шпион! Попробуй остаться незаметным.")
            else:
                await context.bot.send_message(uid, "Вы — обычный игрок.")
        except:
            await update.message.reply_text("❗ Не могу отправить сообщение игроку. Убедитесь, что все начали чат с ботом.")
            return

    game["spy"] = spy
    game["votes"] = {}
    if game.get("task"):
        game["task"].cancel()
    game["task"] = context.application.create_task(game_timer(chat_id, context))
    games[chat_id] = game

    await update.message.reply_text(
        "🎮 Игра началась! Один из игроков — шпион.\n"
        "Голосуйте с помощью команды /vote @username.\n"
        "Игра закончится через 15 минут."
    )

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    active_chats.add(chat_id)

    game = games.get(chat_id)
    if not game or not game.get("spy"):
        await update.message.reply_text("❌ Игра не запущена.")
        return

    voter_id = update.effective_user.id
    if voter_id in game["votes"]:
        await update.message.reply_text("⛔ Вы уже голосовали.")
        return

    if len(context.args) != 1 or not context.args[0].startswith("@"):
        await update.message.reply_text("⚠️ Используйте: /vote @username")
        return

    voted_username = context.args[0][1:]
    user_found = None
    for user_id in game["players"]:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.user.username and member.user.username.lower() == voted_username.lower():
                user_found = user_id
                break
        except:
            continue

    if not user_found:
        await update.message.reply_text("❌ Игрок с таким именем не найден.")
        return

    game["votes"][voter_id] = user_found
    await update.message.reply_text(f"✅ Голос за @{voted_username} принят.")

async def show_vote_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await show_vote_stats(chat_id, context)

async def show_vote_stats(chat_id, context: ContextTypes.DEFAULT_TYPE):
    game = games.get(chat_id)
    if not game:
        return

    vote_counts = {}
    for voted_id in game["votes"].values():
        vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

    if not vote_counts:
        await context.bot.send_message(chat_id, "Пока никто не голосовал.")
        return

    text = "📊 Текущие голоса:\n"
    for uid, count in sorted(vote_counts.items(), key=lambda x: -x[1]):
        try:
            member = await context.bot.get_chat_member(chat_id, uid)
            name = f"@{member.user.username}" if member.user.username else member.user.full_name
            text += f"• {name}: {count} голос(ов)\n"
        except:
            continue

    await context.bot.send_message(chat_id, text)

async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await endgame_auto(chat_id, context)

async def endgame_auto(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games.get(chat_id)
    if not game or not game.get("spy"):
        await context.bot.send_message(chat_id, "⚠️ Игра не запущена.")
        return

    spy = game["spy"]
    votes = game["votes"]

    vote_counts = {}
    for v in votes.values():
        vote_counts[v] = vote_counts.get(v, 0) + 1

    max_votes = max(vote_counts.values()) if vote_counts else 0
    top_voted = [uid for uid, count in vote_counts.items() if count == max_votes]
    spy_caught = spy in top_voted

    spy_user = await context.bot.get_chat_member(chat_id, spy)
    result = "🎉 Шпион пойман!" if spy_caught else "🕵️ Шпион не пойман."

    await context.bot.send_message(chat_id, f"Игра окончена!\nШпионом был @{spy_user.user.username}.\n{result}")
    await show_vote_stats(chat_id, context)

    if game.get("task"):
        game["task"].cancel()
    games.pop(chat_id, None)

async def game_timer(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(10 * 60)
    await context.bot.send_message(chat_id, "⌛ Осталось 5 минут!")
    await asyncio.sleep(5 * 60)
    await endgame_auto(chat_id, context)

async def track_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    active_chats.add(chat_id)

    game = games.get(chat_id, {"players": set(), "spy": None, "votes": {}, "task": None})
    game["players"].add(user_id)
    games[chat_id] = game

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_chats.add(update.effective_chat.id)
    await update.message.reply_text(
        "/start — активировать себя в ЛС\n"
        "/startgame — начать игру\n"
        "/vote @username — проголосовать\n"
        "/votestats — показать текущие голоса\n"
        "/endgame — досрочно завершить\n"
        "/help — показать команды"
    )

# ===== Админ-панель =====

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or context.args[0] != "popopopo":
        await update.message.reply_text("❌ Неверный ключ.")
        return

    await update.message.reply_text(
        "🔐 Админ-панель активна.\n"
        "Используй:\n"
        "/broadcast <текст> — отправить сообщение во все чаты"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if not context.args:
        await update.message.reply_text("⚠️ Используй: /broadcast <текст>")
        return

    text = " ".join(context.args)
    success, failed = 0, 0

    for chat_id in active_chats:
        try:
            await context.bot.send_message(chat_id, text)
            success += 1
        except:
            failed += 1

    await update.message.reply_text(f"✅ Отправлено: {success}, ошибок: {failed}")

# ===== Запуск =====

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("votestats", show_vote_stats_command))
    app.add_handler(CommandHandler("endgame", endgame))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("adminpanel", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), track_players))

    print("🤖 Bot started.")
    app.run_polling()
    
