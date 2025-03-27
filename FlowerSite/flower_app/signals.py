from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser

@receiver(post_save, sender=CustomUser)
def user_registered(sender, instance, created, **kwargs):
    if created:
        # 1. Отправка welcome email
        # 2. Создание профиля
        # 3. Логирование события
        # 4. Инициализация корзины
        pass