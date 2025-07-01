from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from .models import Invoice, InvoiceDetail, InvoicePayment, Customer, Product, SRILog
from .tasks import process_invoice_async, send_invoice_email_async
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=InvoiceDetail)
def update_invoice_totals(sender, instance, created, **kwargs):
    """Actualiza los totales de la factura cuando se modifica un detalle"""
    if instance.invoice_id:
        try:
            instance.invoice.calcular_totales()
            logger.info(f"Totales actualizados para factura {instance.invoice.numero_factura}")
        except Exception as e:
            logger.error(f"Error actualizando totales de factura {instance.invoice.numero_factura}: {str(e)}")

@receiver(post_delete, sender=InvoiceDetail)
def update_invoice_totals_on_delete(sender, instance, **kwargs):
    """Actualiza los totales cuando se elimina un detalle"""
    if instance.invoice_id:
        try:
            instance.invoice.calcular_totales()
            logger.info(f"Totales actualizados tras eliminar detalle de factura {instance.invoice.numero_factura}")
        except Exception as e:
            logger.error(f"Error actualizando totales tras eliminar detalle: {str(e)}")

@receiver(post_save, sender=InvoicePayment)
def validate_payment_total(sender, instance, created, **kwargs):
    """Valida que el total de pagos coincida con el total de la factura"""
    if instance.invoice_id:
        try:
            invoice = instance.invoice
            total_pagos = sum(pago.valor for pago in invoice.invoicepayment_set.all())
            
            if total_pagos != invoice.importe_total:
                logger.warning(
                    f"Discrepancia en pagos de factura {invoice.numero_factura}: "
                    f"Total factura: {invoice.importe_total}, Total pagos: {total_pagos}"
                )
        except Exception as e:
            logger.error(f"Error validando pagos: {str(e)}")

@receiver(post_save, sender=Invoice)
def invoice_status_change(sender, instance, created, **kwargs):
    """Maneja cambios de estado de la factura"""
    if not created:
        # Verificar si el estado cambió
        try:
            old_instance = Invoice.objects.get(pk=instance.pk)
            if hasattr(old_instance, '_state') and old_instance.estado_sri != instance.estado_sri:
                logger.info(f"Estado de factura {instance.numero_factura} cambió de {old_instance.estado_sri} a {instance.estado_sri}")
                
                # Enviar email automáticamente cuando se autoriza
                if instance.estado_sri == 'AUTORIZADO' and instance.customer.email:
                    send_invoice_email_async.delay(str(instance.id))
                    
                # Invalidar cache
                cache_key = f"invoice_stats_{instance.company.id}"
                cache.delete(cache_key)
                
        except Invoice.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error procesando cambio de estado: {str(e)}")

@receiver(post_save, sender=Customer)
def invalidate_customer_cache(sender, instance, **kwargs):
    """Invalida cache cuando se modifica un cliente"""
    cache_key = f"customers_{instance.company.id}"
    cache.delete(cache_key)

@receiver(post_save, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    """Invalida cache cuando se modifica un producto"""
    cache_key = f"products_{instance.company.id}"
    cache.delete(cache_key)

@receiver(post_save, sender=SRILog)
def process_sri_log(sender, instance, created, **kwargs):
    """Procesa logs del SRI para alertas"""
    if created and instance.estado == 'ERROR':
        try:
            # Contar errores recientes
            recent_errors = SRILog.objects.filter(
                company=instance.company,
                proceso=instance.proceso,
                estado='ERROR',
                created_at__gte=timezone.now() - timezone.timedelta(hours=1)
            ).count()
            
            # Alerta si hay muchos errores
            if recent_errors >= 5:
                logger.error(
                    f"Múltiples errores SRI para {instance.company.razon_social}: "
                    f"{recent_errors} errores en {instance.proceso} en la última hora"
                )
                
                # Aquí se puede implementar notificación por email o SMS
                # send_sri_alert.delay(instance.company.id, instance.proceso, recent_errors)
                
        except Exception as e:
            logger.error(f"Error procesando log SRI: {str(e)}")

# Signal personalizado para eventos de facturación
from django.dispatch import Signal

# Definir señales personalizadas
invoice_sent_to_sri = Signal()
invoice_authorized = Signal()
invoice_rejected = Signal()
invoice_email_sent = Signal()

@receiver(invoice_authorized)
def handle_invoice_authorized(sender, invoice, **kwargs):
    """Maneja cuando una factura es autorizada"""
    logger.info(f"Factura {invoice.numero_factura} autorizada exitosamente")
    
    # Actualizar estadísticas en cache
    cache_key = f"daily_stats_{invoice.company.id}_{timezone.now().date()}"
    stats = cache.get(cache_key, {'authorized': 0})
    stats['authorized'] += 1
    cache.set(cache_key, stats, 86400)  # 24 horas

@receiver(invoice_rejected)
def handle_invoice_rejected(sender, invoice, error_message, **kwargs):
    """Maneja cuando una factura es rechazada"""
    logger.error(f"Factura {invoice.numero_factura} rechazada: {error_message}")
    
    # Actualizar estadísticas en cache
    cache_key = f"daily_stats_{invoice.company.id}_{timezone.now().date()}"
    stats = cache.get(cache_key, {'rejected': 0})
    stats['rejected'] += 1
    cache.set(cache_key, stats, 86400)

@receiver(invoice_email_sent)
def handle_invoice_email_sent(sender, invoice, recipient, **kwargs):
    """Maneja cuando se envía email de factura"""
    logger.info(f"Email de factura {invoice.numero_factura} enviado a {recipient}")
    
    # Marcar como enviado por email (se puede agregar campo al modelo)
    # invoice.email_sent = True
    # invoice.email_sent_at = timezone.now()
    # invoice.save(update_fields=['email_sent', 'email_sent_at'])

# Función para emitir señales desde los servicios
def emit_invoice_signals(invoice, action, **kwargs):
    """Función helper para emitir señales de facturación"""
    try:
        if action == 'authorized':
            invoice_authorized.send(sender=invoice.__class__, invoice=invoice, **kwargs)
        elif action == 'rejected':
            invoice_rejected.send(sender=invoice.__class__, invoice=invoice, **kwargs)
        elif action == 'email_sent':
            invoice_email_sent.send(sender=invoice.__class__, invoice=invoice, **kwargs)
        elif action == 'sent_to_sri':
            invoice_sent_to_sri.send(sender=invoice.__class__, invoice=invoice, **kwargs)
    except Exception as e:
        logger.error(f"Error emitiendo señal {action}: {str(e)}")