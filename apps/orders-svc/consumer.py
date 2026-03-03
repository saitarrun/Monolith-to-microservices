import json
import os
import logging
from confluent_kafka import Consumer, KafkaException
from database import SessionLocal
from models import Order

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_GROUP_ID = os.environ.get('KAFKA_GROUP_ID', 'orders-svc-group')

def run_consumer():
    """Consumes order events and stores them in the microservice DB."""
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': KAFKA_GROUP_ID,
        'auto.offset.reset': 'earliest'
    }

    consumer = Consumer(conf)
    consumer.subscribe(['orders.created'])

    logger.info("Starting Kafka Consumer...")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue
                else:
                    logger.error(msg.error())
                    break

            try:
                data = json.loads(msg.value().decode('utf-8'))
                logger.info(f"Received order: {data}")
                
                db = SessionLocal()
                order = Order(
                    original_id=data['id'], # From Monolith
                    user_id=data['user_id'],
                    product_id=data['product_id'],
                    amount=data['amount'],
                    status=data['status'],
                    # created_at handled by default or parsed
                )
                db.add(order)
                db.commit()
                db.close()
                logger.info(f"Order {data['id']} saved to microservice DB")

            except Exception as e:
                logger.error(f"Error processing message: {e}")

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
