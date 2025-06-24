"""
Señales para el módulo de usuarios de VENDO.
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import Group
import logging

from .models import User, UserProfile, UserSession, Role, Permission

logger = logging.getLogger('vendo.users')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Crear perfil de usuario automáticamente cuando se crea un usuario.
    """
    if created:
        try:
            UserProfile.objects.create(user=instance)
            logger.info(f"Perfil creado para usuario: {instance.username}")
            
            # Asignar rol por defecto según el tipo de usuario
            if instance.user_type == 'employee':
                try:
                    default_role = Role.objects.get(code='employee', is_active=True)
                    instance.roles.add(default_role)
                    logger.info(f"Rol por defecto asignado a {instance.username}: {default_role.name}")
                except Role.DoesNotExist:
                    logger.warning(f"Rol por defecto 'employee' no encontrado para {instance.username}")
            
            # Enviar email de bienvenida si está configurado
            if hasattr(settings, 'SEND_WELCOME_EMAIL') and settings.SEND_WELCOME_EMAIL:
                send_welcome_email(instance)
                
        except Exception as e:
            logger.error(f"Error creando perfil para {instance.username}: {str(e)}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Guardar perfil cuando se guarda el usuario.
    """
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
    except UserProfile.DoesNotExist:
        # Si no existe perfil, crearlo
        UserProfile.objects.create(user=instance)
        logger.info(f"Perfil creado tardíamente para usuario: {instance.username}")


@receiver(pre_save, sender=User)
def user_pre_save(sender, instance, **kwargs):
    """
    Acciones antes de guardar un usuario.
    """
    # Si es una actualización (no creación)
    if instance.pk:
        try:
            old_user = User.objects.get(pk=instance.pk)
            
            # Detectar cambio de estado activo/inactivo
            if old_user.is_active != instance.is_active:
                if not instance.is_active:
                    # Usuario desactivado - terminar sesiones activas
                    UserSession.objects.filter(user=instance, is_active=True).update(is_active=False)
                    logger.info(f"Sesiones terminadas para usuario desactivado: {instance.username}")
                
                logger.info(f"Estado de usuario cambiado: {instance.username} - Activo: {instance.is_active}")
            
            # Detectar cambio de email
            if old_user.email != instance.email:
                logger.info(f"Email cambiado para {instance.username}: {old_user.email} -> {instance.email}")
                
        except User.DoesNotExist:
            pass


@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """
    Manejar evento de login exitoso.
    """
    try:
        # Actualizar última actividad
        user.last_activity = timezone.now()
        user.save(update_fields=['last_activity'])
        
        # Registrar sesión
        session_key = request.session.session_key
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        UserSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent,
            location=get_location_from_ip(ip_address)
        )
        
        logger.info(f"Login exitoso: {user.username} desde {ip_address}")
        
        # Notificar login desde nueva ubicación/dispositivo (opcional)
        if should_notify_new_login(user, ip_address, user_agent):
            notify_new_login(user, ip_address, user_agent)
            
    except Exception as e:
        logger.error(f"Error en señal de login: {str(e)}")


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """
    Manejar evento de logout.
    """
    try:
        if user:
            # Marcar sesión como inactiva
            session_key = request.session.session_key
            UserSession.objects.filter(
                user=user,
                session_key=session_key,
                is_active=True
            ).update(is_active=False)
            
            logger.info(f"Logout: {user.username}")
            
    except Exception as e:
        logger.error(f"Error en señal de logout: {str(e)}")


@receiver(user_login_failed)
def user_login_failed_handler(sender, credentials, request, **kwargs):
    """
    Manejar intentos de login fallidos.
    """
    try:
        username = credentials.get('username')
        ip_address = get_client_ip(request)
        
        if username:
            try:
                user = User.objects.get(username=username)
                user.increment_failed_attempts()
                
                logger.warning(f"Login fallido: {username} desde {ip_address} - Intentos: {user.failed_login_attempts}")
                
                # Notificar si la cuenta se bloquea
                if user.is_account_locked():
                    notify_account_locked(user)
                    logger.error(f"Cuenta bloqueada: {username} por demasiados intentos fallidos")
                    
            except User.DoesNotExist:
                logger.warning(f"Intento de login con usuario inexistente: {username} desde {ip_address}")
        
    except Exception as e:
        logger.error(f"Error en señal de login fallido: {str(e)}")


@receiver(post_save, sender=Role)
def role_created(sender, instance, created, **kwargs):
    """
    Acciones al crear un nuevo rol.
    """
    if created:
        logger.info(f"Nuevo rol creado: {instance.name} ({instance.code})")
        
        # Crear grupo de Django correspondiente si no existe
        try:
            group, group_created = Group.objects.get_or_create(name=instance.name)
            if group_created:
                logger.info(f"Grupo de Django creado para rol: {instance.name}")
        except Exception as e:
            logger.error(f"Error creando grupo para rol {instance.name}: {str(e)}")


@receiver(post_delete, sender=User)
def user_deleted(sender, instance, **kwargs):
    """
    Limpiar datos relacionados cuando se elimina un usuario.
    """
    try:
        # Eliminar sesiones
        UserSession.objects.filter(user=instance).delete()
        
        logger.info(f"Usuario eliminado: {instance.username}")
        
    except Exception as e:
        logger.error(f"Error en cleanup de usuario eliminado: {str(e)}")


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def get_client_ip(request):
    """Obtener la IP real del cliente."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_location_from_ip(ip_address):
    """
    Obtener ubicación aproximada desde la IP.
    Implementación básica - puedes integrar servicios como GeoIP.
    """
    # Por ahora retornar vacío
    # En producción podrías usar:
    # - Django GeoIP2
    # - Servicios externos como ipapi.com
    return ""


def should_notify_new_login(user, ip_address, user_agent):
    """
    Determinar si se debe notificar sobre un nuevo login.
    """
    # Verificar si es la primera vez desde esta IP
    recent_sessions = UserSession.objects.filter(
        user=user,
        ip_address=ip_address,
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).exists()
    
    return not recent_sessions


def send_welcome_email(user):
    """
    Enviar email de bienvenida a nuevos usuarios.
    """
    try:
        if user.email:
            subject = f'Bienvenido a {getattr(settings, "COMPANY_NAME", "VENDO")}'
            html_message = render_to_string('emails/welcome.html', {
                'user': user,
                'company_name': getattr(settings, 'COMPANY_NAME', 'VENDO'),
                'login_url': getattr(settings, 'FRONTEND_URL', '') + '/login'
            })
            
            send_mail(
                subject=subject,
                message='',  # Texto plano vacío
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
            
            logger.info(f"Email de bienvenida enviado a: {user.email}")
            
    except Exception as e:
        logger.error(f"Error enviando email de bienvenida a {user.email}: {str(e)}")


def notify_new_login(user, ip_address, user_agent):
    """
    Notificar al usuario sobre un nuevo login.
    """
    try:
        if user.email and user.profile.email_notifications:
            subject = 'Nuevo acceso a tu cuenta'
            html_message = render_to_string('emails/new_login.html', {
                'user': user,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'login_time': timezone.now(),
                'company_name': getattr(settings, 'COMPANY_NAME', 'VENDO')
            })
            
            send_mail(
                subject=subject,
                message='',
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
            
            logger.info(f"Notificación de nuevo login enviada a: {user.email}")
            
    except Exception as e:
        logger.error(f"Error enviando notificación de nuevo login: {str(e)}")


def notify_account_locked(user):
    """
    Notificar al usuario que su cuenta ha sido bloqueada.
    """
    try:
        if user.email:
            subject = 'Cuenta bloqueada por seguridad'
            html_message = render_to_string('emails/account_locked.html', {
                'user': user,
                'max_attempts': getattr(settings, 'MAX_FAILED_LOGIN_ATTEMPTS', 5),
                'company_name': getattr(settings, 'COMPANY_NAME', 'VENDO'),
                'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@vendo.com')
            })
            
            send_mail(
                subject=subject,
                message='',
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
            
            logger.info(f"Notificación de cuenta bloqueada enviada a: {user.email}")
            
    except Exception as e:
        logger.error(f"Error enviando notificación de cuenta bloqueada: {str(e)}")


def cleanup_expired_sessions():
    """
    Limpiar sesiones expiradas.
    Esta función puede ser llamada por un comando de gestión o tarea de Celery.
    """
    try:
        expired_sessions = UserSession.objects.filter(
            last_activity__lt=timezone.now() - timezone.timedelta(
                minutes=getattr(settings, 'SESSION_TIMEOUT_MINUTES', 60)
            ),
            is_active=True
        )
        
        count = expired_sessions.count()
        expired_sessions.update(is_active=False)
        
        logger.info(f"Se marcaron {count} sesiones como expiradas")
        
        return count
        
    except Exception as e:
        logger.error(f"Error limpiando sesiones expiradas: {str(e)}")
        return 0