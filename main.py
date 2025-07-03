import os
import json
import base64
import requests
import asyncio
from datetime import datetime
from aiohttp import web
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ========== المتغيرات البيئية ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8080"))

client = OpenAI(api_key=OPENAI_API_KEY)
user_sessions = {}
user_dialects = {}

# ========== Google Sheets ==========
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
gc = gspread.authorize(creds)
sheet = gc.open("RahimBot_History").sheet1

def save_message_to_sheet(data):
    try:
        sheet.append_row([
            data["timestamp"],
            str(data["user_id"]),
            data["user_name"],
            str(data["group_id"]),
            data["dialect"],
            data["text"]
        ])
        print("✅ Saved to Google Sheet", flush=True)
    except Exception as e:
        print(f"❌ Error saving to Google Sheet: {e}", flush=True)

# ========== البرومبت الأساسي ==========
SYSTEM_PROMPT_TEMPLATE = (
    "أنت مساعد ذكي ودود موجود داخل قروب دردشة. "
    "تتحدث مع المستخدم باللهجة أو اللغة التالية: {dialect}. "
    "تتصرف كأنك عضو متعاون وودود في المجموعة، وتتعامل مع الرسائل وكأنك وسط الناس، مش مجرد دردشة فردية. "
    "لو لاحظت أن الرسالة تحتوي على تاق اسمك (مثل @اسمك) أو ذكرك، اعتبر أن المستخدم يقصدك بالحديث. "
    "لو طلب منك المستخدم تنفيذ أمر يخص عضو آخر في القروب (مثل توصيل رسالة أو نداء عضو)، وضح أنك مجرد بوت لا تملك القدرة الفعلية على التواصل المباشر، لكن ساعد المستخدم بصياغة رسالة مناسبة أو قدم له اقتراح لطيف. "
    "استخدم لغة بسيطة وطبيعية، ووضح فكرتك بشكل منظم ومفهوم، وادعم كلامك بأسباب لو أمكن. "
    "لو المستخدم سأل عن هويتك، عرف نفسك بلطف إنك جزء من شركة OpenAI. "
    "لو حدث خطأ، اعتذر بطريقة مهذبة وشجع المستخدم على المحاولة مرة أخرى."
)

# ========== كشف اللهجة ==========
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
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "أنت مساعد لتحديد لهجة أو لغة النص."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error detecting dialect/language: {e}", flush=True)
        return "العربية الفصحى"

# ========== Start ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_sessions[user_id] = []
    user_dialects[user_id] = "العربية الفصحى"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialect="العربية الفصحى")
    user_sessions[user_id].append({"role": "system", "content": system_prompt})
    await update.message.reply_text("البوت شغال ✅")

# ========== تحليل الصور لأي محتوى ==========
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.chat.send_action(action=ChatAction.TYPING)

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_path = f"temp_{photo.file_unique_id}.jpg"
        await file.download_to_drive(file_path)

        with open(file_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي محترف في تحليل الصور. مهمتك تقديم وصف ذكي ومهني لأي صورة تُعرض عليك، سواء كانت لأشخاص، منتجات، تصاميم، مشاهد طبيعية، أو أي محتوى بصري. كن مهذبًا، دقيقًا، وقدم ملاحظات واقتراحات إن أمكن."},
                {"role": "user", "content": "حلل لي هذه الصورة، وقدم تعليقًا احترافيًا عنها."}
            ],
            images=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                }
            ]
        )

        reply = response.choices[0].message.content.strip()
        await update.message.reply_text(reply)
        os.remove(file_path)

    except Exception as e:
        print(f"Image handling error: {e}", flush=True)
        await update.message.reply_text("ما قدرت أحلل الصورة 😔 جربي ترفعيها تاني.")

# ========== رسائل القروب ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    user_message = update.message.text.lower()

    is_mentioned = (
        f"@{bot_username}".lower() in user_message
        or "رحيم" in user_message
        or "rahim" in user_message
    )
    is_reply_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    if not is_mentioned and not is_reply_to_bot:
        return

    if update.message.reply_to_message and update.message.reply_to_message.text:
        target_text = update.message.reply_to_message.text
        combined_input = f"{update.message.text}\n\nالرسالة المردود عليها:\n{target_text}"
    else:
        combined_input = update.message.text

    user_id = update.message.from_user.id
    group_id = update.message.chat.id
    user_name = update.message.from_user.full_name

    if user_id not in user_sessions:
        user_sessions[user_id] = []
        user_dialects[user_id] = "العربية الفصحى"

    if user_id not in user_dialects or user_dialects[user_id] == "العربية الفصحى":
        detected = await detect_language_or_dialect(combined_input)
        user_dialects[user_id] = detected
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialect=detected)
        user_sessions[user_id] = [{"role": "system", "content": system_prompt}]
    else:
        detected = user_dialects[user_id]

    user_sessions[user_id].append({"role": "user", "content": combined_input})

    save_message_to_sheet({
        "user_id": user_id,
        "user_name": user_name,
        "group_id": group_id,
        "text": combined_input,
        "dialect": detected,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=user_sessions[user_id]
        )
        reply = response.choices[0].message.content.strip()
        user_sessions[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        print(f"OpenAI error: {e}", flush=True)
        await update.message.reply_text("حصل خطأ في الذكاء الصناعي 😔")

# ========== رسائل الخاص ==========
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! 👋 البوت دا مخصص للقروبات فقط. أضفني لقروبك عشان أقدر أساعدك 🚀")

# ========== Webhook ==========
async def webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        print(f"Webhook error: {e}", flush=True)
    return web.Response(text="OK")

# ========== التطبيق ==========
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_message))
application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.GROUPS, handle_photo))

app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", webhook)

async def run():
    await application.initialize()
    await application.start()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=PORT)
    await site.start()
    print("💬 البوت شغال على السيرفر...", flush=True)
    await asyncio.Event().wait()

asyncio.run(run())
