"""
Comando personalizado para crear superusuario en VENDO.
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from apps.users.models import User, Role, UserProfile
import getpass


class Command(BaseCommand):
    help = 'Crear un superusuario para VENDO con información completa'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Nombre de usuario',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email del usuario',
        )
        parser.add_argument(
            '--first-name',
            type=str,
            help='Nombre',
        )
        parser.add_argument(
            '--last-name',
            type=str,
            help='Apellido',
        )
        parser.add_argument(
            '--document-number',
            type=str,
            help='Número de documento (cédula/RUC)',
        )
        parser.add_argument(
            '--phone',
            type=str,
            help='Teléfono',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='No solicitar input del usuario',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Creando superusuario para VENDO...\n')
        )

        # Recopilar información del usuario
        user_data = self.collect_user_data(options)
        
        try:
            with transaction.atomic():
                # Crear el superusuario
                user = self.create_superuser(user_data)
                
                # Crear perfil
                self.create_user_profile(user)
                
                # Asignar rol de administrador
                self.assign_admin_role(user)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ Superusuario creado exitosamente!\n'
                        f'   Usuario: {user.username}\n'
                        f'   Email: {user.email}\n'
                        f'   Nombre: {user.get_full_name()}\n'
                        f'   Documento: {user.document_number}\n'
                        f'\n🔗 Puedes acceder en: http://127.0.0.1:8000/admin/\n'
                    )
                )
                
        except Exception as e:
            raise CommandError(f'Error creando superusuario: {str(e)}')

    def collect_user_data(self, options):
        """Recopilar datos del usuario."""
        user_data = {}
        
        # Username
        user_data['username'] = options.get('username')
        if not user_data['username'] and not options['noinput']:
            while True:
                user_data['username'] = input('Nombre de usuario: ')
                if user_data['username']:
                    if User.objects.filter(username=user_data['username']).exists():
                        self.stdout.write(
                            self.style.ERROR('Este nombre de usuario ya existe.')
                        )
                        continue
                    break
                self.stdout.write(self.style.ERROR('El nombre de usuario es requerido.'))
        
        # Email
        user_data['email'] = options.get('email')
        if not user_data['email'] and not options['noinput']:
            while True:
                user_data['email'] = input('Email: ')
                if user_data['email']:
                    if User.objects.filter(email=user_data['email']).exists():
                        self.stdout.write(
                            self.style.ERROR('Este email ya está en uso.')
                        )
                        continue
                    break
                self.stdout.write(self.style.ERROR('El email es requerido.'))
        
        # Password
        if not options['noinput']:
            while True:
                password = getpass.getpass('Contraseña: ')
                if password:
                    try:
                        validate_password(password)
                        password_confirm = getpass.getpass('Confirmar contraseña: ')
                        if password == password_confirm:
                            user_data['password'] = password
                            break
                        else:
                            self.stdout.write(
                                self.style.ERROR('Las contraseñas no coinciden.')
                            )
                    except ValidationError as e:
                        self.stdout.write(
                            self.style.ERROR(f'Contraseña inválida: {", ".join(e.messages)}')
                        )
                else:
                    self.stdout.write(self.style.ERROR('La contraseña es requerida.'))
        else:
            user_data['password'] = 'admin123'  # Contraseña por defecto para noinput
        
        # Información personal
        user_data['first_name'] = options.get('first_name')
        if not user_data['first_name'] and not options['noinput']:
            user_data['first_name'] = input('Nombre: ') or 'Admin'
        elif not user_data['first_name']:
            user_data['first_name'] = 'Admin'
        
        user_data['last_name'] = options.get('last_name')
        if not user_data['last_name'] and not options['noinput']:
            user_data['last_name'] = input('Apellido: ') or 'VENDO'
        elif not user_data['last_name']:
            user_data['last_name'] = 'VENDO'
        
        # Documento
        user_data['document_number'] = options.get('document_number')
        if not user_data['document_number'] and not options['noinput']:
            while True:
                user_data['document_number'] = input('Número de documento (cédula/RUC): ')
                if user_data['document_number']:
                    if User.objects.filter(document_number=user_data['document_number']).exists():
                        self.stdout.write(
                            self.style.ERROR('Este número de documento ya está en uso.')
                        )
                        continue
                    break
                self.stdout.write(self.style.ERROR('El número de documento es requerido.'))
        elif not user_data['document_number']:
            user_data['document_number'] = '9999999999'  # Documento por defecto
        
        # Teléfono
        user_data['phone'] = options.get('phone')
        if not user_data['phone'] and not options['noinput']:
            user_data['phone'] = input('Teléfono (opcional): ') or ''
        elif not user_data['phone']:
            user_data['phone'] = ''
        
        return user_data

    def create_superuser(self, user_data):
        """Crear el superusuario."""
        user = User.objects.create_superuser(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data['password'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            document_number=user_data['document_number'],
            phone=user_data['phone'],
            user_type='admin',
            is_active=True,
            is_staff=True
        )
        
        self.stdout.write(f'👤 Usuario creado: {user.username}')
        return user

    def create_user_profile(self, user):
        """Crear perfil del usuario."""
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'theme': 'light',
                'language': 'es',
                'timezone': 'America/Guayaquil',
                'email_notifications': True,
                'sms_notifications': False,
                'push_notifications': True,
            }
        )
        
        if created:
            self.stdout.write('📋 Perfil creado')
        return profile

    def assign_admin_role(self, user):
        """Asignar rol de administrador."""
        try:
            admin_role = Role.objects.get(code='admin')
            user.roles.add(admin_role)
            self.stdout.write(f'🔑 Rol asignado: {admin_role.name}')
        except Role.DoesNotExist:
            # Crear rol de administrador si no existe
            admin_role = Role.objects.create(
                name='Administrador',
                code='admin',
                description='Administrador del sistema con acceso completo',
                is_active=True
            )
            user.roles.add(admin_role)
            self.stdout.write(f'🔑 Rol creado y asignado: {admin_role.name}')

    def show_usage_info(self):
        """Mostrar información de uso."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('INFORMACIÓN DE USO'))
        self.stdout.write('='*60)
        self.stdout.write('1. Accede al panel de administración:')
        self.stdout.write('   http://127.0.0.1:8000/admin/')
        self.stdout.write('')
        self.stdout.write('2. Para iniciar el servidor de desarrollo:')
        self.stdout.write('   python manage.py runserver')
        self.stdout.write('')
        self.stdout.write('3. Para crear más usuarios usa el panel de admin o:')
        self.stdout.write('   python manage.py create_superuser')
        self.stdout.write('='*60)