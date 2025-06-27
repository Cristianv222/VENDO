# config/db_router.py - VERSIÓN ARREGLADA
"""
Database Router Universal para VENDO - VERSIÓN ARREGLADA
Soluciona el problema de post-migrate handlers
"""

from django.conf import settings
from django.db import connection
import logging

logger = logging.getLogger(__name__)

class SchemaRouter:
    """
    Router universal que maneja TODOS los esquemas de VENDO
    VERSIÓN ARREGLADA - No interfiere con post-migrate handlers
    """
    
    def __init__(self):
        # Tracker para evitar mensajes repetitivos
        self._migration_messages_shown = set()
    
    # Mapeo de prioridades de search_path por esquema
    SCHEMA_SEARCH_PATHS = {
        'vendo_core': 'vendo_core, public',
        'vendo_inventory': 'vendo_inventory, vendo_core, public',
        'vendo_pos': 'vendo_pos, vendo_core, public',
        'vendo_invoicing': 'vendo_invoicing, vendo_core, public',
        'vendo_purchases': 'vendo_purchases, vendo_core, public',
        'vendo_accounting': 'vendo_accounting, vendo_core, public',
        'vendo_quotations': 'vendo_quotations, vendo_core, public',
        'vendo_reports': 'vendo_reports, vendo_core, vendo_inventory, vendo_pos, vendo_invoicing, vendo_purchases, vendo_accounting, public',
        'public': 'public'
    }
    
    # Solo mostrar mensajes para estas apps
    IMPORTANT_APPS = ['inventory', 'pos', 'invoicing', 'purchases', 'accounting', 'quotations', 'reports']

    def _get_schema_for_app(self, app_label):
        """Obtener el esquema para una aplicación específica."""
        try:
            mapping = getattr(settings, 'DATABASE_APPS_MAPPING', {})
            schema = mapping.get(app_label, 'public')
            return schema
        except Exception as e:
            logger.error(f"Error obteniendo esquema para {app_label}: {e}")
            return 'public'

    def _set_search_path(self, schema_name, context="operation", app_label=None):
        """Establecer el search_path optimizado para el esquema específico."""
        try:
            if not schema_name:
                schema_name = 'public'
            
            # ✅ ARREGLO: Para operaciones de Django core, usar search_path completo
            if app_label in ['admin', 'auth', 'contenttypes', 'sessions'] or context == "POST_MIGRATE":
                search_path = "vendo_core, public"
            else:
                # Obtener el search_path específico para este esquema
                search_path = self.SCHEMA_SEARCH_PATHS.get(schema_name, f"{schema_name}, public")
            
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {search_path}")
                
                # ✅ SOLO MOSTRAR MENSAJE UNA VEZ POR APP IMPORTANTE
                if (context.startswith("MIGRACIÓN") and 
                    app_label in self.IMPORTANT_APPS and 
                    app_label not in self._migration_messages_shown):
                    
                    print(f"🎯 CONFIGURANDO: '{app_label}' → Esquema '{schema_name}'")
                    print(f"   📍 Search path: {search_path}")
                    self._migration_messages_shown.add(app_label)
                        
        except Exception as e:
            # Solo mostrar errores importantes
            if app_label in self.IMPORTANT_APPS:
                print(f"⚠️  Error configurando search_path para {schema_name}: {e}")

    def db_for_read(self, model, **hints):
        """Dirigir las operaciones de lectura al esquema apropiado."""
        try:
            app_label = model._meta.app_label
            schema = self._get_schema_for_app(app_label)
            
            # ✅ ARREGLO: Para apps core de Django, usar esquema adecuado
            if app_label in ['admin', 'auth', 'contenttypes', 'sessions']:
                self._set_search_path('vendo_core', "READ_CORE", app_label)
            else:
                self._set_search_path(schema, "READ", app_label)
                
            return 'default'
        except Exception as e:
            logger.error(f"Error en db_for_read: {e}")
            return 'default'

    def db_for_write(self, model, **hints):
        """Dirigir las operaciones de escritura al esquema apropiado."""
        try:
            app_label = model._meta.app_label
            schema = self._get_schema_for_app(app_label)
            
            # ✅ ARREGLO: Para apps core de Django, usar esquema adecuado  
            if app_label in ['admin', 'auth', 'contenttypes', 'sessions']:
                self._set_search_path('vendo_core', "WRITE_CORE", app_label)
            else:
                self._set_search_path(schema, "WRITE", app_label)
                
            return 'default'
        except Exception as e:
            logger.error(f"Error en db_for_write: {e}")
            return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Permitir relaciones entre modelos."""
        try:
            if not obj1 or not obj2:
                return True
                
            app1 = obj1._meta.app_label
            app2 = obj2._meta.app_label
            
            schema1 = self._get_schema_for_app(app1)
            schema2 = self._get_schema_for_app(app2)
            
            # Mismo esquema - siempre permitido
            if schema1 == schema2:
                return True
                
            # Relaciones con core - siempre permitidas
            if schema1 == 'vendo_core' or schema2 == 'vendo_core':
                return True
                
            # Apps de Django core - siempre permitidas
            django_apps = ['admin', 'auth', 'contenttypes', 'sessions']
            if app1 in django_apps or app2 in django_apps:
                return True
                
            # Reports puede relacionarse con todo
            if schema1 == 'vendo_reports' or schema2 == 'vendo_reports':
                return True
                
            # Esquemas de negocio pueden relacionarse entre sí
            business_schemas = ['vendo_inventory', 'vendo_pos', 'vendo_invoicing', 
                              'vendo_purchases', 'vendo_accounting', 'vendo_quotations']
            if schema1 in business_schemas and schema2 in business_schemas:
                return True
                
            return None
            
        except:
            return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Permitir migraciones según el esquema correspondiente.
        VERSIÓN ARREGLADA - Maneja correctamente post-migrate
        """
        try:
            if db != 'default':
                return False
            
            # Obtener el esquema para esta app
            schema = self._get_schema_for_app(app_label)
            
            # Crear el esquema si no existe
            self._ensure_schema_exists(schema)
            
            # ✅ ARREGLO: Para apps de Django core, usar vendo_core
            if app_label in ['admin', 'auth', 'contenttypes', 'sessions']:
                self._set_search_path('vendo_core', f"MIGRACIÓN", app_label)
            else:
                # Configurar el search_path antes de la migración
                self._set_search_path(schema, f"MIGRACIÓN", app_label)
            
            return True
            
        except Exception as e:
            # Solo mostrar errores para apps importantes
            if app_label in self.IMPORTANT_APPS:
                print(f"❌ Error en allow_migrate para {app_label}: {e}")
            return True

    def _ensure_schema_exists(self, schema_name):
        """Asegurar que el esquema existe antes de usarlo."""
        try:
            if schema_name and schema_name != 'public':
                with connection.cursor() as cursor:
                    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        except Exception as e:
            logger.error(f"Error creando esquema {schema_name}: {e}")


# ==========================================
# FUNCIONES UTILITARIAS MEJORADAS
# ==========================================

def reset_search_path_to_core():
    """Resetea el search path a vendo_core para operaciones normales"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO vendo_core, public;")
            print("✅ Search path reseteado a vendo_core, public")
    except Exception as e:
        print(f"❌ Error reseteando search path: {e}")

def verify_inventory_tables():
    """Verificación rápida de tablas de inventory"""
    print("🔍 VERIFICANDO INVENTORY...")
    
    try:
        with connection.cursor() as cursor:
            # Resetear search path para buscar correctamente
            cursor.execute("SET search_path TO vendo_inventory, vendo_core, public;")
            
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'vendo_inventory'
                ORDER BY table_name;
            """)
            
            tables = cursor.fetchall()
            
            if not tables:
                print("❌ No se encontraron tablas en vendo_inventory")
                return False
            
            print(f"✅ {len(tables)} tablas encontradas en vendo_inventory:")
            for (table,) in tables:
                print(f"  📄 {table}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False