"""
Comando para configurar permisos y roles del sistema
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.utils import create_default_permissions, create_default_roles


class Command(BaseCommand):
    help = 'Configurar permisos y roles por defecto del sistema'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Resetear todos los permisos y roles (¡PELIGROSO!)',
        )
        parser.add_argument(
            '--only-permissions',
            action='store_true',
            help='Solo crear/actualizar permisos',
        )
        parser.add_argument(
            '--only-roles',
            action='store_true',
            help='Solo crear/actualizar roles',
        )
    
    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                if options['reset']:
                    self._reset_permissions_and_roles()
                
                if not options['only_roles']:
                    self._setup_permissions()
                
                if not options['only_permissions']:
                    self._setup_roles()
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error configurando permisos: {e}')
            )
            raise
    
    def _reset_permissions_and_roles(self):
        """Resetear permisos y roles (solo en desarrollo)"""
        from django.conf import settings
        from apps.users.models import Role, Permission
        
        if not settings.DEBUG:
            self.stdout.write(
                self.style.ERROR(
                    'No se puede resetear en producción. Use --settings=dev'
                )
            )
            return
        
        self.stdout.write(
            self.style.WARNING('Eliminando todos los roles y permisos...')
        )
        
        Role.objects.all().delete()
        Permission.objects.all().delete()
        
        self.stdout.write(
            self.style.SUCCESS('Roles y permisos eliminados')
        )
    
    def _setup_permissions(self):
        """Configurar permisos"""
        self.stdout.write('Creando permisos por defecto...')
        
        created_permissions = create_default_permissions()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Se crearon {len(created_permissions)} permisos nuevos'
            )
        )
        
        for permission in created_permissions:
            self.stdout.write(
                f'  ✓ {permission.module}.{permission.codename} - {permission.name}'
            )
    
    def _setup_roles(self):
        """Configurar roles"""
        self.stdout.write('Creando roles por defecto...')
        
        created_roles = create_default_roles()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Se crearon {len(created_roles)} roles nuevos'
            )
        )
        
        for role in created_roles:
            self.stdout.write(
                f'  ✓ {role.name} - {role.permissions.count()} permisos'
            )