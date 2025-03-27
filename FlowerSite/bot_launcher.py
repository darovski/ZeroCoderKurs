import os
from time import process_time

import django
import logging
from telegram import Update, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from django.conf import settings
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from telegram.ext import ConversationHandler, MessageHandler, filters
from datetime import datetime

# Состояния для ConversationHandler
ORDER_ADDRESS, ORDER_DATE, ORDER_TIME, ORDER_PHONE = range(4)


# ... (ваш код функций start_order, process_address, process_date, process_time, process_phone, cancel_order_creation, notify_admin) ...

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

    # Optionally, send a message to the developer to notify them of the error.
    # You can change the chat ID to your own.
    developer_chat_id = settings.TELEGRAM_ADMINS[0] # или любой другой id
    await context.bot.send_message(chat_id=developer_chat_id, text=f"Произошла ошибка при обработке обновления:\n\n{context.error}")

async def web_app_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Открыть магазин в Telegram',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "Открыть магазин",
                web_app=WebAppInfo(url="https://flower-delivery.ru/telegram-shop/")
            )
        ]]))

# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FlowerSite.settings')
django.setup()

from flower_app.models import Product, Order, Cart

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("🛍️ Каталог", callback_data='catalog')],
        [InlineKeyboardButton("📦 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("🌐 Наш сайт", url='https://flower-delivery.ru')]
    ]
    await update.message.reply_text(
        '🌸 Добро пожаловать в цветочный магазин!',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    products = Product.objects.all()[:10]  # Первые 10 товаров
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            f"{product.name} - {product.price}₽",
            callback_data=f"product_{product.id}"
        )])

    await update.callback_query.edit_message_text(
        "Выберите товар:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    product_id = update.callback_query.data.split('_')[1]
    product = Product.objects.get(id=product_id)

    keyboard = [
        [InlineKeyboardButton("🛒 В корзину", callback_data=f"add_{product.id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_catalog")]
    ]

    await update.callback_query.message.reply_photo(
        photo=open(product.image.path, 'rb'),
        caption=f"*{product.name}*\n\n{product.description}\n\nЦена: {product.price}₽",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    product_id = update.callback_query.data.split('_')[1]
    product = Product.objects.get(id=product_id)
    user = update.effective_user
    cart, created = Cart.objects.get_or_create(user__telegram_id=user.id)
    cart.items.add(product)
    await update.callback_query.answer(text=f"{product.name} добавлен в корзину!")

async def back_to_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await catalog(update, context)

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    order_id = update.callback_query.data.split('_')[1]
    order = Order.objects.get(id=order_id)
    # Добавьте логику для подтверждения заказа
    await update.callback_query.message.reply_text(f"Заказ №{order.id} подтвержден.")

async def admin_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    order_id = update.callback_query.data.split('_')[2]
    order = Order.objects.get(id=order_id)
    # Добавьте логику для отмены заказа
    await update.callback_query.message.reply_text(f"Заказ №{order.id} отменен.")

def main(process_phone=None, process_date=None, process_address=None, start_order=None, cancel_order_creation=None) -> None:
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(catalog, pattern='^catalog$'))
    application.add_handler(CallbackQueryHandler(show_product, pattern='^product_'))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern='^add_'))
    application.add_handler(CallbackQueryHandler(back_to_catalog, pattern='^back_to_catalog$'))
    application.add_handler(CallbackQueryHandler(confirm_order, pattern='^confirm_'))
    application.add_handler(CallbackQueryHandler(admin_cancel_order, pattern='^admin_cancel_'))
    application.add_error_handler(error_handler)

    # Обработчик создания заказа
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('checkout', start_order),
            CallbackQueryHandler(start_order, pattern='^create_order$')
        ],
        states={
            ORDER_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_address)],
            ORDER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_date)],
            ORDER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_time)],
            ORDER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_order_creation),
            CallbackQueryHandler(cancel_order_creation, pattern='^cancel_order$')
        ]
    )

    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == '__main__':
    main()