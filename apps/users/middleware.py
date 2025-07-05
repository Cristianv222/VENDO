# apps/users/middleware.py - CREAR ESTE ARCHIVO NUEVO

"""
Middleware para gestión automática de usuarios en sala de espera
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.utils.translation import gettext_lazy as _


class UserApprovalMiddleware:
    """
    Middleware que verifica el estado de aprobación de usuarios
    y los redirige automáticamente según su estado
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs que no requieren verificación de aprobación
        self.exempt_urls = [
            '/users/login/',
            '/users/logout/',
            '/users/waiting-room/',
            '/users/account-rejected/',
            '/users/password_reset/',
            '/users/password_reset/done/',
            '/admin/login/',
            '/admin/logout/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/robots.txt',
            '/accounts/',  # URLs de allauth
        ]
        
        # URLs que solo admins pueden acceder
        self.admin_urls = [
            '/admin/',
            '/users/pending-approval/',
            '/users/approve/',
            '/users/reject/',
        ]
    
    def __call__(self, request):
        # Procesar request
        response = self.process_request(request)
        if response:
            return response
        
        # Continuar con la vista normal
        response = self.get_response(request)
        return response
    
    def process_request(self, request):
        """
        Procesa la request antes de que llegue a la vista
        """
        # Saltar si no hay usuario autenticado
        if not request.user.is_authenticated:
            return None
        
        # Saltar para URLs exentas
        if self.is_exempt_url(request.path):
            return None
        
        # Verificar si el usuario necesita verificación de aprobación
        if not self.user_needs_approval_check(request.user):
            return None
        
        # Verificar estado de aprobación
        return self.check_user_approval_status(request)
    
    def is_exempt_url(self, path):
        """
        Verifica si la URL está exenta de verificación de aprobación
        """
        return any(path.startswith(exempt_url) for exempt_url in self.exempt_urls)
    
    def user_needs_approval_check(self, user):
        """
        Determina si el usuario necesita verificación de aprobación
        """
        # Los superusuarios y admins del sistema siempre pueden pasar
        if user.is_superuser or user.is_system_admin:
            return False
        
        # Los usuarios inactivos necesitan verificación
        return True
    
    def check_user_approval_status(self, request):
        """
        Verifica el estado de aprobación del usuario y redirige si es necesario
        """
        user = request.user
        current_path = request.path
        
        # Usuario pendiente de aprobación
        if user.is_pending_approval():
            # Si ya está en la sala de espera, no redirigir
            if current_path == reverse('users:waiting_room'):
                return None
            
            # Redirigir a sala de espera
            messages.info(
                request, 
                _('Tu cuenta está pendiente de aprobación. Te notificaremos cuando sea revisada.')
            )
            return redirect('users:waiting_room')
        
        # Usuario rechazado
        elif user.is_rejected():
            # Si ya está en la página de rechazo, no redirigir
            if current_path == reverse('users:account_rejected'):
                return None
            
            # Redirigir a página de rechazo
            messages.warning(
                request, 
                _('Tu cuenta ha sido rechazada. Contacta al administrador para más información.')
            )
            return redirect('users:account_rejected')
        
        # Usuario no aprobado (estado desconocido)
        elif not user.is_approved():
            messages.error(
                request, 
                _('Tu cuenta tiene un estado desconocido. Contacta al administrador.')
            )
            return redirect('users:login')
        
        # Usuario aprobado - verificar acceso a URLs de admin
        elif self.is_admin_url(current_path) and not self.user_can_access_admin(user):
            messages.error(
                request,
                _('No tienes permisos para acceder a esta sección.')
            )
            return HttpResponseForbidden('Acceso denegado')
        
        # Usuario está aprobado y puede continuar
        return None
    
    def is_admin_url(self, path):
        """
        Verifica si la URL requiere permisos de administrador
        """
        return any(path.startswith(admin_url) for admin_url in self.admin_urls)
    
    def user_can_access_admin(self, user):
        """
        Verifica si el usuario puede acceder a URLs de administrador
        """
        return (user.is_staff or 
                user.is_superuser or 
                user.is_system_admin or
                user.has_perm('auth.view_user'))


class PendingUsersNotificationMiddleware:
    """
    Middleware que agrega información sobre usuarios pendientes
    al contexto para administradores
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Agregar información de usuarios pendientes al request
        if (request.user.is_authenticated and 
            (request.user.is_staff or request.user.is_superuser or request.user.is_system_admin)):
            
            try:
                from .services import UserApprovalService
                pending_count = UserApprovalService.get_pending_users_count()
                request.pending_users_count = pending_count
            except Exception:
                request.pending_users_count = 0
        else:
            request.pending_users_count = 0
        
        response = self.get_response(request)
        return response