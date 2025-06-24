"""
Excepciones personalizadas para el sistema VENDO
"""
from django.utils.translation import gettext_lazy as _


class VendoBaseException(Exception):
    """
    Excepción base para todas las excepciones del sistema VENDO
    """
    def __init__(self, message=None, code=None, details=None):
        self.message = message or _('Ha ocurrido un error en el sistema.')
        self.code = code or 'vendo_error'
        self.details = details or {}
        super().__init__(self.message)


class CompanyNotFoundException(VendoBaseException):
    """
    Excepción lanzada cuando no se encuentra una empresa
    """
    def __init__(self, company_id=None):
        message = _('Empresa no encontrada.')
        if company_id:
            message = _('Empresa con ID %(company_id)s no encontrada.') % {'company_id': company_id}
        super().__init__(message=message, code='company_not_found')


class BranchNotFoundException(VendoBaseException):
    """
    Excepción lanzada cuando no se encuentra una sucursal
    """
    def __init__(self, branch_id=None):
        message = _('Sucursal no encontrada.')
        if branch_id:
            message = _('Sucursal con ID %(branch_id)s no encontrada.') % {'branch_id': branch_id}
        super().__init__(message=message, code='branch_not_found')


class SchemaException(VendoBaseException):
    """
    Excepción relacionada con esquemas de base de datos
    """
    def __init__(self, schema_name=None, operation=None):
        message = _('Error en operación de esquema.')
        if schema_name and operation:
            message = _('Error al %(operation)s el esquema %(schema_name)s.') % {
                'operation': operation,
                'schema_name': schema_name
            }
        super().__init__(message=message, code='schema_error')


class InvalidRUCException(VendoBaseException):
    """
    Excepción para RUC inválido
    """
    def __init__(self, ruc=None):
        message = _('RUC inválido.')
        if ruc:
            message = _('El RUC %(ruc)s no es válido.') % {'ruc': ruc}
        super().__init__(message=message, code='invalid_ruc')


class DuplicateCompanyException(VendoBaseException):
    """
    Excepción para empresa duplicada
    """
    def __init__(self, ruc=None):
        message = _('Ya existe una empresa registrada.')
        if ruc:
            message = _('Ya existe una empresa con RUC %(ruc)s.') % {'ruc': ruc}
        super().__init__(message=message, code='duplicate_company')


class PermissionDeniedException(VendoBaseException):
    """
    Excepción para permisos denegados
    """
    def __init__(self, permission=None, resource=None):
        message = _('Acceso denegado.')
        if permission and resource:
            message = _('No tiene permisos de %(permission)s en %(resource)s.') % {
                'permission': permission,
                'resource': resource
            }
        super().__init__(message=message, code='permission_denied')


class InactiveCompanyException(VendoBaseException):
    """
    Excepción para empresa inactiva
    """
    def __init__(self, company_name=None):
        message = _('La empresa está inactiva.')
        if company_name:
            message = _('La empresa %(company_name)s está inactiva.') % {'company_name': company_name}
        super().__init__(message=message, code='inactive_company')


class InactiveBranchException(VendoBaseException):
    """
    Excepción para sucursal inactiva
    """
    def __init__(self, branch_name=None):
        message = _('La sucursal está inactiva.')
        if branch_name:
            message = _('La sucursal %(branch_name)s está inactiva.') % {'branch_name': branch_name}
        super().__init__(message=message, code='inactive_branch')


class InvalidConfigurationException(VendoBaseException):
    """
    Excepción para configuración inválida
    """
    def __init__(self, config_key=None, expected_value=None):
        message = _('Configuración inválida.')
        if config_key:
            message = _('Configuración inválida para %(config_key)s.') % {'config_key': config_key}
            if expected_value:
                message += _(' Se esperaba: %(expected_value)s.') % {'expected_value': expected_value}
        super().__init__(message=message, code='invalid_configuration')


class FileProcessingException(VendoBaseException):
    """
    Excepción para errores en procesamiento de archivos
    """
    def __init__(self, filename=None, operation=None):
        message = _('Error al procesar archivo.')
        if filename and operation:
            message = _('Error al %(operation)s el archivo %(filename)s.') % {
                'operation': operation,
                'filename': filename
            }
        super().__init__(message=message, code='file_processing_error')


