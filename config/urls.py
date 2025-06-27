"""
URLs principales del proyecto VENDO - VERSIÓN CORREGIDA
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import HttpResponse

# Vista simple para redirección inteligente
def smart_redirect(request):
    """Redirección inteligente basada en autenticación"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return redirect('users:login')

# Vista simple para robots.txt
def robots_txt(request):
    """Robots.txt básico"""
    content = """User-agent: *
Disallow: /admin/
Disallow: /auth/
Disallow: /api/
Allow: /
"""
    return HttpResponse(content, content_type='text/plain')

urlpatterns = [
    # ==========================================
    # AUTENTICACIÓN DJANGO - PRIORIDAD MÁXIMA
    # ==========================================
    
    # CRÍTICO: URLs de autenticación de Django (namespace 'auth')
    # DEBE ir PRIMERO para resolver todas las referencias a 'auth:'
    path('auth/', include('django.contrib.auth.urls')),
    
    # ==========================================
    # ADMIN Y NAVEGACIÓN PRINCIPAL
    # ==========================================
    
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Redirección inteligente de la raíz
    path('', smart_redirect, name='home'),
    
    # Compatibilidad para URL /login/ (redirige a la correcta)
    path('login/', lambda request: redirect('users:login'), name='login_redirect'),
    
    # Robots.txt para SEO
    path('robots.txt', robots_txt, name='robots_txt'),
    
    # ==========================================
    # MÓDULOS DE LA APLICACIÓN - ORDEN CORREGIDO
    # ==========================================
    
    # Usuarios y autenticación personalizada
    path('users/', include('apps.users.urls')),
    
    # Módulos de negocio (ANTES del core para evitar conflictos)
    path('inventory/', include('apps.inventory.urls')),
    
    # Core (dashboard, empresas, sucursales)
    # IMPORTANTE: Va después de los módulos específicos
    path('', include('apps.core.urls')),
    
    # ==========================================
    # MÓDULOS FUTUROS (preparado para expansión)
    # ==========================================
    
    # Configuraciones del sistema
    # path('settings/', include('apps.settings.urls')),
    
    # Módulos de negocio (descomentar cuando estén listos)
    # path('pos/', include('apps.pos.urls')),
    # path('invoicing/', include('apps.invoicing.urls')),
    # path('purchases/', include('apps.purchases.urls')),
    # path('accounting/', include('apps.accounting.urls')),
    # path('quotations/', include('apps.quotations.urls')),
    # path('reports/', include('apps.reports.urls')),
    
    # APIs externas y webhooks
    # path('api/v1/', include('apps.api.urls')),
    # path('webhooks/', include('apps.webhooks.urls')),
]

# ==========================================
# ARCHIVOS ESTÁTICOS Y MEDIA (DESARROLLO)
# ==========================================

if settings.DEBUG:
    # Servir archivos media y static en desarrollo
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Django Debug Toolbar (con manejo de errores)
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        try:
            import debug_toolbar
            urlpatterns = [
                path('__debug__/', include(debug_toolbar.urls)),
            ] + urlpatterns
        except ImportError:
            # Debug toolbar no disponible, continuar sin él
            pass
    
    # URLs adicionales para desarrollo
    urlpatterns += [
        # URL para testing de errores (solo en desarrollo)
        path('test-404/', lambda request: None),  # Genera 404 automáticamente
    ]

# ==========================================
# CONFIGURACIÓN PARA PRODUCCIÓN
# ==========================================

if not settings.DEBUG:
    # En producción, agregar URLs adicionales
    urlpatterns += [
        # Sitemap XML (cuando se implemente)
        # path('sitemap.xml', sitemap_view, name='sitemap'),
        
        # Configuraciones de seguridad
        # path('.well-known/security.txt', security_txt_view, name='security_txt'),
    ]

# ==========================================
# HANDLERS DE ERROR PERSONALIZADOS
# ==========================================

# Páginas de error personalizadas (solo si existen las vistas)
# handler400 = 'apps.core.views.custom_400'
# handler403 = 'apps.core.views.custom_403'
# handler404 = 'apps.core.views.custom_404'
# handler500 = 'apps.core.views.custom_500'