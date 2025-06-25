"""
Middleware personalizado para el sistema VENDO - CORREGIDO
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
            '/auth/',  # AGREGADO: Toda la ruta auth
            '/users/login/',
            '/users/logout/',
            '/users/password',  # AGREGADO: Para password reset
            '/static/',
            '/media/',
            '/robots.txt',
            '/health/',
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
                # Si no hay empresa asignada, verificar si hay empresas disponibles
                if self._has_available_companies(request.user):
                    # Redirigir a selección de empresa si no estamos ya ahí
                    if request.path != reverse('core:select_company'):
                        return redirect('core:select_company')
                else:
                    # No hay empresas disponibles
                    messages.error(
                        request,
                        _('No tiene acceso a ninguna empresa. Contacte al administrador.')
                    )
                    logout(request)
                    # CORREGIDO: Usar users:login en lugar de auth:login
                    return redirect('users:login')
                return None
            
            # Verificar que la empresa esté activa
            if not company.is_active:
                raise InactiveCompanyException(company.business_name)
            
            # Establecer empresa en request y sesión
            request.company = company
            request.session['company_id'] = str(company.id)
            
            # Establecer sucursal actual si existe
            branch = self._get_current_branch(request, company)
            if branch:
                request.current_branch = branch
            
        except VendoBaseException as e:
            logger.error(f"Error en CompanyMiddleware: {e}")
            messages.error(request, str(e))
            
            # Si es una request AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=400)
            
            # Cerrar sesión y redirigir al login
            logout(request)
            # CORREGIDO: Usar users:login en lugar de auth:login
            return redirect('users:login')
        
        except Exception as e:
            logger.error(f"Error inesperado en CompanyMiddleware: {e}")
            
            # Si es una request AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Error interno del sistema'}, status=500)
            
            # Para requests normales, mostrar mensaje y redirigir
            try:
                messages.error(request, _('Error interno del sistema.'))
                logout(request)
                # CORREGIDO: Usar users:login en lugar de auth:login
                return redirect('users:login')
            except Exception:
                # Si incluso el redirect falla, usar redirect básico
                return redirect('users:login')
        
        return None
    
    def _get_user_company(self, request):
        """
        Obtiene la empresa del usuario - VERSIÓN SEGURA
        """
        try:
            # Primero intentar desde la sesión
            company_id = request.session.get('company_id')
            
            if company_id:
                try:
                    company = Company.objects.get(id=company_id, is_active=True)
                    # Verificar que el usuario tiene acceso a esta empresa
                    if self._user_has_access_to_company(request.user, company):
                        return company
                    else:
                        # Usuario no tiene acceso, limpiar sesión
                        request.session.pop('company_id', None)
                except Company.DoesNotExist:
                    # Limpiar sesión si la empresa ya no existe
                    request.session.pop('company_id', None)
            
            # Si el usuario tiene una empresa asignada directamente
            if hasattr(request.user, 'company') and request.user.company:
                if request.user.company.is_active:
                    return request.user.company
            
            # CORREGIDO: Manejo seguro del perfil de usuario
            # Si el usuario pertenece a una empresa a través de su perfil
            if hasattr(request.user, 'profile'):
                profile = request.user.profile
                # Solo acceder a company si el atributo existe
                if hasattr(profile, 'company') and profile.company:
                    if profile.company.is_active:
                        # Sincronizar con sesión
                        request.session['company_id'] = str(profile.company.id)
                        return profile.company
            
            return None
            
        except Exception as e:
            logger.error(f"Error creando audit log para login: {e}")
            return None
    
    def _get_current_branch(self, request, company):
        """
        Obtiene la sucursal actual del usuario
        """
        try:
            # Intentar obtener de la sesión
            branch_id = request.session.get('current_branch_id')
            if branch_id:
                try:
                    return company.branches.get(id=branch_id, is_active=True)
                except:
                    request.session.pop('current_branch_id', None)
            
            # Obtener sucursal principal por defecto
            main_branch = company.branches.filter(is_main=True, is_active=True).first()
            if main_branch:
                request.session['current_branch_id'] = str(main_branch.id)
                return main_branch
            
            # Si no hay principal, obtener la primera activa
            first_branch = company.branches.filter(is_active=True).first()
            if first_branch:
                request.session['current_branch_id'] = str(first_branch.id)
                return first_branch
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo sucursal: {e}")
            return None
    
    def _user_has_access_to_company(self, user, company):
        """
        Verifica si el usuario tiene acceso a la empresa
        """
        try:
            # Superusuarios tienen acceso a todo
            if user.is_superuser:
                return True
            
            # Por ahora permitir acceso a todas las empresas activas
            # Esto se modificará cuando implementemos el módulo completo de usuarios
            return company.is_active
            
        except Exception as e:
            logger.error(f"Error verificando acceso a empresa: {e}")
            return False
    
    def _has_available_companies(self, user):
        """
        Verifica si el usuario tiene empresas disponibles
        """
        try:
            if user.is_superuser:
                return Company.objects.filter(is_active=True).exists()
            
            # Por ahora verificar si hay empresas activas
            return Company.objects.filter(is_active=True).exists()
            
        except Exception as e:
            logger.error(f"Error verificando empresas disponibles: {e}")
            return False


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware para auditoría de acciones del usuario - VERSIÓN SEGURA
    """
    
    # Métodos que requieren auditoría
    AUDIT_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    
    # Rutas que no requieren auditoría
    SKIP_PATHS = [
        '/admin/',
        '/static/',
        '/media/',
        '/health/',
        '/robots.txt',
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
            # Crear log de auditoría de forma segura
            self._create_audit_log_safe(request, response)
        except Exception as e:
            logger.error(f"Error creando audit log para logout: {e}")
        
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
            '/companies/',
            '/branches/',
        ]
        return any(request.path.startswith(path) for path in important_paths)
    
    def _create_audit_log_safe(self, request, response):
        """
        Crea el log de auditoría de forma segura
        """
        try:
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
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]  # Truncar
            ip_address = get_client_ip(request)
            
            # Calcular tiempo de procesamiento
            processing_time = None
            if hasattr(request, '_audit_start_time'):
                processing_time = time.time() - request._audit_start_time
            
            # Preparar datos extra de forma segura
            extra_data = {
                'method': request.method,
                'path': request.path[:200],  # Truncar
                'status_code': response.status_code,
            }
            
            if processing_time is not None:
                extra_data['processing_time'] = round(processing_time, 3)
            
            # Agregar datos POST si están disponibles (sin contraseñas)
            if request.method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'POST'):
                try:
                    post_data = dict(request.POST)
                    # Remover datos sensibles
                    sensitive_fields = ['password', 'token', 'csrf', 'secret', 'key']
                    for field in list(post_data.keys()):
                        if any(sensitive in field.lower() for sensitive in sensitive_fields):
                            post_data.pop(field, None)
                    
                    if post_data:
                        extra_data['form_data'] = post_data
                except Exception:
                    pass  # Ignorar errores al procesar POST data
            
            # Crear el log de auditoría
            AuditLog.objects.create(
                user=request.user,
                company=getattr(request, 'company', None),
                action=action,
                object_repr=f"{request.method} {request.path}"[:255],  # Truncar
                ip_address=ip_address[:45],  # Truncar IP
                user_agent=user_agent,
                extra_data=extra_data
            )
            
        except Exception as e:
            logger.error(f"Error en _create_audit_log_safe: {e}")


