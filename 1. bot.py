import os
import io
import json
import datetime
import logging
import gspread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from google.oauth2.service_account import Credentials
from google.cloud import vision

# === Створення credentials.json з ENV-перемінної ===
credentials_json = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
with open("credentials.json", "w") as f:
    json.dump(credentials_json, f)

# === Google Sheets Setup ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(credentials)
worksheet = gc.open("AutoService").sheet1

# === Vision API Setup ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"
vision_client = vision.ImageAnnotatorClient()

# === Telegram Token ===
BOT_TOKEN = os.getenv("BOT_TOKEN")

# === Логування ===
logging.basicConfig(level=logging.INFO)

# === Команди ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Надішли фото техпаспорта.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    image_stream = io.BytesIO()
    await photo.download_to_memory(out=image_stream)
    image_content = image_stream.getvalue()

    image = vision.Image(content=image_content)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations

    full_text = texts[0].description if texts else ""
    vin = "---"
    for line in full_text.splitlines():
        line = line.strip()
        if len(line) >= 17 and any(c.isdigit() for c in line):
            vin = line
            break

    context.user_data["vin"] = vin
    worksheet.append_row([str(datetime.datetime.now()), vin, "", full_text])
    await update.message.reply_text(f"✅ VIN: `{vin}`\nВкажи деталі, які потрібно замінити.", parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vin = context.user_data.get("vin", "---")
    details = update.message.text
    worksheet.append_row([str(datetime.datetime.now()), vin, details, ""])
    await update.message.reply_text("🔧 Дані збережено. Дякую!")

# === Запуск ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
