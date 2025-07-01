from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
import logging

logger = logging.getLogger(__name__)

class SRIException(Exception):
    """Excepción base para errores del SRI"""
    def __init__(self, message, error_code=None, details=None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class SRIConnectionError(SRIException):
    """Error de conexión con los servicios del SRI"""
    pass

class SRICertificateError(SRIException):
    """Error relacionado con el certificado digital"""
    pass

class SRISignatureError(SRIException):
    """Error en la firma digital del XML"""
    pass

class SRIValidationError(SRIException):
    """Error de validación en el SRI"""
    pass

class SRIAuthorizationError(SRIException):
    """Error al obtener autorización del SRI"""
    pass

class InvoiceCreationError(Exception):
    """Error al crear una factura"""
    def __init__(self, message, field_errors=None):
        self.message = message
        self.field_errors = field_errors or {}
        super().__init__(self.message)

class EmailServiceError(Exception):
    """Error en el servicio de email"""
    pass

class PDFGenerationError(Exception):
    """Error al generar PDF"""
    pass

class XMLGenerationError(Exception):
    """Error al generar XML"""
    pass

class ConfigurationError(Exception):
    """Error de configuración del sistema"""
    pass

class CompanyAccessError(Exception):
    """Error de acceso a recursos de empresa"""
    pass

class InvoiceStateError(Exception):
    """Error relacionado con el estado de la factura"""
    def __init__(self, message, current_state=None, required_state=None):
        self.message = message
        self.current_state = current_state
        self.required_state = required_state
        super().__init__(self.message)

# Exception handler personalizado para DRF
def custom_exception_handler(exc, context):
    """Handler personalizado para excepciones"""
    
    # Log de la excepción
    logger.error(f"Exception in {context.get('view', 'Unknown')}: {exc}", exc_info=True)
    
    # Manejar excepciones personalizadas
    if isinstance(exc, SRIException):
        error_response = {
            'error': True,
            'error_type': 'SRI_ERROR',
            'message': exc.message,
            'error_code': exc.error_code,
            'details': exc.details
        }
        
        if isinstance(exc, SRIConnectionError):
            return Response(error_response, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        elif isinstance(exc, SRICertificateError):
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(exc, SRIValidationError):
            return Response(error_response, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        else:
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    if isinstance(exc, InvoiceCreationError):
        error_response = {
            'error': True,
            'error_type': 'INVOICE_CREATION_ERROR',
            'message': exc.message,
            'field_errors': exc.field_errors
        }
        return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
    
    if isinstance(exc, InvoiceStateError):
        error_response = {
            'error': True,
            'error_type': 'INVOICE_STATE_ERROR',
            'message': exc.message,
            'current_state': exc.current_state,
            'required_state': exc.required_state
        }
        return Response(error_response, status=status.HTTP_409_CONFLICT)
    
    if isinstance(exc, CompanyAccessError):
        error_response = {
            'error': True,
            'error_type': 'ACCESS_DENIED',
            'message': str(exc)
        }
        return Response(error_response, status=status.HTTP_403_FORBIDDEN)
    
    if isinstance(exc, ConfigurationError):
        error_response = {
            'error': True,
            'error_type': 'CONFIGURATION_ERROR',
            'message': str(exc)
        }
        return Response(error_response, status=status.HTTP_412_PRECONDITION_FAILED)
    
    # Manejar ValidationError de Django
    if isinstance(exc, DjangoValidationError):
        error_response = {
            'error': True,
            'error_type': 'VALIDATION_ERROR',
            'message': 'Error de validación',
            'details': exc.message_dict if hasattr(exc, 'message_dict') else [str(exc)]
        }
        return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
    
    # Usar el handler por defecto para otras excepciones
    response = exception_handler(exc, context)
    
    if response is not None:
        # Personalizar la respuesta de error
        if response.status_code >= 500:
            custom_response_data = {
                'error': True,
                'error_type': 'INTERNAL_ERROR',
                'message': 'Error interno del servidor',
                'details': response.data if hasattr(response, 'data') else None
            }
        else:
            custom_response_data = {
                'error': True,
                'error_type': 'CLIENT_ERROR',
                'message': 'Error en la solicitud',
                'details': response.data if hasattr(response, 'data') else None
            }
        
        response.data = custom_response_data
    
    return response

# Decorador para manejar excepciones en servicios
def handle_service_exceptions(func):
    """Decorador para manejar excepciones en servicios"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SRIException as e:
            logger.error(f"SRI Error in {func.__name__}: {e.message}")
            return {
                'success': False,
                'error_type': 'SRI_ERROR',
                'message': e.message,
                'error_code': e.error_code,
                'details': e.details
            }
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error_type': 'INTERNAL_ERROR',
                'message': f'Error interno en {func.__name__}: {str(e)}'
            }
    return wrapper

# Context manager para manejar errores SRI
class SRIErrorHandler:
    """Context manager para manejar errores del SRI"""
    
    def __init__(self, operation_name, company=None):
        self.operation_name = operation_name
        self.company = company
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        
        # Log del error
        company_name = self.company.razon_social if self.company else 'Unknown'
        logger.error(f"SRI Error in {self.operation_name} for {company_name}: {exc_val}")
        
        # Convertir excepciones comunes a SRIException
        if "connection" in str(exc_val).lower() or "timeout" in str(exc_val).lower():
            raise SRIConnectionError(
                f"Error de conexión en {self.operation_name}",
                error_code="CONNECTION_ERROR",
                details={'original_error': str(exc_val)}
            )
        elif "certificate" in str(exc_val).lower() or "cert" in str(exc_val).lower():
            raise SRICertificateError(
                f"Error de certificado en {self.operation_name}",
                error_code="CERTIFICATE_ERROR",
                details={'original_error': str(exc_val)}
            )
        elif "signature" in str(exc_val).lower() or "sign" in str(exc_val).lower():
            raise SRISignatureError(
                f"Error de firma en {self.operation_name}",
                error_code="SIGNATURE_ERROR",
                details={'original_error': str(exc_val)}
            )
        
        # Re-raise la excepción original si no se puede manejar
        return False