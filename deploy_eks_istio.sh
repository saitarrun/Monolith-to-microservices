#!/bin/bash
# =============================================================================
# AWS EKS Deployment Script with Istio (Strangler Fig Pattern)
# =============================================================================
# Deploys complete infrastructure + Istio service mesh for progressive
# monolith-to-microservices migration.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================="
echo "  AWS EKS + Istio Deployment"
echo "  Strangler Fig Migration"
echo "============================================="
echo ""

# -----------------------------------------------------------
# Step 1: Apply Terraform Infrastructure
# -----------------------------------------------------------
echo "📦 Step 1: Provisioning AWS Infrastructure..."
cd "$SCRIPT_DIR/infra/terraform"
terraform init -upgrade
terraform apply -auto-approve
cd "$SCRIPT_DIR"

# -----------------------------------------------------------
# Step 2: Configure kubectl for EKS
# -----------------------------------------------------------
echo ""
echo "🔧 Step 2: Configuring kubectl..."
REGION=$(terraform -chdir=infra/terraform output -raw region)
CLUSTER_NAME=$(terraform -chdir=infra/terraform output -raw cluster_name)
aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME"

echo "  ✅ kubectl configured for cluster: $CLUSTER_NAME"

# -----------------------------------------------------------
# Step 3: Install Istio Service Mesh
# -----------------------------------------------------------
echo ""
echo "🕸️  Step 3: Installing Istio Service Mesh..."
chmod +x infra/istio/install-istio.sh
bash infra/istio/install-istio.sh

# -----------------------------------------------------------
# Step 4: Apply Istio Gateway + Destination Rules
# -----------------------------------------------------------
echo ""
echo "🌐 Step 4: Applying Istio Gateway and Destination Rules..."
kubectl apply -f infra/istio/gateway.yaml
kubectl apply -f infra/istio/destination-rules.yaml
echo "  ✅ Gateway and DestinationRules applied"

# -----------------------------------------------------------
# Step 5: Deploy Application via Helm
# -----------------------------------------------------------
echo ""
echo "🚀 Step 5: Deploying Application..."
helm upgrade --install demo infra/k8s
echo "  ✅ Application deployed"

# -----------------------------------------------------------
# Step 6: Apply Initial Routing (Phase 1 – All → Monolith)
# -----------------------------------------------------------
echo ""
echo "🛤️  Step 6: Applying Phase 1 routing (all traffic → monolith)..."
kubectl apply -f infra/istio/virtual-service-phase1.yaml
echo "  ✅ Phase 1 VirtualService applied"

# -----------------------------------------------------------
# Summary
# -----------------------------------------------------------
echo ""
echo "============================================="
echo "  ✅ Deployment Complete!"
echo "============================================="
echo ""
echo "Check status:"
echo "  kubectl get pods"
echo "  kubectl get virtualservice"
echo "  kubectl get gateway"
echo ""
echo "Get Istio Ingress Gateway IP:"
echo "  kubectl get svc istio-ingressgateway -n istio-system"
echo ""
echo "Next steps (Strangler Fig Progression):"
echo "  Phase 4: kubectl apply -f infra/istio/virtual-service-phase4.yaml"
echo "  Phase 5: bash infra/k8s/scripts/istio_canary_rollout.sh"
echo "  Phase 7: kubectl apply -f infra/istio/virtual-service-final.yaml"
echo ""
