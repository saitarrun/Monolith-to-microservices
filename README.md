# How to Use the Strangler Fig Pattern to Migrate Monoliths to Microservices on AWS EKS

> A practical guide to incrementally migrating a monolithic application to microservices on AWS EKS using the Strangler Fig pattern with Istio traffic routing.

---

Rewriting a monolith from scratch almost never works. The big-bang approach is risky, expensive, and often ends in failure. The **Strangler Fig pattern** takes a different approach — inspired by the strangler fig tree, which grows around an existing tree and gradually replaces it. You build new features as microservices, incrementally route traffic from the monolith to the new services, and eventually the monolith withers away.

In this guide, we walk through implementing the Strangler Fig pattern on **AWS EKS**, using **Istio** for traffic routing so we can gradually shift functionality from a monolith to new microservices **without any downtime**.

---

## The Migration Strategy

The key idea is simple: put a routing layer in front of your monolith that can selectively forward requests to new microservices. As you extract functionality from the monolith, you update the routing rules. The monolith and microservices run side by side, and users never notice the transition.

![Strangler Fig Pattern Overview](/Users/saitarrunpitta/.gemini/antigravity/brain/323e2726-ef37-4e04-aa67-924a1f6dde22/strangler_fig_overview_1775088696203.png)

```mermaid
graph TD
    A[Client] --> B[Istio Ingress Gateway]
    B -->|"/api/users/*"| C["User Service (New)"]
    B -->|"/api/v2/orders/*"| D["Orders Service (New)"]
    B -->|"Everything else"| E["Monolith (Legacy)"]
    subgraph AWS EKS Cluster
        C
        D
        E
    end
```

> [!IMPORTANT]
> At **any point** during the migration, you have a fully working system. You can stop, pause, or roll back without any downtime.

---

## Phase 1: Deploy the Monolith to EKS

The first step is containerizing the monolith and deploying it to EKS. This gets you onto the platform where you will eventually run your microservices too.

![Phase 1 – Deploy Monolith to EKS](/Users/saitarrunpitta/.gemini/antigravity/brain/323e2726-ef37-4e04-aa67-924a1f6dde22/phase1_monolith_eks_1775088712285.png)

### Containerize the Monolith

Our Django monolith uses a multi-stage Dockerfile for a small, secure image:

```dockerfile
# apps/monolith/Dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Final
FROM python:3.11-slim
RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*
COPY . .
USER appuser
CMD ["gunicorn", "monolith.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### Add a Health Check Endpoint

Kubernetes needs health endpoints for readiness and liveness probes:

```python
# apps/monolith/monolith/urls.py
from django.http import JsonResponse

def health_check(request):
    """Health check endpoint for Kubernetes readiness/liveness probes."""
    return JsonResponse({"status": "healthy", "service": "monolith"})

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
]
```

### Deploy to EKS with Probes and Resource Limits

```yaml
# infra/k8s/templates/monolith.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: monolith
  labels:
    app: monolith
    version: v1
    strangler-fig/role: legacy
spec:
  replicas: 2
  selector:
    matchLabels:
      app: monolith
  template:
    metadata:
      labels:
        app: monolith
        version: v1
    spec:
      containers:
        - name: monolith
          image: monolith:latest
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
          readinessProbe:
            httpGet:
              path: /health/
              port: 8000
            initialDelaySeconds: 10
          livenessProbe:
            httpGet:
              path: /health/
              port: 8000
            initialDelaySeconds: 15
---
apiVersion: v1
kind: Service
metadata:
  name: monolith
spec:
  selector:
    app: monolith
  ports:
    - port: 80
      targetPort: 8000
```

### Provision AWS Infrastructure

The infrastructure is provisioned via Terraform — EKS cluster, RDS PostgreSQL, MSK Kafka, and ElastiCache Redis:

```bash
cd infra/terraform
terraform init
terraform apply
```

---

## Phase 2: Install Istio Service Mesh

Istio gives you fine-grained control over traffic routing, which is essential for the strangler pattern. Install it on your EKS cluster.

### Install Istio

```bash
# Download and install Istio
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.22.0 sh -
istioctl install --set profile=default -y

# Enable automatic sidecar injection
kubectl label namespace default istio-injection=enabled
```

Or use our automated script:

```bash
bash infra/istio/install-istio.sh
```

### Create the Gateway

The Gateway defines the external entry point for all traffic into the mesh:

```yaml
# infra/istio/gateway.yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: strangler-fig-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
    - port:
        number: 80
        name: http
        protocol: HTTP
      hosts:
        - "*"
