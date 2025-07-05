
"""
Comando para listar usuarios pendientes de aprobación
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.users.models import User
from apps.users.services import UserApprovalService


class Command(BaseCommand):
    help = 'Lista usuarios pendientes de aprobación'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'csv', 'json'],
            default='table',
            help='Formato de salida (table, csv, json)'
        )
        parser.add_argument(
            '--older-than',
            type=int,
            help='Mostrar solo usuarios pendientes hace más de X horas'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Número máximo de usuarios a mostrar'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Exportar a archivo (especificar ruta)'
        )
    
    def handle(self, *args, **options):
        format_type = options['format']
        older_than = options.get('older_than')
        limit = options['limit']
        export_file = options.get('export')
        
        # Obtener usuarios pendientes
        pending_users = UserApprovalService.get_pending_users()
        
        # Filtrar por tiempo si se especifica
        if older_than:
            cutoff_time = timezone.now() - timedelta(hours=older_than)
            pending_users = pending_users.filter(created_at__lt=cutoff_time)
        
        # Limitar resultados
        pending_users = pending_users[:limit]
        
        if not pending_users.exists():
            self.stdout.write(self.style.SUCCESS('✓ No hay usuarios pendientes de aprobación'))
            return
        
        # Generar salida según formato
        if format_type == 'table':
            self._output_table(pending_users)
        elif format_type == 'csv':
            output = self._output_csv(pending_users)
            if export_file:
                self._export_to_file(output, export_file)
            else:
                self.stdout.write(output)
        elif format_type == 'json':
            output = self._output_json(pending_users)
            if export_file:
                self._export_to_file(output, export_file)
            else:
                self.stdout.write(output)
    
    def _output_table(self, users):
        """Salida en formato tabla"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('USUARIOS PENDIENTES DE APROBACIÓN')
        self.stdout.write('='*80)
        
        for user in users:
            waiting_time = timezone.now() - user.created_at
            days = waiting_time.days
            hours = waiting_time.seconds // 3600
            
            self.stdout.write(f'\n📧 Email: {user.email}')
            self.stdout.write(f'👤 Nombre: {user.get_full_name()}')
            self.stdout.write(f'📱 Teléfono: {user.phone or "No proporcionado"}')
            self.stdout.write(f'📄 Documento: {user.get_document_type_display()} - {user.document_number or "No proporcionado"}')
            self.stdout.write(f'🕒 Registrado: {user.created_at.strftime("%d/%m/%Y %H:%M")}')
            self.stdout.write(f'⏰ Esperando: {days} días, {hours} horas')
            self.stdout.write('-' * 40)
        
        self.stdout.write(f'\nTotal: {users.count()} usuarios pendientes')
    
    def _output_csv(self, users):
        """Salida en formato CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'Email', 'Nombre Completo', 'Teléfono', 'Tipo Documento', 
            'Número Documento', 'Fecha Registro', 'Días Esperando'
        ])
        
        # Data
        for user in users:
            waiting_days = (timezone.now() - user.created_at).days
            writer.writerow([
                user.email,
                user.get_full_name(),
                user.phone or '',
                user.get_document_type_display(),
                user.document_number or '',
                user.created_at.strftime('%d/%m/%Y %H:%M'),
                waiting_days
            ])
        
        return output.getvalue()
    
    def _output_json(self, users):
        """Salida en formato JSON"""
        import json
        
        data = []
        for user in users:
            waiting_time = timezone.now() - user.created_at
            data.append({
                'email': user.email,
                'full_name': user.get_full_name(),
                'phone': user.phone,
                'document_type': user.get_document_type_display(),
                'document_number': user.document_number,
                'created_at': user.created_at.isoformat(),
                'waiting_days': waiting_time.days,
                'waiting_hours': waiting_time.seconds // 3600,
            })
        
        return json.dumps({
            'total_count': len(data),
            'users': data
        }, indent=2, ensure_ascii=False)
    
    def _export_to_file(self, content, filepath):
        """Exportar contenido a archivo"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.stdout.write(
                self.style.SUCCESS(f'✓ Datos exportados a: {filepath}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error exportando a {filepath}: {str(e)}')
            )
