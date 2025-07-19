from telegram import Update
from telegram.ext import ContextTypes
from trends_manager import get_general_trend

async def handle_trend_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trend = get_general_trend()
    if trend:
        await update.message.reply_text(f"📌 ترند اليوم:\n\n{trend}")
    else:
        await update.message.reply_text("ما لقيت أي ترند 😅، اضيفي بعض الترندات في trends_data.json.")
