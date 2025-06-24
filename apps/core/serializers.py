"""
Serializers para la API REST del módulo Core
"""
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models import Company, Branch, AuditLog
from .validators import validate_ruc_ecuador


class CompanySerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Company
    """
    
    # Campos adicionales calculados
    branch_count = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    is_active_display = serializers.SerializerMethodField()
    
    # Campos de solo lectura
    schema_name = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Company
        fields = [
            'id',
            'ruc',
            'business_name',
            'trade_name',
            'email',
            'phone',
            'mobile',
            'address',
            'city',
            'province',
            'postal_code',
            'sri_environment',
            'logo',
            'logo_url',
            'schema_name',
            'is_active',
            'is_active_display',
            'branch_count',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'ruc': {
                'validators': [validate_ruc_ecuador],
                'help_text': _('RUC ecuatoriano de 13 dígitos')
            },
            'business_name': {
                'help_text': _('Razón social de la empresa')
            },
            'email': {
                'help_text': _('Email principal de la empresa')
            },
            'sri_environment': {
                'help_text': _('Ambiente SRI (test o production)')
            },
        }
    
    def get_branch_count(self, obj):
        """
        Obtiene el número de sucursales activas
        """
        return obj.branches.filter(is_active=True).count()
    
    def get_logo_url(self, obj):
        """
        Obtiene la URL del logo
        """
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
    
    def get_is_active_display(self, obj):
        """
        Obtiene el estado activo en formato legible
        """
        return _('Activo') if obj.is_active else _('Inactivo')
    
    def validate_ruc(self, value):
        """
        Validación adicional para RUC
        """
        # Verificar que no exista otra empresa con el mismo RUC
        if self.instance:
            # Si estamos actualizando, excluir la instancia actual
            existing = Company.objects.filter(ruc=value).exclude(id=self.instance.id)
        else:
            # Si estamos creando, verificar que no exista
            existing = Company.objects.filter(ruc=value)
        
        if existing.exists():
            raise serializers.ValidationError(
                _('Ya existe una empresa con este RUC.')
            )
        
        return value
    
    def validate(self, attrs):
        """
        Validación a nivel de objeto
        """
        # Si se está marcando como inactiva, verificar dependencias
        if 'is_active' in attrs and not attrs['is_active']:
            if self.instance and self.instance.branches.filter(is_active=True).exists():
                raise serializers.ValidationError({
                    'is_active': _('No se puede desactivar una empresa con sucursales activas.')
                })
        
        return attrs


class BranchSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Branch
    """
    
    # Campos relacionados
    company_name = serializers.CharField(source='company.business_name', read_only=True)
    company_ruc = serializers.CharField(source='company.ruc', read_only=True)
    
    # Campos adicionales calculados
    is_active_display = serializers.SerializerMethodField()
    is_main_display = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()
    
    # Campos de solo lectura
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Branch
        fields = [
            'id',
            'company',
            'company_name',
            'company_ruc',
            'code',
            'name',
            'email',
            'phone',
            'address',
            'city',
            'province',
            'full_address',
            'sri_establishment_code',
            'is_main',
            'is_main_display',
            'is_active',
            'is_active_display',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'code': {
                'help_text': _('Código único de la sucursal dentro de la empresa')
            },
            'sri_establishment_code': {
                'help_text': _('Código de establecimiento SRI (3 dígitos)')
            },
            'is_main': {
                'help_text': _('Marcar como sucursal principal')
            },
        }
    
    def get_is_active_display(self, obj):
        """
        Obtiene el estado activo en formato legible
        """
        return _('Activo') if obj.is_active else _('Inactivo')
    
    def get_is_main_display(self, obj):
        """
        Obtiene si es principal en formato legible
        """
        return _('Principal') if obj.is_main else _('Secundaria')
    
    def get_full_address(self, obj):
        """
        Obtiene la dirección completa
        """
        return f"{obj.address}, {obj.city}, {obj.province}"
    
    def validate_code(self, value):
        """
        Validación para el código de sucursal
        """
        company = self.context.get('company') or getattr(self.instance, 'company', None)
        
        if company:
            # Verificar que el código sea único dentro de la empresa
            queryset = Branch.objects.filter(company=company, code=value)
            
            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)
            
            if queryset.exists():
                raise serializers.ValidationError(
                    _('Ya existe una sucursal con este código en la empresa.')
                )
        
        return value
    
    def validate_sri_establishment_code(self, value):
        """
        Validación para el código de establecimiento SRI
        """
        company = self.context.get('company') or getattr(self.instance, 'company', None)
        
        if company:
            # Verificar que el código SRI sea único dentro de la empresa
            queryset = Branch.objects.filter(company=company, sri_establishment_code=value)
            
            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)
            
            if queryset.exists():
                raise serializers.ValidationError(
                    _('Ya existe una sucursal con este código SRI en la empresa.')
                )
        
        return value
    
    def validate(self, attrs):
        """
        Validación a nivel de objeto
        """
        company = attrs.get('company') or getattr(self.instance, 'company', None)
        
        # Si se está marcando como principal, verificar que no haya otra principal
        if attrs.get('is_main') and company:
            queryset = Branch.objects.filter(company=company, is_main=True)
            
            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)
            
            if queryset.exists():
                # Desmarcar la anterior como principal o mostrar error
                attrs['_unset_other_main'] = True
        
        return attrs
    
    def create(self, validated_data):
        """
        Crear nueva sucursal
        """
        unset_other_main = validated_data.pop('_unset_other_main', False)
        
        if unset_other_main:
            # Desmarcar otras sucursales como principales
            Branch.objects.filter(
                company=validated_data['company'],
                is_main=True
            ).update(is_main=False)
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """
        Actualizar sucursal
        """
        unset_other_main = validated_data.pop('_unset_other_main', False)
        
        if unset_other_main:
            # Desmarcar otras sucursales como principales
            Branch.objects.filter(
                company=instance.company,
                is_main=True
            ).exclude(id=instance.id).update(is_main=False)
        
        return super().update(instance, validated_data)


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo AuditLog
    """
    
    # Campos relacionados
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    company_name = serializers.CharField(source='company.business_name', read_only=True)
    content_type_name = serializers.CharField(source='content_type.name', read_only=True)
    
    # Campos adicionales calculados
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    formatted_changes = serializers.SerializerMethodField()
    time_since = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_username',
            'user_full_name',
            'company',
            'company_name',
            'action',
            'action_display',
            'content_type',
            'content_type_name',
            'object_id',
            'object_repr',
            'changes',
            'formatted_changes',
            'ip_address',
            'user_agent',
            'time_since',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['__all__']  # Todos los campos son de solo lectura
    
    def get_user_full_name(self, obj):
        """
        Obtiene el nombre completo del usuario
        """
        if obj.user:
            if obj.user.first_name or obj.user.last_name:
                return f"{obj.user.first_name} {obj.user.last_name}".strip()
            return obj.user.username
        return _('Sistema')
    
    def get_formatted_changes(self, obj):
        """
        Formatea los cambios para mostrar de manera legible
        """
        if not obj.changes:
            return []
        
        formatted = []
        
        for field, change in obj.changes.items():
            if isinstance(change, dict):
                if 'old' in change and 'new' in change:
                    formatted.append({
                        'field': field,
                        'type': 'update',
                        'old_value': change['old'],
                        'new_value': change['new'],
                        'description': _('%(field)s cambió de "%(old)s" a "%(new)s"') % {
                            'field': field,
                            'old': change['old'],
                            'new': change['new']
                        }
                    })
                elif 'new' in change:
                    formatted.append({
                        'field': field,
                        'type': 'create',
                        'value': change['new'],
                        'description': _('%(field)s establecido como "%(value)s"') % {
                            'field': field,
                            'value': change['new']
                        }
                    })
                elif 'deleted' in change:
                    formatted.append({
                        'field': field,
                        'type': 'delete',
                        'value': change['deleted'],
                        'description': _('%(field)s eliminado (valor: "%(value)s")') % {
                            'field': field,
                            'value': change['deleted']
                        }
                    })
            else:
                formatted.append({
                    'field': field,
                    'type': 'info',
                    'value': change,
                    'description': f"{field}: {change}"
                })
        
        return formatted
    
    def get_time_since(self, obj):
        """
        Obtiene el tiempo transcurrido desde la acción
        """
        from django.utils.timesince import timesince
        return timesince(obj.created_at)


class AuditLogDetailSerializer(AuditLogSerializer):
    """
    Serializer detallado para logs de auditoría
    """
    
    # Campos adicionales para vista detallada
    user_email = serializers.CharField(source='user.email', read_only=True)
    browser_info = serializers.SerializerMethodField()
    
    class Meta(AuditLogSerializer.Meta):
        fields = AuditLogSerializer.Meta.fields + [
            'user_email',
            'browser_info',
        ]
    
    def get_browser_info(self, obj):
        """
        Extrae información del navegador desde el user agent
        """
        if not obj.user_agent:
            return None
        
        # Aquí podrías usar una librería como user-agents para parsear
        # Por simplicidad, retornamos el user agent tal como está
        return {
            'user_agent': obj.user_agent[:200],  # Truncar si es muy largo
            'raw': obj.user_agent
        }