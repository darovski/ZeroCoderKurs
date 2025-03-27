from django.core.management.base import BaseCommand
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
from models import Product, Cart

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запускает Telegram бота для цветочного магазина'

    def handle(self, *args, **options):
        from django.conf import settings

        updater = Updater(settings.TELEGRAM_BOT_TOKEN)
        dispatcher = updater.dispatcher

        # Главное меню
        def main_menu():
            keyboard = [
                [InlineKeyboardButton("🌹 Все товары", callback_data='products')],
                [InlineKeyboardButton("🛒 Корзина", callback_data='cart')],
                [InlineKeyboardButton("📦 Мои заказы", callback_data='orders')],
                [InlineKeyboardButton("📞 Контакты", callback_data='contacts')],
            ]
            return InlineKeyboardMarkup(keyboard)

        # Обработчики команд
        def start(update, context):
            user = update.effective_user
            update.message.reply_text(
                f"Привет, {user.first_name}!\n\n"
                "Я бот цветочного магазина 🌸\n"
                "Могу показать каталог, помочь с заказом или рассказать об акциях.",
                reply_markup=main_menu()
            )

        def show_products(update, context):
            query = update.callback_query
            query.answer()

            products = Product.objects.all()
            keyboard = []

            for i in range(0, len(products), 2):
                row = []
                for product in products[i:i + 2]:
                    row.append(InlineKeyboardButton(
                        product.name,
                        callback_data=f'product_{product.id}'
                    ))
                keyboard.append(row)

            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back')])

            query.edit_message_text(
                text="Все товары в магазине:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        def show_product(update, context):
            query = update.callback_query
            query.answer()

            product_id = query.data.split('_')[1]
            product = Product.objects.get(id=product_id)

            keyboard = [
                [InlineKeyboardButton("➕ В корзину", callback_data=f'add_{product.id}')],
                [InlineKeyboardButton("🔙 Назад", callback_data='products')],
            ]

            try:
                context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=open(product.image.path, 'rb'),
                    caption=f"🌸 *{product.name}*\n\n"
                            f"💵 Цена: *{product.price} руб.*\n\n"
                            f"{product.description}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                query.edit_message_text(
                    text=f"🌸 *{product.name}*\n\n"
                         f"💵 Цена: *{product.price} руб.*\n\n"
                         f"{product.description}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        def add_to_cart(update, context):
            query = update.callback_query
            product_id = query.data.split('_')[1]

            user_id = update.effective_user.id
            cart, created = Cart.objects.get_or_create(user_id=user_id)

            product = Product.objects.get(id=product_id)
            cart.products.add(product)

            query.answer(f"{product.name} добавлен в корзину")

        def show_cart(update, context):
            query = update.callback_query
            query.answer()

            user_id = update.effective_user.id
            cart = Cart.objects.filter(user_id=user_id).first()

            if not cart or not cart.products.exists():
                query.edit_message_text(
                    text="Ваша корзина пуста",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🛍️ К товарам", callback_data='products')]]
                    )
                )
                return

            total = sum(product.price for product in cart.products.all())
            items_text = "\n".join(
                f"• {product.name} - {product.price} руб."
                for product in cart.products.all()
            )

            keyboard = [
                [InlineKeyboardButton("🚀 Оформить заказ", callback_data='checkout')],
                [InlineKeyboardButton("🛍️ Продолжить покупки", callback_data='products')],
            ]

            query.edit_message_text(
                text=f"🛒 *Ваша корзина*\n\n"
                     f"{items_text}\n\n"
                     f"💵 *Итого: {total} руб.*",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        def back_to_main(update, context):
            query = update.callback_query
            query.answer()
            query.edit_message_text(
                text="Выберите действие:",
                reply_markup=main_menu()
            )

        # Регистрация обработчиков
        dispatcher.add_handler(CommandHandler('start', start))
        dispatcher.add_handler(CallbackQueryHandler(show_products, pattern='^products$'))
        dispatcher.add_handler(CallbackQueryHandler(show_product, pattern='^product_'))
        dispatcher.add_handler(CallbackQueryHandler(add_to_cart, pattern='^add_'))
        dispatcher.add_handler(CallbackQueryHandler(show_cart, pattern='^cart$'))
        dispatcher.add_handler(CallbackQueryHandler(back_to_main, pattern='^back$'))

        # Обработка ошибок
        def error_handler(update, context):
            logger.error(msg="Ошибка в боте:", exc_info=context.error)
            if update.callback_query:
                update.callback_query.answer("Произошла ошибка, попробуйте позже")
            else:
                update.message.reply_text("Произошла ошибка, попробуйте позже")

        dispatcher.add_error_handler(error_handler)

        # Запуск бота
        self.stdout.write(self.style.SUCCESS('Бот запущен и ожидает сообщений...'))
        updater.start_polling()
        updater.idle()