"""
URL configuration for VENDO project.
Sistema de Ventas con Integración SRI y Esquemas PostgreSQL
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# Vista simple para redireccionar la raíz
def redirect_to_users(request):
    """Redireccionar la URL raíz al dashboard de usuarios."""
    return redirect('users:dashboard')

urlpatterns = [
    # ==========================================
    # URLS PRINCIPALES
    # ==========================================
    
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Redirección desde la raíz
    path('', redirect_to_users, name='home'),
    
    # ==========================================
    # APPS DEL SISTEMA
    # ==========================================
    
    # Usuarios (autenticación, roles, permisos)
    path('users/', include('apps.users.urls')),
    
    # Apps de negocio (agregar cuando estén listas)
    # path('pos/', include('apps.pos.urls')),
    # path('inventory/', include('apps.inventory.urls')),
    # path('invoicing/', include('apps.invoicing.urls')),
    # path('purchases/', include('apps.purchases.urls')),
    # path('accounting/', include('apps.accounting.urls')),
    # path('quotations/', include('apps.quotations.urls')),
    # path('reports/', include('apps.reports.urls')),
    # path('settings/', include('apps.settings.urls')),
    
    # ==========================================
    # API GLOBAL (OPCIONAL)
    # ==========================================
    
    # API general del sistema (si quieres un endpoint unificado)
    # path('api/', include('apps.core.api_urls')),  # Crear cuando sea necesario
]

# ==========================================
# CONFIGURACIONES PARA DESARROLLO
# ==========================================

if settings.DEBUG:
    # Django Debug Toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        # Debug toolbar no está instalado
        pass
    
    # Servir archivos media en desarrollo
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ==========================================
# HANDLERS DE ERROR PERSONALIZADOS (OPCIONAL)
# ==========================================

# Cuando crees las vistas de error personalizadas, descomenta:
# handler404 = 'apps.core.views.page_not_found'
# handler500 = 'apps.core.views.server_error'
# handler403 = 'apps.core.views.permission_denied'
# handler400 = 'apps.core.views.bad_request'