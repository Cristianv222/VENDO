from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import Product, StockMovement, Stock, Category
from .services import InventoryService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    """Señal después de guardar un producto"""
    if created:
        # Crear registro de stock inicial
        Stock.objects.get_or_create(product=instance)
        
        # Generar código de barras si no existe
        if not instance.barcode_image and instance.barcode:
            try:
                instance.generate_barcode_image()
            except Exception as e:
                logger.error(f"Error generando código de barras para {instance.name}: {e}")
        
        logger.info(f"Producto creado: {instance.name} ({instance.sku})")
    
    # Limpiar cache relacionado con productos
    cache_keys = [
        'products_low_stock',
        'products_out_of_stock',
        f'product_stock_{instance.id}',
        'inventory_summary'
    ]
    cache.delete_many(cache_keys)

@receiver(post_save, sender=StockMovement)
def stock_movement_post_save(sender, instance, created, **kwargs):
    """Señal después de crear un movimiento de stock"""
    if created:
        # Verificar niveles de stock después del movimiento
        try:
            service = InventoryService()
            service.check_stock_levels()
        except Exception as e:
            logger.error(f"Error verificando niveles de stock: {e}")
        
        # Limpiar cache de stock
        cache_keys = [
            f'product_stock_{instance.product.id}',
            'products_low_stock',
            'products_out_of_stock',
            'inventory_summary'
        ]
        cache.delete_many(cache_keys)
        
        logger.info(
            f"Movimiento de stock creado: {instance.product.name} "
            f"({instance.get_movement_type_display()}) - {instance.quantity}"
        )

@receiver(pre_save, sender=Product)
def product_pre_save(sender, instance, **kwargs):
    """Señal antes de guardar un producto"""
    # Si cambió el precio de costo, recalcular ganancia
    if instance.pk:
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            if old_instance.cost_price != instance.cost_price:
                # Si no se especificó nuevo precio de venta, calcularlo automáticamente
                if instance.sale_price == old_instance.sale_price:
                    instance.calculate_sale_price_from_category()
                instance.calculate_profit()
        except Product.DoesNotExist:
            pass

@receiver(post_save, sender=Category)
def category_post_save(sender, instance, created, **kwargs):
    """Señal después de guardar una categoría"""
    if not created:
        # Si cambió el porcentaje de ganancia, actualizar productos
        try:
            old_instance = Category.objects.get(pk=instance.pk)
            if old_instance.profit_percentage != instance.profit_percentage:
                # Programar tarea para actualizar precios
                from .tasks import update_product_prices_by_category
                update_product_prices_by_category.delay()
        except Category.DoesNotExist:
            pass

@receiver(post_delete, sender=Product)
def product_post_delete(sender, instance, **kwargs):
    """Señal después de eliminar un producto"""
    # Limpiar archivos asociados
    if instance.image:
        try:
            instance.image.delete(save=False)
        except:
            pass
    
    if instance.barcode_image:
        try:
            instance.barcode_image.delete(save=False)
        except:
            pass
    
    # Limpiar cache
    cache_keys = [
        f'product_stock_{instance.id}',
        'products_low_stock',
        'products_out_of_stock',
        'inventory_summary'
    ]
    cache.delete_many(cache_keys)
    
    logger.info(f"Producto eliminado: {instance.name} ({instance.sku})")

@receiver(post_delete, sender=StockMovement)
def stock_movement_post_delete(sender, instance, **kwargs):
    """Señal después de eliminar un movimiento de stock"""
    # Recalcular stock del producto
    try:
        stock, created = Stock.objects.get_or_create(product=instance.product)
        
        # Recalcular stock basado en movimientos restantes
        from django.db.models import Sum
        total_movements = StockMovement.objects.filter(
            product=instance.product
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        stock.quantity = total_movements
        stock.save()
        
        # Verificar niveles de stock
        service = InventoryService()
        service.check_stock_levels()
        
    except Exception as e:
        logger.error(f"Error recalculando stock después de eliminar movimiento: {e}")
    
    # Limpiar cache
    cache_keys = [
        f'product_stock_{instance.product.id}',
        'products_low_stock',
        'products_out_of_stock',
        'inventory_summary'
    ]
    cache.delete_many(cache_keys)