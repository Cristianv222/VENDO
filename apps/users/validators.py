"""
Validadores personalizados para el módulo de usuarios de VENDO.
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator
)


class EcuadorianCedulaValidator:
    """
    Validador para cédulas ecuatorianas.
    """
    
    def __call__(self, value):
        if not self.validate_cedula(value):
            raise ValidationError(
                _('El número de cédula ingresado no es válido.'),
                code='invalid_cedula'
            )
    
    def validate_cedula(self, cedula):
        """
        Valida una cédula ecuatoriana usando el algoritmo oficial.
        """
        if not cedula or len(cedula) != 10:
            return False
        
        if not cedula.isdigit():
            return False
        
        # Los dos primeros dígitos deben corresponder a una provincia válida (01-24)
        provincia = int(cedula[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        # Aplicar algoritmo de validación
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        suma = 0
        
        for i in range(9):
            valor = int(cedula[i]) * coeficientes[i]
            if valor >= 10:
                valor = valor - 9
            suma += valor
        
        digito_verificador = (10 - (suma % 10)) % 10
        
        return digito_verificador == int(cedula[9])


class EcuadorianRUCValidator:
    """
    Validador para RUC ecuatoriano.
    """
    
    def __call__(self, value):
        if not self.validate_ruc(value):
            raise ValidationError(
                _('El número de RUC ingresado no es válido.'),
                code='invalid_ruc'
            )
    
    def validate_ruc(self, ruc):
        """
        Valida un RUC ecuatoriano.
        """
        if not ruc or len(ruc) != 13:
            return False
        
        if not ruc.isdigit():
            return False
        
        # RUC de persona natural (termina en 001)
        if ruc.endswith('001'):
            return EcuadorianCedulaValidator().validate_cedula(ruc[:10])
        
        # RUC de empresa privada (tercer dígito = 9)
        if ruc[2] == '9':
            return self.validate_ruc_juridico(ruc)
        
        # RUC de empresa pública (tercer dígito = 6)
        if ruc[2] == '6':
            return self.validate_ruc_publico(ruc)
        
        return False
    
    def validate_ruc_juridico(self, ruc):
        """Validar RUC de persona jurídica privada."""
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        
        for i in range(9):
            suma += int(ruc[i]) * coeficientes[i]
        
        digito_verificador = 11 - (suma % 11)
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            return False
        
        return digito_verificador == int(ruc[9])
    
    def validate_ruc_publico(self, ruc):
        """Validar RUC de empresa pública."""
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        
        for i in range(8):
            suma += int(ruc[i]) * coeficientes[i]
        
        digito_verificador = 11 - (suma % 11)
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            return False
        
        return digito_verificador == int(ruc[8])


class EcuadorianPhoneValidator:
    """
    Validador para números de teléfono ecuatorianos.
    """
    
    def __call__(self, value):
        if value and not self.validate_phone(value):
            raise ValidationError(
                _('El número de teléfono no tiene un formato válido para Ecuador.'),
                code='invalid_phone'
            )
    
    def validate_phone(self, phone):
        """
        Valida números de teléfono ecuatorianos.
        """
        if not phone:
            return True  # Permitir vacío si es opcional
        
        # Limpiar el número
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Patrones válidos para Ecuador
        patterns = [
            r'^\+593[2-7]\d{7}$',  # Teléfono fijo con código país
            r'^\+5939\d{8}$',      # Celular con código país
            r'^0[2-7]\d{7}$',      # Teléfono fijo nacional
            r'^09\d{8}$',          # Celular nacional
            r'^[2-7]\d{7}$',       # Teléfono fijo sin prefijo
            r'^9\d{8}$',           # Celular sin prefijo
        ]
        
        return any(re.match(pattern, clean_phone) for pattern in patterns)


class StrongPasswordValidator:
    """
    Validador de contraseñas fuertes personalizado para VENDO.
    """
    
    def __init__(self, min_length=8):
        self.min_length = min_length
    
    def validate(self, password, user=None):
        """
        Validar que la contraseña cumpla con los requisitos de seguridad.
        """
        errors = []
        
        # Longitud mínima
        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    _('La contraseña debe tener al menos %(min_length)d caracteres.'),
                    params={'min_length': self.min_length},
                    code='password_too_short'
                )
            )
        
        # Debe contener al menos una letra minúscula
        if not re.search(r'[a-z]', password):
            errors.append(
                ValidationError(
                    _('La contraseña debe contener al menos una letra minúscula.'),
                    code='password_no_lower'
                )
            )
        
        # Debe contener al menos una letra mayúscula
        if not re.search(r'[A-Z]', password):
            errors.append(
                ValidationError(
                    _('La contraseña debe contener al menos una letra mayúscula.'),
                    code='password_no_upper'
                )
            )
        
        # Debe contener al menos un número
        if not re.search(r'\d', password):
            errors.append(
                ValidationError(
                    _('La contraseña debe contener al menos un número.'),
                    code='password_no_number'
                )
            )
        
        # Debe contener al menos un carácter especial
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\?]', password):
            errors.append(
                ValidationError(
                    _('La contraseña debe contener al menos un carácter especial (!@#$%^&*).'),
                    code='password_no_special'
                )
            )
        
        # No debe contener información del usuario
        if user:
            user_data = [
                user.username.lower() if hasattr(user, 'username') else '',
                user.first_name.lower() if hasattr(user, 'first_name') else '',
                user.last_name.lower() if hasattr(user, 'last_name') else '',
                user.email.lower().split('@')[0] if hasattr(user, 'email') and user.email else '',
            ]
            
            password_lower = password.lower()
            for data in user_data:
                if data and len(data) > 2 and data in password_lower:
                    errors.append(
                        ValidationError(
                            _('La contraseña no debe contener información personal.'),
                            code='password_too_similar'
                        )
                    )
                    break
        
        # No debe ser una secuencia común
        sequences = ['123456', 'abcdef', 'qwerty', 'asdfgh']
        password_lower = password.lower()
        for sequence in sequences:
            if sequence in password_lower:
                errors.append(
                    ValidationError(
                        _('La contraseña no debe contener secuencias comunes.'),
                        code='password_common_sequence'
                    )
                )
                break
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        return _(
            'Su contraseña debe tener al menos %(min_length)d caracteres, '
            'incluyendo mayúsculas, minúsculas, números y caracteres especiales.'
        ) % {'min_length': self.min_length}


class UsernameValidator:
    """
    Validador personalizado para nombres de usuario.
    """
    
    def __call__(self, value):
        if not self.validate_username(value):
            raise ValidationError(
                _('El nombre de usuario solo puede contener letras, números, puntos y guiones bajos.'),
                code='invalid_username'
            )
    
    def validate_username(self, username):
        """
        Validar formato del nombre de usuario.
        """
        if not username:
            return False
        
        # Solo permitir letras, números, puntos y guiones bajos
        pattern = r'^[a-zA-Z0-9._]+$'
        if not re.match(pattern, username):
            return False
        
        # No puede empezar o terminar con punto o guión bajo
        if username.startswith('.') or username.startswith('_'):
            return False
        
        if username.endswith('.') or username.endswith('_'):
            return False
        
        # No puede tener puntos o guiones bajos consecutivos
        if '..' in username or '__' in username:
            return False
        
        # Longitud mínima y máxima
        if len(username) < 3 or len(username) > 30:
            return False
        
        return True


class DocumentTypeValidator:
    """
    Validador que selecciona el validador apropiado según el tipo de documento.
    """
    
    def __init__(self, document_type_field='document_type'):
        self.document_type_field = document_type_field
    
    def __call__(self, value):
        # Este validador debe ser usado en el nivel del formulario o serializer
        # donde tenemos acceso al tipo de documento
        pass
    
    def validate(self, document_number, document_type):
        """
        Validar según el tipo de documento.
        """
        if not document_number:
            return True
        
        if document_type == 'cedula':
            validator = EcuadorianCedulaValidator()
            try:
                validator(document_number)
                return True
            except ValidationError:
                return False
        
        elif document_type == 'ruc':
            validator = EcuadorianRUCValidator()
            try:
                validator(document_number)
                return True
            except ValidationError:
                return False
        
        elif document_type == 'passport':
            # Validación básica para pasaporte
            if len(document_number) < 6 or len(document_number) > 12:
                return False
            
            # Debe contener letras y números
            if not re.match(r'^[A-Z0-9]+$', document_number.upper()):
                return False
        
        return True


class EmployeeCodeValidator:
    """
    Validador para códigos de empleado.
    """
    
    def __call__(self, value):
        if value and not self.validate_employee_code(value):
            raise ValidationError(
                _('El código de empleado debe tener el formato: ABC1234 (3 letras + 4 números).'),
                code='invalid_employee_code'
            )
    
    def validate_employee_code(self, code):
        """
        Validar formato del código de empleado.
        """
        if not code:
            return True  # Permitir vacío si es opcional
        
        # Formato: 3-4 letras + 4 números (ej: EMP2024, ADMIN001)
        pattern = r'^[A-Z]{3,4}\d{4}$'
        return re.match(pattern, code.upper()) is not None


class EmailDomainValidator:
    """
    Validador que verifica dominios de email permitidos.
    """
    
    def __init__(self, allowed_domains=None, blocked_domains=None):
        self.allowed_domains = allowed_domains or []
        self.blocked_domains = blocked_domains or ['temp-mail.org', '10minutemail.com']
    
    def __call__(self, value):
        if not value:
            return True
        
        domain = value.split('@')[-1].lower()
        
        # Verificar dominios bloqueados
        if domain in self.blocked_domains:
            raise ValidationError(
                _('No se permiten emails de este dominio.'),
                code='blocked_domain'
            )
        
        # Verificar dominios permitidos (si se especificaron)
        if self.allowed_domains and domain not in self.allowed_domains:
            raise ValidationError(
                _('Solo se permiten emails de los dominios autorizados.'),
                code='domain_not_allowed'
            )
        
        return True


def validate_age(birth_date):
    """
    Validar que la edad sea apropiada para trabajar.
    """
    if not birth_date:
        return True
    
    from datetime import date
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    
    if age < 18:
        raise ValidationError(
            _('El empleado debe ser mayor de edad.'),
            code='underage'
        )
    
    if age > 100:
        raise ValidationError(
            _('Por favor verifique la fecha de nacimiento.'),
            code='invalid_age'
        )
    
    return True


def validate_hire_date(hire_date):
    """
    Validar que la fecha de contratación sea válida.
    """
    if not hire_date:
        return True
    
    from datetime import date, timedelta
    today = date.today()
    
    # No puede ser una fecha futura (permitir hasta 1 día en el futuro por zona horaria)
    if hire_date > today + timedelta(days=1):
        raise ValidationError(
            _('La fecha de contratación no puede ser futura.'),
            code='future_hire_date'
        )
    
    # No puede ser muy antigua (más de 50 años)
    if hire_date < today - timedelta(days=365 * 50):
        raise ValidationError(
            _('La fecha de contratación parece muy antigua. Por favor verifique.'),
            code='very_old_hire_date'
        )
    
    return True


# Conjunto de validadores para usar en models y forms
VALIDATORS = {
    'cedula': EcuadorianCedulaValidator(),
    'ruc': EcuadorianRUCValidator(),
    'phone': EcuadorianPhoneValidator(),
    'username': UsernameValidator(),
    'employee_code': EmployeeCodeValidator(),
    'email_domain': EmailDomainValidator(),
}


# Lista de validadores de contraseña para settings.py
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'apps.users.validators.StrongPasswordValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]