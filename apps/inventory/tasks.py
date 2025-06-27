from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import Product, StockAlert, StockMovement
from .services import InventoryService, StockAlertService, BarcodeService
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_stock_levels():
    """Tarea para verificar niveles de stock y generar alertas"""
    try:
        service = InventoryService()
        service.check_stock_levels()
        
        logger.info("Verificación de niveles de stock completada")
        return {"status": "success", "message": "Stock levels checked successfully"}
    
    except Exception as e:
        logger.error(f"Error verificando niveles de stock: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def send_stock_alerts():
    """Envía notificaciones de alertas de stock por email"""
    try:
        active_alerts = StockAlert.objects.filter(is_active=True).select_related('product')
        
        if not active_alerts.exists():
            return {"status": "success", "message": "No active alerts to send"}
        
        # Agrupar alertas por tipo
        alerts_by_type = {}
        for alert in active_alerts:
            alert_type = alert.get_alert_type_display()
            if alert_type not in alerts_by_type:
                alerts_by_type[alert_type] = []
            alerts_by_type[alert_type].append(alert)
        
        # Preparar contexto para el email
        context = {
            'alerts_by_type': alerts_by_type,
            'total_alerts': active_alerts.count(),
            'date': timezone.now()
        }
        
        # Renderizar email
        subject = f'Alertas de Inventario - {active_alerts.count()} alertas activas'
        html_message = render_to_string('inventory/emails/stock_alerts.html', context)
        plain_message = render_to_string('inventory/emails/stock_alerts.txt', context)
        
        # Obtener destinatarios (usuarios con permisos de inventario)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recipients = User.objects.filter(
            is_active=True,
            user_permissions__codename__in=['view_stockalert', 'change_stockalert']
        ).values_list('email', flat=True)
        
        recipients = [email for email in recipients if email]
        
        if recipients:
            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False,
            )
            
            logger.info(f"Alertas de stock enviadas a {len(recipients)} destinatarios")
            return {"status": "success", "message": f"Alerts sent to {len(recipients)} recipients"}
        else:
            logger.warning("No hay destinatarios para alertas de stock")
            return {"status": "warning", "message": "No recipients found for stock alerts"}
    
    except Exception as e:
        logger.error(f"Error enviando alertas de stock: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def generate_low_stock_report():
    """Genera reporte de productos con stock bajo"""
    try:
        from django.db import models
        
        low_stock_products = Product.objects.filter(
            is_active=True,
            track_stock=True
        ).annotate(
            current_stock=models.Sum('stock_movements__quantity')
        ).filter(
            current_stock__lte=models.F('min_stock')
        ).select_related('category', 'brand', 'supplier')
        
        if not low_stock_products.exists():
            return {"status": "success", "message": "No low stock products found"}
        
        # Preparar datos del reporte
        report_data = []
        for product in low_stock_products:
            report_data.append({
                'sku': product.sku,
                'name': product.name,
                'category': product.category.name,
                'brand': product.brand.name,
                'current_stock': product.current_stock,
                'min_stock': product.min_stock,
                'difference': product.current_stock - product.min_stock,
                'supplier': product.supplier.name,
                'cost_price': product.cost_price,
            })
        
        # Aquí puedes generar un archivo Excel o CSV del reporte
        # y enviarlo por email o guardarlo en el sistema
        
        logger.info(f"Reporte de stock bajo generado con {len(report_data)} productos")
        return {
            "status": "success", 
            "message": f"Low stock report generated with {len(report_data)} products",
            "data": report_data
        }
    
    except Exception as e:
        logger.error(f"Error generando reporte de stock bajo: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def auto_reorder_products():
    """Tarea para sugerir reorden automático de productos"""
    try:
        from django.db import models
        
        # Productos que necesitan reorden (stock actual <= stock mínimo)
        reorder_products = Product.objects.filter(
            is_active=True,
            track_stock=True
        ).annotate(
            current_stock=models.Sum('stock_movements__quantity')
        ).filter(
            current_stock__lte=models.F('min_stock')
        ).select_related('supplier')
        
        # Agrupar por proveedor para órdenes de compra sugeridas
        suppliers_orders = {}
        for product in reorder_products:
            supplier_id = product.supplier.id
            if supplier_id not in suppliers_orders:
                suppliers_orders[supplier_id] = {
                    'supplier': product.supplier,
                    'products': []
                }
            
            suggested_quantity = product.max_stock - product.current_stock
            suppliers_orders[supplier_id]['products'].append({
                'product': product,
                'current_stock': product.current_stock,
                'suggested_quantity': suggested_quantity,
                'estimated_cost': product.cost_price * suggested_quantity
            })
        
        # Aquí puedes implementar lógica para crear órdenes de compra automáticas
        # o enviar notificaciones a los encargados de compras
        
        logger.info(f"Sugerencias de reorden generadas para {len(suppliers_orders)} proveedores")
        return {
            "status": "success",
            "message": f"Reorder suggestions generated for {len(suppliers_orders)} suppliers",
            "suppliers_count": len(suppliers_orders)
        }
    
    except Exception as e:
        logger.error(f"Error en reorden automático: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def cleanup_old_stock_movements():
    """Limpia movimientos de stock antiguos (mantener solo últimos 2 años)"""
    try:
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=730)  # 2 años
        
        old_movements = StockMovement.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = old_movements.count()
        old_movements.delete()
        
        logger.info(f"Limpieza completada: {count} movimientos antiguos eliminados")
        return {
            "status": "success",
            "message": f"Cleaned up {count} old stock movements"
        }
    
    except Exception as e:
        logger.error(f"Error en limpieza de movimientos: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def generate_barcodes_batch(product_ids, format='pdf', size='medium'):
    """Genera códigos de barras en lote"""
    try:
        service = BarcodeService()
        result = service.generate_printable_barcodes(product_ids, format, size)
        
        # Aquí puedes guardar el archivo generado en el sistema de archivos
        # o enviarlo por email
        
        logger.info(f"Códigos de barras generados para {len(product_ids)} productos")
        return {
            "status": "success",
            "message": f"Barcodes generated for {len(product_ids)} products",
            "file_info": {
                "filename": result['filename'],
                "content_type": result['content_type']
            }
        }
    
    except Exception as e:
        logger.error(f"Error generando códigos de barras: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def update_product_prices_by_category():
    """Actualiza precios de productos basado en cambios en porcentajes de categoría"""
    try:
        updated_count = 0
        
        # Obtener productos que necesitan actualización de precio
        products = Product.objects.filter(
            is_active=True,
            category__isnull=False
        ).select_related('category')
        
        for product in products:
            if product.category.profit_percentage > 0:
                # Calcular nuevo precio basado en la categoría
                expected_sale_price = product.cost_price * (1 + product.category.profit_percentage / 100)
                
                # Solo actualizar si hay diferencia significativa (más del 1%)
                price_difference = abs(product.sale_price - expected_sale_price)
                if price_difference > (product.sale_price * 0.01):
                    product.sale_price = expected_sale_price
                    product.calculate_profit()
                    product.save()
                    updated_count += 1
        
        logger.info(f"Precios actualizados para {updated_count} productos")
        return {
            "status": "success",
            "message": f"Prices updated for {updated_count} products"
        }
    
    except Exception as e:
        logger.error(f"Error actualizando precios: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def backup_inventory_data():
    """Crear backup de datos de inventario"""
    try:
        from django.core.management import call_command
        from io import StringIO
        import json
        
        # Crear backup de los modelos principales
        models_to_backup = [
            'inventory.Brand',
            'inventory.Category', 
            'inventory.Supplier',
            'inventory.Product',
            'inventory.StockMovement',
        ]
        
        backup_data = {}
        
        for model in models_to_backup:
            output = StringIO()
            call_command('dumpdata', model, stdout=output)
            backup_data[model] = output.getvalue()
        
        # Aquí puedes guardar el backup en un archivo o enviarlo a un servicio de backup
        
        logger.info("Backup de inventario completado exitosamente")
        return {
            "status": "success",
            "message": "Inventory backup completed successfully"
        }
    
    except Exception as e:
        logger.error(f"Error en backup de inventario: {str(e)}")
        return {"status": "error", "message": str(e)}