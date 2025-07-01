from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
import json

from .models import (
    Invoice, InvoiceDetail, InvoicePayment, Customer, Product, 
    SRIConfiguration, SRILog
)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['identificacion', 'razon_social', 'email', 'telefono', 'company', 'created_at']
    list_filter = ['tipo_identificacion', 'company', 'created_at']
    search_fields = ['identificacion', 'razon_social', 'email']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'tipo_identificacion', 'identificacion', 'razon_social')
        }),
        ('Contacto', {
            'fields': ('direccion', 'email', 'telefono')
        }),
        ('Sistema', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Filtrar por empresa del usuario si no es superuser
            if hasattr(request.user, 'company'):
                qs = qs.filter(company=request.user.company)
        return qs

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['codigo_principal', 'descripcion', 'precio_unitario', 'porcentaje_iva', 'company', 'is_active']
    list_filter = ['tiene_iva', 'tiene_ice', 'company', 'is_active']
    search_fields = ['codigo_principal', 'codigo_auxiliar', 'descripcion']
    ordering = ['descripcion']
    
    fieldsets = (
        ('Información del Producto', {
            'fields': ('company', 'codigo_principal', 'codigo_auxiliar', 'descripcion', 'precio_unitario')
        }),
        ('Configuración de Impuestos', {
            'fields': ('tiene_iva', 'porcentaje_iva', 'tiene_ice', 'porcentaje_ice')
        }),
        ('Sistema', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if hasattr(request.user, 'company'):
                qs = qs.filter(company=request.user.company)
        return qs

class InvoiceDetailInline(admin.TabularInline):
    model = InvoiceDetail
    extra = 0
    readonly_fields = ('precio_total_sin_impuesto', 'valor_iva', 'valor_ice')
    
    fields = [
        'product', 'codigo_principal', 'descripcion', 'cantidad', 
        'precio_unitario', 'descuento', 'precio_total_sin_impuesto',
        'porcentaje_iva', 'valor_iva', 'porcentaje_ice', 'valor_ice'
    ]

class InvoicePaymentInline(admin.TabularInline):
    model = InvoicePayment
    extra = 0
    
    fields = ['forma_pago', 'valor', 'plazo', 'unidad_tiempo']

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'numero_factura', 'customer_name', 'fecha_emision', 'importe_total', 
        'estado_sri_badge', 'authorization_status', 'company'
    ]
    list_filter = ['estado_sri', 'fecha_emision', 'company', 'created_at']
    search_fields = ['numero_factura', 'customer__razon_social', 'customer__identificacion', 'clave_acceso']
    ordering = ['-created_at']
    
    inlines = [InvoiceDetailInline, InvoicePaymentInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'customer', 'numero_factura', 'fecha_emision', 'observaciones')
        }),
        ('Numeración', {
            'fields': ('establecimiento', 'punto_emision', 'secuencial', 'clave_acceso'),
            'classes': ('collapse',)
        }),
        ('Totales', {
            'fields': (
                'subtotal_sin_impuestos', 'subtotal_0', 'subtotal_12', 
                'valor_iva', 'valor_ice', 'propina', 'importe_total'
            )
        }),
        ('Estado SRI', {
            'fields': ('estado_sri', 'numero_autorizacion', 'fecha_autorizacion')
        }),
        ('Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = (
        'numero_factura', 'secuencial', 'clave_acceso', 'subtotal_sin_impuestos',
        'subtotal_0', 'subtotal_12', 'valor_iva', 'valor_ice', 'importe_total',
        'created_at', 'updated_at'
    )
    
    actions = ['resend_to_sri', 'get_authorization', 'send_email']
    
    def customer_name(self, obj):
        return obj.customer.razon_social
    customer_name.short_description = 'Cliente'
    
    def estado_sri_badge(self, obj):
        colors = {
            'PENDIENTE': 'orange',
            'ENVIADO': 'blue', 
            'AUTORIZADO': 'green',
            'RECHAZADO': 'red'
        }
        color = colors.get(obj.estado_sri, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.estado_sri
        )
    estado_sri_badge.short_description = 'Estado SRI'
    
    def authorization_status(self, obj):
        if obj.numero_autorizacion:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                obj.numero_autorizacion[:20] + '...' if len(obj.numero_autorizacion) > 20 else obj.numero_autorizacion
            )
        return format_html('<span style="color: red;">Sin autorización</span>')
    authorization_status.short_description = 'Autorización'
    
    def resend_to_sri(self, request, queryset):
        from .tasks import process_invoice_async
        
        count = 0
        for invoice in queryset:
            if invoice.estado_sri in ['PENDIENTE', 'RECHAZADO']:
                process_invoice_async.delay(str(invoice.id))
                count += 1
        
        self.message_user(request, f'{count} facturas enviadas a procesamiento SRI')
    resend_to_sri.short_description = 'Reenviar al SRI'
    
    def get_authorization(self, request, queryset):
        from .tasks import get_authorization_async
        
        count = 0
        for invoice in queryset:
            if invoice.estado_sri == 'ENVIADO':
                get_authorization_async.delay(str(invoice.id))
                count += 1
        
        self.message_user(request, f'{count} facturas enviadas a verificación de autorización')
    get_authorization.short_description = 'Obtener autorización'
    
    def send_email(self, request, queryset):
        from .tasks import send_invoice_email_async
        
        count = 0
        for invoice in queryset:
            if invoice.estado_sri == 'AUTORIZADO' and invoice.customer.email:
                send_invoice_email_async.delay(str(invoice.id))
                count += 1
        
        self.message_user(request, f'{count} facturas enviadas por email')
    send_email.short_description = 'Enviar por email'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if hasattr(request.user, 'company'):
                qs = qs.filter(company=request.user.company)
        return qs

