from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint for Kubernetes readiness/liveness probes."""
    return JsonResponse({"status": "healthy", "service": "monolith"})


urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
]
