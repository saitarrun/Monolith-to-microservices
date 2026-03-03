from rest_framework import generics
from .models import Order
from .serializers import OrderSerializer
from .kafka import producer

class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def perform_create(self, serializer):
        order = serializer.save()
        
        # Consistent dual-write (simulated transaction)
        import uuid
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
        
        # Publish to Kafka
        producer.publish_message('orders.created', order.id, event_data)
        producer.flush() # Ensure delivery for demo purposes
