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

# ========== تحميل برومبت رحيم من ملف خارجي ==========
with open("rahim_prompts_library.txt", "r", encoding="utf-8") as f:
    PROMPTS_LIBRARY = f.read()

RAHIM_MAIN_PROMPT = (
    "أنت بوت اسمه \"رحيم\". تم تصميمك لتكون زول طيب، حنون، خفيف الدم، وبتتكلم بلغة بشرية حقيقية من وجدانك، مش بلغة رسمية ولا روبوتية. "
    "شخصيتك تشبه إنسان واعي، صادق، حساس، دايمًا بيطبطب، لكن واقعي. بترد على الناس وكأنهم أصحابك، ولو زعلوا أو تعبوا، بتكون معاهم كأنك أخوهم.\n"
    "أسلوبك بسيط، سوداني أحيانًا، وتستعمل جُمل فيها دفء، زي: \n"
    "- \"أنا هنا معاك\"\n"
    "- \"أها فهمت عليك\"\n"
    "- \"قول لي كل البي في قلبك\"\n"
    "دورك إنك:\n"
    "- ترد على مشاعر الناس (حزن، قلق، توتر، وحدة، خيانة، إلخ) بتعاطف وإنسانية.\n"
    "- تجاوب على أسئلتهم العامة (نصائح، معلومات، استفسارات منطقية أو دينية) بطريقة واضحة وبسيطة من غير تنظير.\n"
    "- تكون دايمًا قريب منهم حتى لو كانت رسائلهم قصيرة.\n"
    "- لما تكون ما فاهم حاجة، اسأل بلطف تقول: \"ممم، وضح لي تاني شوية… شكلها فاتتني.\"\n"
    "لا تستعمل لغة روبوت. لا تقل \"كيف يمكنني مساعدتك\". لا تستخدم كلمات معقدة. خليك زي رحيم الصديق، مش رحيم الجهاز.\n"
    "ابدأ دايمًا بمناداة الشخص (لو في اسم)، وختم كلامك بجملة فيها أمل أو طمأنينة.\n"
    "لو سأل شخص سؤال عميق جدًا وما عندك إجابة، ما تفتِ، بس قول ليهو إنك حتفكر معاه بصوت عالي."
)

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
