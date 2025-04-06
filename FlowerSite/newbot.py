import os
import logging
from datetime import datetime
import django
import asyncio
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

# Настройка логирования
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
def create_order(user, delivery_address, delivery_date, delivery_time, phone, total_price):
    try:
        logger.info(f"Creating order for {user.username} with data: {locals()}")

        order = Order.objects.create(
            user=user,
            delivery_address=delivery_address,
            delivery_date=delivery_date,
            delivery_time=delivery_time,
            phone=phone,
            total_price=total_price,
            status='new'
        )

        cart = Cart.objects.filter(user=user).first()
        if not cart:
            logger.error(f"No cart found for user {user.username}")
            raise ValueError("Корзина не найдена")

        cart_items = CartItem.objects.filter(cart=cart)
        if not cart_items:
            logger.error(f"No items in cart for user {user.username}")
            raise ValueError("Нет товаров в корзине")

        items_created = []
        for item in cart_items:
            order_item = OrderItem.objects.create(
                order=order,
                product=item.product,
                price=item.product.price,
                quantity=item.quantity
            )
            items_created.append(order_item)

        cart_items.delete()
        logger.info(f"Order #{order.id} created successfully with {len(items_created)} items")
        return order

    except Exception as e:
        logger.error(f"Error creating order: {str(e)}", exc_info=True)
        raise


@sync_to_async
def get_user_orders(user):
    return list(Order.objects.filter(user=user)
                .prefetch_related('items__product')
                .order_by('-created_at')[:10])


@sync_to_async
def update_cart_item_quantity_db(item_id, change):
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


@sync_to_async
def get_order_items(order):
    return list(order.items.all())


