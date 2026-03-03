import json
import logging
from django.conf import settings
from confluent_kafka import Producer

logger = logging.getLogger(__name__)

class KafkaProducer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KafkaProducer, cls).__new__(cls)
            conf = {
                'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
                'client.id': 'monolith-producer'
            }
            cls._instance.producer = Producer(conf)
        return cls._instance

    def publish_message(self, topic, key, value):
        try:
            self.producer.produce(
                topic,
                key=str(key),
                value=json.dumps(value),
                callback=self.delivery_report
            )
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")

    def delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def flush(self):
        self.producer.flush()

producer = KafkaProducer()
