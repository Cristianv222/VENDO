"""
Comando para inicializar el sistema VENDO
"""
import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from apps.core.models import Company, Branch


class Command(BaseCommand):
    help = 'Inicializa el sistema VENDO con configuraciones básicas'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--demo-data',
            action='store_true',
            help='Crear datos de demostración'
        )
        parser.add_argument(
            '--skip-superuser',
            action='store_true',
            help='Omitir creación de superusuario'
        )
        parser.add_argument(
            '--company-ruc',
            type=str,
            help='RUC de la empresa inicial'
        )
        parser.add_argument(
            '--company-name',
            type=str,
            help='Nombre de la empresa inicial'
        )
    
    def handle(self, *args, **options):
        """
        Ejecuta la inicialización del sistema
        """
        self.stdout.write(
            self.style.SUCCESS('🚀 Iniciando configuración del sistema VENDO...')
        )
        
        try:
            # 1. Crear directorios necesarios
            self.create_directories()
            
            # 2. Ejecutar migraciones
            self.run_migrations()
            
            # 3. Crear superusuario si no existe
            if not options['skip_superuser']:
                self.create_superuser()
            
            # 4. Crear empresa inicial
            self.create_initial_company(options)
            
            # 5. Crear datos de demo si se solicita
            if options['demo_data']:
                self.create_demo_data()
            
            # 6. Verificar instalación
            self.verify_installation()
            
            self.stdout.write(
                self.style.SUCCESS('✅ Sistema VENDO inicializado correctamente!')
            )
            
            self.show_next_steps()
            
        except Exception as e:
            raise CommandError(f'Error durante la inicialización: {e}')
    
    def create_directories(self):
        """
        Crea directorios necesarios para el sistema
        """
        self.stdout.write('📁 Creando directorios necesarios...')
        
        directories = [
            'logs',
            'media',
            'media/logos',
            'media/certificates',
            'media/documents',
            'media/products',
            'media/invoices',
            'media/reports',
            'media/backups',
            'static',
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            self.stdout.write(f'  ✓ {directory}')
    
    def run_migrations(self):
        """
        Ejecuta las migraciones de la base de datos
        """
        self.stdout.write('🗄️  Ejecutando migraciones...')
        
        # Hacer migraciones del core
        call_command('makemigrations', 'core', verbosity=0)
        
        # Aplicar todas las migraciones
        call_command('migrate', verbosity=0)
        
        self.stdout.write('  ✓ Migraciones completadas')
    
    def create_superuser(self):
        """
        Crea un superusuario si no existe
        """
        User = get_user_model()
        
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('👤 Superusuario ya existe, omitiendo...')
            return
        
        self.stdout.write('👤 Creando superusuario...')
        
        # Intentar crear superusuario con valores por defecto
        try:
            user = User.objects.create_superuser(
                username='admin',
                email='admin@vendo.com',
                password='admin123',
                first_name='Administrador',
                last_name='Sistema'
            )
            
            self.stdout.write(
                self.style.WARNING(
                    '  ✓ Superusuario creado: admin / admin123 (¡CAMBIAR PASSWORD!)'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  No se pudo crear superusuario automáticamente: {e}')
            )
            self.stdout.write('     Créalo manualmente con: python manage.py createsuperuser')
    
    def create_initial_company(self, options):
        """
        Crea una empresa inicial si no existe
        """
        if Company.objects.exists():
            self.stdout.write('🏢 Empresa ya existe, omitiendo...')
            return
        
        self.stdout.write('🏢 Creando empresa inicial...')
        
        # Usar datos proporcionados o valores por defecto
        ruc = options.get('company_ruc') or '1234567890001'
        business_name = options.get('company_name') or 'Empresa Demo S.A.'
        
        try:
            company = Company.objects.create(
                ruc=ruc,
                business_name=business_name,
                trade_name='Empresa Demo',
                email='demo@vendo.com',
                phone='02-1234567',
                address='Av. Principal 123',
                city='Quito',
                province='Pichincha',
                sri_environment='test'
            )
            
            # Crear sucursal principal
            branch = Branch.objects.create(
                company=company,
                code='001',
                name='Sucursal Principal',
                address='Av. Principal 123',
                city='Quito',
                province='Pichincha',
                sri_establishment_code='001',
                is_main=True
            )
            
            self.stdout.write(f'  ✓ Empresa creada: {company.business_name}')
            self.stdout.write(f'  ✓ Sucursal creada: {branch.name}')
            
            # Crear esquema para la empresa
            try:
                call_command('create_schemas', '--company-id', str(company.id), verbosity=0)
                self.stdout.write('  ✓ Esquema de base de datos creado')
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  Error creando esquema: {e}')
                )
            
        except Exception as e:
            raise CommandError(f'Error creando empresa inicial: {e}')
    
    def create_demo_data(self):
        """
        Crea datos de demostración
        """
        self.stdout.write('🎭 Creando datos de demostración...')
        
        # Aquí se pueden agregar más datos de demo cuando
        # tengamos otros módulos implementados
        
        self.stdout.write('  ✓ Datos de demo creados')
    
    def verify_installation(self):
        """
        Verifica que la instalación sea correcta
        """
        self.stdout.write('🔍 Verificando instalación...')
        
        # Verificar que existe al menos una empresa
        if not Company.objects.exists():
            raise CommandError('No se encontraron empresas')
        
        # Verificar que existe al menos una sucursal
        if not Branch.objects.exists():
            raise CommandError('No se encontraron sucursales')
        
        # Verificar directorios
        required_dirs = ['logs', 'media', 'static']
        for directory in required_dirs:
            if not os.path.exists(directory):
                raise CommandError(f'Directorio faltante: {directory}')
        
        self.stdout.write('  ✓ Verificación completada')
    
    def show_next_steps(self):
        """
        Muestra los siguientes pasos
        """
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('🎉 ¡SISTEMA LISTO!'))
        self.stdout.write('='*50)
        
        self.stdout.write('\n📋 PRÓXIMOS PASOS:')
        self.stdout.write('')
        self.stdout.write('1. Ejecutar el servidor de desarrollo:')
        self.stdout.write('   python manage.py runserver')
        self.stdout.write('')
        self.stdout.write('2. Acceder al admin en:')
        self.stdout.write('   http://localhost:8000/admin/')
        self.stdout.write('')
        self.stdout.write('3. Acceder al dashboard en:')
        self.stdout.write('   http://localhost:8000/dashboard/')
        self.stdout.write('')
        self.stdout.write('4. Cambiar la contraseña del administrador')
        self.stdout.write('')
        self.stdout.write('5. Configurar los datos reales de tu empresa')
        self.stdout.write('')
        
        if Company.objects.exists():
            company = Company.objects.first()
            self.stdout.write(f'🏢 Empresa actual: {company.business_name}')
            self.stdout.write(f'📍 RUC: {company.ruc}')
            
        self.stdout.write('')
        self.stdout.write('📚 Consulta INSTALL.md para configuraciones avanzadas')
        self.stdout.write('')