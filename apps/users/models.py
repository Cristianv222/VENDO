"""
Modelos del módulo Users
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, Permission as DjangoPermission
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings

from apps.core.models import BaseModel, Company, Branch


class User(AbstractUser):
    """
    Modelo de usuario personalizado
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        verbose_name=_('ID')
    )
    
    # ✅ CORREGIR EMAIL PARA USERNAME_FIELD
    email = models.EmailField(
        _('email address'),
        unique=True,  # ✅ AGREGADO: unique=True requerido para USERNAME_FIELD
        error_messages={
            'unique': _("Ya existe un usuario con este email."),
        },
    )
    
    # Información personal adicional
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('cedula', _('Cédula')),
            ('pasaporte', _('Pasaporte')),
            ('ruc', _('RUC')),
        ],
        default='cedula',
        verbose_name=_('Tipo de documento')
    )
    document_number = models.CharField(
    max_length=20,
    unique=True,
    blank=True,        # ← Permite campo vacío en formularios
    null=True,         # ← Permite NULL en base de datos
    verbose_name=_('Número de documento'),
    help_text=_('Número de cédula o documento de identidad (opcional para registro social)'),
    validators=[
        RegexValidator(
            regex=r'^[\d\-]+$',
            message=_('El número de documento solo puede contener números y guiones.'),
            ),
        ]   
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Teléfono'),
        validators=[
            RegexValidator(
                regex=r'^[\d\+\-\(\)\s]+$',
                message=_('Formato de teléfono inválido.'),
            ),
        ]
    )
    mobile = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Celular'),
        validators=[
            RegexValidator(
                regex=r'^[\d\+\-\(\)\s]+$',
                message=_('Formato de celular inválido.'),
            ),
        ]
    )
    
    # Relaciones con empresa
    companies = models.ManyToManyField(
        Company,
        through='UserCompany',
        related_name='users',
        verbose_name=_('Empresas')
    )
    
    # Campos adicionales
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        verbose_name=_('Avatar')
    )
    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Fecha de nacimiento')
    )
    address = models.TextField(
        blank=True,
        verbose_name=_('Dirección')
    )
    
    # Configuración de usuario
    language = models.CharField(
        max_length=10,
        choices=[
            ('es', _('Español')),
            ('en', _('Inglés')),
        ],
        default='es',
        verbose_name=_('Idioma')
    )
    timezone = models.CharField(
        max_length=50,
        default='America/Guayaquil',
        verbose_name=_('Zona horaria')
    )
    
    # Control de acceso
    is_system_admin = models.BooleanField(
        default=False,
        verbose_name=_('Administrador del sistema')
    )
    force_password_change = models.BooleanField(
        default=False,
        verbose_name=_('Forzar cambio de contraseña')
    )
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Contraseña cambiada el')
    )
    last_activity = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Última actividad')
    )
    
    # Fechas de control
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Fecha de actualización')
    )
    
    # ✅ CORREGIR CONFLICTOS DE RELATED_NAME
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='vendo_user_set',  # ✅ AGREGADO: related_name único
        related_query_name='vendo_user',
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='vendo_user_set',  # ✅ AGREGADO: related_name único
        related_query_name='vendo_user',
    )
    
    # ✅ CONFIGURACIÓN PARA LOGIN CON EMAIL
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name', 'document_number']
    
    class Meta:
        verbose_name = _('Usuario')
        verbose_name_plural = _('Usuarios')
        db_table = 'users_user'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['document_number']),
            models.Index(fields=['is_active', 'is_staff']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        super().clean()
        
        # Validar email
        if self.email:
            self.email = self.email.lower().strip()
        
        # Validar documento
        if self.document_type == 'cedula' and self.document_number:
            if len(self.document_number) != 10:
                raise ValidationError({
                    'document_number': _('La cédula debe tener 10 dígitos.')
                })
        elif self.document_type == 'ruc' and self.document_number:
            if len(self.document_number) != 13:
                raise ValidationError({
                    'document_number': _('El RUC debe tener 13 dígitos.')
                })
    
    def save(self, *args, **kwargs):
        """Sobrescribir save para lógica adicional"""
        self.full_clean()  # Ejecutar validaciones
        
        # Normalizar email
        if self.email:
            self.email = self.email.lower().strip()
        
        super().save(*args, **kwargs)
        
        # Crear perfil automáticamente
        if not hasattr(self, 'profile'):
            UserProfile.objects.create(user=self)
    
    def get_absolute_url(self):
        return reverse('users:user_detail', kwargs={'pk': self.pk})
    
    def get_full_name(self):
        """Retorna el nombre completo del usuario"""
        return f"{self.first_name} {self.last_name}".strip() or self.username
    
    def get_companies(self):
        """Retorna las empresas a las que pertenece el usuario"""
        return self.companies.filter(is_active=True)
    
    def has_company_access(self, company):
        """Verifica si el usuario tiene acceso a una empresa"""
        if self.is_system_admin:
            return True
        return self.companies.filter(id=company.id, is_active=True).exists()
    
    def get_roles_for_company(self, company):
        """Obtiene los roles del usuario para una empresa específica"""
        return Role.objects.filter(
            usercompany__user=self,
            usercompany__company=company
        )
    
    def has_permission_in_company(self, permission_codename, company):
        """Verifica si el usuario tiene un permiso específico en una empresa"""
        if self.is_system_admin:
            return True
        
        # Verificar permisos a través de roles
        roles = self.get_roles_for_company(company)
        return Permission.objects.filter(
            roles__in=roles,
            codename=permission_codename
        ).exists()
    
    def get_user_company(self, company):
        """Obtiene la relación UserCompany para una empresa específica"""
        try:
            return UserCompany.objects.get(user=self, company=company)
        except UserCompany.DoesNotExist:
            return None
    
    def is_company_admin(self, company):
        """Verifica si el usuario es administrador de una empresa"""
        if self.is_system_admin:
            return True
        
        user_company = self.get_user_company(company)
        return user_company and user_company.is_admin
    
    def get_accessible_branches(self, company):
        """Obtiene las sucursales a las que el usuario tiene acceso en una empresa"""
        user_company = self.get_user_company(company)
        if not user_company:
            return Branch.objects.none()
        
        if user_company.is_admin:
            return company.branches.filter(is_active=True)
        
        return user_company.branches.filter(is_active=True)


class Role(BaseModel):
    """
    Modelo para roles de usuario
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Nombre')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Descripción')
    )
    
    # Permisos del rol
    permissions = models.ManyToManyField(
        'Permission',
        blank=True,
        related_name='roles',
        verbose_name=_('Permisos')
    )
    
    # Configuración
    is_system_role = models.BooleanField(
        default=False,
        verbose_name=_('Rol del sistema')
    )
    color = models.CharField(
        max_length=7,
        default='#007bff',
        verbose_name=_('Color'),
        validators=[
            RegexValidator(
                regex=r'^#[0-9A-Fa-f]{6}$',
                message=_('Color debe ser un código hexadecimal válido (ej: #007bff).'),
            ),
        ]
    )
    
    class Meta:
        verbose_name = _('Rol')
        verbose_name_plural = _('Roles')
        db_table = 'users_role'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('users:role_detail', kwargs={'pk': self.pk})
    
    @property
    def users_count(self):
        """Retorna el número de usuarios con este rol"""
        return self.user_companies.count()


class Permission(BaseModel):
    """
    Modelo para permisos específicos del sistema
    """
    name = models.CharField(
        max_length=100,
        verbose_name=_('Nombre')
    )
    codename = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Código'),
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9_]+$',
                message=_('El código solo puede contener letras minúsculas, números y guiones bajos.'),
            ),
        ]
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Descripción')
    )
    
    # Categorización
    module = models.CharField(
        max_length=50,
        choices=[
            ('core', _('Core')),
            ('users', _('Usuarios')),
            ('pos', _('Punto de Venta')),
            ('inventory', _('Inventario')),
            ('invoicing', _('Facturación')),
            ('purchases', _('Compras')),
            ('accounting', _('Contabilidad')),
            ('quotations', _('Cotizaciones')),
            ('reports', _('Reportes')),
            ('settings', _('Configuraciones')),
        ],
        verbose_name=_('Módulo')
    )
    
    class Meta:
        verbose_name = _('Permiso')
        verbose_name_plural = _('Permisos')
        db_table = 'users_permission'
        unique_together = [('codename', 'module')]
        indexes = [
            models.Index(fields=['module']),
            models.Index(fields=['codename']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.codename})"


class UserCompany(BaseModel):
    """
    Modelo intermedio para la relación usuario-empresa con roles
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_('Usuario')
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_('Empresa')
    )
    
    # Roles en la empresa
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='user_companies',
        verbose_name=_('Roles')
    )
    
    # Sucursales a las que tiene acceso
    branches = models.ManyToManyField(
        Branch,
        blank=True,
        related_name='user_companies',
        verbose_name=_('Sucursales')
    )
    
    # Configuración
    is_admin = models.BooleanField(
        default=False,
        verbose_name=_('Administrador de empresa')
    )
    
    # Fechas específicas de la relación
    joined_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de incorporación')
    )
    
    class Meta:
        verbose_name = _('Usuario-Empresa')
        verbose_name_plural = _('Usuarios-Empresas')
        db_table = 'users_user_company'
        unique_together = [('user', 'company')]
        indexes = [
            models.Index(fields=['user', 'company']),
            models.Index(fields=['is_admin']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.company.business_name}"
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        super().clean()
        
        # Validar que las sucursales pertenezcan a la empresa
        if self.pk and self.branches.exists():
            invalid_branches = self.branches.exclude(company=self.company)
            if invalid_branches.exists():
                raise ValidationError({
                    'branches': _('Todas las sucursales deben pertenecer a la empresa seleccionada.')
                })


class UserProfile(BaseModel):
    """
    Perfil extendido del usuario
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('Usuario')
    )
    
    # Información profesional
    position = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Cargo')
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Departamento')
    )
    employee_code = models.CharField(
        max_length=20,
        blank=True,
        unique=True,
        null=True,
        verbose_name=_('Código de empleado')
    )
    
    # Configuraciones de la interfaz
    theme = models.CharField(
        max_length=20,
        choices=[
            ('light', _('Claro')),
            ('dark', _('Oscuro')),
            ('auto', _('Automático')),
        ],
        default='light',
        verbose_name=_('Tema')
    )
    sidebar_collapsed = models.BooleanField(
        default=False,
        verbose_name=_('Sidebar colapsado')
    )
    
    # Notificaciones
    email_notifications = models.BooleanField(
        default=True,
        verbose_name=_('Notificaciones por email')
    )
    sms_notifications = models.BooleanField(
        default=False,
        verbose_name=_('Notificaciones por SMS')
    )
    system_notifications = models.BooleanField(
        default=True,
        verbose_name=_('Notificaciones del sistema')
    )
    
    # Información adicional
    bio = models.TextField(
        blank=True,
        verbose_name=_('Biografía')
    )
    social_media = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Redes sociales')
    )
    
    class Meta:
        verbose_name = _('Perfil de usuario')
        verbose_name_plural = _('Perfiles de usuario')
        db_table = 'users_user_profile'
    
    def __str__(self):
        return f"Perfil de {self.user.get_full_name()}"


class UserSession(BaseModel):
    """
    Modelo para gestionar sesiones de usuario
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name=_('Usuario')
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Empresa')
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Sucursal')
    )
    
    # Información de la sesión
    session_key = models.CharField(
        max_length=40,
        unique=True,
        verbose_name=_('Clave de sesión')
    )
    ip_address = models.GenericIPAddressField(
        verbose_name=_('Dirección IP')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    
    # Control de tiempo
    login_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Inicio de sesión')
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Última actividad')
    )
    logout_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Cierre de sesión')
    )
    
    # Estado
    is_expired = models.BooleanField(
        default=False,
        verbose_name=_('Expirada')
    )
    
    class Meta:
        verbose_name = _('Sesión de usuario')
        verbose_name_plural = _('Sesiones de usuario')
        db_table = 'users_user_session'
        indexes = [
            models.Index(fields=['user', 'login_at']),
            models.Index(fields=['session_key']),
            models.Index(fields=['is_expired']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.login_at}"
    
    @property
    def duration(self):
        """Retorna la duración de la sesión"""
        end_time = self.logout_at or self.last_activity
        return end_time - self.login_at if end_time else None