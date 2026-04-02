"""
=============================================================================
Unit Tests – Migration Integrity & Docker Compose Validation
=============================================================================
Validates that the overall migration setup is consistent:
- docker-compose.yml has all services
- migration-status.yaml is correct
- All required files exist
- Service connectivity configuration is correct
=============================================================================
"""

import pytest
import yaml
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def load_yaml_file(relative_path):
    """Load a YAML file relative to project root."""
    path = os.path.join(PROJECT_ROOT, relative_path)
    with open(path) as f:
        return yaml.safe_load(f)


# =============================================================================
# Docker Compose Validation
# =============================================================================

class TestDockerCompose:
    @pytest.fixture(autouse=True)
    def load_compose(self):
        self.compose = load_yaml_file('docker-compose.yml')

    def test_all_services_present(self):
        """docker-compose contains all required services."""
        services = set(self.compose['services'].keys())
        expected = {'db', 'redis', 'kafka', 'zookeeper', 'monolith',
                    'orders-svc', 'user-svc', 'notifications-svc',
                    'prometheus', 'grafana', 'storefront'}
        assert expected.issubset(services), f"Missing services: {expected - services}"

    def test_user_svc_config(self):
        """user-svc has correct port and DB configuration."""
        user_svc = self.compose['services']['user-svc']
        assert '8002:8002' in user_svc['ports']
        assert 'DATABASE_URL' in str(user_svc.get('environment', {}))

    def test_monolith_has_dual_write_env(self):
        """Monolith has DUAL_WRITE_ENABLED and USER_SVC_URL env vars."""
        monolith = self.compose['services']['monolith']
        env = monolith.get('environment', {})
        assert 'DUAL_WRITE_ENABLED' in str(env)
        assert 'USER_SVC_URL' in str(env)

    def test_monolith_depends_on_infrastructure(self):
        """Monolith depends on db, redis, and kafka."""
        monolith = self.compose['services']['monolith']
        deps = monolith.get('depends_on', [])
        assert 'db' in deps
        assert 'redis' in deps
        assert 'kafka' in deps

    def test_user_svc_depends_on_db(self):
        """user-svc depends on db."""
        user_svc = self.compose['services']['user-svc']
        deps = user_svc.get('depends_on', [])
        assert 'db' in deps

    def test_storefront_depends_on_user_svc(self):
        """Storefront depends on user-svc."""
        storefront = self.compose['services']['storefront']
        deps = storefront.get('depends_on', [])
        assert 'user-svc' in deps

    def test_no_version_key(self):
        """docker-compose doesn't have deprecated 'version' key."""
        assert 'version' not in self.compose


# =============================================================================
# Migration Status Validation
# =============================================================================

class TestMigrationStatus:
    @pytest.fixture(autouse=True)
    def load_status(self):
        self.status = load_yaml_file('migration-status.yaml')

    def test_has_migration_section(self):
        """migration-status.yaml has a migration section."""
        assert 'migration' in self.status

    def test_strategy_is_strangler_fig(self):
        """Migration strategy is strangler-fig."""
        assert self.status['migration']['strategy'] == 'strangler-fig'

    def test_completed_extractions(self):
        """At least 3 services are listed as completed."""
        completed = self.status['migration']['completed']
        assert len(completed) >= 3

    def test_completed_services_have_required_fields(self):
        """Each completed service has name, service, language."""
        for svc in self.status['migration']['completed']:
            assert 'name' in svc, f"Missing 'name' in {svc}"
            assert 'service' in svc, f"Missing 'service' in {svc}"
            assert 'language' in svc, f"Missing 'language' in {svc}"

    def test_remaining_services_listed(self):
        """Remaining services are tracked."""
        remaining = self.status['migration']['remaining']
        assert len(remaining) > 0

    def test_current_routing_phase(self):
        """Current routing phase is documented."""
        routing = self.status['migration']['current_routing']
        assert 'phase' in routing
        assert 'config' in routing


# =============================================================================
# Project File Integrity Tests
# =============================================================================

