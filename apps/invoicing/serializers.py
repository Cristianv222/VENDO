from rest_framework import serializers
from .models import (
    Invoice, InvoiceDetail, InvoicePayment, Customer, Product, 
    SRIConfiguration, SRILog, TipoDocumento, TipoIdentificacion, FormaPago
)
from decimal import Decimal

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'id', 'tipo_identificacion', 'identificacion', 'razon_social',
            'direccion', 'email', 'telefono', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_identificacion(self):
        identificacion = self.validated_data['identificacion']
        tipo_identificacion = self.validated_data.get('tipo_identificacion')
        
        # Validaciones específicas
        if tipo_identificacion == TipoIdentificacion.CEDULA:
            if len(identificacion) != 10 or not identificacion.isdigit():
                raise serializers.ValidationError('La cédula debe tener 10 dígitos numéricos')
        elif tipo_identificacion == TipoIdentificacion.RUC:
            if len(identificacion) != 13 or not identificacion.isdigit():
                raise serializers.ValidationError('El RUC debe tener 13 dígitos numéricos')
        
        return identificacion

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'codigo_principal', 'codigo_auxiliar', 'descripcion',
            'precio_unitario', 'tiene_iva', 'porcentaje_iva', 
            'tiene_ice', 'porcentaje_ice', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_precio_unitario(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a 0')
        return value

class InvoicePaymentSerializer(serializers.ModelSerializer):
    forma_pago_display = serializers.CharField(source='get_forma_pago_display', read_only=True)
    
    class Meta:
        model = InvoicePayment
        fields = [
            'id', 'forma_pago', 'forma_pago_display', 'valor', 
            'plazo', 'unidad_tiempo'
        ]
        read_only_fields = ['id']
    
    def validate_valor(self, value):
        if value <= 0:
            raise serializers.ValidationError('El valor debe ser mayor a 0')
        return value

class InvoiceDetailSerializer(serializers.ModelSerializer):
    product_data = ProductSerializer(source='product', read_only=True)
    subtotal = serializers.SerializerMethodField()
    
    class Meta:
        model = InvoiceDetail
        fields = [
            'id', 'product', 'product_data', 'codigo_principal', 'codigo_auxiliar',
            'descripcion', 'cantidad', 'precio_unitario', 'descuento',
            'precio_total_sin_impuesto', 'porcentaje_iva', 'valor_iva',
            'porcentaje_ice', 'valor_ice', 'subtotal'
        ]
        read_only_fields = [
            'id', 'precio_total_sin_impuesto', 'valor_iva', 'valor_ice', 'subtotal'
        ]
    
    def get_subtotal(self, obj):
        return obj.precio_total_sin_impuesto + obj.valor_iva + obj.valor_ice
    
    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad debe ser mayor a 0')
        return value
    
    def validate_precio_unitario(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio unitario debe ser mayor a 0')
        return value

class InvoiceSerializer(serializers.ModelSerializer):
    customer_data = CustomerSerializer(source='customer', read_only=True)
    detalles = InvoiceDetailSerializer(source='invoicedetail_set', many=True, read_only=True)
    pagos = InvoicePaymentSerializer(source='invoicepayment_set', many=True, read_only=True)
    estado_sri_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'customer', 'customer_data', 'establecimiento', 'punto_emision',
            'secuencial', 'numero_factura', 'fecha_emision', 'clave_acceso',
            'subtotal_sin_impuestos', 'subtotal_0', 'subtotal_12', 'valor_iva',
            'valor_ice', 'propina', 'importe_total', 'estado_sri', 'estado_sri_display',
            'numero_autorizacion', 'fecha_autorizacion', 'observaciones',
            'detalles', 'pagos', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'secuencial', 'numero_factura', 'clave_acceso',
            'subtotal_sin_impuestos', 'subtotal_0', 'subtotal_12', 'valor_iva',
            'valor_ice', 'importe_total', 'estado_sri', 'numero_autorizacion',
            'fecha_autorizacion', 'created_at', 'updated_at'
        ]
    
    def get_estado_sri_display(self, obj):
        status_map = {
            'PENDIENTE': 'Pendiente',
            'ENVIADO': 'Enviado al SRI',
            'AUTORIZADO': 'Autorizado',
            'RECHAZADO': 'Rechazado'
        }
        return status_map.get(obj.estado_sri, obj.estado_sri)

class InvoiceCreateSerializer(serializers.Serializer):
    """Serializer para crear facturas con todos sus componentes"""
    
    # Datos del cliente
    customer = serializers.JSONField()
    
    # Datos de la factura
    establecimiento = serializers.CharField(max_length=3, default='001')
    punto_emision = serializers.CharField(max_length=3, default='001')
    observaciones = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    # Detalles de productos
    detalles = serializers.ListField(
        child=serializers.JSONField(),
        min_length=1
    )
    
    # Formas de pago
    pagos = serializers.ListField(
        child=serializers.JSONField(),
        min_length=1
    )
    
    def validate_customer(self, value):
        """Valida los datos del cliente"""
        required_fields = ['tipo_identificacion', 'identificacion', 'razon_social']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f'Campo requerido en customer: {field}')
        
        # Validar tipo de identificación
        if value['tipo_identificacion'] not in dict(TipoIdentificacion.choices):
            raise serializers.ValidationError('Tipo de identificación inválido')
        
        return value
    
    def validate_detalles(self, value):
        """Valida los detalles de la factura"""
        if not value:
            raise serializers.ValidationError('Debe incluir al menos un detalle')
        
        for i, detalle in enumerate(value):
            required_fields = ['codigo_principal', 'cantidad', 'precio_unitario']
            for field in required_fields:
                if field not in detalle:
                    raise serializers.ValidationError(f'Campo requerido en detalle {i+1}: {field}')
            
            # Validar valores numéricos
            try:
                cantidad = Decimal(str(detalle['cantidad']))
                precio_unitario = Decimal(str(detalle['precio_unitario']))
                
                if cantidad <= 0:
                    raise serializers.ValidationError(f'Cantidad inválida en detalle {i+1}')
                if precio_unitario <= 0:
                    raise serializers.ValidationError(f'Precio unitario inválido en detalle {i+1}')
                    
            except (ValueError, TypeError):
                raise serializers.ValidationError(f'Valores numéricos inválidos en detalle {i+1}')
        
        return value
    
    def validate_pagos(self, value):
        """Valida las formas de pago"""
        if not value:
            raise serializers.ValidationError('Debe incluir al menos una forma de pago')
        
        total_pagos = Decimal('0')
        
        for i, pago in enumerate(value):
            required_fields = ['forma_pago', 'valor']
            for field in required_fields:
                if field not in pago:
                    raise serializers.ValidationError(f'Campo requerido en pago {i+1}: {field}')
            
            # Validar forma de pago
            if pago['forma_pago'] not in dict(FormaPago.choices):
                raise serializers.ValidationError(f'Forma de pago inválida en pago {i+1}')
            
            # Validar valor
            try:
                valor = Decimal(str(pago['valor']))
                if valor <= 0:
                    raise serializers.ValidationError(f'Valor inválido en pago {i+1}')
                total_pagos += valor
            except (ValueError, TypeError):
                raise serializers.ValidationError(f'Valor numérico inválido en pago {i+1}')
        
        return value

class SRILogSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.razon_social', read_only=True)
    invoice_number = serializers.CharField(source='invoice.numero_factura', read_only=True)
    
    class Meta:
        model = SRILog
        fields = [
            'id', 'company', 'company_name', 'invoice', 'invoice_number',
            'clave_acceso', 'proceso', 'estado', 'response_data',
            'error_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class SRIConfigurationSerializer(serializers.ModelSerializer):
    certificate_info = serializers.SerializerMethodField()
    
    class Meta:
        model = SRIConfiguration
        fields = [
            'id', 'environment', 'email_host', 'email_port',
            'email_host_user', 'email_use_tls', 'certificate_info',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'certificate_info', 'created_at', 'updated_at'
        ]
    
    def get_certificate_info(self, obj):
        try:
            from .sri_client import SRIClient
            sri_client = SRIClient(obj.company)
            return sri_client.validate_certificate()
        except Exception as e:
            return {'valid': False, 'error': str(e)}

# Serializers para respuestas de acciones específicas
class InvoiceActionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.JSONField(required=False)

class SRITestResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    certificate_info = serializers.JSONField(required=False)

class EmailTestResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()