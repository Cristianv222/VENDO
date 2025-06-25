"""
Configuración del admin para el módulo Users
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count

from .models import User, Role, Permission, UserCompany, UserProfile, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin personalizado para usuarios
    """
    list_display = [
        'username', 'email', 'get_full_name', 'document_number',
        'is_active', 'is_staff', 'is_system_admin', 'last_login',
        'companies_count'
    ]
    list_filter = [
        'is_active', 'is_staff', 'is_system_admin', 'document_type',
        'language', 'created_at', 'last_login'
    ]
    search_fields = [
        'username', 'email', 'first_name', 'last_name',
        'document_number', 'phone', 'mobile'
    ]
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login', 'date_joined']
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('username', 'email', 'password')
        }),
        (_('Información personal'), {
            'fields': (
                'first_name', 'last_name', 'document_type', 'document_number',
                'phone', 'mobile', 'birth_date', 'address', 'avatar'
            )
        }),
        (_('Configuración'), {
            'fields': ('language', 'timezone')
        }),
        (_('Permisos'), {
            'fields': (
                'is_active', 'is_staff', 'is_superuser', 'is_system_admin',
                'force_password_change'
            )
        }),
        (_('Fechas importantes'), {
            'fields': ('last_login', 'date_joined', 'password_changed_at', 'last_activity')
        }),
        (_('Metadatos'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (_('Información básica'), {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'password1', 'password2',
                'first_name', 'last_name', 'document_type', 'document_number'
            )
        }),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_system_admin')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            companies_count=Count('companies', distinct=True)
        )
    
    def companies_count(self, obj):
        """Número de empresas del usuario"""
        return obj.companies_count
    companies_count.short_description = _('Empresas')
    companies_count.admin_order_field = 'companies_count'
    
    def get_full_name(self, obj):
        """Nombre completo del usuario"""
        return obj.get_full_name()
    get_full_name.short_description = _('Nombre completo')


