"""
=============================================================================
Unit Tests – Istio VirtualService Configuration Validation
=============================================================================
Validates that all Istio routing configurations are structurally correct
and the Strangler Fig traffic routing progression is consistent.
=============================================================================
"""

import pytest
import yaml
import os

ISTIO_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'infra', 'istio'))


def load_yaml(filename):
    """Load and parse an Istio YAML file."""
    path = os.path.join(ISTIO_DIR, filename)
    with open(path) as f:
        return yaml.safe_load(f)


# =============================================================================
# Gateway Tests
# =============================================================================

class TestGateway:
    def test_gateway_exists(self):
        """Gateway YAML file exists."""
        assert os.path.exists(os.path.join(ISTIO_DIR, 'gateway.yaml'))

    def test_gateway_structure(self):
        """Gateway has correct Istio API structure."""
        gw = load_yaml('gateway.yaml')
        assert gw['apiVersion'] == 'networking.istio.io/v1beta1'
        assert gw['kind'] == 'Gateway'
        assert gw['metadata']['name'] == 'strangler-fig-gateway'

    def test_gateway_uses_istio_ingress(self):
        """Gateway uses istio: ingressgateway selector."""
        gw = load_yaml('gateway.yaml')
        assert gw['spec']['selector']['istio'] == 'ingressgateway'

    def test_gateway_has_http_server(self):
        """Gateway defines an HTTP server on port 80."""
        gw = load_yaml('gateway.yaml')
        servers = gw['spec']['servers']
        assert len(servers) >= 1
        assert servers[0]['port']['number'] == 80
        assert servers[0]['port']['protocol'] == 'HTTP'


# =============================================================================
# VirtualService Phase Tests
# =============================================================================

class TestVirtualServicePhase1:
    def test_phase1_all_traffic_to_monolith(self):
        """Phase 1: 100% traffic goes to monolith."""
        vs = load_yaml('virtual-service-phase1.yaml')
        routes = vs['spec']['http']
        assert len(routes) == 1
        dest = routes[0]['route'][0]
        assert dest['destination']['host'] == 'monolith'
        assert dest['weight'] == 100

    def test_phase1_references_gateway(self):
        """Phase 1 VirtualService references the strangler-fig-gateway."""
        vs = load_yaml('virtual-service-phase1.yaml')
        assert 'strangler-fig-gateway' in vs['spec']['gateways']


class TestVirtualServicePhase4:
    def test_phase4_users_route_to_user_svc(self):
        """Phase 4: /api/users goes to user-svc."""
        vs = load_yaml('virtual-service-phase4.yaml')
        routes = vs['spec']['http']

        users_route = routes[0]
        assert users_route['match'][0]['uri']['prefix'] == '/api/users'
        assert users_route['route'][0]['destination']['host'] == 'user-svc'
        assert users_route['route'][0]['weight'] == 100

    def test_phase4_orders_route_to_orders_svc(self):
        """Phase 4: /api/v2/orders goes to orders-svc."""
        vs = load_yaml('virtual-service-phase4.yaml')
        routes = vs['spec']['http']

        orders_route = routes[1]
        assert orders_route['match'][0]['uri']['prefix'] == '/api/v2/orders'
        assert orders_route['route'][0]['destination']['host'] == 'orders-svc'

    def test_phase4_catchall_to_monolith(self):
        """Phase 4: catch-all goes to monolith."""
        vs = load_yaml('virtual-service-phase4.yaml')
        routes = vs['spec']['http']

        catchall = routes[-1]
        assert 'match' not in catchall
        assert catchall['route'][0]['destination']['host'] == 'monolith'


# =============================================================================
# Canary Split Tests
# =============================================================================

