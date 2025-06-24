"""
Permisos personalizados para el sistema VENDO
"""
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.decorators import method_decorator
from rest_framework import permissions

from .exceptions import PermissionDeniedException, InactiveCompanyException


class BasePermissionMixin:
    """
    Mixin base para verificaciones de permisos
    """
    
    def dispatch(self, request, *args, **kwargs):
        """
        Verifica permisos básicos antes de procesar la vista
        """
        # Verificar autenticación
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Verificar empresa activa
        if hasattr(request, 'company') and not request.company.is_active:
            raise InactiveCompanyException(request.company.business_name)
        
        return super().dispatch(request, *args, **kwargs)
    
    def handle_no_permission(self):
        """
        Maneja cuando el usuario no tiene permisos
        """
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': _('No tiene permisos para esta acción.')}, status=403)
        
        messages.error(self.request, _('No tiene permisos para acceder a esta página.'))
        return redirect('core:dashboard')


class CompanyPermissionMixin(BasePermissionMixin):
    """
    Mixin para verificar que el usuario pertenece a la empresa
    """
    
    def dispatch(self, request, *args, **kwargs):
        """
        Verifica que el usuario pertenece a la empresa actual
        """
        response = super().dispatch(request, *args, **kwargs)
        
        if hasattr(request, 'company') and hasattr(request.user, 'profile'):
            user_company = getattr(request.user.profile, 'company', None)
            if user_company and user_company != request.company:
                raise PermissionDeniedException(
                    permission='acceso',
                    resource=f'empresa {request.company.business_name}'
                )
        
        return response


class BranchPermissionMixin(CompanyPermissionMixin):
    """
    Mixin para verificar permisos de sucursal
    """
    
    def get_user_branches(self):
        """
        Obtiene las sucursales a las que el usuario tiene acceso
        """
        if not hasattr(self.request.user, 'profile'):
            return []
        
        user_profile = self.request.user.profile
        if hasattr(user_profile, 'branches'):
            return user_profile.branches.filter(is_active=True)
        
        return []
    
    def check_branch_permission(self, branch):
        """
        Verifica si el usuario tiene acceso a una sucursal específica
        """
        user_branches = self.get_user_branches()
        
        # Si no tiene sucursales asignadas, puede acceder a todas (superusuario)
        if not user_branches.exists():
            return True
        
        return branch in user_branches


class RolePermissionMixin(CompanyPermissionMixin):
    """
    Mixin para verificar permisos basados en roles
    """
    required_roles = []  # Lista de roles requeridos
    require_all_roles = False  # Si requiere todos los roles o solo uno
    
    def dispatch(self, request, *args, **kwargs):
        """
        Verifica roles del usuario
        """
        response = super().dispatch(request, *args, **kwargs)
        
        if self.required_roles and not self.check_user_roles():
            raise PermissionDeniedException(
                permission='rol requerido',
                resource=', '.join(self.required_roles)
            )
        
        return response
    
    def check_user_roles(self):
        """
        Verifica si el usuario tiene los roles requeridos
        """
        if not hasattr(self.request.user, 'profile'):
            return False
        
        user_roles = self.request.user.profile.roles.filter(is_active=True)
        user_role_names = [role.name for role in user_roles]
        
        if self.require_all_roles:
            return all(role in user_role_names for role in self.required_roles)
        else:
            return any(role in user_role_names for role in self.required_roles)


class ModulePermissionMixin(RolePermissionMixin):
    """
    Mixin para verificar permisos de módulo específico
    """
    required_module = None  # Módulo requerido
    required_permissions = []  # Permisos específicos requeridos
    
    def dispatch(self, request, *args, **kwargs):
        """
        Verifica permisos de módulo
        """
        response = super().dispatch(request, *args, **kwargs)
        
        if self.required_module and not self.check_module_permission():
            raise PermissionDeniedException(
                permission='acceso al módulo',
                resource=self.required_module
            )
        
        return response
    
    def check_module_permission(self):
        """
        Verifica si el usuario tiene acceso al módulo
        """
        if not hasattr(self.request.user, 'profile'):
            return False
        
        user_profile = self.request.user.profile
        
        # Verificar si tiene permisos específicos del módulo
        if self.required_permissions:
            user_permissions = user_profile.get_all_permissions()
            for permission in self.required_permissions:
                if permission not in user_permissions:
                    return False
        
        return True


