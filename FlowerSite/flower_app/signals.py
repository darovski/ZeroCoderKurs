from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps

def register_signals():
    Order = apps.get_model('flower_app', 'Order')
    CustomUser = apps.get_model('flower_app', 'CustomUser')

    @receiver(post_save, sender=Order)
    def order_status_changed(sender, instance, **kwargs):
        # Проверяем, что kwargs не None и содержит 'update_fields'
        if kwargs is not None and 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            if 'status' in kwargs['update_fields']:
                from ..newbot import update_order_status
                update_order_status(instance.id, instance.status)

    @receiver(post_save, sender=CustomUser)
    def notify_user_created(sender, instance, created, **kwargs):
        if created and instance.telegram_id:
            from ..newbot import send_telegram_notification
            send_telegram_notification(
                instance.telegram_id,
                "✅ Ваш аккаунт успешно привязан к боту!"
            )

# Явный вызов регистрации сигналов
register_signals()