```

### Route Everything to the Monolith (Initial State)

Create a VirtualService that initially routes **all traffic** to the monolith:

```yaml
# infra/istio/virtual-service-phase1.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: strangler-fig-routing
  labels:
    strangler-fig/phase: "1"
spec:
  hosts:
    - "*"
  gateways:
    - strangler-fig-gateway
  http:
    # All traffic goes to the monolith initially
    - route:
        - destination:
            host: monolith
            port:
              number: 80
          weight: 100
```

```bash
kubectl apply -f infra/istio/gateway.yaml
kubectl apply -f infra/istio/virtual-service-phase1.yaml
```

---

## Phase 3: Extract the User Service

Pick a bounded context from the monolith to extract first. Start with something that has clear boundaries and low risk. We chose **user management**.

![Phase 2-3 – Install Istio + Extract User Service](/Users/saitarrunpitta/.gemini/antigravity/brain/323e2726-ef37-4e04-aa67-924a1f6dde22/phase2_3_istio_extract_1775088724502.png)

### Build the New Microservice

We built a Flask microservice with full CRUD operations:

```python
# apps/user-svc/main.py
import os
from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/monolith")

@app.route('/api/users', methods=['GET'])
def list_users():
    """List users – this was previously handled by the monolith."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, email, name, created_at FROM users_microservice "
            "ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (per_page, offset)
        )
        users = cur.fetchall()
    conn.close()
    return jsonify({"users": users, "pagination": {...}}), 200

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a single user by ID."""
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM users_microservice WHERE id = %s", (user_id,))
        user = cur.fetchone()
    conn.close()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO users_microservice (email, name) "
            "VALUES (%s, %s) RETURNING id, email, name",
            (data['email'], data['name'])
        )
        user = cur.fetchone()
    conn.commit()
    conn.close()
    return jsonify(user), 201
```

### Deploy Alongside the Monolith

```yaml
# infra/k8s/templates/user-svc.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-svc
  labels:
    app: user-svc
    version: v1
    strangler-fig/phase: "3"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: user-svc
  template:
    metadata:
      labels:
        app: user-svc
        version: v1
    spec:
      containers:
        - name: user-svc
          image: user-svc:latest
          ports:
            - containerPort: 8002
          resources:
            requests:
              cpu: 200m
              memory: 256Mi
          readinessProbe:
            httpGet:
              path: /health
              port: 8002
---
apiVersion: v1
kind: Service
metadata:
  name: user-svc
spec:
  selector:
    app: user-svc
  ports:
    - port: 80
      targetPort: 8002
```

---

## Phase 4: Route Traffic to the New Service

Now update the VirtualService to route user-related requests to the new microservice while everything else still goes to the monolith.

```yaml
# infra/istio/virtual-service-phase4.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: strangler-fig-routing
  labels:
    strangler-fig/phase: "4"
spec:
  hosts:
    - "*"
  gateways:
    - strangler-fig-gateway
  http:
    # User endpoints now go to the new microservice
    - match:
        - uri:
            prefix: /api/users
      route:
        - destination:
            host: user-svc
            port:
              number: 80

    # Orders v2 go to the orders microservice
    - match:
        - uri:
            prefix: /api/v2/orders
      route:
        - destination:
            host: orders-svc
            port:
              number: 80

    # Everything else still goes to the monolith
    - route:
        - destination:
            host: monolith
            port:
              number: 80
```

```bash
kubectl apply -f infra/istio/virtual-service-phase4.yaml
```

---

## Phase 5: Canary Traffic Splitting

Before routing all user traffic to the new service, do a **gradual rollout**. Start with 10% of traffic and increase as you gain confidence.

![Phase 5 – Canary Traffic Splitting](/Users/saitarrunpitta/.gemini/antigravity/brain/323e2726-ef37-4e04-aa67-924a1f6dde22/phase5_canary_split_1775088755553.png)

### Stage 1: 10% Traffic

```yaml
# infra/istio/virtual-service-canary-10.yaml
http:
  - match:
      - uri:
          prefix: /api/users
    route:
      # Send 10% of user traffic to the new service
      - destination:
          host: user-svc
          port:
            number: 80
        weight: 10
      # Keep 90% on the monolith
      - destination:
          host: monolith
          port:
            number: 80
        weight: 90