### Основные обработчики ###
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if not user.username:
        await (update.callback_query.edit_message_text if update.callback_query else update.message.reply_text)(
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
    await (update.callback_query.edit_message_text if update.callback_query else update.message.reply_text)(
        '🌸 Добро пожаловать в цветочный магазин!',
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
🌸 *Помощь по боту* 🌸

*Основные команды:*
/start - Начать работу с ботом
/help - Показать это сообщение

*Как сделать заказ:*
1. Выберите товары в каталоге
2. Добавьте их в корзину
3. Перейдите в корзину (/cart)
4. Нажмите "Оформить заказ"
5. Введите данные для доставки

*Управление корзиной:*
- Используйте кнопки ➕/➖ для изменения количества
- "❌ Очистить корзину" - удалить все товары

*Техническая поддержка:*
Если возникли проблемы, пишите @FlowerSiteAdmins

Мы работаем ежедневно с 9:00 до 21:00
    """

    keyboard = [
        [InlineKeyboardButton("🛍️ Каталог", callback_data='catalog'),
         InlineKeyboardButton("🛒 Корзина", callback_data='view_cart')],
        [InlineKeyboardButton("📦 Мои заказы", callback_data='my_orders')]
    ]

    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
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

    # Проверяем, есть ли сохраненное сообщение с фото
    last_photo_id = context.user_data.get('last_photo_message_id')
    if last_photo_id:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=last_photo_id)
            del context.user_data['last_photo_message_id']
        except Exception as e:
            logger.error(f"Error deleting photo message: {e}")

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
        # Сначала отправляем фото с описанием
        photo_message = await query.message.reply_photo(
            photo=open(product.image.path, 'rb'),
            caption=f"*{product.name}*\n\n{product.description}\n\nЦена: {product.price}₽",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))

        # Сохраняем ID сообщения с фото для последующего редактирования
        context.user_data['last_photo_message_id'] = photo_message.message_id

    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        # Если не удалось отправить фото, отправляем текстовое сообщение
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
        try:
            await query.edit_message_text(
                "🛒 Ваша корзина пуста!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍️ В каталог", callback_data="catalog")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
                ]))
        except Exception as e:
            await query.message.reply_text(
                "🛒 Ваша корзина пуста!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍️ В каталог", callback_data="catalog")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
                ]))
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
        try:
            await query.edit_message_text(
                "📦 У вас пока нет заказов",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍️ В каталог", callback_data="catalog")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
                ]))
        except Exception as e:
            await query.message.reply_text(
                "📦 У вас пока нет заказов",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍️ В каталог", callback_data="catalog")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
                ]))
        return

    message = "📋 Ваши последние заказы:\n\n"
    for order in orders:
        message += (
            f"🔹 Заказ #{order.id}\n"
            f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"🏠 Адрес: {order.delivery_address}\n"
            f"📞 Телефон: {order.phone}\n"
            f"🚚 Доставка: {order.delivery_date} в {order.delivery_time}\n"
            f"💵 Сумма: {order.total_price} руб.\n"
            f"📌 Статус: {order.get_status_display()}\n\n"
        )

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]))
    except Exception as e:
        await query.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]))


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

    if not hasattr(context, 'user_data') or context.user_data is None:
        context.user_data = {}

    cart, created = await get_or_create_cart(user_obj)
    cart_items = await get_cart_items(cart)

    if not cart_items:
        try:
            await query.edit_message_text(
                "🛒 Ваша корзина пуста!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍️ В каталог", callback_data="catalog")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
                ]))
        except Exception as e:
            await query.message.reply_text(
                "🛒 Ваша корзина пуста!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍️ В каталог", callback_data="catalog")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
                ]))
        return

    try:
        await query.edit_message_text(
            "Пожалуйста, введите адрес доставки:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
        return ORDER_ADDRESS
    except Exception as e:
        await query.message.reply_text(
            "Пожалуйста, введите адрес доставки:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_order")]
            ]))
        return ORDER_ADDRESS


async def process_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not hasattr(context, 'user_data') or context.user_data is None:
            context.user_data = {}

        context.user_data['delivery_address'] = update.message.text
        logger.info(f"Delivery address saved: {context.user_data['delivery_address']}")

        await update.message.reply_text(
            "📅 Введите дату доставки в формате ДД.ММ.ГГГГ (например, 25.12.2023):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))

        return ORDER_DATE

    except Exception as e:
        logger.error(f"Error in process_address: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка. Попробуйте ввести адрес ещё раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))
        return ORDER_ADDRESS


async def process_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if 'delivery_address' not in context.user_data:
            await update.message.reply_text("❌ Адрес не найден. Начните заново.")
            return ConversationHandler.END

        delivery_date = datetime.strptime(update.message.text, '%d.%m.%Y').date()
        context.user_data['delivery_date'] = delivery_date
        logger.info(f"Delivery date saved: {delivery_date}")

        await update.message.reply_text(
            "⌚ Введите время доставки в формате ЧЧ:ММ (например, 14:00):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))

        return ORDER_TIME

    except ValueError:
        logger.warning(f"Invalid date format: {update.message.text}")
        await update.message.reply_text(
            "⚠️ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n"
            "Например: 25.12.2023",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))
        return ORDER_DATE

    except Exception as e:
        logger.error(f"Unexpected error in process_date: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обработке даты. Пожалуйста, попробуйте ещё раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))
        return ORDER_DATE


async def process_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if 'delivery_address' not in context.user_data or 'delivery_date' not in context.user_data:
            await update.message.reply_text("❌ Отсутствуют предыдущие данные. Начните заново.")
            return ConversationHandler.END

        delivery_time = datetime.strptime(update.message.text, '%H:%M').time()
        context.user_data['delivery_time'] = delivery_time
        logger.info(f"Delivery time saved: {delivery_time}")

        await update.message.reply_text(
            "📱 Введите ваш номер телефона для связи:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))

        return ORDER_PHONE

    except ValueError:
        logger.warning(f"Invalid time format: {update.message.text}")
        await update.message.reply_text(
            "⚠️ Неверный формат времени. Пожалуйста, введите время в формате ЧЧ:ММ\n"
            "Например: 14:00",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))
        return ORDER_TIME

    except Exception as e:
        logger.error(f"Unexpected error in process_time: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обработке времени. Пожалуйста, попробуйте ещё раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel_order")]
            ]))
        return ORDER_TIME


async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Processing phone, user_data: {context.user_data}")

        required_fields = ['delivery_address', 'delivery_date', 'delivery_time']
        missing_fields = [field for field in required_fields if field not in context.user_data]

        if missing_fields:
            error_msg = f"Отсутствуют данные: {', '.join(missing_fields)}. Начните заново."
            await update.message.reply_text(error_msg)
            return ConversationHandler.END

        phone = update.message.text.strip()
        if not phone:
            await update.message.reply_text("❌ Номер телефона не может быть пустым.")
            return ORDER_PHONE

        user = update.effective_user
        user_obj = await get_user_by_telegram_username(user.username)
        if not user_obj:
            await update.message.reply_text("❌ Пользователь не найден.")
            return ConversationHandler.END

        cart, _ = await get_or_create_cart(user_obj)
        cart_items = await get_cart_items(cart)
        if not cart_items:
            await update.message.reply_text("❌ Корзина пуста.")
            return ConversationHandler.END

        total_price = sum(item.product.price * item.quantity for item in cart_items)

        try:
            order = await create_order(
                user=user_obj,
                delivery_address=context.user_data['delivery_address'],
                delivery_date=context.user_data['delivery_date'],
                delivery_time=context.user_data['delivery_time'],
                phone=phone,
                total_price=total_price
            )
        except Exception as e:
            logger.error(f"Order creation failed: {e}")
            await update.message.reply_text("❌ Ошибка при создании заказа. Пожалуйста, попробуйте ещё раз.")
            return ConversationHandler.END

        order_info = (
            f"✅ Заказ #{order.id} успешно оформлен!\n"
            f"Адрес: {context.user_data['delivery_address']}\n"
            f"Дата: {context.user_data['delivery_date']}\n"
            f"Время: {context.user_data['delivery_time']}\n"
            f"Телефон: {phone}\n"
            f"Сумма: {total_price} руб.\n\n"
            "Мы свяжемся с вами для подтверждения."
        )

        # Отправляем информацию о заказе
        await update.message.reply_text(order_info)

        # Добавляем завершающее сообщение с кнопкой в главное меню
        goodbye_message = (
            "🌸 Спасибо за ваш заказ!\n"
            "Желаем вам прекрасного дня!\n"
            "Если у вас есть вопросы, мы всегда на связи."
        )

        await update.message.reply_text(
            goodbye_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
            ])
        )

        # Уведомление администратора в фоне
        asyncio.create_task(notify_admin(context.bot, order))

        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in process_phone: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при оформлении заказа. Пожалуйста, попробуйте ещё раз.")
        return ConversationHandler.END


@sync_to_async
def prepare_admin_notification(order_id):
    try:
        order = Order.objects.select_related('user').prefetch_related('items__product').get(id=order_id)
        items_text = "\n".join(
            f"   • {item.product.name} × {item.quantity} = {item.price * item.quantity}₽"
            for item in order.items.all()
        )

        return (
            f"🛒 *Новый заказ!*\n\n"
            f"🔹 Номер: #{order.id}\n"
            f"👤 Клиент: @{order.user.telegram_username}\n"
            f"📞 Телефон: {order.phone}\n"
            f"🏠 Адрес: {order.delivery_address}\n"
            f"📅 Дата: {order.delivery_date}\n"
            f"⌚ Время: {order.delivery_time}\n"
            f"{items_text}\n\n"
            f"💵 Итого: {order.total_price}₽\n"
            f"📌 Статус: Новый"
        )
    except Exception as e:
        logger.error(f"Error preparing admin notification: {e}")
        return None


async def notify_admin(bot, order):
    try:
        message = await prepare_admin_notification(order.id)
        if not message:
            return

        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order.id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order.id}")
            ]
        ]

        await bot.send_message(
            chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
            text=message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Admin notification error: {e}")


async def cancel_order_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                "❌ Оформление заказа отменено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("В главное меню", callback_data="main_menu")]
                ]))
        except:
            await update.callback_query.message.reply_text(
                "❌ Оформление заказа отменено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("В главное меню", callback_data="main_menu")]
                ]))
    else:
        await update.message.reply_text("❌ Оформление заказа отменено.")

    if hasattr(context, 'user_data'):
        context.user_data.clear()

    return ConversationHandler.END


async def clear_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_obj = await get_user_by_telegram_username(user.username)

    if user_obj:
        cart, created = await get_or_create_cart(user_obj)
        await clear_cart(cart)
        await query.answer("🛒 Корзина очищена!")
        await view_cart(update, context)


async def change_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, item_id = query.data.split('_')
    item = await update_cart_item_quantity_db(item_id, action)

    if item:
        await view_cart(update, context)
    else:
        await query.answer("⚠️ Ошибка обновления количества")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    if settings.DEBUG:
        developer_chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
        await context.bot.send_message(
            chat_id=developer_chat_id,
            text=f"Произошла ошибка:\n\n{context.error}")


def main() -> None:
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("help", help_command))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order, pattern='^checkout$')],
        states={
            ORDER_ADDRESS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    process_address
                )
            ],
            ORDER_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    process_date
                )
            ],
            ORDER_TIME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    process_time
                )
            ],
            ORDER_PHONE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    process_phone
                )
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_order_creation, pattern='^cancel_order$'),
            CommandHandler('cancel', cancel_order_creation)
        ],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(catalog, pattern='^catalog$'))
    application.add_handler(CallbackQueryHandler(show_product, pattern='^product_'))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern='^add_'))
    application.add_handler(CallbackQueryHandler(view_cart, pattern='^view_cart$'))
    application.add_handler(CallbackQueryHandler(list_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(clear_cart_handler, pattern='^clear_cart$'))
    application.add_handler(CallbackQueryHandler(change_quantity, pattern='^(increase|decrease)_'))
    application.add_handler(CallbackQueryHandler(start, pattern='^main_menu$'))
    application.add_error_handler(error_handler)

    application.run_polling()


if __name__ == '__main__':
    main()