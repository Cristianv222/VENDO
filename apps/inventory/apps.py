from django.apps import AppConfig

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
    verbose_name = 'Inventario'
    
    def ready(self):
        # Importar señales
        import apps.inventory.signals
        
        # Registrar permisos personalizados si es necesario
        self.setup_permissions()
    
    def setup_permissions(self):
        """Configura permisos personalizados si es necesario"""
        try:
            from django.contrib.auth.models import Permission
            from django.contrib.contenttypes.models import ContentType
            from .models import Product, StockMovement, StockAlert
            
            # Aquí puedes agregar permisos personalizados si los necesitas
            # Por ejemplo:
            # content_type = ContentType.objects.get_for_model(Product)
            # Permission.objects.get_or_create(
            #     codename='can_generate_barcodes',
            #     name='Can generate barcodes',
            #     content_type=content_type,
            # )
            
        except Exception as e:
            # En caso de error (ej: durante migraciones), continuar silenciosamente
            pass