import json
import os
import logging
import time
from confluent_kafka import Consumer, Producer, KafkaException
from database import SessionLocal
from models import Order, IdempotentEvent

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_GROUP_ID = os.environ.get('KAFKA_GROUP_ID', 'orders-svc-group')
DLQ_TOPIC = 'orders.dlq'

dlq_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

def run_consumer():
    """Consumes order events and stores them in the microservice DB."""
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': KAFKA_GROUP_ID,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False # Manual offset committing for safety
    }

    consumer = Consumer(conf)
    consumer.subscribe(['orders.created'])

    logger.info("Starting Kafka Consumer with Idempotency and DLQ...")

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
                event_id = data.get('event_id', str(data.get('id', 'unknown')))
                logger.info(f"Received order event_id: {event_id}")
                
                # Setup retries for transient DB failures
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        db = SessionLocal()
                        
                        # Idempotency Check
                        existing = db.query(IdempotentEvent).filter(IdempotentEvent.event_id == event_id).first()
                        if existing:
                            logger.info(f"Duplicate event {event_id} ignored.")
                            db.close()
                            break # Break retry loop, successfully ignored
                            
                        # Transaction: Save Event and Order
                        order = Order(
                            original_id=data['id'],
                            user_id=data['user_id'],
                            product_id=data['product_id'],
                            amount=data['amount'],
                            status=data['status'],
                        )
                        db.add(order)
                        db.add(IdempotentEvent(event_id=event_id))
                        db.commit()
                        logger.info(f"Order {data['id']} saved idempotently.")
                        db.close()
                        break # Success
                        
                    except Exception as e:
                        db.rollback()
                        db.close()
                        logger.warning(f"Attempt {attempt+1} failed: {e}")
                        if attempt == max_retries - 1:
                            raise e # bubble up to DLQ logic
                        time.sleep(2 ** attempt) # Exponential backoff
                        
                # Commit offset only after successful processing or successful ignore
                consumer.commit(asynchronous=False)

            except Exception as e:
                logger.error(f"Failed processing message {msg.value()}: {e}")
                # Send to Dead Letter Queue (DLQ)
                logger.info("Publishing to DLQ...")
                dlq_producer.produce(DLQ_TOPIC, key=msg.key(), value=msg.value())
                dlq_producer.flush()
                # Commit offset because the message is safely in the DLQ
                consumer.commit(asynchronous=False)

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
