import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import SRIConfiguration, SRILog
from .pdf_generators import PDFGenerator
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, company):
        self.company = company
        try:
            self.sri_config = SRIConfiguration.objects.get(company=company)
        except SRIConfiguration.DoesNotExist:
            raise Exception("No existe configuración de email para esta empresa")
    
    def send_invoice_email(self, invoice, xml_autorizado=None):
        """Envía la factura por email al cliente"""
        try:
            if not invoice.customer.email:
                raise Exception("El cliente no tiene email configurado")
            
            # Generar PDF
            pdf_generator = PDFGenerator()
            pdf_content = pdf_generator.generate_invoice_pdf(invoice, xml_autorizado)
            
            # Preparar contexto para el template
            context = {
                'invoice': invoice,
                'company': self.company,
                'customer': invoice.customer
            }
            
            # Renderizar template de email
            html_content = render_to_string('invoicing/email/invoice_email.html', context)
            text_content = render_to_string('invoicing/email/invoice_email.txt', context)
            
            # Crear email
            subject = f"Factura Electrónica {invoice.numero_factura} - {self.company.razon_social}"
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.sri_config.email_host_user,
                to=[invoice.customer.email],
                connection=self._get_email_connection()
            )
            
            email.attach_alternative(html_content, "text/html")
            
            # Adjuntar PDF
            filename = f"Factura_{invoice.numero_factura}.pdf"
            email.attach(filename, pdf_content, 'application/pdf')
            
            # Adjuntar XML si está disponible
            if xml_autorizado:
                xml_filename = f"Factura_{invoice.numero_factura}.xml"
                email.attach(xml_filename, xml_autorizado.encode('utf-8'), 'application/xml')
            
            # Enviar email
            email.send()
            
            # Log exitoso
            SRILog.objects.create(
                company=self.company,
                invoice=invoice,
                clave_acceso=invoice.clave_acceso,
                proceso='EMAIL',
                estado='EXITOSO',
                response_data={
                    'destinatario': invoice.customer.email,
                    'asunto': subject
                }
            )
            
            return {
                'success': True,
                'message': f'Email enviado exitosamente a {invoice.customer.email}'
            }
            
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            
            # Log del error
            SRILog.objects.create(
                company=self.company,
                invoice=invoice,
                clave_acceso=invoice.clave_acceso if hasattr(invoice, 'clave_acceso') else '',
                proceso='EMAIL',
                estado='ERROR',
                error_message=str(e)
            )
            
            return {
                'success': False,
                'message': f'Error enviando email: {str(e)}'
            }
    
    def _get_email_connection(self):
        """Obtiene la conexión SMTP configurada"""
        from django.core.mail import get_connection
        
        return get_connection(
            host=self.sri_config.email_host,
            port=self.sri_config.email_port,
            username=self.sri_config.email_host_user,
            password=self.sri_config.email_host_password,
            use_tls=self.sri_config.email_use_tls,
            fail_silently=False,
        )
    
    def test_email_connection(self):
        """Prueba la conexión de email"""
        try:
            connection = self._get_email_connection()
            connection.open()
            connection.close()
            return {'success': True, 'message': 'Conexión de email exitosa'}
        except Exception as e:
            return {'success': False, 'message': f'Error en conexión de email: {str(e)}'}