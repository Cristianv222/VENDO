"""
Utilidades para el módulo de usuarios de VENDO.
"""

import secrets
import string
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.db.models import Q
import re
import logging

from .models import User, UserSession, Role, Permission

logger = logging.getLogger('vendo.users')


def generate_random_password(length=12):
    """
    Generar una contraseña aleatoria segura.
    
    Args:
        length (int): Longitud de la contraseña
    
    Returns:
        str: Contraseña generada
    """
    # Definir caracteres permitidos
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%&*"
    
    # Asegurar que tenga al menos un carácter de cada tipo
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Completar con caracteres aleatorios
    all_chars = lowercase + uppercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # Mezclar la contraseña
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def validate_ecuadorian_cedula(cedula):
    """
    Validar cédula ecuatoriana.
    
    Args:
        cedula (str): Número de cédula
    
    Returns:
        bool: True si es válida, False caso contrario
    """
    if not cedula or len(cedula) != 10:
        return False
    
    if not cedula.isdigit():
        return False
    
    # Los dos primeros dígitos deben ser válidos (01-24)
    provincia = int(cedula[:2])
    if provincia < 1 or provincia > 24:
        return False
    
    # Algoritmo de validación
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    
    for i in range(9):
        valor = int(cedula[i]) * coeficientes[i]
        if valor >= 10:
            valor = valor - 9
        suma += valor
    
    digito_verificador = (10 - (suma % 10)) % 10
    
    return digito_verificador == int(cedula[9])


def validate_ecuadorian_ruc(ruc):
    """
    Validar RUC ecuatoriano.
    
    Args:
        ruc (str): Número de RUC
    
    Returns:
        bool: True si es válido, False caso contrario
    """
    if not ruc or len(ruc) != 13:
        return False
    
    if not ruc.isdigit():
        return False
    
    # RUC de persona natural (termina en 001)
    if ruc.endswith('001'):
        return validate_ecuadorian_cedula(ruc[:10])
    
    # RUC de empresa privada
    tipo = int(ruc[2])
    if tipo == 9:
        return validate_ruc_juridico(ruc)
    
    # RUC de empresa pública
    if tipo == 6:
        return validate_ruc_publico(ruc)
    
    return False


def validate_ruc_juridico(ruc):
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


def validate_ruc_publico(ruc):
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


def validate_phone_number(phone):
    """
    Validar número de teléfono ecuatoriano.
    
    Args:
        phone (str): Número de teléfono
    
    Returns:
        bool: True si es válido, False caso contrario
    """
    if not phone:
        return True  # Teléfono es opcional
    
    # Remover espacios y caracteres especiales
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


def format_phone_number(phone):
    """
    Formatear número de teléfono a formato estándar.
    
    Args:
        phone (str): Número de teléfono
    
    Returns:
        str: Teléfono formateado
    """
    if not phone:
        return ''
    
    # Remover caracteres no numéricos excepto +
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Si no tiene código de país, agregarlo
    if not clean_phone.startswith('+593'):
        if clean_phone.startswith('0'):
            clean_phone = '+593' + clean_phone[1:]
        elif clean_phone.startswith('9'):
            clean_phone = '+593' + clean_phone
        elif len(clean_phone) in [7, 8]:
            clean_phone = '+593' + clean_phone
    
    return clean_phone


def generate_employee_code(user_type='EMP'):
    """
    Generar código único de empleado.
    
    Args:
        user_type (str): Tipo de usuario para el prefijo
    
    Returns:
        str: Código de empleado generado
    """
    year = datetime.now().year
    
    # Buscar el último código generado para el año actual
    last_user = User.objects.filter(
        employee_code__startswith=f'{user_type}{year}',
        user_type='employee'
    ).order_by('employee_code').last()
    
    if last_user and last_user.employee_code:
        # Extraer el número del último código
        try:
            last_number = int(last_user.employee_code[-4:])
            next_number = last_number + 1
        except (ValueError, IndexError):
            next_number = 1
    else:
        next_number = 1
    
    return f'{user_type}{year}{next_number:04d}'


def send_password_reset_email(user, request=None):
    """
    Enviar email de restablecimiento de contraseña.
    
    Args:
        user: Usuario al que enviar el email
        request: Objeto request para construir URLs absolutas
    
    Returns:
        bool: True si se envió correctamente, False caso contrario
    """
    try:
        # Generar token de restablecimiento
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Construir URL de restablecimiento
        reset_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:8000')}/reset-password/{uid}/{token}/"
        
        # Preparar contexto del email
        context = {
            'user': user,
            'reset_url': reset_url,
            'company_name': getattr(settings, 'COMPANY_NAME', 'VENDO'),
            'valid_hours': 24,
        }
        
        # Renderizar email
        subject = f'Restablecer contraseña - {context["company_name"]}'
        html_message = render_to_string('emails/password_reset.html', context)
        plain_message = render_to_string('emails/password_reset.txt', context)
        
        # Enviar email
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"Email de restablecimiento enviado a: {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Error enviando email de restablecimiento a {user.email}: {str(e)}")
        return False


