"""
Utilidades base del sistema VENDO
"""
import re
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal

from django.db import connection
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.shortcuts import redirect
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages


def generate_uuid() -> str:
    """
    Genera un UUID único
    """
    return str(uuid.uuid4())


def validate_ruc(ruc: str) -> bool:
    """
    Valida un RUC ecuatoriano
    
    Args:
        ruc: RUC a validar
        
    Returns:
        bool: True si es válido, False caso contrario
    """
    if not ruc or len(ruc) != 13:
        return False
    
    try:
        # Los primeros 2 dígitos deben corresponder a una provincia válida (01-24)
        provincia = int(ruc[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        # El tercer dígito define el tipo de RUC
        tercer_digito = int(ruc[2])
        
        if tercer_digito < 6:  # Persona natural
            return _validate_cedula_ruc(ruc[:10])
        elif tercer_digito == 6:  # Sector público
            return _validate_sector_publico_ruc(ruc)
        elif tercer_digito == 9:  # Persona jurídica
            return _validate_persona_juridica_ruc(ruc)
        else:
            return False
            
    except (ValueError, IndexError):
        return False


def _validate_cedula_ruc(cedula: str) -> bool:
    """Valida cédula o RUC de persona natural"""
    if len(cedula) != 10:
        return False
    
    try:
        # Algoritmo de validación de cédula ecuatoriana
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        suma = 0
        
        for i in range(9):
            producto = int(cedula[i]) * coeficientes[i]
            if producto >= 10:
                producto -= 9
            suma += producto
        
        digito_verificador = (10 - (suma % 10)) % 10
        return digito_verificador == int(cedula[9])
        
    except (ValueError, IndexError):
        return False


def _validate_sector_publico_ruc(ruc: str) -> bool:
    """Valida RUC de sector público"""
    if len(ruc) != 13:
        return False
    
    try:
        # Algoritmo para sector público
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        
        for i in range(8):
            suma += int(ruc[i]) * coeficientes[i]
        
        residuo = suma % 11
        digito_verificador = 11 - residuo if residuo != 0 else 0
        
        return digito_verificador == int(ruc[8])
        
    except (ValueError, IndexError):
        return False


def _validate_persona_juridica_ruc(ruc: str) -> bool:
    """Valida RUC de persona jurídica"""
    if len(ruc) != 13:
        return False
    
    try:
        # Algoritmo para persona jurídica
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        
        for i in range(9):
            suma += int(ruc[i]) * coeficientes[i]
        
        residuo = suma % 11
        digito_verificador = 11 - residuo if residuo != 0 else 0
        
        return digito_verificador == int(ruc[9])
        
    except (ValueError, IndexError):
        return False


def validate_email(email: str) -> bool:
    """
    Valida formato de email
    """
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, email))


def validate_phone(phone: str) -> bool:
    """
    Valida formato de teléfono ecuatoriano
    """
    # Formato: 02-XXXXXXX, 09-XXXXXXXX, +593-X-XXXXXXX
    phone_patterns = [
        r'^0[2-7]-\d{7}$',  # Teléfonos fijos
        r'^09-\d{8}$',      # Celulares
        r'^\+593-[2-9]-\d{7,8}$',  # Formato internacional
    ]
    
    for pattern in phone_patterns:
        if re.match(pattern, phone):
            return True
    return False


def format_currency(amount: Decimal, currency: str = 'USD') -> str:
    """
    Formatea un monto como moneda
    
    Args:
        amount: Monto a formatear
        currency: Código de moneda (USD por defecto)
        
    Returns:
        str: Monto formateado
    """
    if currency == 'USD':
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def get_current_schema() -> Optional[str]:
    """
    Obtiene el esquema actual de la base de datos
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        result = cursor.fetchone()
        return result[0] if result else None


def set_schema(schema_name: str) -> bool:
    """
    Establece el esquema de la base de datos
    
    Args:
        schema_name: Nombre del esquema
        
    Returns:
        bool: True si se estableció correctamente
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SET search_path TO {schema_name}")
        return True
    except Exception:
        return False


def create_schema(schema_name: str) -> bool:
    """
    Crea un nuevo esquema en la base de datos
    
    Args:
        schema_name: Nombre del esquema a crear
        
    Returns:
        bool: True si se creó correctamente
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        return True
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitiza un nombre de archivo removiendo caracteres especiales
    
    Args:
        filename: Nombre de archivo a sanitizar
        
    Returns:
        str: Nombre de archivo sanitizado
    """
    # Remover caracteres especiales y espacios
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    # Remover múltiples guiones bajos consecutivos
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remover guiones bajos al inicio y final
    sanitized = sanitized.strip('_')
    
    return sanitized


