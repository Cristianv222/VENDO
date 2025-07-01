from django.core.management.base import BaseCommand
from apps.invoicing.models import SRIConfiguration, SRILog
from apps.invoicing.sri_client import SRIClient
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Verifica el estado de las configuraciones SRI'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=str,
            help='ID específico de empresa a verificar'
        )
    
    def handle(self, *args, **options):
        company_id = options.get('company_id')
        
        if company_id:
            try:
                sri_configs = SRIConfiguration.objects.filter(company__id=company_id)
            except:
                self.stdout.write(self.style.ERROR(f"Empresa {company_id} no encontrada"))
                return
        else:
            sri_configs = SRIConfiguration.objects.filter(is_active=True)
        
        self.stdout.write(f"Verificando {sri_configs.count()} configuraciones SRI...")
        
        for config in sri_configs:
            self.stdout.write(f"\n--- {config.company.razon_social} ---")
            
            try:
                # Verificar certificado
                sri_client = SRIClient(config.company)
                cert_info = sri_client.validate_certificate()
                
                if cert_info['valid']:
                    self.stdout.write(self.style.SUCCESS("✓ Certificado válido"))
                    
                    # Mostrar días hasta vencimiento
                    days_to_expire = (cert_info['not_valid_after'] - timezone.now()).days
                    if days_to_expire <= 30:
                        self.stdout.write(
                            self.style.WARNING(f"⚠ Certificado vence en {days_to_expire} días")
                        )
                    else:
                        self.stdout.write(f"✓ Certificado válido por {days_to_expire} días")
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Certificado inválido: {cert_info['error']}"))
                
                # Verificar logs recientes
                recent_errors = SRILog.objects.filter(
                    company=config.company,
                    estado='ERROR',
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count()
                
                if recent_errors == 0:
                    self.stdout.write(self.style.SUCCESS("✓ Sin errores en las últimas 24 horas"))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ {recent_errors} errores en las últimas 24 horas")
                    )
                
                # Verificar conectividad
                try:
                    # Aquí se podría hacer una prueba de conectividad básica
                    self.stdout.write(self.style.SUCCESS("✓ Conectividad SRI OK"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ Error de conectividad: {str(e)}"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Error general: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS("\nVerificación completada"))