class SecurityMiddleware(MiddlewareMixin):
    """
    Middleware para seguridad adicional
    """
    
    def process_request(self, request):
        """
        Verifica aspectos de seguridad en la request
        """
        try:
            # Verificar headers de seguridad maliciosos
            if self._has_malicious_headers(request):
                logger.warning(f"Request maliciosa detectada desde {get_client_ip(request)}")
                return JsonResponse({'error': 'Request no válida'}, status=400)
        except Exception as e:
            logger.error(f"Error en SecurityMiddleware.process_request: {e}")
        
        return None
    
    def process_response(self, request, response):
        """
        Agrega headers de seguridad a la respuesta
        """
        try:
            # Headers de seguridad
            security_headers = {
                'X-Content-Type-Options': 'nosniff',
                'X-XSS-Protection': '1; mode=block',
                'Referrer-Policy': 'strict-origin-when-cross-origin',
            }
            
            # En desarrollo, usar SAMEORIGIN para debug toolbar
            if settings.DEBUG:
                security_headers['X-Frame-Options'] = 'SAMEORIGIN'
            else:
                security_headers['X-Frame-Options'] = 'DENY'
            
            for header, value in security_headers.items():
                response[header] = value
                
        except Exception as e:
            logger.error(f"Error en SecurityMiddleware.process_response: {e}")
        
        return response
    
    def _has_malicious_headers(self, request):
        """
        Verifica si la request tiene headers maliciosos
        """
        try:
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
            
        except Exception as e:
            logger.error(f"Error verificando headers maliciosos: {e}")
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
        try:
            if not hasattr(request, '_performance_start_time'):
                return response
            
            # Calcular tiempo total
            total_time = time.time() - request._performance_start_time
            
            # Agregar header con tiempo de respuesta
            response['X-Response-Time'] = f"{total_time:.3f}s"
            
            # Log para requests lentas (más de 2 segundos)
            if total_time > 2.0:
                username = getattr(request.user, 'username', 'Anónimo') if hasattr(request, 'user') else 'Anónimo'
                logger.warning(
                    f"Request lenta detectada: {request.method} {request.path} "
                    f"- {total_time:.3f}s - Usuario: {username}"
                )
                
        except Exception as e:
            logger.error(f"Error en PerformanceMiddleware: {e}")
        
        return response