#!/bin/bash
# =============================================================================
# Istio Canary Rollout Script – Strangler Fig Phase 5
# =============================================================================
# Progressively shifts traffic from the monolith to the user-service
# using Istio VirtualService weight adjustments.
#
# Usage: ./istio_canary_rollout.sh [--auto]
#   --auto: Skip manual confirmation between stages
# =============================================================================

set -euo pipefail

NAMESPACE="default"
ISTIO_DIR="$(dirname "$0")/../../istio"
AUTO_MODE="${1:-}"

confirm_proceed() {
    if [[ "$AUTO_MODE" == "--auto" ]]; then
        echo "  [Auto mode] Proceeding in 30 seconds..."
        sleep 30
    else
        echo ""
        read -p "  Press Enter to proceed to the next stage, or Ctrl+C to abort... " _
    fi
}

check_health() {
    local service=$1
    echo "  🔍 Checking $service health..."
    
    # Check pod readiness
    READY=$(kubectl get pods -l app=$service -n $NAMESPACE -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
    echo "    Pod readiness: $READY"
    
    # Check for recent errors in Istio metrics (via Prometheus)
    echo "    Check Kiali/Grafana for error rates and latency."
}

echo "============================================="
echo "  Strangler Fig – Canary Rollout (User Service)"
echo "============================================="
echo ""
echo "This script will progressively shift /api/users traffic:"
echo "  Phase 1: 10% → user-svc, 90% → monolith"
echo "  Phase 2: 50% → user-svc, 50% → monolith"
echo "  Phase 3: 100% → user-svc (full cutover)"
echo ""

# -----------------------------------------------------------
# Pre-flight: Verify both services are running
# -----------------------------------------------------------
echo "🔍 Pre-flight checks..."
check_health "monolith"
check_health "user-svc"
echo ""

# -----------------------------------------------------------
# Stage 1: 10% traffic to user-service
# -----------------------------------------------------------
echo "============================================="
echo "  Stage 1: 10% Traffic to User Service"
echo "============================================="
echo ""
echo "⏳ Applying canary-10 VirtualService..."
kubectl apply -f "$ISTIO_DIR/virtual-service-canary-10.yaml" -n $NAMESPACE
echo "✅ 10% of /api/users traffic now routed to user-svc"
echo ""
echo "📊 Monitor the following metrics:"
echo "   - Error rates: istioctl dashboard kiali"
echo "   - Latency: istioctl dashboard grafana"
echo "   - Logs: kubectl logs -l app=user-svc --tail=50"
echo ""
check_health "user-svc"
confirm_proceed

# -----------------------------------------------------------
# Stage 2: 50% traffic to user-service
# -----------------------------------------------------------
echo ""
echo "============================================="
echo "  Stage 2: 50% Traffic to User Service"
echo "============================================="
echo ""
echo "⏳ Applying canary-50 VirtualService..."
kubectl apply -f "$ISTIO_DIR/virtual-service-canary-50.yaml" -n $NAMESPACE
echo "✅ 50% of /api/users traffic now routed to user-svc"
echo ""
check_health "user-svc"
confirm_proceed

# -----------------------------------------------------------
# Stage 3: 100% traffic to user-service (Full Cutover)
# -----------------------------------------------------------
echo ""
echo "============================================="
echo "  Stage 3: 100% Traffic to User Service (CUTOVER)"
echo "============================================="
echo ""
echo "⏳ Applying canary-100 VirtualService..."
kubectl apply -f "$ISTIO_DIR/virtual-service-canary-100.yaml" -n $NAMESPACE
echo "🎉 100% of /api/users traffic now routed to user-svc"
echo ""

# -----------------------------------------------------------
# Summary
# -----------------------------------------------------------
echo ""
echo "============================================="
echo "  ✅ Canary Rollout Complete"
echo "============================================="
echo ""
echo "Current routing state:"
kubectl get virtualservice strangler-fig-routing -n $NAMESPACE -o yaml | grep -A 20 "http:"
echo ""
echo "Next steps:"
echo "  1. Monitor for 24-48 hours"
echo "  2. Verify data consistency between monolith and user-svc databases"
echo "  3. Remove user-related code from the monolith (Phase 7)"
echo "  4. Update migration-status.yaml"
echo ""
echo "To rollback at any time:"
echo "  kubectl apply -f $ISTIO_DIR/virtual-service-phase1.yaml"
echo ""