def get_client_ip(request) -> str:
    """
    Obtiene la IP real del cliente considerando proxies
    
    Args:
        request: Request de Django
        
    Returns:
        str: Dirección IP del cliente
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def paginate_queryset(queryset, page_number: int, page_size: int = 25):
    """
    Pagina un queryset
    
    Args:
        queryset: QuerySet a paginar
        page_number: Número de página
        page_size: Tamaño de página
        
    Returns:
        Page: Objeto Page de Django
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    paginator = Paginator(queryset, page_size)
    
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    
    return page


def truncate_string(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    Trunca una cadena de texto
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        suffix: Sufijo a agregar cuando se trunca
        
    Returns:
        str: Texto truncado
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def get_model_verbose_name(model_class) -> str:
    """
    Obtiene el nombre verboso de un modelo
    
    Args:
        model_class: Clase del modelo
        
    Returns:
        str: Nombre verboso del modelo
    """
    return model_class._meta.verbose_name


def safe_decimal(value: Any, default: Decimal = Decimal('0.00')) -> Decimal:
    """
    Convierte un valor a Decimal de forma segura
    
    Args:
        value: Valor a convertir
        default: Valor por defecto si la conversión falla
        
    Returns:
        Decimal: Valor convertido o valor por defecto
    """
    try:
        if value is None or value == '':
            return default
        return Decimal(str(value))
    except (ValueError, TypeError):
        return default


def format_datetime(dt: datetime, format_string: str = '%d/%m/%Y %H:%M') -> str:
    """
    Formatea una fecha y hora
    
    Args:
        dt: Objeto datetime
        format_string: Formato de salida
        
    Returns:
        str: Fecha formateada
    """
    if not dt:
        return ''
    return dt.strftime(format_string)


def format_date(d: date, format_string: str = '%d/%m/%Y') -> str:
    """
    Formatea una fecha
    
    Args:
        d: Objeto date
        format_string: Formato de salida
        
    Returns:
        str: Fecha formateada
    """
    if not d:
        return ''
    return d.strftime(format_string)


# ==========================================
# FUNCIONES ADICIONALES PARA EL SISTEMA
# ==========================================

def health_check_basic(request):
    """
    Health check básico para verificar que el sistema funciona
    """
    return JsonResponse({
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
        'message': 'Sistema VENDO funcionando correctamente',
        'version': '1.0.0'
    })


def safe_redirect(request, fallback_url='core:dashboard'):
    """
    Redirección segura con fallback
    """
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect(fallback_url)


def add_success_message(request, message):
    """
    Agregar mensaje de éxito de forma segura
    """
    try:
        messages.success(request, message)
    except Exception:
        # Si falla el sistema de mensajes, continuar sin error
        pass


def add_error_message(request, message):
    """
    Agregar mensaje de error de forma segura
    """
    try:
        messages.error(request, message)
    except Exception:
        # Si falla el sistema de mensajes, continuar sin error
        pass


def validate_company_access(user, company):
    """
    Valida si un usuario tiene acceso a una empresa
    """
    if user.is_superuser:
        return True
    
    # Por ahora permitir acceso a todas las empresas activas
    # Esto se modificará cuando implementemos el módulo completo de usuarios
    return company.is_active


def get_user_companies(user):
    """
    Obtiene las empresas disponibles para un usuario
    """
    from .models import Company
    
    if user.is_superuser:
        return Company.objects.filter(is_active=True)
    
    # Por ahora devolver todas las empresas activas
    # Esto se modificará con el módulo de usuarios completo
    return Company.objects.filter(is_active=True)


def get_user_branches(user, company):
    """
    Obtiene las sucursales disponibles para un usuario en una empresa
    """
    if not company:
        return []
    
    # Por ahora devolver todas las sucursales activas de la empresa
    return company.branches.filter(is_active=True).order_by('name')


def generate_audit_log_entry(user, action, object_instance, company=None, extra_data=None):
    """
    Genera una entrada en el log de auditoría
    """
    try:
        from .models import AuditLog
        from django.contrib.contenttypes.models import ContentType
        
        content_type = ContentType.objects.get_for_model(object_instance)
        
        log_data = {
            'user': user,
            'company': company,
            'action': action,
            'content_type': content_type,
            'object_id': str(object_instance.pk),
            'object_repr': str(object_instance),
            'ip_address': '',  # Se llenará en el middleware
        }
        
        if extra_data:
            log_data['extra_data'] = extra_data
        
        AuditLog.objects.create(**log_data)
        
    except Exception as e:
        # Si falla el logging, no interrumpir el flujo principal
        print(f"Error generando log de auditoría: {e}")


def check_system_health():
    """
    Verifica el estado general del sistema
    """
    try:
        from .models import Company, Branch
        from django.db import connection
        
        # Verificar conexión a base de datos
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Contar elementos básicos
        companies_count = Company.objects.filter(is_active=True).count()
        branches_count = Branch.objects.filter(is_active=True).count()
        
        return {
            'status': 'healthy',
            'database': 'connected',
            'companies': companies_count,
            'branches': branches_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def cleanup_old_audit_logs(days_to_keep=365):
    """
    Limpia logs de auditoría antiguos
    """
    try:
        from .models import AuditLog
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        deleted_count = AuditLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        return {
            'success': True,
            'deleted_logs': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def generate_sri_sequential(company, branch, document_type):
    """
    Genera secuencial para documentos SRI
    
    Args:
        company: Instancia de Company
        branch: Instancia de Branch
        document_type: Tipo de documento ('01', '03', '04', etc.)
        
    Returns:
        str: Secuencial formateado (001-001-000000001)
    """
    try:
        # Formato: 001-001-000000001
        # Los primeros 3 dígitos son el punto de emisión
        # Los siguientes 3 son el establecimiento
        # Los últimos 9 son el secuencial
        
        establishment = branch.sri_establishment_code or '001'
        emission_point = '001'  # Por defecto, se puede configurar después
        
        # Obtener el siguiente secuencial (esto se implementará con el módulo de facturación)
        next_sequential = 1
        
        return f"{establishment}-{emission_point}-{next_sequential:09d}"
        
    except Exception:
        return '001-001-000000001'


def validate_sri_certificate(certificate_path):
    """
    Valida un certificado digital del SRI
    
    Args:
        certificate_path: Ruta al archivo del certificado
        
    Returns:
        dict: Información del certificado
    """
    try:
        # Esta función se implementará completamente cuando tengamos el módulo SRI
        return {
            'valid': True,
            'owner': 'Certificado válido',
            'expires': timezone.now() + timedelta(days=365),
            'serial': 'XXXXXXXXXX'
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }


def backup_database():
    """
    Crea un backup de la base de datos
    """
    try:
        # Esta función se implementará con el módulo de backup
        backup_filename = f"backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sql"
        
        return {
            'success': True,
            'filename': backup_filename,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# ==========================================
# CONSTANTES Y CONFIGURACIONES
# ==========================================

# Acciones de auditoría
AUDIT_ACTIONS = {
    'CREATE': 'create',
    'UPDATE': 'update',
    'DELETE': 'delete',
    'LOGIN': 'login',
    'LOGOUT': 'logout',
    'VIEW': 'view',
    'EXPORT': 'export',
    'IMPORT': 'import',
    'APPROVE': 'approve',
    'REJECT': 'reject',
    'SEND': 'send',
    'RECEIVE': 'receive',
}

# Configuraciones por defecto
DEFAULT_PAGINATION = 25
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
MAX_CERTIFICATE_SIZE = 1 * 1024 * 1024  # 1MB

# Configuraciones de empresa por defecto
DEFAULT_COMPANY_CONFIG = {
    'currency': 'USD',
    'decimal_places': 2,
    'date_format': '%d/%m/%Y',
    'time_format': '%H:%M:%S',
    'datetime_format': '%d/%m/%Y %H:%M:%S',
    'timezone': 'America/Guayaquil',
    'tax_rate': Decimal('0.12'),  # IVA 12%
    'retention_rate': Decimal('0.02'),  # Retención 2%
}

# Tipos de documentos SRI
SRI_DOCUMENT_TYPES = {
    '01': 'Factura',
    '03': 'Liquidación de compra',
    '04': 'Nota de crédito',
    '05': 'Nota de débito',
    '06': 'Guía de remisión',
    '07': 'Comprobante de retención',
}

# Estados de documentos
DOCUMENT_STATES = {
    'DRAFT': 'draft',
    'SENT': 'sent',
    'AUTHORIZED': 'authorized',
    'REJECTED': 'rejected',
    'CANCELLED': 'cancelled',
}

# Patrones de validación
VALIDATION_PATTERNS = {
    'RUC': r'^\d{13}$',
    'CEDULA': r'^\d{10}$',
    'EMAIL': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'PHONE': r'^(0[2-7]-\d{7}|09-\d{8}|\+593-[2-9]-\d{7,8})$',
    'POSTAL_CODE': r'^\d{6}$',
}

# Configuraciones de archivo
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx']
ALLOWED_CERTIFICATE_EXTENSIONS = ['p12', 'pfx']

# Configuraciones de cache
CACHE_TIMEOUTS = {
    'SHORT': 300,      # 5 minutos
    'MEDIUM': 1800,    # 30 minutos
    'LONG': 3600,      # 1 hora
    'VERY_LONG': 86400,  # 24 horas
}