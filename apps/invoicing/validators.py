from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import re
from decimal import Decimal

def validate_ecuadorian_ruc(value):
    """Valida un RUC ecuatoriano"""
    if not value or len(value) != 13:
        raise ValidationError('El RUC debe tener 13 dígitos')
    
    if not value.isdigit():
        raise ValidationError('El RUC debe contener solo números')
    
    # Validar dígito verificador
    coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    sum_total = 0
    
    for i in range(9):
        digit = int(value[i])
        result = digit * coefficients[i]
        if result >= 10:
            result = result - 9
        sum_total += result
    
    remainder = sum_total % 10
    check_digit = 0 if remainder == 0 else 10 - remainder
    
    if int(value[9]) != check_digit:
        raise ValidationError('RUC inválido - dígito verificador incorrecto')

def validate_ecuadorian_cedula(value):
    """Valida una cédula ecuatoriana"""
    if not value or len(value) != 10:
        raise ValidationError('La cédula debe tener 10 dígitos')
    
    if not value.isdigit():
        raise ValidationError('La cédula debe contener solo números')
    
    # Validar provincia (primeros 2 dígitos)
    province = int(value[:2])
    if province < 1 or province > 24:
        raise ValidationError('Código de provincia inválido en la cédula')
    
    # Validar dígito verificador
    coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    sum_total = 0
    
    for i in range(9):
        digit = int(value[i])
        result = digit * coefficients[i]
        if result >= 10:
            result = result - 9
        sum_total += result
    
    remainder = sum_total % 10
    check_digit = 0 if remainder == 0 else 10 - remainder
    
    if int(value[9]) != check_digit:
        raise ValidationError('Cédula inválida - dígito verificador incorrecto')

def validate_positive_decimal(value):
    """Valida que el valor sea un decimal positivo"""
    if value is None:
        return
    
    if not isinstance(value, (int, float, Decimal)):
        raise ValidationError('El valor debe ser numérico')
    
    if Decimal(str(value)) <= 0:
        raise ValidationError('El valor debe ser mayor a 0')

def validate_percentage(value):
    """Valida que el valor sea un porcentaje válido (0-100)"""
    if value is None:
        return
    
    if not isinstance(value, (int, float, Decimal)):
        raise ValidationError('El porcentaje debe ser numérico')
    
    decimal_value = Decimal(str(value))
    if decimal_value < 0 or decimal_value > 100:
        raise ValidationError('El porcentaje debe estar entre 0 y 100')

def validate_clave_acceso(value):
    """Valida el formato de la clave de acceso del SRI"""
    if not value:
        return
    
    if len(value) != 49:
        raise ValidationError('La clave de acceso debe tener 49 dígitos')
    
    if not value.isdigit():
        raise ValidationError('La clave de acceso debe contener solo números')

def validate_establecimiento(value):
    """Valida el código de establecimiento"""
    if not value:
        raise ValidationError('El establecimiento es requerido')
    
    if len(value) != 3:
        raise ValidationError('El establecimiento debe tener 3 dígitos')
    
    if not value.isdigit():
        raise ValidationError('El establecimiento debe contener solo números')

def validate_punto_emision(value):
    """Valida el código de punto de emisión"""
    if not value:
        raise ValidationError('El punto de emisión es requerido')
    
    if len(value) != 3:
        raise ValidationError('El punto de emisión debe tener 3 dígitos')
    
    if not value.isdigit():
        raise ValidationError('El punto de emisión debe contener solo números')

def validate_secuencial(value):
    """Valida el secuencial de la factura"""
    if not value:
        raise ValidationError('El secuencial es requerido')
    
    if len(value) != 9:
        raise ValidationError('El secuencial debe tener 9 dígitos')
    
    if not value.isdigit():
        raise ValidationError('El secuencial debe contener solo números')

def validate_email_list(value):
    """Valida una lista de emails separados por coma"""
    if not value:
        return
    
    emails = [email.strip() for email in value.split(',')]
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    for email in emails:
        if not email_regex.match(email):
            raise ValidationError(f'Email inválido: {email}')

def validate_product_code(value):
    """Valida el código de producto"""
    if not value:
        raise ValidationError('El código del producto es requerido')
    
    if len(value) > 25:
        raise ValidationError('El código del producto no puede tener más de 25 caracteres')
    
    # Permitir solo caracteres alfanuméricos, guiones y puntos
    if not re.match(r'^[a-zA-Z0-9.-]+$', value):
        raise ValidationError('El código del producto solo puede contener letras, números, puntos y guiones')

def validate_iva_percentage(value):
    """Valida porcentajes de IVA válidos en Ecuador"""
    if value is None:
        return
    
    valid_iva_rates = [Decimal('0'), Decimal('12'), Decimal('14'), Decimal('15')]
    decimal_value = Decimal(str(value))
    
    if decimal_value not in valid_iva_rates:
        raise ValidationError(f'Porcentaje de IVA inválido. Valores válidos: {[float(rate) for rate in valid_iva_rates]}')

def validate_certificate_file(value):
    """Valida que el archivo sea un certificado P12 válido"""
    if not value:
        return
    
    if not value.name.lower().endswith('.p12'):
        raise ValidationError('El archivo debe tener extensión .p12')
    
    # Verificar tamaño mínimo y máximo
    if value.size < 1024:  # 1KB mínimo
        raise ValidationError('El archivo del certificado es demasiado pequeño')
    
    if value.size > 50 * 1024 * 1024:  # 50MB máximo
        raise ValidationError('El archivo del certificado es demasiado grande')

# Validadores usando regex
ruc_validator = RegexValidator(
    regex=r'^\d{13}$',
    message='El RUC debe tener exactamente 13 dígitos'
)

cedula_validator = RegexValidator(
    regex=r'^\d{10}$',
    message='La cédula debe tener exactamente 10 dígitos'
)

phone_validator = RegexValidator(
    regex=r'^[0-9+\-\s()]{7,20}$',
    message='Formato de teléfono inválido'
)

codigo_producto_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9.\-_]+$',
    message='El código solo puede contener letras, números, puntos, guiones y guiones bajos'
)