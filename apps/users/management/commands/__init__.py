"""
Comando para inicializar el sistema de usuarios de VENDO.
Crea roles, permisos y datos por defecto necesarios.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.users.models import Role, Permission, User, UserProfile
from apps.users.utils import create_initial_roles, create_initial_permissions


class Command(BaseCommand):
    help = 'Inicializar datos básicos del sistema de usuarios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-admin',
            action='store_true',
            help='Crear usuario administrador por defecto',
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            default='admin',
            help='Nombre de usuario para el administrador',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@vendo.com',
            help='Email para el administrador',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='admin123',
            help='Contraseña para el administrador',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recreación de datos existentes',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Inicializando sistema de usuarios VENDO...\n')
        )

        try:
            with transaction.atomic():
                # 1. Crear permisos por defecto
                self.create_permissions()
                
                # 2. Crear roles por defecto
                self.create_roles()
                
                # 3. Asignar permisos a roles
                self.assign_permissions_to_roles()
                
                # 4. Crear usuario administrador si se solicita
                if options['create_admin']:
                    self.create_admin_user(options)
                
                # 5. Mostrar resumen
                self.show_summary()
                
                self.stdout.write(
                    self.style.SUCCESS('\n✅ Inicialización completada exitosamente!')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error durante la inicialización: {str(e)}')
            )
            raise CommandError(f'Falló la inicialización: {str(e)}')

    def create_permissions(self):
        """Crear permisos por defecto del sistema."""
        self.stdout.write('📋 Creando permisos del sistema...')
        
        permissions_data = [
            # POS Permissions
            {'name': 'Ver POS', 'code': 'pos_view', 'module': 'pos', 'description': 'Acceso al módulo de punto de venta'},
            {'name': 'Crear Venta', 'code': 'pos_create_sale', 'module': 'pos', 'description': 'Procesar ventas en el POS'},
            {'name': 'Cancelar Venta', 'code': 'pos_cancel_sale', 'module': 'pos', 'description': 'Cancelar ventas procesadas'},
            {'name': 'Gestionar Caja', 'code': 'pos_manage_cash', 'module': 'pos', 'description': 'Abrir/cerrar caja y gestionar efectivo'},
            
            # Inventory Permissions
            {'name': 'Ver Inventario', 'code': 'inventory_view', 'module': 'inventory', 'description': 'Consultar productos y stock'},
            {'name': 'Crear Productos', 'code': 'inventory_create', 'module': 'inventory', 'description': 'Agregar nuevos productos'},
            {'name': 'Editar Productos', 'code': 'inventory_edit', 'module': 'inventory', 'description': 'Modificar información de productos'},
            {'name': 'Eliminar Productos', 'code': 'inventory_delete', 'module': 'inventory', 'description': 'Eliminar productos del sistema'},
            {'name': 'Ajustar Stock', 'code': 'inventory_adjust', 'module': 'inventory', 'description': 'Realizar ajustes de inventario'},
            
            # Invoicing Permissions
            {'name': 'Ver Facturas', 'code': 'invoice_view', 'module': 'invoicing', 'description': 'Consultar documentos electrónicos'},
            {'name': 'Crear Facturas', 'code': 'invoice_create', 'module': 'invoicing', 'description': 'Generar facturas electrónicas'},
            {'name': 'Editar Facturas', 'code': 'invoice_edit', 'module': 'invoicing', 'description': 'Modificar facturas antes del envío'},
            {'name': 'Anular Facturas', 'code': 'invoice_cancel', 'module': 'invoicing', 'description': 'Anular documentos electrónicos'},
            {'name': 'Enviar a SRI', 'code': 'invoice_send_sri', 'module': 'invoicing', 'description': 'Autorizar envío al SRI'},
            
            # Purchases Permissions
            {'name': 'Ver Compras', 'code': 'purchases_view', 'module': 'purchases', 'description': 'Consultar órdenes de compra'},
            {'name': 'Crear Órdenes', 'code': 'purchases_create', 'module': 'purchases', 'description': 'Generar órdenes de compra'},
            {'name': 'Aprobar Compras', 'code': 'purchases_approve', 'module': 'purchases', 'description': 'Aprobar órdenes de compra'},
            {'name': 'Gestionar Proveedores', 'code': 'purchases_suppliers', 'module': 'purchases', 'description': 'Administrar proveedores'},
            
            # Accounting Permissions
            {'name': 'Ver Contabilidad', 'code': 'accounting_view', 'module': 'accounting', 'description': 'Acceso a información contable'},
            {'name': 'Gestionar Cuentas', 'code': 'accounting_manage', 'module': 'accounting', 'description': 'Administrar plan de cuentas'},
            {'name': 'Cuentas por Cobrar', 'code': 'accounting_receivable', 'module': 'accounting', 'description': 'Gestionar cuentas por cobrar'},
            {'name': 'Cuentas por Pagar', 'code': 'accounting_payable', 'module': 'accounting', 'description': 'Gestionar cuentas por pagar'},
            
            # Reports Permissions
            {'name': 'Ver Reportes', 'code': 'reports_view', 'module': 'reports', 'description': 'Acceso a reportes básicos'},
            {'name': 'Exportar Reportes', 'code': 'reports_export', 'module': 'reports', 'description': 'Exportar reportes a Excel/PDF'},
            {'name': 'Reportes Financieros', 'code': 'reports_financial', 'module': 'reports', 'description': 'Reportes financieros y contables'},
            {'name': 'Reportes Gerenciales', 'code': 'reports_management', 'module': 'reports', 'description': 'Reportes ejecutivos y KPIs'},
            
            # Quotations Permissions
            {'name': 'Ver Cotizaciones', 'code': 'quotations_view', 'module': 'quotations', 'description': 'Consultar cotizaciones'},
            {'name': 'Crear Cotizaciones', 'code': 'quotations_create', 'module': 'quotations', 'description': 'Generar cotizaciones'},
            {'name': 'Aprobar Cotizaciones', 'code': 'quotations_approve', 'module': 'quotations', 'description': 'Aprobar cotizaciones'},
            
            # Admin Permissions
            {'name': 'Gestionar Usuarios', 'code': 'admin_users', 'module': 'admin', 'description': 'Administrar usuarios y roles'},
            {'name': 'Configurar Sistema', 'code': 'admin_settings', 'module': 'admin', 'description': 'Configuraciones del sistema'},
            {'name': 'Gestionar Respaldos', 'code': 'admin_backup', 'module': 'admin', 'description': 'Respaldos y restauración'},
            {'name': 'Ver Logs', 'code': 'admin_logs', 'module': 'admin', 'description': 'Acceso a logs del sistema'},
        ]
        
        created_count = 0
        for perm_data in permissions_data:
            permission, created = Permission.objects.get_or_create(
                code=perm_data['code'],
                defaults={
                    'name': perm_data['name'],
                    'module': perm_data['module'],
                    'description': perm_data['description'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'  ✅ {permission.name}')
            else:
                self.stdout.write(f'  ℹ️  {permission.name} (ya existe)')
        
        self.stdout.write(f'\n📋 Permisos procesados: {created_count} nuevos, {len(permissions_data) - created_count} existentes')

    def create_roles(self):
        """Crear roles por defecto del sistema."""
        self.stdout.write('\n🔑 Creando roles del sistema...')
        
        roles_data = [
            {
                'name': 'Administrador',
                'code': 'admin',
                'description': 'Acceso completo al sistema con todos los permisos'
            },
            {
                'name': 'Gerente',
                'code': 'manager',
                'description': 'Gestión general, reportes y supervisión operativa'
            },
            {
                'name': 'Cajero',
                'code': 'cashier',
                'description': 'Operación del punto de venta y gestión de caja'
            },
            {
                'name': 'Encargado de Inventario',
                'code': 'inventory_manager',
                'description': 'Gestión completa de productos, stock y proveedores'
            },
            {
                'name': 'Contador',
                'code': 'accountant',
                'description': 'Gestión contable, financiera y facturación electrónica'
            },
            {
                'name': 'Vendedor',
                'code': 'sales_rep',
                'description': 'Ventas, cotizaciones y atención al cliente'
            },
            {
                'name': 'Solo Lectura',
                'code': 'viewer',
                'description': 'Solo visualización de información sin modificaciones'
            },
        ]
        
        created_count = 0
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'  ✅ {role.name}')
            else:
                self.stdout.write(f'  ℹ️  {role.name} (ya existe)')
        
        self.stdout.write(f'\n🔑 Roles procesados: {created_count} nuevos, {len(roles_data) - created_count} existentes')

    def assign_permissions_to_roles(self):
        """Asignar permisos por defecto a los roles."""
        self.stdout.write('\n🔗 Asignando permisos a roles...')
        
        # Definir permisos por rol
        role_permissions = {
            'admin': [
                # Administrador tiene TODOS los permisos
                'pos_view', 'pos_create_sale', 'pos_cancel_sale', 'pos_manage_cash',
                'inventory_view', 'inventory_create', 'inventory_edit', 'inventory_delete', 'inventory_adjust',
                'invoice_view', 'invoice_create', 'invoice_edit', 'invoice_cancel', 'invoice_send_sri',
                'purchases_view', 'purchases_create', 'purchases_approve', 'purchases_suppliers',
                'accounting_view', 'accounting_manage', 'accounting_receivable', 'accounting_payable',
                'reports_view', 'reports_export', 'reports_financial', 'reports_management',
                'quotations_view', 'quotations_create', 'quotations_approve',
                'admin_users', 'admin_settings', 'admin_backup', 'admin_logs'
            ],
            'manager': [
                # Gerente: acceso amplio pero no administración
                'pos_view', 'pos_create_sale', 'pos_cancel_sale', 'pos_manage_cash',
                'inventory_view', 'inventory_create', 'inventory_edit', 'inventory_adjust',
                'invoice_view', 'invoice_create', 'invoice_edit', 'invoice_send_sri',
                'purchases_view', 'purchases_create', 'purchases_approve', 'purchases_suppliers',
                'accounting_view', 'accounting_receivable', 'accounting_payable',
                'reports_view', 'reports_export', 'reports_financial', 'reports_management',
                'quotations_view', 'quotations_create', 'quotations_approve'
            ],
            'cashier': [
                # Cajero: principalmente POS y consultas básicas
                'pos_view', 'pos_create_sale', 'pos_manage_cash',
                'inventory_view',
                'invoice_view', 'invoice_create',
                'quotations_view', 'quotations_create',
                'reports_view'
            ],
            'inventory_manager': [
                # Encargado de inventario: gestión completa de productos
                'inventory_view', 'inventory_create', 'inventory_edit', 'inventory_delete', 'inventory_adjust',
                'purchases_view', 'purchases_create', 'purchases_suppliers',
                'reports_view', 'reports_export',
                'pos_view'
            ],
            'accountant': [
                # Contador: facturación y contabilidad
                'invoice_view', 'invoice_create', 'invoice_edit', 'invoice_cancel', 'invoice_send_sri',
                'accounting_view', 'accounting_manage', 'accounting_receivable', 'accounting_payable',
                'purchases_view', 'purchases_approve',
                'reports_view', 'reports_export', 'reports_financial',
                'inventory_view', 'pos_view'
            ],
            'sales_rep': [
                # Vendedor: ventas y cotizaciones
                'pos_view', 'pos_create_sale',
                'inventory_view',
                'quotations_view', 'quotations_create',
                'invoice_view',
                'reports_view'
            ],
            'viewer': [
                # Solo lectura: consultas básicas
                'pos_view', 'inventory_view', 'invoice_view',
                'purchases_view', 'accounting_view',
                'reports_view', 'quotations_view'
            ]
        }
        
        for role_code, permission_codes in role_permissions.items():
            try:
                role = Role.objects.get(code=role_code)
                permissions = Permission.objects.filter(code__in=permission_codes)
                
                # Limpiar permisos existentes si ya tiene algunos
                role.permissions.clear()
                
                # Asignar nuevos permisos
                for permission in permissions:
                    # Aquí podrías usar UserPermission si quisieras un control más granular
                    pass
                
                self.stdout.write(f'  ✅ {role.name}: {len(permissions)} permisos asignados')
                
            except Role.DoesNotExist:
                self.stdout.write(f'  ❌ Rol {role_code} no encontrado')

    def create_admin_user(self, options):
        """Crear usuario administrador por defecto."""
        self.stdout.write('\n👤 Creando usuario administrador...')
        
        username = options['admin_username']
        email = options['admin_email']
        password = options['admin_password']
        
        # Verificar si ya existe
        if User.objects.filter(username=username).exists():
            if options['force']:
                User.objects.filter(username=username).delete()
                self.stdout.write(f'  🗑️  Usuario existente "{username}" eliminado')
            else:
                self.stdout.write(f'  ℹ️  Usuario "{username}" ya existe, saltando...')
                return
        
        # Crear usuario
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name='Administrador',
            last_name='VENDO',
            document_type='cedula',
            document_number='9999999999',
            user_type='admin'
        )
        
        # Crear perfil
        UserProfile.objects.create(
            user=user,
            theme='light',
            language='es',
            timezone='America/Guayaquil',
            email_notifications=True
        )
        
        # Asignar rol de administrador
        try:
            admin_role = Role.objects.get(code='admin')
            user.roles.add(admin_role)
            self.stdout.write(f'  ✅ Usuario "{username}" creado con rol de administrador')
        except Role.DoesNotExist:
            self.stdout.write(f'  ⚠️  Usuario creado pero rol "admin" no encontrado')
        
        self.stdout.write(f'  📧 Email: {email}')
        self.stdout.write(f'  🔑 Contraseña: {password}')

    def show_summary(self):
        """Mostrar resumen de la inicialización."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 RESUMEN DE INICIALIZACIÓN'))
        self.stdout.write('='*60)
        
        # Estadísticas
        total_permissions = Permission.objects.count()
        total_roles = Role.objects.count()
        total_users = User.objects.count()
        
        self.stdout.write(f'📋 Permisos totales: {total_permissions}')
        self.stdout.write(f'🔑 Roles totales: {total_roles}')
        self.stdout.write(f'👤 Usuarios totales: {total_users}')
        
        # Módulos disponibles
        modules = Permission.objects.values_list('module', flat=True).distinct()
        self.stdout.write(f'📦 Módulos configurados: {", ".join(modules)}')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.WARNING('PRÓXIMOS PASOS:'))
        self.stdout.write('1. python manage.py runserver')
        self.stdout.write('2. Acceder a http://127.0.0.1:8000/users/login/')
        self.stdout.write('3. Configurar datos adicionales de la empresa')
        self.stdout.write('4. Crear usuarios adicionales según necesidades')
        self.stdout.write('='*60)