"""
Señales para auditoría automática del sistema VENDO
"""
import json
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .models import Company, Branch, AuditLog
from .utils import get_client_ip


def get_current_user():
    """
    Obtiene el usuario actual del hilo de ejecución
    """
    import threading
    return getattr(threading.current_thread(), 'user', None)


def get_current_company():
    """
    Obtiene la empresa actual del hilo de ejecución
    """
    import threading
    return getattr(threading.current_thread(), 'company', None)


def set_current_user(user):
    """
    Establece el usuario actual en el hilo de ejecución
    """
    import threading
    threading.current_thread().user = user


def set_current_company(company):
    """
    Establece la empresa actual en el hilo de ejecución
    """
    import threading
    threading.current_thread().company = company


class AuditableMixin:
    """
    Mixin para modelos que requieren auditoría
    """
    _audit_enabled = True
    _audit_fields_exclude = ['updated_at', 'created_at']
    
    def get_audit_fields(self):
        """
        Obtiene los campos que se deben auditar
        """
        fields = []
        for field in self._meta.fields:
            if field.name not in self._audit_fields_exclude:
                fields.append(field.name)
        return fields
    
    def get_field_value(self, field_name):
        """
        Obtiene el valor de un campo de forma segura
        """
        try:
            value = getattr(self, field_name)
            # Serializar valores complejos
            if hasattr(value, 'id'):  # ForeignKey
                return {'id': str(value.id), 'str': str(value)}
            elif isinstance(value, (list, dict)):
                return value
            else:
                return str(value) if value is not None else None
        except Exception:
            return None


@receiver(pre_save)
def capture_old_values(sender, instance, **kwargs):
    """
    Captura los valores anteriores del objeto antes de guardarlo
    """
    # Solo auditar modelos que hereden de AuditableMixin
    if not isinstance(instance, AuditableMixin) or not instance._audit_enabled:
        return
    
    # Saltar auditoría para el mismo AuditLog
    if sender == AuditLog:
        return
    
    # Solo para actualizaciones (no creaciones)
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_values = {}
            
            for field_name in instance.get_audit_fields():
                instance._old_values[field_name] = old_instance.get_field_value(field_name)
        except sender.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save)
def log_model_changes(sender, instance, created, **kwargs):
    """
    Registra cambios en modelos auditables
    """
    # Solo auditar modelos que hereden de AuditableMixin
    if not isinstance(instance, AuditableMixin) or not instance._audit_enabled:
        return
    
    # Saltar auditoría para el mismo AuditLog
    if sender == AuditLog:
        return
    
    user = get_current_user()
    company = get_current_company()
    
    # Si no hay usuario o empresa, no auditar
    if not user or not company:
        return
    
    try:
        content_type = ContentType.objects.get_for_model(sender)
        action = 'CREATE' if created else 'UPDATE'
        
        # Calcular cambios
        changes = {}
        if created:
            # Para nuevos objetos, registrar todos los campos
            for field_name in instance.get_audit_fields():
                value = instance.get_field_value(field_name)
                if value is not None:
                    changes[field_name] = {'new': value}
        else:
            # Para actualizaciones, comparar con valores anteriores
            old_values = getattr(instance, '_old_values', {})
            for field_name in instance.get_audit_fields():
                old_value = old_values.get(field_name)
                new_value = instance.get_field_value(field_name)
                
                # Solo registrar si cambió
                if old_value != new_value:
                    changes[field_name] = {
                        'old': old_value,
                        'new': new_value
                    }
        
        # Solo crear log si hay cambios
        if changes or created:
            AuditLog.objects.create(
                user=user,
                company=company,
                action=action,
                content_type=content_type,
                object_id=str(instance.pk),
                object_repr=str(instance)[:200],
                changes=changes
            )
    
    except Exception as e:
        # Log del error sin interrumpir el flujo principal
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creando audit log: {e}")


