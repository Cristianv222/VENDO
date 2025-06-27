from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import (
    Brand, Category, Supplier, Product, StockMovement, 
    StockAlert, ProductImage
)
from .validators import (
    validate_sku, validate_barcode, validate_price, 
    validate_cost_price, validate_sale_price, validate_ruc_ecuador,
    validate_min_max_stock, ProductValidator, SupplierValidator
)
from decimal import Decimal

class BrandForm(forms.ModelForm):
    """Formulario para marcas"""
    
    class Meta:
        model = Brand
        fields = ['name', 'description', 'logo', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la marca'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la marca'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            # Verificar que no exista otra marca con el mismo nombre
            qs = Brand.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ya existe una marca con este nombre.")
        return name

class CategoryForm(forms.ModelForm):
    """Formulario para categorías"""
    
    class Meta:
        model = Category
        fields = ['name', 'parent', 'description', 'profit_percentage', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la categoría'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la categoría'
            }),
            'profit_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '1000',
                'placeholder': 'Porcentaje de ganancia (%)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Evitar que una categoría sea padre de sí misma
        if self.instance.pk:
            self.fields['parent'].queryset = Category.objects.filter(
                is_active=True
            ).exclude(pk=self.instance.pk)
        else:
            self.fields['parent'].queryset = Category.objects.filter(is_active=True)
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        parent = self.cleaned_data.get('parent')
        
        if name:
            name = name.strip()
            # Verificar que no exista otra categoría con el mismo nombre en el mismo nivel
            qs = Category.objects.filter(name__iexact=name, parent=parent)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ya existe una categoría con este nombre en este nivel.")
        return name
    
    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get('parent')
        
        # Verificar que no se cree una referencia circular
        if parent and self.instance.pk:
            current = parent
            while current.parent:
                if current.parent.pk == self.instance.pk:
                    raise ValidationError("No se puede crear una referencia circular en las categorías.")
                current = current.parent
        
        return cleaned_data

class SupplierForm(forms.ModelForm):
    """Formulario para proveedores"""
    
    class Meta:
        model = Supplier
        fields = [
            'name', 'ruc', 'email', 'phone', 'address', 
            'contact_person', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del proveedor'
            }),
            'ruc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '1234567890123',
                'maxlength': '13'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@ejemplo.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+593 99 999 9999'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección del proveedor'
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Persona de contacto'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def clean_ruc(self):
        ruc = self.cleaned_data.get('ruc')
        if ruc:
            ruc = ruc.strip()
            validate_ruc_ecuador(ruc)
            
            # Verificar que no exista otro proveedor con el mismo RUC
            qs = Supplier.objects.filter(ruc=ruc)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ya existe un proveedor con este RUC.")
        return ruc
    
    def clean(self):
        cleaned_data = super().clean()
        errors = SupplierValidator.validate_supplier_data(cleaned_data)
        
        for field, field_errors in errors.items():
            for error in field_errors:
                self.add_error(field, error)
        
        return cleaned_data

class ProductForm(forms.ModelForm):
    """Formulario para productos"""
    
    initial_stock = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Stock inicial (opcional)'
        }),
        help_text="Stock inicial del producto"
    )
    
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'category', 'brand', 'supplier',
            'cost_price', 'sale_price', 'unit', 'weight', 'dimensions',
            'image', 'track_stock', 'min_stock', 'max_stock', 'is_active', 'is_for_sale'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del producto'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción del producto'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'loadCategoryProfit(this.value)'
            }),
            'brand': forms.Select(attrs={
                'class': 'form-select'
            }),
            'supplier': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'onchange': 'calculateSalePrice()'
            }),
            'sale_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'unit': forms.Select(attrs={
                'class': 'form-select'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0',
                'placeholder': '0.000'
            }),
            'dimensions': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 10 x 5 x 2 cm'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'track_stock': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleStockFields()'
            }),
            'min_stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'max_stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_for_sale': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo registros activos
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['brand'].queryset = Brand.objects.filter(is_active=True)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            # Verificar que no exista otro producto con el mismo nombre
            qs = Product.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ya existe un producto con este nombre.")
        return name
    
    def clean_cost_price(self):
        cost_price = self.cleaned_data.get('cost_price')
        if cost_price is not None:
            validate_cost_price(cost_price)
        return cost_price
    
    def clean_sale_price(self):
        sale_price = self.cleaned_data.get('sale_price')
        if sale_price is not None:
            validate_sale_price(sale_price)
        return sale_price
    
    def clean(self):
        cleaned_data = super().clean()
        cost_price = cleaned_data.get('cost_price')
        sale_price = cleaned_data.get('sale_price')
        min_stock = cleaned_data.get('min_stock')
        max_stock = cleaned_data.get('max_stock')
        track_stock = cleaned_data.get('track_stock')
        
        # Validar que precio de venta sea mayor al de costo
        if cost_price and sale_price:
            if sale_price <= cost_price:
                self.add_error('sale_price', 'El precio de venta debe ser mayor al precio de costo.')
        
        # Validar stock mínimo y máximo si se controla stock
        if track_stock:
            try:
                validate_min_max_stock(min_stock, max_stock)
            except ValidationError as e:
                self.add_error('max_stock', e.message)
        
        # Si no se especifica precio de venta, calcularlo automáticamente
        category = cleaned_data.get('category')
        if cost_price and category and category.profit_percentage and not sale_price:
            profit_amount = cost_price * (category.profit_percentage / 100)
            cleaned_data['sale_price'] = cost_price + profit_amount
        
        return cleaned_data

