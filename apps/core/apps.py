"""
Configuración de la aplicación Core
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = _('Core')
    
    def ready(self):
        """
        Método ejecutado cuando la app está lista
        """
        # Importar señales
        try:
            import apps.core.signals  # noqa
        except ImportError:
            pass