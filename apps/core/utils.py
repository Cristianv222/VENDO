"""
Utilidades base del sistema VENDO
"""
import re
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal

from django.db import connection
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings


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