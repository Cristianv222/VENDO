"""
Utilidades del módulo Users
"""
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError

# Solo importar para anotaciones de tipo
if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

from .models import Role, Permission, UserSession
from apps.core.models import Company

# Para uso en runtime
User = get_user_model()


def generate_username(first_name: str, last_name: str, email: str = None) -> str:
    """
    Generar un nombre de usuario único
    """
    # Intentar con nombre.apellido
    base_username = f"{first_name.lower()}.{last_name.lower()}"
    base_username = base_username.replace(' ', '').replace('ñ', 'n')
    
    # Remover caracteres especiales
    allowed_chars = string.ascii_lowercase + string.digits + '._-'
    base_username = ''.join(c for c in base_username if c in allowed_chars)
    
    # Si está disponible, usarlo
    if not User.objects.filter(username=base_username).exists():
        return base_username
    
    # Si no está disponible, intentar con email
    if email:
        email_username = email.split('@')[0]
        if not User.objects.filter(username=email_username).exists():
            return email_username
    
    # Si no, agregar números
    counter = 1
    while User.objects.filter(username=f"{base_username}{counter}").exists():
        counter += 1
    
    return f"{base_username}{counter}"


def generate_temporary_password(length: int = 12) -> str:
    """
    Generar una contraseña temporal segura
    """
    # Caracteres permitidos
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%&*"
    
    # Asegurar que tenga al menos uno de cada tipo
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Completar el resto de la longitud
    all_chars = lowercase + uppercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # Mezclar los caracteres
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def send_password_reset_email(user: 'AbstractUser', reset_url: str) -> bool:
    """
    Enviar email de reseteo de contraseña
    """
    try:
        subject = f'Resetear contraseña - {settings.SITE_NAME or "VENDO"}'
        
        html_message = render_to_string('users/emails/password_reset.html', {
            'user': user,
            'reset_url': reset_url,
            'site_name': settings.SITE_NAME or 'VENDO',
            'expiry_hours': 24
        })
        
        plain_message = f'''
        Hola {user.get_full_name()},
        
        Se ha solicitado resetear tu contraseña. Haz clic en el siguiente enlace:
        {reset_url}
        
        Este enlace expira en 24 horas.
        
        Si no solicitaste este cambio, ignora este email.
        '''
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        return True
        
    except Exception as e:
        print(f"Error enviando email de reseteo: {e}")
        return False


def send_new_user_credentials(user: 'AbstractUser', temporary_password: str) -> bool:
    """
    Enviar credenciales a usuario nuevo
    """
    try:
        subject = f'Credenciales de acceso - {settings.SITE_NAME or "VENDO"}'
        
        html_message = render_to_string('users/emails/new_user_credentials.html', {
            'user': user,
            'username': user.username,
            'password': temporary_password,
            'login_url': f"{settings.SITE_URL}/users/login/" if hasattr(settings, 'SITE_URL') else None,
            'site_name': settings.SITE_NAME or 'VENDO'
        })
        
        plain_message = f'''
        Hola {user.get_full_name()},
        
        Se ha creado tu cuenta en {settings.SITE_NAME or "VENDO"}.
        
        Tus credenciales de acceso son:
        Usuario: {user.username}
        Contraseña temporal: {temporary_password}
        
        Por seguridad, debes cambiar tu contraseña al primer inicio de sesión.
        '''
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        return True
        
    except Exception as e:
        print(f"Error enviando credenciales: {e}")
        return False


def validate_password_strength(password: str) -> List[str]:
    """
    Validar la fortaleza de una contraseña
    """
    errors = []
    
    if len(password) < 8:
        errors.append("La contraseña debe tener al menos 8 caracteres")
    
    if not any(c.islower() for c in password):
        errors.append("La contraseña debe tener al menos una letra minúscula")
    
    if not any(c.isupper() for c in password):
        errors.append("La contraseña debe tener al menos una letra mayúscula")
    
    if not any(c.isdigit() for c in password):
        errors.append("La contraseña debe tener al menos un número")
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("La contraseña debe tener al menos un carácter especial")
    
    # Verificar patrones comunes
    common_patterns = [
        '123456', 'password', 'qwerty', 'abc123', 'admin',
        '12345678', 'welcome', 'login', 'user'
    ]
    
    if password.lower() in common_patterns:
        errors.append("No se permiten contraseñas comunes")
    
    return errors


