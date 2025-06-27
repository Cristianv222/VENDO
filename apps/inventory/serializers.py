from rest_framework import serializers
from .models import (
    Brand, Category, Supplier, Product, Stock, 
    StockMovement, StockAlert, ProductImage
)
from decimal import Decimal

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    subcategories = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = '__all__'
    
    def get_subcategories(self, obj):
        if obj.subcategories.exists():
            return CategorySerializer(obj.subcategories.all(), many=True).data
        return []

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    current_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    images = ProductImageSerializer(many=True, read_only=True)
    stock_info = StockSerializer(source='stock', read_only=True)
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['sku', 'barcode', 'barcode_image', 'profit_amount', 'profit_percentage']
    
    def create(self, validated_data):
        # Si no se proporciona precio de venta, calcularlo automáticamente
        if 'sale_price' not in validated_data or not validated_data['sale_price']:
            product = Product(**validated_data)
            product.calculate_sale_price_from_category()
            validated_data['sale_price'] = product.sale_price
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Recalcular precios si cambia el costo o la categoría
        if 'cost_price' in validated_data or 'category' in validated_data:
            instance = super().update(instance, validated_data)
            instance.calculate_profit()
            instance.save()
            return instance
        
        return super().update(instance, validated_data)

class ProductListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listas de productos"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    current_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 'category_name', 'brand_name',
            'cost_price', 'sale_price', 'current_stock', 'is_low_stock',
            'is_active', 'is_for_sale', 'image'
        ]

class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = StockMovement
        fields = '__all__'
        read_only_fields = ['total_cost']

class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockAlert
        fields = '__all__'

class ProductImportSerializer(serializers.Serializer):
    """Serializer para importación de productos"""
    file = serializers.FileField()
    
    def validate_file(self, value):
        if not value.name.endswith(('.xlsx', '.xls', '.csv')):
            raise serializers.ValidationError("Solo se permiten archivos Excel (.xlsx, .xls) o CSV (.csv)")
        return value

class BarcodeGenerationSerializer(serializers.Serializer):
    """Serializer para generación de códigos de barras"""
    products = serializers.ListField(child=serializers.IntegerField())
    format = serializers.ChoiceField(choices=['pdf', 'png'], default='pdf')
    size = serializers.ChoiceField(choices=['small', 'medium', 'large'], default='medium')