class UserCompanyInline(admin.TabularInline):
    """
    Inline para relación usuario-empresa
    """
    model = UserCompany
    extra = 0
    readonly_fields = ['created_at']
    filter_horizontal = ['roles', 'branches']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin para roles
    """
    list_display = [
        'name', 'description_truncated', 'permissions_count',
        'color_display', 'is_system_role', 'is_active', 'created_at'
    ]
    list_filter = ['is_system_role', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['permissions']
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('name', 'description', 'color')
        }),
        (_('Configuración'), {
            'fields': ('is_system_role', 'is_active')
        }),
        (_('Permisos'), {
            'fields': ('permissions',)
        }),
        (_('Metadatos'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            permissions_count=Count('permissions', distinct=True)
        )
    
    def description_truncated(self, obj):
        """Descripción truncada"""
        if obj.description:
            return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
        return '-'
    description_truncated.short_description = _('Descripción')
    
    def permissions_count(self, obj):
        """Número de permisos"""
        return obj.permissions_count
    permissions_count.short_description = _('Permisos')
    permissions_count.admin_order_field = 'permissions_count'
    
    def color_display(self, obj):
        """Mostrar color"""
        return format_html(
            '<span style="background-color: {}; padding: 2px 8px; border-radius: 3px; color: white;">{}</span>',
            obj.color,
            obj.color
        )
    color_display.short_description = _('Color')


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    Admin para permisos
    """
    list_display = [
        'name', 'codename', 'module', 'description_truncated',
        'roles_count', 'is_active', 'created_at'
    ]
    list_filter = ['module', 'is_active', 'created_at']
    search_fields = ['name', 'codename', 'description']
    ordering = ['module', 'name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('name', 'codename', 'description')
        }),
        (_('Configuración'), {
            'fields': ('module', 'is_active')
        }),
        (_('Metadatos'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            roles_count=Count('roles', distinct=True)
        )
    
    def description_truncated(self, obj):
        """Descripción truncada"""
        if obj.description:
            return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
        return '-'
    description_truncated.short_description = _('Descripción')
    
    def roles_count(self, obj):
        """Número de roles que tienen este permiso"""
        return obj.roles_count
    roles_count.short_description = _('Roles')
    roles_count.admin_order_field = 'roles_count'


@admin.register(UserCompany)
class UserCompanyAdmin(admin.ModelAdmin):
    """
    Admin para relación usuario-empresa
    """
    list_display = [
        'user', 'company', 'roles_display', 'branches_count',
        'is_admin', 'is_active', 'created_at'
    ]
    list_filter = ['is_admin', 'is_active', 'company', 'created_at']
    search_fields = [
        'user__username', 'user__email', 'user__first_name',
        'user__last_name', 'company__business_name'
    ]
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['roles', 'branches']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'company'
        ).prefetch_related('roles', 'branches')
    
    def roles_display(self, obj):
        """Mostrar roles"""
        roles = obj.roles.all()[:3]
        result = ', '.join([role.name for role in roles])
        if obj.roles.count() > 3:
            result += f' (+{obj.roles.count() - 3} más)'
        return result or '-'
    roles_display.short_description = _('Roles')
    
    def branches_count(self, obj):
        """Número de sucursales"""
        return obj.branches.count()
    branches_count.short_description = _('Sucursales')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Admin para perfiles de usuario
    """
    list_display = [
        'user', 'position', 'department', 'employee_code',
        'theme', 'email_notifications', 'is_active', 'created_at'
    ]
    list_filter = [
        'theme', 'email_notifications', 'sms_notifications',
        'system_notifications', 'is_active', 'created_at'
    ]
    search_fields = [
        'user__username', 'user__email', 'user__first_name',
        'user__last_name', 'position', 'department', 'employee_code'
    ]
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Usuario'), {
            'fields': ('user',)
        }),
        (_('Información profesional'), {
            'fields': ('position', 'department', 'employee_code')
        }),
        (_('Configuración de interfaz'), {
            'fields': ('theme', 'sidebar_collapsed')
        }),
        (_('Notificaciones'), {
            'fields': (
                'email_notifications', 'sms_notifications',
                'system_notifications'
            )
        }),
        (_('Información adicional'), {
            'fields': ('bio', 'social_media')
        }),
        (_('Estado'), {
            'fields': ('is_active',)
        }),
        (_('Metadatos'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """
    Admin para sesiones de usuario
    """
    list_display = [
        'user', 'company', 'branch', 'ip_address',
        'login_at', 'last_activity', 'logout_at', 'is_expired'
    ]
    list_filter = [
        'is_expired', 'company', 'branch', 'login_at', 'logout_at'
    ]
    search_fields = [
        'user__username', 'user__email', 'ip_address',
        'session_key', 'user_agent'
    ]
    ordering = ['-login_at']
    readonly_fields = [
        'id', 'session_key', 'login_at', 'last_activity',
        'logout_at', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (_('Usuario y empresa'), {
            'fields': ('user', 'company', 'branch')
        }),
        (_('Información de sesión'), {
            'fields': ('session_key', 'ip_address', 'user_agent')
        }),
        (_('Fechas'), {
            'fields': ('login_at', 'last_activity', 'logout_at')
        }),
        (_('Estado'), {
            'fields': ('is_expired', 'is_active')
        }),
        (_('Metadatos'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """No permitir crear sesiones desde admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Solo permitir cambiar el estado is_expired"""
        return True
    
    def get_readonly_fields(self, request, obj=None):
        """Campos de solo lectura"""
        readonly = list(self.readonly_fields)
        if obj:  # Si está editando
            readonly.extend(['user', 'company', 'branch', 'ip_address', 'user_agent'])
        return readonly


# Personalización del admin site
admin.site.site_header = _('VENDO - Administración')
admin.site.site_title = _('VENDO Admin')
admin.site.index_title = _('Panel de administración')