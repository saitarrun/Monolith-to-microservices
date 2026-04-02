import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics for Strangler Fig validation
const monolithErrorRate = new Rate('monolith_errors');
const microserviceErrorRate = new Rate('microservice_errors');
const dualWriteLatency = new Trend('dual_write_latency');

export const options = {
    stages: [
        { duration: '30s', target: 20 },  // Ramp up
        { duration: '1m', target: 20 },   // Stay at 20 users
        { duration: '30s', target: 0 },   // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<2000'],        // 95th percentile < 2s
        monolith_errors: ['rate<0.05'],            // Monolith error rate < 5%
        microservice_errors: ['rate<0.05'],        // Microservice error rate < 5%
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://demo.local';

export default function () {
    // -------------------------------------------------------
    // Group 1: Monolith v1 – Create Order (writes to DB + Kafka)
    // -------------------------------------------------------
    group('Monolith V1 – Create Order', () => {
        const orderPayload = JSON.stringify({
            user_id: Math.floor(Math.random() * 100) + 1,
            product_id: `prod-${Math.floor(Math.random() * 1000)}`,
            amount: parseFloat((Math.random() * 500 + 10).toFixed(2)),
        });

        const params = {
            headers: { 'Content-Type': 'application/json' },
        };

        const res = http.post(`${BASE_URL}/api/v1/orders/`, orderPayload, params);

        const success = check(res, {
            'v1 create order status 201': (r) => r.status === 201,
        });
        monolithErrorRate.add(!success);
    });

    // Give Kafka time to propagate the dual-write
    sleep(1);

    // -------------------------------------------------------
    // Group 2: Orders Microservice v2 – Read Orders
    // -------------------------------------------------------
    group('Microservice V2 – Read Orders', () => {
        const res = http.get(`${BASE_URL}/api/v2/orders/`);

        const success = check(res, {
            'v2 orders status 200': (r) => r.status === 200,
            'v2 returns orders': (r) => {
                try {
                    return r.json().length > 0;
                } catch (e) {
                    return false;
                }
            },
        });
        microserviceErrorRate.add(!success);
    });

    // -------------------------------------------------------
    // Group 3: User Microservice – CRUD Operations
    // -------------------------------------------------------
    group('User Service – Create User', () => {
        const email = `user-${Date.now()}-${Math.random().toString(36).substr(2, 5)}@test.com`;
        const userPayload = JSON.stringify({
            email: email,
            name: `Test User ${Math.floor(Math.random() * 10000)}`,
        });

        const params = {
            headers: { 'Content-Type': 'application/json' },
        };

        const startTime = Date.now();
        const res = http.post(`${BASE_URL}/api/users/`, userPayload, params);
        dualWriteLatency.add(Date.now() - startTime);

        const success = check(res, {
            'user create status 201': (r) => r.status === 201,
            'user has id': (r) => {
                try {
                    return r.json().id !== undefined;
                } catch (e) {
                    return false;
                }
            },
        });
        microserviceErrorRate.add(!success);

        // Read back the created user
        if (res.status === 201) {
            const userId = res.json().id;
            const getRes = http.get(`${BASE_URL}/api/users/${userId}`);
            check(getRes, {
                'user get status 200': (r) => r.status === 200,
                'user data matches': (r) => {
                    try {
                        return r.json().email === email;
                    } catch (e) {
                        return false;
                    }
                },
            });
        }
    });

    group('User Service – List Users', () => {
        const res = http.get(`${BASE_URL}/api/users/?page=1&per_page=10`);

        check(res, {
            'users list status 200': (r) => r.status === 200,
            'users list has pagination': (r) => {
                try {
                    return r.json().pagination !== undefined;
                } catch (e) {
                    return false;
                }
            },
        });
    });

    // -------------------------------------------------------
    // Group 4: Health Checks
    // -------------------------------------------------------
    group('Health Checks', () => {
        const monolithHealth = http.get(`${BASE_URL}/health/`);
        check(monolithHealth, {
            'monolith healthy': (r) => r.status === 200,
        });

        const userSvcHealth = http.get(`${BASE_URL}/api/users/../health`);
        // Health endpoint may not be routed through Istio gateway
        // This is mostly for direct service verification
    });

    sleep(1);
}
