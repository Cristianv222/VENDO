"""
Validadores personalizados del módulo Users
"""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone  


User = get_user_model()


def validate_document_number(value):
    """
    Validador para números de documento ecuatorianos
    """
    if not value:
        return
    
    # Limpiar el valor
    value = str(value).strip()
    
    # Validar cédula (10 dígitos)
    if len(value) == 10:
        if not value.isdigit():
            raise ValidationError(_('La cédula debe contener solo números'))
        
        # Algoritmo de validación de cédula ecuatoriana
        if not _validate_cedula(value):
            raise ValidationError(_('Número de cédula inválido'))
    
    # Validar RUC (13 dígitos)
    elif len(value) == 13:
        if not value.isdigit():
            raise ValidationError(_('El RUC debe contener solo números'))
        
        # Validar RUC ecuatoriano
        if not _validate_ruc(value):
            raise ValidationError(_('Número de RUC inválido'))
    
    # Validar pasaporte (formato alfanumérico)
    elif len(value) >= 6 and len(value) <= 20:
        if not re.match(r'^[A-Za-z0-9]+$', value):
            raise ValidationError(_('El pasaporte debe contener solo letras y números'))
    
    else:
        raise ValidationError(_('Formato de documento inválido'))


def _validate_cedula(cedula):
    """
    Validar cédula ecuatoriana usando el algoritmo oficial
    """
    if len(cedula) != 10:
        return False
    
    # Los primeros dos dígitos deben corresponder a una provincia válida (01-24)
    provincia = int(cedula[:2])
    if provincia < 1 or provincia > 24:
        return False
    
    # El tercer dígito debe ser menor a 6 (para personas naturales)
    tercer_digito = int(cedula[2])
    if tercer_digito >= 6:
        return False
    
    # Algoritmo de validación
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    
    for i in range(9):
        resultado = int(cedula[i]) * coeficientes[i]
        if resultado >= 10:
            resultado = resultado - 9
        suma += resultado
    
    residuo = suma % 10
    digito_verificador = 0 if residuo == 0 else 10 - residuo
    
    return digito_verificador == int(cedula[9])


def _validate_ruc(ruc):
    """
    Validar RUC ecuatoriano
    """
    if len(ruc) != 13:
        return False
    
    # Los primeros dos dígitos deben corresponder a una provincia válida (01-24)
    provincia = int(ruc[:2])
    if provincia < 1 or provincia > 24:
        return False
    
    tercer_digito = int(ruc[2])
    
    # RUC de persona natural (tercer dígito < 6)
    if tercer_digito < 6:
        # Debe terminar en 001
        if ruc[10:] != '001':
            return False
        # Validar como cédula los primeros 10 dígitos
        return _validate_cedula(ruc[:10])
    
    # RUC de empresa privada (tercer dígito = 9)
    elif tercer_digito == 9:
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        
        for i in range(9):
            suma += int(ruc[i]) * coeficientes[i]
        
        residuo = suma % 11
        digito_verificador = 0 if residuo == 0 else 11 - residuo
        
        return digito_verificador == int(ruc[9])
    
    # RUC de empresa pública (tercer dígito = 6)
    elif tercer_digito == 6:
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        
        for i in range(8):
            suma += int(ruc[i]) * coeficientes[i]
        
        residuo = suma % 11
        digito_verificador = 0 if residuo == 0 else 11 - residuo
        
        return digito_verificador == int(ruc[8])
    
    return False


def validate_phone_number(value):
    """
    Validador para números de teléfono ecuatorianos
    """
    if not value:
        return
    
    # Limpiar espacios y caracteres especiales
    phone = re.sub(r'[\s\-\(\)]+', '', str(value))
    
    # Patrón para teléfonos ecuatorianos
    # Fijos: 02XXXXXXX, 03XXXXXXX, 04XXXXXXX, 05XXXXXXX, 06XXXXXXX, 07XXXXXXX
    # Móviles: 09XXXXXXXX, 08XXXXXXXX
    # Con código de país: +593XXXXXXXXX, 593XXXXXXXXX
    
    patterns = [
        r'^0[2-7]\d{7}$',           # Teléfonos fijos
        r'^0[89]\d{8}$',            # Teléfonos móviles
        r'^\+593[2-7]\d{7}$',       # Fijos con código de país
        r'^\+593[89]\d{8}$',        # Móviles con código de país
        r'^593[2-7]\d{7}$',         # Fijos con código sin +
        r'^593[89]\d{8}$',          # Móviles con código sin +
    ]
    
    if not any(re.match(pattern, phone) for pattern in patterns):
        raise ValidationError(_('Formato de teléfono inválido'))


def validate_username_unique(value):
    """
    Validador para verificar que el username es único
    """
    if User.objects.filter(username=value).exists():
        raise ValidationError(_('Este nombre de usuario ya está en uso'))


def validate_email_unique(value):
    """
    Validador para verificar que el email es único
    """
    if User.objects.filter(email=value).exists():
        raise ValidationError(_('Este email ya está en uso'))


