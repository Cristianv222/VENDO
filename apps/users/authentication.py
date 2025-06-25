"""
Backends de autenticación personalizados
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from .models import UserSession

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Backend que permite autenticación con email o username
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        if username is None or password is None:
            return None
        
        try:
            # Buscar por username o email
            user = User.objects.get(
                Q(username=username) | Q(email=username)
            )
        except User.DoesNotExist:
            # Ejecutar hasheo de contraseña por defecto para evitar timing attacks
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Si hay múltiples usuarios con el mismo email, usar el primero activo
            user = User.objects.filter(
                Q(username=username) | Q(email=username),
                is_active=True
            ).first()
            if not user:
                return None
        
        # Verificar contraseña y estado del usuario
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
    
    def user_can_authenticate(self, user):
        """
        Verificar si el usuario puede autenticarse
        """
        # Verificar si está activo
        if not user.is_active:
            return False
        
        # Verificar si debe cambiar contraseña
        if user.force_password_change:
            # Permitir autenticación pero marcar que debe cambiar contraseña
            pass
        
        # Verificar límite de sesiones concurrentes
        if not self._check_concurrent_sessions(user):
            return False
        
        return True
    
    def _check_concurrent_sessions(self, user, max_sessions=5):
        """
        Verificar límite de sesiones concurrentes
        """
        active_sessions = UserSession.objects.filter(
            user=user,
            logout_at__isnull=True,
            is_expired=False
        ).count()
        
        return active_sessions < max_sessions


class CompanyAwareBackend(EmailOrUsernameModelBackend):
    """
    Backend que considera el contexto de empresa
    """
    
    def authenticate(self, request, username=None, password=None, company=None, **kwargs):
        user = super().authenticate(request, username, password, **kwargs)
        
        if user and company:
            # Verificar que el usuario tenga acceso a la empresa
            if not user.has_company_access(company):
                return None
        
        return user
    
    def has_perm(self, user_obj, perm, obj=None):
        """
        Verificar permisos considerando la empresa actual
        """
        if not user_obj.is_active:
            return False
        
        if user_obj.is_system_admin:
            return True
        
        # Si hay una empresa en el contexto, verificar permisos específicos
        if hasattr(user_obj, 'current_company'):
            return user_obj.has_permission_in_company(perm, user_obj.current_company)
        
        return super().has_perm(user_obj, perm, obj)


class TokenAuthentication:
    """
    Autenticación basada en tokens para API
    """
    
    def authenticate(self, request):
        """
        Autenticar usando token en header Authorization
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            # Aquí implementarías la lógica de validación de tokens
            # Podrías usar JWT, tokens de sesión, etc.
            user = self._validate_token(token)
            if user:
                return (user, token)
        except Exception:
            pass
        
        return None
    
    def _validate_token(self, token):
        """
        Validar token y retornar usuario
        """
        # Implementación pendiente según el tipo de token usado
        # JWT, session tokens, etc.
        pass


class IPWhitelistBackend(ModelBackend):
    """
    Backend que verifica lista blanca de IPs
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Verificar IP si está configurado
        if not self._is_ip_allowed(request):
            return None
        
        return super().authenticate(request, username, password, **kwargs)
    
    def _is_ip_allowed(self, request):
        """
        Verificar si la IP está en la lista blanca
        """
        from django.conf import settings
        
        # Si no hay lista blanca configurada, permitir todo
        if not hasattr(settings, 'ALLOWED_IPS') or not settings.ALLOWED_IPS:
            return True
        
        client_ip = self._get_client_ip(request)
        
        # Verificar si la IP está en la lista blanca
        return client_ip in settings.ALLOWED_IPS
    
    def _get_client_ip(self, request):
        """
        Obtener IP del cliente
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TimeBasedAccessBackend(ModelBackend):
    """
    Backend que verifica horarios de acceso
    """
    
    def user_can_authenticate(self, user):
        """
        Verificar si el usuario puede autenticarse en este horario
        """
        if not super().user_can_authenticate(user):
            return False
        
        # Verificar horarios de acceso si están configurados
        return self._is_access_time_allowed(user)
    
    def _is_access_time_allowed(self, user):
        """
        Verificar si el horario actual está permitido para el usuario
        """
        # Aquí podrías implementar lógica de horarios por usuario/rol
        # Por ejemplo, restringir acceso nocturno para ciertos roles
        
        from django.conf import settings
        
        if not hasattr(settings, 'ACCESS_TIME_RESTRICTIONS'):
            return True
        
        current_time = timezone.now().time()
        current_day = timezone.now().weekday()
        
        # Implementar lógica específica según requirements
        return True


