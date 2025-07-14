import os
import json
from datetime import datetime
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import asyncio
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import aiohttp
import base64

# مكتبات قراءة الملفات
import fitz  # PyMuPDF
from docx import Document as DocxReader
import pandas as pd
import tempfile

# ========== المتغيرات ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
MAX_SESSION_LENGTH = 20

client = OpenAI(api_key=OPENAI_API_KEY)
group_sessions = {}
group_dialects = {}
image_context = {}  # تخزين مؤقت للصورة لكل مستخدم

# ========== Google Sheets ==========
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
gc = gspread.authorize(creds)
sheet = gc.open("RahimBot_History").sheet1

# ========== تحميل برومبت ==========
with open("rahim_prompts_library.txt", "r", encoding="utf-8") as f:
    PROMPTS_LIBRARY = f.read()

RAHIM_MAIN_PROMPT = (
    "أنت بوت اسمه \"رحيم\". تم تصميمك لتكون زول طيب، حنون، خفيف الدم، وبتتكلم بلغة بشرية حقيقية. \
    لو حسيت إنو السائل محتاج معلومة دقيقة، ممكن تفتش في الإنترنت وترد عليه برابط موثوق."
)

# ========== أدوات قراءة الملفات ==========
def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    return "\n".join(page.get_text() for page in doc)

def extract_text_from_docx(file_path):
    doc = DocxReader(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_excel(file_path):
    try:
        df = pd.read_excel(file_path)
        preview = df.head(10)
        return preview.to_string(index=False)
    except Exception as e:
        return f"📛 حصل خطأ أثناء قراءة الإكسل: {str(e)}"

# ========== حفظ في Google Sheets ==========
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

# ========== كشف اللهجة ==========
async def detect_language_or_dialect(text: str) -> str:
    prompt = (
        "حدد لي لغة أو لهجة النص التالي بدقة عالية..."
        f"النص: \"{text}\""
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

# ========== البحث في الويب ==========
async def perform_web_search(query: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={query}"
            async with session.get(url) as response:
                data = await response.json()
                if "items" in data and len(data["items"]) > 0:
                    top = data["items"][0]
                    title = top["title"]
                    snippet = top["snippet"]
                    link = top["link"]
                    return f"أنا مش مختص، لكن لقيت ليك من Google:\n**{title}**\n{snippet}\n📎 {link}"
                else:
                    return "ما لقيت نتيجة واضحة في البحث 😕"
    except Exception as e:
        return f"📛 حصل خطأ أثناء البحث: {str(e)}"

# ========== تحليل الصور ==========
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    # تحويل الصورة إلى base64
    image_base64 = base64.b64encode(image_bytes).decode()
    image_data_url = f"data:image/jpeg;base64,{image_base64}"

    user_id = update.message.from_user.id
    image_context[user_id] = image_data_url

    await update.message.reply_text("✅ استلمت الصورة، تحب أعمل فيها شنو؟")

async def handle_image_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in image_context:
        await update.message.reply_text("🚫 ما عندي صورة حالياً ليك، أرسل صورة الأول.")
        return

    prompt = update.message.text.strip()
    image_data_url = image_context[user_id]

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ],
        "max_tokens": 500
    }

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as resp:
            data = await resp.json()

            if "error" in data:
                await update.message.reply_text(f"📛 حصل خطأ:\n{data['error']['message']}")
                print("🔴 خطأ OpenAI:", data)
                return

            result = data['choices'][0]['message']['content']

    await update.message.reply_text(result)
    del image_context[user_id]

# ========== /start ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = update.message.chat.id
    dialect = "العربية الفصحى"
    group_dialects[group_id] = dialect
    group_sessions[group_id] = [{"role": "system", "content": RAHIM_MAIN_PROMPT}]
    await update.message.reply_text("البوت شغال ✅")

# ========== رسائل القروب ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username.lower()
    user_message = update.message.text.lower()

    if (
        f"@{bot_username}" not in user_message
        and "رحيم" not in user_message
        and "rahim" not in user_message
        and not update.message.reply_to_message
    ):
        return

    group_id = update.message.chat.id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.full_name

    if update.message.reply_to_message and update.message.reply_to_message.text:
        target_text = update.message.reply_to_message.text
        combined_input = f"{update.message.text}\n\nالرسالة المردود عليها:\n{target_text}"
    else:
        combined_input = update.message.text

    if group_id not in group_sessions:
        detected = await detect_language_or_dialect(combined_input)
        group_dialects[group_id] = detected
        group_sessions[group_id] = [{"role": "system", "content": RAHIM_MAIN_PROMPT}]
    else:
        detected = group_dialects.get(group_id, "العربية الفصحى")

    group_sessions[group_id].append({"role": "user", "content": combined_input})
    group_sessions[group_id] = group_sessions[group_id][-MAX_SESSION_LENGTH:]

    save_message_to_sheet({
        "user_id": user_id,
        "user_name": user_name,
        "group_id": group_id,
        "text": combined_input,
        "dialect": detected,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    if any(x in combined_input for x in ["علاج", "تشخيص", "أعراض", "مرض", "دواء"]):
        web_result = await perform_web_search(combined_input)
    
        if "ما لقيت نتيجة واضحة" in web_result or "📛 حصل خطأ" in web_result:
            await update.message.reply_text("ما لقيت مصدر خارجي، لكن خليني أشرح ليك من معرفتي العامة...")
        else:
            await update.message.reply_text(web_result)
            return  # لو نجح في البحث، ما في داعي يرجع لـ GPT

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=group_sessions[group_id]
        )
        reply = response.choices[0].message.content.strip()
        group_sessions[group_id].append({"role": "assistant", "content": reply})
        group_sessions[group_id] = group_sessions[group_id][-MAX_SESSION_LENGTH:]
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("حصل خطأ في الذكاء الصناعي 😔")
        print(f"OpenAI error: {e}", flush=True)

# ========== الخاص ==========
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً! 👋 البوت دا مخصص للقروبات فقط.\n"
        "Please note: This bot is designed for group chats only.\n"
        "أضفني لقروبك عشان أقدر أساعدك 🚀"
    )

# ========== التعامل مع الملفات ==========
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_ext = file.file_path.split('.')[-1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp:
        await file.download_to_drive(temp.name)

        if file_ext == "pdf":
            text = extract_text_from_pdf(temp.name)
        elif file_ext in ["docx", "doc"]:
            text = extract_text_from_docx(temp.name)
        elif file_ext in ["xlsx", "xls"]:
            text = extract_text_from_excel(temp.name)
        else:
            await update.message.reply_text("حالياً بقدر أقرأ ملفات PDF, Word و Excel فقط.")
            return

        if len(text) > 2000:
            text = text[:2000] + "\n\n📌 النص طويل جداً، تم عرض جزء فقط."

        await update.message.reply_text(
            f"📂 تم استخراج المحتوى:\n\n{text}\n\nتحب أعمل شنو بيهو؟ (تلخيص؟ تحليل؟ فلاش كارد؟)"
        )

# ========== Webhook ==========
async def webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        print(f"Webhook error: {e}", flush=True)
    return web.Response(text="OK")

# ========== تشغيل التطبيق ==========
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_message))
application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.TEXT, handle_image_action))
app = web.Application()
app.router.add_post(f'/{BOT_TOKEN}', webhook)

async def run():
    await application.initialize()
    await application.start()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=int(os.getenv("PORT", 8080)))
    await site.start()
    print("💬 البوت شغال على السيرفر...")
    await asyncio.Event().wait()

asyncio.run(run())
