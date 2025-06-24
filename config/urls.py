"""
URL configuration for VENDO project.
Sistema de Ventas con Integración SRI

URLs principales que enrutan a todas las aplicaciones del sistema.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.defaults import page_not_found, server_error, permission_denied
from django.http import HttpResponse


def health_check(request):
    """Vista simple de health check"""
    return HttpResponse("OK", content_type="text/plain")


# ==========================================
# URL PATTERNS PRINCIPALES
# ==========================================

urlpatterns = [
    # ==========================================
    # ADMIN DE DJANGO
    # ==========================================
    path('admin/', admin.site.urls),
    
    # ==========================================
    # REDIRECCIÓN RAÍZ AL DASHBOARD
    # ==========================================
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
    
    # ==========================================
    # MÓDULO CORE (Dashboard y funcionalidades base)
    # ==========================================
    path('', include('apps.core.urls')),  # Incluye dashboard, empresas, sucursales
    
    # ==========================================
    # MÓDULO USERS (cuando esté listo)
    # ==========================================
    # path('auth/', include('apps.users.urls')),
    # path('users/', include('apps.users.urls')),
    
    # ==========================================
    # MÓDULO SETTINGS (cuando esté listo)
    # ==========================================
    # path('settings/', include('apps.settings.urls')),
    
    # ==========================================
    # MÓDULOS DE NEGOCIO (cuando estén listos)
    # ==========================================
    # path('pos/', include('apps.pos.urls')),
    # path('inventory/', include('apps.inventory.urls')),
    # path('invoicing/', include('apps.invoicing.urls')),
    # path('purchases/', include('apps.purchases.urls')),
    # path('accounting/', include('apps.accounting.urls')),
    # path('quotations/', include('apps.quotations.urls')),
    # path('reports/', include('apps.reports.urls')),
    
    # ==========================================
    # HEALTH CHECK SIMPLE
    # ==========================================
    path('health/', health_check, name='health_check'),
]

# ==========================================
# API URLS (VERSIÓN 1)
# ==========================================

api_v1_patterns = [
    # API del Core
    path('core/', include('apps.core.urls')),
    
    # APIs de otros módulos (cuando estén listos)
    # path('users/', include('apps.users.urls')),
    # path('pos/', include('apps.pos.urls')),
    # path('inventory/', include('apps.inventory.urls')),
    # path('invoicing/', include('apps.invoicing.urls')),
    # path('purchases/', include('apps.purchases.urls')),
    # path('accounting/', include('apps.accounting.urls')),
    # path('quotations/', include('apps.quotations.urls')),
    # path('reports/', include('apps.reports.urls')),
]

# Agregar APIs a las URLs principales
urlpatterns += [
    path('api/v1/', include(api_v1_patterns)),
]

# ==========================================
# CONFIGURACIÓN PARA DESARROLLO
# ==========================================

if settings.DEBUG:
    # Servir archivos media en desarrollo
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Django Debug Toolbar
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        try:
            import debug_toolbar
            urlpatterns = [
                path('__debug__/', include(debug_toolbar.urls)),
            ] + urlpatterns
        except ImportError:
            pass
    
    # URLs adicionales para desarrollo
    urlpatterns += [
        # Página de prueba
        path('test/', lambda request: HttpResponse('<h1>🚀 VENDO - Sistema funcionando!</h1><p>Debug: ON</p>')),
        
        # Información del sistema
        path('system-info/', lambda request: HttpResponse(f'''
        <h1>VENDO System Info</h1>
        <ul>
            <li>Debug: {settings.DEBUG}</li>
            <li>Database: {list(settings.DATABASES.keys())}</li>
            <li>Apps: {len(settings.INSTALLED_APPS)}</li>
            <li>Middleware: {len(settings.MIDDLEWARE)}</li>
            <li>Esquemas: {len(settings.DATABASE_APPS_MAPPING)}</li>
        </ul>
        ''')),
    ]

# ==========================================
# HANDLERS DE ERROR PERSONALIZADOS
# ==========================================

# Estas funciones se ejecutarán cuando ocurran errores HTTP
handler400 = 'apps.core.views.custom_400'  # Bad Request
handler403 = 'apps.core.views.custom_403'  # Forbidden
handler404 = 'apps.core.views.custom_404'  # Not Found
handler500 = 'apps.core.views.custom_500'  # Internal Server Error

# ==========================================
# URLs FUTURAS (preparadas para descommentar)
# ==========================================

"""
URLS para agregar cuando los módulos estén listos:

