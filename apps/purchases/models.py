# apps/purchases/models.py

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from apps.core.models import BaseModel


class Supplier(BaseModel):
    """Proveedores"""
    
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        verbose_name="Empresa"
    )
    
    # Identificación
    identification_type = models.CharField(
        max_length=20,
        choices=[
            ('cedula', 'Cédula'),
            ('ruc', 'RUC'),
            ('passport', 'Pasaporte'),
            ('foreigner', 'Identificación del Exterior'),
        ],
        verbose_name="Tipo de Identificación"
    )
    identification = models.CharField(max_length=20, verbose_name="Identificación")
    
    # Información del proveedor
    name = models.CharField(max_length=255, verbose_name="Nombre/Razón Social")
    commercial_name = models.CharField(max_length=255, blank=True, verbose_name="Nombre Comercial")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    mobile = models.CharField(max_length=20, blank=True, verbose_name="Móvil")
    website = models.URLField(blank=True, verbose_name="Sitio Web")
    
    # Dirección
    address = models.TextField(verbose_name="Dirección")
    city = models.CharField(max_length=100, verbose_name="Ciudad")
    province = models.CharField(max_length=100, verbose_name="Provincia")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="Código Postal")
    
    # Información comercial
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Límite de Crédito"
    )
    payment_terms = models.PositiveIntegerField(
        default=30,
        verbose_name="Días de Crédito"
    )
    
    # Contacto principal
    contact_person = models.CharField(max_length=255, blank=True, verbose_name="Persona de Contacto")
    contact_email = models.EmailField(blank=True, verbose_name="Email de Contacto")
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono de Contacto")
    
    # Estado
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    # Observaciones
    notes = models.TextField(blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        db_table = 'purchases_supplier'
        unique_together = [['company', 'identification']]
        indexes = [
            models.Index(fields=['identification']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.identification})"


class PurchaseOrder(BaseModel):
    """Órdenes de compra"""
    
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        verbose_name="Empresa"
    )
    branch = models.ForeignKey(
        'core.Branch',
        on_delete=models.CASCADE,
        verbose_name="Sucursal"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        verbose_name="Proveedor"
    )
    
    # Número de orden
    order_number = models.CharField(max_length=20, verbose_name="Número de Orden")
    
    # Fechas
    order_date = models.DateField(default=timezone.now, verbose_name="Fecha de Orden")
    expected_date = models.DateField(verbose_name="Fecha Esperada")
    delivery_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Entrega")
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Borrador'),
            ('sent', 'Enviada'),
            ('confirmed', 'Confirmada'),
            ('partial', 'Parcial'),
            ('completed', 'Completada'),
            ('cancelled', 'Cancelada'),
        ],
        default='draft',
        verbose_name="Estado"
    )
    
    # Totales
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal"
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Valor Impuestos"
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Total"
    )
    
    # Usuario que creó la orden
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name="Creado por"
    )
    
    # Observaciones
    notes = models.TextField(blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        db_table = 'purchases_purchase_order'
        unique_together = [['company', 'order_number']]
        indexes = [
            models.Index(fields=['order_date']),
            models.Index(fields=['status']),
            models.Index(fields=['supplier']),
        ]
    
    def __str__(self):
        return f"OC {self.order_number} - {self.supplier.name}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Genera el número de orden"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        
        # Obtener último número del día
        last_order = PurchaseOrder.objects.filter(
            company=self.company,
            order_number__startswith=f"OC-{today}"
        ).order_by('-order_number').first()
        
        if last_order:
            last_number = int(last_order.order_number.split('-')[2])
            next_number = last_number + 1
        else:
            next_number = 1
        
        return f"OC-{today}-{next_number:04d}"
    
    def calculate_totals(self):
        """Calcula los totales de la orden"""
        details = self.details.all()
        
        self.subtotal = sum(detail.subtotal for detail in details)
        self.tax_amount = sum(detail.tax_amount for detail in details)
        self.total = self.subtotal + self.tax_amount
        
        self.save()


class PurchaseOrderDetail(BaseModel):
    """Detalles de órdenes de compra"""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='details',
        verbose_name="Orden de Compra"
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.CASCADE,
        verbose_name="Producto"
    )
    
    # Cantidades y precios
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Cantidad"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Costo Unitario"
    )
    
    # Totales
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Subtotal"
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.12'),
        verbose_name="Tarifa Impuesto"
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Valor Impuesto"
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Total"
    )
    
    # Control de recepción
    received_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Cantidad Recibida"
    )
    
    class Meta:
        verbose_name = "Detalle de Orden de Compra"
        verbose_name_plural = "Detalles de Órdenes de Compra"
        db_table = 'purchases_purchase_order_detail'
    
    def __str__(self):
        return f"{self.product.name} - {self.quantity} x {self.unit_cost}"
    
    def save(self, *args, **kwargs):
        self.calculate_amounts()
        super().save(*args, **kwargs)
    
    def calculate_amounts(self):
        """Calcula los montos del detalle"""
        self.subtotal = self.quantity * self.unit_cost
        self.tax_amount = self.subtotal * self.tax_rate
        self.total = self.subtotal + self.tax_amount
    
    @property
    def pending_quantity(self):
        """Cantidad pendiente de recibir"""
        return self.quantity - self.received_quantity