def validate_strong_password(value):
    """
    Validador para contraseñas seguras
    """
    if len(value) < 8:
        raise ValidationError(_('La contraseña debe tener al menos 8 caracteres'))
    
    if not re.search(r'[a-z]', value):
        raise ValidationError(_('La contraseña debe contener al menos una letra minúscula'))
    
    if not re.search(r'[A-Z]', value):
        raise ValidationError(_('La contraseña debe contener al menos una letra mayúscula'))
    
    if not re.search(r'\d', value):
        raise ValidationError(_('La contraseña debe contener al menos un número'))
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', value):
        raise ValidationError(_('La contraseña debe contener al menos un carácter especial'))
    
    # Verificar patrones comunes
    common_passwords = [
        'password', '12345678', 'qwerty', 'abc123', 'admin',
        'welcome', 'login', 'user', '11111111', '00000000'
    ]
    
    if value.lower() in common_passwords:
        raise ValidationError(_('No se permite usar contraseñas comunes'))


def validate_role_name(value):
    """
    Validador para nombres de roles
    """
    if not value:
        raise ValidationError(_('El nombre del rol es requerido'))
    
    # No permitir nombres de roles del sistema si no es admin
    system_roles = ['Super Administrador', 'Administrador del Sistema']
    if value in system_roles:
        raise ValidationError(_('No se puede usar nombres de roles del sistema'))
    
    # Validar longitud
    if len(value) < 3:
        raise ValidationError(_('El nombre del rol debe tener al menos 3 caracteres'))
    
    if len(value) > 50:
        raise ValidationError(_('El nombre del rol no puede tener más de 50 caracteres'))


def validate_employee_code(value):
    """
    Validador para códigos de empleado
    """
    if not value:
        return
    
    # Solo letras, números y guiones
    if not re.match(r'^[A-Za-z0-9\-]+$', value):
        raise ValidationError(_('El código de empleado solo puede contener letras, números y guiones'))
    
    # Longitud entre 3 y 20 caracteres
    if len(value) < 3 or len(value) > 20:
        raise ValidationError(_('El código de empleado debe tener entre 3 y 20 caracteres'))


def validate_timezone(value):
    """
    Validador para zonas horarias
    """
    import pytz
    
    if value not in pytz.all_timezones:
        raise ValidationError(_('Zona horaria inválida'))


def validate_language_code(value):
    """
    Validador para códigos de idioma
    """
    from django.conf import settings
    
    valid_languages = [lang[0] for lang in settings.LANGUAGES]
    
    if value not in valid_languages:
        raise ValidationError(_('Código de idioma inválido'))


def validate_color_hex(value):
    """
    Validador para códigos de color hexadecimal
    """
    if not value:
        return
    
    if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
        raise ValidationError(_('Código de color inválido. Use formato #RRGGBB'))


def validate_permission_codename(value):
    """
    Validador para códigos de permisos
    """
    if not value:
        raise ValidationError(_('El código del permiso es requerido'))
    
    # Solo letras minúsculas, números, puntos y guiones bajos
    if not re.match(r'^[a-z0-9._]+$', value):
        raise ValidationError(
            _('El código del permiso solo puede contener letras minúsculas, números, puntos y guiones bajos')
        )
    
    # Debe tener el formato módulo.acción
    if '.' not in value:
        raise ValidationError(_('El código del permiso debe tener el formato módulo.acción'))
    
    parts = value.split('.')
    if len(parts) != 2:
        raise ValidationError(_('El código del permiso debe tener exactamente un punto'))
    
    module, action = parts
    
    # Validar módulo
    valid_modules = [
        'core', 'users', 'pos', 'inventory', 'invoicing',
        'purchases', 'accounting', 'quotations', 'reports', 'settings'
    ]
    
    if module not in valid_modules:
        raise ValidationError(
            _('Módulo inválido. Los módulos válidos son: %(modules)s') % {
                'modules': ', '.join(valid_modules)
            }
        )
    
    # Validar acción
    valid_actions = [
        'view', 'add', 'change', 'delete', 'manage', 'approve',
        'void', 'authorize', 'export', 'generate', 'adjust'
    ]
    
    if action not in valid_actions:
        raise ValidationError(
            _('Acción inválida. Las acciones válidas son: %(actions)s') % {
                'actions': ', '.join(valid_actions)
            }
        )


class PasswordHistoryValidator:
    """
    Validador para evitar reutilización de contraseñas
    """
    def __init__(self, history_length=5):
        self.history_length = history_length
    
    def validate(self, password, user=None):
        if not user or not user.pk:
            return
        
        # Aquí podrías implementar un modelo PasswordHistory
        # para guardar las últimas contraseñas del usuario
        pass
    
    def get_help_text(self):
        return _(
            f'Su contraseña no puede ser igual a las últimas {self.history_length} contraseñas utilizadas.'
        )


class SimilarityPasswordValidator:
    """
    Validador para evitar contraseñas similares a información del usuario
    """
    def validate(self, password, user=None):
        if not user:
            return
        
        # Verificar similitud con información del usuario
        user_info = [
            user.username,
            user.first_name,
            user.last_name,
            user.email.split('@')[0] if user.email else '',
            user.document_number,
        ]
        
        for info in user_info:
            if info and len(info) >= 3:
                if info.lower() in password.lower():
                    raise ValidationError(
                        _('La contraseña no puede contener información personal del usuario.')
                    )
    
    def get_help_text(self):
        return _('Su contraseña no puede contener su información personal.')