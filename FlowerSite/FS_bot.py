import os
import logging
from datetime import datetime
import django
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist

# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FlowerSite.settings')
django.setup()

from flower_app.models import Order, Cart, Product, User, CartItem, OrderItem
from django.conf import settings

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для оформления заказа
ORDER_ADDRESS, ORDER_DATE, ORDER_TIME, ORDER_PHONE = range(4)


### Асинхронные обертки для Django ORM ###
@sync_to_async
def get_user_by_telegram_username(username):
    try:
        return User.objects.get(telegram_username=username)
    except ObjectDoesNotExist:
        return None


@sync_to_async
def get_or_create_user(telegram_id, username, first_name):
    user, created = User.objects.get_or_create(
        telegram_username=username,
        defaults={
            'telegram_id': str(telegram_id),
            'first_name': first_name,
        }
    )
    return user


@sync_to_async
def get_product(product_id):
    try:
        return Product.objects.get(id=product_id)
    except ObjectDoesNotExist:
        return None


@sync_to_async
def get_or_create_cart(user):
    cart, created = Cart.objects.get_or_create(user=user)
    return cart, created


@sync_to_async
def get_cart_items(cart):
    return list(CartItem.objects.filter(cart=cart).select_related('product'))


@sync_to_async
def clear_cart(cart):
    CartItem.objects.filter(cart=cart).delete()


@sync_to_async
def add_to_cart_db(cart, product):
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return cart_item


@sync_to_async
def create_order(user, address, delivery_date, delivery_time, phone, total_price):
    cart = Cart.objects.get(user=user)
    cart_items = CartItem.objects.filter(cart=cart)

    order = Order.objects.create(
        user=user,
        address=address,
        delivery_date=delivery_date,
        delivery_time=delivery_time,
        phone=phone,
        total_price=total_price,
        status='new'
    )

    for cart_item in cart_items:
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            quantity=cart_item.quantity,
            price=cart_item.product.price
        )

    cart_items.delete()
    return order


@sync_to_async
def get_user_orders(user):
    return list(Order.objects.filter(user=user)
                .prefetch_related('orderitem_set__product')
                .order_by('-created_at')[:10])


