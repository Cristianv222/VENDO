"""
Configuración del admin de Django para el módulo Core
CORREGIDO: Eliminadas referencias a campos inexistentes
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe

from .models import Company, Branch, AuditLog


class ActiveFilter(SimpleListFilter):
    """
    Filtro personalizado para elementos activos/inactivos
    """
    title = _('Estado')
    parameter_name = 'active'
    
    def lookups(self, request, model_admin):
        return (
            ('active', _('Activos')),
            ('inactive', _('Inactivos')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset


class BranchInline(admin.TabularInline):
    """
    Inline para sucursales en la empresa
    """
    model = Branch
    extra = 1
    fields = ('code', 'name', 'city', 'sri_establishment_code', 'is_main', 'is_active')
    
    def get_readonly_fields(self, request, obj=None):
        # Si está editando, no permitir cambiar el código
        if obj:
            return ('code',)
        return ()


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """
    Administración de empresas
    """
    # ✅ CORREGIDO: Eliminada referencia a 'sri_environment' inexistente
    list_display = (
        'business_name',
        'ruc', 
        'trade_name',
        'email',
        'phone',
        'branch_count',
        'is_active_display',
        'created_at'
    )
    
    # ✅ CORREGIDO: Eliminada referencia a 'sri_environment' inexistente
    list_filter = (
        ActiveFilter,
        'city',
        'province',
        'created_at'
    )
    
    search_fields = (
        'business_name',
        'trade_name', 
        'ruc',
        'email'
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at'
    )
    
    # ✅ CORREGIDO: Eliminados campos SRI inexistentes del fieldset
    fieldsets = (
        (_('Información Básica'), {
            'fields': (
                'ruc',
                'business_name',
                'trade_name',
                'email'
            )
        }),
        (_('Contacto'), {
            'fields': (
                'phone',
                'address',
                'city',
                'province'
            )
        }),
        (_('Configuración Contable'), {
            'fields': (
                'obligado_contabilidad',
            ),
            'classes': ('collapse',)
        }),
        (_('Sistema'), {
            'fields': (
                'is_active',
            ),
            'classes': ('collapse',)
        }),
        (_('Auditoría'), {
            'fields': (
                'id',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    inlines = [BranchInline]
    
    def is_active_display(self, obj):
        """
        Muestra el estado activo con colores
        """
        if obj.is_active:
            return format_html(
                '<span style="color: green;">●</span> {}',
                _('Activo')
            )
        else:
            return format_html(
                '<span style="color: red;">●</span> {}',
                _('Inactivo')
            )
    is_active_display.short_description = _('Estado')
    
    def branch_count(self, obj):
        """
        Cuenta las sucursales de la empresa
        """
        count = obj.branches.count()
        if count > 0:
            url = reverse('admin:core_branch_changelist')
            return format_html(
                '<a href="{}?company__id__exact={}">{} sucursales</a>',
                url, obj.id, count
            )
        return '0 sucursales'
    branch_count.short_description = _('Sucursales')
    
    def get_readonly_fields(self, request, obj=None):
        """
        Campos de solo lectura según el contexto
        """
        readonly = list(self.readonly_fields)
        
        # Si está editando, no permitir cambiar RUC
        if obj:
            readonly.append('ruc')
        
        return readonly
    
    def save_model(self, request, obj, form, change):
        """
        Acciones adicionales al guardar
        """
        super().save_model(request, obj, form, change)
        
        # Si es nueva empresa, crear configuraciones por defecto
        if not change:
            # Crear configuraciones por defecto cuando esté disponible
            # try:
            #     from apps.settings.models import SRIConfiguration
            #     SRIConfiguration.objects.get_or_create(company=obj)
            # except ImportError:
            #     pass
            pass


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    """
    Administración de sucursales
    """
    list_display = (
        'name',
        'company_link',
        'code',
        'city',
        'sri_establishment_code',
        'is_main_display',
        'is_active_display',
        'created_at'
    )
    
    list_filter = (
        ActiveFilter,
        'is_main',
        'company',
        'city',
        'province',
        'created_at'
    )
    
    search_fields = (
        'name',
        'code',
        'company__business_name',
        'city',
        'address'
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at'
    )
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': (
                'company',
                'code',
                'name',
                'is_main'
            )
        }),
        (_('Contacto'), {
            'fields': (
                'email',
                'phone',
                'address',
                'city',
                'province'
            )
        }),
        (_('Configuración SRI'), {
            'fields': (
                'sri_establishment_code',
            )
        }),
        (_('Sistema'), {
            'fields': (
                'is_active',
            ),
            'classes': ('collapse',)
        }),
        (_('Auditoría'), {
            'fields': (
                'id',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def company_link(self, obj):
        """
        Link a la empresa
        """
        url = reverse('admin:core_company_change', args=[obj.company.id])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.company.business_name
        )
    company_link.short_description = _('Empresa')
    
    def is_main_display(self, obj):
        """
        Muestra si es sucursal principal
        """
        if obj.is_main:
            return format_html(
                '<span style="color: blue;">★</span> {}',
                _('Principal')
            )
        return '-'
    is_main_display.short_description = _('Principal')
    
    def is_active_display(self, obj):
        """
        Muestra el estado activo con colores
        """
        if obj.is_active:
            return format_html(
                '<span style="color: green;">●</span> {}',
                _('Activo')
            )
        else:
            return format_html(
                '<span style="color: red;">●</span> {}',
                _('Inactivo')
            )
    is_active_display.short_description = _('Estado')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Administración de logs de auditoría
    """
    list_display = (
        'created_at',
        'user_link',
        'company_link',
        'action_display',
        'object_repr',
        'ip_address'
    )
    
    # ✅ CORREGIDO: Usar nombres de campos correctos
    list_filter = (
        'action',
        'company',
        'created_at'
    )
    
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'object_repr',
        'ip_address'
    )
    
    # ✅ CORREGIDO: Usar nombres de campos correctos del modelo
    readonly_fields = (
        'id',
        'user',
        'company',
        'action',
        'object_id',
        'object_repr',
        'changes_display',
        'ip_address',
        'user_agent',
        'created_at'
    )
    
    fieldsets = (
        (_('Información General'), {
            'fields': (
                'created_at',
                'user',
                'company',
                'action',
                'ip_address'
            )
        }),
        (_('Objeto Afectado'), {
            'fields': (
                'object_id',
                'object_repr'
            )
        }),
        (_('Cambios'), {
            'fields': (
                'changes_display',
            )
        }),
        (_('Información Técnica'), {
            'fields': (
                'user_agent',
                'id'
            ),
            'classes': ('collapse',)
        })
    )
    
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        """
        No permitir crear logs manualmente
        """
        return False
    
    def has_change_permission(self, request, obj=None):
        """
        No permitir modificar logs
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        Solo superusuarios pueden eliminar logs
        """
        return request.user.is_superuser
    
    def user_link(self, obj):
        """
        Link al usuario
        """
        if obj.user:
            try:
                url = reverse('admin:auth_user_change', args=[obj.user.id])
                return format_html(
                    '<a href="{}">{}</a>',
                    url, obj.user.username
                )
            except:
                return obj.user.username
        return '-'
    user_link.short_description = _('Usuario')
    
    def company_link(self, obj):
        """
        Link a la empresa
        """
        if obj.company:
            try:
                url = reverse('admin:core_company_change', args=[obj.company.id])
                return format_html(
                    '<a href="{}">{}</a>',
                    url, obj.company.business_name
                )
            except:
                return obj.company.business_name
        return '-'
    company_link.short_description = _('Empresa')
    
    def action_display(self, obj):
        """
        Muestra la acción con colores
        """
        colors = {
            'CREATE': 'green',
            'UPDATE': 'orange',
            'DELETE': 'red',
            'VIEW': 'blue',
            'LOGIN': 'purple',
            'LOGOUT': 'gray'
        }
        # ✅ CORREGIDO: Usar obj.action en lugar de obj.action_type
        color = colors.get(obj.action, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.action
        )
    action_display.short_description = _('Acción')
    
    def changes_display(self, obj):
        """
        Muestra los cambios en formato legible
        """
        if not obj.changes:
            return '-'
        
        import json
        try:
            if isinstance(obj.changes, dict):
                changes_html = '<ul>'
                for field, change in obj.changes.items():
                    if isinstance(change, dict):
                        if 'old' in change and 'new' in change:
                            changes_html += f'<li><strong>{field}:</strong> {change["old"]} → {change["new"]}</li>'
                        elif 'new' in change:
                            changes_html += f'<li><strong>{field}:</strong> {change["new"]} (nuevo)</li>'
                        elif 'deleted' in change:
                            changes_html += f'<li><strong>{field}:</strong> {change["deleted"]} (eliminado)</li>'
                    else:
                        changes_html += f'<li><strong>{field}:</strong> {change}</li>'
                changes_html += '</ul>'
                return mark_safe(changes_html)
            else:
                return mark_safe(f'<pre>{json.dumps(obj.changes, indent=2, ensure_ascii=False)}</pre>')
        except Exception:
            return str(obj.changes)
    changes_display.short_description = _('Cambios')


# Personalización del admin site
admin.site.site_header = _('VENDO - Administración')
admin.site.site_title = _('VENDO Admin')
admin.site.index_title = _('Panel de Administración')