def send_account_activation_email(user, request=None):
    """
    Enviar email de activación de cuenta.
    
    Args:
        user: Usuario al que enviar el email
        request: Objeto request para construir URLs absolutas
    
    Returns:
        bool: True si se envió correctamente, False caso contrario
    """
    try:
        # Generar token de activación
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Construir URL de activación
        activation_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:8000')}/activate/{uid}/{token}/"
        
        # Preparar contexto del email
        context = {
            'user': user,
            'activation_url': activation_url,
            'company_name': getattr(settings, 'COMPANY_NAME', 'VENDO'),
        }
        
        # Renderizar email
        subject = f'Activar cuenta - {context["company_name"]}'
        html_message = render_to_string('emails/account_activation.html', context)
        plain_message = render_to_string('emails/account_activation.txt', context)
        
        # Enviar email
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"Email de activación enviado a: {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Error enviando email de activación a {user.email}: {str(e)}")
        return False


def cleanup_expired_sessions(hours=24):
    """
    Limpiar sesiones expiradas.
    
    Args:
        hours (int): Horas de inactividad para considerar expirada
    
    Returns:
        int: Número de sesiones limpiadas
    """
    try:
        cutoff_time = timezone.now() - timedelta(hours=hours)
        expired_sessions = UserSession.objects.filter(
            last_activity__lt=cutoff_time,
            is_active=True
        )
        
        count = expired_sessions.count()
        expired_sessions.update(is_active=False)
        
        logger.info(f"Se marcaron {count} sesiones como expiradas")
        return count
        
    except Exception as e:
        logger.error(f"Error limpiando sesiones expiradas: {str(e)}")
        return 0


def get_user_permissions_by_module(user):
    """
    Obtener permisos del usuario organizados por módulo.
    
    Args:
        user: Usuario
    
    Returns:
        dict: Permisos organizados por módulo
    """
    if not user or not user.is_authenticated:
        return {}
    
    permissions = {}
    
    # Obtener permisos directos del usuario
    user_permissions = user.permissions.filter(is_active=True)
    
    # Obtener permisos de roles
    role_permissions = Permission.objects.filter(
        userpermission__user=user,
        userpermission__is_active=True,
        is_active=True
    ).distinct()
    
    # Combinar permisos
    all_permissions = user_permissions.union(role_permissions)
    
    # Organizar por módulo
    for permission in all_permissions:
        module = permission.module
        if module not in permissions:
            permissions[module] = []
        permissions[module].append({
            'code': permission.code,
            'name': permission.name,
            'description': permission.description
        })
    
    return permissions


