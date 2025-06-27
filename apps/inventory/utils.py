import uuid
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.core.files.base import ContentFile
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
import barcode
from barcode.writer import ImageWriter
import pandas as pd
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class InventoryUtils:
    """Utilidades generales para inventario"""
    
    @staticmethod
    def generate_sku(category=None, brand=None):
        """Genera un SKU único para productos"""
        prefix = "PRD"
        
        if category:
            prefix = category.name[:3].upper()
        elif brand:
            prefix = brand.name[:3].upper()
        
        # Eliminar caracteres especiales del prefix
        prefix = ''.join(e for e in prefix if e.isalnum())
        
        # Generar ID único
        unique_id = str(uuid.uuid4())[:8].upper()
        
        return f"{prefix}-{unique_id}"
    
    @staticmethod
    def generate_barcode_number():
        """Genera un número de código de barras único"""
        import time
        import random
        
        # Usar timestamp + número aleatorio para garantizar unicidad
        timestamp = str(int(time.time()))[-10:]  # Últimos 10 dígitos del timestamp
        random_part = str(random.randint(10, 99))
        
        # Crear código de 12 dígitos para EAN13
        code = f"78{timestamp}{random_part}"
        
        # Calcular dígito de verificación para EAN13
        check_digit = BarcodeUtils.calculate_ean13_check_digit(code)
        
        return f"{code}{check_digit}"
    
    @staticmethod
    def calculate_profit(cost_price, sale_price):
        """Calcula ganancia y porcentaje de ganancia"""
        if not cost_price or not sale_price:
            return {'amount': 0, 'percentage': 0}
        
        cost = Decimal(str(cost_price))
        sale = Decimal(str(sale_price))
        
        profit_amount = sale - cost
        profit_percentage = (profit_amount / cost * 100) if cost > 0 else 0
        
        return {
            'amount': profit_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'percentage': profit_percentage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        }
    
    @staticmethod
    def apply_category_profit(cost_price, category):
        """Aplica el porcentaje de ganancia de la categoría"""
        if not cost_price or not category or not category.profit_percentage:
            return cost_price
        
        cost = Decimal(str(cost_price))
        percentage = Decimal(str(category.profit_percentage))
        
        profit_amount = cost * (percentage / 100)
        sale_price = cost + profit_amount
        
        return sale_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def format_currency(amount):
        """Formatea cantidad como moneda"""
        if not amount:
            return "$0.00"
        
        return f"${amount:,.2f}"
    
    @staticmethod
    def validate_ruc(ruc):
        """Valida formato de RUC ecuatoriano"""
        if not ruc or len(ruc) != 13:
            return False
        
        if not ruc.isdigit():
            return False
        
        # Validación específica para RUC Ecuador
        provincia = int(ruc[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        tercer_digito = int(ruc[2])
        if tercer_digito < 0 or tercer_digito > 9:
            return False
        
        return True

class BarcodeUtils:
    """Utilidades para códigos de barras"""
    
    @staticmethod
    def calculate_ean13_check_digit(code):
        """Calcula el dígito de verificación para EAN13"""
        if len(code) != 12:
            raise ValueError("El código debe tener 12 dígitos")
        
        odd_sum = sum(int(code[i]) for i in range(0, 12, 2))
        even_sum = sum(int(code[i]) for i in range(1, 12, 2))
        
        total = odd_sum + (even_sum * 3)
        check_digit = (10 - (total % 10)) % 10
        
        return str(check_digit)
    
    @staticmethod
    def generate_barcode_image(code, format='PNG', size=(300, 100)):
        """Genera imagen de código de barras"""
        try:
            # Determinar tipo de código de barras
            if len(code) == 13:
                code_class = barcode.get('ean13')
            elif len(code) == 12:
                # Agregar dígito de verificación
                check_digit = BarcodeUtils.calculate_ean13_check_digit(code)
                code = f"{code}{check_digit}"
                code_class = barcode.get('ean13')
            else:
                code_class = barcode.get('code128')
            
            # Generar código de barras
            barcode_instance = code_class(code, writer=ImageWriter())
            
            # Configurar opciones del writer
            options = {
                'module_width': 0.2,
                'module_height': 15,
                'quiet_zone': 6.5,
                'font_size': 10,
                'text_distance': 5,
                'background': 'white',
                'foreground': 'black',
            }
            
            buffer = BytesIO()
            barcode_instance.write(buffer, options)
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generando código de barras: {e}")
            raise
    
    @staticmethod
    def generate_qr_code(data, size=(200, 200)):
        """Genera código QR"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Redimensionar si es necesario
            if size != img.size:
                img = img.resize(size, Image.LANCZOS)
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generando código QR: {e}")
            raise

class ExportUtils:
    """Utilidades para exportación de datos"""
    
    @staticmethod
    def export_products_to_excel(products, include_stock=True):
        """Exporta productos a Excel"""
        data = []
        
        for product in products:
            row = {
                'SKU': product.sku,
                'Código de Barras': product.barcode,
                'Nombre': product.name,
                'Descripción': product.description,
                'Categoría': product.category.name if product.category else '',
                'Marca': product.brand.name if product.brand else '',
                'Proveedor': product.supplier.name if product.supplier else '',
                'Precio Costo': float(product.cost_price),
                'Precio Venta': float(product.sale_price),
                'Ganancia $': float(product.profit_amount),
                'Ganancia %': float(product.profit_percentage),
                'Unidad': product.get_unit_display(),
                'Peso': float(product.weight) if product.weight else '',
                'Dimensiones': product.dimensions,
                'Stock Mínimo': product.min_stock,
                'Stock Máximo': product.max_stock,
                'Controla Stock': 'Sí' if product.track_stock else 'No',
                'Activo': 'Sí' if product.is_active else 'No',
                'Para Venta': 'Sí' if product.is_for_sale else 'No',
                'Fecha Creación': product.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            if include_stock:
                row['Stock Actual'] = product.current_stock
                row['Estado Stock'] = 'Sin stock' if product.is_out_of_stock else 'Stock bajo' if product.is_low_stock else 'Normal'
            
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Crear buffer en memoria
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Productos', index=False)
            
            # Ajustar ancho de columnas
            worksheet = writer.sheets['Productos']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def export_stock_movements_to_excel(movements):
        """Exporta movimientos de stock a Excel"""
        data = []
        
        for movement in movements:
            data.append({
                'Fecha': movement.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Producto': movement.product.name,
                'SKU': movement.product.sku,
                'Tipo Movimiento': movement.get_movement_type_display(),
                'Motivo': movement.get_reason_display(),
                'Cantidad': movement.quantity,
                'Costo Unitario': float(movement.unit_cost) if movement.unit_cost else '',
                'Costo Total': float(movement.total_cost) if movement.total_cost else '',
                'Documento Referencia': movement.reference_document,
                'Usuario': movement.user.get_full_name() or movement.user.username,
                'Notas': movement.notes,
            })
        
        df = pd.DataFrame(data)
        
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Movimientos', index=False)
        
        buffer.seek(0)
        return buffer

class ImportUtils:
    """Utilidades para importación de datos"""
    
    @staticmethod
    def validate_import_file(file):
        """Valida archivo de importación"""
        errors = []
        
        # Validar extensión
        if not file.name.lower().endswith(('.xlsx', '.xls', '.csv')):
            errors.append("Formato de archivo no válido. Use Excel (.xlsx, .xls) o CSV (.csv)")
            return errors
        
        # Validar tamaño (máximo 10MB)
        if file.size > 10 * 1024 * 1024:
            errors.append("El archivo es demasiado grande. Máximo 10MB permitido.")
        
        return errors
    
    @staticmethod
    def parse_import_file(file):
        """Parsea archivo de importación"""
        try:
            if file.name.lower().endswith('.csv'):
                df = pd.read_csv(file, encoding='utf-8')
            else:
                df = pd.read_excel(file)
            
            # Normalizar nombres de columnas
            df.columns = df.columns.str.lower().str.strip()
            df.columns = df.columns.str.replace(' ', '_')
            df.columns = df.columns.str.replace('ó', 'o')
            df.columns = df.columns.str.replace('ú', 'u')
            df.columns = df.columns.str.replace('í', 'i')
            df.columns = df.columns.str.replace('á', 'a')
            df.columns = df.columns.str.replace('é', 'e')
            
            return df
            
        except Exception as e:
            raise ValueError(f"Error leyendo archivo: {str(e)}")
    
    @staticmethod
    def validate_import_data(df):
        """Valida datos de importación"""
        errors = []
        required_columns = ['nombre', 'categoria', 'marca', 'proveedor', 'precio_costo']
        
        # Verificar columnas requeridas
        missing_columns = []
        for col in required_columns:
            if col not in df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            errors.append(f"Columnas faltantes: {', '.join(missing_columns)}")
        
        # Validar datos por fila
        for index, row in df.iterrows():
            row_errors = []
            
            # Validar campos obligatorios
            for col in required_columns:
                if col in df.columns and (pd.isna(row[col]) or str(row[col]).strip() == ''):
                    row_errors.append(f"Campo '{col}' es obligatorio")
            
            # Validar precio_costo numérico
            if 'precio_costo' in df.columns:
                try:
                    float(row['precio_costo'])
                except (ValueError, TypeError):
                    if not pd.isna(row['precio_costo']):
                        row_errors.append("Precio de costo debe ser numérico")
            
            # Validar precio_venta si existe
            if 'precio_venta' in df.columns and not pd.isna(row['precio_venta']):
                try:
                    float(row['precio_venta'])
                except (ValueError, TypeError):
                    row_errors.append("Precio de venta debe ser numérico")
            
            if row_errors:
                errors.append(f"Fila {index + 2}: {'; '.join(row_errors)}")
        
        return errors

class StockUtils:
    """Utilidades para manejo de stock"""
    
    @staticmethod
    def calculate_stock_value(products):
        """Calcula el valor total del stock"""
        total_value = Decimal('0')
        
        for product in products:
            if product.track_stock:
                stock_value = product.current_stock * product.cost_price
                total_value += stock_value
        
        return total_value
    
    @staticmethod
    def get_stock_summary(products):
        """Obtiene resumen de stock"""
        summary = {
            'total_products': 0,
            'products_with_stock': 0,
            'products_low_stock': 0,
            'products_out_of_stock': 0,
            'total_stock_value': Decimal('0'),
            'average_stock_level': 0
        }
        
        stock_levels = []
        
        for product in products:
            summary['total_products'] += 1
            
            if product.track_stock:
                current_stock = product.current_stock
                
                if current_stock > 0:
                    summary['products_with_stock'] += 1
                    stock_levels.append(current_stock)
                    
                    # Valor del stock
                    stock_value = current_stock * product.cost_price
                    summary['total_stock_value'] += stock_value
                
                if current_stock <= 0:
                    summary['products_out_of_stock'] += 1
                elif current_stock <= product.min_stock:
                    summary['products_low_stock'] += 1
        
        # Calcular nivel promedio de stock
        if stock_levels:
            summary['average_stock_level'] = sum(stock_levels) / len(stock_levels)
        
        return summary

class PricingUtils:
    """Utilidades para cálculos de precios"""
    
    @staticmethod
    def calculate_sale_price_with_margin(cost_price, margin_percentage):
        """Calcula precio de venta con margen de ganancia"""
        if not cost_price or not margin_percentage:
            return cost_price
        
        cost = Decimal(str(cost_price))
        margin = Decimal(str(margin_percentage))
        
        margin_amount = cost * (margin / 100)
        sale_price = cost + margin_amount
        
        return sale_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_margin_from_prices(cost_price, sale_price):
        """Calcula margen de ganancia a partir de precios"""
        if not cost_price or not sale_price or cost_price <= 0:
            return 0
        
        cost = Decimal(str(cost_price))
        sale = Decimal(str(sale_price))
        
        margin = ((sale - cost) / cost) * 100
        
        return margin.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def suggest_sale_price(cost_price, category=None, competitor_prices=None):
        """Sugiere precio de venta basado en diferentes factores"""
        if not cost_price:
            return cost_price
        
        suggestions = []
        
        # Sugerencia basada en categoría
        if category and category.profit_percentage:
            category_price = PricingUtils.calculate_sale_price_with_margin(
                cost_price, category.profit_percentage
            )
            suggestions.append({
                'method': 'Categoría',
                'price': category_price,
                'margin': category.profit_percentage
            })
        
        # Sugerencias estándar de márgenes
        standard_margins = [25, 50, 75, 100]
        for margin in standard_margins:
            price = PricingUtils.calculate_sale_price_with_margin(cost_price, margin)
            suggestions.append({
                'method': f'Margen {margin}%',
                'price': price,
                'margin': margin
            })
        
        # Sugerencia basada en precios competencia
        if competitor_prices:
            avg_competitor = sum(competitor_prices) / len(competitor_prices)
            margin = PricingUtils.calculate_margin_from_prices(cost_price, avg_competitor)
            suggestions.append({
                'method': 'Competencia',
                'price': Decimal(str(avg_competitor)),
                'margin': margin
            })
        
        return suggestions