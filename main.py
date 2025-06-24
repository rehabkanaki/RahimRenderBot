import os
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# جلسات المستخدم (لحفظ المحادثة)
user_sessions = {}

# prompt محسن
SYSTEM_PROMPT = (
    "أنت مساعد ذكي تتحدث كإنسان حقيقي، ودود، بسيط، وتستخدم تعبيرات بشرية عفوية، "
    "وتظهر التعاطف واللطف، وتتفادى الردود الجافة أو الروبوتية."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_sessions[user_id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    await update.message.reply_text("البوت شغال ✅")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_message = update.message.text

    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    user_sessions[user_id].append({"role": "user", "content": user_message})

    # لو الجلسة طويلة نقص الأقدم
    if len(user_sessions[user_id]) > 10:
        # احتفظ بـ system + آخر 9 رسائل
        user_sessions[user_id] = [user_sessions[user_id][0]] + user_sessions[user_id][-9:]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=user_sessions[user_id]
        )
        reply = response.choices[0].message.content.strip()

        # فلتر لو الرد ضعيف
        if not reply or len(reply) < 3:
            reply = "ممكن توضّح لي أكتر عشان أقدر أساعدك؟ 😊"

        user_sessions[user_id].append({"role": "assistant", "content": reply})

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("حصل خطأ في الذكاء الصناعي 😔")
        print(f"OpenAI error: {e}", flush=True)

async def webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        print(f"Webhook error: {e}", flush=True)
    return web.Response(text="OK")

application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app = web.Application()
app.router.add_post(f'/{BOT_TOKEN}', webhook)

async def run():
    await application.initialize()
    await application.start()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=int(os.getenv("PORT")))
    await site.start()
    print("البوت شغال على السيرفر...", flush=True)
    await asyncio.Event().wait()

import asyncio
asyncio.run(run())