class ProductSearchForm(forms.Form):
    """Formulario para búsqueda de productos"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre, SKU o código de barras...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="Todas las categorías",
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    brand = forms.ModelChoiceField(
        queryset=Brand.objects.filter(is_active=True),
        required=False,
        empty_label="Todas las marcas",
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label="Todos los proveedores",
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    stock_status = forms.ChoiceField(
        choices=[
            ('', 'Todos'),
            ('low_stock', 'Stock bajo'),
            ('out_of_stock', 'Sin stock'),
            ('normal', 'Stock normal')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    is_active = forms.ChoiceField(
        choices=[
            ('', 'Todos'),
            ('true', 'Activos'),
            ('false', 'Inactivos')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

class StockMovementForm(forms.ModelForm):
    """Formulario para movimientos de stock"""
    
    class Meta:
        model = StockMovement
        fields = [
            'product', 'movement_type', 'reason', 'quantity',
            'unit_cost', 'reference_document', 'notes'
        ]
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'updateProductInfo()'
            }),
            'movement_type': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'updateQuantityField()'
            }),
            'reason': forms.Select(attrs={
                'class': 'form-select'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Cantidad'
            }),
            'unit_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'reference_document': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de factura, orden, etc.'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas adicionales'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo productos activos que controlan stock
        self.fields['product'].queryset = Product.objects.filter(
            is_active=True, track_stock=True
        )
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        movement_type = self.cleaned_data.get('movement_type')
        product = self.cleaned_data.get('product')
        
        if quantity is not None and quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero.")
        
        # Validar stock disponible para salidas
        if movement_type == 'OUT' and product and quantity:
            current_stock = product.current_stock
            if quantity > current_stock:
                raise ValidationError(
                    f"No hay suficiente stock. Stock actual: {current_stock}"
                )
        
        return quantity
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Ajustar cantidad según tipo de movimiento
        if instance.movement_type == 'OUT':
            instance.quantity = -abs(instance.quantity)
        else:
            instance.quantity = abs(instance.quantity)
        
        if commit:
            instance.save()
        
        return instance

class QuickStockMovementForm(forms.Form):
    """Formulario rápido para movimientos de stock"""
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True, track_stock=True),
        widget=forms.HiddenInput()
    )
    
    movement_type = forms.ChoiceField(
        choices=StockMovement.MOVEMENT_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    reason = forms.ChoiceField(
        choices=StockMovement.MOVEMENT_REASONS,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cantidad'
        })
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Notas (opcional)'
        })
    )

class ProductImageForm(forms.ModelForm):
    """Formulario para imágenes de productos"""
    
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_main', 'order']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'alt_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descripción de la imagen'
            }),
            'is_main': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            })
        }

class ProductImportForm(forms.Form):
    """Formulario para importación de productos"""
    
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls,.csv'
        }),
        help_text="Formatos permitidos: Excel (.xlsx, .xls) o CSV (.csv). Máximo 10MB."
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Actualizar productos existentes si se encuentra el mismo SKU"
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if file:
            # Validar extensión
            if not file.name.lower().endswith(('.xlsx', '.xls', '.csv')):
                raise ValidationError(
                    "Formato de archivo no válido. Use Excel (.xlsx, .xls) o CSV (.csv)"
                )
            
            # Validar tamaño (máximo 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("El archivo es demasiado grande. Máximo 10MB permitido.")
        
        return file

class BarcodeGenerationForm(forms.Form):
    """Formulario para generación de códigos de barras"""
    
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        help_text="Seleccione los productos para generar códigos de barras"
    )
    
    format = forms.ChoiceField(
        choices=[
            ('pdf', 'PDF para impresión'),
            ('png', 'Imágenes PNG (ZIP)')
        ],
        initial='pdf',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    size = forms.ChoiceField(
        choices=[
            ('small', 'Pequeño (40x20mm)'),
            ('medium', 'Mediano (60x30mm)'),
            ('large', 'Grande (80x40mm)')
        ],
        initial='medium',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

class StockAlertResolveForm(forms.Form):
    """Formulario para resolver alertas de stock"""
    
    alert_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    resolution_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notas sobre la resolución (opcional)'
        })
    )

class CategoryProfitUpdateForm(forms.Form):
    """Formulario para actualizar porcentajes de ganancia de categorías"""
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    new_profit_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=1000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Nuevo porcentaje de ganancia'
        })
    )
    
    update_existing_products = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Actualizar precios de productos existentes en esta categoría"
    )

# FormSet para múltiples imágenes de productos
ProductImageFormSet = forms.inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    extra=3,
    can_delete=True,
    fields=['image', 'alt_text', 'is_main', 'order']
)