"""
Modelos base del sistema VENDO
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
    Modelo para empresas (Multi-tenant)
    """
    # Validador para RUC ecuatoriano
    ruc_validator = RegexValidator(
        regex=r'^\d{13}$',
        message=_('El RUC debe tener 13 dígitos')
    )
    
    # Información básica
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
    
    # Información de contacto
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
    
    # Dirección
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
    
    # Configuración SRI
    sri_environment = models.CharField(
        max_length=20,
        choices=[
            ('test', _('Pruebas')),
            ('production', _('Producción'))
        ],
        default='test',
        verbose_name=_('Ambiente SRI')
    )
    sri_certificate = models.FileField(
        upload_to='certificates/',
        blank=True,
        verbose_name=_('Certificado digital')
    )
    sri_password = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Contraseña certificado')
    )
    
    # Logo y configuración visual
    logo = models.ImageField(
        upload_to='logos/',
        blank=True,
        verbose_name=_('Logo')
    )
    
    # Configuración del sistema
    schema_name = models.CharField(
        max_length=63,
        unique=True,
        verbose_name=_('Esquema de base de datos')
    )
    
    class Meta:
        verbose_name = _('Empresa')
        verbose_name_plural = _('Empresas')
        db_table = 'core_company'
    
    def __str__(self):
        return f"{self.business_name} ({self.ruc})"
    
    def get_absolute_url(self):
        return reverse('core:company_detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        # Auto-generar schema_name si no existe
        if not self.schema_name:
            self.schema_name = f"company_{self.ruc}"
        super().save(*args, **kwargs)


class Branch(BaseModel):
    """
    Modelo para sucursales de la empresa
    """
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name=_('Empresa')
    )
    
    # Información básica
    code = models.CharField(
        max_length=10,
        verbose_name=_('Código')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Nombre')
    )
    
    # Información de contacto
    email = models.EmailField(
        blank=True,
        verbose_name=_('Email')
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Teléfono')
    )
    
    # Dirección
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
    
    # Configuración
    is_main = models.BooleanField(
        default=False,
        verbose_name=_('Sucursal principal')
    )
    
    # SRI - Puntos de emisión
    sri_establishment_code = models.CharField(
        max_length=3,
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
    
    def __str__(self):
        return f"{self.company.business_name} - {self.name}"
    
    def get_absolute_url(self):
        return reverse('core:branch_detail', kwargs={'pk': self.pk})


class AuditLog(BaseModel):
    """
    Modelo para auditoría de cambios en el sistema
    """
    # Información del usuario - CORREGIDO: Usar settings.AUTH_USER_MODEL
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # ✅ Cambio principal aquí
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
    
    # Información de la acción
    action = models.CharField(
        max_length=20,
        choices=[
            ('CREATE', _('Crear')),
            ('UPDATE', _('Actualizar')),
            ('DELETE', _('Eliminar')),
            ('VIEW', _('Ver')),
            ('LOGIN', _('Iniciar sesión')),
            ('LOGOUT', _('Cerrar sesión')),
        ],
        verbose_name=_('Acción')
    )
    
    # Información del objeto afectado
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
    
    # Detalles de la acción
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Cambios')
    )
    
    # Información técnica
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('Dirección IP')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    
    class Meta:
        verbose_name = _('Log de auditoría')
        verbose_name_plural = _('Logs de auditoría')
        db_table = 'core_audit_log'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['company', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.object_repr}"