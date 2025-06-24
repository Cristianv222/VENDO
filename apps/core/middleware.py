"""
Middleware personalizado para el sistema VENDO
"""
import logging
import time
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from .models import Company, AuditLog
from .utils import get_client_ip
from .exceptions import (
    VendoBaseException, 
    CompanyNotFoundException, 
    InactiveCompanyException
)

logger = logging.getLogger(__name__)


class CompanyMiddleware(MiddlewareMixin):
    """
    Middleware para manejar el contexto de empresa en sistema multi-tenant
    """
    
    def process_request(self, request):
        """
        Procesa la request para establecer el contexto de empresa
        """
        # Saltar para rutas de autenticación y admin
        skip_paths = [
            '/admin/',
            '/auth/login/',
            '/auth/logout/',
            '/static/',
            '/media/',
            '/__debug__/',  # Debug toolbar
        ]
        
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Si el usuario no está autenticado, no procesamos empresa
        if not request.user.is_authenticated:
            return None
        
        try:
            # Obtener empresa del usuario o de la sesión
            company = self._get_user_company(request)
            
            if not company:
                # Si no hay empresa asignada, redirigir a selección de empresa
                if request.path != reverse('core:select_company'):
                    return redirect('core:select_company')
                return None
            
            # Verificar que la empresa esté activa
            if not company.is_active:
                raise InactiveCompanyException(company.business_name)
            
            # Establecer empresa en request y sesión
            request.company = company
            request.session['company_id'] = str(company.id)
            
            # En esquemas por módulo, no cambiamos esquema aquí
            # El router ya maneja los esquemas por app
            pass
            
        except VendoBaseException as e:
            logger.error(f"Error en CompanyMiddleware: {e}")
            messages.error(request, str(e))
            
            # Si es una request AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=400)
            
            # Cerrar sesión y redirigir al login
            logout(request)
            return redirect('auth:login')
        
        except Exception as e:
            logger.error(f"Error inesperado en CompanyMiddleware: {e}")
            messages.error(request, _('Error interno del sistema.'))
            logout(request)
            return redirect('auth:login')
        
        return None
    
    def _get_user_company(self, request):
        """
        Obtiene la empresa del usuario
        """
        # Primero intentar desde la sesión
        company_id = request.session.get('company_id')
        
        if company_id:
            try:
                return Company.objects.get(id=company_id, is_active=True)
            except Company.DoesNotExist:
                # Limpiar sesión si la empresa ya no existe
                request.session.pop('company_id', None)
        
        # Si el usuario tiene una empresa asignada directamente
        if hasattr(request.user, 'company') and request.user.company:
            return request.user.company
        
        # Si el usuario pertenece a una empresa a través de su perfil
        if hasattr(request.user, 'profile') and request.user.profile.company:
            return request.user.profile.company
        
        return None
    
    # En esquemas por módulo, el router maneja los esquemas automáticamente


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware para auditoría de acciones del usuario
    """
    
    # Métodos que requieren auditoría
    AUDIT_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    
    # Rutas que no requieren auditoría
    SKIP_PATHS = [
        '/admin/',
        '/static/',
        '/media/',
        '/__debug__/',
        '/auth/logout/',  # El logout ya se audita en la vista
    ]
    
    def process_request(self, request):
        """
        Marca el inicio de la request para medir tiempo
        """
        request._audit_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """
        Procesa la respuesta para crear logs de auditoría
        """
        # Saltar si no cumple condiciones para auditoría
        if not self._should_audit(request, response):
            return response
        
        try:
            # Crear log de auditoría
            self._create_audit_log(request, response)
        except Exception as e:
            logger.error(f"Error al crear log de auditoría: {e}")
        
        return response
    
    def _should_audit(self, request, response):
        """
        Determina si la request debe ser auditada
        """
        # No auditar si no hay usuario autenticado
        if not request.user.is_authenticated:
            return False
        
        # No auditar rutas específicas
        if any(request.path.startswith(path) for path in self.SKIP_PATHS):
            return False
        
        # Auditar métodos específicos
        if request.method in self.AUDIT_METHODS:
            return True
        
        # Auditar GET solo para vistas importantes
        if request.method == 'GET' and self._is_important_view(request):
            return True
        
        return False
    
    def _is_important_view(self, request):
        """
        Determina si una vista GET es importante para auditar
        """
        important_paths = [
            '/reports/',
            '/admin/',
            '/settings/',
        ]
        return any(request.path.startswith(path) for path in important_paths)
    
    def _create_audit_log(self, request, response):
        """
        Crea el log de auditoría
        """
        # Determinar acción basada en método HTTP
        action_map = {
            'GET': 'VIEW',
            'POST': 'CREATE',
            'PUT': 'UPDATE',
            'PATCH': 'UPDATE',
            'DELETE': 'DELETE',
        }
        
        action = action_map.get(request.method, 'VIEW')
        
        # Obtener información adicional
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = get_client_ip(request)
        
        # Calcular tiempo de procesamiento
        processing_time = None
        if hasattr(request, '_audit_start_time'):
            processing_time = time.time() - request._audit_start_time
        
        # Crear el log
        audit_data = {
            'user': request.user,
            'company': getattr(request, 'company', None),
            'action': action,
            'object_repr': f"{request.method} {request.path}",
            'ip_address': ip_address,
            'user_agent': user_agent,
            'changes': {
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'processing_time': processing_time,
            }
        }
        
        # Agregar datos POST si están disponibles (sin contraseñas)
        if request.method in ['POST', 'PUT', 'PATCH']:
            post_data = dict(request.POST)
            # Remover datos sensibles
            sensitive_fields = ['password', 'token', 'csrf', 'secret']
            for field in sensitive_fields:
                post_data.pop(field, None)
            
            if post_data:
                audit_data['changes']['form_data'] = post_data
        
        AuditLog.objects.create(**audit_data)


class SecurityMiddleware(MiddlewareMixin):
    """
    Middleware para seguridad adicional
    """
    
    def process_request(self, request):
        """
        Verifica aspectos de seguridad en la request
        """
        # Verificar headers de seguridad maliciosos
        if self._has_malicious_headers(request):
            logger.warning(f"Request maliciosa detectada desde {get_client_ip(request)}")
            return JsonResponse({'error': 'Request no válida'}, status=400)
        
        return None
    
    def process_response(self, request, response):
        """
        Agrega headers de seguridad a la respuesta
        """
        # Headers de seguridad
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
        }
        
        for header, value in security_headers.items():
            response[header] = value
        
        return response
    
    def _has_malicious_headers(self, request):
        """
        Verifica si la request tiene headers maliciosos
        """
        malicious_patterns = [
            'script',
            'javascript:',
            '<script',
            'onclick',
            'onerror',
        ]
        
        # Verificar en User-Agent y Referer
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        referer = request.META.get('HTTP_REFERER', '').lower()
        
        for pattern in malicious_patterns:
            if pattern in user_agent or pattern in referer:
                return True
        
        return False


class PerformanceMiddleware(MiddlewareMixin):
    """
    Middleware para monitoreo de rendimiento
    """
    
    def process_request(self, request):
        """
        Marca el inicio de la request
        """
        request._performance_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """
        Calcula y registra métricas de rendimiento
        """
        if not hasattr(request, '_performance_start_time'):
            return response
        
        # Calcular tiempo total
        total_time = time.time() - request._performance_start_time
        
        # Agregar header con tiempo de respuesta
        response['X-Response-Time'] = f"{total_time:.3f}s"
        
        # Log para requests lentas (más de 2 segundos)
        if total_time > 2.0:
            logger.warning(
                f"Request lenta detectada: {request.method} {request.path} "
                f"- {total_time:.3f}s - Usuario: {getattr(request.user, 'username', 'Anónimo')}"
            )
        
        return response