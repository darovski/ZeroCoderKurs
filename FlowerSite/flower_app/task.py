from celery import shared_task
from .models import Order

@shared_task
def send_client_notification(order_id):
    order = Order.objects.get(id=order_id)
    # Отправка уведомления клиенту через Telegram/SMS/Email