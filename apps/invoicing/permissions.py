from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import permissions
from rest_framework.permissions import BasePermission
from .models import Invoice, Customer, Product, SRIConfiguration

class InvoicingPermissions:
    """Definición de permisos personalizados para facturación"""
    
    # Permisos de facturas
    CAN_CREATE_INVOICE = 'invoicing.add_invoice'
    CAN_VIEW_INVOICE = 'invoicing.view_invoice'
    CAN_CHANGE_INVOICE = 'invoicing.change_invoice'
    CAN_DELETE_INVOICE = 'invoicing.delete_invoice'
    CAN_SEND_TO_SRI = 'invoicing.send_to_sri'
    CAN_RESEND_TO_SRI = 'invoicing.resend_to_sri'
    CAN_SEND_EMAIL = 'invoicing.send_email_invoice'
    CAN_DOWNLOAD_PDF = 'invoicing.download_pdf_invoice'
    CAN_DOWNLOAD_XML = 'invoicing.download_xml_invoice'
    
    # Permisos de configuración SRI
    CAN_CONFIGURE_SRI = 'invoicing.configure_sri'
    CAN_VIEW_SRI_LOGS = 'invoicing.view_sri_logs'
    
    # Permisos de clientes y productos
    CAN_MANAGE_CUSTOMERS = 'invoicing.manage_customers'
    CAN_MANAGE_PRODUCTS = 'invoicing.manage_products'

class CompanyPermissionMixin:
    """Mixin para verificar que el usuario pertenece a la empresa"""
    
    def has_company_permission(self, user, obj):
        """Verifica si el usuario tiene acceso al objeto de su empresa"""
        if not hasattr(user, 'company'):
            return False
        
        if hasattr(obj, 'company'):
            return obj.company == user.company
        
        return False

class IsInvoiceOwner(BasePermission, CompanyPermissionMixin):
    """Permiso para verificar que el usuario puede acceder a la factura de su empresa"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'company')
    
    def has_object_permission(self, request, view, obj):
        return self.has_company_permission(request.user, obj)

class CanCreateInvoice(BasePermission):
    """Permiso para crear facturas"""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'company') and
            request.user.has_perm(InvoicingPermissions.CAN_CREATE_INVOICE)
        )

class CanSendToSRI(BasePermission):
    """Permiso para enviar facturas al SRI"""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'company') and
            request.user.has_perm(InvoicingPermissions.CAN_SEND_TO_SRI)
        )

class CanConfigureSRI(BasePermission):
    """Permiso para configurar el SRI"""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'company') and
            request.user.has_perm(InvoicingPermissions.CAN_CONFIGURE_SRI)
        )

class CanManageCustomers(BasePermission):
    """Permiso para gestionar clientes"""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'company') and
            request.user.has_perm(InvoicingPermissions.CAN_MANAGE_CUSTOMERS)
        )

class CanManageProducts(BasePermission):
    """Permiso para gestionar productos"""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'company') and
            request.user.has_perm(InvoicingPermissions.CAN_MANAGE_PRODUCTS)
        )

# Decoradores para vistas basadas en funciones
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required

def require_company_permission(permission_name):
    """Decorador para requerir un permiso específico"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'company'):
                raise PermissionDenied("Usuario no pertenece a ninguna empresa")
            
            if not request.user.has_perm(permission_name):
                raise PermissionDenied(f"No tiene permiso: {permission_name}")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def require_sri_configuration(view_func):
    """Decorador para requerir configuración SRI"""
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'company'):
            raise PermissionDenied("Usuario no pertenece a ninguna empresa")
        
        try:
            SRIConfiguration.objects.get(company=request.user.company)
        except SRIConfiguration.DoesNotExist:
            raise PermissionDenied("Debe configurar el SRI antes de realizar esta acción")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def require_invoice_owner(view_func):
    """Decorador para verificar que la factura pertenece a la empresa del usuario"""
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'company'):
            raise PermissionDenied("Usuario no pertenece a ninguna empresa")
        
        # Obtener ID de factura de los kwargs
        invoice_id = kwargs.get('invoice_id') or kwargs.get('pk')
        if invoice_id:
            try:
                invoice = Invoice.objects.get(id=invoice_id)
                if invoice.company != request.user.company:
                    raise PermissionDenied("No tiene acceso a esta factura")
            except Invoice.DoesNotExist:
                raise PermissionDenied("Factura no encontrada")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view