```

### Stage 2: 50% Traffic

```yaml
# infra/istio/virtual-service-canary-50.yaml
    route:
      - destination:
          host: user-svc
          weight: 50
      - destination:
          host: monolith
          weight: 50
```

### Stage 3: 100% Traffic (Full Cutover)

```yaml
# infra/istio/virtual-service-canary-100.yaml
    route:
      - destination:
          host: user-svc
          weight: 100
```

### Automated Canary Rollout

We built an automated script that progresses through each stage with health checks:

```bash
# Interactive mode (confirms between stages)
bash infra/k8s/scripts/istio_canary_rollout.sh

# Auto mode (30-second pauses between stages)
bash infra/k8s/scripts/istio_canary_rollout.sh --auto
```

### Validate the Traffic Split

Use our K6 canary validation test to statistically verify the split is correct:

```bash
k6 run tests/k6/canary-validation.js --env EXPECTED_WEIGHT=50
```

```
=== Canary Validation Results ===
Expected split: 50% microservice / 50% monolith
Actual split:   48.5% microservice / 51.5% monolith
Tolerance:      ±10%
Result:         ✅ PASS
================================
```

---

## Phase 6: Data Migration Strategy

One of the trickiest parts of the strangler pattern is handling data. The monolith has its own database, and the new microservice uses separate tables. Here is our approach using **dual writes** during the transition period.

![Phase 6 – Dual-Write Data Migration Strategy](/Users/saitarrunpitta/.gemini/antigravity/brain/323e2726-ef37-4e04-aa67-924a1f6dde22/phase6_dual_write_1775088765316.png)

### Dual-Write Implementation

During migration, the monolith writes to both the old DB and the new one. This keeps data in sync while both systems are active.

```python
# apps/monolith/core/dual_write.py

DUAL_WRITE_ENABLED = os.environ.get('DUAL_WRITE_ENABLED', 'true') == 'true'
USER_SVC_URL = os.environ.get('USER_SVC_URL', 'http://user-svc')

def dual_write_user_http(user_data: dict):
    """Write user data to the user-service via HTTP POST."""
    if not DUAL_WRITE_ENABLED:
        return None
    try:
        response = requests.post(
            f"{USER_SVC_URL}/api/users",
            json=user_data, timeout=5
        )
        if response.status_code in (200, 201):
            logger.info(f"Dual-write success: {user_data['email']}")
            return response.json()
        elif response.status_code == 409:
            logger.info(f"User already exists (idempotent)")
            return None
    except requests.exceptions.RequestException as e:
        # Fallback to direct DB write
        return dual_write_user_db(user_data)

