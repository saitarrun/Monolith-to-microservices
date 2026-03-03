# Monolith to Microservices Demo

![CI/CD Pipeline](https://github.com/monolith-microservices-demo/actions/workflows/ci-cd.yaml/badge.svg)
![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)
![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)

This project demonstrates a zero-downtime migration from a Django Monolith to Microservices (FastAPI, Node.js) on AWS EKS.

Please refer to the [Contributing Guide](CONTRIBUTING.md) for information on setting up your local environment and pushing code.

## Key Engineering Outcomes (FAANG-Level Signals)

FAANG companies look for projects that demonstrate measurable validation, reliability, and correctness mechanisms. This project demonstrates these principles through:
- **Zero-Downtime Migration**: Utilizes a strangler fig networking pattern via Kubernetes Ingress to safely transition traffic from the V1 Django monolith to V2 Microservices, supporting immediate rollback.
- **Event-Driven Correctness**: Leverages Kafka for reliable dual-writes and data replication, ensuring eventual consistency between decoupled databases.
- **Measured Validation**: Incorporates `k6` load testing to simulate high-concurrency traffic (concurrent VUs) and validate response stability and 200/201 status correctness under sustained load.

## Architecture

- **Infrastructure**: AWS (EKS, RDS, MSK, ElastiCache) provisioning via Terraform.
- **Monolith**: Django application (v1 API).
- **Orders Service**: FastAPI application (v2 API).
- **Notifications Service**: Node.js application (Kafka Consumer).
- **Orchestration**: Kubernetes with Helm.

## Prerequisites

- Terraform >= 1.0
- Kotlin/Helm
- AWS CLI configured
- Python 3.11+ (for local dev)
- Node.js 18+ (for local dev)

## Deployment Steps

1. **Infrastructure**:
   ```bash
   cd infra/terraform
   terraform init
   terraform apply
   ```

2. **Kubernetes**:
   Update `infra/k8s/values.yaml` with the endpoints from Terraform outputs.
   ```bash
   helm install demo infra/k8s
   ```

3. **Migration Flow (Zero Downtime)**:
   - Initial State: Traffic to Monolith (`/`).
   - Dual Write: Monolith writes to DB + Kafka.
   - Deploy Microservices: Orders Service consumes Kafka events.
   - Strangler Pattern: Ingress routes `/api/v2/orders` to Microservice.
   - Verification: Run K6 tests to ensure consistency.
   - Cutover: Gradually shift traffic or deprecate v1.

## Testing

Run K6 load tests:
```bash
k6 run tests/k6/load-test.js
```
