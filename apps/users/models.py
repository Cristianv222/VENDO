"""
Modelos para el módulo de usuarios de VENDO.
Incluye User personalizado, Roles, Permisos y Perfiles.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid
from datetime import datetime


class Role(models.Model):
    """
    Modelo para gestionar roles de usuario en el sistema.
    """
    ROLE_TYPES = [
        ('admin', _('Administrador')),
        ('manager', _('Gerente')),
        ('cashier', _('Cajero')),
        ('inventory_manager', _('Encargado de Inventario')),
        ('accountant', _('Contador')),
        ('sales_rep', _('Vendedor')),
        ('viewer', _('Solo Lectura')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Nombre'), max_length=50, unique=True)
    code = models.CharField(
        _('Código'), 
        max_length=20, 
        unique=True,
        choices=ROLE_TYPES
    )
    description = models.TextField(_('Descripción'), blank=True)
    is_active = models.BooleanField(_('Activo'), default=True)
    created_at = models.DateTimeField(_('Creado en'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Actualizado en'), auto_now=True)

    class Meta:
        db_table = 'users_role'
        verbose_name = _('Rol')
        verbose_name_plural = _('Roles')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def user_count(self):
        """Cantidad de usuarios con este rol."""
        return self.vendo_users.filter(is_active=True).count()


class Permission(models.Model):
    """
    Modelo para gestionar permisos específicos del sistema VENDO.
    """
    PERMISSION_TYPES = [
        # POS Permissions
        ('pos_view', _('Ver POS')),
        ('pos_create_sale', _('Crear Venta')),
        ('pos_cancel_sale', _('Cancelar Venta')),
        ('pos_manage_cash', _('Gestionar Caja')),
        
        # Inventory Permissions
        ('inventory_view', _('Ver Inventario')),
        ('inventory_create', _('Crear Productos')),
        ('inventory_edit', _('Editar Productos')),
        ('inventory_delete', _('Eliminar Productos')),
        ('inventory_adjust', _('Ajustar Stock')),
        
        # Invoicing Permissions
        ('invoice_view', _('Ver Facturas')),
        ('invoice_create', _('Crear Facturas')),
        ('invoice_edit', _('Editar Facturas')),
        ('invoice_cancel', _('Anular Facturas')),
        ('invoice_send_sri', _('Enviar a SRI')),
        
        # Reports Permissions
        ('reports_view', _('Ver Reportes')),
        ('reports_export', _('Exportar Reportes')),
        ('reports_financial', _('Reportes Financieros')),
        
        # Admin Permissions
        ('admin_users', _('Gestionar Usuarios')),
        ('admin_settings', _('Configurar Sistema')),
        ('admin_backup', _('Gestionar Respaldos')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Nombre'), max_length=100)
    code = models.CharField(
        _('Código'), 
        max_length=50, 
        unique=True,
        choices=PERMISSION_TYPES
    )
    description = models.TextField(_('Descripción'), blank=True)
    module = models.CharField(_('Módulo'), max_length=50)
    is_active = models.BooleanField(_('Activo'), default=True)
    created_at = models.DateTimeField(_('Creado en'), auto_now_add=True)

    class Meta:
        db_table = 'users_permission'
        verbose_name = _('Permiso')
        verbose_name_plural = _('Permisos')
        ordering = ['module', 'name']

    def __str__(self):
        return f"{self.module} - {self.name}"


class User(AbstractUser):
    """
    Modelo de usuario personalizado para VENDO.
    Extiende el usuario de Django con campos específicos del negocio.
    """
    USER_TYPES = [
        ('admin', _('Administrador')),
        ('employee', _('Empleado')),
        ('customer', _('Cliente')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Sobrescribir campos de AbstractUser para evitar conflictos
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_('The groups this user belongs to.'),
        related_name='vendo_users',
        related_query_name='vendo_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='vendo_users',
        related_query_name='vendo_user',
    )
    
    # Información personal
    document_type = models.CharField(
        _('Tipo de Documento'),
        max_length=10,
        choices=[
            ('cedula', _('Cédula')),
            ('ruc', _('RUC')),
            ('passport', _('Pasaporte')),
        ],
        default='cedula'
    )
    document_number = models.CharField(
        _('Número de Documento'), 
        max_length=20, 
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[0-9]+$',
                message=_('Solo se permiten números.')
            )
        ]
    )
    phone = models.CharField(
        _('Teléfono'), 
        max_length=15, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message=_('Formato de teléfono inválido.')
            )
        ]
    )
    address = models.TextField(_('Dirección'), blank=True)
    
    # Información laboral
    user_type = models.CharField(
        _('Tipo de Usuario'),
        max_length=20,
        choices=USER_TYPES,
        default='employee'
    )
    employee_code = models.CharField(
        _('Código de Empleado'), 
        max_length=20, 
        blank=True, 
        unique=True,
        null=True
    )
    hire_date = models.DateField(_('Fecha de Contratación'), null=True, blank=True)
    department = models.CharField(_('Departamento'), max_length=100, blank=True)
    position = models.CharField(_('Cargo'), max_length=100, blank=True)
    
    # Relaciones con through_fields especificados para evitar ambigüedad
    roles = models.ManyToManyField(
        Role, 
        through='UserRole',
        through_fields=('user', 'role'),
        related_name='vendo_users',
        blank=True
    )
    permissions = models.ManyToManyField(
        Permission,
        through='UserPermission',
        through_fields=('user', 'permission'),
        related_name='vendo_users',
        blank=True
    )
    
    # Configuraciones
    is_active = models.BooleanField(_('Activo'), default=True)
    failed_login_attempts = models.PositiveIntegerField(
        _('Intentos de Login Fallidos'), 
        default=0
    )
    last_password_change = models.DateTimeField(
        _('Último Cambio de Contraseña'), 
        null=True, 
        blank=True
    )
    force_password_change = models.BooleanField(
        _('Forzar Cambio de Contraseña'), 
        default=False
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('Creado en'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Actualizado en'), auto_now=True)
    last_activity = models.DateTimeField(_('Última Actividad'), null=True, blank=True)

    class Meta:
        db_table = 'users_user'
        verbose_name = _('Usuario')
        verbose_name_plural = _('Usuarios')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"

    def save(self, *args, **kwargs):
        # Generar código de empleado automáticamente si no existe
        if not self.employee_code and self.user_type == 'employee':
            self.employee_code = self.generate_employee_code()
        super().save(*args, **kwargs)

    def generate_employee_code(self):
        """Genera un código único de empleado."""
        year = datetime.now().year
        count = User.objects.filter(
            employee_code__startswith=f'EMP{year}',
            user_type='employee'
        ).count() + 1
        return f'EMP{year}{count:04d}'

    @property
    def full_name(self):
        """Retorna el nombre completo del usuario."""
        return self.get_full_name() or self.username

    @property
    def primary_role(self):
        """Retorna el rol principal del usuario."""
        return self.roles.filter(is_active=True).first()

    def has_permission(self, permission_code):
        """Verifica si el usuario tiene un permiso específico."""
        return self.permissions.filter(
            code=permission_code, 
            is_active=True
        ).exists()

    def has_role(self, role_code):
        """Verifica si el usuario tiene un rol específico."""
        return self.roles.filter(
            code=role_code, 
            is_active=True
        ).exists()

    def is_admin(self):
        """Verifica si el usuario es administrador."""
        return self.has_role('admin') or self.is_superuser

    def can_access_module(self, module_name):
        """Verifica si el usuario puede acceder a un módulo."""
        return self.permissions.filter(
            module=module_name,
            is_active=True
        ).exists()

    def reset_failed_attempts(self):
        """Resetea los intentos fallidos de login."""
        self.failed_login_attempts = 0
        self.save(update_fields=['failed_login_attempts'])

    def increment_failed_attempts(self):
        """Incrementa los intentos fallidos de login."""
        self.failed_login_attempts += 1
        self.save(update_fields=['failed_login_attempts'])

    def is_account_locked(self):
        """Verifica si la cuenta está bloqueada por intentos fallidos."""
        max_attempts = getattr(settings, 'MAX_FAILED_LOGIN_ATTEMPTS', 5)
        return self.failed_login_attempts >= max_attempts


class UserRole(models.Model):
    """
    Modelo intermedio para la relación Usuario-Rol.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='assigned_roles'
    )
    assigned_at = models.DateTimeField(_('Asignado en'), auto_now_add=True)
    is_active = models.BooleanField(_('Activo'), default=True)

    class Meta:
        db_table = 'users_user_role'
        unique_together = ['user', 'role']
        verbose_name = _('Rol de Usuario')
        verbose_name_plural = _('Roles de Usuario')

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class UserPermission(models.Model):
    """
    Modelo intermedio para la relación Usuario-Permiso.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    granted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='granted_permissions'
    )
    granted_at = models.DateTimeField(_('Otorgado en'), auto_now_add=True)
    is_active = models.BooleanField(_('Activo'), default=True)

    class Meta:
        db_table = 'users_user_permission'
        unique_together = ['user', 'permission']
        verbose_name = _('Permiso de Usuario')
        verbose_name_plural = _('Permisos de Usuario')

    def __str__(self):
        return f"{self.user.username} - {self.permission.name}"


class UserProfile(models.Model):
    """
    Perfil extendido del usuario con configuraciones adicionales.
    """
    THEMES = [
        ('light', _('Claro')),
        ('dark', _('Oscuro')),
        ('auto', _('Automático')),
    ]

    LANGUAGES = [
        ('es', _('Español')),
        ('en', _('English')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    # Información adicional
    avatar = models.ImageField(
        _('Avatar'), 
        upload_to='avatars/', 
        blank=True, 
        null=True
    )
    birth_date = models.DateField(_('Fecha de Nacimiento'), null=True, blank=True)
    bio = models.TextField(_('Biografía'), blank=True, max_length=500)
    
    # Preferencias
    theme = models.CharField(
        _('Tema'), 
        max_length=10, 
        choices=THEMES, 
        default='light'
    )
    language = models.CharField(
        _('Idioma'), 
        max_length=5, 
        choices=LANGUAGES, 
        default='es'
    )
    timezone = models.CharField(
        _('Zona Horaria'), 
        max_length=50, 
        default='America/Guayaquil'
    )
    
    # Configuraciones de notificación
    email_notifications = models.BooleanField(
        _('Notificaciones por Email'), 
        default=True
    )
    sms_notifications = models.BooleanField(
        _('Notificaciones por SMS'), 
        default=False
    )
    push_notifications = models.BooleanField(
        _('Notificaciones Push'), 
        default=True
    )
    
    # Configuraciones del POS
    default_pos_session_timeout = models.PositiveIntegerField(
        _('Timeout de Sesión POS (minutos)'), 
        default=60
    )
    auto_print_receipts = models.BooleanField(
        _('Imprimir Recibos Automáticamente'), 
        default=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('Creado en'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Actualizado en'), auto_now=True)

    class Meta:
        db_table = 'users_user_profile'
        verbose_name = _('Perfil de Usuario')
        verbose_name_plural = _('Perfiles de Usuario')

    def __str__(self):
        return f"Perfil de {self.user.username}"

    @property
    def age(self):
        """Calcula la edad del usuario."""
        if self.birth_date:
            from datetime import date
            today = date.today()
            return today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None


class UserSession(models.Model):
    """
    Modelo para gestionar sesiones activas de usuarios.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(_('Clave de Sesión'), max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(_('Dirección IP'))
    user_agent = models.TextField(_('User Agent'), blank=True)
    location = models.CharField(_('Ubicación'), max_length=100, blank=True)
    is_active = models.BooleanField(_('Activa'), default=True)
    created_at = models.DateTimeField(_('Creada en'), auto_now_add=True)
    last_activity = models.DateTimeField(_('Última Actividad'), auto_now=True)

    class Meta:
        db_table = 'users_user_session'
        verbose_name = _('Sesión de Usuario')
        verbose_name_plural = _('Sesiones de Usuario')
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"

    @property
    def is_expired(self):
        """Verifica si la sesión ha expirado."""
        from datetime import timedelta
        from django.utils import timezone
        
        timeout = getattr(settings, 'SESSION_TIMEOUT_MINUTES', 60)
        expiry_time = self.last_activity + timedelta(minutes=timeout)
        return timezone.now() > expiry_time
    """
Actualización del modelo User para incluir campos faltantes.
Agregar estos campos al modelo User existente.
"""

# AGREGAR ESTOS CAMPOS AL MODELO USER EXISTENTE:
    # CAMPOS ADICIONALES REQUERIDOS:
    
    # Configuración de seguridad
    failed_login_attempts = models.PositiveIntegerField(
        _('Intentos fallidos'),
        default=0,
        help_text=_('Número de intentos de login fallidos')
    )
    
    force_password_change = models.BooleanField(
        _('Forzar cambio de contraseña'),
        default=False,
        help_text=_('Usuario debe cambiar contraseña en siguiente login')
    )
    
    last_password_change = models.DateTimeField(
        _('Último cambio de contraseña'),
        blank=True,
        null=True
    )
    
    last_activity = models.DateTimeField(
        _('Última actividad'),
        blank=True,
        null=True
    )
    
    # Información adicional
    document_number = models.CharField(
        _('Número de documento'),
        max_length=20,
        blank=True,
        help_text=_('Cédula, RUC o pasaporte')
    )
    
    department = models.CharField(
        _('Departamento'),
        max_length=100,
        blank=True
    )
    
    # MÉTODOS ADICIONALES:
    
    def reset_failed_attempts(self):
        """Resetear intentos fallidos de login."""
        self.failed_login_attempts = 0
        self.save(update_fields=['failed_login_attempts'])
    
    def increment_failed_attempts(self):
        """Incrementar intentos fallidos de login."""
        self.failed_login_attempts += 1
        self.save(update_fields=['failed_login_attempts'])
    
    def is_account_locked(self):
        """Verificar si la cuenta está bloqueada por intentos fallidos."""
        from django.conf import settings
        max_attempts = getattr(settings, 'MAX_FAILED_LOGIN_ATTEMPTS', 5)
        return self.failed_login_attempts >= max_attempts
    
    @property
    def full_name(self):
        """Propiedad para compatibilidad."""
        return self.get_full_name()