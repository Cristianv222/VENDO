"""
Configuración del panel de administración para el módulo de usuarios.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import User, Role, Permission, UserProfile, UserRole, UserPermission, UserSession


class UserProfileInline(admin.StackedInline):
    """Inline para el perfil de usuario."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = _('Perfil')
    extra = 0
    fieldsets = (
        (_('Información Personal'), {
            'fields': ('avatar', 'birth_date', 'bio')
        }),
        (_('Preferencias'), {
            'fields': ('theme', 'language', 'timezone')
        }),
        (_('Notificaciones'), {
            'fields': ('email_notifications', 'sms_notifications', 'push_notifications')
        }),
        (_('Configuraciones POS'), {
            'fields': ('default_pos_session_timeout', 'auto_print_receipts')
        }),
    )


class UserRoleInline(admin.TabularInline):
    """Inline para roles de usuario."""
    model = UserRole
    fk_name = 'user'  # Especificar cuál FK usar
    extra = 0
    readonly_fields = ('assigned_at', 'assigned_by')
    fields = ('role', 'is_active', 'assigned_at', 'assigned_by')


class UserPermissionInline(admin.TabularInline):
    """Inline para permisos de usuario."""
    model = UserPermission
    fk_name = 'user'  # Especificar cuál FK usar
    extra = 0
    readonly_fields = ('granted_at', 'granted_by')
    fields = ('permission', 'is_active', 'granted_at', 'granted_by')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Administración personalizada para el modelo User."""
    
    inlines = [UserProfileInline, UserRoleInline, UserPermissionInline]
    
    list_display = (
        'username', 'email', 'full_name', 'user_type', 
        'document_number', 'is_active', 'last_login', 'created_at'
    )
    list_filter = (
        'user_type', 'is_active', 'is_staff', 'document_type',
        'department', 'created_at', 'last_login'
    )
    search_fields = (
        'username', 'email', 'first_name', 'last_name', 
        'document_number', 'employee_code'
    )
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        (_('Información Personal'), {
            'fields': (
                'first_name', 'last_name', 'email', 
                'document_type', 'document_number', 
                'phone', 'address'
            )
        }),
        (_('Información Laboral'), {
            'fields': (
                'user_type', 'employee_code', 'hire_date',
                'department', 'position'
            )
        }),
        (_('Permisos'), {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        (_('Seguridad'), {
            'fields': (
                'failed_login_attempts', 'last_password_change',
                'force_password_change'
            )
        }),
        (_('Fechas Importantes'), {
            'fields': ('last_login', 'date_joined', 'last_activity')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'password1', 'password2',
                'first_name', 'last_name', 'document_type', 
                'document_number', 'user_type'
            ),
        }),
    )
    
    readonly_fields = ('last_login', 'date_joined', 'last_activity', 'created_at', 'updated_at')
    
    actions = ['activate_users', 'deactivate_users', 'reset_password', 'reset_failed_attempts']

    def activate_users(self, request, queryset):
        """Activar usuarios seleccionados."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} usuarios han sido activados exitosamente.'
        )
    activate_users.short_description = _('Activar usuarios seleccionados')

    def deactivate_users(self, request, queryset):
        """Desactivar usuarios seleccionados."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} usuarios han sido desactivados exitosamente.'
        )
    deactivate_users.short_description = _('Desactivar usuarios seleccionados')

    def reset_failed_attempts(self, request, queryset):
        """Resetear intentos fallidos de login."""
        updated = queryset.update(failed_login_attempts=0)
        self.message_user(
            request,
            f'Se han reseteado los intentos fallidos de {updated} usuarios.'
        )
    reset_failed_attempts.short_description = _('Resetear intentos fallidos')

    def full_name(self, obj):
        """Mostrar nombre completo."""
        return obj.full_name
    full_name.short_description = _('Nombre Completo')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Administración para el modelo Role."""
    
    list_display = ('name', 'code', 'user_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'is_active')
        }),
        (_('Información del Sistema'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['activate_roles', 'deactivate_roles']

    def activate_roles(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} roles han sido activados.')
    activate_roles.short_description = _('Activar roles seleccionados')

    def deactivate_roles(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} roles han sido desactivados.')
    deactivate_roles.short_description = _('Desactivar roles seleccionados')


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Administración para el modelo Permission."""
    
    list_display = ('name', 'code', 'module', 'is_active', 'created_at')
    list_filter = ('module', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'description', 'module')
    ordering = ('module', 'name')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'module', 'description', 'is_active')
        }),
        (_('Información del Sistema'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Administración para el modelo UserProfile."""
    
    list_display = ('user', 'theme', 'language', 'email_notifications', 'age')
    list_filter = ('theme', 'language', 'email_notifications', 'sms_notifications')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    
    fieldsets = (
        (_('Usuario'), {
            'fields': ('user',)
        }),
        (_('Información Personal'), {
            'fields': ('avatar', 'birth_date', 'bio')
        }),
        (_('Preferencias'), {
            'fields': ('theme', 'language', 'timezone')
        }),
        (_('Notificaciones'), {
            'fields': ('email_notifications', 'sms_notifications', 'push_notifications')
        }),
        (_('Configuraciones POS'), {
            'fields': ('default_pos_session_timeout', 'auto_print_receipts')
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')

    def age(self, obj):
        """Mostrar edad del usuario."""
        return obj.age if obj.age else '-'
    age.short_description = _('Edad')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """Administración para la relación Usuario-Rol."""
    
    list_display = ('user', 'role', 'is_active', 'assigned_by', 'assigned_at')
    list_filter = ('role', 'is_active', 'assigned_at')
    search_fields = ('user__username', 'role__name')
    ordering = ('-assigned_at',)
    
    def save_model(self, request, obj, form, change):
        if not change:  # Solo en creación
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    """Administración para la relación Usuario-Permiso."""
    
    list_display = ('user', 'permission', 'is_active', 'granted_by', 'granted_at')
    list_filter = ('permission__module', 'is_active', 'granted_at')
    search_fields = ('user__username', 'permission__name')
    ordering = ('-granted_at',)
    
    def save_model(self, request, obj, form, change):
        if not change:  # Solo en creación
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Administración para las sesiones de usuario."""
    
    list_display = (
        'user', 'ip_address', 'location', 'is_active', 
        'created_at', 'last_activity', 'is_expired_display'
    )
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__username', 'ip_address', 'location')
    ordering = ('-last_activity',)
    readonly_fields = ('session_key', 'created_at', 'last_activity')
    
    actions = ['terminate_sessions']

    def is_expired_display(self, obj):
        """Mostrar si la sesión está expirada."""
        if obj.is_expired:
            return format_html('<span style="color: red;">Expirada</span>')
        return format_html('<span style="color: green;">Activa</span>')
    is_expired_display.short_description = _('Estado')

    def terminate_sessions(self, request, queryset):
        """Terminar sesiones seleccionadas."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} sesiones han sido terminadas.'
        )
    terminate_sessions.short_description = _('Terminar sesiones seleccionadas')


# Configuración del sitio de administración
admin.site.site_header = _('VENDO - Panel de Administración')
admin.site.site_title = _('VENDO Admin')
admin.site.index_title = _('Bienvenido al Panel de Administración de VENDO')