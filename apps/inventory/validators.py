from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import re

def validate_sku(value):
    """Valida formato de SKU"""
    if not value:
        raise ValidationError(_('SKU es requerido'))
    
    # SKU debe ser alfanumérico con guiones
    pattern = r'^[A-Z0-9\-]+$'
    if not re.match(pattern, value.upper()):
        raise ValidationError(
            _('SKU debe contener solo letras mayúsculas, números y guiones')
        )
    
    if len(value) < 3 or len(value) > 20:
        raise ValidationError(
            _('SKU debe tener entre 3 y 20 caracteres')
        )

def validate_barcode(value):
    """Valida formato de código de barras"""
    if not value:
        return  # Es opcional
    
    # Código de barras debe ser numérico
    if not value.isdigit():
        raise ValidationError(
            _('Código de barras debe contener solo números')
        )
    
    # Longitudes válidas para códigos de barras
    valid_lengths = [8, 12, 13, 14]  # EAN8, UPC-A, EAN13, GTIN-14
    if len(value) not in valid_lengths:
        raise ValidationError(
            _('Código de barras debe tener 8, 12, 13 o 14 dígitos')
        )
    
    # Validar dígito de verificación para EAN13
    if len(value) == 13:
        if not validate_ean13_check_digit(value):
            raise ValidationError(
                _('Código de barras EAN13 tiene un dígito de verificación inválido')
            )

def validate_ean13_check_digit(barcode):
    """Valida dígito de verificación EAN13"""
    if len(barcode) != 13:
        return False
    
    try:
        # Calcular dígito de verificación
        odd_sum = sum(int(barcode[i]) for i in range(0, 12, 2))
        even_sum = sum(int(barcode[i]) for i in range(1, 12, 2))
        
        total = odd_sum + (even_sum * 3)
        check_digit = (10 - (total % 10)) % 10
        
        return str(check_digit) == barcode[12]
    except (ValueError, IndexError):
        return False

def validate_price(value):
    """Valida que el precio sea positivo"""
    if value is None:
        raise ValidationError(_('Precio es requerido'))
    
    if value < 0:
        raise ValidationError(_('Precio no puede ser negativo'))
    
    if value == 0:
        raise ValidationError(_('Precio debe ser mayor a cero'))
    
    # Validar máximo 2 decimales
    decimal_value = Decimal(str(value))
    if decimal_value.as_tuple().exponent < -2:
        raise ValidationError(_('Precio no puede tener más de 2 decimales'))

def validate_cost_price(value):
    """Valida precio de costo"""
    validate_price(value)
    
    # Precio de costo no puede ser excesivamente alto
    if value > 999999.99:
        raise ValidationError(_('Precio de costo no puede exceder $999,999.99'))

def validate_sale_price(value):
    """Valida precio de venta"""
    validate_price(value)
    
    # Precio de venta no puede ser excesivamente alto
    if value > 999999.99:
        raise ValidationError(_('Precio de venta no puede exceder $999,999.99'))

def validate_profit_percentage(value):
    """Valida porcentaje de ganancia"""
    if value is None:
        return  # Es opcional
    
    if value < 0:
        raise ValidationError(_('Porcentaje de ganancia no puede ser negativo'))
    
    if value > 1000:
        raise ValidationError(_('Porcentaje de ganancia no puede exceder 1000%'))

def validate_stock_quantity(value):
    """Valida cantidad de stock"""
    if value is None:
        raise ValidationError(_('Cantidad es requerida'))
    
    if not isinstance(value, int):
        raise ValidationError(_('Cantidad debe ser un número entero'))
    
    if value < 0:
        raise ValidationError(_('Cantidad no puede ser negativa'))
    
    if value > 999999:
        raise ValidationError(_('Cantidad no puede exceder 999,999'))

def validate_min_max_stock(min_stock, max_stock):
    """Valida que el stock mínimo sea menor al máximo"""
    if min_stock is not None and max_stock is not None:
        if min_stock >= max_stock:
            raise ValidationError(
                _('Stock mínimo debe ser menor al stock máximo')
            )
        
        if min_stock < 0:
            raise ValidationError(_('Stock mínimo no puede ser negativo'))
        
        if max_stock <= 0:
            raise ValidationError(_('Stock máximo debe ser mayor a cero'))

def validate_weight(value):
    """Valida peso del producto"""
    if value is None:
        return  # Es opcional
    
    if value <= 0:
        raise ValidationError(_('Peso debe ser mayor a cero'))
    
    if value > 99999.999:
        raise ValidationError(_('Peso no puede exceder 99,999.999'))

def validate_dimensions(value):
    """Valida formato de dimensiones"""
    if not value:
        return  # Es opcional
    
    # Formato esperado: "largo x ancho x alto" o similar
    pattern = r'^\d+(\.\d+)?\s*x\s*\d+(\.\d+)?\s*x\s*\d+(\.\d+)?(\s*(cm|mm|m|in))?$'
    if not re.match(pattern, value.lower()):
        raise ValidationError(
            _('Formato de dimensiones inválido. Use: "largo x ancho x alto" (ej: "10 x 5 x 2 cm")')
        )

