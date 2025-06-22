import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import openai

# ====== المتغيرات ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 10000))

client = openai.OpenAI(api_key=OPENAI_API_KEY)
user_sessions = {}

# ====== أوامر البوت ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت شغال ✅")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text

    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {"role": "system", "content": "أنت مساعد ذكي جدًا يشبه ChatGPT. ردودك طبيعية، ودودة، وعميقة، وبتحاول تفهم السؤال كويس قبل ما تجاوب. أكتب بلغة بشرية طبيعية."}
        ]

    user_sessions[user_id].append({"role": "user", "content": text})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_sessions[user_id],
            temperature=0.7,
            max_tokens=300
        )
        reply = response.choices[0].message.content.strip()
        user_sessions[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("حصل خطأ في الذكاء الصناعي 😔")
        print(f"OpenAI error: {e}", flush=True)

# ====== تشغيل البوت ======
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("البوت شغال على السيرفر باستخدام Webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
