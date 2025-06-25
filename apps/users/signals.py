"""
Señales del módulo Users
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .models import User, UserProfile, UserSession, Role, Permission
from apps.core.models import AuditLog


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Crear perfil automáticamente cuando se crea un usuario
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Guardar perfil cuando se guarda el usuario
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(pre_save, sender=User)
def user_pre_save(sender, instance, **kwargs):
    """
    Acciones antes de guardar usuario
    """
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            
            # Detectar cambio de contraseña
            if old_instance.password != instance.password:
                instance.password_changed_at = timezone.now()
            
            # Detectar cambio de estado activo
            if old_instance.is_active != instance.is_active:
                if not instance.is_active:
                    # Expirar todas las sesiones activas
                    UserSession.objects.filter(
                        user=instance,
                        logout_at__isnull=True
                    ).update(
                        is_expired=True,
                        logout_at=timezone.now()
                    )
        except User.DoesNotExist:
            pass


@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """
    Manejar inicio de sesión
    """
    # Actualizar última actividad
    user.last_activity = timezone.now()
    user.save(update_fields=['last_activity'])
    
    # Crear o actualizar sesión
    session_key = request.session.session_key
    if session_key:
        UserSession.objects.update_or_create(
            user=user,
            session_key=session_key,
            defaults={
                'ip_address': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'login_at': timezone.now(),
                'last_activity': timezone.now(),
                'is_expired': False,
                'logout_at': None,
            }
        )
    
    # Registrar en auditoría
    try:
        AuditLog.objects.create(
            user=user,
            action='LOGIN',
            object_repr=f"Inicio de sesión - {user.get_full_name()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            changes={'login_time': timezone.now().isoformat()}
        )
    except Exception:
        pass  # No fallar el login por problemas de auditoría


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """
    Manejar cierre de sesión
    """
    if user:
        session_key = request.session.session_key
        if session_key:
            # Marcar sesión como cerrada
            UserSession.objects.filter(
                user=user,
                session_key=session_key,
                logout_at__isnull=True
            ).update(
                logout_at=timezone.now()
            )
        
        # Registrar en auditoría
        try:
            AuditLog.objects.create(
                user=user,
                action='LOGOUT',
                object_repr=f"Cierre de sesión - {user.get_full_name()}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                changes={'logout_time': timezone.now().isoformat()}
            )
        except Exception:
            pass


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """
    Enviar email de bienvenida a usuarios nuevos
    """
    if created and instance.email:
        try:
            # Solo enviar si está configurado
            if hasattr(settings, 'SEND_WELCOME_EMAIL') and settings.SEND_WELCOME_EMAIL:
                subject = f'Bienvenido a {settings.SITE_NAME or "VENDO"}'
                
                html_message = render_to_string('users/emails/welcome.html', {
                    'user': instance,
                    'site_name': settings.SITE_NAME or 'VENDO',
                    'login_url': f"{settings.SITE_URL}/users/login/" if hasattr(settings, 'SITE_URL') else None
                })
                
                send_mail(
                    subject=subject,
                    message=f'Bienvenido {instance.get_full_name()}, su cuenta ha sido creada exitosamente.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instance.email],
                    html_message=html_message,
                    fail_silently=True
                )
        except Exception:
            pass  # No fallar la creación por problemas de email


@receiver(post_save, sender=Role)
def role_audit_log(sender, instance, created, **kwargs):
    """
    Registrar cambios en roles
    """
    try:
        action = 'CREATE' if created else 'UPDATE'
        AuditLog.objects.create(
            action=action,
            object_repr=f"Rol: {instance.name}",
            changes={
                'role_id': str(instance.id),
                'role_name': instance.name,
                'is_active': instance.is_active,
                'permissions_count': instance.permissions.count()
            }
        )
    except Exception:
        pass


@receiver(post_delete, sender=Role)
def role_delete_audit_log(sender, instance, **kwargs):
    """
    Registrar eliminación de roles
    """
    try:
        AuditLog.objects.create(
            action='DELETE',
            object_repr=f"Rol eliminado: {instance.name}",
            changes={
                'role_id': str(instance.id),
                'role_name': instance.name,
                'deleted_at': timezone.now().isoformat()
            }
        )
    except Exception:
        pass


@receiver(post_save, sender=Permission)
def permission_audit_log(sender, instance, created, **kwargs):
    """
    Registrar cambios en permisos
    """
    try:
        action = 'CREATE' if created else 'UPDATE'
        AuditLog.objects.create(
            action=action,
            object_repr=f"Permiso: {instance.name}",
            changes={
                'permission_id': str(instance.id),
                'permission_name': instance.name,
                'codename': instance.codename,
                'module': instance.module,
                'is_active': instance.is_active
            }
        )
    except Exception:
        pass


def get_client_ip(request):
    """
    Obtener IP del cliente
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# Limpiar sesiones expiradas automáticamente
@receiver(user_logged_in)
def cleanup_expired_sessions(sender, request, user, **kwargs):
    """
    Limpiar sesiones expiradas del usuario al iniciar sesión
    """
    try:
        # Marcar como expiradas las sesiones antiguas (más de 30 días)
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        UserSession.objects.filter(
            user=user,
            last_activity__lt=cutoff_date,
            logout_at__isnull=True
        ).update(
            is_expired=True,
            logout_at=timezone.now()
        )
    except Exception:
        pass