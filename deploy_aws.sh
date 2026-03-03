#!/bin/bash
set -e

echo "Starting AWS Deployment..."

# 1. Apply Terraform
echo "Applying Terraform Infrastructure..."
cd infra/terraform
terraform init -upgrade
terraform apply -auto-approve
cd ../..

# 2. Configure kubectl
echo "Configuring kubectl..."
REGION=$(terraform -chdir=infra/terraform output -raw region)
CLUSTER_NAME=$(terraform -chdir=infra/terraform output -raw cluster_name)
aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME

# 3. Deploy Helm Chart
echo "Deploying Application via Helm..."
# Note: Image tags would typically come from CI/CD, defaulting to latest for demo
helm upgrade --install demo infra/k8s

echo "Deployment Complete!"
echo "Check status with: kubectl get pods"