class TestCanarySplits:
    def test_canary_10_weights(self):
        """Canary 10%: user-svc gets 10%, monolith gets 90%."""
        vs = load_yaml('virtual-service-canary-10.yaml')
        users_route = vs['spec']['http'][0]
        assert users_route['match'][0]['uri']['prefix'] == '/api/users'

        destinations = users_route['route']
        weights = {d['destination']['host']: d['weight'] for d in destinations}
        assert weights['user-svc'] == 10
        assert weights['monolith'] == 90

    def test_canary_50_weights(self):
        """Canary 50%: equal split between user-svc and monolith."""
        vs = load_yaml('virtual-service-canary-50.yaml')
        users_route = vs['spec']['http'][0]

        destinations = users_route['route']
        weights = {d['destination']['host']: d['weight'] for d in destinations}
        assert weights['user-svc'] == 50
        assert weights['monolith'] == 50

    def test_canary_100_weights(self):
        """Canary 100%: all user traffic to user-svc."""
        vs = load_yaml('virtual-service-canary-100.yaml')
        users_route = vs['spec']['http'][0]

        destinations = users_route['route']
        assert len(destinations) == 1
        assert destinations[0]['destination']['host'] == 'user-svc'
        assert destinations[0]['weight'] == 100

    def test_canary_weights_always_sum_to_100(self):
        """All canary configs have weights that sum to 100 for user routes."""
        for filename in ['virtual-service-canary-10.yaml',
                         'virtual-service-canary-50.yaml',
                         'virtual-service-canary-100.yaml']:
            vs = load_yaml(filename)
            users_route = vs['spec']['http'][0]
            total = sum(d['weight'] for d in users_route['route'])
            assert total == 100, f"{filename}: weights sum to {total}, expected 100"

    def test_canary_configs_preserve_orders_routing(self):
        """All canary configs keep /api/v2/orders → orders-svc."""
        for filename in ['virtual-service-canary-10.yaml',
                         'virtual-service-canary-50.yaml',
                         'virtual-service-canary-100.yaml']:
            vs = load_yaml(filename)
            routes = vs['spec']['http']
            orders_route = [r for r in routes if r.get('match') and
                           r['match'][0]['uri']['prefix'] == '/api/v2/orders']
            assert len(orders_route) == 1, f"{filename}: missing orders route"
            assert orders_route[0]['route'][0]['destination']['host'] == 'orders-svc'

    def test_canary_configs_preserve_monolith_catchall(self):
        """All canary configs keep catch-all → monolith."""
        for filename in ['virtual-service-canary-10.yaml',
                         'virtual-service-canary-50.yaml',
                         'virtual-service-canary-100.yaml']:
            vs = load_yaml(filename)
            routes = vs['spec']['http']
            catchall = routes[-1]
            assert 'match' not in catchall
            assert catchall['route'][0]['destination']['host'] == 'monolith'


# =============================================================================
# Final State Tests
# =============================================================================

class TestVirtualServiceFinal:
    def test_final_users_to_user_svc(self):
        """Final: /api/users → user-svc (100%)."""
        vs = load_yaml('virtual-service-final.yaml')
        routes = vs['spec']['http']
        users_route = routes[0]
        assert users_route['match'][0]['uri']['prefix'] == '/api/users'
        assert users_route['route'][0]['destination']['host'] == 'user-svc'

    def test_final_orders_to_orders_svc(self):
        """Final: /api/v2/orders → orders-svc."""
        vs = load_yaml('virtual-service-final.yaml')
        routes = vs['spec']['http']
        orders_route = routes[1]
        assert orders_route['match'][0]['uri']['prefix'] == '/api/v2/orders'
        assert orders_route['route'][0]['destination']['host'] == 'orders-svc'

    def test_final_catchall_to_monolith(self):
        """Final: remaining traffic → monolith."""
        vs = load_yaml('virtual-service-final.yaml')
        routes = vs['spec']['http']
        catchall = routes[-1]
        assert catchall['route'][0]['destination']['host'] == 'monolith'

    def test_final_has_phase_label(self):
        """Final config has strangler-fig/phase label."""
        vs = load_yaml('virtual-service-final.yaml')
        assert 'strangler-fig/phase' in vs['metadata']['labels']


