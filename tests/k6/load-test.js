import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    stages: [
        { duration: '30s', target: 20 }, // Ramp up
        { duration: '1m', target: 20 },  // Stay at 20 users
        { duration: '30s', target: 0 },  // Ramp down
    ],
};

const BASE_URL = 'http://demo.local'; // Ingress host

export default function () {
    // Test Monolith Create Order
    const payload = JSON.stringify({
        user_id: 1,
        product_id: 'prod-123',
        amount: 99.99
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const res = http.post(`${BASE_URL}/api/v1/orders/`, payload, params);

    check(res, {
        'is status 201': (r) => r.status === 201,
    });

    // Test Microservice Read Order (Verify Dual Write/Replication)
    // Give some time for Kafka to propagate
    sleep(1);

    const res2 = http.get(`${BASE_URL}/api/v2/orders/`);
    check(res2, {
        'is status 200': (r) => r.status === 200,
        'ms returns orders': (r) => r.json().length > 0
    });

    sleep(1);
}
