from django.shortcuts import render
from django.contrib import admin

from .models import SiteSettings, Product, ProductBouquet, ProductGorshok

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
        'min_order_price'
    ]

class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['stripe_public_key', 'stripe_secret_key']

#admin.site.register(SiteSettings, SiteSettingsAdmin)

admin.site.register(Product)
admin.site.register(ProductBouquet)
admin.site.register(ProductGorshok)