def check_user_activity(user, days=30):
    """
    Verificar actividad reciente del usuario.
    
    Args:
        user: Usuario a verificar
        days (int): Días a verificar hacia atrás
    
    Returns:
        dict: Información de actividad del usuario
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Sesiones recientes
    recent_sessions = UserSession.objects.filter(
        user=user,
        created_at__gte=cutoff_date
    ).count()
    
    # Última actividad
    last_session = UserSession.objects.filter(
        user=user
    ).order_by('-last_activity').first()
    
    return {
        'recent_sessions': recent_sessions,
        'last_activity': last_session.last_activity if last_session else None,
        'days_inactive': (timezone.now() - user.last_activity).days if user.last_activity else None,
        'is_active_user': recent_sessions > 0
    }


def suggest_username(first_name, last_name, document_number=None):
    """
    Sugerir nombre de usuario basado en los datos del usuario.
    
    Args:
        first_name (str): Nombre
        last_name (str): Apellido
        document_number (str): Número de documento
    
    Returns:
        str: Nombre de usuario sugerido y único
    """
    # Limpiar y normalizar nombres
    first_clean = re.sub(r'[^a-zA-Z]', '', first_name.lower()) if first_name else ''
    last_clean = re.sub(r'[^a-zA-Z]', '', last_name.lower()) if last_name else ''
    
    # Generar opciones de username
    suggestions = []
    
    if first_clean and last_clean:
        suggestions.extend([
            f"{first_clean}.{last_clean}",
            f"{first_clean}{last_clean}",
            f"{first_clean[0]}{last_clean}",
            f"{first_clean}.{last_clean[0]}",
        ])
    
    if document_number:
        doc_clean = re.sub(r'[^0-9]', '', document_number)
        if first_clean:
            suggestions.append(f"{first_clean}{doc_clean[-4:]}")
        if last_clean:
            suggestions.append(f"{last_clean}{doc_clean[-4:]}")
    
    # Si no hay nombres, usar documento
    if not suggestions and document_number:
        suggestions.append(f"user{document_number[-6:]}")
    
    # Verificar disponibilidad y retornar el primero disponible
    for suggestion in suggestions:
        if not User.objects.filter(username=suggestion).exists():
            return suggestion
    
    # Si todos están ocupados, agregar número
    base = suggestions[0] if suggestions else 'user'
    counter = 1
    while User.objects.filter(username=f"{base}{counter}").exists():
        counter += 1
    
    return f"{base}{counter}"


def create_initial_permissions():
    """
    Crear permisos iniciales del sistema.
    
    Returns:
        int: Número de permisos creados
    """
    permissions_data = [
        # POS Permissions
        {'name': 'Ver POS', 'code': 'pos_view', 'module': 'pos'},
        {'name': 'Crear Venta', 'code': 'pos_create_sale', 'module': 'pos'},
        {'name': 'Cancelar Venta', 'code': 'pos_cancel_sale', 'module': 'pos'},
        {'name': 'Gestionar Caja', 'code': 'pos_manage_cash', 'module': 'pos'},
        
        # Inventory Permissions
        {'name': 'Ver Inventario', 'code': 'inventory_view', 'module': 'inventory'},
        {'name': 'Crear Productos', 'code': 'inventory_create', 'module': 'inventory'},
        {'name': 'Editar Productos', 'code': 'inventory_edit', 'module': 'inventory'},
        {'name': 'Eliminar Productos', 'code': 'inventory_delete', 'module': 'inventory'},
        {'name': 'Ajustar Stock', 'code': 'inventory_adjust', 'module': 'inventory'},
        
        # Invoicing Permissions
        {'name': 'Ver Facturas', 'code': 'invoice_view', 'module': 'invoicing'},
        {'name': 'Crear Facturas', 'code': 'invoice_create', 'module': 'invoicing'},
        {'name': 'Editar Facturas', 'code': 'invoice_edit', 'module': 'invoicing'},
        {'name': 'Anular Facturas', 'code': 'invoice_cancel', 'module': 'invoicing'},
        {'name': 'Enviar a SRI', 'code': 'invoice_send_sri', 'module': 'invoicing'},
        
        # Reports Permissions
        {'name': 'Ver Reportes', 'code': 'reports_view', 'module': 'reports'},
        {'name': 'Exportar Reportes', 'code': 'reports_export', 'module': 'reports'},
        {'name': 'Reportes Financieros', 'code': 'reports_financial', 'module': 'reports'},
        
        # Admin Permissions
        {'name': 'Gestionar Usuarios', 'code': 'admin_users', 'module': 'admin'},
        {'name': 'Configurar Sistema', 'code': 'admin_settings', 'module': 'admin'},
        {'name': 'Gestionar Respaldos', 'code': 'admin_backup', 'module': 'admin'},
    ]
    
    created_count = 0
    for perm_data in permissions_data:
        permission, created = Permission.objects.get_or_create(
            code=perm_data['code'],
            defaults={
                'name': perm_data['name'],
                'module': perm_data['module'],
                'is_active': True
            }
        )
        
        if created:
            created_count += 1
            logger.info(f"Permiso creado: {permission.name}")
    
    return created_count


def create_initial_roles():
    """
    Crear roles iniciales del sistema.
    
    Returns:
        int: Número de roles creados
    """
    roles_data = [
        {
            'name': 'Administrador',
            'code': 'admin',
            'description': 'Acceso completo al sistema'
        },
        {
            'name': 'Gerente',
            'code': 'manager',
            'description': 'Gestión general y reportes'
        },
        {
            'name': 'Cajero',
            'code': 'cashier',
            'description': 'Operación del punto de venta'
        },
        {
            'name': 'Encargado de Inventario',
            'code': 'inventory_manager',
            'description': 'Gestión de productos e inventario'
        },
        {
            'name': 'Contador',
            'code': 'accountant',
            'description': 'Gestión contable y financiera'
        },
        {
            'name': 'Vendedor',
            'code': 'sales_rep',
            'description': 'Ventas y atención al cliente'
        },
        {
            'name': 'Solo Lectura',
            'code': 'viewer',
            'description': 'Solo visualización de información'
        },
    ]
    
    created_count = 0
    for role_data in roles_data:
        role, created = Role.objects.get_or_create(
            code=role_data['code'],
            defaults={
                'name': role_data['name'],
                'description': role_data['description'],
                'is_active': True
            }
        )
        
        if created:
            created_count += 1
            logger.info(f"Rol creado: {role.name}")
    
    return created_count