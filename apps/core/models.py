"""
Modelos base del sistema VENDO - CORREGIDOS
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings


class BaseModel(models.Model):
    """
    Modelo base abstracto con campos comunes para todos los modelos
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        verbose_name=_('ID')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Fecha de actualización')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Activo')
    )
    
    class Meta:
        abstract = True
        ordering = ['-created_at']


class Company(BaseModel):
    """
    ✅ Modelo para empresas (Multi-tenant) - SIN configuración SRI
    """
    # Validador para RUC ecuatoriano
    ruc_validator = RegexValidator(
        regex=r'^\d{13}$',
        message=_('El RUC debe tener 13 dígitos')
    )
    
    # ✅ Información básica de la empresa
    ruc = models.CharField(
        max_length=13,
        unique=True,
        validators=[ruc_validator],
        verbose_name=_('RUC')
    )
    business_name = models.CharField(
        max_length=200,
        verbose_name=_('Razón social')
    )
    trade_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Nombre comercial')
    )
    
    # ✅ Información de contacto
    email = models.EmailField(
        verbose_name=_('Email')
    )
    phone = models.CharField(
        max_length=20,
        verbose_name=_('Teléfono')
    )
    mobile = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Celular')
    )
    website = models.URLField(
        blank=True,
        verbose_name=_('Sitio web')
    )
    
    # ✅ Dirección completa
    address = models.TextField(
        verbose_name=_('Dirección')
    )
    city = models.CharField(
        max_length=100,
        verbose_name=_('Ciudad')
    )
    province = models.CharField(
        max_length=100,
        verbose_name=_('Provincia')
    )
    postal_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('Código postal')
    )
    country = models.CharField(
        max_length=100,
        default='Ecuador',
        verbose_name=_('País')
    )
    
    # ✅ Información fiscal básica
    actividad_economica = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Actividad económica')
    )
    obligado_contabilidad = models.CharField(
        max_length=2,
        choices=[
            ('SI', _('Sí')),
            ('NO', _('No'))
        ],
        default='NO',
        verbose_name=_('Obligado a llevar contabilidad')
    )
    
    # ✅ Representación legal
    representante_legal = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Representante legal')
    )
    cedula_representante = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('Cédula del representante')
    )
    
    # ✅ Logo y configuración visual
    logo = models.ImageField(
        upload_to='company_logos/',
        blank=True,
        verbose_name=_('Logo')
    )
    
    # ✅ Configuración del sistema (multi-tenant)
    schema_name = models.CharField(
        max_length=63,
        unique=True,
        blank=True,
        verbose_name=_('Esquema de base de datos')
    )
    
    # ✅ Estado y configuración
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Empresa por defecto')
    )
    
    class Meta:
        verbose_name = _('Empresa')
        verbose_name_plural = _('Empresas')
        db_table = 'core_company'
        ordering = ['business_name']
    
    def __str__(self):
        return f"{self.business_name} ({self.ruc})"
    
    def get_absolute_url(self):
        return reverse('core:company_detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        # Auto-generar schema_name si no existe
        if not self.schema_name:
            # Generar nombre de esquema basado en RUC
            self.schema_name = f"company_{self.ruc}"
        
        super().save(*args, **kwargs)
    
    def get_full_name(self):
        """Retorna el nombre completo (comercial o razón social)"""
        return self.trade_name or self.business_name
    
    def get_main_branch(self):
        """Retorna la sucursal principal"""
        return self.branches.filter(is_main=True).first()
    
    def has_sri_configuration(self):
        """Verifica si tiene configuración SRI"""
        return hasattr(self, 'sri_configuration') and self.sri_configuration.is_active


class Branch(BaseModel):
    """
    ✅ Modelo para sucursales de la empresa
    """
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name=_('Empresa')
    )
    
    # ✅ Información básica
    code = models.CharField(
        max_length=10,
        verbose_name=_('Código')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Nombre')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Descripción')
    )
    
    # ✅ Información de contacto
    email = models.EmailField(
        blank=True,
        verbose_name=_('Email')
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Teléfono')
    )
    manager = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Encargado')
    )
    
    # ✅ Dirección
    address = models.TextField(
        verbose_name=_('Dirección')
    )
    city = models.CharField(
        max_length=100,
        verbose_name=_('Ciudad')
    )
    province = models.CharField(
        max_length=100,
        verbose_name=_('Provincia')
    )
    
    # ✅ Configuración
    is_main = models.BooleanField(
        default=False,
        verbose_name=_('Sucursal principal')
    )
    
    # ✅ SRI - Códigos de establecimiento
    sri_establishment_code = models.CharField(
        max_length=3,
        default='001',
        validators=[RegexValidator(regex=r'^\d{3}$', message='Debe ser 3 dígitos')],
        verbose_name=_('Código establecimiento SRI')
    )
    
    class Meta:
        verbose_name = _('Sucursal')
        verbose_name_plural = _('Sucursales')
        db_table = 'core_branch'
        unique_together = [
            ('company', 'code'),
            ('company', 'sri_establishment_code')
        ]
        ordering = ['code']
    
    def __str__(self):
        return f"{self.company.get_full_name()} - {self.name}"
    
    def get_absolute_url(self):
        return reverse('core:branch_detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        # Si es la primera sucursal, marcarla como principal
        if not self.company.branches.exists():
            self.is_main = True
        
        # Solo puede haber una sucursal principal por empresa
        if self.is_main:
            Branch.objects.filter(company=self.company, is_main=True).exclude(pk=self.pk).update(is_main=False)
        
        super().save(*args, **kwargs)
    
    def get_points_of_sale(self):
        """Retorna los puntos de emisión de esta sucursal"""
        return self.points_of_sale.filter(is_active=True)


class AuditLog(BaseModel):
    """
    ✅ Modelo para auditoría de cambios en el sistema
    """
    # ✅ Información del usuario
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Usuario')
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Empresa')
    )
    
    # ✅ Información de la acción
    action = models.CharField(
        max_length=20,
        choices=[
            ('CREATE', _('Crear')),
            ('UPDATE', _('Actualizar')),
            ('DELETE', _('Eliminar')),
            ('VIEW', _('Ver')),
            ('LOGIN', _('Iniciar sesión')),
            ('LOGOUT', _('Cerrar sesión')),
            ('EXPORT', _('Exportar')),
            ('IMPORT', _('Importar')),
            ('SEND_SRI', _('Enviar al SRI')),
            ('EMAIL_SENT', _('Email enviado')),
        ],
        verbose_name=_('Acción')
    )
    
    # ✅ Información del objeto afectado
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Tipo de contenido')
    )
    object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('ID del objeto')
    )
    object_repr = models.CharField(
        max_length=200,
        verbose_name=_('Representación del objeto')
    )
    
    # ✅ Detalles de la acción
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Cambios realizados')
    )
    
    # ✅ Información técnica
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('Dirección IP')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    
    # ✅ Información adicional
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
            ('reports', _('Reportes')),
            ('settings', _('Configuraciones')),
        ],
        blank=True,
        verbose_name=_('Módulo')
    )
    
    class Meta:
        verbose_name = _('Log de auditoría')
        verbose_name_plural = _('Logs de auditoría')
        db_table = 'core_audit_log'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['module']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        user_name = self.user.get_full_name() if self.user else 'Sistema'
        return f"{user_name} - {self.get_action_display()} - {self.object_repr}"
    
    @classmethod
    def log_action(cls, user, action, obj=None, changes=None, request=None, company=None):
        """
        Método helper para crear logs de auditoría
        """
        from django.contrib.contenttypes.models import ContentType
        
        # Determinar company
        if not company and user and hasattr(user, 'company'):
            company = user.company
        
        # Información del objeto
        content_type = None
        object_id = None
        object_repr = str(obj) if obj else ''
        
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = str(obj.pk)
        
        # Información de la request
        ip_address = None
        user_agent = ''
        
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Crear log
        return cls.objects.create(
            user=user,
            company=company,
            action=action,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )