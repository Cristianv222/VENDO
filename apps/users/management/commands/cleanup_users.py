"""
Comando para limpiar usuarios y sesiones
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.users.models import User, UserSession
from apps.users.utils import cleanup_expired_sessions


class Command(BaseCommand):
    help = 'Limpiar usuarios inactivos y sesiones expiradas'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days-inactive',
            type=int,
            default=90,
            help='Días de inactividad para considerar usuarios inactivos (default: 90)',
        )
        parser.add_argument(
            '--days-sessions',
            type=int,
            default=30,
            help='Días para limpiar sesiones antiguas (default: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se haría, sin hacer cambios',
        )
        parser.add_argument(
            '--deactivate-users',
            action='store_true',
            help='Desactivar usuarios inactivos (no los elimina)',
        )
    
    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        
        # Limpiar sesiones expiradas
        self._cleanup_sessions(options['days_sessions'])
        
        # Manejar usuarios inactivos
        if options['deactivate_users']:
            self._deactivate_inactive_users(options['days_inactive'])
        
        self.stdout.write(self.style.SUCCESS('Limpieza completada'))
    
    def _cleanup_sessions(self, days):
        """Limpiar sesiones expiradas"""
        expired_count = cleanup_expired_sessions(days)
        
        if self.dry_run:
            self.stdout.write(
                f'Se limpiarían {expired_count} sesiones expiradas'
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Se limpiaron {expired_count} sesiones expiradas'
                )
            )
    
    def _deactivate_inactive_users(self, days):
        """Desactivar usuarios inactivos"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        inactive_users = User.objects.filter(
            is_active=True,
            is_system_admin=False,
            last_activity__lt=cutoff_date
        ).exclude(
            last_login__isnull=True  # No desactivar usuarios que nunca iniciaron sesión
        )
        
        count = inactive_users.count()
        
        if self.dry_run:
            self.stdout.write(
                f'Se desactivarían {count} usuarios inactivos por más de {days} días'
            )
            for user in inactive_users[:10]:  # Mostrar solo los primeros 10
                self.stdout.write(
                    f'  - {user.get_full_name()} ({user.email}) - '
                    f'Última actividad: {user.last_activity}'
                )
            if count > 10:
                self.stdout.write(f'  ... y {count - 10} más')
        else:
            inactive_users.update(is_active=False)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Se desactivaron {count} usuarios inactivos'
                )
            )