"""
Permisos personalizados para el módulo de usuarios de VENDO.
"""

from rest_framework import permissions
from django.contrib.auth.models import Permission as DjangoPermission


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permiso que permite acceso solo al propietario del objeto o administradores.
    """
    
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura para cualquier usuario autenticado
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Permisos de escritura solo para el propietario o administradores
        return obj == request.user or request.user.is_staff or request.user.is_superuser


class CanManageUsers(permissions.BasePermission):
    """
    Permiso para gestionar usuarios.
    Solo administradores o usuarios con permisos específicos.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Verificar si tiene el permiso específico
        if request.user.has_permission('admin_users'):
            return True
        
        # Verificar permisos Django tradicionales
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('users.view_user')
        
        if request.method == 'POST':
            return request.user.has_perm('users.add_user')
        
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('users.change_user')
        
        if request.method == 'DELETE':
            return request.user.has_perm('users.delete_user')
        
        return False

    def has_object_permission(self, request, view, obj):
        # Los usuarios pueden ver y editar su propio perfil
        if obj == request.user:
            return True
        
        return self.has_permission(request, view)


class CanManageRoles(permissions.BasePermission):
    """
    Permiso para gestionar roles.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Verificar si tiene rol de administrador
        if request.user.has_role('admin'):
            return True
        
        # Verificar permisos específicos
        return request.user.has_permission('admin_users')


class CanViewReports(permissions.BasePermission):
    """
    Permiso para ver reportes.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Verificar permisos de reportes
        return request.user.has_permission('reports_view')


class CanAccessPOS(permissions.BasePermission):
    """
    Permiso para acceder al módulo POS.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Verificar permisos POS
        return (
            request.user.is_superuser or
            request.user.has_permission('pos_view') or
            request.user.has_role('cashier') or
            request.user.has_role('admin') or
            request.user.has_role('manager')
        )


class CanManageInventory(permissions.BasePermission):
    """
    Permiso para gestionar inventario.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Verificar roles específicos
        if request.user.has_role('inventory_manager') or request.user.has_role('admin'):
            return True
        
        # Verificar permisos específicos según el método
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_permission('inventory_view')
        
        if request.method == 'POST':
            return request.user.has_permission('inventory_create')
        
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_permission('inventory_edit')
        
        if request.method == 'DELETE':
            return request.user.has_permission('inventory_delete')
        
        return False


class CanManageInvoicing(permissions.BasePermission):
    """
    Permiso para gestionar facturación.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Verificar roles específicos
        if (request.user.has_role('admin') or 
            request.user.has_role('accountant') or
            request.user.has_role('manager')):
            return True
        
        # Verificar permisos específicos según el método
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_permission('invoice_view')
        
        if request.method == 'POST':
            return request.user.has_permission('invoice_create')
        
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_permission('invoice_edit')
        
        return False


class CanAccessAccounting(permissions.BasePermission):
    """
    Permiso para acceder al módulo de contabilidad.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Solo contadores, administradores y gerentes
        return (
            request.user.has_role('accountant') or
            request.user.has_role('admin') or
            request.user.has_role('manager')
        )


class CanManageSettings(permissions.BasePermission):
    """
    Permiso para gestionar configuraciones del sistema.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Solo superusuarios y administradores
        return (
            request.user.is_superuser or
            request.user.has_role('admin') or
            request.user.has_permission('admin_settings')
        )


class IsActiveUser(permissions.BasePermission):
    """
    Permiso que verifica que el usuario esté activo.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active
        )


class DepartmentBasedPermission(permissions.BasePermission):
    """
    Permiso basado en departamento del usuario.
    Los usuarios solo pueden ver/editar datos de su departamento.
    """
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios y administradores tienen acceso total
        if request.user.is_superuser or request.user.has_role('admin'):
            return True
        
        # Verificar si el objeto pertenece al mismo departamento
        if hasattr(obj, 'department') and hasattr(request.user, 'department'):
            return obj.department == request.user.department
        
        # Si no tiene departamento definido, verificar si es el propietario
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class BranchBasedPermission(permissions.BasePermission):
    """
    Permiso basado en sucursal del usuario.
    Los usuarios solo pueden ver/editar datos de su sucursal.
    """
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios y administradores tienen acceso total
        if request.user.is_superuser or request.user.has_role('admin'):
            return True
        
        # Verificar si el objeto pertenece a la misma sucursal
        if hasattr(obj, 'branch') and hasattr(request.user, 'branch'):
            return obj.branch == request.user.branch
        
        return False


class TimeBasedPermission(permissions.BasePermission):
    """
    Permiso basado en horarios de trabajo.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Aquí podrías implementar lógica de horarios
        # Por ahora, siempre permitir acceso
        return True


def check_module_permission(user, module_name, action='view'):
    """
    Función auxiliar para verificar permisos de módulo.
    
    Args:
        user: Usuario a verificar
        module_name: Nombre del módulo (pos, inventory, invoicing, etc.)
        action: Acción a verificar (view, create, edit, delete)
    
    Returns:
        bool: True si tiene permiso, False caso contrario
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superusuarios siempre tienen acceso
    if user.is_superuser:
        return True
    
    # Verificar permiso específico
    permission_code = f"{module_name}_{action}"
    return user.has_permission(permission_code)


def get_user_modules(user):
    """
    Obtiene la lista de módulos a los que el usuario tiene acceso.
    
    Args:
        user: Usuario
    
    Returns:
        list: Lista de módulos accesibles
    """
    if not user or not user.is_authenticated:
        return []
    
    modules = []
    
    # Verificar acceso a cada módulo
    if check_module_permission(user, 'pos'):
        modules.append('pos')
    
    if check_module_permission(user, 'inventory'):
        modules.append('inventory')
    
    if check_module_permission(user, 'invoice'):
        modules.append('invoicing')
    
    if check_module_permission(user, 'reports'):
        modules.append('reports')
    
    if user.has_role('admin') or user.has_permission('admin_users'):
        modules.append('users')
    
    if user.has_role('admin') or user.has_permission('admin_settings'):
        modules.append('settings')
    
    return modules


def get_user_permissions_summary(user):
    """
    Obtiene un resumen de todos los permisos del usuario.
    
    Args:
        user: Usuario
    
    Returns:
        dict: Diccionario con permisos organizados por módulo
    """
    if not user or not user.is_authenticated:
        return {}
    
    summary = {
        'is_superuser': user.is_superuser,
        'is_staff': user.is_staff,
        'roles': [role.code for role in user.roles.filter(is_active=True)],
        'modules': {}
    }
    
    # Permisos por módulo
    modules = ['pos', 'inventory', 'invoicing', 'accounting', 'reports', 'users', 'settings']
    actions = ['view', 'create', 'edit', 'delete']
    
    for module in modules:
        summary['modules'][module] = {}
        for action in actions:
            summary['modules'][module][action] = check_module_permission(user, module, action)
    
    return summary