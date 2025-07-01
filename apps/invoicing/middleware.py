import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from .models import SRILog
from .exceptions import CompanyAccessError, ConfigurationError

logger = logging.getLogger(__name__)

class InvoicingLoggingMiddleware(MiddlewareMixin):
    """Middleware para logging de operaciones de facturación"""
    
    def process_request(self, request):
        # Marcar inicio de request
        request._start_time = time.time()
        
        # Log de requests a endpoints de facturación
        if '/api/invoicing/' in request.path:
            logger.info(f"Invoicing API Request: {request.method} {request.path} - User: {request.user}")
    
    def process_response(self, request, response):
        # Calcular tiempo de respuesta
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            
            # Log de responses lentas en facturación
            if '/api/invoicing/' in request.path and duration > 5:
                logger.warning(
                    f"Slow Invoicing Request: {request.method} {request.path} - "
                    f"Duration: {duration:.2f}s - Status: {response.status_code}"
                )
        
        return response

class CompanyAccessMiddleware(MiddlewareMixin):
    """Middleware para verificar acceso a empresa en rutas de facturación"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Solo aplicar a rutas de facturación
        if not request.path.startswith('/invoicing/') and not request.path.startswith('/api/invoicing/'):
            return None
        
        # Saltar para usuarios no autenticados (se manejará en las vistas)
        if not request.user.is_authenticated:
            return None
        
        # Verificar que el usuario tenga empresa asignada
        if not hasattr(request.user, 'company') or not request.user.company:
            logger.warning(f"User {request.user.username} tried to access invoicing without company")
            
            if request.path.startswith('/api/'):
                return JsonResponse({
                    'error': True,
                    'error_type': 'NO_COMPANY',
                    'message': 'Usuario no pertenece a ninguna empresa'
                }, status=403)
            else:
                raise CompanyAccessError("Usuario no pertenece a ninguna empresa")
        
        # Agregar empresa al request para fácil acceso
        request.company = request.user.company
        return None

class SRIRateLimitMiddleware(MiddlewareMixin):
    """Middleware para limitar requests al SRI por empresa"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit = 10  # requests per minute
        self.window = 60  # seconds
        super().__init__(get_response)
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Solo aplicar a endpoints que interactúan con SRI
        sri_endpoints = [
            '/api/invoicing/invoices/',
            '/api/invoicing/sri-configuration/test-sri-connection/',
            '/invoicing/invoices/resend-sri/',
            '/invoicing/invoices/get-authorization/'
        ]
        
        is_sri_endpoint = any(request.path.startswith(endpoint) for endpoint in sri_endpoints)
        
        if not is_sri_endpoint or not request.user.is_authenticated:
            return None
        
        company_id = request.user.company.id if hasattr(request.user, 'company') else None
        if not company_id:
            return None
        
        # Cache key para rate limiting
        cache_key = f"sri_rate_limit_{company_id}"
        
        # Obtener contador actual
        current_requests = cache.get(cache_key, 0)
        
        if current_requests >= self.rate_limit:
            logger.warning(f"Rate limit exceeded for company {company_id}")
            
            if request.path.startswith('/api/'):
                return JsonResponse({
                    'error': True,
                    'error_type': 'RATE_LIMIT_EXCEEDED',
                    'message': f'Límite de {self.rate_limit} requests por minuto excedido'
                }, status=429)
            else:
                return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
        
        # Incrementar contador
        cache.set(cache_key, current_requests + 1, self.window)
        
        return None

class SRIMaintenanceMiddleware(MiddlewareMixin):
    """Middleware para manejar mantenimiento del SRI"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Verificar si hay mantenimiento programado
        maintenance_key = "sri_maintenance_mode"
        maintenance_info = cache.get(maintenance_key)
        
        if not maintenance_info:
            return None
        
        # Solo aplicar a operaciones SRI
        sri_operations = [
            'resend_to_sri',
            'get_authorization', 
            'test_sri_connection',
            'create'  # crear facturas
        ]
        
        view_name = getattr(view_func, '__name__', '')
        if not any(op in view_name for op in sri_operations):
            return None
        
        logger.info(f"SRI maintenance mode active - blocking {view_name}")
        
        if request.path.startswith('/api/'):
            return JsonResponse({
                'error': True,
                'error_type': 'MAINTENANCE_MODE',
                'message': maintenance_info.get('message', 'SRI en mantenimiento'),
                'estimated_end': maintenance_info.get('estimated_end')
            }, status=503)
        else:
            return JsonResponse({
                'error': 'SRI en mantenimiento',
                'message': maintenance_info.get('message', 'Servicio temporalmente no disponible')
            }, status=503)

class InvoiceAuditMiddleware(MiddlewareMixin):
    """Middleware para auditoría de operaciones de facturación"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Solo auditar operaciones críticas
        audit_operations = [
            'create',
            'update', 
            'delete',
            'resend_to_sri',
            'send_email'
        ]
        
        view_name = getattr(view_func, '__name__', '')
        should_audit = any(op in view_name for op in audit_operations)
        
        if should_audit and request.user.is_authenticated:
            # Almacenar información para auditoría
            request._audit_info = {
                'user': request.user,
                'company': getattr(request.user, 'company', None),
                'operation': view_name,
                'path': request.path,
                'method': request.method,
                'timestamp': timezone.now(),
                'ip_address': self.get_client_ip(request)
            }
        
        return None
    
    def process_response(self, request, response):
        if hasattr(request, '_audit_info'):
            audit_info = request._audit_info
            
            # Log de auditoría
            logger.info(
                f"Audit: {audit_info['user'].username} performed {audit_info['operation']} "
                f"from {audit_info['ip_address']} - Status: {response.status_code}"
            )
            
            # Aquí se podría guardar en una tabla de auditoría
            # AuditLog.objects.create(**audit_info, status_code=response.status_code)
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class SRIErrorTrackingMiddleware(MiddlewareMixin):
    """Middleware para tracking de errores del SRI"""
    
    def process_exception(self, request, exception):
        # Solo procesar excepciones relacionadas con SRI
        if not request.path.startswith('/invoicing/') and not request.path.startswith('/api/invoicing/'):
            return None
        
        from .exceptions import SRIException
        
        if isinstance(exception, SRIException):
            company = getattr(request.user, 'company', None) if request.user.is_authenticated else None
            
            if company:
                # Crear log de error
                try:
                    SRILog.objects.create(
                        company=company,
                        clave_acceso='',
                        proceso='MIDDLEWARE_ERROR',
                        estado='ERROR',
                        error_message=str(exception),
                        response_data={
                            'error_type': exception.__class__.__name__,
                            'error_code': getattr(exception, 'error_code', None),
                            'path': request.path,
                            'method': request.method
                        }
                    )
                except Exception as e:
                    logger.error(f"Error creating SRI log: {str(e)}")
            
            # Log del error
            logger.error(f"SRI Exception in {request.path}: {exception}")
        
        return None