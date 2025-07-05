# apps/users/management/commands/init_roles.py
# CREAR ESTE ARCHIVO NUEVO

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from apps.users.models import Role, Permission

class Command(BaseCommand):
    help = 'Inicializa roles y permisos por defecto del sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la recreación de roles existentes',
        )

    def handle(self, *args, **options):
        self.stdout.write('🚀 Inicializando roles y permisos del sistema...')
        
        with transaction.atomic():
            # Crear permisos por defecto
            self.create_permissions()
            
            # Crear roles por defecto
            self.create_roles(force=options['force'])
            
        self.stdout.write(
            self.style.SUCCESS('✅ Roles y permisos inicializados correctamente')
        )

    def create_permissions(self):
        """Crear permisos por defecto del sistema"""
        permissions_data = [
            # Core permissions
            ('view_dashboard', 'Ver Dashboard', 'Acceso al dashboard principal', 'core'),
            ('manage_companies', 'Gestionar Empresas', 'Crear, editar y eliminar empresas', 'core'),
            ('manage_branches', 'Gestionar Sucursales', 'Crear, editar y eliminar sucursales', 'core'),
            
            # Users permissions
            ('manage_users', 'Gestionar Usuarios', 'Crear, editar y eliminar usuarios', 'users'),
            ('approve_users', 'Aprobar Usuarios', 'Aprobar o rechazar usuarios pendientes', 'users'),
            ('assign_roles', 'Asignar Roles', 'Asignar roles a usuarios', 'users'),
            ('view_user_reports', 'Ver Reportes de Usuarios', 'Acceso a reportes de usuarios', 'users'),
            
            # POS permissions
            ('access_pos', 'Acceso POS', 'Acceso al punto de venta', 'pos'),
            ('process_sales', 'Procesar Ventas', 'Realizar ventas en el POS', 'pos'),
            ('manage_cash_register', 'Gestionar Caja', 'Abrir/cerrar caja registradora', 'pos'),
            ('apply_discounts', 'Aplicar Descuentos', 'Aplicar descuentos en ventas', 'pos'),
            ('cancel_sales', 'Cancelar Ventas', 'Cancelar transacciones de venta', 'pos'),
            
            # Inventory permissions
            ('view_inventory', 'Ver Inventario', 'Consultar productos e inventario', 'inventory'),
            ('manage_products', 'Gestionar Productos', 'Crear, editar y eliminar productos', 'inventory'),
            ('manage_categories', 'Gestionar Categorías', 'Gestionar categorías de productos', 'inventory'),
            ('manage_suppliers', 'Gestionar Proveedores', 'Gestionar información de proveedores', 'inventory'),
            ('adjust_stock', 'Ajustar Stock', 'Realizar ajustes de inventario', 'inventory'),
            ('transfer_stock', 'Transferir Stock', 'Transferir productos entre sucursales', 'inventory'),
            
            # Invoicing permissions
            ('create_invoices', 'Crear Facturas', 'Emitir facturas electrónicas', 'invoicing'),
            ('manage_invoices', 'Gestionar Facturas', 'Editar y administrar facturas', 'invoicing'),
            ('cancel_invoices', 'Anular Facturas', 'Anular facturas emitidas', 'invoicing'),
            ('send_sri', 'Enviar al SRI', 'Transmitir documentos al SRI', 'invoicing'),
            ('reprint_invoices', 'Reimprimir Facturas', 'Reimprimir documentos fiscales', 'invoicing'),
            
            # Purchases permissions
            ('create_purchases', 'Crear Compras', 'Registrar compras y gastos', 'purchases'),
            ('manage_purchase_orders', 'Gestionar Órdenes de Compra', 'Crear y gestionar órdenes de compra', 'purchases'),
            ('approve_purchases', 'Aprobar Compras', 'Aprobar compras pendientes', 'purchases'),
            
            # Accounting permissions
            ('view_accounting', 'Ver Contabilidad', 'Acceso a módulo contable', 'accounting'),
            ('manage_accounts', 'Gestionar Cuentas', 'Administrar plan de cuentas', 'accounting'),
            ('create_journal_entries', 'Crear Asientos', 'Crear asientos contables', 'accounting'),
            ('close_periods', 'Cerrar Períodos', 'Cerrar períodos contables', 'accounting'),
            
            # Reports permissions
            ('view_sales_reports', 'Ver Reportes de Ventas', 'Acceso a reportes de ventas', 'reports'),
            ('view_inventory_reports', 'Ver Reportes de Inventario', 'Acceso a reportes de inventario', 'reports'),
            ('view_financial_reports', 'Ver Reportes Financieros', 'Acceso a reportes financieros', 'reports'),
            ('export_reports', 'Exportar Reportes', 'Exportar reportes a Excel/PDF', 'reports'),
            
            # Settings permissions
            ('manage_system_settings', 'Gestionar Configuración del Sistema', 'Configurar parámetros del sistema', 'settings'),
            ('manage_tax_settings', 'Gestionar Configuración de Impuestos', 'Configurar impuestos y tarifas', 'settings'),
            ('manage_integrations', 'Gestionar Integraciones', 'Configurar integraciones externas', 'settings'),
            ('backup_restore', 'Backup y Restauración', 'Realizar copias de seguridad', 'settings'),
        ]
        
        created_count = 0
        for codename, name, description, module in permissions_data:
            permission, created = Permission.objects.get_or_create(
                codename=codename,
                defaults={
                    'name': name,
                    'description': description,
                    'module': module,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Permiso creado: {name}')
        
        self.stdout.write(f'📋 Permisos: {created_count} nuevos, {Permission.objects.count()} total')

    def create_roles(self, force=False):
        """Crear roles por defecto del sistema"""
        roles_data = [
            {
                'name': 'super_admin',
                'description': 'Acceso completo a todo el sistema',
                'color': '#dc3545',
                'is_system_role': True,
                'permissions': 'all'
            },
            {
                'name': 'admin',
                'description': 'Administrador de empresa con acceso completo',
                'color': '#fd7e14',
                'is_system_role': False,
                'permissions': [
                    'view_dashboard', 'manage_companies', 'manage_branches',
                    'manage_users', 'assign_roles', 'view_user_reports',
                    'access_pos', 'process_sales', 'manage_cash_register', 'apply_discounts',
                    'view_inventory', 'manage_products', 'manage_categories', 'adjust_stock',
                    'create_invoices', 'manage_invoices', 'send_sri', 'reprint_invoices',
                    'create_purchases', 'manage_purchase_orders', 'approve_purchases',
                    'view_accounting', 'manage_accounts', 'create_journal_entries',
                    'view_sales_reports', 'view_inventory_reports', 'view_financial_reports', 'export_reports',
                    'manage_system_settings', 'manage_tax_settings'
                ]
            },
            {
                'name': 'supervisor',
                'description': 'Supervisor con permisos de gestión limitados',
                'color': '#ffc107',
                'is_system_role': False,
                'permissions': [
                    'view_dashboard',
                    'access_pos', 'process_sales', 'manage_cash_register', 'apply_discounts',
                    'view_inventory', 'manage_products', 'adjust_stock',
                    'create_invoices', 'manage_invoices', 'reprint_invoices',
                    'create_purchases',
                    'view_sales_reports', 'view_inventory_reports', 'export_reports'
                ]
            },
            {
                'name': 'cajero',
                'description': 'Operador de punto de venta',
                'color': '#28a745',
                'is_system_role': False,
                'permissions': [
                    'view_dashboard',
                    'access_pos', 'process_sales',
                    'view_inventory',
                    'create_invoices', 'reprint_invoices',
                    'view_sales_reports'
                ]
            },
            {
                'name': 'inventario',
                'description': 'Encargado de inventario',
                'color': '#17a2b8',
                'is_system_role': False,
                'permissions': [
                    'view_dashboard',
                    'view_inventory', 'manage_products', 'manage_categories', 
                    'manage_suppliers', 'adjust_stock', 'transfer_stock',
                    'create_purchases', 'manage_purchase_orders',
                    'view_inventory_reports', 'export_reports'
                ]
            },
            {
                'name': 'contador',
                'description': 'Gestión contable y fiscal',
                'color': '#6f42c1',
                'is_system_role': False,
                'permissions': [
                    'view_dashboard',
                    'create_invoices', 'manage_invoices', 'cancel_invoices', 'send_sri',
                    'view_accounting', 'manage_accounts', 'create_journal_entries', 'close_periods',
                    'view_sales_reports', 'view_financial_reports', 'export_reports',
                    'manage_tax_settings'
                ]
            },
            {
                'name': 'consulta',
                'description': 'Solo consulta de información',
                'color': '#6c757d',
                'is_system_role': False,
                'permissions': [
                    'view_dashboard',
                    'view_inventory',
                    'view_sales_reports', 'view_inventory_reports'
                ]
            }
        ]
        
        created_count = 0
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'description': role_data['description'],
                    'color': role_data['color'],
                    'is_system_role': role_data['is_system_role'],
                    'is_active': True
                }
            )
            
            if created or force:
                if force and not created:
                    self.stdout.write(f'  🔄 Actualizando rol: {role_data["name"]}')
                else:
                    self.stdout.write(f'  ✓ Rol creado: {role_data["name"]}')
                    created_count += 1
                
                # Asignar permisos
                if role_data['permissions'] == 'all':
                    role.permissions.set(Permission.objects.filter(is_active=True))
                else:
                    permissions = Permission.objects.filter(
                        codename__in=role_data['permissions'],
                        is_active=True
                    )
                    role.permissions.set(permissions)
                    
                self.stdout.write(f'    📋 {role.permissions.count()} permisos asignados')
        
        self.stdout.write(f'👥 Roles: {created_count} nuevos, {Role.objects.count()} total')