class BusinessLogicException(VendoBaseException):
    """
    Excepción para errores de lógica de negocio
    """
    def __init__(self, message=None, business_rule=None):
        if not message and business_rule:
            message = _('Violación de regla de negocio: %(business_rule)s.') % {'business_rule': business_rule}
        elif not message:
            message = _('Error en lógica de negocio.')
        super().__init__(message=message, code='business_logic_error')


class ValidationException(VendoBaseException):
    """
    Excepción para errores de validación
    """
    def __init__(self, field=None, value=None, validation_rule=None):
        message = _('Error de validación.')
        if field and validation_rule:
            message = _('Error de validación en campo %(field)s: %(validation_rule)s.') % {
                'field': field,
                'validation_rule': validation_rule
            }
        super().__init__(message=message, code='validation_error')


class APIException(VendoBaseException):
    """
    Excepción para errores de API
    """
    def __init__(self, api_name=None, status_code=None, response=None):
        message = _('Error en API externa.')
        if api_name:
            message = _('Error en API %(api_name)s.') % {'api_name': api_name}
            if status_code:
                message += _(' Código de estado: %(status_code)s.') % {'status_code': status_code}
        
        details = {}
        if response:
            details['response'] = response
        if status_code:
            details['status_code'] = status_code
            
        super().__init__(message=message, code='api_error', details=details)


class DatabaseException(VendoBaseException):
    """
    Excepción para errores de base de datos
    """
    def __init__(self, operation=None, table=None):
        message = _('Error en base de datos.')
        if operation and table:
            message = _('Error al %(operation)s en tabla %(table)s.') % {
                'operation': operation,
                'table': table
            }
        super().__init__(message=message, code='database_error')


class CacheException(VendoBaseException):
    """
    Excepción para errores de caché
    """
    def __init__(self, cache_key=None, operation=None):
        message = _('Error en caché.')
        if cache_key and operation:
            message = _('Error al %(operation)s clave de caché %(cache_key)s.') % {
                'operation': operation,
                'cache_key': cache_key
            }
        super().__init__(message=message, code='cache_error')


class ExternalServiceException(VendoBaseException):
    """
    Excepción para errores de servicios externos
    """
    def __init__(self, service_name=None, error_message=None):
        message = _('Error en servicio externo.')
        if service_name:
            message = _('Error en servicio %(service_name)s.') % {'service_name': service_name}
            if error_message:
                message += f' {error_message}'
        super().__init__(message=message, code='external_service_error')


# Excepciones específicas para diferentes módulos

class InventoryException(VendoBaseException):
    """
    Excepción base para errores de inventario
    """
    def __init__(self, message=None):
        super().__init__(message=message or _('Error en inventario.'), code='inventory_error')


class POSException(VendoBaseException):
    """
    Excepción base para errores de POS
    """
    def __init__(self, message=None):
        super().__init__(message=message or _('Error en punto de venta.'), code='pos_error')


class InvoicingException(VendoBaseException):
    """
    Excepción base para errores de facturación
    """
    def __init__(self, message=None):
        super().__init__(message=message or _('Error en facturación.'), code='invoicing_error')


class AccountingException(VendoBaseException):
    """
    Excepción base para errores de contabilidad
    """
    def __init__(self, message=None):
        super().__init__(message=message or _('Error en contabilidad.'), code='accounting_error')


class ReportsException(VendoBaseException):
    """
    Excepción base para errores de reportes
    """
    def __init__(self, message=None):
        super().__init__(message=message or _('Error en reportes.'), code='reports_error')


# Función auxiliar para manejar excepciones
def handle_vendo_exception(exception, logger=None):
    """
    Maneja excepciones del sistema VENDO
    
    Args:
        exception: Excepción a manejar
        logger: Logger para registrar el error
        
    Returns:
        dict: Diccionario con información del error
    """
    error_info = {
        'message': str(exception),
        'code': getattr(exception, 'code', 'unknown_error'),
        'details': getattr(exception, 'details', {})
    }
    
    if logger:
        logger.error(f"VendoException: {error_info}")
    
    return error_info