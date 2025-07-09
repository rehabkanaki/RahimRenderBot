# ========== استيراد مكتبات جديدة ==========
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

# مكتبات قراءة الملفات
import fitz  # PyMuPDF للـ PDF
from docx import Document as DocxReader
import pandas as pd
import tempfile

# ========== المتغيرات ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MAX_SESSION_LENGTH = 20

client = OpenAI(api_key=OPENAI_API_KEY)
group_sessions = {}
group_dialects = {}

# ========== Google Sheets ==========
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
gc = gspread.authorize(creds)
sheet = gc.open("RahimBot_History").sheet1

# ========== تحميل برومبت ==========
with open("rahim_prompts_library.txt", "r", encoding="utf-8") as f:
    PROMPTS_LIBRARY = f.read()

RAHIM_MAIN_PROMPT = """
(هنا نفس البرومبت الطويل الخاص بشخصية رحيم)
"""

# ========== أدوات قراءة الملفات ==========
def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

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

# ========== التعامل مع الملفات المرسلة ==========
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بيك! 👋 أنا رحيم، مساعدك الذكي. أرسل لي أي سؤال أو ملف وحنبدأ 😄")

# ========== إضافة الهاندلر ==========
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_message))
application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

# ========== Webhook ==========
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
