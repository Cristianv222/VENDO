# apps/users/services.py - AGREGAR AL ARCHIVO EXISTENTE

"""
Servicios adicionales para aprobación de usuarios
"""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType

import logging

logger = logging.getLogger(__name__)


class UserApprovalService:
    """
    Servicio para manejar la aprobación de usuarios
    """
    
    @staticmethod
    def notify_admins_new_user(user):
        """
        Notifica a los administradores sobre un nuevo usuario pendiente
        """
        try:
            # Obtener todos los administradores del sistema
            from .models import User
            admins = User.objects.filter(
                models.Q(is_superuser=True) | models.Q(is_system_admin=True),
                is_active=True,
                approval_status='approved'
            ).distinct()
            
            if not admins.exists():
                logger.warning("No hay administradores activos para notificar")
                return
            
            # Preparar datos para el email
            context = {
                'user': user,
                'admin_url': f"{settings.BASE_URL if hasattr(settings, 'BASE_URL') else ''}/admin/users/user/{user.pk}/change/",
                'site_name': 'VENDO',
                'approval_url': f"{settings.BASE_URL if hasattr(settings, 'BASE_URL') else ''}/users/pending-approval/"
            }
            
            # Renderizar templates
            subject = f'[VENDO] Nuevo usuario pendiente: {user.get_full_name()}'
            html_message = render_to_string('users/emails/new_user_pending.html', context)
            plain_message = strip_tags(html_message)
            
            # Enviar email a cada admin
            admin_emails = [admin.email for admin in admins if admin.email]
            
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    html_message=html_message,
                    fail_silently=False,
                )
                
                logger.info(f"Notificación enviada a {len(admin_emails)} administradores para usuario {user.email}")
            
            # Crear log de auditoría
            UserApprovalService._create_audit_log(
                user=None,  # Sistema automático
                action='NOTIFICATION',
                obj=user,
                message=f"Notificación enviada a administradores sobre nuevo usuario pendiente"
            )
            
        except Exception as e:
            logger.error(f"Error enviando notificación de nuevo usuario: {str(e)}")
    
    @staticmethod
    def send_approval_notification(user):
        """
        Envía notificación al usuario que ha sido aprobado
        """
        try:
            if not user.email:
                logger.warning(f"Usuario {user.pk} no tiene email configurado")
                return
            
            context = {
                'user': user,
                'login_url': f"{settings.BASE_URL if hasattr(settings, 'BASE_URL') else ''}/users/login/",
                'site_name': 'VENDO',
            }
            
            subject = '[VENDO] ¡Tu cuenta ha sido aprobada!'
            html_message = render_to_string('users/emails/user_approved.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Notificación de aprobación enviada a {user.email}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de aprobación: {str(e)}")
    
    @staticmethod
    def send_rejection_notification(user, reason=''):
        """
        Envía notificación al usuario que ha sido rechazado
        """
        try:
            if not user.email:
                logger.warning(f"Usuario {user.pk} no tiene email configurado")
                return
            
            context = {
                'user': user,
                'reason': reason,
                'contact_email': settings.DEFAULT_FROM_EMAIL,
                'site_name': 'VENDO',
            }
            
            subject = '[VENDO] Información sobre tu solicitud de cuenta'
            html_message = render_to_string('users/emails/user_rejected.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Notificación de rechazo enviada a {user.email}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de rechazo: {str(e)}")
    
    @staticmethod
    def approve_user(user_to_approve, approved_by_user):
        """
        Aprueba un usuario y envía notificaciones
        """
        try:
            user_to_approve.approve_user(approved_by_user, send_notification=True)
            
            # Crear log de auditoría
            UserApprovalService._create_audit_log(
                user=approved_by_user,
                action='APPROVAL',
                obj=user_to_approve,
                message=f"Usuario aprobado por {approved_by_user.get_full_name()}"
            )
            
            return True, "Usuario aprobado exitosamente"
            
        except Exception as e:
            logger.error(f"Error aprobando usuario: {str(e)}")
            return False, f"Error al aprobar usuario: {str(e)}"
    
    @staticmethod
    def reject_user(user_to_reject, rejected_by_user, reason=''):
        """
        Rechaza un usuario y envía notificaciones
        """
        try:
            user_to_reject.reject_user(rejected_by_user, reason, send_notification=True)
            
            # Crear log de auditoría
            UserApprovalService._create_audit_log(
                user=rejected_by_user,
                action='REJECTION',
                obj=user_to_reject,
                message=f"Usuario rechazado por {rejected_by_user.get_full_name()}. Razón: {reason}"
            )
            
            return True, "Usuario rechazado exitosamente"
            
        except Exception as e:
            logger.error(f"Error rechazando usuario: {str(e)}")
            return False, f"Error al rechazar usuario: {str(e)}"
    
    @staticmethod
    def get_pending_users():
        """
        Obtiene todos los usuarios pendientes de aprobación
        """
        from .models import User
        return User.objects.filter(
            approval_status='pending',
            is_active=False
        ).order_by('-created_at')
    
    @staticmethod
    def get_pending_users_count():
        """
        Obtiene el conteo de usuarios pendientes
        """
        return UserApprovalService.get_pending_users().count()
    
    @staticmethod
    def _create_audit_log(user, action, obj, message):
        """
        Crea un log de auditoría para las acciones de aprobación
        """
        try:
            content_type = ContentType.objects.get_for_model(obj)
            
            LogEntry.objects.create(
                user_id=user.pk if user else None,
                content_type=content_type,
                object_id=obj.pk,
                object_repr=str(obj),
                action_flag=CHANGE,
                change_message=message
            )
        except Exception as e:
            logger.error(f"Error creando log de auditoría: {str(e)}")


class UserNotificationService:
    """
    Servicio para notificaciones del sistema a usuarios
    """
    
    @staticmethod
    def create_notification(user, title, message, notification_type='info', url=None):
        """
        Crea una notificación del sistema para un usuario
        Esto se puede expandir en el futuro con un modelo de Notification
        """
        # Por ahora, enviar por email
        try:
            if user.email and user.profile.email_notifications:
                context = {
                    'user': user,
                    'title': title,
                    'message': message,
                    'url': url,
                    'site_name': 'VENDO',
                }
                
                subject = f'[VENDO] {title}'
                html_message = render_to_string('users/emails/system_notification.html', context)
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=True,
                )
                
        except Exception as e:
            logger.error(f"Error enviando notificación: {str(e)}")
    
    @staticmethod
    def notify_all_admins(title, message, notification_type='info'):
        """
        Notifica a todos los administradores del sistema
        """
        from .models import User
        
        admins = User.objects.filter(
            models.Q(is_superuser=True) | models.Q(is_system_admin=True),
            is_active=True,
            approval_status='approved'
        )
        
        for admin in admins:
            UserNotificationService.create_notification(
                user=admin,
                title=title,
                message=message,
                notification_type=notification_type
            )