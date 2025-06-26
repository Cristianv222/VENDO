"""
Comando para configurar OAuth providers en VENDO
"""
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Configurar OAuth providers para autenticación social'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--google-client-id',
            type=str,
            help='Google Client ID',
        )
        parser.add_argument(
            '--google-client-secret',
            type=str,
            help='Google Client Secret',
        )
        parser.add_argument(
            '--site-domain',
            type=str,
            default='localhost:8000',
            help='Dominio del sitio (default: localhost:8000)',
        )
        parser.add_argument(
            '--site-name',
            type=str,
            default='VENDO',
            help='Nombre del sitio (default: VENDO)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Configurando OAuth para VENDO...\n')
        )
        
        # 1. Configurar el sitio
        self.setup_site(options)
        
        # 2. Configurar Google OAuth
        self.setup_google_oauth(options)
        
        # 3. Mostrar resumen
        self.show_summary()
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Configuración OAuth completada!')
        )
    
    def setup_site(self, options):
        """Configurar el sitio de Django"""
        self.stdout.write('🌐 Configurando sitio...')
        
        site_domain = options['site_domain']
        site_name = options['site_name']
        
        try:
            site = Site.objects.get(pk=settings.SITE_ID)
            site.domain = site_domain
            site.name = site_name
            site.save()
            
            self.stdout.write(f'  ✅ Sitio actualizado: {site_name} ({site_domain})')
            
        except Site.DoesNotExist:
            site = Site.objects.create(
                pk=settings.SITE_ID,
                domain=site_domain,
                name=site_name
            )
            self.stdout.write(f'  ✅ Sitio creado: {site_name} ({site_domain})')
    
    def setup_google_oauth(self, options):
        """Configurar Google OAuth"""
        self.stdout.write('\n🔐 Configurando Google OAuth...')
        
        # Obtener credenciales de argumentos o variables de entorno
        client_id = (
            options.get('google_client_id') or 
            os.getenv('GOOGLE_CLIENT_ID')
        )
        client_secret = (
            options.get('google_client_secret') or 
            os.getenv('GOOGLE_CLIENT_SECRET')
        )
        
        if not client_id or not client_secret:
            self.stdout.write(
                self.style.WARNING(
                    '  ⚠️  Credenciales de Google no encontradas.\n'
                    '     Usa --google-client-id y --google-client-secret\n'
                    '     o configura GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en .env'
                )
            )
            return
        
        # Crear o actualizar SocialApp para Google
        social_app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google OAuth',
                'client_id': client_id,
                'secret': client_secret,
            }
        )
        
        # Asignar al sitio actual
        site = Site.objects.get(pk=settings.SITE_ID)
        social_app.sites.clear()
        social_app.sites.add(site)
        
        if created:
            self.stdout.write('  ✅ Google OAuth configurado')
        else:
            self.stdout.write('  ✅ Google OAuth actualizado')
            
        self.stdout.write(f'     Client ID: {client_id[:20]}...')
    
    def show_summary(self):
        """Mostrar resumen de la configuración"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 RESUMEN DE CONFIGURACIÓN'))
        self.stdout.write('='*60)
        
        # Información del sitio
        site = Site.objects.get(pk=settings.SITE_ID)
        self.stdout.write(f'🌐 Sitio: {site.name} ({site.domain})')
        
        # Providers configurados
        social_apps = SocialApp.objects.all()
        self.stdout.write(f'🔐 Providers OAuth: {social_apps.count()}')
        
        for app in social_apps:
            self.stdout.write(f'   • {app.provider}: {app.name}')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.WARNING('CONFIGURACIÓN DE GOOGLE CLOUD:'))
        self.stdout.write('1. Ve a https://console.cloud.google.com/')
        self.stdout.write('2. Crea un proyecto o selecciona uno existente')
        self.stdout.write('3. Habilita la API de Google+ o Google Identity')
        self.stdout.write('4. Crea credenciales OAuth 2.0')
        self.stdout.write('5. Agrega estas URLs autorizadas:')
        self.stdout.write(f'   - http://{site.domain}/accounts/google/login/callback/')
        if site.domain == 'localhost:8000':
            self.stdout.write('   - http://127.0.0.1:8000/accounts/google/login/callback/')
        self.stdout.write('6. Usa el Client ID y Client Secret generados')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.WARNING('PRÓXIMOS PASOS:'))
        self.stdout.write('1. python manage.py migrate')
        self.stdout.write('2. python manage.py runserver')
        self.stdout.write('3. Prueba el login en http://localhost:8000/users/login/')
        self.stdout.write('='*60)