@admin.register(SRIConfiguration)
class SRIConfigurationAdmin(admin.ModelAdmin):
    list_display = ['company', 'environment', 'email_host_user', 'certificate_status', 'is_active']
    list_filter = ['environment', 'is_active', 'created_at']
    search_fields = ['company__razon_social', 'email_host_user']
    
    fieldsets = (
        ('Empresa', {
            'fields': ('company',)
        }),
        ('Configuración SRI', {
            'fields': ('environment', 'certificate_file', 'certificate_password')
        }),
        ('Configuración Email', {
            'fields': ('email_host', 'email_port', 'email_host_user', 'email_host_password', 'email_use_tls')
        }),
        ('Sistema', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def certificate_status(self, obj):
        try:
            from .sri_client import SRIClient
            sri_client = SRIClient(obj.company)
            cert_info = sri_client.validate_certificate()
            
            if cert_info['valid']:
                days_to_expire = (cert_info['not_valid_after'] - timezone.now()).days
                if days_to_expire <= 30:
                    return format_html(
                        '<span style="color: orange;">⚠ Vence en {} días</span>',
                        days_to_expire
                    )
                else:
                    return format_html('<span style="color: green;">✓ Válido</span>')
            else:
                return format_html('<span style="color: red;">✗ Inválido</span>')
        except:
            return format_html('<span style="color: gray;">Sin verificar</span>')
    certificate_status.short_description = 'Estado Certificado'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if hasattr(request.user, 'company'):
                qs = qs.filter(company=request.user.company)
        return qs

@admin.register(SRILog)
class SRILogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'company_name', 'clave_acceso_short', 'proceso', 'estado_badge', 'error_preview']
    list_filter = ['proceso', 'estado', 'created_at', 'company']
    search_fields = ['clave_acceso', 'error_message', 'company__razon_social']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'invoice', 'clave_acceso', 'proceso', 'estado')
        }),
        ('Respuesta', {
            'fields': ('response_data_formatted', 'error_message')
        }),
        ('Sistema', {
            'fields': ('created_at',)
        })
    )
    
    readonly_fields = ('response_data_formatted', 'created_at')
    
    def company_name(self, obj):
        return obj.company.razon_social
    company_name.short_description = 'Empresa'
    
    def clave_acceso_short(self, obj):
        if obj.clave_acceso:
            return obj.clave_acceso[:20] + '...' if len(obj.clave_acceso) > 20 else obj.clave_acceso
        return '-'
    clave_acceso_short.short_description = 'Clave de Acceso'
    
    def estado_badge(self, obj):
        color = 'green' if obj.estado == 'EXITOSO' else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.estado
        )
    estado_badge.short_description = 'Estado'
    
    def error_preview(self, obj):
        if obj.error_message:
            preview = obj.error_message[:50] + '...' if len(obj.error_message) > 50 else obj.error_message
            return format_html('<span style="color: red;">{}</span>', preview)
        return '-'
    error_preview.short_description = 'Error'
    
    def response_data_formatted(self, obj):
        if obj.response_data:
            formatted_json = json.dumps(obj.response_data, indent=2, ensure_ascii=False)
            return format_html('<pre>{}</pre>', formatted_json)
        return '-'
    response_data_formatted.short_description = 'Datos de Respuesta'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if hasattr(request.user, 'company'):
                qs = qs.filter(company=request.user.company)
        return qs

# Dashboard personalizado para facturación
class InvoicingAdminDashboard:
    """Dashboard personalizado para el admin de facturación"""
    
    def __init__(self, request):
        self.request = request
        self.company = getattr(request.user, 'company', None) if hasattr(request.user, 'company') else None
    
    def get_stats(self):
        if not self.company:
            return {}
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Estadísticas básicas
        total_invoices = Invoice.objects.filter(company=self.company).count()
        today_invoices = Invoice.objects.filter(company=self.company, fecha_emision__date=today).count()
        pending_invoices = Invoice.objects.filter(company=self.company, estado_sri='PENDIENTE').count()
        
        # Ingresos del día
        today_revenue = Invoice.objects.filter(
            company=self.company, 
            fecha_emision__date=today,
            estado_sri='AUTORIZADO'
        ).aggregate(total=Sum('importe_total'))['total'] or 0
        
        # Errores recientes
        recent_errors = SRILog.objects.filter(
            company=self.company,
            estado='ERROR',
            created_at__gte=week_ago
        ).count()
        
        return {
            'total_invoices': total_invoices,
            'today_invoices': today_invoices,
            'pending_invoices': pending_invoices,
            'today_revenue': today_revenue,
            'recent_errors': recent_errors
        }

# Personalizar el admin site
admin.site.site_header = 'Vendo - Administración de Facturación Electrónica'
admin.site.site_title = 'Vendo Admin'
admin.site.index_title = 'Panel de Administración'