class LDAPBackend:
    """
    Backend para autenticación LDAP/Active Directory usando ldap3
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Autenticar contra servidor LDAP
        """
        if not self._ldap_available():
            return None
        
        try:
            # Implementar autenticación LDAP
            ldap_user = self._authenticate_ldap(username, password)
            
            if ldap_user:
                # Crear o actualizar usuario local
                user = self._get_or_create_user(ldap_user)
                return user
                
        except Exception as e:
            # Log del error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en autenticación LDAP: {e}")
        
        return None
    
    def _ldap_available(self):
        """
        Verificar si LDAP está configurado y disponible
        """
        from django.conf import settings
        return hasattr(settings, 'LDAP_SERVER_URI') and settings.LDAP_SERVER_URI
    
    def _authenticate_ldap(self, username, password):
        """
        Autenticar contra servidor LDAP usando ldap3
        """
        try:
            from ldap3 import Server, Connection
            from django.conf import settings
            
            # Crear servidor LDAP
            server = Server(
                settings.LDAP_SERVER_URI,
                use_ssl=getattr(settings, 'LDAP_USE_SSL', False),
                port=getattr(settings, 'LDAP_PORT', None)
            )
            
            # Construir DN del usuario
            user_dn = self._build_user_dn(username, settings)
            
            # Crear conexión y autenticar
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                raise_exceptions=True
            )
            
            # Si llegamos aquí, la autenticación fue exitosa
            # Buscar información adicional del usuario
            user_data = self._search_user_info(conn, username, settings)
            
            # Cerrar conexión
            conn.unbind()
            
            return user_data
            
        except ImportError:
            # ldap3 no está instalado
            import logging
            logger = logging.getLogger(__name__)
            logger.error("ldap3 no está instalado. Instalar con: pip install ldap3")
            pass
        except Exception as e:
            # Error de autenticación o conexión
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en autenticación LDAP: {e}")
            pass
        
        return None
    
    def _build_user_dn(self, username, settings):
        """
        Construir DN del usuario para autenticación
        """
        # Formato común: uid=username,ou=users,dc=example,dc=com
        user_rdn = getattr(settings, 'LDAP_USER_RDN_ATTR', 'uid')
        user_base = getattr(settings, 'LDAP_USER_BASE', 'ou=users,dc=example,dc=com')
        
        return f"{user_rdn}={username},{user_base}"
    
    def _search_user_info(self, conn, username, settings):
        """
        Buscar información adicional del usuario en LDAP
        """
        try:
            # Base de búsqueda y filtro
            search_base = getattr(settings, 'LDAP_USER_BASE', 'ou=users,dc=example,dc=com')
            user_rdn_attr = getattr(settings, 'LDAP_USER_RDN_ATTR', 'uid')
            search_filter = f"({user_rdn_attr}={username})"
            
            # Atributos a obtener
            attributes = getattr(settings, 'LDAP_USER_ATTRS', [
                'uid', 'cn', 'mail', 'givenName', 'sn', 'displayName'
            ])
            
            # Realizar búsqueda usando 2 como valor para SUBTREE
            # 2 = SUBTREE, 1 = LEVEL, 0 = BASE
            search_success = conn.search(
                search_base=search_base,
                search_filter=search_filter,
                search_scope=2,  # SUBTREE scope
                attributes=attributes
            )
            
            if search_success and conn.entries:
                # Procesar el primer resultado
                entry = conn.entries[0]
                user_data = self._extract_user_attributes(entry, attributes)
                return user_data
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al buscar información del usuario LDAP: {e}")
        
        return {'uid': username}  # Retornar al menos el username
    
    def _extract_user_attributes(self, entry, attributes):
        """
        Extraer atributos del usuario desde la entrada LDAP
        """
        user_data = {}
        
        for attr in attributes:
            try:
                # Verificar si el atributo existe en la entrada
                if hasattr(entry, attr):
                    # ldap3 devuelve objetos complejos, obtener el valor
                    attr_value = getattr(entry, attr)
                    
                    # Manejar diferentes tipos de valores
                    if hasattr(attr_value, 'value'):
                        value = attr_value.value
                        
                        # Si es una lista, tomar el primer valor
                        if isinstance(value, list) and value:
                            user_data[attr] = str(value[0])
                        elif value:
                            user_data[attr] = str(value)
                    else:
                        # Fallback para casos especiales
                        user_data[attr] = str(attr_value)
                        
            except Exception as e:
                # Si hay error con un atributo específico, continuar con los demás
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Error extrayendo atributo {attr}: {e}")
                continue
        
        return user_data
    
    def _get_or_create_user(self, ldap_user_data):
        """
        Crear o actualizar usuario local basado en datos LDAP
        """
        username = ldap_user_data.get('uid', '')
        email = ldap_user_data.get('mail', '')
        first_name = ldap_user_data.get('givenName', '')
        last_name = ldap_user_data.get('sn', '')
        display_name = ldap_user_data.get('displayName', '')
        
        # Si no hay first_name/last_name, intentar extraer de displayName
        if not first_name and not last_name and display_name:
            name_parts = display_name.split(' ', 1)
            first_name = name_parts[0]
            if len(name_parts) > 1:
                last_name = name_parts[1]
        
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'is_active': True,
            }
        )
        
        # Actualizar datos si no es nuevo
        if not created:
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.save()
        
        return user
    
    def get_user(self, user_id):
        """
        Obtener usuario por ID
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class MultiFactorAuthBackend(ModelBackend):
    """
    Backend con autenticación de dos factores (2FA)
    """
    
    def authenticate(self, request, username=None, password=None, otp_token=None, **kwargs):
        """
        Autenticar con contraseña y token OTP
        """
        # Primer paso: autenticación normal
        user = super().authenticate(request, username, password, **kwargs)
        
        if not user:
            return None
        
        # Segundo paso: verificar OTP si está habilitado
        if self._requires_2fa(user):
            if not otp_token or not self._verify_otp(user, otp_token):
                return None
        
        return user
    
    def _requires_2fa(self, user):
        """
        Verificar si el usuario requiere 2FA
        """
        # Verificar si tiene 2FA habilitado en su perfil
        if hasattr(user, 'profile') and hasattr(user.profile, 'two_factor_enabled'):
            return user.profile.two_factor_enabled
        
        # O si su rol lo requiere
        if user.is_system_admin:
            return True
        
        return False
    
    def _verify_otp(self, user, otp_token):
        """
        Verificar token OTP
        """
        # Implementar verificación usando TOTP/HOTP
        # Ejemplo con pyotp:
        try:
            import pyotp
            
            # Obtener secreto del usuario
            if hasattr(user, 'profile') and hasattr(user.profile, 'otp_secret'):
                totp = pyotp.TOTP(user.profile.otp_secret)
                return totp.verify(otp_token, valid_window=1)
                
        except ImportError:
            pass
        
        return False