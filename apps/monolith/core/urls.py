from django.urls import path
from .views import OrderListCreateView, CreatePaymentIntentView, StripeWebhookView

urlpatterns = [
    path('orders/', OrderListCreateView.as_view(), name='order-list-create'),
    path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
    path('stripe-webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
]
