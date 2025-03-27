import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_payment_intent(order):
    amount = int(order.total_amount * 100)  # в копейках/центах
    return stripe.PaymentIntent.create(
        amount=amount,
        currency='rub',
        metadata={'order_id': order.id}
    )