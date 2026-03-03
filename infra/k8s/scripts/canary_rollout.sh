#!/bin/bash
# Canary Rollout Script for Orders V2
# This script incrementally shifts traffic from the Monolith to the new Orders Microservice.

set -e

NAMESPACE="default"
INGRESS_NAME="demo-ingress"

echo "🚀 Starting Canary Rollout for Orders Service..."

# Step 1: 10% Traffic
echo "⏳ Shifting 10% of traffic to V2..."
kubectl annotate ingress $INGRESS_NAME nginx.ingress.kubernetes.io/canary="true" -n $NAMESPACE --overwrite
kubectl annotate ingress $INGRESS_NAME nginx.ingress.kubernetes.io/canary-weight="10" -n $NAMESPACE --overwrite
echo "✅ 10% traffic shifted. Monitor /metrics for p99 latency and error rates."
sleep 10 # Wait for observation

# Step 2: 50% Traffic
echo "⏳ Shifting 50% of traffic to V2..."
kubectl annotate ingress $INGRESS_NAME nginx.ingress.kubernetes.io/canary-weight="50" -n $NAMESPACE --overwrite
echo "✅ 50% traffic shifted. Check Grafana dashboards."
sleep 10 # Wait for observation

# Step 3: 100% Traffic (Full Cutover)
echo "🚀 Shifting 100% of traffic to V2..."
kubectl annotate ingress $INGRESS_NAME nginx.ingress.kubernetes.io/canary-weight="100" -n $NAMESPACE --overwrite
echo "🎉 Cutover complete. V2 is handling all traffic."