### Обработчики команд ###
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if not user.username:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ У вас не установлен username в Telegram. Пожалуйста, добавьте его в настройках профиля!"
            )
        else:
            await update.message.reply_text(
                "❌ У вас не установлен username в Telegram. Пожалуйста, добавьте его в настройках профиля!"
            )
        return

    user_obj = await get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    keyboard = [
        [InlineKeyboardButton("🛍️ Каталог", callback_data='catalog')],
        [InlineKeyboardButton("📦 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("🛒 Корзина", callback_data='view_cart')],
        [InlineKeyboardButton("🌐 Наш сайт", url='https://flower-delivery.ru')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                '🌸 Добро пожаловать в цветочный магазин!',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await update.callback_query.message.reply_text(
                '🌸 Добро пожаловать в цветочный магазин!',
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(
            '🌸 Добро пожаловать в цветочный магазин!',
            reply_markup=reply_markup
        )


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    products = await sync_to_async(list)(Product.objects.all()[:10])
    keyboard = [
        [InlineKeyboardButton(f"{p.name} - {p.price}₽", callback_data=f"product_{p.id}")]
        for p in products
    ]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        try:
            await query.edit_message_text(
                "Выберите товар:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing catalog: {e}")
            await query.message.reply_text(
                "Выберите товар:",
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(
            "Выберите товар:",
            reply_markup=reply_markup
        )


async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.split('_')[1]
    product = await get_product(product_id)

    if not product:
        await query.answer("Товар не найден")
        return

    keyboard = [
        [InlineKeyboardButton("➕ В корзину", callback_data=f"add_{product.id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="catalog")],
    ]

    try:
        await query.message.reply_photo(
            photo=open(product.image.path, 'rb'),
            caption=f"*{product.name}*\n\n{product.description}\n\nЦена: {product.price}₽",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        try:
            await query.edit_message_text(
                f"*{product.name}*\n\n{product.description}\n\nЦена: {product.price}₽",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.message.reply_text(
                f"*{product.name}*\n\n{product.description}\n\nЦена: {product.price}₽",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard))


async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    if not user.username:
        await query.edit_message_text("❌ У вас не установлен username!")
        return

    user_obj = await get_user_by_telegram_username(user.username)
    if not user_obj:
        await query.edit_message_text("Сначала нажмите /start")
        return

    product_id = query.data.split('_')[1]
    product = await get_product(product_id)
    if not product:
        await query.answer("Товар не найден")
        return

    cart, created = await get_or_create_cart(user_obj)
    cart_item = await add_to_cart_db(cart, product)
    await query.answer(f"{product.name} добавлен в корзину (теперь {cart_item.quantity} шт.)")


async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    if not user.username:
        await query.edit_message_text("❌ У вас не установлен username!")
        return

    user_obj = await get_user_by_telegram_username(user.username)
    if not user_obj:
        await query.edit_message_text("Сначала нажмите /start")
        return

    cart, created = await get_or_create_cart(user_obj)
    cart_items = await get_cart_items(cart)

    if not cart_items:
        await query.answer("Ваша корзина пуста")
        return

    total = sum(item.product.price * item.quantity for item in cart_items)
    message = "🛒 Ваша корзина:\n\n" + "\n".join(
        f"• {item.product.name} - {item.product.price}₽ × {item.quantity} = {item.product.price * item.quantity}₽"
        for item in cart_items
    )
    message += f"\n\n💵 Итого: {total}₽"

    keyboard = [
        [InlineKeyboardButton(f"➖ {item.product.name}", callback_data=f"decrease_{item.id}"),
         InlineKeyboardButton(f"➕ {item.product.name}", callback_data=f"increase_{item.id}")]
        for item in cart_items
    ]
    keyboard += [
        [InlineKeyboardButton("🚀 Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("❌ Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error editing cart: {e}")
        await query.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard))


async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    if not user.username:
        await query.edit_message_text("❌ У вас не установлен username!")
        return

    user_obj = await get_user_by_telegram_username(user.username)
    if not user_obj:
        await query.edit_message_text("Сначала нажмите /start")
        return

    orders = await get_user_orders(user_obj)

    if not orders:
        await query.edit_message_text("📭 У вас пока нет заказов")
        return

    message = "📋 Ваши последние заказы:\n\n"
    for order in orders:
        order_items = await sync_to_async(list)(order.orderitem_set.all())
        message += f"🛒 Заказ #{order.id}\n"
        message += f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        message += f"🏠 Адрес: {order.address}\n"
        message += f"📞 Телефон: {order.phone}\n"
        message += f"🚚 Доставка: {order.delivery_date} в {order.delivery_time}\n"

        for item in order_items:
            message += f"   • {item.product.name} × {item.quantity} = {item.price * item.quantity}₽\n"

        message += f"💵 Итого: {order.total_price}₽\n"
        message += f"📌 Статус: {order.get_status_display()}\n\n"

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]))
    except Exception as e:
        logger.error(f"Error editing orders: {e}")
        await query.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]))


### Оформление заказа ###
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    if not user.username:
        await query.edit_message_text("❌ У вас не установлен username!")
        return

    user_obj = await get_user_by_telegram_username(user.username)
    if not user_obj:
        await query.edit_message_text("Сначала нажмите /start")
        return

    cart, created = await get_or_create_cart(user_obj)
    cart_items = await get_cart_items(cart)

    if not cart_items:
        await query.answer("Ваша корзина пуста!")
        return

    try:
        await query.edit_message_text(
            "Пожалуйста, введите адрес доставки:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
    except Exception as e:
        logger.error(f"Error starting order: {e}")
        await query.message.reply_text(
            "Пожалуйста, введите адрес доставки:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
    return ORDER_ADDRESS


async def process_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['address'] = update.message.text
    await update.message.reply_text(
        "Введите дату доставки (например, 25.12.2023):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
        ]))
    return ORDER_DATE


async def process_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delivery_date = datetime.strptime(update.message.text, '%d.%m.%Y').date()
        context.user_data['delivery_date'] = delivery_date
        await update.message.reply_text(
            "Введите время доставки (например, 14:00):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
        return ORDER_TIME
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
        return ORDER_DATE


async def process_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delivery_time = datetime.strptime(update.message.text, '%H:%M').time()
        context.user_data['delivery_time'] = delivery_time
        await update.message.reply_text(
            "Введите ваш телефон для связи:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
        return ORDER_PHONE
    except ValueError:
        await update.message.reply_text(
            "Неверный формат времени. Пожалуйста, введите время в формате ЧЧ:ММ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
        return ORDER_TIME


async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone = update.message.text

    if not user.username:
        await update.message.reply_text("Ошибка: username не найден")
        return ConversationHandler.END

    user_obj = await get_user_by_telegram_username(user.username)
    if not user_obj:
        await update.message.reply_text("Ошибка: пользователь не найден")
        return ConversationHandler.END

    cart, created = await get_or_create_cart(user_obj)
    cart_items = await get_cart_items(cart)
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    order = await create_order(
        user=user_obj,
        address=context.user_data['address'],
        delivery_date=context.user_data['delivery_date'],
        delivery_time=context.user_data['delivery_time'],
        phone=phone,
        total_price=total_price
    )

    await update.message.reply_text(
        f"✅ Заказ #{order.id} успешно оформлен!\n"
        f"Мы свяжемся с вами для подтверждения.")

    # Уведомление администратора
    await notify_admin(context.bot, order)

    return ConversationHandler.END


async def notify_admin(bot, order):
    try:
        admin_chat_id = settings.TELEGRAM_ADMIN_CHAT_ID

        order_items = await sync_to_async(list)(order.orderitem_set.all())
        message = (
            "🛒 *Новый заказ!*\n\n"
            f"🔹 Номер: #{order.id}\n"
            f"👤 Клиент: @{order.user.telegram_username}\n"
            f"📞 Телефон: {order.phone}\n"
            f"🏠 Адрес: {order.address}\n"
            f"🚚 Доставка: {order.delivery_date} в {order.delivery_time}\n"
        )

        for item in order_items:
            message += f"   • {item.product.name} × {item.quantity} = {item.price * item.quantity}₽\n"

        message += f"\n💵 Итого: {order.total_price}₽\n"
        message += "📌 Статус: Новый"

        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order.id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order.id}")
            ]
        ]

        await bot.send_message(
            chat_id=admin_chat_id,
            text=message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Admin notification error: {e}")


async def cancel_order_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                "Оформление заказа отменено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("В главное меню", callback_data="main_menu")]
                ]))
        except:
            await update.callback_query.message.reply_text(
                "Оформление заказа отменено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("В главное меню", callback_data="main_menu")]
                ]))
    else:
        await update.message.reply_text("Оформление заказа отменено.")
    return ConversationHandler.END


