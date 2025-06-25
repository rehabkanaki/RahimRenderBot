import os
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

user_sessions = {}
user_dialects = {}

async def detect_language_or_dialect(text: str) -> str:
    prompt = (
        "حدد لي لغة أو لهجة النص التالي بدقة عالية، "
        "إذا كانت العربية حدد لهجتها (سوداني، مصري، خليجي، شامي، مغربي، ...)، "
        "وإذا كانت لغة أخرى اذكر اسم اللغة بالإنجليزية فقط.\n\n"
        f"النص: \"{text}\"\n\n"
        "الرد يجب أن يكون فقط كلمة واحدة أو جملة قصيرة تصف اللهجة أو اللغة."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "أنت مساعد لتحديد لهجة أو لغة النص."},
                {"role": "user", "content": prompt}
            ]
        )
        dialect = response.choices[0].message.content.strip()
        return dialect
    except Exception as e:
        print(f"Error detecting dialect/language: {e}", flush=True)
        return "العربية الفصحى"

SYSTEM_PROMPT_TEMPLATE = (
    "أنت مساعد ذكي ودود، تتحدث مع المستخدم باللهجة أو اللغة التالية: {dialect}. "
    "تستخدم لغة بسيطة وطبيعية، وترد كأنك شخص حقيقي متعاطف ومهتم. "
    "لو المستخدم سأل عن هويتك، عرف نفسك بلطف إنك جزء من شركة OpenAI. "
    "لو حدث خطأ، اعتذر بطريقة مهذبة وشجع المستخدم على المحاولة مرة أخرى."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_sessions[user_id] = []
    user_dialects[user_id] = "العربية الفصحى"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialect=user_dialects[user_id])
    user_sessions[user_id].append({"role": "system", "content": system_prompt})
    await update.message.reply_text("البوت شغال ✅")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    user_message = update.message.text.lower()  # حولنا الرسالة لحروف صغيرة

    if (
        f"@{bot_username}".lower() not in user_message
        and "رحيم" not in user_message
        and "rahim" not in user_message
    ):
        return

    user_id = update.message.from_user.id

    if user_id not in user_sessions:
        user_sessions[user_id] = []
        user_dialects[user_id] = "العربية الفصحى"

    if user_id not in user_dialects or user_dialects[user_id] == "العربية الفصحى":
        detected = await detect_language_or_dialect(update.message.text)
        user_dialects[user_id] = detected
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialect=detected)
        user_sessions[user_id] = [{"role": "system", "content": system_prompt}]

    user_sessions[user_id].append({"role": "user", "content": update.message.text})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_sessions[user_id]
        )
        reply = response.choices[0].message.content.strip()

        user_sessions[user_id].append({"role": "assistant", "content": reply})

        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("حصل خطأ في الذكاء الصناعي 😔")
        print(f"OpenAI error: {e}", flush=True)

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! 👋 البوت دا مخصص للقروبات فقط. أضفني لقروبك عشان أقدر أساعدك 🚀")

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
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_message))

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

asyncio.run(run())
