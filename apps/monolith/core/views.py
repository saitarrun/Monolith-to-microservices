from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Order
from .serializers import OrderSerializer
from .kafka import producer
import stripe
import os
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_placeholder')

class CreatePaymentIntentView(APIView):
    def post(self, request):
        try:
            # In a real app, calculate amount from DB product price
            amount = int(request.data.get('amount', 0) * 100) # Stripe needs cents
            
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='usd',
                metadata={'product_id': request.data.get('product_id'), 'user_id': request.data.get('user_id')}
            )
            return Response({'client_secret': intent.client_secret})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

        try:
            if endpoint_secret:
                event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            else:
                # If no secret configured (local dev), just parse JSON
                event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except ValueError as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Handle the event
        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            
            # 1. Create Order in Monolith DB
            order = Order.objects.create(
                user_id=payment_intent.metadata.get('user_id', 1),
                product_id=payment_intent.metadata.get('product_id', 'unknown'),
                amount=payment_intent.amount / 100.0,
                status='PAID' # Set to PAID immediately since Stripe confirmed
            )
            
            # 2. Dual-Write to Kafka using Saga pattern
            event_id = str(uuid.uuid4())
            event_data = {
                'event_id': event_id,
                'id': order.id,
                'user_id': order.user_id,
                'product_id': order.product_id,
                'amount': float(order.amount),
                'status': order.status,
                'created_at': order.created_at.isoformat()
            }
            producer.publish_message('orders.created', order.id, event_data)
            producer.flush()

        return Response(status=status.HTTP_200_OK)

class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def perform_create(self, serializer):
        # Legacy synchronous flow (optional to keep for backwards compat)
        order = serializer.save()
        event_id = str(uuid.uuid4())
        event_data = {
            'event_id': event_id,
            'id': order.id,
            'user_id': order.user_id,
            'product_id': order.product_id,
            'amount': float(order.amount),
            'status': order.status,
            'created_at': order.created_at.isoformat()
        }
        producer.publish_message('orders.created', order.id, event_data)
        producer.flush()
