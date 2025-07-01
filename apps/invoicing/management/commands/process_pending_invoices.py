from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.invoicing.models import Invoice
from apps.invoicing.tasks import get_authorization_async
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Procesa facturas pendientes de autorización'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=1,
            help='Facturas enviadas hace X horas sin respuesta'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Máximo número de facturas a procesar'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué facturas se procesarían'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        limit = options['limit']
        dry_run = options['dry_run']
        
        # Buscar facturas enviadas sin autorización
        time_threshold = timezone.now() - timedelta(hours=hours)
        pending_invoices = Invoice.objects.filter(
            estado_sri='ENVIADO',
            updated_at__lt=time_threshold
        )[:limit]
        
        self.stdout.write(f"Encontradas {pending_invoices.count()} facturas pendientes")
        
        processed = 0
        for invoice in pending_invoices:
            try:
                if dry_run:
                    self.stdout.write(f"[DRY RUN] Procesaría factura {invoice.numero_factura}")
                else:
                    # Programar tarea para obtener autorización
                    get_authorization_async.delay(str(invoice.id))
                    self.stdout.write(f"Programada verificación para {invoice.numero_factura}")
                
                processed += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error con factura {invoice.numero_factura}: {str(e)}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"Procesadas {processed} facturas")
        )