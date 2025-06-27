from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import BaseModel
import uuid
from io import BytesIO
from django.core.files import File
from decimal import Decimal

# Importaciones opcionales para código de barras
try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

# Importaciones opcionales para manejo de imágenes
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

User = get_user_model()

class Brand(BaseModel):
    """Modelo para las marcas de productos"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    logo = models.ImageField(upload_to='brands/', blank=True, null=True, verbose_name="Logo")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ['name']
        db_table = 'inv_brands'
    
    def __str__(self):
        return self.name

class Category(BaseModel):
    """Modelo para categorías de productos con ganancia automática"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, 
                              related_name='subcategories', verbose_name="Categoría padre")
    profit_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        default=0, verbose_name="Porcentaje de ganancia (%)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['name']
        db_table = 'inv_categories'
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def get_full_name(self):
        """Obtiene el nombre completo de la categoría con su jerarquía"""
        if self.parent:
            return f"{self.parent.get_full_name()} > {self.name}"
        return self.name

class Supplier(BaseModel):
    """Modelo para proveedores"""
    name = models.CharField(max_length=200, verbose_name="Nombre")
    ruc = models.CharField(max_length=13, unique=True, verbose_name="RUC")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    address = models.TextField(blank=True, verbose_name="Dirección")
    contact_person = models.CharField(max_length=100, blank=True, verbose_name="Persona de contacto")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['name']
        db_table = 'inv_suppliers'
    
    def __str__(self):
        return f"{self.name} - {self.ruc}"

