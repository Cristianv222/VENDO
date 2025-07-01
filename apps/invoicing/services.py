from django.db import transaction
from django.utils import timezone
from .models import Invoice, InvoiceDetail, InvoicePayment, Customer, Product
from .utils import generar_clave_acceso, generar_numero_factura, obtener_siguiente_secuencial
from .xml_generators import XMLGenerator
from .sri_client import SRIClient
from .email_service import EmailService
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class InvoiceService:
    def __init__(self, company):
        self.company = company
    
    @transaction.atomic
    def create_invoice(self, invoice_data):
        """Crea una nueva factura"""
        try:
            # Obtener o crear cliente
            customer_data = invoice_data['customer']
            customer, created = Customer.objects.get_or_create(
                company=self.company,
                identificacion=customer_data['identificacion'],
                defaults={
                    'tipo_identificacion': customer_data['tipo_identificacion'],
                    'razon_social': customer_data['razon_social'],
                    'direccion': customer_data.get('direccion', ''),
                    'email': customer_data.get('email', ''),
                    'telefono': customer_data.get('telefono', ''),
                }
            )
            
            # Generar secuencial
            establecimiento = invoice_data.get('establecimiento', '001')
            punto_emision = invoice_data.get('punto_emision', '001')
            secuencial = obtener_siguiente_secuencial(self.company, establecimiento, punto_emision)
            numero_factura = generar_numero_factura(establecimiento, punto_emision, secuencial)
            
            # Generar clave de acceso
            fecha_emision = timezone.now()
            clave_acceso = generar_clave_acceso(
                fecha_emision=fecha_emision,
                tipo_comprobante='01',  # Factura
                ruc=self.company.ruc,
                ambiente='1' if self.company.sri_config.environment == 'test' else '2',
                establecimiento=establecimiento,
                punto_emision=punto_emision,
                secuencial=secuencial
            )
            
            # Crear factura
            invoice = Invoice.objects.create(
                company=self.company,
                customer=customer,
                establecimiento=establecimiento,
                punto_emision=punto_emision,
                secuencial=secuencial,
                numero_factura=numero_factura,
                fecha_emision=fecha_emision,
                clave_acceso=clave_acceso,
                observaciones=invoice_data.get('observaciones', '')
            )
            
            # Crear detalles
            for detalle_data in invoice_data['detalles']:
                product = Product.objects.get(
                    company=self.company,
                    codigo_principal=detalle_data['codigo_principal']
                )
                
                InvoiceDetail.objects.create(
                    invoice=invoice,
                    product=product,
                    codigo_principal=product.codigo_principal,
                    codigo_auxiliar=product.codigo_auxiliar,
                    descripcion=product.descripcion,
                    cantidad=Decimal(str(detalle_data['cantidad'])),
                    precio_unitario=Decimal(str(detalle_data.get('precio_unitario', product.precio_unitario))),
                    descuento=Decimal(str(detalle_data.get('descuento', 0))),
                    porcentaje_iva=product.porcentaje_iva,
                    porcentaje_ice=product.porcentaje_ice
                )
            
            # Crear pagos
            for pago_data in invoice_data['pagos']:
                InvoicePayment.objects.create(
                    invoice=invoice,
                    forma_pago=pago_data['forma_pago'],
                    valor=Decimal(str(pago_data['valor'])),
                    plazo=pago_data.get('plazo', 0),
                    unidad_tiempo=pago_data.get('unidad_tiempo', 'dias')
                )
            
            # Calcular totales
            invoice.calcular_totales()
            
            return {
                'success': True,
                'invoice': invoice,
                'message': 'Factura creada exitosamente'
            }
            
        except Exception as e:
            logger.error(f"Error creando factura: {str(e)}")
            return {
                'success': False,
                'message': f'Error creando factura: {str(e)}'
            }
    
    def process_electronic_invoice(self, invoice):
        """Procesa la factura electrónica (genera XML, firma, envía al SRI)"""
        try:
            # Generar XML
            xml_generator = XMLGenerator()
            xml_content = xml_generator.generar_xml_factura(invoice)
            
            # Firmar XML
            sri_client = SRIClient(self.company)
            xml_signed = sri_client.sign_xml(xml_content)
            
            # Enviar al SRI
            response = sri_client.send_document(xml_signed, invoice.clave_acceso)
            
            if response['success']:
                invoice.estado_sri = 'ENVIADO'
                invoice.save()
                
                return {
                    'success': True,
                    'message': 'Factura enviada al SRI exitosamente',
                    'response': response
                }
            else:
                return {
                    'success': False,
                    'message': f'Error enviando al SRI: {response.get("estado", "Error desconocido")}',
                    'response': response
                }
                
        except Exception as e:
            logger.error(f"Error procesando factura electrónica: {str(e)}")
            return {
                'success': False,
                'message': f'Error procesando factura electrónica: {str(e)}'
            }
    
    def get_authorization(self, invoice):
        """Obtiene la autorización del SRI"""
        try:
            sri_client = SRIClient(self.company)
            response = sri_client.get_authorization(invoice.clave_acceso)
            
            if response['success']:
                invoice.numero_autorizacion = response['numero_autorizacion']
                invoice.fecha_autorizacion = response['fecha_autorizacion']
                invoice.xml_autorizado = response['xml_autorizado']
                invoice.estado_sri = 'AUTORIZADO'
                invoice.save()
                
                return {
                    'success': True,
                    'message': 'Autorización obtenida exitosamente',
                    'response': response
                }
            else:
                return {
                    'success': False,
                    'message': 'No se pudo obtener la autorización',
                    'response': response
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo autorización: {str(e)}")
            return {
                'success': False,
                'message': f'Error obteniendo autorización: {str(e)}'
            }
    
    def send_invoice_email(self, invoice):
        """Envía la factura por email"""
        try:
            email_service = EmailService(self.company)
            result = email_service.send_invoice_email(invoice, invoice.xml_autorizado)
            return result
            
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            return {
                'success': False,
                'message': f'Error enviando email: {str(e)}'
            }
    
    def complete_invoice_process(self, invoice_data):
        """Proceso completo: crear factura, enviar al SRI, obtener autorización y enviar email"""
        try:
            # Crear factura
            result = self.create_invoice(invoice_data)
            if not result['success']:
                return result
            
            invoice = result['invoice']
            
            # Procesar electrónicamente
            result = self.process_electronic_invoice(invoice)
            if not result['success']:
                return result
            
            # Obtener autorización (puede tomar tiempo)
            # En producción esto debería ser asíncrono
            import time
            time.sleep(5)  # Esperar un poco antes de consultar autorización
            
            result = self.get_authorization(invoice)
            if result['success']:
                # Enviar email
                email_result = self.send_invoice_email(invoice)
                
                return {
                    'success': True,
                    'invoice': invoice,
                    'message': 'Factura procesada completamente',
                    'email_sent': email_result['success'],
                    'email_message': email_result['message']
                }
            else:
                return {
                    'success': True,
                    'invoice': invoice,
                    'message': 'Factura enviada al SRI, pendiente de autorización',
                    'authorization_message': result['message']
                }
                
        except Exception as e:
            logger.error(f"Error en proceso completo: {str(e)}")
            return {
                'success': False,
                'message': f'Error en proceso completo: {str(e)}'
            }

class CustomerService:
    def __init__(self, company):
        self.company = company
    
    def create_or_update_customer(self, customer_data):
        """Crea o actualiza un cliente"""
        try:
            customer, created = Customer.objects.update_or_create(
                company=self.company,
                identificacion=customer_data['identificacion'],
                defaults={
                    'tipo_identificacion': customer_data['tipo_identificacion'],
                    'razon_social': customer_data['razon_social'],
                    'direccion': customer_data.get('direccion', ''),
                    'email': customer_data.get('email', ''),
                    'telefono': customer_data.get('telefono', ''),
                }
            )
            
            return {
                'success': True,
                'customer': customer,
                'created': created,
                'message': 'Cliente creado exitosamente' if created else 'Cliente actualizado exitosamente'
            }
            
        except Exception as e:
            logger.error(f"Error con cliente: {str(e)}")
            return {
                'success': False,
                'message': f'Error con cliente: {str(e)}'
            }

class ProductService:
    def __init__(self, company):
        self.company = company
    
    def create_or_update_product(self, product_data):
        """Crea o actualiza un producto"""
        try:
            product, created = Product.objects.update_or_create(
                company=self.company,
                codigo_principal=product_data['codigo_principal'],
                defaults={
                    'codigo_auxiliar': product_data.get('codigo_auxiliar', ''),
                    'descripcion': product_data['descripcion'],
                    'precio_unitario': Decimal(str(product_data['precio_unitario'])),
                    'tiene_iva': product_data.get('tiene_iva', True),
                    'porcentaje_iva': Decimal(str(product_data.get('porcentaje_iva', 12))),
                    'tiene_ice': product_data.get('tiene_ice', False),
                    'porcentaje_ice': Decimal(str(product_data.get('porcentaje_ice', 0))),
                }
            )
            
            return {
                'success': True,
                'product': product,
                'created': created,
                'message': 'Producto creado exitosamente' if created else 'Producto actualizado exitosamente'
            }
            
        except Exception as e:
            logger.error(f"Error con producto: {str(e)}")
            return {
                'success': False,
                'message': f'Error con producto: {str(e)}'
            }