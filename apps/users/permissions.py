"""
Permisos personalizados del módulo Users
"""
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions

from .models import User, Role, Permission


class RoleRequiredMixin(UserPassesTestMixin):
    """
    Mixin que requiere que el usuario tenga un rol específico
    """
    required_role = None
    company_required = True
    
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        
        if self.request.user.is_system_admin:
            return True
        
        if self.company_required and not hasattr(self.request, 'company'):
            return False
        
        if self.required_role:
            return self.request.user.has_permission_in_company(
                self.required_role,
                getattr(self.request, 'company', None)
            )
        
        return True
    
    def handle_no_permission(self):
        messages.error(
            self.request,
            _('No tiene permisos para acceder a esta página.')
        )
        return redirect('core:dashboard')


class PermissionRequiredMixin(UserPassesTestMixin):
    """
    Mixin que requiere que el usuario tenga un permiso específico
    """
    required_permission = None
    company_required = True
    
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        
        if self.request.user.is_system_admin:
            return True
        
        if self.company_required and not hasattr(self.request, 'company'):
            return False
        
        if self.required_permission:
            return self.request.user.has_permission_in_company(
                self.required_permission,
                getattr(self.request, 'company', None)
            )
        
        return True
    
    def handle_no_permission(self):
        messages.error(
            self.request,
            _('No tiene permisos para realizar esta acción.')
        )
        return redirect('core:dashboard')


class UserManagementPermissionMixin(PermissionRequiredMixin):
    """
    Mixin para permisos de gestión de usuarios
    """
    required_permission = 'users.manage_users'


class RoleManagementPermissionMixin(PermissionRequiredMixin):
    """
    Mixin para permisos de gestión de roles
    """
    required_permission = 'users.manage_roles'


class SystemAdminRequiredMixin(UserPassesTestMixin):
    """
    Mixin que requiere ser administrador del sistema
    """
    def test_func(self):
        return (
            self.request.user.is_authenticated and 
            self.request.user.is_system_admin
        )
    
    def handle_no_permission(self):
        messages.error(
            self.request,
            _('Solo los administradores del sistema pueden acceder a esta página.')
        )
        return redirect('core:dashboard')


class OwnProfileOrAdminMixin(UserPassesTestMixin):
    """
    Mixin que permite acceso solo al propio perfil o a administradores
    """
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        
        if self.request.user.is_system_admin:
            return True
        
        # Verificar si es su propio perfil
        user_id = self.kwargs.get('pk')
        if user_id:
            return str(self.request.user.id) == str(user_id)
        
        return True
    
    def handle_no_permission(self):
        messages.error(
            self.request,
            _('Solo puede acceder a su propio perfil.')
        )
        return redirect('users:profile')


# Decoradores de función
def role_required(role_name, company_required=True):
    """
    Decorador que requiere un rol específico
    """
    def check_role(user):
        if not user.is_authenticated:
            return False
        
        if user.is_system_admin:
            return True
        
        if company_required and not hasattr(user, 'company'):
            return False
        
        return user.has_permission_in_company(
            role_name,
            getattr(user, 'company', None)
        )
    
    return user_passes_test(check_role)


def permission_required(permission_name, company_required=True):
    """
    Decorador que requiere un permiso específico
    """
    def check_permission(user):
        if not user.is_authenticated:
            return False
        
        if user.is_system_admin:
            return True
        
        if company_required and not hasattr(user, 'company'):
            return False
        
        return user.has_permission_in_company(
            permission_name,
            getattr(user, 'company', None)
        )
    
    return user_passes_test(check_permission)


def system_admin_required(user):
    """
    Decorador que requiere ser administrador del sistema
    """
    return user.is_authenticated and user.is_system_admin


def own_profile_or_admin_required(user):
    """
    Decorador para acceso a perfil propio o admin
    """
    return user.is_authenticated and (user.is_system_admin or user == user)


# Permisos para DRF
class IsSystemAdmin(permissions.BasePermission):
    """
    Permiso que solo permite acceso a administradores del sistema
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_system_admin
        )


class HasCompanyAccess(permissions.BasePermission):
    """
    Permiso que verifica acceso a la empresa actual
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_system_admin:
            return True
        
        if not hasattr(request, 'company'):
            return False
        
        return request.user.has_company_access(request.company)


class HasModulePermission(permissions.BasePermission):
    """
    Permiso que verifica permisos específicos del módulo
    """
    required_permission = None
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_system_admin:
            return True
        
        if not hasattr(request, 'company'):
            return False
        
        permission = getattr(view, 'required_permission', self.required_permission)
        if permission:
            return request.user.has_permission_in_company(
                permission,
                request.company
            )
        
        return True


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permiso que permite acceso solo al propietario del objeto o admin
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_system_admin:
            return True
        
        # Verificar si el objeto tiene un campo 'user'
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Si el objeto es un usuario, verificar si es el mismo
        if isinstance(obj, User):
            return obj == request.user
        
        return False