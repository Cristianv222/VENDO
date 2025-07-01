from django.core.management.base import BaseCommand
from apps.invoicing.services import InvoiceService
from apps.invoicing.models import Customer, Product
from apps.core.models import Company
from decimal import Decimal
import json

class Command(BaseCommand):
    help = 'Genera una factura de prueba'
    
    def add_arguments(self, parser):
        parser.add_argument('company_id', type=str, help='ID de la empresa')
        parser.add_argument(
            '--customer-id',
            type=str,
            help='ID del cliente (se crea uno de prueba si no se especifica)'
        )
        parser.add_argument(
            '--send-sri',
            action='store_true',
            help='Enviar automáticamente al SRI'
        )
    
    def handle(self, *args, **options):
        company_id = options['company_id']
        customer_id = options.get('customer_id')
        send_sri = options.get('send_sri', False)
        
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Empresa {company_id} no encontrada"))
            return
        
        # Obtener o crear cliente de prueba
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id, company=company)
            except Customer.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Cliente {customer_id} no encontrado"))
                return
        else:
            customer, created = Customer.objects.get_or_create(
                company=company,
                identificacion='9999999999',
                defaults={
                    'tipo_identificacion': '05',
                    'razon_social': 'Cliente de Prueba',
                    'direccion': 'Dirección de Prueba',
                    'email': 'prueba@ejemplo.com',
                    'telefono': '0999999999'
                }
            )
            if created:
                self.stdout.write(f"Cliente de prueba creado: {customer.razon_social}")
        
        # Obtener o crear producto de prueba
        product, created = Product.objects.get_or_create(
            company=company,
            codigo_principal='TEST001',
            defaults={
                'descripcion': 'Producto de Prueba',
                'precio_unitario': Decimal('10.00'),
                'tiene_iva': True,
                'porcentaje_iva': Decimal('12.00')
            }
        )
        if created:
            self.stdout.write(f"Producto de prueba creado: {product.descripcion}")
        
        # Datos de la factura de prueba
        invoice_data = {
            'customer': {
                'tipo_identificacion': customer.tipo_identificacion,
                'identificacion': customer.identificacion,
                'razon_social': customer.razon_social,
                'direccion': customer.direccion,
                'email': customer.email,
                'telefono': customer.telefono
            },
            'detalles': [
                {
                    'codigo_principal': product.codigo_principal,
                    'cantidad': 2,
                    'precio_unitario': float(product.precio_unitario),
                    'descuento': 0
                }
            ],
            'pagos': [
                {
                    'forma_pago': '01',  # Sin utilización del sistema financiero
                    'valor': 22.40  # 2 * 10.00 * 1.12
                }
            ],
            'observaciones': 'Factura de prueba generada automáticamente'
        }
        
        self.stdout.write("Creando factura de prueba...")
        
        try:
            invoice_service = InvoiceService(company)
            
            if send_sri:
                result = invoice_service.complete_invoice_process(invoice_data)
            else:
                result = invoice_service.create_invoice(invoice_data)
            
            if result['success']:
                invoice = result['invoice']
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Factura creada exitosamente: {invoice.numero_factura}"
                    )
                )
                self.stdout.write(f"Clave de acceso: {invoice.clave_acceso}")
                self.stdout.write(f"Total: ${invoice.importe_total}")
                
                if send_sri:
                    self.stdout.write(f"Estado SRI: {invoice.estado_sri}")
            else:
                self.stdout.write(self.style.ERROR(f"Error: {result['message']}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creando factura: {str(e)}"))