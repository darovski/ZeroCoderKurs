import requests
import os
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from telegram import User

from .models import Product, ProductBouquet, ProductGorshok, SiteSettings, Favorite
from .models import Cart, CartItem, Order, OrderItem
from django.shortcuts import render, redirect, get_object_or_404
from .forms import OrderForm, UserEditForm, CartAddProductForm
from allauth.account.views import SignupView, login
from .forms import CustomSignupForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'flower_app/product_detail.html', {'product': product})

def favorite_remove(request, product_id):
    if request.user.is_authenticated:
        favorite = get_object_or_404(Favorite, user=request.user, product_id=product_id)
        favorite.delete()
    return redirect('flower_app:favorites')

def product_list(request):
    products = Product.objects.all()
    return render(request, 'flower_app/product_list.html', {'products': products})

def telegram_auth(request):
    auth_data = request.GET
    user, created = User.objects.get_or_create(
        telegram_id=auth_data['id'],
        defaults={
            'username': auth_data['username'],
            'first_name': auth_data.get('first_name', ''),
            'last_name': auth_data.get('last_name', '')
        }
    )
    login(request, user)
    return redirect('home')

@csrf_exempt
def telegram_webhook(request):
    if request.method == 'POST':
        update = json.loads(request.body)
        # Обработка update
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'})

@login_required
def favorite_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, product=product)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'added' if created else 'already_exists'})

    return redirect(request.META.get('HTTP_REFERER', 'flower_app:product_list'))


@login_required
def favorite_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Favorite.objects.filter(user=request.user, product=product).delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'removed'})

    return redirect(request.META.get('HTTP_REFERER', 'flower_app:product_list'))

class BotInfoView(TemplateView):
    template_name = 'bot_info.html'

@login_required
def favorite_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    return render(request, 'flower_app/favorites.html', {'favorites': favorites})

class CustomSignupView(SignupView):
    form_class = CustomSignupForm
    template_name = 'signup.html'

def form_valid(self, form):
    # Дополнительная логика перед сохранением
    response = super().form_valid(form)

    # # Пример: отправка приветственного письма
    # user = self.user
    # user.send_welcome_email()  # Ваш метод модели

    return response

def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_settings'] = SiteSettings.load()
        return context

def index(request):
    user = getattr(request, 'user', None)  # Безопасное получение пользователя
    context = {
        'user': user,
    }
    return render(request, 'flower_app/index.html')

def catalog_flowers(request):
    products = Product.objects.all()
    return render(request, 'flower_app/catalog_flowers.html', {'products': products})

def catalog_bouquets(request):
    products = ProductBouquet.objects.all()
    return render(request, 'flower_app/catalog_flowers.html', {'products': products})

def catalog_gorshok(request):
    products = ProductGorshok.objects.all()
    return render(request, 'flower_app/catalog_gorshok.html', {'products': products})

def catalog_action(request):
    user = getattr(request, 'user', None)
    context = {
        'user': user,
    }
    return render(request, 'flower_app/action.html')



def signup(request):
#    products = ProductBouquet.objects.all()
    return render(request, 'flower_app/signup.html')

def account_login(request):
#    products = ProductBouquet.objects.all()
    return render(request, 'flower_app/account_login.html')

def account_logout(request):
#    products = ProductBouquet.objects.all()
    return render(request, 'flower_app/account_logout.html')


@login_required
def account_edit(request):
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('flower_app:profile')
    else:
        form = UserEditForm(instance=request.user)

    return render(request, 'flower_app/account_edit.html', {'form': form})

def account_reset_password(request):
#    products = ProductBouquet.objects.all()
    return render(request, 'flower_app/account_reset_password.html')

@login_required(login_url='account_login')
def profile_view(request):
    # template_name = 'flower_app/profile.html'
    # login_url = 'account_login/'
     orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
     return render(request, 'flower_app/profile.html', {'orders': orders})

#@login_required
def create_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.save()
            form.save_m2m()
            send_telegram_notification(order)
            return redirect('order_success', order_id=order.id)
    else:
        form = OrderForm()
    return render(request, 'order.html', {'form': form})

def send_telegram_notification(order):
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    message = f"Новый заказ №{order.id}!\nКлиент: {order.customer_name}"
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        params={'chat_id': chat_id, 'text': message}
    )


@login_required
def cart_detail(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    return render(request, 'flower_app/detail.html', {'cart': cart})


@login_required
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('flower_app:detail')


@login_required
def cart_remove(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)
    product = get_object_or_404(Product, id=product_id)
    cart_item = get_object_or_404(CartItem, cart=cart, product=product)
    cart_item.delete()
    return redirect('flower_app:detail')


@login_required
def cart_update(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)
    product = get_object_or_404(Product, id=product_id)
    cart_item = get_object_or_404(CartItem, cart=cart, product=product)

    if request.method == 'POST':
        form = CartAddProductForm(request.POST, instance=cart_item)
        if form.is_valid():
            form.save()

    return redirect('flower_app:detail')


def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Проверка, что заказ принадлежит текущему пользователю
    if order.user != request.user:
        return redirect('flower_app:product_list')

    context = {
        'order': order,
        'order_items': order.items.all(),
        'total_cost': order.get_total_cost(),
    }

    return render(request, 'flower_app/detail.html', context)


@login_required
def order_create(request):
    cart = get_object_or_404(Cart, user=request.user)

    if request.method == 'POST':
        order = Order.objects.create(user=request.user)

        # Переносим товары из корзины в заказ
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                price=cart_item.product.price,
                quantity=cart_item.quantity
            )

        # Очищаем корзину
        cart.items.all().delete()

        return redirect('flower_app:order_detail', order_id=order.id)

    return render(request, 'flower_app/order_create.html', {'cart': cart})