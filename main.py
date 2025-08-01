import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import random

TOKEN = "твой_токен_бота"  # <-- вставь сюда свой токен

games = {}

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id, {"players": set(), "spy": None, "votes": {}, "task": None})

    players = list(game["players"])
    if len(players) < 3:
        await update.message.reply_text("Нужно минимум 3 игрока, которые писали в чат.")
        return

    spy = random.choice(players)
    game["spy"] = spy
    game["votes"] = {}
    games[chat_id] = game

    try:
        await context.bot.send_message(spy, "Ты — шпион! Твоя задача: постарайся не выдать себя в течение часа.")
    except Exception:
        await update.message.reply_text("Не могу отправить личное сообщение шпиону. Убедитесь, что бот начал с ним чат.")
        return

    await update.message.reply_text(
        "Игра началась! Найдите шпиона! Голосуйте командой /vote @username\n"
        "Игра закончится автоматически через 1 час."
    )

    if game.get("task"):
        game["task"].cancel()
    game["task"] = context.application.create_task(game_timer(chat_id, context))
    games[chat_id] = game

async def game_timer(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(55 * 60)
    await context.bot.send_message(chat_id, "До окончания игры осталось 5 минут! Поторопитесь с голосованием!")
    await asyncio.sleep(5 * 60)
    await endgame_auto(chat_id, context)

async def endgame_auto(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games.get(chat_id)
    if not game or not game.get("spy"):
        await context.bot.send_message(chat_id, "Игра не запущена или уже завершена.")
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

    if spy_caught:
        text = f"⏰ Время вышло! Шпион — @{spy_user.user.username} пойман! Поздравляем!"
    else:
        text = f"⏰ Время вышло! Шпион — @{spy_user.user.username} остался не пойман."

    await context.bot.send_message(chat_id, text)
    games.pop(chat_id, None)

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game or not game.get("spy"):
        await update.message.reply_text("Игра не запущена.")
        return
    if len(context.args) != 1 or not context.args[0].startswith("@"):
        await update.message.reply_text("Используйте: /vote @username")
        return
    voted_username = context.args[0][1:]
    user_found = None
    for user_id in game["players"]:
        user = await context.bot.get_chat_member(chat_id, user_id)
        if user.user.username == voted_username:
            user_found = user_id
            break
    if not user_found:
        await update.message.reply_text("Игрок с таким именем не найден в игре.")
        return
    game["votes"][update.effective_user.id] = user_found
    await update.message.reply_text(f"Ваш голос за @{voted_username} учтён.")

async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await endgame_auto(chat_id, context)

async def track_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    game = games.get(chat_id, {"players": set(), "spy": None, "votes": {}, "task": None})
    game["players"].add(user_id)
    games[chat_id] = game

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/startgame — начать игру\n"
        "/vote @username — проголосовать за шпиона\n"
        "/endgame — закончить игру и узнать результат\n"
        "Для участия — просто пиши в чат!"
    )
    await update.message.reply_text(help_text)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("endgame", endgame))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), track_players))

    print("Bot started")
    app.run_polling()
  
