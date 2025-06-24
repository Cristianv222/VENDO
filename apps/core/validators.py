"""
Validadores personalizados para el sistema VENDO
"""
import re
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.core.validators import BaseValidator

from .utils import validate_ruc, validate_email, validate_phone


class RUCValidator:
    """
    Validador para RUC ecuatoriano
    """
    message = _('Ingrese un RUC válido de 13 dígitos.')
    code = 'invalid_ruc'
    
    def __call__(self, value):
        if not validate_ruc(value):
            raise ValidationError(self.message, code=self.code)


class CedulaValidator:
    """
    Validador para cédula ecuatoriana
    """
    message = _('Ingrese una cédula válida de 10 dígitos.')
    code = 'invalid_cedula'
    
    def __call__(self, value):
        if not value or len(value) != 10:
            raise ValidationError(self.message, code=self.code)
        
        # Reutilizar la función de validación de RUC para cédulas
        from .utils import _validate_cedula_ruc
        if not _validate_cedula_ruc(value):
            raise ValidationError(self.message, code=self.code)


class PhoneValidator:
    """
    Validador para teléfonos ecuatorianos
    """
    message = _('Ingrese un número de teléfono válido.')
    code = 'invalid_phone'
    
    def __call__(self, value):
        if not validate_phone(value):
            raise ValidationError(self.message, code=self.code)


class PositiveDecimalValidator:
    """
    Validador para números decimales positivos
    """
    message = _('Este valor debe ser positivo.')
    code = 'negative_value'
    
    def __call__(self, value):
        if value is not None and value < 0:
            raise ValidationError(self.message, code=self.code)


class MaxDecimalPlacesValidator(BaseValidator):
    """
    Validador para máximo número de decimales
    """
    message = _('Asegúrese de que no haya más de %(limit_value)s decimales.')
    code = 'max_decimal_places'
    
    def compare(self, value, limit_value):
        if value is None:
            return False
        
        # Convertir a string y verificar decimales
        str_value = str(value)
        if '.' in str_value:
            decimal_places = len(str_value.split('.')[1])
            return decimal_places > limit_value
        return False


class AlphanumericValidator:
    """
    Validador para caracteres alfanuméricos únicamente
    """
    message = _('Este campo solo puede contener letras y números.')
    code = 'invalid_alphanumeric'
    
    def __call__(self, value):
        if not re.match(r'^[a-zA-Z0-9]+$', value):
            raise ValidationError(self.message, code=self.code)