class Product(BaseModel):
    """Modelo principal para productos"""
    UNIT_CHOICES = [
        ('UNIT', 'Unidad'),
        ('KG', 'Kilogramo'),
        ('LT', 'Litro'),
        ('MT', 'Metro'),
        ('BOX', 'Caja'),
        ('PACK', 'Paquete'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    barcode = models.CharField(max_length=50, unique=True, blank=True, verbose_name="Código de barras")
    barcode_image = models.ImageField(upload_to='barcodes/', blank=True, null=True, 
                                     verbose_name="Imagen código de barras")
    
    # Relaciones
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="Categoría")
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, verbose_name="Marca")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Proveedor")
    
    # Precios y costos
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de costo")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de venta")
    profit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                                       verbose_name="Ganancia en dinero")
    profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, 
                                           verbose_name="Porcentaje de ganancia")
    
    # Detalles del producto
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='UNIT', verbose_name="Unidad")
    weight = models.DecimalField(max_digits=8, decimal_places=3, blank=True, null=True, verbose_name="Peso")
    dimensions = models.CharField(max_length=100, blank=True, verbose_name="Dimensiones")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Imagen")
    
    # Control de inventario
    track_stock = models.BooleanField(default=True, verbose_name="Controlar stock")
    min_stock = models.PositiveIntegerField(default=5, verbose_name="Stock mínimo")
    max_stock = models.PositiveIntegerField(default=100, verbose_name="Stock máximo")
    
    # Estado
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    is_for_sale = models.BooleanField(default=True, verbose_name="Disponible para venta")
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['name']
        db_table = 'inv_products'
        indexes = [
            models.Index(fields=['barcode']),
            models.Index(fields=['sku']),
            models.Index(fields=['category']),
            models.Index(fields=['brand']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.sku}"
    
    def save(self, *args, **kwargs):
        # Generar SKU si no existe
        if not self.sku:
            self.sku = self.generate_sku()
        
        # Generar código de barras si no existe
        if not self.barcode:
            self.barcode = self.generate_barcode()
        
        # Calcular ganancia automáticamente basada en la categoría
        if self.cost_price and self.category:
            if not self.sale_price or self.sale_price == 0:
                self.calculate_sale_price_from_category()
            self.calculate_profit()
        
        super().save(*args, **kwargs)
        
        # Generar imagen del código de barras
        if self.barcode and not self.barcode_image and BARCODE_AVAILABLE:
            self.generate_barcode_image()
    
    def generate_sku(self):
        """Genera un SKU único para el producto"""
        prefix = "PRD"
        if hasattr(self, 'category') and self.category:
            prefix = self.category.name[:3].upper()
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"{prefix}-{unique_id}"
    
    def generate_barcode(self):
        """Genera un código de barras único"""
        import time
        timestamp = str(int(time.time()))
        return f"78{timestamp[-10:]}"  # Código de 12 dígitos
    
    def generate_barcode_image(self):
        """Genera la imagen del código de barras"""
        if not self.barcode or not BARCODE_AVAILABLE:
            return
        
        try:
            # Generar código de barras EAN13
            ean = barcode.get('ean13', self.barcode, writer=ImageWriter())
            buffer = BytesIO()
            ean.write(buffer)
            
            # Guardar imagen
            filename = f"barcode_{self.barcode}.png"
            self.barcode_image.save(
                filename,
                File(buffer),
                save=False
            )
            self.save(update_fields=['barcode_image'])
        except Exception as e:
            print(f"Error generando código de barras: {e}")
    
    def calculate_sale_price_from_category(self):
        """Calcula el precio de venta basado en el porcentaje de la categoría"""
        if self.cost_price and self.category and self.category.profit_percentage:
            profit_amount = self.cost_price * (self.category.profit_percentage / 100)
            self.sale_price = self.cost_price + profit_amount
    
    def calculate_profit(self):
        """Calcula la ganancia y porcentaje de ganancia"""
        if self.cost_price and self.sale_price:
            self.profit_amount = self.sale_price - self.cost_price
            if self.cost_price > 0:
                self.profit_percentage = (self.profit_amount / self.cost_price) * 100
    
    @property
    def current_stock(self):
        """Obtiene el stock actual del producto"""
        return self.stock_movements.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def is_low_stock(self):
        """Verifica si el producto tiene stock bajo"""
        if not self.track_stock:
            return False
        return self.current_stock <= self.min_stock
    
    @property
    def is_out_of_stock(self):
        """Verifica si el producto está agotado"""
        if not self.track_stock:
            return False
        return self.current_stock <= 0

class Stock(BaseModel):
    """Modelo para el control de stock actual"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.IntegerField(default=0, verbose_name="Cantidad")
    reserved_quantity = models.IntegerField(default=0, verbose_name="Cantidad reservada")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        db_table = 'inv_stock'
    
    def __str__(self):
        return f"{self.product.name} - Stock: {self.quantity}"
    
    @property
    def available_quantity(self):
        """Cantidad disponible (sin reservas)"""
        return self.quantity - self.reserved_quantity

class StockMovement(BaseModel):
    """Modelo para movimientos de stock"""
    MOVEMENT_TYPES = [
        ('IN', 'Entrada'),
        ('OUT', 'Salida'),
        ('ADJUSTMENT', 'Ajuste'),
        ('TRANSFER', 'Transferencia'),
        ('RETURN', 'Devolución'),
    ]
    
    MOVEMENT_REASONS = [
        ('PURCHASE', 'Compra'),
        ('SALE', 'Venta'),
        ('ADJUSTMENT', 'Ajuste de inventario'),
        ('DAMAGED', 'Producto dañado'),
        ('EXPIRED', 'Producto vencido'),
        ('TRANSFER_IN', 'Transferencia entrada'),
        ('TRANSFER_OUT', 'Transferencia salida'),
        ('RETURN', 'Devolución'),
        ('INITIAL', 'Inventario inicial'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, verbose_name="Tipo de movimiento")
    reason = models.CharField(max_length=20, choices=MOVEMENT_REASONS, verbose_name="Motivo")
    quantity = models.IntegerField(verbose_name="Cantidad")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                   verbose_name="Costo unitario")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                    verbose_name="Costo total")
    reference_document = models.CharField(max_length=100, blank=True, verbose_name="Documento de referencia")
    notes = models.TextField(blank=True, verbose_name="Notas")
    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Usuario")
    
    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"
        ordering = ['-created_at']
        db_table = 'inv_stock_movements'
    
    def __str__(self):
        return f"{self.product.name} - {self.get_movement_type_display()} - {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Calcular costo total
        if self.unit_cost and self.quantity:
            self.total_cost = self.unit_cost * abs(self.quantity)
        
        super().save(*args, **kwargs)
        
        # Actualizar stock del producto
        self.update_product_stock()
    
    def update_product_stock(self):
        """Actualiza el stock del producto"""
        stock, created = Stock.objects.get_or_create(product=self.product)
        
        # Recalcular stock basado en todos los movimientos
        total_movements = StockMovement.objects.filter(
            product=self.product
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        stock.quantity = total_movements
        stock.save()

class StockAlert(BaseModel):
    """Modelo para alertas de stock"""
    ALERT_TYPES = [
        ('LOW_STOCK', 'Stock bajo'),
        ('OUT_OF_STOCK', 'Sin stock'),
        ('OVERSTOCK', 'Sobrestock'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, verbose_name="Tipo de alerta")
    current_stock = models.IntegerField(verbose_name="Stock actual")
    threshold = models.IntegerField(verbose_name="Umbral")
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Resuelta en")
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   verbose_name="Resuelta por")
    
    class Meta:
        verbose_name = "Alerta de Stock"
        verbose_name_plural = "Alertas de Stock"
        ordering = ['-created_at']
        db_table = 'inv_stock_alerts'
    
    def __str__(self):
        return f"{self.product.name} - {self.get_alert_type_display()}"
    
    def resolve(self, user):
        """Marca la alerta como resuelta"""
        self.is_active = False
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save()

class ProductImage(BaseModel):
    """Modelo para múltiples imágenes de productos"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/', verbose_name="Imagen")
    alt_text = models.CharField(max_length=200, blank=True, verbose_name="Texto alternativo")
    is_main = models.BooleanField(default=False, verbose_name="Imagen principal")
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    
    class Meta:
        verbose_name = "Imagen de Producto"
        verbose_name_plural = "Imágenes de Productos"
        ordering = ['order']
        db_table = 'inv_product_images'
    
    def __str__(self):
        return f"{self.product.name} - Imagen {self.order}"