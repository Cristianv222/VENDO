from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
import uuid
from decimal import Decimal

class TipoDocumento(models.TextChoices):
    FACTURA = '01', 'Factura'
    NOTA_CREDITO = '04', 'Nota de Crédito'
    NOTA_DEBITO = '05', 'Nota de Débito'
    GUIA_REMISION = '06', 'Guía de Remisión'
    COMPROBANTE_RETENCION = '07', 'Comprobante de Retención'

class TipoIdentificacion(models.TextChoices):
    CEDULA = '05', 'Cédula'
    RUC = '04', 'RUC'
    PASAPORTE = '06', 'Pasaporte'
    CONSUMIDOR_FINAL = '07', 'Consumidor Final'
    EXTERIOR = '08', 'Identificación del Exterior'

class FormaPago(models.TextChoices):
    SIN_UTILIZACION = '01', 'Sin utilización del sistema financiero'
    COMPENSACION = '15', 'Compensación de deudas'
    TARJETA_DEBITO = '16', 'Tarjeta de débito'
    DINERO_ELECTRONICO = '17', 'Dinero electrónico'
    TARJETA_PREPAGO = '18', 'Tarjeta prepago'
    TARJETA_CREDITO = '19', 'Tarjeta de crédito'
    OTROS = '20', 'Otros con utilización del sistema financiero'

class TipoImpuesto(models.TextChoices):
    IVA = '2', 'IVA'
    ICE = '3', 'ICE'
    IRBPNR = '5', 'IRBPNR'

class Customer(BaseModel):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    tipo_identificacion = models.CharField(max_length=2, choices=TipoIdentificacion.choices)
    identificacion = models.CharField(max_length=20)
    razon_social = models.CharField(max_length=300)
    direccion = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        unique_together = ['company', 'identificacion']
    
    def __str__(self):
        return f"{self.identificacion} - {self.razon_social}"

class Product(BaseModel):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    codigo_principal = models.CharField(max_length=25)
    codigo_auxiliar = models.CharField(max_length=25, blank=True)
    descripcion = models.CharField(max_length=300)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=4)
    
    # Configuración de impuestos
    tiene_iva = models.BooleanField(default=True)
    porcentaje_iva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('12.00'))
    tiene_ice = models.BooleanField(default=False)
    porcentaje_ice = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        unique_together = ['company', 'codigo_principal']
    
    def __str__(self):
        return f"{self.codigo_principal} - {self.descripcion}"

class Invoice(BaseModel):
    # Información básica
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    
    # Numeración
    establecimiento = models.CharField(max_length=3, default='001')
    punto_emision = models.CharField(max_length=3, default='001')
    secuencial = models.CharField(max_length=9)
    numero_factura = models.CharField(max_length=17)  # 001-001-000000001
    
    # Fechas
    fecha_emision = models.DateTimeField()
    
    # Clave de acceso
    clave_acceso = models.CharField(max_length=49, unique=True, blank=True)
    
    # Totales
    subtotal_sin_impuestos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal_0 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal_12 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_ice = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    propina = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    importe_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Estados SRI
    estado_sri = models.CharField(max_length=20, default='PENDIENTE')  # PENDIENTE, ENVIADO, AUTORIZADO, RECHAZADO
    numero_autorizacion = models.CharField(max_length=49, blank=True)
    fecha_autorizacion = models.DateTimeField(null=True, blank=True)
    xml_autorizado = models.TextField(blank=True)
    
    # Observaciones
    observaciones = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        unique_together = ['company', 'establecimiento', 'punto_emision', 'secuencial']
    
    def __str__(self):
        return self.numero_factura
    
    def calcular_totales(self):
        """Calcula los totales de la factura"""
        detalles = self.invoicedetail_set.all()
        
        self.subtotal_sin_impuestos = sum(d.precio_total_sin_impuesto for d in detalles)
        self.subtotal_0 = sum(d.precio_total_sin_impuesto for d in detalles if d.porcentaje_iva == 0)
        self.subtotal_12 = sum(d.precio_total_sin_impuesto for d in detalles if d.porcentaje_iva > 0)
        self.valor_iva = sum(d.valor_iva for d in detalles)
        self.valor_ice = sum(d.valor_ice for d in detalles)
        self.importe_total = self.subtotal_sin_impuestos + self.valor_iva + self.valor_ice + self.propina
        
        self.save()

class InvoiceDetail(BaseModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    # Detalle del producto
    codigo_principal = models.CharField(max_length=25)
    codigo_auxiliar = models.CharField(max_length=25, blank=True)
    descripcion = models.CharField(max_length=300)
    cantidad = models.DecimalField(max_digits=12, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=4)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_total_sin_impuesto = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Impuestos
    porcentaje_iva = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    valor_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    porcentaje_ice = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    valor_ice = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        verbose_name = "Detalle de Factura"
        verbose_name_plural = "Detalles de Facturas"
    
    def save(self, *args, **kwargs):
        # Calcular totales automáticamente
        precio_sin_descuento = self.cantidad * self.precio_unitario
        self.precio_total_sin_impuesto = precio_sin_descuento - self.descuento
        
        if self.porcentaje_iva > 0:
            self.valor_iva = self.precio_total_sin_impuesto * (self.porcentaje_iva / 100)
        
        if self.porcentaje_ice > 0:
            self.valor_ice = self.precio_total_sin_impuesto * (self.porcentaje_ice / 100)
        
        super().save(*args, **kwargs)

class InvoicePayment(BaseModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    forma_pago = models.CharField(max_length=2, choices=FormaPago.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    plazo = models.IntegerField(default=0)  # días
    unidad_tiempo = models.CharField(max_length=10, default='dias')
    
    class Meta:
        verbose_name = "Pago de Factura"
        verbose_name_plural = "Pagos de Facturas"

class SRIConfiguration(BaseModel):
    company = models.OneToOneField('core.Company', on_delete=models.CASCADE, related_name='sri_config')
    
    # Certificado P12
    certificate_file = models.FileField(upload_to='certificates/', help_text="Archivo de certificado P12")
    certificate_password = models.CharField(max_length=255, help_text="Contraseña del certificado P12")
    
    # Configuración SRI
    environment = models.CharField(
        max_length=20,
        choices=[('test', 'Pruebas'), ('production', 'Producción')],
        default='test'
    )
    
    # Configuración de Email
    email_host = models.CharField(max_length=255, default='smtp.gmail.com')
    email_port = models.IntegerField(default=587)
    email_host_user = models.EmailField()
    email_host_password = models.CharField(max_length=255)
    email_use_tls = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Configuración SRI"
        verbose_name_plural = "Configuraciones SRI"

class SRILog(BaseModel):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True)
    clave_acceso = models.CharField(max_length=49)
    
    # Proceso
    proceso = models.CharField(max_length=50)  # ENVIO, AUTORIZACION, EMAIL
    estado = models.CharField(max_length=20)   # EXITOSO, ERROR
    
    # Respuesta del SRI
    response_data = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Log SRI"
        verbose_name_plural = "Logs SRI"