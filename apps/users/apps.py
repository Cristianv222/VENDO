"""
Configuración de la aplicación Users
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    """
    Configuración de la aplicación Users
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = _('Usuarios')
    
    def ready(self):
        """
        Configuración cuando la app está lista
        """
        try:
            # Importar señales
            import apps.users.signals
            
            # Registrar tareas de Celery
            self._register_celery_tasks()
            
            # Configurar permisos y roles por defecto
            self._setup_default_permissions()
            
        except ImportError:
            pass
    
    def _register_celery_tasks(self):
        """
        Registrar tareas de Celery
        """
        try:
            from celery import Celery
            from django.conf import settings
            
            if hasattr(settings, 'CELERY_ALWAYS_EAGER') and not settings.CELERY_ALWAYS_EAGER:
                # Registrar tareas periódicas
                from .tasks import cleanup_expired_sessions, send_password_expiry_notifications
                
        except ImportError:
            pass
    
    def _setup_default_permissions(self):
        """
        Configurar permisos y roles por defecto
        """
        try:
            from django.db import transaction
            from .utils import create_default_permissions, create_default_roles
            
            # Crear en una transacción para evitar problemas de concurrencia
            with transaction.atomic():
                create_default_permissions()
                create_default_roles()
                
        except Exception:
            # No fallar la inicialización de la app por esto
            pass