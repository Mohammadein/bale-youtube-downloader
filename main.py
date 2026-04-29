from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

BOT_TOKEN = "665419412:REnWbsHEGIC_EP0kjB_VbKhxzTpLyZsFPG4"

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(update.message.text)


def main():
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .base_url("https://tapi.bale.ai/bot")
        .build()
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, echo)
    )

    print("Echo Bot is running on Bale API...")
    application.run_polling()


if __name__ == "__main__":
    main()
