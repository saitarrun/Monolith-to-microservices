import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// =============================================================================
// Canary Validation Test – Strangler Fig Phase 5
// =============================================================================
// This test validates that the canary traffic split is working correctly.
// It sends a burst of requests and verifies that the expected percentage
// of requests are being served by the new microservice vs the monolith.
//
// Usage:
//   k6 run tests/k6/canary-validation.js --env EXPECTED_WEIGHT=10
// =============================================================================

const monolithResponses = new Rate('monolith_responses');
const microserviceResponses = new Rate('microservice_responses');

export const options = {
    vus: 10,
    iterations: 200,  // Enough samples for statistical significance
    thresholds: {
        http_req_duration: ['p(99)<5000'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://demo.local';
const EXPECTED_WEIGHT = parseInt(__ENV.EXPECTED_WEIGHT || '100', 10);

export default function () {
    // -------------------------------------------------------
    // Send a request to /api/users and check which service responds
    // -------------------------------------------------------
    const res = http.get(`${BASE_URL}/api/users/?page=1&per_page=1`);

    check(res, {
        'status is 200': (r) => r.status === 200,
    });

    // Detect which service handled the request using response headers or body
    // The user-svc returns { users: [...], pagination: {...} }
    // The monolith returns a DRF-style response
    try {
        const body = res.json();

        if (body.pagination !== undefined) {
            // User microservice response format
            microserviceResponses.add(1);
            monolithResponses.add(0);
        } else {
            // Monolith response format (DRF)
            monolithResponses.add(1);
            microserviceResponses.add(0);
        }
    } catch (e) {
        // If we can't parse, count as unknown
        monolithResponses.add(0);
        microserviceResponses.add(0);
    }

    sleep(0.1);
}

export function handleSummary(data) {
    const msRate = data.metrics.microservice_responses
        ? data.metrics.microservice_responses.values.rate * 100
        : 0;
    const monolithRate = data.metrics.monolith_responses
        ? data.metrics.monolith_responses.values.rate * 100
        : 0;

    const tolerance = 10; // Allow 10% tolerance
    const msExpected = EXPECTED_WEIGHT;
    const monolithExpected = 100 - EXPECTED_WEIGHT;

    const msOk = Math.abs(msRate - msExpected) <= tolerance;
    const monolithOk = Math.abs(monolithRate - monolithExpected) <= tolerance;

    console.log('\n=== Canary Validation Results ===');
    console.log(`Expected split: ${msExpected}% microservice / ${monolithExpected}% monolith`);
    console.log(`Actual split:   ${msRate.toFixed(1)}% microservice / ${monolithRate.toFixed(1)}% monolith`);
    console.log(`Tolerance:      ±${tolerance}%`);
    console.log(`Result:         ${msOk && monolithOk ? '✅ PASS' : '❌ FAIL'}`);
    console.log('================================\n');

    return {};
}
