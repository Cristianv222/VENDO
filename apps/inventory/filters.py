import django_filters
from django.db import models
from .models import Product, StockMovement, StockAlert, Category, Brand, Supplier

class ProductFilter(django_filters.FilterSet):
    """Filtros para productos"""
    name = django_filters.CharFilter(lookup_expr='icontains')
    sku = django_filters.CharFilter(lookup_expr='icontains')
    barcode = django_filters.CharFilter(lookup_expr='exact')
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.filter(is_active=True))
    brand = django_filters.ModelChoiceFilter(queryset=Brand.objects.filter(is_active=True))
    supplier = django_filters.ModelChoiceFilter(queryset=Supplier.objects.filter(is_active=True))
    
    # Filtros de precio
    cost_price_min = django_filters.NumberFilter(field_name='cost_price', lookup_expr='gte')
    cost_price_max = django_filters.NumberFilter(field_name='cost_price', lookup_expr='lte')
    sale_price_min = django_filters.NumberFilter(field_name='sale_price', lookup_expr='gte')
    sale_price_max = django_filters.NumberFilter(field_name='sale_price', lookup_expr='lte')
    
    # Filtros de stock
    low_stock = django_filters.BooleanFilter(method='filter_low_stock')
    out_of_stock = django_filters.BooleanFilter(method='filter_out_of_stock')
    has_stock = django_filters.BooleanFilter(method='filter_has_stock')
    
    # Filtros de estado
    is_active = django_filters.BooleanFilter()
    is_for_sale = django_filters.BooleanFilter()
    track_stock = django_filters.BooleanFilter()
    
    # Filtros de fecha
    created_after = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = Product
        fields = []
    
    def filter_low_stock(self, queryset, name, value):
        """Filtrar productos con stock bajo"""
        if value:
            return queryset.annotate(
                current_stock=models.Sum('stock_movements__quantity')
            ).filter(
                track_stock=True,
                current_stock__lte=models.F('min_stock')
            )
        return queryset
    
    def filter_out_of_stock(self, queryset, name, value):
        """Filtrar productos sin stock"""
        if value:
            return queryset.annotate(
                current_stock=models.Sum('stock_movements__quantity')
            ).filter(
                track_stock=True,
                current_stock__lte=0
            )
        return queryset
    
    def filter_has_stock(self, queryset, name, value):
        """Filtrar productos con stock disponible"""
        if value:
            return queryset.annotate(
                current_stock=models.Sum('stock_movements__quantity')
            ).filter(
                track_stock=True,
                current_stock__gt=0
            )
        return queryset

class StockMovementFilter(django_filters.FilterSet):
    """Filtros para movimientos de stock"""
    product = django_filters.ModelChoiceFilter(queryset=Product.objects.filter(is_active=True))
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    product_sku = django_filters.CharFilter(field_name='product__sku', lookup_expr='icontains')
    movement_type = django_filters.ChoiceFilter(choices=StockMovement.MOVEMENT_TYPES)
    reason = django_filters.ChoiceFilter(choices=StockMovement.MOVEMENT_REASONS)
    
    # Filtros de cantidad
    quantity_min = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    quantity_max = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')
    
    # Filtros de fecha
    date_from = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')
    
    # Filtro de usuario
    user = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    
    # Filtro de documento de referencia
    reference_document = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = StockMovement
        fields = []

class StockAlertFilter(django_filters.FilterSet):
    """Filtros para alertas de stock"""
    product = django_filters.ModelChoiceFilter(queryset=Product.objects.filter(is_active=True))
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    alert_type = django_filters.ChoiceFilter(choices=StockAlert.ALERT_TYPES)
    is_active = django_filters.BooleanFilter()
    
    # Filtros de fecha
    created_after = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')
    resolved_after = django_filters.DateFilter(field_name='resolved_at', lookup_expr='gte')
    resolved_before = django_filters.DateFilter(field_name='resolved_at', lookup_expr='lte')
    
    class Meta:
        model = StockAlert
        fields = []

class CategoryFilter(django_filters.FilterSet):
    """Filtros para categorías"""
    name = django_filters.CharFilter(lookup_expr='icontains')
    parent = django_filters.ModelChoiceFilter(queryset=Category.objects.filter(is_active=True))
    is_active = django_filters.BooleanFilter()
    has_subcategories = django_filters.BooleanFilter(method='filter_has_subcategories')
    
    class Meta:
        model = Category
        fields = []
    
    def filter_has_subcategories(self, queryset, name, value):
        """Filtrar categorías que tienen subcategorías"""
        if value:
            return queryset.filter(subcategories__isnull=False).distinct()
        else:
            return queryset.filter(subcategories__isnull=True)

class BrandFilter(django_filters.FilterSet):
    """Filtros para marcas"""
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = Brand
        fields = []

class SupplierFilter(django_filters.FilterSet):
    """Filtros para proveedores"""
    name = django_filters.CharFilter(lookup_expr='icontains')
    ruc = django_filters.CharFilter(lookup_expr='icontains')
    email = django_filters.CharFilter(lookup_expr='icontains')
    contact_person = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = Supplier
        fields = []