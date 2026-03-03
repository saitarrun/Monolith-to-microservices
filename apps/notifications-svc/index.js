const express = require('express');
const { Kafka } = require('kafkajs');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

const kafka = new Kafka({
    clientId: 'notifications-svc',
    brokers: (process.env.KAFKA_BOOTSTRAP_SERVERS || 'localhost:9092').split(',')
});

const consumer = kafka.consumer({ groupId: 'notifications-group' });

const run = async () => {
    await consumer.connect();
    await consumer.subscribe({ topic: 'orders.created', fromBeginning: true });

    await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
            const order = JSON.parse(message.value.toString());
            console.log(`[Notification] Sending email for Order ID: ${order.id}`);
            // Simulate email sending
        },
    });
};

run().catch(console.error);

app.get('/health', (req, res) => {
    res.json({ status: 'healthy' });
});

app.listen(port, () => {
    console.log(`Notification service listening at http://localhost:${port}`);
});
