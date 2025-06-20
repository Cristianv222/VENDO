from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Inicializa los datos básicos de la empresa VENDO'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            default='VENDO Corporation',
            help='Nombre de la empresa'
        )
        parser.add_argument(
            '--ruc',
            type=str,
            default='1234567890001',
            help='RUC de la empresa'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@vendo.com',
            help='Email del administrador'
        )
        parser.add_argument(
            '--admin-user',
            type=str,
            default='admin',
            help='Nombre de usuario administrador'
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='admin123',
            help='Contraseña del administrador'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar inicialización (sobrescribir datos existentes)'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Iniciando configuración de VENDO...')
        )
        
        try:
            with transaction.atomic():
                # 1. Crear superusuario
                self._create_superuser(options)
                
                # 2. Crear datos iniciales de empresa
                self._create_company_data(options)
                
                # 3. Crear categorías por defecto
                self._create_default_categories()
                
                # 4. Crear configuraciones iniciales
                self._create_initial_settings(options)
                
                # 5. Crear directorios necesarios
                self._create_directories()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        '✅ VENDO inicializado exitosamente!\n'
                        f'   Usuario admin: {options["admin_user"]}\n'
                        f'   Contraseña: {options["admin_password"]}\n'
                        f'   Email: {options["email"]}'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error durante la inicialización: {str(e)}')
            )
            raise CommandError(f'Falló la inicialización: {str(e)}')
    
    def _create_superuser(self, options):
        """Crear usuario administrador"""
        username = options['admin_user']
        email = options['email']
        password = options['admin_password']
        
        if User.objects.filter(username=username).exists():
            if options['force']:
                User.objects.filter(username=username).delete()
                self.stdout.write(f'🗑️  Usuario existente "{username}" eliminado')
            else:
                self.stdout.write(f'ℹ️  Usuario "{username}" ya existe, saltando...')
                return
        
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name='Administrador',
            last_name='VENDO'
        )
        
        self.stdout.write(f'👤 Superusuario "{username}" creado exitosamente')
    
    def _create_company_data(self, options):
        """Crear datos básicos de la empresa"""
        company_name = options['name']
        company_ruc = options['ruc']
        
        # Aquí crearías el modelo Company cuando lo tengas
        # Por ahora solo mostrar información
        self.stdout.write(f'🏢 Configurando empresa: {company_name}')
        self.stdout.write(f'📄 RUC: {company_ruc}')
        
        # Ejemplo de cómo sería con el modelo Company:
        # from apps.core.models import Company
        # company, created = Company.objects.get_or_create(
        #     ruc=company_ruc,
        #     defaults={
        #         'name': company_name,
        #         'address': 'Dirección de la empresa',
        #         'phone': '+593 99 999 9999',
        #         'email': options['email'],
        #         'is_active': True
        #     }
        # )
        # 
        # if created:
        #     self.stdout.write(f'🏢 Empresa "{company_name}" creada')
        # else:
        #     self.stdout.write(f'🏢 Empresa "{company_name}" ya existe')
    
    def _create_default_categories(self):
        """Crear categorías de productos por defecto"""
        categories = [
            'Electrónicos',
            'Ropa y Accesorios',
            'Hogar y Jardín',
            'Deportes',
            'Libros',
            'Salud y Belleza',
            'Automóvil',
            'Servicios'
        ]
        
        self.stdout.write('📁 Creando categorías por defecto...')
        
        # Aquí crearías las categorías cuando tengas el modelo
        # from apps.inventory.models import Category
        # for cat_name in categories:
        #     category, created = Category.objects.get_or_create(
        #         name=cat_name,
        #         defaults={
        #             'description': f'Categoría de {cat_name}',
        #             'is_active': True
        #         }
        #     )
        #     if created:
        #         self.stdout.write(f'  ✅ Categoría "{cat_name}" creada')
        
        for cat in categories:
            self.stdout.write(f'  📂 {cat}')
    
    def _create_initial_settings(self, options):
        """Crear configuraciones iniciales del sistema"""
        self.stdout.write('⚙️  Configurando ajustes iniciales...')
        
        # Configuraciones iniciales
        initial_settings = {
            'COMPANY_NAME': options['name'],
            'COMPANY_RUC': options['ruc'],
            'COMPANY_EMAIL': options['email'],
            'TAX_RATE': '12.00',  # IVA Ecuador
            'CURRENCY': 'USD',
            'DECIMAL_PLACES': '2',
            'LOW_STOCK_THRESHOLD': '10',
            'AUTO_BACKUP': 'True',
            'NOTIFICATION_EMAIL': options['email'],
        }
        
        # Aquí crearías las configuraciones cuando tengas el modelo
        # from apps.settings.models import SystemSetting
        # for key, value in initial_settings.items():
        #     setting, created = SystemSetting.objects.get_or_create(
        #         key=key,
        #         defaults={'value': value, 'description': f'Configuración {key}'}
        #     )
        #     if created:
        #         self.stdout.write(f'  ✅ Configuración "{key}" = "{value}"')
        
        for key, value in initial_settings.items():
            self.stdout.write(f'  ⚙️  {key} = {value}')
    
    def _create_directories(self):
        """Crear directorios necesarios para el proyecto"""
        directories = [
            'media',
            'media/invoices',
            'media/products',
            'media/company',
            'media/reports',
            'logs',
            'backups',
            'static',
            'templates/emails'
        ]
        
        self.stdout.write('📁 Creando directorios necesarios...')
        
        base_dir = settings.BASE_DIR
        
        for directory in directories:
            dir_path = os.path.join(base_dir, directory)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                self.stdout.write(f'  ✅ Directorio creado: {directory}')
            else:
                self.stdout.write(f'  ℹ️  Directorio ya existe: {directory}')
    
    def _show_summary(self, options):
        """Mostrar resumen de la configuración"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE CONFIGURACIÓN'))
        self.stdout.write('='*50)
        self.stdout.write(f'Empresa: {options["name"]}')
        self.stdout.write(f'RUC: {options["ruc"]}')
        self.stdout.write(f'Email: {options["email"]}')
        self.stdout.write(f'Usuario Admin: {options["admin_user"]}')
        self.stdout.write(f'URL Admin: http://127.0.0.1:8000/admin/')
        self.stdout.write('='*50)
        
        # Próximos pasos
        self.stdout.write('\n' + self.style.WARNING('PRÓXIMOS PASOS:'))
        self.stdout.write('1. python manage.py runserver')
        self.stdout.write('2. Visitar http://127.0.0.1:8000/admin/')
        self.stdout.write('3. Configurar datos adicionales de la empresa')
        self.stdout.write('4. Agregar productos y categorías')
        self.stdout.write('5. Configurar integración SRI')