from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import logging
from .models import Invoice, SRILog, SRIConfiguration
from .services import InvoiceService
from .sri_client import SRIClient
from .email_service import EmailService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_invoice_async(self, invoice_id):
    """Procesa una factura de forma asíncrona"""
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        invoice_service = InvoiceService(invoice.company)
        
        # Procesar factura electrónica
        result = invoice_service.process_electronic_invoice(invoice)
        
        if result['success']:
            # Programar tarea para obtener autorización
            get_authorization_async.apply_async(
                args=[invoice_id],
                countdown=30  # Esperar 30 segundos
            )
            
            return {
                'success': True,
                'message': 'Factura procesada y enviada al SRI',
                'invoice_id': str(invoice_id)
            }
        else:
            # Reintentar si hay error
            raise self.retry(exc=Exception(result['message']))
            
    except Invoice.DoesNotExist:
        logger.error(f"Factura {invoice_id} no encontrada")
        return {'success': False, 'message': 'Factura no encontrada'}
    except Exception as e:
        logger.error(f"Error procesando factura {invoice_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'message': f'Error procesando factura: {str(e)}'}

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def get_authorization_async(self, invoice_id):
    """Obtiene la autorización del SRI de forma asíncrona"""
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Solo procesar si está en estado ENVIADO
        if invoice.estado_sri != 'ENVIADO':
            return {'success': False, 'message': 'Factura no está en estado ENVIADO'}
        
        invoice_service = InvoiceService(invoice.company)
        result = invoice_service.get_authorization(invoice)
        
        if result['success']:
            # Enviar email automáticamente si está autorizada
            send_invoice_email_async.delay(invoice_id)
            
            return {
                'success': True,
                'message': 'Autorización obtenida exitosamente',
                'numero_autorizacion': result['numero_autorizacion']
            }
        else:
            # Reintentar hasta 5 veces con intervalo creciente
            countdown = (self.request.retries + 1) * 60  # 1min, 2min, 3min, etc.
            raise self.retry(exc=Exception(result['message']), countdown=countdown)
            
    except Invoice.DoesNotExist:
        logger.error(f"Factura {invoice_id} no encontrada")
        return {'success': False, 'message': 'Factura no encontrada'}
    except Exception as e:
        logger.error(f"Error obteniendo autorización para factura {invoice_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            countdown = (self.request.retries + 1) * 60
            raise self.retry(exc=e, countdown=countdown)
        return {'success': False, 'message': f'Error obteniendo autorización: {str(e)}'}

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invoice_email_async(self, invoice_id):
    """Envía el email de la factura de forma asíncrona"""
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Solo enviar si está autorizada
        if invoice.estado_sri != 'AUTORIZADO':
            return {'success': False, 'message': 'Factura no está autorizada'}
        
        # Verificar que el cliente tenga email
        if not invoice.customer.email:
            return {'success': False, 'message': 'Cliente no tiene email configurado'}
        
        invoice_service = InvoiceService(invoice.company)
        result = invoice_service.send_invoice_email(invoice)
        
        if result['success']:
            return {
                'success': True,
                'message': 'Email enviado exitosamente',
                'destinatario': invoice.customer.email
            }
        else:
            raise self.retry(exc=Exception(result['message']))
            
    except Invoice.DoesNotExist:
        logger.error(f"Factura {invoice_id} no encontrada")
        return {'success': False, 'message': 'Factura no encontrada'}
    except Exception as e:
        logger.error(f"Error enviando email para factura {invoice_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'message': f'Error enviando email: {str(e)}'}

@shared_task
def check_pending_authorizations():
    """Tarea periódica para verificar autorizaciones pendientes"""
    try:
        # Buscar facturas enviadas hace más de 5 minutos sin autorización
        time_threshold = timezone.now() - timedelta(minutes=5)
        pending_invoices = Invoice.objects.filter(
            estado_sri='ENVIADO',
            created_at__lt=time_threshold
        )
        
        results = []
        for invoice in pending_invoices[:10]:  # Procesar máximo 10 por vez
            try:
                # Intentar obtener autorización
                get_authorization_async.delay(str(invoice.id))
                results.append(f"Programada verificación para factura {invoice.numero_factura}")
            except Exception as e:
                logger.error(f"Error programando verificación para {invoice.numero_factura}: {str(e)}")
                results.append(f"Error con factura {invoice.numero_factura}: {str(e)}")
        
        return {
            'success': True,
            'processed': len(results),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error en check_pending_authorizations: {str(e)}")
        return {'success': False, 'message': str(e)}

@shared_task
def check_certificate_expiration():
    """Tarea para verificar vencimiento de certificados"""
    try:
        results = []
        sri_configs = SRIConfiguration.objects.filter(is_active=True)
        
        for config in sri_configs:
            try:
                sri_client = SRIClient(config.company)
                cert_info = sri_client.validate_certificate()
                
                if not cert_info['valid']:
                    results.append(f"Certificado inválido para {config.company.razon_social}: {cert_info['error']}")
                else:
                    # Verificar si vence en los próximos 30 días
                    not_valid_after = cert_info['not_valid_after']
                    days_to_expire = (not_valid_after - timezone.now()).days
                    
                    if days_to_expire <= 30:
                        results.append(f"Certificado de {config.company.razon_social} vence en {days_to_expire} días")
                        
                        # Enviar email de alerta (implementar según necesidades)
                        # send_certificate_expiration_alert.delay(config.company.id, days_to_expire)
                        
            except Exception as e:
                results.append(f"Error verificando certificado de {config.company.razon_social}: {str(e)}")
        
        return {
            'success': True,
            'checked': len(sri_configs),
            'alerts': results
        }
        
    except Exception as e:
        logger.error(f"Error en check_certificate_expiration: {str(e)}")
        return {'success': False, 'message': str(e)}

@shared_task
def cleanup_old_logs():
    """Limpia logs antiguos del SRI"""
    try:
        # Eliminar logs de más de 90 días
        cutoff_date = timezone.now() - timedelta(days=90)
        deleted_count = SRILog.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        return {
            'success': True,
            'deleted_logs': deleted_count,
            'message': f'Eliminados {deleted_count} logs antiguos'
        }
        
    except Exception as e:
        logger.error(f"Error en cleanup_old_logs: {str(e)}")
        return {'success': False, 'message': str(e)}

@shared_task
def generate_daily_report():
    """Genera reporte diario de facturación"""
    try:
        today = timezone.now().date()
        
        # Estadísticas del día
        invoices_today = Invoice.objects.filter(fecha_emision__date=today)
        total_invoices = invoices_today.count()
        authorized_invoices = invoices_today.filter(estado_sri='AUTORIZADO').count()
        pending_invoices = invoices_today.filter(estado_sri='PENDIENTE').count()
        rejected_invoices = invoices_today.filter(estado_sri='RECHAZADO').count()
        
        total_amount = sum(inv.importe_total for inv in invoices_today)
        
        report = {
            'date': today.isoformat(),
            'total_invoices': total_invoices,
            'authorized_invoices': authorized_invoices,
            'pending_invoices': pending_invoices,
            'rejected_invoices': rejected_invoices,
            'total_amount': float(total_amount),
            'success_rate': (authorized_invoices / total_invoices * 100) if total_invoices > 0 else 0
        }
        
        # Aquí se puede enviar el reporte por email o guardarlo en la base de datos
        logger.info(f"Reporte diario generado: {report}")
        
        return {
            'success': True,
            'report': report
        }
        
    except Exception as e:
        logger.error(f"Error generando reporte diario: {str(e)}")
        return {'success': False, 'message': str(e)}

# Task para el proceso completo de facturación
@shared_task
def complete_invoice_process_async(invoice_data, company_id):
    """Proceso completo de facturación de forma asíncrona"""
    try:
        from apps.core.models import Company
        company = Company.objects.get(id=company_id)
        
        invoice_service = InvoiceService(company)
        
        # Crear factura
        result = invoice_service.create_invoice(invoice_data)
        if not result['success']:
            return result
        
        invoice = result['invoice']
        
        # Procesar de forma asíncrona
        process_invoice_async.delay(str(invoice.id))
        
        return {
            'success': True,
            'invoice_id': str(invoice.id),
            'numero_factura': invoice.numero_factura,
            'message': 'Factura creada y enviada a procesamiento asíncrono'
        }
        
    except Exception as e:
        logger.error(f"Error en proceso completo asíncrono: {str(e)}")
        return {'success': False, 'message': str(e)}