def create_default_roles() -> List[Role]:
    """
    Crear roles por defecto del sistema
    """
    default_roles = [
        {
            'name': 'Administrador',
            'description': 'Acceso completo al sistema',
            'color': '#dc3545',
            'is_system_role': True,
            'permissions': ['*']  # Todos los permisos
        },
        {
            'name': 'Gerente',
            'description': 'Gestión de la empresa y reportes',
            'color': '#fd7e14',
            'is_system_role': True,
            'permissions': [
                'core.view_company', 'core.change_company',
                'users.view_user', 'users.add_user', 'users.change_user',
                'reports.view_report', 'reports.generate_report'
            ]
        },
        {
            'name': 'Vendedor',
            'description': 'Punto de venta y cotizaciones',
            'color': '#198754',
            'is_system_role': True,
            'permissions': [
                'pos.add_sale', 'pos.view_sale',
                'quotations.add_quotation', 'quotations.view_quotation',
                'inventory.view_product'
            ]
        },
        {
            'name': 'Contador',
            'description': 'Facturación y contabilidad',
            'color': '#0dcaf0',
            'is_system_role': True,
            'permissions': [
                'invoicing.add_invoice', 'invoicing.view_invoice',
                'accounting.view_account', 'accounting.add_transaction',
                'reports.view_financial_report'
            ]
        },
        {
            'name': 'Bodeguero',
            'description': 'Gestión de inventario',
            'color': '#6f42c1',
            'is_system_role': True,
            'permissions': [
                'inventory.add_product', 'inventory.change_product',
                'inventory.view_stock', 'inventory.add_movement',
                'purchases.view_purchase'
            ]
        }
    ]
    
    created_roles = []
    
    for role_data in default_roles:
        role, created = Role.objects.get_or_create(
            name=role_data['name'],
            defaults={
                'description': role_data['description'],
                'color': role_data['color'],
                'is_system_role': role_data['is_system_role']
            }
        )
        
        if created:
            created_roles.append(role)
            
            # Asignar permisos
            if role_data['permissions'] == ['*']:
                # Todos los permisos
                role.permissions.set(Permission.objects.all())
            else:
                # Permisos específicos
                permissions = Permission.objects.filter(
                    codename__in=role_data['permissions']
                )
                role.permissions.set(permissions)
    
    return created_roles


