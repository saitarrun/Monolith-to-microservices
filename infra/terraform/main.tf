data "aws_availability_zones" "available" {}

locals {
  name   = "ex-${basename(path.cwd)}"
  region = var.region

  vpc_cidr = var.vpc_cidr
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    Example    = local.name
    GithubRepo = "terraform-aws-eks"
    GithubOrg  = "terraform-aws-modules"
  }

  db_password = "password123" # Hardcoded for demo simplicity
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = local.vpc_cidr

  azs             = local.azs
  private_subnets = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k)]
  public_subnets  = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 4)]
  intra_subnets   = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 8)]

  enable_nat_gateway = true
  single_nat_gateway = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = local.tags
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.30"

  cluster_endpoint_public_access  = true

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.intra_subnets

  # EKS Managed Node Group(s)
  eks_managed_node_group_defaults = {
    instance_types = ["t3.medium"]
  }

  eks_managed_node_groups = {
    green = {
      min_size     = 1
      max_size     = 3
      desired_size = 2

      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
    }
  }

  tags = local.tags
}

module "db_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "${local.name}-db-sg"
  description = "Security group for RDS/Redis/MSK"
  vpc_id      = module.vpc.vpc_id

  ingress_with_source_security_group_id = [
    {
      rule                     = "postgresql-tcp"
      source_security_group_id = module.eks.node_security_group_id
    },
    {
      rule                     = "redis-tcp"
      source_security_group_id = module.eks.node_security_group_id
    },
    {
      from_port                = 9092
      to_port                  = 9092
      protocol                 = "tcp"
      description              = "Kafka plaintext"
      source_security_group_id = module.eks.node_security_group_id
    },
    {
      from_port                = 9094
      to_port                  = 9094
      protocol                 = "tcp"
      description              = "Kafka TLS"
      source_security_group_id = module.eks.node_security_group_id
    }
  ]
  
  tags = local.tags
}

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "${local.name}-postgres"

  engine               = "postgres"
  engine_version       = "14"
  family               = "postgres14"
  major_engine_version = "14"
  instance_class       = "db.t3.micro"

  allocated_storage     = 20
  max_allocated_storage = 100

  db_name  = "monolith"
  username = "postgres"
  password = local.db_password
  manage_master_user_password = false # Disable Secrets Manager management for direct output
  port     = 5432

  multi_az               = false
  db_subnet_group_name   = module.vpc.database_subnet_group
  vpc_security_group_ids = [module.db_sg.security_group_id]

  maintenance_window      = "Mon:00:00-Mon:03:00"
  backup_window           = "03:00-06:00"
  backup_retention_period = 0

  create_db_subnet_group = true
  subnet_ids             = module.vpc.private_subnets

  tags = local.tags
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-redis-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis"
  description          = "Redis cluster for caching"
  node_type            = "cache.t3.micro"
  port                 = 6379
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [module.db_sg.security_group_id]

  automatic_failover_enabled = false
  num_node_groups            = 1
  replicas_per_node_group    = 0
}

resource "aws_msk_cluster" "kafka" {
  cluster_name           = "${local.name}-kafka"
  kafka_version          = "3.6.0" # Updated version
  number_of_broker_nodes = 2

  broker_node_group_info {
    instance_type   = "kafka.t3.small"
    client_subnets  = slice(module.vpc.private_subnets, 0, 2)
    security_groups = [module.db_sg.security_group_id]
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "PLAINTEXT"
    }
  }

  tags = local.tags
}

resource "kubernetes_secret_v1" "db_creds" {
  metadata {
    name = "db-creds"
  }

  data = {
    username = module.rds.db_instance_username
    password = local.db_password
    host     = module.rds.db_instance_endpoint
    dbname   = module.rds.db_instance_name
    url      = "postgresql://${module.rds.db_instance_username}:${local.db_password}@${module.rds.db_instance_endpoint}/${module.rds.db_instance_name}"
  }
}

resource "kubernetes_secret_v1" "redis_creds" {
  metadata {
    name = "redis-creds"
  }

  data = {
    host = aws_elasticache_replication_group.redis.primary_endpoint_address
    url  = "redis://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
  }
}

resource "kubernetes_secret_v1" "kafka_creds" {
  metadata {
    name = "kafka-creds"
  }

  data = {
    brokers = aws_msk_cluster.kafka.bootstrap_brokers
  }
}