class NoSpecialCharsValidator:
    """
    Validador que no permite caracteres especiales peligrosos
    """
    message = _('Este campo contiene caracteres no permitidos.')
    code = 'invalid_characters'
    
    # Caracteres no permitidos
    forbidden_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`']
    
    def __call__(self, value):
        for char in self.forbidden_chars:
            if char in value:
                raise ValidationError(self.message, code=self.code)


class FileExtensionValidator:
    """
    Validador para extensiones de archivo
    """
    def __init__(self, allowed_extensions):
        self.allowed_extensions = [ext.lower() for ext in allowed_extensions]
        self.message = _('Tipo de archivo no permitido. Extensiones permitidas: %(extensions)s')
        self.code = 'invalid_extension'
    
    def __call__(self, value):
        if not value or not value.name:
            return
        
        extension = value.name.split('.')[-1].lower()
        if extension not in self.allowed_extensions:
            raise ValidationError(
                self.message,
                code=self.code,
                params={'extensions': ', '.join(self.allowed_extensions)}
            )


class FileSizeValidator:
    """
    Validador para tamaño de archivo
    """
    def __init__(self, max_size_mb):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_size_mb = max_size_mb
        self.message = _('El archivo es demasiado grande. Tamaño máximo: %(max_size)s MB')
        self.code = 'file_too_large'
    
    def __call__(self, value):
        if not value:
            return
        
        if value.size > self.max_size_bytes:
            raise ValidationError(
                self.message,
                code=self.code,
                params={'max_size': self.max_size_mb}
            )


class SchemaNameValidator:
    """
    Validador para nombres de esquema de PostgreSQL
    """
    message = _('Nombre de esquema inválido. Use solo letras, números y guiones bajos.')
    code = 'invalid_schema_name'
    
    def __call__(self, value):
        # Los nombres de esquema en PostgreSQL deben:
        # - Comenzar con letra o guión bajo
        # - Contener solo letras, números y guiones bajos
        # - Tener máximo 63 caracteres
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
            raise ValidationError(self.message, code=self.code)
        
        if len(value) > 63:
            raise ValidationError(
                _('El nombre del esquema no puede tener más de 63 caracteres.'),
                code='schema_name_too_long'
            )


class EstablishmentCodeValidator:
    """
    Validador para código de establecimiento SRI (3 dígitos)
    """
    message = _('El código de establecimiento debe tener exactamente 3 dígitos.')
    code = 'invalid_establishment_code'
    
    def __call__(self, value):
        if not re.match(r'^\d{3}$', value):
            raise ValidationError(self.message, code=self.code)


class EmissionPointValidator:
    """
    Validador para punto de emisión SRI (3 dígitos)
    """
    message = _('El punto de emisión debe tener exactamente 3 dígitos.')
    code = 'invalid_emission_point'
    
    def __call__(self, value):
        if not re.match(r'^\d{3}$', value):
            raise ValidationError(self.message, code=self.code)


class SequentialNumberValidator:
    """
    Validador para número secuencial SRI (9 dígitos)
    """
    message = _('El número secuencial debe tener exactamente 9 dígitos.')
    code = 'invalid_sequential_number'
    
    def __call__(self, value):
        if not re.match(r'^\d{9}$', value):
            raise ValidationError(self.message, code=self.code)


class PercentageValidator:
    """
    Validador para porcentajes (0-100)
    """
    message = _('El valor debe estar entre 0 y 100.')
    code = 'invalid_percentage'
    
    def __call__(self, value):
        if value is not None and (value < 0 or value > 100):
            raise ValidationError(self.message, code=self.code)


class MinAmountValidator:
    """
    Validador para monto mínimo
    """
    def __init__(self, min_amount):
        self.min_amount = Decimal(str(min_amount))
        self.message = _('El monto debe ser mayor o igual a %(min_amount)s.')
        self.code = 'min_amount'
    
    def __call__(self, value):
        if value is not None and value < self.min_amount:
            raise ValidationError(
                self.message,
                code=self.code,
                params={'min_amount': self.min_amount}
            )


# Instancias predefinidas de validadores comunes
validate_ruc_ecuador = RUCValidator()
validate_cedula_ecuador = CedulaValidator()
validate_phone_ecuador = PhoneValidator()
validate_positive_decimal = PositiveDecimalValidator()
validate_two_decimal_places = MaxDecimalPlacesValidator(2)
validate_alphanumeric = AlphanumericValidator()
validate_no_special_chars = NoSpecialCharsValidator()
validate_schema_name = SchemaNameValidator()
validate_establishment_code = EstablishmentCodeValidator()
validate_emission_point = EmissionPointValidator()
validate_sequential_number = SequentialNumberValidator()
validate_percentage = PercentageValidator()

# Validadores para archivos comunes
validate_image_file = FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp'])
validate_document_file = FileExtensionValidator(['pdf', 'doc', 'docx', 'txt'])
validate_certificate_file = FileExtensionValidator(['p12', 'pfx'])
validate_excel_file = FileExtensionValidator(['xls', 'xlsx', 'csv'])

# Validadores para tamaño de archivo
validate_image_size = FileSizeValidator(5)  # 5 MB
validate_document_size = FileSizeValidator(10)  # 10 MB
validate_certificate_size = FileSizeValidator(1)  # 1 MB