from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework import permissions
from rest_framework.permissions import BasePermission

class InventoryPermission(BasePermission):
    """Permisos personalizados para inventario"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Mapeo de acciones a permisos
        permission_map = {
            'list': 'inventory.view_product',
            'retrieve': 'inventory.view_product',
            'create': 'inventory.add_product',
            'update': 'inventory.change_product',
            'partial_update': 'inventory.change_product',
            'destroy': 'inventory.delete_product',
            'stock_movement': 'inventory.add_stockmovement',
            'import_products': 'inventory.add_product',
            'export_products': 'inventory.view_product',
            'generate_barcodes': 'inventory.view_product',
        }
        
        required_permission = permission_map.get(view.action)
        if required_permission:
            return request.user.has_perm(required_permission)
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Verificar permisos a nivel de objeto
        if view.action in ['retrieve', 'update', 'partial_update']:
            return request.user.has_perm('inventory.change_product')
        elif view.action == 'destroy':
            return request.user.has_perm('inventory.delete_product')
        
        return True

class StockMovementPermission(BasePermission):
    """Permisos para movimientos de stock"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        permission_map = {
            'list': 'inventory.view_stockmovement',
            'retrieve': 'inventory.view_stockmovement',
            'create': 'inventory.add_stockmovement',
            'update': 'inventory.change_stockmovement',
            'destroy': 'inventory.delete_stockmovement',
        }
        
        required_permission = permission_map.get(view.action)
        if required_permission:
            return request.user.has_perm(required_permission)
        
        return True

class StockAlertPermission(BasePermission):
    """Permisos para alertas de stock"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        permission_map = {
            'list': 'inventory.view_stockalert',
            'retrieve': 'inventory.view_stockalert',
            'resolve': 'inventory.change_stockalert',
        }
        
        required_permission = permission_map.get(view.action)
        if required_permission:
            return request.user.has_perm(required_permission)
        
        return True

class InventoryManagerPermission(PermissionRequiredMixin):
    """Mixin para vistas que requieren permisos de gestión de inventario"""
    permission_required = [
        'inventory.view_product',
        'inventory.add_product',
        'inventory.change_product'
    ]

class InventoryViewPermission(PermissionRequiredMixin):
    """Mixin para vistas de solo lectura de inventario"""
    permission_required = 'inventory.view_product'

class StockManagerPermission(PermissionRequiredMixin):
    """Mixin para gestión de stock"""
    permission_required = [
        'inventory.view_stockmovement',
        'inventory.add_stockmovement'
    ]