class TestFileIntegrity:
    """Verify all critical files exist."""

    @pytest.mark.parametrize("filepath", [
        # User service
        'apps/user-svc/main.py',
        'apps/user-svc/Dockerfile',
        'apps/user-svc/requirements.txt',
        # Dual write
        'apps/monolith/core/dual_write.py',
        # Monolith
        'apps/monolith/Dockerfile',
        'apps/monolith/monolith/urls.py',
        'apps/monolith/core/views.py',
        # Orders service
        'apps/orders-svc/main.py',
        'apps/orders-svc/Dockerfile',
        # Notifications service
        'apps/notifications-svc/index.js',
        'apps/notifications-svc/Dockerfile',
        # Istio configs
        'infra/istio/gateway.yaml',
        'infra/istio/destination-rules.yaml',
        'infra/istio/virtual-service-phase1.yaml',
        'infra/istio/virtual-service-phase4.yaml',
        'infra/istio/virtual-service-canary-10.yaml',
        'infra/istio/virtual-service-canary-50.yaml',
        'infra/istio/virtual-service-canary-100.yaml',
        'infra/istio/virtual-service-final.yaml',
        'infra/istio/install-istio.sh',
        # K8s templates
        'infra/k8s/templates/monolith.yaml',
        'infra/k8s/templates/orders-svc.yaml',
        'infra/k8s/templates/user-svc.yaml',
        'infra/k8s/values.yaml',
        # Scripts
        'deploy_eks_istio.sh',
        'infra/k8s/scripts/istio_canary_rollout.sh',
        # CI/CD
        '.github/workflows/ci-cd.yaml',
        # Docs
        'docs/strangler-fig-migration.md',
        'docs/strangler-fig-migration.pdf',
        # Config
        'docker-compose.yml',
        'migration-status.yaml',
    ])
    def test_file_exists(self, filepath):
        """All critical migration files exist."""
        full_path = os.path.join(PROJECT_ROOT, filepath)
        assert os.path.exists(full_path), f"Missing: {filepath}"

    def test_scripts_are_executable(self):
        """Shell scripts have executable permissions."""
        scripts = [
            'deploy_eks_istio.sh',
            'infra/istio/install-istio.sh',
            'infra/k8s/scripts/istio_canary_rollout.sh',
        ]
        for script in scripts:
            path = os.path.join(PROJECT_ROOT, script)
            assert os.access(path, os.X_OK), f"{script} is not executable"


# =============================================================================
# Helm Values Validation
# =============================================================================

class TestHelmValues:
    @pytest.fixture(autouse=True)
    def load_values(self):
        self.values = load_yaml_file('infra/k8s/values.yaml')

    def test_has_all_services(self):
        """Helm values define all 4 application services."""
        assert 'monolith' in self.values
        assert 'orders' in self.values
        assert 'users' in self.values
        assert 'notifications' in self.values

    def test_istio_enabled(self):
        """Istio is enabled in values."""
        assert self.values.get('istio', {}).get('enabled') is True

    def test_replicas_are_positive(self):
        """All services have at least 1 replica."""
        for svc in ['monolith', 'orders', 'users']:
            assert self.values[svc]['replicas'] >= 1, f"{svc} has 0 replicas"


# =============================================================================
# CI/CD Pipeline Validation
# =============================================================================

class TestCICD:
    @pytest.fixture(autouse=True)
    def load_workflow(self):
        self.workflow = load_yaml_file('.github/workflows/ci-cd.yaml')

    def test_has_required_jobs(self):
        """CI/CD has code-quality, build-and-push, deploy jobs."""
        jobs = set(self.workflow['jobs'].keys())
        assert 'code-quality' in jobs
        assert 'build-and-push' in jobs
        assert 'deploy' in jobs

    def test_builds_all_four_services(self):
        """CI/CD builds user-svc alongside other services."""
        env = self.workflow.get('env', {})
        assert 'ECR_REPOSITORY_USERS' in env

    def test_deploy_applies_istio_configs(self):
        """Deploy job applies Istio gateway and routing."""
        deploy_steps = self.workflow['jobs']['deploy']['steps']
        step_names = [s.get('name', '') for s in deploy_steps]
        assert any('Istio' in name for name in step_names)
