from .models import Favorite

def favorites(request):
    if request.user.is_authenticated:
        return {
            'user_favorites': Favorite.objects.filter(user=request.user).values_list('product_id', flat=True)
        }
    return {}