def dual_write_user_db(user_data: dict):
    """Fallback: write directly to the user-service database."""
    conn = psycopg2.connect(USER_SVC_DB_URL)
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO users_microservice (email, name, migrated_from)
               VALUES (%s, %s, 'dual-write')
               ON CONFLICT (email) DO NOTHING""",
            (user_data['email'], user_data['name'])
        )
    conn.commit()
```

### Circuit Breaking with Istio

Istio DestinationRules protect services during the migration:

```yaml
# infra/istio/destination-rules.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: user-svc-destination
spec:
  host: user-svc
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        maxRetries: 3
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
```

---

## Phase 7: Remove the Old Code

Once the new service is handling 100% of user traffic and you've verified everything works, remove the user-related code from the monolith. The monolith gets smaller with each extraction.

![Phase 7 – Final Architecture](/Users/saitarrunpitta/.gemini/antigravity/brain/323e2726-ef37-4e04-aa67-924a1f6dde22/phase7_final_state_1775088775018.png)

### Verify No Traffic Reaches the Monolith

```bash
# Should show zero hits for /api/users
kubectl logs -l app=monolith --tail=1000 | grep "/api/users"
```

### Apply the Final Routing Configuration

```yaml
# infra/istio/virtual-service-final.yaml
http:
  # Users → User Microservice
  - match:
      - uri:
          prefix: /api/users
    route:
      - destination:
          host: user-svc
          port:
            number: 80

  # Orders → Orders Microservice
  - match:
      - uri:
          prefix: /api/v2/orders
    route:
      - destination:
          host: orders-svc
          port:
            number: 80

  # Everything remaining → Monolith (shrunk)
  - route:
      - destination:
          host: monolith
          port:
            number: 80
```

### Disable Dual Writes and Clean Up

```bash
# 1. Disable dual-writes
kubectl set env deployment/monolith DUAL_WRITE_ENABLED=false

# 2. Remove user-related code from monolith codebase
# 3. Rebuild and deploy the slimmed-down monolith

# 4. Apply final routing
kubectl apply -f infra/istio/virtual-service-final.yaml
```

---

## Tracking Migration Progress

Keep a clear record of what has been migrated and what remains in the monolith:

```yaml
# migration-status.yaml
migration:
  completed:
    - name: user-management
      service: user-svc
      routes: ["/api/users/*"]
    - name: order-management
      service: orders-svc
      routes: ["/api/v2/orders/*"]
    - name: notifications
      service: notifications-svc
      routes: []  # Event-driven, no HTTP routes

  remaining:
    - name: payment-processing
    - name: admin-panel
    - name: static-assets
```

---

## Key Takeaways

> [!TIP]
> The Strangler Fig pattern lets you migrate **at your own pace** with minimal risk. You can stop at any point and have a working system. Each extracted service is independently deployable and scalable.

The critical tools are:
1. **Istio VirtualService** — for weight-based traffic splitting and path-based routing
2. **Canary releases** — to gain confidence before full cutover (10% → 50% → 100%)
3. **Dual writes** — to keep data consistent between old and new systems
4. **Circuit breaking** — DestinationRules prevent cascading failures during transition
5. **K6 load testing** — to compare error rates and latency between implementations
6. **Instant rollback** — one `kubectl apply` to route everything back to the monolith

### Quick Reference – Commands for Each Phase

| Phase | Description | Command |
|-------|-------------|---------|
| **1** | All traffic → Monolith | `kubectl apply -f infra/istio/virtual-service-phase1.yaml` |
| **2** | Install Istio | `bash infra/istio/install-istio.sh` |
| **3** | Deploy User Service | `helm upgrade --install demo infra/k8s` |
| **4** | Route users → User Svc | `kubectl apply -f infra/istio/virtual-service-phase4.yaml` |
| **5** | Canary rollout | `bash infra/k8s/scripts/istio_canary_rollout.sh` |
| **6** | Enable dual-writes | `kubectl set env deployment/monolith DUAL_WRITE_ENABLED=true` |
| **7** | Final state | `kubectl apply -f infra/istio/virtual-service-final.yaml` |
| **🚨** | **Rollback** | `kubectl apply -f infra/istio/virtual-service-phase1.yaml` |

---

## Project File Reference

### Infrastructure
| File | Purpose |
|------|---------|
| [main.tf](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/terraform/main.tf) | AWS infrastructure (EKS, RDS, MSK, ElastiCache) |
| [install-istio.sh](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/install-istio.sh) | Istio mesh installation |
| [gateway.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/gateway.yaml) | External traffic entry point |
| [destination-rules.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/destination-rules.yaml) | Circuit breaking & retries |

### Istio Routing (Progressive)
| File | Phase |
|------|-------|
| [virtual-service-phase1.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/virtual-service-phase1.yaml) | 1 — All → monolith |
| [virtual-service-phase4.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/virtual-service-phase4.yaml) | 4 — Users → user-svc |
| [virtual-service-canary-10.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/virtual-service-canary-10.yaml) | 5a — 10% canary |
| [virtual-service-canary-50.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/virtual-service-canary-50.yaml) | 5b — 50% canary |
| [virtual-service-canary-100.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/virtual-service-canary-100.yaml) | 5c — Full cutover |
| [virtual-service-final.yaml](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/istio/virtual-service-final.yaml) | 7 — Final state |

### Applications
| Service | Directory | Technology |
|---------|-----------|-----------|
| [Monolith](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/apps/monolith) | `apps/monolith/` | Django 4.2 |
| [Orders Service](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/apps/orders-svc) | `apps/orders-svc/` | FastAPI |
| [User Service](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/apps/user-svc) | `apps/user-svc/` | Flask |
| [Notifications](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/apps/notifications-svc) | `apps/notifications-svc/` | Node.js |

### Scripts & Tests
| File | Purpose |
|------|---------|
| [deploy_eks_istio.sh](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/deploy_eks_istio.sh) | Full deployment script |
| [istio_canary_rollout.sh](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/k8s/scripts/istio_canary_rollout.sh) | Canary progression |
| [rollback.sh](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/infra/k8s/scripts/rollback.sh) | Emergency rollback |
| [load-test.js](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/tests/k6/load-test.js) | K6 load test |
| [canary-validation.js](file:///Users/saitarrunpitta/Projects/monolith-microservices-demo/tests/k6/canary-validation.js) | Traffic split validation |
