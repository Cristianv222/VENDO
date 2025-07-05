# apps/users/migrations/0003_add_approval_status.py
"""
Migración para agregar el campo approval_status que falta
"""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        # Solo agregar el campo que realmente falta
        migrations.AddField(
            model_name='user',
            name='approval_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pendiente de aprobación'),
                    ('approved', 'Aprobado'),
                    ('rejected', 'Rechazado')
                ],
                default='pending',
                max_length=20,
                verbose_name='Estado de aprobación'
            ),
        ),
    ]