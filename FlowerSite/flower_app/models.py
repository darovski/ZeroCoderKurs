from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.shortcuts import render

# Определяем константы в начале файла
STATUS_CHOICES = [
    ('pending', 'В обработке'),
    ('processing', 'В процессе'),
    ('completed', 'Завершен'),
    ('cancelled', 'Отменен'),
]


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ('user', 'product')  # Один товар - один раз у пользователя
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранные товары'

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class CustomUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    telegram_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    telegram_username = models.CharField(max_length=100, blank=True)
    delivery_address = models.TextField(blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

class Profile(models.Model):
    user = models.OneToOneField(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='profile'
    )

    def __str__(self):
        return f"{self.telegram_username or self.telegram_id}"

class SiteSettings(models.Model):
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj
    # Основные настройки
    site_name = models.CharField("Название сайта", max_length=100, default='Flower Delivery')
    company_phone = models.CharField("Телефон компании", max_length=20)
    company_email = models.EmailField("Email компании")

    # Соцсети
    instagram_url = models.URLField("Instagram", blank=True)
    vk_url = models.URLField("VK", blank=True)
    telegram_url = models.URLField("Telegram", blank=True)

    # Платежные системы
    stripe_public_key = models.CharField("Stripe Public Key", max_length=100, blank=True)
    stripe_secret_key = models.CharField("Stripe Secret Key", max_length=100, blank=True)

    # Настройки по умолчанию
    delivery_price = models.DecimalField("Стоимость доставки", max_digits=8, decimal_places=2, default=0)
    min_order_price = models.DecimalField("Минимальный заказ", max_digits=8, decimal_places=2, default=0)

class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('product', 'Свежие цветы'),
        ('bouquet', 'Букеты'),
        ('gorshok', 'Комнатные цветы'),
    ]

    category = models.CharField(
        max_length=10,
        choices=CATEGORY_CHOICES,
        default='product'
    )

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField()
    image = models.ImageField(upload_to='products/')

class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Корзина {self.user.username}'

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.quantity} x {self.product.name}'

    def total_price(self):
        return self.product.price * self.quantity

@login_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    return render(request, 'cart.html', {'cart': cart})

def __str__(self):
    return self.site_name

def save(self, *args, **kwargs):
    # Гарантируем, что будет только один экземпляр
    self.id = 1
    super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey('Order', related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    def get_cost(self):
        return self.price * self.quantity

    class Meta:
        verbose_name = 'Элемент заказа'
        verbose_name_plural = 'Элементы заказа'


User = get_user_model()


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('processing', 'В обработке'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменен'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='orders')
    customer_name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    products = models.ManyToManyField('Product')  # Assuming Product is defined elsewhere
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=100, blank=True)
    is_paid = models.BooleanField(default=False)
    delivery_address = models.TextField(default='Не указан')
    delivery_date = models.DateField(null=True, blank=True)
    delivery_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"Заказ #{self.id} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Для корректной работы сигналов при обновлении
        if self.pk:
            from django.db.models import F
            kwargs['update_fields'] = kwargs.get('update_fields', set()) | {'status'}
        super().save(*args, **kwargs)

    def get_total_cost(self):
        return sum(item.get_cost() for item in self.products.all())

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'