
"""
Comando para rechazar un usuario desde la línea de comandos
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.users.models import User
from apps.users.services import UserApprovalService


class Command(BaseCommand):
    help = 'Rechaza uno o más usuarios pendientes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'emails',
            nargs='+',
            type=str,
            help='Email(s) de los usuarios a rechazar'
        )
        parser.add_argument(
            '--reason',
            type=str,
            required=True,
            help='Motivo del rechazo'
        )
        parser.add_argument(
            '--rejected-by',
            type=str,
            help='Email del administrador que rechaza (por defecto: sistema)'
        )
        parser.add_argument(
            '--no-notification',
            action='store_true',
            help='No enviar notificación por email'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Rechazar incluso si no está en estado pendiente'
        )
    
    def handle(self, *args, **options):
        emails = options['emails']
        reason = options['reason']
        rejected_by_email = options.get('rejected_by')
        send_notification = not options.get('no_notification', False)
        force = options.get('force', False)
        
        # Obtener usuario que rechaza
        rejected_by = None
        if rejected_by_email:
            try:
                rejected_by = User.objects.get(email=rejected_by_email)
                if not (rejected_by.is_staff or rejected_by.is_superuser or rejected_by.is_system_admin):
                    raise CommandError(f'El usuario {rejected_by_email} no tiene permisos de administrador')
            except User.DoesNotExist:
                raise CommandError(f'No se encontró el usuario administrador: {rejected_by_email}')
        
        rejected_count = 0
        errors = []
        
        for email in emails:
            try:
                user = User.objects.get(email=email)
                
                # Verificar estado
                if not force and not user.is_pending_approval():
                    errors.append(f'{email}: Usuario no está pendiente (estado: {user.approval_status})')
                    continue
                
                # Rechazar usuario
                if rejected_by:
                    success, message = UserApprovalService.reject_user(
                        user_to_reject=user,
                        rejected_by_user=rejected_by,
                        reason=reason
                    )
                else:
                    # Rechazo automático del sistema
                    user.approval_status = 'rejected'
                    user.approved_at = timezone.now()
                    user.rejection_reason = reason
                    user.is_active = False
                    user.save(update_fields=['approval_status', 'approved_at', 'rejection_reason', 'is_active'])
                    
                    if send_notification:
                        UserApprovalService.send_rejection_notification(user, reason)
                    
                    success = True
                    message = 'Usuario rechazado por el sistema'
                
                if success:
                    rejected_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {email}: {message}')
                    )
                else:
                    errors.append(f'{email}: {message}')
                    
            except User.DoesNotExist:
                errors.append(f'{email}: Usuario no encontrado')
            except Exception as e:
                errors.append(f'{email}: Error - {str(e)}')
        
        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'Usuarios rechazados: {rejected_count}')
        
        if errors:
            self.stdout.write(f'Errores: {len(errors)}')
            for error in errors:
                self.stdout.write(self.style.ERROR(f'✗ {error}'))
        
        if rejected_count > 0:
            self.stdout.write(
                self.style.WARNING(f'\n¡Proceso completado! {rejected_count} usuario(s) rechazado(s).')
            )
