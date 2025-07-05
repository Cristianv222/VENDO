
"""
Comando para limpieza automática de usuarios pendientes antiguos
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.users.models import User
from apps.users.services import UserApprovalService


class Command(BaseCommand):
    help = 'Limpia usuarios pendientes muy antiguos'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Eliminar usuarios pendientes hace más de X días (por defecto: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular la eliminación sin ejecutar'
        )
        parser.add_argument(
            '--send-notification',
            action='store_true',
            help='Enviar notificación antes de eliminar'
        )
        parser.add_argument(
            '--reject-instead',
            action='store_true',
            help='Rechazar en lugar de eliminar'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        send_notification = options['send_notification']
        reject_instead = options['reject_instead']
        
        # Calcular fecha límite
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Obtener usuarios antiguos pendientes
        old_pending_users = User.objects.filter(
            approval_status='pending',
            created_at__lt=cutoff_date
        )
        
        count = old_pending_users.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ No hay usuarios pendientes anteriores a {days} días')
            )
            return
        
        self.stdout.write(f'Encontrados {count} usuarios pendientes hace más de {days} días:')
        
        # Mostrar lista
        for user in old_pending_users:
            waiting_days = (timezone.now() - user.created_at).days
            self.stdout.write(f'- {user.email} ({user.get_full_name()}) - {waiting_days} días')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No se realizaron cambios'))
            return
        
        # Confirmar acción
        if not self._confirm_action(count, days, reject_instead):
            self.stdout.write('Operación cancelada')
            return
        
        processed_count = 0
        errors = []
        
        for user in old_pending_users:
            try:
                if send_notification:
                    # Enviar notificación de limpieza
                    self._send_cleanup_notification(user, days, reject_instead)
                
                if reject_instead:
                    # Rechazar usuario
                    reason = f'Solicitud expirada después de {days} días sin revisión'
                    user.approval_status = 'rejected'
                    user.approved_at = timezone.now()
                    user.rejection_reason = reason
                    user.is_active = False
                    user.save()
                    action = 'rechazado'
                else:
                    # Eliminar usuario
                    user.delete()
                    action = 'eliminado'
                
                processed_count += 1
                self.stdout.write(f'✓ {user.email}: {action}')
                
            except Exception as e:
                errors.append(f'{user.email}: {str(e)}')
        
        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'Usuarios procesados: {processed_count}')
        
        if errors:
            self.stdout.write(f'Errores: {len(errors)}')
            for error in errors:
                self.stdout.write(self.style.ERROR(f'✗ {error}'))
        
        action_word = 'rechazados' if reject_instead else 'eliminados'
        self.stdout.write(
            self.style.SUCCESS(f'\n¡Limpieza completada! {processed_count} usuarios {action_word}.')
        )
    
    def _confirm_action(self, count, days, reject_instead):
        """Confirmar la acción con el usuario"""
        action = 'rechazar' if reject_instead else 'eliminar'
        
        response = input(f'\n¿Estás seguro de {action} {count} usuarios pendientes hace más de {days} días? [y/N]: ')
        return response.lower() in ['y', 'yes', 'sí', 'si']
    
    def _send_cleanup_notification(self, user, days, reject_instead):
        """Enviar notificación de limpieza"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            action = 'rechazada' if reject_instead else 'eliminada'
            
            subject = f'[VENDO] Solicitud de cuenta {action} por inactividad'
            message = f"""
Estimado/a {user.get_full_name()},

Tu solicitud de cuenta en el sistema VENDO ha sido {action} automáticamente 
debido a que estuvo pendiente de revisión por más de {days} días.

Si aún necesitas acceso al sistema, puedes crear una nueva solicitud.

Para cualquier consulta, contacta al administrador.

Saludos,
Sistema VENDO
            """.strip()
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            
        except Exception:
            pass  # No fallar la limpieza por errores de email