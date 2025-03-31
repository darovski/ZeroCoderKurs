from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import (
    index,
    account_login,
    account_edit,
    account_logout,
    account_reset_password,
    cart_detail,
    cart_add,
    cart_remove,
    cart_update,
    order_create,
    order_detail,
    signup,
    catalog_flowers,
    catalog_action,
    CustomSignupView,
    profile_view,
    favorite_remove,
    favorite_add,
    favorite_list,
    product_detail,
    product_list,
    BotInfoView,
    telegram_webhook,
    telegram_auth,


#    create_order,
#    checkout,
#     cart_view,
#     order_success,
#    order_history,
#    order_detail,
#    CustomLoginView,
#    CustomLogoutView,
#    SignUpView,
#    update_cart
 )

app_name = 'flower_app'

urlpatterns = [
    path('', index, name='index'),
    path('account/login/', auth_views.LoginView.as_view(template_name='account_login.html'), name='login'),
    path('catalog_flowers/', catalog_flowers, name='catalog_flowers'),
    path('account_login/', account_login, name='account_login'),
    path('account_edit/', account_edit, name='account_edit'),
    path('account_logout,/', account_logout, name='account_logout,'),
    path('profile/', profile_view, name='profile'),
    path('account/', include('allauth.urls')),
    path('account_reset_password/', account_reset_password, name='account_reset_password'),
    path('signup/', CustomSignupView.as_view(), name="account_signup"),
    path('detail', cart_detail, name='detail'),
    path('add/<int:product_id>/', cart_add, name='add'),
    path('remove/<int:product_id>/', cart_remove, name='remove'),
    path('update/<int:product_id>/', cart_update, name='update'),
#    path('favorites/add/<int:product_id>/', favorite_add, name='favorite_add'),
    path('favorites/', favorite_list, name='favorite_list'),
    path('favorites/add/<int:product_id>/', favorite_add, name='favorite_add'),
    path('favorites/remove/<int:product_id>/', favorite_remove, name='favorite_remove'),
    path('orders/<int:order_id>/', order_detail, name='order_detail'),
#    path('order_create<int:order_id>/', order_create, name='order_create'),
    path('products/<int:pk>/', product_detail, name='product-detail'),
    path('favorites/remove/<int:product_id>/', favorite_remove, name='favorite-remove'),
    path('products/', product_list, name='product-list'),
    path('fresh-flowers/', product_list, {'category': 'product'}, name='fresh_flowers'),
    path('bouquets/', product_list, {'category': 'bouquet'}, name='bouquets'),
    path('potted-plants/', product_list, {'category': 'gorshok'}, name='potted_plants'),
    path('orders/create/', order_create, name='order_create'),
    path('orders/<int:order_id>/', order_detail, name='order_detail'),
    path('catalog_action/', catalog_action, name='catalog_action'),
    path('webhook/', telegram_webhook, name='telegram-webhook'),
    path('telegram-bot/', BotInfoView.as_view(), name='bot-info'),
    path('auth/telegram/', telegram_auth, name='telegram-auth'),

#    path('account/', include('allauth.urls'))

#      # Корзина и заказы
#      path('cart/', cart_view, name='cart'),
#      path('cart/update/', update_cart, name='update_cart'),
#
#      # Процесс оформления заказа
#      path('order/create/', create_order, name='create_order'),
#      path('order/success/<int:order_id>/', order_success, name='order_success'),
#
# #     # Оплата
# #     path('checkout/<int:order_id>/', checkout, name='checkout'),
#
#      # История заказов
#      path('orders/', order_history, name='order_list'),
#      path('orders/<int:pk>/', order_detail, name='order_detail'),
#
#      # Аутентификация
#       path('login/', CustomLoginView.as_view(), name='login'),
#       path('logout/', CustomLogoutView.as_view(), name='logout'),
#       path('signup/', SignUpView.as_view(), name='signup'),
]