def validate_ruc_ecuador(value):
    """Valida RUC ecuatoriano"""
    if not value:
        raise ValidationError(_('RUC es requerido'))
    
    # RUC debe tener 13 dígitos
    if len(value) != 13:
        raise ValidationError(_('RUC debe tener 13 dígitos'))
    
    if not value.isdigit():
        raise ValidationError(_('RUC debe contener solo números'))
    
    # Validar provincia (primeros 2 dígitos)
    provincia = int(value[:2])
    if provincia < 1 or provincia > 24:
        raise ValidationError(_('Código de provincia inválido en RUC'))
    
    # Validar tercer dígito
    tercer_digito = int(value[2])
    if tercer_digito > 9:
        raise ValidationError(_('Tercer dígito de RUC inválido'))
    
    # Validar dígito verificador según tipo de RUC
    if tercer_digito < 6:  # Persona natural
        if not validate_ruc_persona_natural(value):
            raise ValidationError(_('RUC de persona natural inválido'))
    elif tercer_digito == 6:  # Sociedad pública
        if not validate_ruc_sociedad_publica(value):
            raise ValidationError(_('RUC de sociedad pública inválido'))
    elif tercer_digito == 9:  # Sociedad privada
        if not validate_ruc_sociedad_privada(value):
            raise ValidationError(_('RUC de sociedad privada inválido'))
    else:
        raise ValidationError(_('Tipo de RUC no válido'))

def validate_ruc_persona_natural(ruc):
    """Valida RUC de persona natural"""
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    
    for i in range(9):
        producto = int(ruc[i]) * coeficientes[i]
        if producto > 9:
            producto = int(str(producto)[0]) + int(str(producto)[1])
        suma += producto
    
    resto = suma % 10
    digito_verificador = 10 - resto if resto != 0 else 0
    
    return digito_verificador == int(ruc[9])

def validate_ruc_sociedad_publica(ruc):
    """Valida RUC de sociedad pública"""
    coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
    suma = 0
    
    for i in range(8):
        suma += int(ruc[i]) * coeficientes[i]
    
    resto = suma % 11
    digito_verificador = 11 - resto if resto != 0 else 0
    
    return digito_verificador == int(ruc[8])

def validate_ruc_sociedad_privada(ruc):
    """Valida RUC de sociedad privada"""
    coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = 0
    
    for i in range(9):
        suma += int(ruc[i]) * coeficientes[i]
    
    resto = suma % 11
    digito_verificador = 11 - resto if resto != 0 else 0
    
    return digito_verificador == int(ruc[9])

def validate_product_name(value):
    """Valida nombre de producto"""
    if not value:
        raise ValidationError(_('Nombre de producto es requerido'))
    
    if len(value.strip()) < 2:
        raise ValidationError(_('Nombre de producto debe tener al menos 2 caracteres'))
    
    if len(value) > 200:
        raise ValidationError(_('Nombre de producto no puede exceder 200 caracteres'))
    
    # No permitir solo números
    if value.strip().isdigit():
        raise ValidationError(_('Nombre de producto no puede ser solo números'))

def validate_category_profit_percentage(value):
    """Valida porcentaje de ganancia de categoría"""
    if value is None:
        return  # Es opcional
    
    if value < 0:
        raise ValidationError(_('Porcentaje de ganancia no puede ser negativo'))
    
    if value > 1000:
        raise ValidationError(_('Porcentaje de ganancia no puede exceder 1000%'))
    
    # Advertir si es muy alto
    if value > 500:
        raise ValidationError(_('Porcentaje de ganancia muy alto, verifique el valor'))

class ProductValidator:
    """Validador integral para productos"""
    
    @staticmethod
    def validate_product_data(data):
        """Valida todos los datos de un producto"""
        errors = {}
        
        # Validar nombre
        try:
            validate_product_name(data.get('name'))
        except ValidationError as e:
            errors['name'] = e.messages
        
        # Validar SKU
        try:
            validate_sku(data.get('sku'))
        except ValidationError as e:
            errors['sku'] = e.messages
        
        # Validar código de barras
        try:
            validate_barcode(data.get('barcode'))
        except ValidationError as e:
            errors['barcode'] = e.messages
        
        # Validar precios
        cost_price = data.get('cost_price')
        sale_price = data.get('sale_price')
        
        try:
            validate_cost_price(cost_price)
        except ValidationError as e:
            errors['cost_price'] = e.messages
        
        try:
            validate_sale_price(sale_price)
        except ValidationError as e:
            errors['sale_price'] = e.messages
        
        # Validar que precio de venta sea mayor al de costo
        if cost_price and sale_price:
            if sale_price <= cost_price:
                errors['sale_price'] = [_('Precio de venta debe ser mayor al precio de costo')]
        
        # Validar stock
        min_stock = data.get('min_stock')
        max_stock = data.get('max_stock')
        
        try:
            validate_min_max_stock(min_stock, max_stock)
        except ValidationError as e:
            errors['max_stock'] = e.messages
        
        # Validar peso
        try:
            validate_weight(data.get('weight'))
        except ValidationError as e:
            errors['weight'] = e.messages
        
        # Validar dimensiones
        try:
            validate_dimensions(data.get('dimensions'))
        except ValidationError as e:
            errors['dimensions'] = e.messages
        
        return errors

class SupplierValidator:
    """Validador para proveedores"""
    
    @staticmethod
    def validate_supplier_data(data):
        """Valida datos de proveedor"""
        errors = {}
        
        # Validar RUC
        try:
            validate_ruc_ecuador(data.get('ruc'))
        except ValidationError as e:
            errors['ruc'] = e.messages
        
        # Validar nombre
        name = data.get('name')
        if not name or len(name.strip()) < 2:
            errors['name'] = [_('Nombre de proveedor es requerido y debe tener al menos 2 caracteres')]
        
        # Validar email si se proporciona
        email = data.get('email')
        if email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                errors['email'] = [_('Email no tiene un formato válido')]
        
        return errors