class Purchase(BaseModel):
    """Compras realizadas"""
    
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        verbose_name="Empresa"
    )
    branch = models.ForeignKey(
        'core.Branch',
        on_delete=models.CASCADE,
        verbose_name="Sucursal"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        verbose_name="Proveedor"
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Orden de Compra"
    )
    
    # Número de compra
    purchase_number = models.CharField(max_length=20, verbose_name="Número de Compra")
    
    # Información del documento del proveedor
    supplier_invoice = models.CharField(max_length=50, verbose_name="Factura del Proveedor")
    supplier_authorization = models.CharField(max_length=49, blank=True, verbose_name="Autorización")
    
    # Fechas
    purchase_date = models.DateField(default=timezone.now, verbose_name="Fecha de Compra")
    invoice_date = models.DateField(verbose_name="Fecha de Factura")
    due_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento")
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Borrador'),
            ('received', 'Recibida'),
            ('validated', 'Validada'),
            ('posted', 'Contabilizada'),
            ('cancelled', 'Cancelada'),
        ],
        default='draft',
        verbose_name="Estado"
    )
    
    # Totales
    subtotal_0 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal 0%"
    )
    subtotal_12 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal 12%"
    )
    iva_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Valor IVA"
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Total"
    )
    
    # Usuario que registró la compra
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name="Registrado por"
    )
    
    # Observaciones
    notes = models.TextField(blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        db_table = 'purchases_purchase'
        unique_together = [['company', 'purchase_number']]
        indexes = [
            models.Index(fields=['purchase_date']),
            models.Index(fields=['status']),
            models.Index(fields=['supplier']),
            models.Index(fields=['supplier_invoice']),
        ]
    
    def __str__(self):
        return f"Compra {self.purchase_number} - {self.supplier.name}"
    
    def save(self, *args, **kwargs):
        if not self.purchase_number:
            self.purchase_number = self.generate_purchase_number()
        super().save(*args, **kwargs)
    
    def generate_purchase_number(self):
        """Genera el número de compra"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        
        # Obtener último número del día
        last_purchase = Purchase.objects.filter(
            company=self.company,
            purchase_number__startswith=f"CP-{today}"
        ).order_by('-purchase_number').first()
        
        if last_purchase:
            last_number = int(last_purchase.purchase_number.split('-')[2])
            next_number = last_number + 1
        else:
            next_number = 1
        
        return f"CP-{today}-{next_number:04d}"
    
    def calculate_totals(self):
        """Calcula los totales de la compra"""
        details = self.details.all()
        
        self.subtotal_0 = sum(detail.subtotal for detail in details if detail.tax_rate == 0)
        self.subtotal_12 = sum(detail.subtotal for detail in details if detail.tax_rate == 0.12)
        self.iva_value = sum(detail.tax_amount for detail in details)
        self.total = self.subtotal_0 + self.subtotal_12 + self.iva_value
        
        self.save()


class PurchaseDetail(BaseModel):
    """Detalles de compras"""
    
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name='details',
        verbose_name="Compra"
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.CASCADE,
        verbose_name="Producto"
    )
    
    # Cantidades y precios
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Cantidad"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Costo Unitario"
    )
    
    # Totales
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Subtotal"
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.12'),
        verbose_name="Tarifa Impuesto"
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Valor Impuesto"
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Total"
    )
    
    class Meta:
        verbose_name = "Detalle de Compra"
        verbose_name_plural = "Detalles de Compras"
        db_table = 'purchases_purchase_detail'
    
    def __str__(self):
        return f"{self.product.name} - {self.quantity} x {self.unit_cost}"
    
    def save(self, *args, **kwargs):
        self.calculate_amounts()
        super().save(*args, **kwargs)
    
    def calculate_amounts(self):
        """Calcula los montos del detalle"""
        self.subtotal = self.quantity * self.unit_cost
        self.tax_amount = self.subtotal * self.tax_rate
        self.total = self.subtotal + self.tax_amount


class Expense(BaseModel):
    """Gastos de la empresa"""
    
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        verbose_name="Empresa"
    )
    branch = models.ForeignKey(
        'core.Branch',
        on_delete=models.CASCADE,
        verbose_name="Sucursal"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        verbose_name="Proveedor"
    )
    
    # Número de gasto
    expense_number = models.CharField(max_length=20, verbose_name="Número de Gasto")
    
    # Información del documento
    supplier_invoice = models.CharField(max_length=50, verbose_name="Factura del Proveedor")
    supplier_authorization = models.CharField(max_length=49, blank=True, verbose_name="Autorización")
    
    # Fechas
    expense_date = models.DateField(default=timezone.now, verbose_name="Fecha del Gasto")
    invoice_date = models.DateField(verbose_name="Fecha de Factura")
    due_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento")
    
    # Categoría del gasto
    category = models.CharField(
        max_length=50,
        choices=[
            ('office_supplies', 'Suministros de Oficina'),
            ('utilities', 'Servicios Básicos'),
            ('rent', 'Alquiler'),
            ('maintenance', 'Mantenimiento'),
            ('professional_services', 'Servicios Profesionales'),
            ('transportation', 'Transporte'),
            ('marketing', 'Marketing'),
            ('other', 'Otros'),
        ],
        verbose_name="Categoría"
    )
    
    # Descripción
    description = models.TextField(verbose_name="Descripción")
    
    # Montos
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Subtotal"
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Valor Impuestos"
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Total"
    )
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Borrador'),
            ('approved', 'Aprobado'),
            ('paid', 'Pagado'),
            ('cancelled', 'Cancelado'),
        ],
        default='draft',
        verbose_name="Estado"
    )
    
    # Usuario que registró el gasto
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name="Registrado por"
    )
    
    # Observaciones
    notes = models.TextField(blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        db_table = 'purchases_expense'
        unique_together = [['company', 'expense_number']]
        indexes = [
            models.Index(fields=['expense_date']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['supplier']),
        ]
    
    def __str__(self):
        return f"Gasto {self.expense_number} - {self.description[:50]}"
    
    def save(self, *args, **kwargs):
        if not self.expense_number:
            self.expense_number = self.generate_expense_number()
        super().save(*args, **kwargs)
    
    def generate_expense_number(self):
        """Genera el número de gasto"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        
        # Obtener último número del día
        last_expense = Expense.objects.filter(
            company=self.company,
            expense_number__startswith=f"GS-{today}"
        ).order_by('-expense_number').first()
        
        if last_expense:
            last_number = int(last_expense.expense_number.split('-')[2])
            next_number = last_number + 1
        else:
            next_number = 1
        
        return f"GS-{today}-{next_number:04d}"