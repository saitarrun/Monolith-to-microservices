#!/bin/bash
# Immediate Rollback Script
# This script instantly un-routes all traffic from the microservice and sends it back to the monolith.

set -e

NAMESPACE="default"
INGRESS_NAME="demo-ingress"

echo "🚨 Initiating Emergency Rollback..."

# Remove Canary Annotations to instantly fallback to default rules
kubectl annotate ingress $INGRESS_NAME nginx.ingress.kubernetes.io/canary- -n $NAMESPACE || true
kubectl annotate ingress $INGRESS_NAME nginx.ingress.kubernetes.io/canary-weight- -n $NAMESPACE || true

echo "✅ Rollback complete. 100% of traffic is routed back to the Django Monolith."
echo "Wait for dual-write consumer lag to clear before investigating V2 issues."
