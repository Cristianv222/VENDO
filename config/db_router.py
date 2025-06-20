
"""
Database Router for Schema Management
Gestiona la separación de datos por esquemas en PostgreSQL para VENDO
"""

from django.conf import settings
from django.db import connection


class SchemaRouter:
    """
    Router para dirigir las operaciones de base de datos a diferentes esquemas
    basado en las aplicaciones de Django.
    """

    def _get_schema_for_app(self, app_label):
        """Obtener el esquema para una aplicación específica."""
        try:
            return getattr(settings, 'DATABASE_APPS_MAPPING', {}).get(app_label, 'public')
        except:
            return 'public'

    def _set_search_path(self, schema_name):
        """Establecer el search_path para el esquema específico."""
        try:
            if schema_name and schema_name != 'public':
                with connection.cursor() as cursor:
                    cursor.execute(f"SET search_path TO {schema_name}, public")
        except:
            # Silenciar errores durante la inicialización
            pass

    def db_for_read(self, model, **hints):
        """Dirigir las operaciones de lectura al esquema apropiado."""
        try:
            app_label = model._meta.app_label
            schema = self._get_schema_for_app(app_label)
            self._set_search_path(schema)
            return 'default'
        except:
            return 'default'

    def db_for_write(self, model, **hints):
        """Dirigir las operaciones de escritura al esquema apropiado."""
        try:
            app_label = model._meta.app_label
            schema = self._get_schema_for_app(app_label)
            self._set_search_path(schema)
            return 'default'
        except:
            return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Permitir relaciones entre modelos.
        Permitimos relaciones entre el mismo esquema o con core.
        """
        try:
            db_set = {'default'}
            if obj1._state.db in db_set and obj2._state.db in db_set:
                return True
            return None
        except:
            return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Permitir migraciones según el esquema correspondiente.
        """
        try:
            if db == 'default':
                return True
            return None
        except:
            return True
