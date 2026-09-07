# -*- coding: utf-8 -*-
"""
Pul Perewot - Telegram Bot (Webhook / Render.com versiyonu)

GEREKLİ KÜTÜPHANELER (requirements.txt dosyasına yaz):
    python-telegram-bot==21.6
    requests
    flask

RENDER.COM AYARLARI:
    Build Command: pip install -r requirements.txt
    Start Command: python bot.py
    Environment Variable ekle:
        BOT_TOKEN = 8914060771:AAE6Uw9uXd2-vKH8jjeL4A7A2ddim5tPNWI
        RENDER_EXTERNAL_URL = (Render sana otomatik verir, deploy sonrası kopyala)
"""

import os
import requests
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import asyncio

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =====================================================
# AYARLAR
# =====================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8914060771:AAE6Uw9uXd2-vKH8jjeL4A7A2ddim5tPNWI")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")  # Render otomatik doldurur (bazı planlarda)
PORT = int(os.environ.get("PORT", 10000))

COMMISSION = 1.03
PHONE = "79030156403"

rates = {
    "USD": 86.56,
    "EUR": 94.20,
    "TRY": 2.65,
}

COIN_SYMBOL = {"USD": "$", "EUR": "€", "TRY": "₺"}


def fetch_rates():
    try:
        response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
        data = response.json()
        if data.get("rates"):
            rub = data["rates"]["RUB"]
            eur = data["rates"]["EUR"]
            try_ = data["rates"]["TRY"]
            rates["USD"] = rub
            rates["EUR"] = rub / eur
            rates["TRY"] = rub / try_
            return True
    except Exception as e:
        logger.warning(f"Kur çekilemedi: {e}")
    return False


def currency_keyboard():
    buttons = [
        [
            InlineKeyboardButton("💵 USD", callback_data="cur_USD"),
            InlineKeyboardButton("💶 EUR", callback_data="cur_EUR"),
            InlineKeyboardButton("💷 TRY", callback_data="cur_TRY"),
        ],
        [InlineKeyboardButton("↻ Kursy täzele", callback_data="refresh")],
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fetch_rates()
    text = "👋 *Pul Perewot*-a hoş geldiňiz!\n\nWalýuta saýlaň, soň mukdary ýazyň:"
    await update.message.reply_text(text, reply_markup=currency_keyboard(), parse_mode="Markdown")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "refresh":
        ok = fetch_rates()
        msg = "✅ Kursy täzelendi!" if ok else "⚠️ Täzelenip bilmedi, öňki kurs görkezilýär."
        await query.edit_message_text(f"{msg}\n\nWalýuta saýlaň:", reply_markup=currency_keyboard())
        return

    if query.data.startswith("cur_"):
        currency = query.data.replace("cur_", "")
        context.user_data["currency"] = currency
        await query.edit_message_text(
            f"Saýlanan walýuta: *{currency}* {COIN_SYMBOL[currency]}\n\nIndi mukdary ýazyň (mysal: 100):",
            parse_mode="Markdown",
        )


async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = context.user_data.get("currency")
    if not currency:
        await update.message.reply_text("Ilki walýuta saýlaň:", reply_markup=currency_keyboard())
        return

    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("⚠️ San ýazyň, mysal üçin: 100")
        return

    raw_rate = rates[currency]
    final_rate = raw_rate * COMMISSION
    total = round(amount * final_rate)

    message = (
        f"Walýuta: {currency}\nMukdar: {amount}\n"
        f"Kurs: {final_rate:.2f} RUB\nJemi: {total} RUB"
    )
    wa_text = message.replace(" ", "%20").replace("\n", "%0A")
    wa_link = f"https://wa.me/{PHONE}?text={wa_text}"

    result_text = f"💰 *Siz alarsyňyz:* {total:,} RUB\n📊 Kurs: {final_rate:.2f} RUB\n\n".replace(",", ".")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 WhatsApp arkaly ugrat", url=wa_link)],
        [InlineKeyboardButton("🔁 Başga walýuta", callback_data="new")],
    ])

    await update.message.reply_text(result_text, reply_markup=keyboard, parse_mode="Markdown")


async def new_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("currency", None)
    await query.edit_message_text("Walýuta saýlaň:", reply_markup=currency_keyboard())


# =====================================================
# TELEGRAM APPLICATION KURULUMU
# =====================================================

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(new_selection, pattern="^new$"))
telegram_app.add_handler(CallbackQueryHandler(button_handler, pattern="^(cur_|refresh)"))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler))

# =====================================================
# FLASK SUNUCUSU (Render'ın istediği web sunucusu)
# =====================================================

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "Pul Perewot bot işleýär! ✅"


@flask_app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"


async def setup_webhook():
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook/{BOT_TOKEN}"
        await telegram_app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook ayarlandı: {webhook_url}")
    else:
        logger.warning("RENDER_EXTERNAL_URL bulunamadı, webhook ayarlanamadı.")


async def main():
    await telegram_app.initialize()
    await setup_webhook()
    await telegram_app.start()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    flask_app.run(host="0.0.0.0", port=PORT)
