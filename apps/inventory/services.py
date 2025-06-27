from django.db import transaction, models
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from .models import Product, StockMovement, StockAlert, Category, Brand, Supplier
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import mm
import tempfile
import os
import platform
import serial
import serial.tools.list_ports
import subprocess
import time
import random
import logging

logger = logging.getLogger(__name__)

class ZebraPrinterService:
    """Servicio para imprimir códigos de barras en impresoras Zebra USB"""
    
    def __init__(self, port=None, baudrate=9600):
        # Configuración por defecto para conexión USB
        self.port = port or getattr(settings, 'ZEBRA_USB_PORT', None)
        self.baudrate = baudrate or getattr(settings, 'ZEBRA_BAUDRATE', 9600)
        self.timeout = getattr(settings, 'ZEBRA_TIMEOUT', 5)
        
        # Nombre de la impresora en Windows (si está instalada como impresora del sistema)
        self.printer_name = getattr(settings, 'ZEBRA_PRINTER_NAME', 'ZDesigner')
    
    def find_zebra_port(self):
        """
        Busca automáticamente el puerto USB de la impresora Zebra
        """
        try:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                # Buscar puertos que contengan "Zebra" en la descripción
                if any(keyword in port.description.upper() for keyword in ['ZEBRA', 'ZDESIGNER']):
                    logger.info(f"Impresora Zebra encontrada en puerto: {port.device}")
                    return port.device
            
            # Si no encuentra por descripción, listar todos los puertos disponibles
            available_ports = [port.device for port in ports]
            logger.warning(f"No se encontró impresora Zebra automáticamente. Puertos disponibles: {available_ports}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error buscando puerto Zebra: {str(e)}")
            return None
    
    def generate_zpl_barcode(self, barcode, product_name="", sale_price="", copies=1):
        """
        Genera código ZPL para imprimir código de barras en Zebra
        """
        # Truncar nombre del producto si es muy largo
        if len(product_name) > 25:
            product_name = product_name[:22] + "..."
        
        # Formatear precio
        if sale_price:
            try:
                price_formatted = f"${float(sale_price):.2f}"
            except:
                price_formatted = f"${sale_price}"
        else:
            price_formatted = ""
        
        # Código ZPL para etiqueta de producto con código de barras
        zpl_code = f"""
^XA
^MMT
^PW320
^LL0240
^LS0

^FT15,45^A0N,25,25^FH\^FD{product_name}^FS
^FT15,75^A0N,20,20^FH\^FD{price_formatted}^FS

^FT15,120^BY2,3,80^BCN,,Y,N
^FD{barcode}^FS

^FT15,220^A0N,15,15^FH\^FD{barcode}^FS

^PQ{copies},0,1,Y
^XZ
"""
        return zpl_code.strip()
    
    def send_via_serial(self, zpl_code):
        """
        Envía código ZPL a la impresora vía puerto serial USB
        """
        try:
            # Usar puerto configurado o buscar automáticamente
            port = self.port or self.find_zebra_port()
            
            if not port:
                return False, "No se pudo encontrar la impresora Zebra. Verifique que esté conectada y los drivers instalados."
            
            # Abrir conexión serial
            with serial.Serial(port, self.baudrate, timeout=self.timeout) as ser:
                # Enviar código ZPL
                ser.write(zpl_code.encode('utf-8'))
                ser.flush()
                
                logger.info(f"Código de barras enviado exitosamente al puerto {port}")
                return True, f"Impresión enviada exitosamente al puerto {port}"
                
        except serial.SerialException as e:
            error_msg = f"Error de conexión serial: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Error inesperado al imprimir vía serial: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def send_via_windows_printer(self, zpl_code):
        """
        Envía código ZPL usando el spooler de Windows (si la impresora está instalada)
        """
        try:
            if platform.system() != 'Windows':
                return False, "El método de impresión por Windows solo funciona en sistemas Windows"
            
            # Crear archivo temporal con el código ZPL
            with tempfile.NamedTemporaryFile(mode='w', suffix='.zpl', delete=False) as temp_file:
                temp_file.write(zpl_code)
                temp_path = temp_file.name
            
            try:
                # Enviar archivo a la impresora usando copy en Windows
                # Esto funciona si la impresora está instalada como impresora de sistema
                result = subprocess.run([
                    'copy', temp_path, f'{self.printer_name}:'
                ], shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Código de barras enviado exitosamente a {self.printer_name}")
                    return True, f"Impresión enviada exitosamente a {self.printer_name}"
                else:
                    error_msg = f"Error enviando a impresora: {result.stderr}"
                    logger.error(error_msg)
                    return False, error_msg
                    
            finally:
                # Limpiar archivo temporal
                os.unlink(temp_path)
                
        except Exception as e:
            error_msg = f"Error en impresión por Windows: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def send_via_lpr(self, zpl_code):
        """
        Envía código ZPL usando lpr en sistemas Unix/Linux
        """
        try:
            if platform.system() == 'Windows':
                return False, "El método lpr no está disponible en Windows"
            
            # Intentar enviar usando lpr
            process = subprocess.Popen(
                ['lpr', '-P', self.printer_name, '-l'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = process.communicate(input=zpl_code.encode('utf-8'))
            
            if process.returncode == 0:
                logger.info(f"Código de barras enviado exitosamente vía lpr")
                return True, "Impresión enviada exitosamente vía lpr"
            else:
                error_msg = f"Error en lpr: {stderr.decode()}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error en impresión vía lpr: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def print_barcode(self, barcode, product_name="", sale_price="", copies=1):
        """
        Método principal para imprimir código de barras
        Intenta diferentes métodos en orden de preferencia
        """
        try:
            # Generar código ZPL
            zpl_code = self.generate_zpl_barcode(barcode, product_name, sale_price, copies)
            
            # Intentar métodos en orden de preferencia
            methods = [
                ("Serial USB", self.send_via_serial),
                ("Windows Printer", self.send_via_windows_printer),
                ("LPR (Unix/Linux)", self.send_via_lpr)
            ]
            
            for method_name, method_func in methods:
                try:
                    success, message = method_func(zpl_code)
                    if success:
                        return True, f"{message} (método: {method_name})"
                    else:
                        logger.warning(f"Método {method_name} falló: {message}")
                except Exception as e:
                    logger.warning(f"Método {method_name} generó excepción: {str(e)}")
                    continue
            
            # Si ningún método funcionó
            return False, "No se pudo imprimir con ningún método disponible. Verifique la conexión de la impresora."
            
        except Exception as e:
            error_msg = f"Error al procesar impresión: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def test_connection(self):
        """
        Prueba la conexión con la impresora Zebra
        """
        test_zpl = """
^XA
^FT50,100^A0N,30,30^FH\^FDPRUEBA DE IMPRESORA^FS
^FT50,150^A0N,20,20^FH\^FDConexion exitosa^FS
^XZ
"""
        return self.print_barcode("123456789012", "PRUEBA", "", 1)
    
    def get_available_ports(self):
        """
        Obtiene una lista de puertos seriales disponibles
        """
        try:
            ports = serial.tools.list_ports.comports()
            return [
                {
                    'device': port.device,
                    'description': port.description,
                    'manufacturer': getattr(port, 'manufacturer', 'N/A')
                }
                for port in ports
            ]
        except Exception as e:
            logger.error(f"Error obteniendo puertos: {str(e)}")
            return []

class BarcodeGeneratorService:
    """Servicio para generación de códigos de barras únicos"""
    
    @staticmethod
    def generate_unique_barcode():
        """
        Genera un código de barras único
        """
        # Usar timestamp actual + número aleatorio para asegurar unicidad
        timestamp = str(int(time.time()))
        random_part = str(random.randint(100, 999))
        
        # Formato: 78 + últimos 7 dígitos del timestamp + 3 dígitos aleatorios
        barcode = f"78{timestamp[-7:]}{random_part}"
        
        # Verificar que sea único en la base de datos
        while Product.objects.filter(barcode=barcode).exists():
            random_part = str(random.randint(100, 999))
            barcode = f"78{timestamp[-7:]}{random_part}"
        
        return barcode
    
    @staticmethod
    def validate_barcode(barcode):
        """
        Valida que un código de barras sea válido
        """
        if not barcode:
            return False, "Código de barras requerido"
        
        if not barcode.isdigit():
            return False, "El código de barras solo debe contener números"
        
        if len(barcode) < 8:
            return False, "El código de barras debe tener al menos 8 dígitos"
        
        if len(barcode) > 13:
            return False, "El código de barras no puede tener más de 13 dígitos"
        
        return True, "Código válido"

class InventoryService:
    """Servicio para lógica de negocio de inventario"""
    
    def calculate_product_profit(self, product, cost_price=None, sale_price=None):
        """Calcula la ganancia de un producto"""
        cost = cost_price or product.cost_price
        sale = sale_price or product.sale_price
        
        if cost and sale:
            profit_amount = sale - cost
            profit_percentage = (profit_amount / cost) * 100 if cost > 0 else 0
            return {
                'profit_amount': profit_amount,
                'profit_percentage': profit_percentage
            }
        return {'profit_amount': 0, 'profit_percentage': 0}
    
    def apply_category_profit(self, product):
        """Aplica la ganancia de la categoría al producto"""
        if product.category and product.category.profit_percentage and product.cost_price:
            profit_amount = product.cost_price * (product.category.profit_percentage / 100)
            return product.cost_price + profit_amount
        return product.cost_price
    
    def check_stock_levels(self):
        """Verifica los niveles de stock y genera alertas"""
        products = Product.objects.filter(track_stock=True, is_active=True)
        
        for product in products:
            current_stock = product.current_stock
            
            # Verificar stock bajo
            if current_stock <= product.min_stock and current_stock > 0:
                self._create_or_update_alert(
                    product, 'LOW_STOCK', current_stock, product.min_stock
                )
            
            # Verificar sin stock
            elif current_stock <= 0:
                self._create_or_update_alert(
                    product, 'OUT_OF_STOCK', current_stock, 0
                )
            
            # Verificar sobrestock
            elif current_stock > product.max_stock:
                self._create_or_update_alert(
                    product, 'OVERSTOCK', current_stock, product.max_stock
                )
            
            else:
                # Resolver alertas si el stock está en niveles normales
                StockAlert.objects.filter(
                    product=product,
                    is_active=True
                ).update(
                    is_active=False,
                    resolved_at=timezone.now()
                )
    
    def _create_or_update_alert(self, product, alert_type, current_stock, threshold):
        """Crea o actualiza una alerta de stock"""
        alert, created = StockAlert.objects.get_or_create(
            product=product,
            alert_type=alert_type,
            is_active=True,
            defaults={
                'current_stock': current_stock,
                'threshold': threshold
            }
        )
        
        if not created:
            alert.current_stock = current_stock
            alert.threshold = threshold
            alert.save()
    
    @transaction.atomic
    def create_stock_movement(self, product, movement_type, quantity, reason, user, **kwargs):
        """Crea un movimiento de stock"""
        # Validar cantidad para salidas
        if movement_type == 'OUT' and abs(quantity) > product.current_stock:
            raise ValueError("No hay suficiente stock disponible")
        
        # Ajustar cantidad según tipo de movimiento
        if movement_type == 'OUT':
            quantity = -abs(quantity)
        else:
            quantity = abs(quantity)
        
        movement = StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            reason=reason,
            quantity=quantity,
            user=user,
            **kwargs
        )
        
        # Verificar niveles de stock después del movimiento
        self.check_stock_levels()
        
        return movement
    
    def get_inventory_summary(self):
        """Obtiene un resumen del inventario"""
        products = Product.objects.filter(is_active=True)
        
        total_products = products.count()
        total_value = sum(
            product.current_stock * product.cost_price 
            for product in products 
            if product.track_stock
        )
        
        low_stock = products.filter(
            track_stock=True
        ).annotate(
            current_stock=models.Sum('stock_movements__quantity')
        ).filter(
            current_stock__lte=models.F('min_stock')
        ).count()
        
        out_of_stock = products.filter(
            track_stock=True
        ).annotate(
            current_stock=models.Sum('stock_movements__quantity')
        ).filter(
            current_stock__lte=0
        ).count()
        
        return {
            'total_products': total_products,
            'total_value': total_value,
            'low_stock_count': low_stock,
            'out_of_stock_count': out_of_stock
        }

class BarcodeService:
    """Servicio para generación de códigos de barras"""
    
    def generate_barcode_image(self, code, format='png'):
        """Genera imagen de código de barras"""
        try:
            # Usar EAN13 para códigos de 12-13 dígitos
            if len(code) in [12, 13]:
                barcode_class = barcode.get('ean13')
            else:
                barcode_class = barcode.get('code128')
            
            ean = barcode_class(code, writer=ImageWriter())
            buffer = BytesIO()
            ean.write(buffer)
            buffer.seek(0)
            
            return buffer
        except Exception as e:
            raise Exception(f"Error generando código de barras: {str(e)}")
    
    def generate_printable_barcodes(self, product_ids, format='pdf', size='medium'):
        """Genera códigos de barras para imprimir"""
        products = Product.objects.filter(id__in=product_ids)
        
        if format == 'pdf':
            return self._generate_pdf_barcodes(products, size)
        else:
            return self._generate_image_barcodes(products, size)
    
    def _generate_pdf_barcodes(self, products, size):
        """Genera PDF con códigos de barras"""
        buffer = BytesIO()
        
        # Configuraciones de tamaño
        sizes = {
            'small': {'width': 40*mm, 'height': 20*mm, 'cols': 4, 'rows': 10},
            'medium': {'width': 60*mm, 'height': 30*mm, 'cols': 3, 'rows': 7},
            'large': {'width': 80*mm, 'height': 40*mm, 'cols': 2, 'rows': 5}
        }
        
        config = sizes.get(size, sizes['medium'])
        
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        x_start = 10*mm
        y_start = height - 20*mm
        
        col = 0
        row = 0
        
        for product in products:
            if not product.barcode:
                continue
            
            x = x_start + (col * config['width'])
            y = y_start - (row * config['height'])
            
            # Generar código de barras
            try:
                barcode_buffer = self.generate_barcode_image(product.barcode)
                
                # Crear imagen temporal
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_file.write(barcode_buffer.getvalue())
                    temp_file.flush()
                    
                    # Insertar en PDF
                    c.drawImage(
                        temp_file.name,
                        x, y - config['height'] + 10*mm,
                        width=config['width'] - 5*mm,
                        height=config['height'] - 15*mm
                    )
                    
                    # Agregar texto
                    c.drawString(x, y - 5*mm, product.name[:25])
                    c.drawString(x, y - 8*mm, f"SKU: {product.sku}")
                    c.drawString(x, y - 11*mm, f"${product.sale_price}")
                    
                    # Limpiar archivo temporal
                    os.unlink(temp_file.name)
                
            except Exception as e:
                print(f"Error generando código de barras para {product.name}: {e}")
            
            col += 1
            if col >= config['cols']:
                col = 0
                row += 1
                if row >= config['rows']:
                    c.showPage()
                    row = 0
        
        c.save()
        buffer.seek(0)
        
        return {
            'file': buffer,
            'filename': f'codigos_barras_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            'content_type': 'application/pdf'
        }
    
    def _generate_image_barcodes(self, products, size):
        """Genera archivo ZIP con imágenes de códigos de barras"""
        buffer = BytesIO()
        
        with zipfile.ZipFile(buffer, 'w') as zip_file:
            for product in products:
                if not product.barcode:
                    continue
                
                try:
                    barcode_buffer = self.generate_barcode_image(product.barcode)
                    filename = f"{product.sku}_{product.barcode}.png"
                    zip_file.writestr(filename, barcode_buffer.getvalue())
                except Exception as e:
                    print(f"Error generando código de barras para {product.name}: {e}")
        
        buffer.seek(0)
        
        return {
            'file': buffer,
            'filename': f'codigos_barras_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip',
            'content_type': 'application/zip'
        }

class ImportExportService:
    """Servicio para importación y exportación de productos"""
    
    def import_products(self, file, user):
        """Importa productos desde archivo Excel o CSV"""
        try:
            # Leer archivo
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            results = {
                'total': len(df),
                'created': 0,
                'updated': 0,
                'errors': []
            }
            
            for index, row in df.iterrows():
                try:
                    with transaction.atomic():
                        self._process_product_row(row, user)
                        results['created'] += 1
                except Exception as e:
                    results['errors'].append(f"Fila {index + 2}: {str(e)}")
            
            return results
            
        except Exception as e:
            raise Exception(f"Error procesando archivo: {str(e)}")
    
    def _process_product_row(self, row, user):
        """Procesa una fila del archivo de importación"""
        # Validar campos obligatorios
        required_fields = ['nombre', 'categoria', 'marca', 'proveedor', 'precio_costo']
        for field in required_fields:
            if pd.isna(row.get(field)):
                raise ValueError(f"Campo obligatorio faltante: {field}")
        
        # Obtener o crear categoría
        category, _ = Category.objects.get_or_create(
            name=row['categoria'],
            defaults={'profit_percentage': row.get('ganancia_categoria', 0)}
        )
        
        # Obtener o crear marca
        brand, _ = Brand.objects.get_or_create(
            name=row['marca']
        )
        
        # Obtener o crear proveedor
        supplier, _ = Supplier.objects.get_or_create(
            name=row['proveedor'],
            defaults={'ruc': row.get('ruc_proveedor', '9999999999999')}
        )
        
        # Crear o actualizar producto
        product_data = {
            'name': row['nombre'],
            'description': row.get('descripcion', ''),
            'category': category,
            'brand': brand,
            'supplier': supplier,
            'cost_price': row['precio_costo'],
            'sale_price': row.get('precio_venta', 0),
            'unit': row.get('unidad', 'UNIT'),
            'min_stock': row.get('stock_minimo', 5),
            'max_stock': row.get('stock_maximo', 100),
        }
        
        sku = row.get('sku')
        if sku:
            product, created = Product.objects.update_or_create(
                sku=sku,
                defaults=product_data
            )
        else:
            product = Product.objects.create(**product_data)
        
        # Crear stock inicial si se especifica
        initial_stock = row.get('stock_inicial')
        if initial_stock and initial_stock > 0:
            StockMovement.objects.create(
                product=product,
                movement_type='IN',
                reason='INITIAL',
                quantity=initial_stock,
                unit_cost=product.cost_price,
                user=user,
                notes='Importación inicial'
            )
    
    def export_products(self, queryset):
        """Exporta productos a Excel"""
        data = []
        
        for product in queryset:
            data.append({
                'SKU': product.sku,
                'Código de Barras': product.barcode,
                'Nombre': product.name,
                'Descripción': product.description,
                'Categoría': product.category.name,
                'Marca': product.brand.name,
                'Proveedor': product.supplier.name,
                'Precio Costo': product.cost_price,
                'Precio Venta': product.sale_price,
                'Ganancia': product.profit_amount,
                'Porcentaje Ganancia': product.profit_percentage,
                'Unidad': product.get_unit_display(),
                'Stock Actual': product.current_stock,
                'Stock Mínimo': product.min_stock,
                'Stock Máximo': product.max_stock,
                'Activo': 'Sí' if product.is_active else 'No',
                'Para Venta': 'Sí' if product.is_for_sale else 'No',
                'Fecha Creación': product.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        df = pd.DataFrame(data)
        
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Productos', index=False)
        
        buffer.seek(0)
        return buffer

class StockAlertService:
    """Servicio para manejo de alertas de stock"""
    
    def check_all_stock_alerts(self):
        """Verifica todas las alertas de stock"""
        inventory_service = InventoryService()
        inventory_service.check_stock_levels()
    
    def get_active_alerts(self):
        """Obtiene todas las alertas activas"""
        return StockAlert.objects.filter(is_active=True).select_related('product')
    
    def resolve_alerts_for_product(self, product, user):
        """Resuelve todas las alertas de un producto"""
        alerts = StockAlert.objects.filter(product=product, is_active=True)
        for alert in alerts:
            alert.resolve(user)
    
    def send_alert_notifications(self):
        """Envía notificaciones de alertas (implementar según necesidades)"""
        # Aquí puedes implementar envío de emails, SMS, etc.
        pass

# ==================== FUNCIONES AUXILIARES ====================

def get_zebra_service():
    """
    Factory function para obtener una instancia del servicio Zebra
    """
    return ZebraPrinterService()

def get_barcode_generator():
    """
    Factory function para obtener una instancia del generador de códigos
    """
    return BarcodeGeneratorService()

def get_inventory_service():
    """
    Factory function para obtener una instancia del servicio de inventario
    """
    return InventoryService()

def get_barcode_service():
    """
    Factory function para obtener una instancia del servicio de códigos de barras
    """
    return BarcodeService()

def get_import_export_service():
    """
    Factory function para obtener una instancia del servicio de importación/exportación
    """
    return ImportExportService()

def get_stock_alert_service():
    """
    Factory function para obtener una instancia del servicio de alertas
    """
    return StockAlertService()