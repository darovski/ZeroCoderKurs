from django.shortcuts import render
from django.contrib import admin

from .models import SiteSettings, Product

def some_view(request):
    settings = SiteSettings.load()
    context = {
        'phone': settings.company_phone,
        'delivery_price': settings.delivery_price
    }
    return render(request, 'template.html', context)

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'site_name',
        'company_phone',
        'delivery_price',
        'min_order_price',
        'stripe_public_key',
        'stripe_secret_key'
    ]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'category')
    list_display_links = ('name', 'price')
    list_editable = ('category',)
    list_filter = ('category',)
    ordering = ('category', 'name')