# Mixins específicos para diferentes módulos

class POSPermissionMixin(ModulePermissionMixin):
    """
    Mixin para permisos del módulo POS
    """
    required_module = 'pos'
    required_roles = ['vendedor', 'cajero', 'supervisor']


class InventoryPermissionMixin(ModulePermissionMixin):
    """
    Mixin para permisos del módulo de inventario
    """
    required_module = 'inventory'
    required_roles = ['inventarista', 'supervisor', 'administrador']


class InvoicingPermissionMixin(ModulePermissionMixin):
    """
    Mixin para permisos del módulo de facturación
    """
    required_module = 'invoicing'
    required_roles = ['facturador', 'contador', 'administrador']


class ReportsPermissionMixin(ModulePermissionMixin):
    """
    Mixin para permisos del módulo de reportes
    """
    required_module = 'reports'
    required_roles = ['supervisor', 'contador', 'administrador']


class SettingsPermissionMixin(ModulePermissionMixin):
    """
    Mixin para permisos del módulo de configuraciones
    """
    required_module = 'settings'
    required_roles = ['administrador']
    require_all_roles = True


# Decoradores para funciones

def company_required(view_func):
    """
    Decorador que requiere que el usuario tenga una empresa asignada
    """
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request, 'company') or not request.company:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': _('Empresa requerida.')}, status=403)
            messages.error(request, _('Debe seleccionar una empresa.'))
            return redirect('core:select_company')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def role_required(*roles, require_all=False):
    """
    Decorador que requiere roles específicos
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'profile'):
                raise PermissionDeniedException()
            
            user_roles = request.user.profile.roles.filter(is_active=True)
            user_role_names = [role.name for role in user_roles]
            
            if require_all:
                has_permission = all(role in user_role_names for role in roles)
            else:
                has_permission = any(role in user_role_names for role in roles)
            
            if not has_permission:
                raise PermissionDeniedException(
                    permission='rol',
                    resource=', '.join(roles)
                )
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def branch_access_required(view_func):
    """
    Decorador que verifica acceso a sucursal
    """
    def _wrapped_view(request, *args, **kwargs):
        branch_id = kwargs.get('branch_id') or request.GET.get('branch_id')
        
        if branch_id and hasattr(request.user, 'profile'):
            from .models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
                user_branches = request.user.profile.branches.filter(is_active=True)
                
                if user_branches.exists() and branch not in user_branches:
                    raise PermissionDeniedException(
                        permission='acceso a sucursal',
                        resource=branch.name
                    )
            except Branch.DoesNotExist:
                raise PermissionDeniedException(permission='sucursal', resource='inexistente')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# Permisos para DRF (Django REST Framework)

class IsAuthenticatedAndActive(permissions.BasePermission):
    """
    Permiso que requiere usuario autenticado y activo
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active
        )


class HasCompanyAccess(permissions.BasePermission):
    """
    Permiso que requiere acceso a la empresa
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return (
            hasattr(request, 'company') and
            request.company and
            request.company.is_active
        )


class HasModulePermission(permissions.BasePermission):
    """
    Permiso basado en módulos
    """
    required_module = None
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        # Verificar si tiene acceso al módulo
        module = getattr(view, 'required_module', self.required_module)
        if module:
            user_modules = request.user.profile.get_accessible_modules()
            return module in user_modules
        
        return True


class HasRolePermission(permissions.BasePermission):
    """
    Permiso basado en roles
    """
    required_roles = []
    require_all = False
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        roles = getattr(view, 'required_roles', self.required_roles)
        if not roles:
            return True
        
        user_roles = request.user.profile.roles.filter(is_active=True)
        user_role_names = [role.name for role in user_roles]
        
        require_all = getattr(view, 'require_all_roles', self.require_all)
        
        if require_all:
            return all(role in user_role_names for role in roles)
        else:
            return any(role in user_role_names for role in roles)