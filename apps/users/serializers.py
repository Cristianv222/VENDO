"""
Serializers del módulo Users
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import User, Role, Permission, UserCompany, UserProfile, UserSession
from apps.core.models import Company, Branch


class PermissionSerializer(serializers.ModelSerializer):
    """
    Serializer para permisos
    """
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'description', 'module']


class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer para roles
    """
    permissions = PermissionSerializer(many=True, read_only=True)
    permissions_count = serializers.IntegerField(source='permissions.count', read_only=True)
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'color', 'is_system_role',
            'permissions', 'permissions_count', 'is_active',
            'created_at', 'updated_at'
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer para perfil de usuario
    """
    class Meta:
        model = UserProfile
        fields = [
            'position', 'department', 'employee_code', 'theme',
            'sidebar_collapsed', 'email_notifications', 'sms_notifications',
            'system_notifications', 'bio', 'social_media'
        ]


class UserCompanySerializer(serializers.ModelSerializer):
    """
    Serializer para relación usuario-empresa
    """
    company_name = serializers.CharField(source='company.business_name', read_only=True)
    roles = RoleSerializer(many=True, read_only=True)
    roles_names = serializers.StringRelatedField(source='roles', many=True, read_only=True)
    
    class Meta:
        model = UserCompany
        fields = [
            'company', 'company_name', 'roles', 'roles_names',
            'is_admin', 'created_at'
        ]


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer para usuarios
    """
    profile = UserProfileSerializer(read_only=True)
    companies = UserCompanySerializer(source='usercompany_set', many=True, read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    last_login_display = serializers.DateTimeField(source='last_login', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'document_type', 'document_number', 'phone', 'mobile',
            'avatar', 'avatar_url', 'birth_date', 'address', 'language', 'timezone',
            'is_active', 'is_staff', 'is_system_admin', 'last_login', 'last_login_display',
            'last_activity', 'created_at', 'updated_at', 'profile', 'companies'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
        }
    
    def get_avatar_url(self, obj):
        """Obtiene la URL del avatar"""
        if obj.avatar:
            return obj.avatar.url
        return None
    
    def create(self, validated_data):
        """Crear usuario con contraseña encriptada"""
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        # Crear perfil automáticamente
        UserProfile.objects.get_or_create(user=user)
        
        return user
    
    def update(self, instance, validated_data):
        """Actualizar usuario"""
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserSessionSerializer(serializers.ModelSerializer):
    """
    Serializer para sesiones de usuario
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    company_name = serializers.CharField(source='company.business_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'user', 'user_name', 'company', 'company_name',
            'branch', 'branch_name', 'session_key', 'ip_address',
            'user_agent', 'login_at', 'last_activity', 'logout_at',
            'is_expired', 'duration'
        ]
    
    def get_duration(self, obj):
        """Calcula la duración de la sesión"""
        if obj.logout_at:
            duration = obj.logout_at - obj.login_at
        else:
            duration = obj.last_activity - obj.login_at
        
        return duration.total_seconds()


class LoginSerializer(serializers.Serializer):
    """
    Serializer para login via API
    """
    username = serializers.CharField()
    password = serializers.CharField(style={'input_type': 'password'})
    remember_me = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # Permitir login con email
            if '@' in username:
                try:
                    user = User.objects.get(email=username)
                    username = user.username
                except User.DoesNotExist:
                    pass
            
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    _('Credenciales incorrectas'),
                    code='authorization'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    _('Cuenta desactivada'),
                    code='authorization'
                )
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                _('Debe incluir username y password'),
                code='authorization'
            )


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer para cambio de contraseña
    """
    old_password = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()
    
    def validate_old_password(self, value):
        """Validar contraseña actual"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('Contraseña actual incorrecta'))
        return value
    
    def validate(self, attrs):
        """Validar que las contraseñas coincidan"""
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(_('Las contraseñas no coinciden'))
        return attrs
    
    def save(self):
        """Guardar nueva contraseña"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.password_changed_at = timezone.now()
        user.force_password_change = False
        user.save()
        return user