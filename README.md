# Monolith to Microservices Demo – Strangler Fig Pattern

![CI/CD Pipeline](https://github.com/monolith-microservices-demo/actions/workflows/ci-cd.yaml/badge.svg)
![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)
![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)
![Strangler Fig](https://img.shields.io/badge/pattern-strangler%20fig-blue)

This project demonstrates a **zero-downtime migration from a Django Monolith to Microservices** using the **Strangler Fig Pattern** on **AWS EKS** with **Istio** service mesh for progressive traffic routing.

## Architecture

```
┌─────────┐     ┌──────────────────────────────────────┐
│  Client  │────▶│  Istio Ingress Gateway               │
└─────────┘     │                                      │
                │  ┌─────────────────────────────────┐ │
                │  │  VirtualService (Routing Rules)  │ │
                │  └──────┬──────────┬───────────┬────┘ │
                │         │          │           │      │
                │     /api/users  /api/v2/orders  /*    │
                │         │          │           │      │
                │    ┌────▼───┐ ┌────▼────┐ ┌────▼───┐ │
                │    │User Svc│ │Order Svc│ │Monolith│ │
                │    │(Flask) │ │(FastAPI)│ │(Django)│ │
                │    └────┬───┘ └────┬────┘ └───┬────┘ │
                │         │          │          │      │
                │    ┌────▼──────────▼──────────▼───┐  │
                │    │        PostgreSQL (RDS)       │  │
                │    └──────────────────────────────┘  │
                │    ┌──────────────────────────────┐  │
                │    │     Kafka (MSK) → Events     │  │
                │    │          ↓                    │  │
                │    │   Notifications Svc (Node)   │  │
                │    └──────────────────────────────┘  │
                └──────────────────────────────────────┘
                          AWS EKS Cluster
```

### Key Components

| Component | Technology | Role |
|-----------|-----------|------|
| **Monolith** | Django 4.2 + DRF | Legacy application (v1 API) |
| **Orders Service** | FastAPI | Extracted order management (v2 API) |
| **User Service** | Flask | Extracted user management (Strangler Fig Phase 3) |
| **Notifications** | Node.js + Express | Event-driven email notifications (Kafka consumer) |
| **Storefront** | React (Vite) + Nginx | Frontend SPA |
| **Service Mesh** | Istio | Traffic routing, canary releases, observability |
| **Infrastructure** | AWS EKS, RDS, MSK, ElastiCache | Managed Kubernetes + data layer |

## Key Engineering Outcomes

- **Strangler Fig Pattern**: Istio VirtualService-based progressive traffic routing from monolith to microservices, supporting canary releases (10% → 50% → 100%)
- **Zero-Downtime Migration**: Side-by-side deployment with instant rollback capability
- **Event-Driven Correctness**: Kafka dual-writes ensure eventual consistency between monolith and microservice databases
- **Dual-Write Data Sync**: HTTP + direct DB fallback dual-write pattern keeping data consistent during transition
- **Circuit Breaking**: Istio DestinationRules with outlier detection prevent cascading failures
- **Measured Validation**: K6 load testing with custom canary validation metrics

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0
- kubectl + Helm
- Istio CLI (`istioctl`)
- Python 3.11+ (for local dev)
- Node.js 18+ (for local dev)
- Docker & Docker Compose (for local dev)

## Quick Start (Local Development)

```bash
# Start all services locally
docker-compose up --build

# Services:
#   Monolith:       http://localhost:8000
#   Orders Service: http://localhost:8001
#   User Service:   http://localhost:8002
#   Storefront:     http://localhost:80
#   Grafana:        http://localhost:3000
```

## Deployment (AWS EKS + Istio)

### 1. Provision Infrastructure
```bash
cd infra/terraform
terraform init
terraform apply
```

### 2. Full Deploy (Infra + Istio + App)
```bash
./deploy_eks_istio.sh
```

### 3. Strangler Fig Migration Flow

| Phase | Description | Command |
|-------|-------------|---------|
| **1** | All traffic → Monolith | `kubectl apply -f infra/istio/virtual-service-phase1.yaml` |
| **2** | Install Istio + Gateway | `bash infra/istio/install-istio.sh` |
| **3** | Deploy User Service | `helm upgrade --install demo infra/k8s` |
| **4** | Route users → User Svc | `kubectl apply -f infra/istio/virtual-service-phase4.yaml` |
| **5** | Canary (10→50→100%) | `bash infra/k8s/scripts/istio_canary_rollout.sh` |
| **6** | Enable dual-writes | Set `DUAL_WRITE_ENABLED=true` in monolith |
| **7** | Final routing state | `kubectl apply -f infra/istio/virtual-service-final.yaml` |

### Rollback (Instant)
```bash
# Route all traffic back to monolith
kubectl apply -f infra/istio/virtual-service-phase1.yaml
```

## Testing

```bash
# K6 load tests (full suite)
k6 run tests/k6/load-test.js

# Canary validation (verify traffic split)
k6 run tests/k6/canary-validation.js --env EXPECTED_WEIGHT=50
```

## Migration Status

See [migration-status.yaml](migration-status.yaml) for current progress.

## Documentation

See [docs/strangler-fig-migration.md](docs/strangler-fig-migration.md) for the complete migration guide.

## Contributing

Please refer to the [Contributing Guide](CONTRIBUTING.md) for information on setting up your local environment and pushing code.
