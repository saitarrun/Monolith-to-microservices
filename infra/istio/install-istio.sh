#!/bin/bash
# =============================================================================
# Istio Installation Script for AWS EKS
# Part of the Strangler Fig Pattern Migration
# =============================================================================
# This script installs Istio on an existing EKS cluster and configures it
# for progressive traffic routing between the monolith and microservices.
# =============================================================================

set -euo pipefail

ISTIO_VERSION="${ISTIO_VERSION:-1.22.0}"
NAMESPACE="${NAMESPACE:-default}"
ISTIO_NAMESPACE="istio-system"

echo "============================================="
echo "  Strangler Fig – Istio Setup on AWS EKS"
echo "============================================="
echo ""

# -------------------------------------------
# Step 1: Download and install Istio CLI
# -------------------------------------------
echo "📥 Step 1: Installing Istio ${ISTIO_VERSION}..."

if command -v istioctl &> /dev/null; then
    echo "  istioctl already installed: $(istioctl version --short 2>/dev/null || echo 'unknown')"
else
    curl -L https://istio.io/downloadIstio | ISTIO_VERSION=$ISTIO_VERSION sh -
    export PATH="$PWD/istio-${ISTIO_VERSION}/bin:$PATH"
    echo "  ✅ istioctl installed"
fi

# -------------------------------------------
# Step 2: Pre-flight check
# -------------------------------------------
echo ""
echo "🔍 Step 2: Running pre-flight checks..."
istioctl x precheck
echo "  ✅ Pre-flight checks passed"

# -------------------------------------------
# Step 3: Install Istio with the 'default' profile
# The default profile includes:
#   - istiod (control plane)
#   - istio-ingressgateway
# -------------------------------------------
echo ""
echo "🚀 Step 3: Installing Istio with default profile..."
istioctl install --set profile=default -y \
    --set meshConfig.accessLogFile=/dev/stdout \
    --set meshConfig.defaultConfig.holdApplicationUntilProxyStarts=true

echo "  ✅ Istio installed"

# -------------------------------------------
# Step 4: Verify installation
# -------------------------------------------
echo ""
echo "🔎 Step 4: Verifying Istio installation..."
kubectl get pods -n $ISTIO_NAMESPACE
istioctl verify-install
echo "  ✅ Istio verified"

# -------------------------------------------
# Step 5: Enable sidecar injection on the target namespace
# -------------------------------------------
echo ""
echo "💉 Step 5: Enabling automatic sidecar injection on '${NAMESPACE}' namespace..."
kubectl label namespace $NAMESPACE istio-injection=enabled --overwrite
echo "  ✅ Sidecar injection enabled for namespace: $NAMESPACE"

# -------------------------------------------
# Step 6: Restart existing pods to inject sidecars
# -------------------------------------------
echo ""
echo "🔄 Step 6: Restarting existing deployments to inject Istio sidecars..."
kubectl rollout restart deployment -n $NAMESPACE
echo "  ✅ Deployments restarting with Istio sidecars"

# -------------------------------------------
# Step 7: Install Kiali, Prometheus, Grafana (observability)
# -------------------------------------------
echo ""
echo "📊 Step 7: Installing Istio addons (Kiali, Prometheus, Grafana, Jaeger)..."
kubectl apply -f "https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/prometheus.yaml" || true
kubectl apply -f "https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/grafana.yaml" || true
kubectl apply -f "https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/jaeger.yaml" || true
kubectl apply -f "https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/kiali.yaml" || true
echo "  ✅ Observability addons installed"

# -------------------------------------------
# Summary
# -------------------------------------------
echo ""
echo "============================================="
echo "  ✅ Istio Installation Complete"
echo "============================================="
echo ""
echo "Next steps:"
echo "  1. Apply the Istio Gateway:        kubectl apply -f infra/istio/gateway.yaml"
echo "  2. Apply the initial routing:       kubectl apply -f infra/istio/virtual-service-phase1.yaml"
echo "  3. Get the ingress gateway IP:      kubectl get svc istio-ingressgateway -n istio-system"
echo ""
echo "Access observability dashboards:"
echo "  Kiali:    istioctl dashboard kiali"
echo "  Grafana:  istioctl dashboard grafana"
echo "  Jaeger:   istioctl dashboard jaeger"
echo ""
