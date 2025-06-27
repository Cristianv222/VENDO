from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.forms import TextInput, Textarea
from .models import (
    Brand, Category, Supplier, Product, Stock, 
    StockMovement, StockAlert, ProductImage
)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'products_count', 'logo_preview', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'logo', 'is_active')
        }),
        ('Información del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 4px;" />',
                obj.logo.url
            )
        return "Sin logo"
    logo_preview.short_description = "Logo"
    
    def products_count(self, obj):
        count = obj.product_set.count()
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?brand__id__exact={obj.id}'
            return format_html('<a href="{}">{} productos</a>', url, count)
        return "0 productos"
    products_count.short_description = "Productos"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'profit_percentage', 'products_count', 'is_active', 'created_at']
    list_filter = ['parent', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'parent', 'description', 'profit_percentage', 'is_active')
        }),
        ('Información del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def products_count(self, obj):
        count = obj.product_set.count()
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?category__id__exact={obj.id}'
            return format_html('<a href="{}">{} productos</a>', url, count)
        return "0 productos"
    products_count.short_description = "Productos"

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'ruc', 'email', 'phone', 'contact_person', 'products_count', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'ruc', 'email', 'contact_person']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'ruc', 'is_active')
        }),
        ('Información de Contacto', {
            'fields': ('email', 'phone', 'contact_person', 'address')
        }),
        ('Información del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def products_count(self, obj):
        count = obj.product_set.count()
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?supplier__id__exact={obj.id}'
            return format_html('<a href="{}">{} productos</a>', url, count)
        return "0 productos"
    products_count.short_description = "Productos"

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_main', 'order']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'sku', 'name', 'category', 'brand', 'supplier', 
        'cost_price', 'sale_price', 'profit_display', 
        'current_stock_display', 'stock_status', 'is_active'
    ]
    list_filter = [
        'category', 'brand', 'supplier', 'unit', 
        'is_active', 'is_for_sale', 'track_stock', 'created_at'
    ]
    search_fields = ['name', 'sku', 'barcode', 'description']
    readonly_fields = [
        'sku', 'barcode', 'barcode_image_preview', 'profit_amount', 
        'profit_percentage', 'current_stock_display', 'created_at', 'updated_at'
    ]
    inlines = [ProductImageInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'sku', 'barcode', 'barcode_image_preview')
        }),
        ('Clasificación', {
            'fields': ('category', 'brand', 'supplier')
        }),
        ('Precios y Costos', {
            'fields': ('cost_price', 'sale_price', 'profit_amount', 'profit_percentage')
        }),
        ('Detalles del Producto', {
            'fields': ('unit', 'weight', 'dimensions', 'image')
        }),
        ('Control de Inventario', {
            'fields': ('track_stock', 'min_stock', 'max_stock', 'current_stock_display')
        }),
        ('Estado', {
            'fields': ('is_active', 'is_for_sale')
        }),
        ('Información del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '40'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 60})},
    }
    
    def barcode_image_preview(self, obj):
        if obj.barcode_image:
            return format_html(
                '<img src="{}" width="200" style="border: 1px solid #ddd;" />',
                obj.barcode_image.url
            )
        return "Sin imagen de código de barras"
    barcode_image_preview.short_description = "Código de Barras"
    
    def profit_display(self, obj):
        return format_html(
            '<span style="color: green;">${:.2f} ({:.1f}%)</span>',
            obj.profit_amount,
            obj.profit_percentage
        )
    profit_display.short_description = "Ganancia"
    
    def current_stock_display(self, obj):
        stock = obj.current_stock
        if not obj.track_stock:
            return "No controlado"
        
        color = "red" if stock <= obj.min_stock else "orange" if stock <= obj.min_stock * 1.5 else "green"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, stock
        )
    current_stock_display.short_description = "Stock Actual"
    
    def stock_status(self, obj):
        if not obj.track_stock:
            return format_html('<span style="color: gray;">No controlado</span>')
        
        if obj.is_out_of_stock:
            return format_html('<span style="color: red; font-weight: bold;">Sin stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: orange; font-weight: bold;">Stock bajo</span>')
        else:
            return format_html('<span style="color: green;">Stock normal</span>')
    stock_status.short_description = "Estado Stock"
    
    actions = ['generate_barcodes', 'activate_products', 'deactivate_products']
    
    def generate_barcodes(self, request, queryset):
        """Acción para generar códigos de barras"""
        for product in queryset:
            if not product.barcode_image:
                product.generate_barcode_image()
        
        self.message_user(
            request,
            f"Códigos de barras generados para {queryset.count()} productos."
        )
    generate_barcodes.short_description = "Generar códigos de barras"
    
    def activate_products(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} productos activados.")
    activate_products.short_description = "Activar productos seleccionados"
    
    def deactivate_products(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} productos desactivados.")
    deactivate_products.short_description = "Desactivar productos seleccionados"

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'movement_type', 'reason', 'quantity_display', 
        'unit_cost', 'total_cost', 'user', 'created_at'
    ]
    list_filter = ['movement_type', 'reason', 'created_at', 'user']
    search_fields = ['product__name', 'product__sku', 'reference_document', 'notes']
    readonly_fields = ['total_cost', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('product', 'movement_type', 'reason', 'quantity')
        }),
        ('Costos', {
            'fields': ('unit_cost', 'total_cost')
        }),
        ('Información Adicional', {
            'fields': ('reference_document', 'notes', 'user')
        }),
        ('Información del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def quantity_display(self, obj):
        color = "green" if obj.quantity > 0 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.quantity
        )
    quantity_display.short_description = "Cantidad"
    
    def has_delete_permission(self, request, obj=None):
        # Solo permitir eliminar movimientos recientes (menos de 24 horas)
        if obj:
            from django.utils import timezone
            from datetime import timedelta
            return obj.created_at > timezone.now() - timedelta(hours=24)
        return True

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'alert_type', 'current_stock', 'threshold', 
        'is_active', 'created_at', 'resolved_by'
    ]
    list_filter = ['alert_type', 'is_active', 'created_at']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        # Las alertas se generan automáticamente
        return False

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'reserved_quantity', 'available_quantity', 'last_updated']
    list_filter = ['last_updated']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['last_updated']
    
    def available_quantity(self, obj):
        return obj.available_quantity
    available_quantity.short_description = "Cantidad Disponible"
    
    def has_add_permission(self, request):
        # Los stocks se crean automáticamente
        return False

# Configuración del admin site
admin.site.site_header = "Sistema de Inventario"
admin.site.site_title = "Inventario Admin"
admin.site.index_title = "Administración de Inventario"