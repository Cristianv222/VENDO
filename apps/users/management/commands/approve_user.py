"""
Comando para aprobar un usuario desde la línea de comandos
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.users.models import User
from apps.users.services import UserApprovalService


class Command(BaseCommand):
    help = 'Aprueba uno o más usuarios pendientes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'emails',
            nargs='+',
            type=str,
            help='Email(s) de los usuarios a aprobar'
        )
        parser.add_argument(
            '--approved-by',
            type=str,
            help='Email del administrador que aprueba (por defecto: sistema)'
        )
        parser.add_argument(
            '--no-notification',
            action='store_true',
            help='No enviar notificación por email'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Aprobar incluso si no está en estado pendiente'
        )
    
    def handle(self, *args, **options):
        emails = options['emails']
        approved_by_email = options.get('approved_by')
        send_notification = not options.get('no_notification', False)
        force = options.get('force', False)
        
        # Obtener usuario que aprueba
        approved_by = None
        if approved_by_email:
            try:
                approved_by = User.objects.get(email=approved_by_email)
                if not (approved_by.is_staff or approved_by.is_superuser or approved_by.is_system_admin):
                    raise CommandError(f'El usuario {approved_by_email} no tiene permisos de administrador')
            except User.DoesNotExist:
                raise CommandError(f'No se encontró el usuario administrador: {approved_by_email}')
        
        approved_count = 0
        errors = []
        
        for email in emails:
            try:
                user = User.objects.get(email=email)
                
                # Verificar estado
                if not force and not user.is_pending_approval():
                    errors.append(f'{email}: Usuario no está pendiente (estado: {user.approval_status})')
                    continue
                
                # Aprobar usuario
                if approved_by:
                    success, message = UserApprovalService.approve_user(
                        user_to_approve=user,
                        approved_by_user=approved_by
                    )
                else:
                    # Aprobación automática del sistema
                    user.approval_status = 'approved'
                    user.approved_at = timezone.now()
                    user.is_active = True
                    user.save(update_fields=['approval_status', 'approved_at', 'is_active'])
                    
                    if send_notification:
                        UserApprovalService.send_approval_notification(user)
                    
                    success = True
                    message = 'Usuario aprobado por el sistema'
                
                if success:
                    approved_count += 1
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
        self.stdout.write(f'Usuarios aprobados: {approved_count}')
        
        if errors:
            self.stdout.write(f'Errores: {len(errors)}')
            for error in errors:
                self.stdout.write(self.style.ERROR(f'✗ {error}'))
        
        if approved_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\n¡Proceso completado! {approved_count} usuario(s) aprobado(s).')
            )