"""
Configuración del admin para el módulo Users
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.contrib.admin import SimpleListFilter, TabularInline
from django.forms import ModelForm
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta

from .models import User, Role, Permission, UserCompany, UserProfile, UserSession


# ==========================================
# CLASES AUXILIARES PARA USER ADMIN
# ==========================================

class UserCompanyInline(TabularInline):
    """
    Inline para gestionar roles de usuario por empresa desde el admin de User
    """
    model = UserCompany
    extra = 0
    fields = ['company', 'roles', 'branches', 'is_admin', 'is_active']
    filter_horizontal = ['roles', 'branches']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company').prefetch_related('roles', 'branches')


class UserAdminForm(ModelForm):
    """
    Formulario personalizado para el admin de usuarios
    """
    class Meta:
        model = User
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Verifica si el campo 'approval_status' existe en el modelo
            if hasattr(self.instance, 'approval_status') and 'approval_status' in self.fields:
                self.fields['approval_status'].help_text = (
                    "Estado actual del usuario en el sistema de aprobación. "
                    "Los usuarios deben estar 'Aprobados' para acceder al sistema."
                )
            
        # Opcional: Personalizar otros campos
        if 'password' in self.fields:
            self.fields['password'].help_text = (
                "Las contraseñas no se almacenan en texto plano, "
                "por lo que no hay forma de ver la contraseña del usuario."
            )


class ApprovalStatusFilter(SimpleListFilter):
    """
    Filtro personalizado para estado de aprobación
    """
    title = _('Estado de Aprobación')
    parameter_name = 'approval_status'
    
    def lookups(self, request, model_admin):
        return [
            ('pending', _('⏳ Pendientes')),
            ('approved', _('✅ Aprobados')),
            ('rejected', _('❌ Rechazados')),
            ('pending_old', _('⚠️ Pendientes > 24h')),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(approval_status='pending')
        elif self.value() == 'approved':
            return queryset.filter(approval_status='approved')
        elif self.value() == 'rejected':
            return queryset.filter(approval_status='rejected')
        elif self.value() == 'pending_old':
            cutoff_date = timezone.now() - timedelta(hours=24)
            return queryset.filter(
                approval_status='pending',
                created_at__lt=cutoff_date
            )
        return queryset


# ==========================================
# USER ADMIN PRINCIPAL
# ==========================================

class UserAdmin(BaseUserAdmin):
    """
    Admin personalizado para usuarios - CON GESTIÓN DE APROBACIÓN Y ROLES
    """
    # CONFIGURACIÓN PARA ROLES
    form = UserAdminForm
    inlines = [UserCompanyInline]
    
    # LISTA CON COLUMNA DE ROLES AGREGADA
    list_display = [
        'username', 'email', 'get_full_name', 'document_number',
        'get_user_roles',  # NUEVA COLUMNA PARA ROLES
        'approval_status_display', 'is_active', 'is_staff', 'is_system_admin', 
        'last_login', 'companies_count', 'created_at'
    ]
    list_filter = [
        ApprovalStatusFilter,  # FILTRO PERSONALIZADO
        'is_active', 'is_staff', 'is_system_admin', 'document_type',
        'language', 'created_at', 'last_login', 'approved_at'
    ]
    search_fields = [
        'username', 'email', 'first_name', 'last_name',
        'document_number', 'phone', 'mobile'
    ]
    ordering = ['-created_at']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'last_login', 'date_joined',
        'approved_at', 'approved_by'
    ]
    
    # ACCIONES PERSONALIZADAS
    actions = ['approve_selected_users', 'reject_selected_users', 'send_approval_reminders']
    
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
        (_('Estado de aprobación'), {
            'fields': (
                'approval_status', 'approved_by', 'approved_at', 'rejection_reason'
            ),
            'classes': ('collapse',)
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
        (_('Estado inicial'), {
            'fields': ('approval_status', 'is_active', 'is_staff', 'is_system_admin')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            companies_count=Count('companies', distinct=True)
        ).select_related('approved_by')
    
    def companies_count(self, obj):
        """Número de empresas del usuario"""
        return obj.companies_count
    companies_count.short_description = _('Empresas')
    companies_count.admin_order_field = 'companies_count'
    
    def get_full_name(self, obj):
        """Nombre completo del usuario"""
        return obj.get_full_name()
    get_full_name.short_description = _('Nombre completo')
    
    def approval_status_display(self, obj):
        """Estado de aprobación con icono y color"""
        return obj.get_approval_status_display_with_icon()
    approval_status_display.short_description = _('Estado de Aprobación')
    approval_status_display.allow_tags = True
    
    # NUEVO MÉTODO PARA MOSTRAR ROLES
    def get_user_roles(self, obj):
        """Mostrar roles del usuario en el listado"""
        try:
            user_companies = UserCompany.objects.filter(user=obj).prefetch_related('roles', 'company')
            roles_display = []
            
            for uc in user_companies[:3]:  # Mostrar solo las primeras 3 empresas
                company_roles = uc.roles.all()[:2]  # Mostrar solo los primeros 2 roles por empresa
                if company_roles:
                    roles_names = [role.name for role in company_roles]
                    company_display = f"{uc.company.business_name}: {', '.join(roles_names)}"
                    if uc.roles.count() > 2:
                        company_display += f" (+{uc.roles.count() - 2} más)"
                    roles_display.append(company_display)
            
            result = ' | '.join(roles_display)
            if user_companies.count() > 3:
                result += f" | (+{user_companies.count() - 3} empresas más)"
            
            return result or "Sin roles asignados"
        except Exception as e:
            return f"Error: {str(e)}"
    
    get_user_roles.short_description = _('Roles por Empresa')
    get_user_roles.allow_tags = True
    
    # ACCIONES PERSONALIZADAS
    def approve_selected_users(self, request, queryset):
        """Acción para aprobar usuarios seleccionados"""
        pending_users = queryset.filter(approval_status='pending')
        approved_count = 0
        
        for user in pending_users:
            try:
                user.approval_status = 'approved'
                user.approved_by = request.user
                user.approved_at = timezone.now()
                user.is_active = True
                user.save(update_fields=[
                    'approval_status', 'approved_by', 'approved_at', 'is_active'
                ])
                approved_count += 1
                
            except Exception as e:
                self.message_user(
                    request, 
                    f'Error aprobando usuario {user.email}: {str(e)}',
                    level=messages.ERROR
                )
        
        if approved_count > 0:
            self.message_user(
                request,
                f'{approved_count} usuario(s) aprobado(s) exitosamente.',
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'No se aprobaron usuarios. Verifique que estén en estado pendiente.',
                level=messages.WARNING
            )
    
    approve_selected_users.short_description = _('✅ Aprobar usuarios seleccionados')
    
    def reject_selected_users(self, request, queryset):
        """Acción para rechazar usuarios seleccionados - redirige a página especial"""
        pending_users = queryset.filter(approval_status='pending')
        user_ids = list(pending_users.values_list('id', flat=True))
        
        if not user_ids:
            self.message_user(
                request,
                'No hay usuarios pendientes en la selección.',
                level=messages.WARNING
            )
            return
        
        # Redirigir a página especial para rechazo masivo
        return HttpResponseRedirect(
            f'/admin/users/user/reject-multiple/?ids={",".join(map(str, user_ids))}'
        )
    
    reject_selected_users.short_description = _('❌ Rechazar usuarios seleccionados')
    
    def send_approval_reminders(self, request, queryset):
        """Enviar recordatorios sobre usuarios pendientes"""
        pending_count = queryset.filter(approval_status='pending').count()
        
        if pending_count > 0:
            self.message_user(
                request,
                f'Recordatorio: Hay {pending_count} usuarios pendientes de aprobación.',
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'No hay usuarios pendientes en la selección.',
                level=messages.INFO
            )
    
    send_approval_reminders.short_description = _('📧 Enviar recordatorios de aprobación')
    
    # SOBRESCRIBIR save_model PARA MANEJAR CAMBIOS DE ESTADO
    def save_model(self, request, obj, form, change):
        """Manejar cambios en el estado de aprobación"""
        old_status = None
        
        if change:
            # Obtener el estado anterior
            try:
                old_obj = User.objects.get(pk=obj.pk)
                old_status = old_obj.approval_status
            except User.DoesNotExist:
                pass
        
        # Guardar el objeto
        super().save_model(request, obj, form, change)
        
        # Si cambió el estado de aprobación, manejar notificaciones
        if change and old_status and old_status != obj.approval_status:
            if obj.approval_status == 'approved' and old_status == 'pending':
                # Usuario fue aprobado manualmente
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
                obj.is_active = True
                obj.save(update_fields=['approved_by', 'approved_at', 'is_active'])
                
                self.message_user(
                    request,
                    f'Usuario {obj.get_full_name()} aprobado y notificado.',
                    level=messages.SUCCESS
                )
            
            elif obj.approval_status == 'rejected' and old_status == 'pending':
                # Usuario fue rechazado manualmente
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
                obj.is_active = False
                obj.save(update_fields=['approved_by', 'approved_at', 'is_active'])
                
                self.message_user(
                    request,
                    f'Usuario {obj.get_full_name()} rechazado y notificado.',
                    level=messages.WARNING
                )
    
    # PERSONALIZAR EL CHANGELIST TEMPLATE
    def changelist_view(self, request, extra_context=None):
        """Agregar contexto extra al changelist"""
        extra_context = extra_context or {}
        
        # Estadísticas de usuarios pendientes
        pending_count = User.objects.filter(approval_status='pending').count()
        approved_today = User.objects.filter(
            approval_status='approved',
            approved_at__date=timezone.now().date()
        ).count()
        rejected_today = User.objects.filter(
            approval_status='rejected',
            approved_at__date=timezone.now().date()
        ).count()
        
        extra_context.update({
            'pending_users_count': pending_count,
            'approved_today': approved_today,
            'rejected_today': rejected_today,
        })
        
        return super().changelist_view(request, extra_context)


# ==========================================
# OTRAS CLASES ADMIN (MEJORADAS)
# ==========================================

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin mejorado para roles con gestión de usuarios
    """
    list_display = [
        'name', 'description_truncated', 'permissions_count',
        'users_count', 'color_display', 'is_system_role', 'is_active', 'created_at'
    ]
    list_filter = ['is_system_role', 'is_active', 'created_at', 'permissions__module']
    search_fields = ['name', 'description']
    ordering = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'users_count']
    filter_horizontal = ['permissions']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'description', 'color')
        }),
        ('Configuración', {
            'fields': ('is_system_role', 'is_active')
        }),
        ('Permisos', {
            'fields': ('permissions',),
            'description': 'Selecciona los permisos que tendrán los usuarios con este rol.'
        }),
        ('Estadísticas', {
            'fields': ('users_count',),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['duplicate_role', 'activate_roles', 'deactivate_roles']
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            permissions_count=Count('permissions', distinct=True),
            users_count=Count('user_companies', distinct=True)
        )
    
    def description_truncated(self, obj):
        """Descripción truncada"""
        if obj.description:
            return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
        return '-'
    description_truncated.short_description = 'Descripción'
    
    def permissions_count(self, obj):
        """Número de permisos"""
        return obj.permissions_count
    permissions_count.short_description = 'Permisos'
    permissions_count.admin_order_field = 'permissions_count'
    
    def users_count(self, obj):
        """Número de usuarios con este rol"""
        return obj.users_count
    users_count.short_description = 'Usuarios'
    users_count.admin_order_field = 'users_count'
    
    def color_display(self, obj):
        """Mostrar color"""
        return format_html(
            '<span style="background-color: {}; padding: 2px 8px; border-radius: 3px; color: white; font-weight: bold;">{}</span>',
            obj.color,
            obj.name
        )
    color_display.short_description = 'Vista previa'
    
    # Acciones personalizadas
    def duplicate_role(self, request, queryset):
        """Duplicar roles seleccionados"""
        for role in queryset:
            permissions = role.permissions.all()
            role.pk = None
            role.name = f"{role.name} (Copia)"
            role.save()
            role.permissions.set(permissions)
        
        self.message_user(
            request,
            f'{queryset.count()} rol(es) duplicado(s) exitosamente.',
            level=messages.SUCCESS
        )
    duplicate_role.short_description = "Duplicar roles seleccionados"
    
    def activate_roles(self, request, queryset):
        """Activar roles seleccionados"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} rol(es) activado(s) exitosamente.',
            level=messages.SUCCESS
        )
    activate_roles.short_description = "Activar roles seleccionados"
    
    def deactivate_roles(self, request, queryset):
        """Desactivar roles seleccionados"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} rol(es) desactivado(s) exitosamente.',
            level=messages.WARNING
        )
    deactivate_roles.short_description = "Desactivar roles seleccionados"


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
    Admin mejorado para relación usuario-empresa-roles
    """
    list_display = [
        'user_display', 'company', 'roles_display', 'branches_count',
        'is_admin', 'is_active', 'joined_at'
    ]
    list_filter = [
        'is_admin', 'is_active', 'company', 'roles', 'joined_at'
    ]
    search_fields = [
        'user__username', 'user__email', 'user__first_name',
        'user__last_name', 'company__business_name'
    ]
    ordering = ['-joined_at']
    readonly_fields = ['id', 'joined_at', 'created_at', 'updated_at']
    filter_horizontal = ['roles', 'branches']
    
    fieldsets = (
        ('Relación básica', {
            'fields': ('user', 'company')
        }),
        ('Roles y permisos', {
            'fields': ('roles', 'is_admin'),
            'description': 'Asigna roles específicos para esta empresa. El usuario administrador tiene acceso completo.'
        }),
        ('Sucursales', {
            'fields': ('branches',),
            'description': 'Sucursales a las que el usuario tiene acceso en esta empresa.'
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
        ('Fechas', {
            'fields': ('joined_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'company'
        ).prefetch_related('roles', 'branches')
    
    def user_display(self, obj):
        """Mostrar usuario con nombre completo"""
        return f"{obj.user.get_full_name()} ({obj.user.username})"
    user_display.short_description = 'Usuario'
    user_display.admin_order_field = 'user__first_name'
    
    def roles_display(self, obj):
        """Mostrar roles con colores"""
        roles = obj.roles.all()[:3]
        if not roles:
            return format_html('<em style="color: #999;">Sin roles</em>')
        
        roles_html = []
        for role in roles:
            roles_html.append(
                format_html(
                    '<span style="background-color: {}; color: white; padding: 1px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
                    role.color,
                    role.name
                )
            )
        
        result = ' '.join(roles_html)
        if obj.roles.count() > 3:
            result += format_html(' <small>(+{} más)</small>', obj.roles.count() - 3)
        
        return format_html(result)
    roles_display.short_description = 'Roles'
    roles_display.allow_tags = True
    
    def branches_count(self, obj):
        """Número de sucursales"""
        count = obj.branches.count()
        total = obj.company.branches.count()
        if count == total and total > 0:
            return format_html('<strong>{}/{}</strong> (Todas)', count, total)
        return f"{count}/{total}"
    branches_count.short_description = 'Sucursales'


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


# ==========================================
# FUNCIÓN PARA RECHAZO MASIVO
# ==========================================

@staff_member_required
def reject_multiple_users_view(request):
    """Vista para rechazar múltiples usuarios con razón"""
    if request.method == 'POST':
        user_ids = request.POST.get('user_ids', '').split(',')
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, 'Debe proporcionar una razón para el rechazo.')
            return redirect('admin:users_user_changelist')
        
        rejected_count = 0
        for user_id in user_ids:
            try:
                user = User.objects.get(pk=user_id, approval_status='pending')
                # Actualizar usuario rechazado
                user.approval_status = 'rejected'
                user.approved_by = request.user
                user.approved_at = timezone.now()
                user.rejection_reason = reason
                user.is_active = False
                user.save(update_fields=[
                    'approval_status', 'approved_by', 'approved_at', 
                    'rejection_reason', 'is_active'
                ])
                rejected_count += 1
                
            except User.DoesNotExist:
                continue
            except Exception as e:
                messages.error(request, f'Error rechazando usuario: {str(e)}')
        
        if rejected_count > 0:
            messages.success(
                request, 
                f'{rejected_count} usuario(s) rechazado(s) exitosamente.'
            )
        
        return redirect('admin:users_user_changelist')
    
    # GET request - mostrar formulario
    user_ids = request.GET.get('ids', '').split(',')
    users = User.objects.filter(pk__in=user_ids, approval_status='pending')
    
    context = {
        'users': users,
        'user_ids': ','.join(user_ids),
        'title': 'Rechazar Usuarios Seleccionados'
    }
    
    return render(request, 'admin/users/reject_multiple.html', context)


# ==========================================
# REGISTRAR USER ADMIN
# ==========================================

# IMPORTANTE: Registrar User al final para evitar conflictos
admin.site.register(User, UserAdmin)

# Personalización del admin site
admin.site.site_header = _('VENDO - Administración')
admin.site.site_title = _('VENDO Admin')
admin.site.index_title = _('Panel de administración')