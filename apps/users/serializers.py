"""
Serializers para la API REST del módulo de usuarios.
"""

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import User, Role, Permission, UserProfile, UserRole, UserPermission, UserSession


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Permission."""
    
    class Meta:
        model = Permission
        fields = [
            'id', 'name', 'code', 'description', 'module', 
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class RoleSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Role."""
    
    user_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'code', 'description', 'is_active',
            'user_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_count']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer para el modelo UserProfile."""
    
    age = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'avatar', 'avatar_url', 'birth_date', 'bio', 'age',
            'theme', 'language', 'timezone',
            'email_notifications', 'sms_notifications', 'push_notifications',
            'default_pos_session_timeout', 'auto_print_receipts',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'age']

    def get_avatar_url(self, obj):
        """Obtener URL completa del avatar."""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer para la relación Usuario-Rol."""
    
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    assigned_by_username = serializers.CharField(source='assigned_by.username', read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'role', 'role_name', 'role_code',
            'assigned_by', 'assigned_by_username', 'assigned_at', 'is_active'
        ]
        read_only_fields = ['id', 'assigned_at', 'assigned_by']


class UserPermissionSerializer(serializers.ModelSerializer):
    """Serializer para la relación Usuario-Permiso."""
    
    permission_name = serializers.CharField(source='permission.name', read_only=True)
    permission_code = serializers.CharField(source='permission.code', read_only=True)
    permission_module = serializers.CharField(source='permission.module', read_only=True)
    granted_by_username = serializers.CharField(source='granted_by.username', read_only=True)
    
    class Meta:
        model = UserPermission
        fields = [
            'id', 'permission', 'permission_name', 'permission_code', 'permission_module',
            'granted_by', 'granted_by_username', 'granted_at', 'is_active'
        ]
        read_only_fields = ['id', 'granted_at', 'granted_by']


class UserListSerializer(serializers.ModelSerializer):
    """Serializer para listar usuarios (vista resumida)."""
    
    full_name = serializers.ReadOnlyField()
    primary_role = serializers.CharField(source='primary_role.name', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'document_number', 'phone', 'user_type', 'employee_code',
            'primary_role', 'avatar_url', 'is_active', 'last_login', 'created_at'
        ]

    def get_avatar_url(self, obj):
        """Obtener URL del avatar del perfil."""
        if hasattr(obj, 'profile') and obj.profile.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile.avatar.url)
            return obj.profile.avatar.url
        return None


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer para detalles completos del usuario."""
    
    full_name = serializers.ReadOnlyField()
    profile = UserProfileSerializer(read_only=True)
    roles = UserRoleSerializer(source='userrole_set', many=True, read_only=True)
    permissions = UserPermissionSerializer(source='userpermission_set', many=True, read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'document_type', 'document_number', 'phone', 'address',
            'user_type', 'employee_code', 'hire_date', 'department', 'position',
            'is_active', 'failed_login_attempts', 'last_password_change',
            'force_password_change', 'last_login', 'last_activity',
            'created_at', 'updated_at', 'profile', 'roles', 'permissions'
        ]
        read_only_fields = [
            'id', 'failed_login_attempts', 'last_password_change',
            'last_login', 'last_activity', 'created_at', 'updated_at'
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear usuarios."""
    
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    profile = UserProfileSerializer(required=False)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'document_type', 'document_number',
            'phone', 'address', 'user_type', 'hire_date', 'department',
            'position', 'is_active', 'profile'
        ]

    def validate(self, attrs):
        """Validaciones personalizadas."""
        # Verificar que las contraseñas coincidan
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': _('Las contraseñas no coinciden.')
            })
        
        # Validar la contraseña con las reglas de Django
        try:
            validate_password(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        
        # Verificar que el documento no esté duplicado
        document_number = attrs.get('document_number')
        if document_number and User.objects.filter(document_number=document_number).exists():
            raise serializers.ValidationError({
                'document_number': _('Ya existe un usuario con este número de documento.')
            })
        
        return attrs

    def create(self, validated_data):
        """Crear usuario con perfil."""
        profile_data = validated_data.pop('profile', {})
        validated_data.pop('password_confirm')
        
        # Crear usuario
        user = User.objects.create_user(**validated_data)
        
        # Crear o actualizar perfil
        if profile_data:
            UserProfile.objects.update_or_create(
                user=user,
                defaults=profile_data
            )
        else:
            # Crear perfil por defecto
            UserProfile.objects.create(user=user)
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar usuarios."""
    
    profile = UserProfileSerializer(required=False)
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'document_type',
            'document_number', 'phone', 'address', 'user_type',
            'hire_date', 'department', 'position', 'is_active',
            'force_password_change', 'profile'
        ]

    def validate_document_number(self, value):
        """Validar que el documento no esté duplicado (excepto el usuario actual)."""
        if value:
            user_id = self.instance.id if self.instance else None
            if User.objects.filter(document_number=value).exclude(id=user_id).exists():
                raise serializers.ValidationError(
                    _('Ya existe un usuario con este número de documento.')
                )
        return value

    def update(self, instance, validated_data):
        """Actualizar usuario y perfil."""
        profile_data = validated_data.pop('profile', {})
        
        # Actualizar usuario
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Actualizar perfil
        if profile_data:
            profile, created = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer para cambio de contraseña."""
    
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)

    def validate_current_password(self, value):
        """Validar contraseña actual."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('La contraseña actual es incorrecta.'))
        return value

    def validate(self, attrs):
        """Validar que las nuevas contraseñas coincidan."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': _('Las contraseñas no coinciden.')
            })
        
        # Validar la nueva contraseña
        try:
            validate_password(attrs['new_password'])
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        
        return attrs

    def save(self):
        """Guardar nueva contraseña."""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.force_password_change = False
        user.last_password_change = timezone.now()
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer para login de usuarios."""
    
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        """Validar credenciales de login."""
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            # Intentar autenticar
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
            
            if not user:
                # Incrementar intentos fallidos si el usuario existe
                try:
                    user_obj = User.objects.get(username=username)
                    user_obj.increment_failed_attempts()
                    
                    if user_obj.is_account_locked():
                        raise serializers.ValidationError(
                            _('Cuenta bloqueada por demasiados intentos fallidos.')
                        )
                except User.DoesNotExist:
                    pass
                
                raise serializers.ValidationError(
                    _('Credenciales inválidas.')
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    _('Esta cuenta está desactivada.')
                )
            
            if user.is_account_locked():
                raise serializers.ValidationError(
                    _('Cuenta bloqueada por demasiados intentos fallidos.')
                )
            
            attrs['user'] = user
            return attrs
        
        raise serializers.ValidationError(
            _('Debe proporcionar nombre de usuario y contraseña.')
        )


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer para sesiones de usuario."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'username', 'user_full_name', 'session_key',
            'ip_address', 'user_agent', 'location', 'is_active',
            'is_expired', 'created_at', 'last_activity'
        ]
        read_only_fields = ['id', 'created_at', 'last_activity']


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar solo el perfil del usuario actual."""
    
    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'bio', 'theme', 'language', 'timezone',
            'email_notifications', 'sms_notifications', 'push_notifications',
            'default_pos_session_timeout', 'auto_print_receipts'
        ]

    def update(self, instance, validated_data):
        """Actualizar perfil."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    """
