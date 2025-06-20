"""
Management command para crear esquemas PostgreSQL para VENDO
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Crear todos los esquemas definidos en DATABASE_APPS_MAPPING'

    def add_arguments(self, parser):
        parser.add_argument(
            '--drop',
            action='store_true',
            help='Eliminar esquemas existentes antes de crearlos',
        )
        parser.add_argument(
            '--schema',
            type=str,
            help='Crear solo un esquema específico',
        )

    def handle(self, *args, **options):
        """Crear los esquemas necesarios para el proyecto VENDO."""
        
        # Obtener todos los esquemas únicos
        schemas = set(settings.DATABASE_APPS_MAPPING.values())
        schemas.discard('public')  # No necesitamos crear 'public'
        
        # Si se especifica un esquema específico
        if options['schema']:
            if options['schema'] in schemas:
                schemas = {options['schema']}
            else:
                self.stdout.write(
                    self.style.ERROR(f"Esquema '{options['schema']}' no encontrado en configuración")
                )
                return

        self.stdout.write(
            self.style.SUCCESS(f"Creando {len(schemas)} esquemas: {', '.join(schemas)}")
        )

        with connection.cursor() as cursor:
            for schema in schemas:
                try:
                    # Eliminar esquema si se solicita
                    if options['drop']:
                        self.stdout.write(f"Eliminando esquema '{schema}'...")
                        cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE;")
                    
                    # Crear esquema
                    self.stdout.write(f"Creando esquema '{schema}'...")
                    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
                    
                    # Otorgar permisos al usuario
                    db_user = settings.DATABASES['default']['USER']
                    cursor.execute(f"GRANT ALL ON SCHEMA {schema} TO {db_user};")
                    cursor.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {db_user};")
                    cursor.execute(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {schema} TO {db_user};")
                    cursor.execute(f"GRANT ALL ON ALL FUNCTIONS IN SCHEMA {schema} TO {db_user};")
                    
                    # Configurar permisos por defecto para objetos futuros
                    cursor.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {db_user};")
                    cursor.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON SEQUENCES TO {db_user};")
                    cursor.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON FUNCTIONS TO {db_user};")
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Esquema '{schema}' creado exitosamente")
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error creando esquema '{schema}': {e}")
                    )
                    logger.error(f"Error creando esquema {schema}: {e}")

        # Mostrar mapeo de apps a esquemas
        self.stdout.write("\n" + "="*50)
        self.stdout.write("MAPEO DE APLICACIONES A ESQUEMAS:")
        self.stdout.write("="*50)
        
        for app, schema in settings.DATABASE_APPS_MAPPING.items():
            self.stdout.write(f"  {app:<15} → {schema}")
        
        self.stdout.write("\n" + self.style.SUCCESS("✅ Configuración de esquemas completada!"))