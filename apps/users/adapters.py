"""
Adaptadores personalizados para allauth
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.conf import settings

from .models import UserProfile
from .utils import generate_username

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Adaptador personalizado para cuentas
    """
    
    def get_login_redirect_url(self, request):
        """
        Personalizar redirección después del login
        """
        # Si el usuario tiene múltiples empresas, redirigir a selección
        if hasattr(request.user, 'get_companies'):
            companies = request.user.get_companies()
            if companies.count() > 1:
                return '/dashboard/select-company/'
            elif companies.count() == 1:
                # Auto-seleccionar empresa si solo tiene una
                company = companies.first()
                request.session['company_id'] = str(company.id)
        
        return '/dashboard/'
    
    def save_user(self, request, user, form, commit=True):
        """
        Personalizar guardado de usuario
        """
        user = super().save_user(request, user, form, commit=False)
        
        # Asegurar que el email sea único
        if User.objects.filter(email=user.email).exclude(pk=user.pk).exists():
            raise forms.ValidationError(_('Ya existe un usuario con este email.'))
        
        if commit:
            user.save()
            
            # Crear perfil automáticamente
            UserProfile.objects.get_or_create(user=user)
        
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adaptador personalizado para cuentas sociales
    """
    
    def pre_social_login(self, request, sociallogin):
        """
        Ejecutar antes del login social
        """
        # Verificar si ya existe un usuario con el mismo email
        if sociallogin.account.extra_data.get('email'):
            email = sociallogin.account.extra_data['email']
            
            try:
                existing_user = User.objects.get(email=email)
                
                # Si el usuario existe pero no tiene cuenta social, conectarla
                if not sociallogin.is_existing:
                    sociallogin.connect(request, existing_user)
                    messages.info(
                        request,
                        _('Tu cuenta de Google ha sido vinculada exitosamente.')
                    )
                
            except User.DoesNotExist:
                pass  # El usuario no existe, se creará automáticamente
    
    def save_user(self, request, sociallogin, form=None):
        """
        Personalizar creación de usuario desde datos sociales
        """
        user = super().save_user(request, sociallogin, form)
        
        # Completar información del usuario desde Google
        extra_data = sociallogin.account.extra_data
        
        # Obtener información básica
        if not user.first_name and extra_data.get('given_name'):
            user.first_name = extra_data.get('given_name', '')
        
        if not user.last_name and extra_data.get('family_name'):
            user.last_name = extra_data.get('family_name', '')
        
        # Generar username si no tiene
        if not user.username:
            user.username = generate_username(
                user.first_name or 'Usuario',
                user.last_name or 'Google',
                user.email
            )
        
        # Establecer valores por defecto para campos requeridos
        if not user.document_number:
            # Generar un documento temporal basado en el ID de Google
            google_id = extra_data.get('id', '')
            user.document_number = f"GOOGLE{google_id[-6:]}"  # Últimos 6 dígitos
        
        user.save()
        
        # Crear o actualizar perfil
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'theme': 'light',
                'language': 'es',
                'timezone': 'America/Guayaquil',
                'email_notifications': True,
            }
        )
        
        # Guardar foto de perfil si está disponible
        if extra_data.get('picture') and not user.avatar:
            try:
                self._save_avatar_from_url(user, extra_data['picture'])
            except Exception:
                pass  # No fallar si no se puede guardar la imagen
        
        return user
    
    def _save_avatar_from_url(self, user, picture_url):
        """
        Guardar avatar desde URL de Google
        """
        import requests
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        import os
        
        try:
            response = requests.get(picture_url, timeout=10)
            if response.status_code == 200:
                # Generar nombre único para el archivo
                file_name = f"avatars/google_{user.id}.jpg"
                
                # Guardar archivo
                file_content = ContentFile(response.content)
                user.avatar.save(file_name, file_content, save=True)
                
        except Exception as e:
            # Log del error pero no fallar el proceso
            print(f"Error saving avatar from Google: {e}")
    
    def get_login_redirect_url(self, request):
        """
        Personalizar redirección después del login social
        """
        # Si el usuario tiene múltiples empresas, redirigir a selección
        if hasattr(request.user, 'get_companies'):
            companies = request.user.get_companies()
            if companies.count() > 1:
                return '/dashboard/select-company/'
            elif companies.count() == 1:
                # Auto-seleccionar empresa si solo tiene una
                company = companies.first()
                request.session['company_id'] = str(company.id)
        
        return '/dashboard/'
    
    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Determinar si se permite el registro automático
        """
        # Permitir registro automático solo si está habilitado
        return getattr(settings, 'SOCIALACCOUNT_AUTO_SIGNUP', True)
    
    def populate_user(self, request, sociallogin, data):
        """
        Poblar datos del usuario desde la cuenta social
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Datos adicionales específicos de Google
        extra_data = sociallogin.account.extra_data
        
        # Verificar si el email está verificado en Google
        if extra_data.get('email_verified', False):
            user.email = extra_data.get('email', user.email)
        
        # Información adicional
        if extra_data.get('locale'):
            # Mapear locale de Google a idiomas soportados
            locale_map = {
                'es': 'es',
                'es-ES': 'es',
                'es-MX': 'es',
                'en': 'en',
                'en-US': 'en',
                'en-GB': 'en',
            }
            user.language = locale_map.get(extra_data['locale'], 'es')
        
        return user