def create_default_permissions() -> List[Permission]:
    """
    Crear permisos por defecto del sistema
    """
    default_permissions = [
        # Core
        {'name': 'Ver empresa', 'codename': 'view_company', 'module': 'core'},
        {'name': 'Cambiar empresa', 'codename': 'change_company', 'module': 'core'},
        {'name': 'Ver sucursal', 'codename': 'view_branch', 'module': 'core'},
        {'name': 'Agregar sucursal', 'codename': 'add_branch', 'module': 'core'},
        {'name': 'Cambiar sucursal', 'codename': 'change_branch', 'module': 'core'},
        
        # Users
        {'name': 'Ver usuario', 'codename': 'view_user', 'module': 'users'},
        {'name': 'Agregar usuario', 'codename': 'add_user', 'module': 'users'},
        {'name': 'Cambiar usuario', 'codename': 'change_user', 'module': 'users'},
        {'name': 'Eliminar usuario', 'codename': 'delete_user', 'module': 'users'},
        {'name': 'Gestionar roles', 'codename': 'manage_roles', 'module': 'users'},
        
        # POS
        {'name': 'Ver venta', 'codename': 'view_sale', 'module': 'pos'},
        {'name': 'Agregar venta', 'codename': 'add_sale', 'module': 'pos'},
        {'name': 'Anular venta', 'codename': 'void_sale', 'module': 'pos'},
        {'name': 'Ver caja', 'codename': 'view_cash_register', 'module': 'pos'},
        {'name': 'Gestionar caja', 'codename': 'manage_cash_register', 'module': 'pos'},
        
        # Inventory
        {'name': 'Ver producto', 'codename': 'view_product', 'module': 'inventory'},
        {'name': 'Agregar producto', 'codename': 'add_product', 'module': 'inventory'},
        {'name': 'Cambiar producto', 'codename': 'change_product', 'module': 'inventory'},
        {'name': 'Ver stock', 'codename': 'view_stock', 'module': 'inventory'},
        {'name': 'Ajustar stock', 'codename': 'adjust_stock', 'module': 'inventory'},
        {'name': 'Ver movimiento', 'codename': 'view_movement', 'module': 'inventory'},
        {'name': 'Agregar movimiento', 'codename': 'add_movement', 'module': 'inventory'},
        
        # Invoicing
        {'name': 'Ver factura', 'codename': 'view_invoice', 'module': 'invoicing'},
        {'name': 'Agregar factura', 'codename': 'add_invoice', 'module': 'invoicing'},
        {'name': 'Anular factura', 'codename': 'void_invoice', 'module': 'invoicing'},
        {'name': 'Autorizar factura', 'codename': 'authorize_invoice', 'module': 'invoicing'},
        
        # Purchases
        {'name': 'Ver compra', 'codename': 'view_purchase', 'module': 'purchases'},
        {'name': 'Agregar compra', 'codename': 'add_purchase', 'module': 'purchases'},
        {'name': 'Ver proveedor', 'codename': 'view_supplier', 'module': 'purchases'},
        {'name': 'Gestionar proveedores', 'codename': 'manage_suppliers', 'module': 'purchases'},
        
        # Accounting
        {'name': 'Ver cuenta', 'codename': 'view_account', 'module': 'accounting'},
        {'name': 'Agregar transacción', 'codename': 'add_transaction', 'module': 'accounting'},
        {'name': 'Ver cuentas por cobrar', 'codename': 'view_receivable', 'module': 'accounting'},
        {'name': 'Ver cuentas por pagar', 'codename': 'view_payable', 'module': 'accounting'},
        
        # Quotations
        {'name': 'Ver cotización', 'codename': 'view_quotation', 'module': 'quotations'},
        {'name': 'Agregar cotización', 'codename': 'add_quotation', 'module': 'quotations'},
        {'name': 'Aprobar cotización', 'codename': 'approve_quotation', 'module': 'quotations'},
        
        # Reports
        {'name': 'Ver reporte', 'codename': 'view_report', 'module': 'reports'},
        {'name': 'Generar reporte', 'codename': 'generate_report', 'module': 'reports'},
        {'name': 'Ver reporte financiero', 'codename': 'view_financial_report', 'module': 'reports'},
        {'name': 'Exportar reporte', 'codename': 'export_report', 'module': 'reports'},
        
        # Settings
        {'name': 'Ver configuración', 'codename': 'view_settings', 'module': 'settings'},
        {'name': 'Cambiar configuración', 'codename': 'change_settings', 'module': 'settings'},
        {'name': 'Gestionar impuestos', 'codename': 'manage_taxes', 'module': 'settings'},
    ]
    
    created_permissions = []
    
    for perm_data in default_permissions:
        permission, created = Permission.objects.get_or_create(
            codename=perm_data['codename'],
            defaults={
                'name': perm_data['name'],
                'module': perm_data['module'],
                'description': f"Permite {perm_data['name'].lower()}"
            }
        )
        
        if created:
            created_permissions.append(permission)
    
    return created_permissions


def get_user_permissions_for_company(user: 'AbstractUser', company: Company) -> List[str]:
    """
    Obtener todos los permisos de un usuario para una empresa
    """
    if user.is_system_admin:
        return list(Permission.objects.values_list('codename', flat=True))
    
    # Obtener permisos a través de roles
    permissions = Permission.objects.filter(
        roles__usercompany__user=user,
        roles__usercompany__company=company
    ).distinct().values_list('codename', flat=True)
    
    return list(permissions)


def cleanup_expired_sessions(days_old: int = 30) -> int:
    """
    Limpiar sesiones expiradas
    """
    cutoff_date = timezone.now() - timedelta(days=days_old)
    
    # Marcar como expiradas
    expired_count = UserSession.objects.filter(
        last_activity__lt=cutoff_date,
        logout_at__isnull=True
    ).update(
        is_expired=True,
        logout_at=timezone.now()
    )
    
    return expired_count


def get_active_users_count(company: Company = None) -> int:
    """
    Obtener número de usuarios activos
    """
    queryset = User.objects.filter(is_active=True)
    
    if company:
        queryset = queryset.filter(companies=company)
    
    return queryset.count()


def get_user_activity_stats(user: 'AbstractUser', days: int = 30) -> Dict[str, Any]:
    """
    Obtener estadísticas de actividad de un usuario
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    sessions = UserSession.objects.filter(
        user=user,
        login_at__gte=cutoff_date
    )
    
    return {
        'total_sessions': sessions.count(),
        'active_sessions': sessions.filter(logout_at__isnull=True, is_expired=False).count(),
        'total_login_time': sum([
            (s.logout_at or s.last_activity) - s.login_at 
            for s in sessions
        ], timedelta()).total_seconds(),
        'last_login': user.last_login,
        'last_activity': user.last_activity,
    }