# AUTENTICACIÓN Y USUARIOS
path('login/', include('apps.users.urls')),
path('logout/', LogoutView.as_view(), name='logout'),
path('profile/', include('apps.users.urls')),

# PUNTO DE VENTA
path('pos/', include('apps.pos.urls')),
path('sales/', include('apps.pos.urls')),
path('cash-register/', include('apps.pos.urls')),

# INVENTARIO
path('inventory/', include('apps.inventory.urls')),
path('products/', include('apps.inventory.urls')),
path('categories/', include('apps.inventory.urls')),
path('stock/', include('apps.inventory.urls')),

# FACTURACIÓN ELECTRÓNICA
path('invoicing/', include('apps.invoicing.urls')),
path('invoices/', include('apps.invoicing.urls')),
path('credit-notes/', include('apps.invoicing.urls')),
path('electronic-documents/', include('apps.invoicing.urls')),

# COMPRAS
path('purchases/', include('apps.purchases.urls')),
path('suppliers/', include('apps.purchases.urls')),
path('purchase-orders/', include('apps.purchases.urls')),

# CONTABILIDAD
path('accounting/', include('apps.accounting.urls')),
path('accounts-receivable/', include('apps.accounting.urls')),
path('accounts-payable/', include('apps.accounting.urls')),

# COTIZACIONES
path('quotations/', include('apps.quotations.urls')),
path('quotes/', include('apps.quotations.urls')),

# REPORTES
path('reports/', include('apps.reports.urls')),
path('analytics/', include('apps.reports.urls')),
path('dashboard-reports/', include('apps.reports.urls')),

# CONFIGURACIONES
path('settings/', include('apps.settings.urls')),
path('company-settings/', include('apps.settings.urls')),
path('tax-settings/', include('apps.settings.urls')),

# INTEGRACIONES EXTERNAS
path('sri/', include('apps.invoicing.sri_urls')),  # URLs específicas SRI
path('integrations/', include('apps.settings.integration_urls')),

# WEBHOOKS (para integraciones)
path('webhooks/', include('apps.core.webhook_urls')),

# API V2 (futura)
path('api/v2/', include('config.api_v2_urls')),
"""

# ==========================================
# CONFIGURACIÓN ADICIONAL DE URLs
# ==========================================

# Personalizar el admin
admin.site.site_header = "VENDO - Administración"
admin.site.site_title = "VENDO Admin"
admin.site.index_title = "Panel de Administración"

# ==========================================
# PATRONES DE URL CONDICIONALES
# ==========================================

# Agregar URLs según feature flags
if hasattr(settings, 'FEATURE_FLAGS'):
    # API v2 si está habilitada
    if settings.FEATURE_FLAGS.get('API_V2', False):
        # urlpatterns += [path('api/v2/', include('config.api_v2_urls'))]
        pass
    
    # Integraciones si están habilitadas
    if settings.FEATURE_FLAGS.get('INTEGRATIONS', False):
        # urlpatterns += [path('integrations/', include('apps.integrations.urls'))]
        pass
    
    # Aplicación móvil si está habilitada
    if settings.FEATURE_FLAGS.get('MOBILE_APP', False):
        # urlpatterns += [path('mobile-api/', include('apps.mobile.urls'))]
        pass

# ==========================================
# INFORMACIÓN DE DEPURACIÓN
# ==========================================

if settings.DEBUG:
    print("=== URLs CONFIGURADAS ===")
    print(f"✅ URLs principales configuradas: {len(urlpatterns)} patrones")
    print(f"✅ Admin: /admin/")
    print(f"✅ Dashboard: /dashboard/")
    print(f"✅ API v1: /api/v1/")
    print(f"✅ Health check: /health/")
    print(f"✅ Debug toolbar: /__debug__/")
    print("========================")