async def clear_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_obj = await get_user_by_telegram_username(user.username)

    if user_obj:
        cart, created = await get_or_create_cart(user_obj)
        await clear_cart(cart)
        await query.answer("Корзина очищена!")
        await view_cart(update, context)


@sync_to_async
def update_cart_item_quantity(item_id, change):
    try:
        item = CartItem.objects.get(id=item_id)
        if change == 'increase':
            item.quantity += 1
        elif change == 'decrease' and item.quantity > 1:
            item.quantity -= 1
        item.save()
        return item
    except CartItem.DoesNotExist:
        return None


async def change_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, item_id = query.data.split('_')
    item = await update_cart_item_quantity(item_id, action)

    if item:
        await view_cart(update, context)
    else:
        await query.answer("Ошибка обновления количества")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    if settings.DEBUG:
        developer_chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
        await context.bot.send_message(
            chat_id=developer_chat_id,
            text=f"Произошла ошибка:\n\n{context.error}")


def main() -> None:
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Основные обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(catalog, pattern='^catalog$'))
    application.add_handler(CallbackQueryHandler(show_product, pattern='^product_'))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern='^add_'))
    application.add_handler(CallbackQueryHandler(view_cart, pattern='^view_cart$'))
    application.add_handler(CallbackQueryHandler(list_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(start_order, pattern='^checkout$'))
    application.add_handler(CallbackQueryHandler(cancel_order_creation, pattern='^cancel_order$'))
    application.add_handler(CallbackQueryHandler(clear_cart_handler, pattern='^clear_cart$'))
    application.add_handler(CallbackQueryHandler(change_quantity, pattern='^(increase|decrease)_'))
    application.add_handler(CallbackQueryHandler(start, pattern='^main_menu$'))

    # Обработчик оформления заказа
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order, pattern='^checkout$')],
        states={
            ORDER_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_address)],
            ORDER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_date)],
            ORDER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_time)],
            ORDER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_order_creation),
            CallbackQueryHandler(cancel_order_creation, pattern='^cancel_order$')
        ],
    )
    application.add_handler(conv_handler)

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()