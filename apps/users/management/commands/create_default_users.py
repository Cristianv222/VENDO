"""
Comando para crear usuarios por defecto del sistema
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext as _

from apps.users.models import Role, UserCompany
from apps.users.utils import generate_temporary_password, create_default_roles
from apps.core.models import Company

User = get_user_model()


class Command(BaseCommand):
    help = 'Crear usuarios por defecto del sistema'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=str,
            help='ID de la empresa para asignar usuarios',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@vendo.com',
            help='Email del administrador (default: admin@vendo.com)',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            help='Contraseña del administrador (si no se especifica, se genera una)',
        )
        parser.add_argument(
            '--create-demo-users',
            action='store_true',
            help='Crear usuarios de demostración',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recreación si los usuarios ya existen',
        )
    
    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                self._create_system_admin(options)
                
                if options['company_id']:
                    company = Company.objects.get(id=options['company_id'])
                    self._create_company_users(company, options)
                
                if options['create_demo_users']:
                    self._create_demo_users(options)
                    
        except Exception as e:
            raise CommandError(f'Error creando usuarios: {e}')
    
    def _create_system_admin(self, options):
        """Crear administrador del sistema"""
        admin_email = options['admin_email']
        admin_password = options['admin_password'] or generate_temporary_password()
        
        # Verificar si ya existe
        if User.objects.filter(email=admin_email).exists():
            if not options['force']:
                self.stdout.write(
                    self.style.WARNING(f'El administrador {admin_email} ya existe')
                )
                return
            else:
                User.objects.filter(email=admin_email).delete()
        
        # Crear administrador
        admin_user = User.objects.create_user(
            username='admin',
            email=admin_email,
            password=admin_password,
            first_name='Administrador',
            last_name='Sistema',
            document_type='cedula',
            document_number='1234567890',
            is_staff=True,
            is_superuser=True,
            is_system_admin=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Administrador creado:\n'
                f'  Email: {admin_email}\n'
                f'  Usuario: admin\n'
                f'  Contraseña: {admin_password}'
            )
        )
    
    def _create_company_users(self, company, options):
        """Crear usuarios para una empresa específica"""
        # Asegurar que existen los roles
        create_default_roles()
        
        users_data = [
            {
                'username': f'gerente_{company.ruc}',
                'email': f'gerente@{company.ruc}.com',
                'first_name': 'Gerente',
                'last_name': 'General',
                'role': 'Gerente'
            },
            {
                'username': f'vendedor_{company.ruc}',
                'email': f'vendedor@{company.ruc}.com',
                'first_name': 'Vendedor',
                'last_name': 'Principal',
                'role': 'Vendedor'
            },
            {
                'username': f'contador_{company.ruc}',
                'email': f'contador@{company.ruc}.com',
                'first_name': 'Contador',
                'last_name': 'Principal',
                'role': 'Contador'
            }
        ]
        
        for user_data in users_data:
            self._create_company_user(company, user_data, options)
    
    def _create_company_user(self, company, user_data, options):
        """Crear un usuario para la empresa"""
        email = user_data['email']
        
        # Verificar si ya existe
        if User.objects.filter(email=email).exists():
            if not options['force']:
                self.stdout.write(
                    self.style.WARNING(f'El usuario {email} ya existe')
                )
                return
            else:
                User.objects.filter(email=email).delete()
        
        # Generar contraseña temporal
        password = generate_temporary_password()
        
        # Crear usuario
        user = User.objects.create_user(
            username=user_data['username'],
            email=email,
            password=password,
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            document_type='cedula',
            document_number=f"098765432{len(User.objects.all())}",
            force_password_change=True
        )
        
        # Asignar a empresa
        user_company = UserCompany.objects.create(
            user=user,
            company=company
        )
        
        # Asignar rol
        try:
            role = Role.objects.get(name=user_data['role'])
            user_company.roles.add(role)
        except Role.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'Rol {user_data["role"]} no encontrado')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Usuario creado para {company.business_name}:\n'
                f'  Email: {email}\n'
                f'  Usuario: {user_data["username"]}\n'
                f'  Contraseña: {password}\n'
                f'  Rol: {user_data["role"]}'
            )
        )
    
    def _create_demo_users(self, options):
        """Crear usuarios de demostración"""
        demo_users = [
            {
                'username': 'demo_admin',
                'email': 'demo.admin@vendo.com',
                'first_name': 'Demo',
                'last_name': 'Administrador',
                'is_system_admin': True
            },
            {
                'username': 'demo_user',
                'email': 'demo.user@vendo.com',
                'first_name': 'Demo',
                'last_name': 'Usuario',
                'is_system_admin': False
            }
        ]
        
        for user_data in demo_users:
            email = user_data['email']
            
            if User.objects.filter(email=email).exists():
                if not options['force']:
                    continue
                else:
                    User.objects.filter(email=email).delete()
            
            password = 'demo123456'
            
            user = User.objects.create_user(
                username=user_data['username'],
                email=email,
                password=password,
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                document_type='cedula',
                document_number=f"111111111{len(User.objects.all())}",
                is_system_admin=user_data['is_system_admin']
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Usuario demo creado:\n'
                    f'  Email: {email}\n'
                    f'  Usuario: {user_data["username"]}\n'
                    f'  Contraseña: {password}'
                )
            )