Serializers adicionales faltantes para la aplicación Users.
AGREGAR ESTOS al archivo serializers.py existente.
"""

class UserListSerializer(serializers.ModelSerializer):
    """
    Serializer para lista de usuarios (vista simplificada).
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_names = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name', 'phone',
            'is_active', 'date_joined', 'last_login', 'last_activity',
            'department', 'role_names'
        ]
    
    def get_role_names(self, obj):
        """Obtener nombres de roles activos."""
        return [ur.role.name for ur in obj.get_active_roles()]


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para usuarios.
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile = UserProfileSerializer(read_only=True)
    active_roles = UserRoleSerializer(source='get_active_roles', many=True, read_only=True)
    permissions_list = serializers.ListField(source='get_permissions_list', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    default_branch_name = serializers.CharField(source='default_branch.name', read_only=True)
    is_account_locked = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'phone', 'document_number', 'department', 'is_active', 'is_staff', 
            'is_verified', 'date_joined', 'last_login', 'last_activity',
            'company', 'company_name', 'default_branch', 'default_branch_name',
            'profile', 'active_roles', 'permissions_list', 'failed_login_attempts',
            'is_account_locked', 'force_password_change', 'last_password_change'
        ]
        read_only_fields = [
            'date_joined', 'last_login', 'full_name', 'company_name',
            'default_branch_name', 'profile', 'active_roles', 'permissions_list',
            'failed_login_attempts', 'is_account_locked', 'last_password_change'
        ]
    
    def get_is_account_locked(self, obj):
        """Verificar si la cuenta está bloqueada."""
        return obj.is_account_locked()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar perfil de usuario.
    """
    class Meta:
        model = UserProfile
        fields = [
            'document_type', 'document_number', 'address', 'city', 'country',
            'position', 'department', 'hire_date', 'language', 'timezone',
            'avatar', 'email_notifications', 'sms_notifications'
        ]
    
    def validate_document_number(self, value):
        """Validar número de documento según el tipo."""
        if value:
            document_type = self.initial_data.get('document_type', 'cedula')
            
            if document_type == 'cedula' and len(value) != 10:
                raise serializers.ValidationError(
                    _('La cédula debe tener exactamente 10 dígitos.')
                )
            elif document_type == 'ruc' and len(value) != 13:
                raise serializers.ValidationError(
                    _('El RUC debe tener exactamente 13 dígitos.')
                )
        
        return value