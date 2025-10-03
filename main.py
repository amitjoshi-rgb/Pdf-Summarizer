import os
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
import openai
import PyPDF2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env vars
TELEGRAM_TOKEN = os.environ.get("")
OPENAI_API_KEY = os.environ.get("")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "mysecret")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Please set TELEGRAM_TOKEN and OPENAI_API_KEY in env vars")

bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

openai.api_key = OPENAI_API_KEY

# Dispatcher for Telegram updates
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# Handlers
def start(update, context):
    update.message.reply_text("नमस्ते! मुझे कोई PDF भेजिए और मैं उसका सारांश दूँगा।")

def help_command(update, context):
    update.message.reply_text("📄 बस मुझे कोई PDF file भेजिए, मैं उसका सारांश OpenAI API से बना दूँगा।")

def handle_pdf(update, context):
    file = update.message.document
    if not file.file_name.endswith(".pdf"):
        update.message.reply_text("❌ कृपया केवल PDF भेजें।")
        return
    
    file_id = file.file_id
    newFile = context.bot.get_file(file_id)
    file_path = "temp.pdf"
    newFile.download(file_path)

    # Extract text from PDF
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages[:5]:  # limit first 5 pages to save tokens
            text += page.extract_text() + "\n"

    if not text.strip():
        update.message.reply_text("❌ PDF से text निकालने में दिक्कत हुई।")
        return

    # Summarize with OpenAI
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a PDF summarizer."},
                {"role": "user", "content": f"Summarize this text:\n{text}"}
            ],
            max_tokens=300
        )
        summary = response["choices"][0]["message"]["content"]
        update.message.reply_text("📑 Summary:\n\n" + summary)
    except Exception as e:
        logger.error("OpenAI error: %s", str(e))
        update.message.reply_text("⚠️ OpenAI summarization failed।")

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(MessageHandler(Filters.document.mime_type("application/pdf"), handle_pdf))

@app.route("/")
def index():
    return "PDF summarizer bot running."

@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

if __name__ == "__main__":
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        webhook_url = f"{render_url}/webhook/{WEBHOOK_SECRET}"
        bot.set_webhook(webhook_url)
        logger.info(f"Webhook set: {webhook_url}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