# =============================================================================
# Destination Rules Tests
# =============================================================================

class TestDestinationRules:
    def test_destination_rules_exist(self):
        """Destination rules YAML file exists."""
        assert os.path.exists(os.path.join(ISTIO_DIR, 'destination-rules.yaml'))

    def test_circuit_breaking_for_all_services(self):
        """Destination rules define circuit breaking for all 3 services."""
        path = os.path.join(ISTIO_DIR, 'destination-rules.yaml')
        with open(path) as f:
            docs = list(yaml.safe_load_all(f))

        hosts = [doc['spec']['host'] for doc in docs if doc]
        assert 'user-svc' in hosts
        assert 'monolith' in hosts
        assert 'orders-svc' in hosts

    def test_outlier_detection_configured(self):
        """All destination rules have outlier detection."""
        path = os.path.join(ISTIO_DIR, 'destination-rules.yaml')
        with open(path) as f:
            docs = list(yaml.safe_load_all(f))

        for doc in docs:
            if doc is None:
                continue
            policy = doc['spec']['trafficPolicy']
            assert 'outlierDetection' in policy, f"Missing outlierDetection for {doc['spec']['host']}"
            od = policy['outlierDetection']
            assert od['consecutive5xxErrors'] > 0
            assert od['maxEjectionPercent'] > 0


# =============================================================================
# Progressive Migration Sequence Test
# =============================================================================

class TestMigrationProgression:
    """Validates the full Strangler Fig progression is consistent."""

    def test_progressive_user_traffic_shift(self):
        """Validate the traffic shift: 0% → 10% → 50% → 100% to user-svc."""
        expected = [
            ('virtual-service-phase1.yaml', 0),      # Phase 1: 0% to user-svc
            ('virtual-service-canary-10.yaml', 10),   # Phase 5a: 10%
            ('virtual-service-canary-50.yaml', 50),   # Phase 5b: 50%
            ('virtual-service-canary-100.yaml', 100), # Phase 5c: 100%
        ]

        for filename, expected_weight in expected:
            vs = load_yaml(filename)
            routes = vs['spec']['http']

            # Find user-svc weight
            user_svc_weight = 0
            for route in routes:
                if route.get('match') and route['match'][0]['uri']['prefix'] == '/api/users':
                    for dest in route['route']:
                        if dest['destination']['host'] == 'user-svc':
                            user_svc_weight = dest['weight']

            assert user_svc_weight == expected_weight, \
                f"{filename}: expected {expected_weight}% to user-svc, got {user_svc_weight}%"

    def test_all_virtualservices_use_same_name(self):
        """All VirtualServices use the same name for kubectl apply replacement."""
        name = 'strangler-fig-routing'
        for filename in [
            'virtual-service-phase1.yaml',
            'virtual-service-phase4.yaml',
            'virtual-service-canary-10.yaml',
            'virtual-service-canary-50.yaml',
            'virtual-service-canary-100.yaml',
            'virtual-service-final.yaml',
        ]:
            vs = load_yaml(filename)
            assert vs['metadata']['name'] == name, \
                f"{filename}: name is '{vs['metadata']['name']}', expected '{name}'"

    def test_all_configs_reference_same_gateway(self):
        """All VirtualServices reference strangler-fig-gateway."""
        for filename in [
            'virtual-service-phase1.yaml',
            'virtual-service-phase4.yaml',
            'virtual-service-canary-10.yaml',
            'virtual-service-canary-50.yaml',
            'virtual-service-canary-100.yaml',
            'virtual-service-final.yaml',
        ]:
            vs = load_yaml(filename)
            assert 'strangler-fig-gateway' in vs['spec']['gateways'], \
                f"{filename}: doesn't reference strangler-fig-gateway"