@receiver(post_delete)
def log_model_deletion(sender, instance, **kwargs):
    """
    Registra eliminaciones de modelos auditables
    """
    # Solo auditar modelos que hereden de AuditableMixin
    if not isinstance(instance, AuditableMixin) or not instance._audit_enabled:
        return
    
    # Saltar auditoría para el mismo AuditLog
    if sender == AuditLog:
        return
    
    user = get_current_user()
    company = get_current_company()
    
    # Si no hay usuario o empresa, no auditar
    if not user or not company:
        return
    
    try:
        content_type = ContentType.objects.get_for_model(sender)
        
        # Capturar valores del objeto eliminado
        changes = {}
        for field_name in instance.get_audit_fields():
            value = instance.get_field_value(field_name)
            if value is not None:
                changes[field_name] = {'deleted': value}
        
        AuditLog.objects.create(
            user=user,
            company=company,
            action='DELETE',
            content_type=content_type,
            object_id=str(instance.pk),
            object_repr=str(instance)[:200],
            changes=changes
        )
    
    except Exception as e:
        # Log del error sin interrumpir el flujo principal
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creando audit log para eliminación: {e}")


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Registra cuando un usuario inicia sesión
    """
    try:
        # Intentar obtener la empresa del usuario
        company = None
        if hasattr(user, 'profile') and user.profile and user.profile.company:
            company = user.profile.company
        elif hasattr(request, 'company'):
            company = request.company
        
        # Crear log de login
        audit_data = {
            'user': user,
            'action': 'LOGIN',
            'object_repr': f"Login de {user.username}",
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'changes': {
                'login_time': timezone.now().isoformat(),
                'session_key': request.session.session_key,
            }
        }
        
        if company:
            audit_data['company'] = company
        
        AuditLog.objects.create(**audit_data)
        
        # Establecer usuario en el hilo actual para futuras auditorías
        set_current_user(user)
        if company:
            set_current_company(company)
    
    except Exception as e:
        # Log del error sin interrumpir el login
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creando audit log para login: {e}")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Registra cuando un usuario cierra sesión
    """
    try:
        # Solo si hay usuario (puede ser None en algunos casos)
        if not user:
            return
        
        # Intentar obtener la empresa
        company = None
        if hasattr(user, 'profile') and user.profile and user.profile.company:
            company = user.profile.company
        elif hasattr(request, 'company'):
            company = request.company
        
        # Crear log de logout
        audit_data = {
            'user': user,
            'action': 'LOGOUT',
            'object_repr': f"Logout de {user.username}",
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'changes': {
                'logout_time': timezone.now().isoformat(),
            }
        }
        
        if company:
            audit_data['company'] = company
        
        AuditLog.objects.create(**audit_data)
    
    except Exception as e:
        # Log del error sin interrumpir el logout
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creando audit log para logout: {e}")


@receiver(post_save, sender=Company)
def company_post_save(sender, instance, created, **kwargs):
    """
    Acciones después de guardar una empresa
    """
    if created:
        try:
            # Crear esquema de base de datos para la nueva empresa
            from .utils import create_schema
            create_schema(instance.schema_name)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creando esquema para empresa {instance.ruc}: {e}")


@receiver(post_save, sender=Branch)
def branch_post_save(sender, instance, created, **kwargs):
    """
    Acciones después de guardar una sucursal
    """
    if created:
        try:
            # Si es la primera sucursal, marcarla como principal
            if not Branch.objects.filter(
                company=instance.company,
                is_main=True
            ).exclude(id=instance.id).exists():
                instance.is_main = True
                instance.save()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error configurando sucursal principal: {e}")


# Middleware personalizado para capturar usuario y empresa
class AuditMiddleware:
    """
    Middleware para capturar usuario y empresa para auditoría
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Establecer usuario y empresa en el hilo actual
        if request.user.is_authenticated:
            set_current_user(request.user)
            
            if hasattr(request, 'company'):
                set_current_company(request.company)
        
        response = self.get_response(request)
        
        # Limpiar el hilo después de la request
        set_current_user(None)
        set_current_company(None)
        
        return response