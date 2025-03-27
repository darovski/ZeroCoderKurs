# middleware.py
from django.utils.functional import SimpleLazyObject
from .models import Cart


def get_cart(request):
    if not hasattr(request, '_cached_cart'):
        if request.user.is_authenticated:
            request._cached_cart = Cart.objects.get_or_create(user=request.user)[0]
        else:
            request._cached_cart = None
    return request._cached_cart


class CartMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cart = SimpleLazyObject(lambda: get_cart(request))
        return self.get_response(request)