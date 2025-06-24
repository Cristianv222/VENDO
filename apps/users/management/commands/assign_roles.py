"""
Comando para asignar roles a usuarios en VENDO.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.users.models import User, Role, UserRole
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Asignar roles a usuarios en VENDO'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Nombre de usuario al que asignar el rol',
        )
        parser.add_argument(
            '--user-id',
            type=str,
            help='ID del usuario al que asignar el rol',
        )
        parser.add_argument(
            '--role',
            type=str,
            help='Código del rol a asignar (admin, manager, cashier, etc.)',
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Remover el rol en lugar de asignarlo',
        )
        parser.add_argument(
            '--list-roles',
            action='store_true',
            help='Listar todos los roles disponibles',
        )
        parser.add_argument(
            '--list-users',
            action='store_true',
            help='Listar todos los usuarios',
        )
        parser.add_argument(
            '--user-roles',
            type=str,
            help='Mostrar roles de un usuario específico',
        )
        parser.add_argument(
            '--create-default-roles',
            action='store_true',
            help='Crear roles por defecto del sistema',
        )

    def handle(self, *args, **options):
        try:
            if options['list_roles']:
                self.list_roles()
            elif options['list_users']:
                self.list_users()
            elif options['user_roles']:
                self.show_user_roles(options['user_roles'])
            elif options['create_default_roles']:
                self.create_default_roles()
            else:
                self.assign_or_remove_role(options)
                
        except Exception as e:
            raise CommandError(f'Error: {str(e)}')

    def assign_or_remove_role(self, options):
        """Asignar o remover rol de un usuario."""
        # Validar argumentos requeridos
        if not options['role']:
            raise CommandError('El parámetro --role es requerido')
        
        if not options['username'] and not options['user_id']:
            raise CommandError('Debe especificar --username o --user-id')
        
        # Buscar usuario
        try:
            if options['username']:
                user = User.objects.get(username=options['username'])
            else:
                user = User.objects.get(id=options['user_id'])
        except User.DoesNotExist:
            raise CommandError('Usuario no encontrado')
        
        # Buscar rol
        try:
            role = Role.objects.get(code=options['role'])
        except Role.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Rol "{options["role"]}" no encontrado')
            )
            self.stdout.write('Roles disponibles:')
            self.list_roles()
            return
        
        # Realizar la acción
        with transaction.atomic():
            if options['remove']:
                self.remove_role_from_user(user, role)
            else:
                self.assign_role_to_user(user, role)

    def assign_role_to_user(self, user, role):
        """Asignar rol a usuario."""
        user_role, created = UserRole.objects.get_or_create(
            user=user,
            role=role,
            defaults={'is_active': True}
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Rol "{role.name}" asignado a "{user.username}" exitosamente'
                )
            )
        else:
            if user_role.is_active:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  El usuario "{user.username}" ya tiene el rol "{role.name}"'
                    )
                )
            else:
                user_role.is_active = True
                user_role.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Rol "{role.name}" reactivado para "{user.username}"'
                    )
                )

    def remove_role_from_user(self, user, role):
        """Remover rol de usuario."""
        try:
            user_role = UserRole.objects.get(user=user, role=role, is_active=True)
            user_role.is_active = False
            user_role.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Rol "{role.name}" removido de "{user.username}" exitosamente'
                )
            )
        except UserRole.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  El usuario "{user.username}" no tiene el rol "{role.name}" activo'
                )
            )

    def list_roles(self):
        """Listar todos los roles disponibles."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('ROLES DISPONIBLES'))
        self.stdout.write('='*60)
        
        roles = Role.objects.all().order_by('name')
        
        if not roles:
            self.stdout.write(self.style.WARNING('No hay roles configurados'))
            self.stdout.write('Ejecuta: python manage.py assign_roles --create-default-roles')
            return
        
        for role in roles:
            status = '✅ Activo' if role.is_active else '❌ Inactivo'
            user_count = role.user_count
            
            self.stdout.write(f'📋 {role.name}')
            self.stdout.write(f'   Código: {role.code}')
            self.stdout.write(f'   Estado: {status}')
            self.stdout.write(f'   Usuarios: {user_count}')
            if role.description:
                self.stdout.write(f'   Descripción: {role.description}')
            self.stdout.write('')

    def list_users(self):
        """Listar todos los usuarios."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('USUARIOS REGISTRADOS'))
        self.stdout.write('='*60)
        
        users = User.objects.all().order_by('username')
        
        for user in users:
            status = '✅ Activo' if user.is_active else '❌ Inactivo'
            roles = ', '.join([
                role.name for role in user.roles.filter(is_active=True)
            ]) or 'Sin roles'
            
            self.stdout.write(f'👤 {user.username} ({user.get_full_name()})')
            self.stdout.write(f'   ID: {user.id}')
            self.stdout.write(f'   Email: {user.email}')
            self.stdout.write(f'   Estado: {status}')
            self.stdout.write(f'   Tipo: {user.get_user_type_display()}')
            self.stdout.write(f'   Roles: {roles}')
            self.stdout.write('')

    def show_user_roles(self, username):
        """Mostrar roles de un usuario específico."""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'Usuario "{username}" no encontrado')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'ROLES DE {user.username}'))
        self.stdout.write('='*60)
        
        self.stdout.write(f'👤 Usuario: {user.get_full_name()} ({user.username})')
        self.stdout.write(f'📧 Email: {user.email}')
        self.stdout.write(f'🏷️  Tipo: {user.get_user_type_display()}')
        self.stdout.write(f'✅ Activo: {"Sí" if user.is_active else "No"}')
        self.stdout.write('')
        
        user_roles = UserRole.objects.filter(user=user).select_related('role')
        
        if user_roles:
            self.stdout.write('📋 ROLES ASIGNADOS:')
            for user_role in user_roles:
                status = '✅ Activo' if user_role.is_active else '❌ Inactivo'
                assigned_by = user_role.assigned_by.username if user_role.assigned_by else 'Sistema'
                
                self.stdout.write(f'   • {user_role.role.name} ({user_role.role.code})')
                self.stdout.write(f'     Estado: {status}')
                self.stdout.write(f'     Asignado por: {assigned_by}')
                self.stdout.write(f'     Fecha: {user_role.assigned_at.strftime("%Y-%m-%d %H:%M")}')
                self.stdout.write('')
        else:
            self.stdout.write(self.style.WARNING('Este usuario no tiene roles asignados'))

    def create_default_roles(self):
        """Crear roles por defecto del sistema."""
        self.stdout.write(self.style.SUCCESS('🚀 Creando roles por defecto de VENDO...'))
        
        default_roles = [
            {
                'name': 'Administrador',
                'code': 'admin',
                'description': 'Acceso completo al sistema'
            },
            {
                'name': 'Gerente',
                'code': 'manager',
                'description': 'Gestión general y reportes'
            },
            {
                'name': 'Cajero',
                'code': 'cashier',
                'description': 'Operación del punto de venta'
            },
            {
                'name': 'Encargado de Inventario',
                'code': 'inventory_manager',
                'description': 'Gestión de productos e inventario'
            },
            {
                'name': 'Contador',
                'code': 'accountant',
                'description': 'Gestión contable y financiera'
            },
            {
                'name': 'Vendedor',
                'code': 'sales_rep',
                'description': 'Ventas y atención al cliente'
            },
            {
                'name': 'Solo Lectura',
                'code': 'viewer',
                'description': 'Solo visualización de información'
            },
        ]
        
        created_count = 0
        for role_data in default_roles:
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
                self.stdout.write(f'✅ Rol creado: {role.name}')
            else:
                self.stdout.write(f'ℹ️  Rol ya existe: {role.name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Proceso completado: {created_count} roles nuevos creados'
            )
        )
        
        if created_count > 0:
            self.stdout.write('\nPuedes asignar roles usando:')
            self.stdout.write('python manage.py assign_roles --username USUARIO --role CODIGO_ROL')
            self.stdout.write('\nPara ver todos los roles: python manage.py assign_roles --list-roles')