"""
Formularios del módulo Users
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from .models import Role, Permission, UserCompany, UserProfile
from apps.core.models import Company, Branch

User = get_user_model()


class CustomAuthenticationForm(AuthenticationForm):
    """
    Formulario personalizado de autenticación para login con email
    """
    # ✅ CORREGIDO: Como tu modelo User usa email como USERNAME_FIELD
    username = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ingrese su email'),
            'autofocus': True
        })
    )
    password = forms.CharField(
        label=_('Contraseña'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ingrese su contraseña')
        })
    )
    remember_me = forms.BooleanField(
        label=_('Recordarme'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    # ✅ CORREGIDO: Sobrescribir error_messages
    error_messages = {
        'invalid_login': _(
            'Por favor, ingresa un email y contraseña correctos. '
            'Ten en cuenta que ambos campos pueden ser sensibles a mayúsculas.'
        ),
        'inactive': _('Esta cuenta está inactiva.'),
    }
    
    def clean_username(self):
        """
        Normalizar email a minúsculas
        """
        username = self.cleaned_data.get('username')
        if username:
            username = username.lower().strip()
        return username
    
    def clean(self):
        """
        Validación personalizada del formulario
        """
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username and password:
            self.user_cache = authenticate(
                self.request, 
                username=username, 
                password=password
            )
            
            if self.user_cache is None:
                raise ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login'
                )
            else:
                self.confirm_login_allowed(self.user_cache)
        
        return self.cleaned_data


class CustomUserCreationForm(UserCreationForm):
    """
    Formulario para crear usuarios
    """
    email = forms.EmailField(
        label=_('Email'),
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('email@ejemplo.com')
        })
    )
    first_name = forms.CharField(
        label=_('Nombres'),
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nombres')
        })
    )
    last_name = forms.CharField(
        label=_('Apellidos'),
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Apellidos')
        })
    )
    
    # ✅ CORREGIDO: Obtener choices correctamente
    document_type = forms.ChoiceField(
        label=_('Tipo de documento'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    document_number = forms.CharField(
        label=_('Número de documento'),
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Número de documento')
        })
    )
    phone = forms.CharField(
        label=_('Teléfono'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Teléfono')
        })
    )
    mobile = forms.CharField(
        label=_('Celular'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Celular')
        })
    )
    
    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'document_type', 'document_number', 'phone', 'mobile',
            'password1', 'password2'
        )
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Usuario')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ✅ CORREGIDO: Establecer choices dinámicamente
        self.fields['document_type'].choices = User._meta.get_field('document_type').choices
        
        # ✅ MEJORADO: Personalizar labels y help_text
        self.fields['username'].help_text = _('Identificador único del usuario en el sistema.')
        self.fields['email'].help_text = _('Este será el email para iniciar sesión.')
        self.fields['password1'].help_text = _('Mínimo 8 caracteres.')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            if User.objects.filter(email=email).exists():
                raise ValidationError(_('Ya existe un usuario con este email.'))
        return email
    
    def clean_document_number(self):
        document_number = self.cleaned_data.get('document_number')
        if User.objects.filter(document_number=document_number).exists():
            raise ValidationError(_('Ya existe un usuario con este número de documento.'))
        return document_number
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.lower().strip()
            if User.objects.filter(username=username).exists():
                raise ValidationError(_('Ya existe un usuario con este nombre de usuario.'))
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    """
    Formulario para actualizar usuarios
    """
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'document_type', 'document_number', 'phone', 'mobile',
            'avatar', 'birth_date', 'address', 'language', 'timezone',
            'is_active', 'is_staff'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'language': forms.Select(attrs={'class': 'form-control'}),
            'timezone': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise ValidationError(_('Ya existe un usuario con este email.'))
        return email
    
    def clean_document_number(self):
        document_number = self.cleaned_data.get('document_number')
        if User.objects.filter(document_number=document_number).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_('Ya existe un usuario con este número de documento.'))
        return document_number
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.lower().strip()
            if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
                raise ValidationError(_('Ya existe un usuario con este nombre de usuario.'))
        return username


class RoleForm(forms.ModelForm):
    """
    Formulario para roles
    """
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label=_('Permisos')
    )
    
    class Meta:
        model = Role
        fields = ['name', 'description', 'color', 'permissions', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Nombre del rol')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Descripción del rol')
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color',
                'value': '#007bff'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agrupar permisos por módulo
        self.fields['permissions'].queryset = Permission.objects.select_related().order_by('module', 'name')
        
        # ✅ MEJORADO: Personalizar el queryset y widget de permisos
        self.fields['permissions'].widget.attrs.update({
            'data-toggle': 'tooltip',
            'title': _('Seleccione los permisos que tendrá este rol')
        })
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            queryset = Role.objects.filter(name__iexact=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError(_('Ya existe un rol con este nombre.'))
        return name
    
    def clean_color(self):
        color = self.cleaned_data.get('color')
        if color and not color.startswith('#'):
            color = f'#{color}'
        return color


class UserCompanyForm(forms.ModelForm):
    """
    Formulario para gestionar acceso de usuario a empresa
    """
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label=_('Roles')
    )
    branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label=_('Sucursales'),
        help_text=_('Si no selecciona ninguna sucursal, el usuario tendrá acceso a todas.')
    )
    
    class Meta:
        model = UserCompany
        fields = ['roles', 'branches', 'is_admin']
        widgets = {
            'is_admin': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-toggle': 'tooltip',
                'title': _('Los administradores tienen acceso completo a la empresa')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        if company:
            self.fields['branches'].queryset = Branch.objects.filter(
                company=company,
                is_active=True
            ).order_by('name')
            
            # ✅ MEJORADO: Personalizar queryset de roles
            self.fields['roles'].queryset = Role.objects.filter(
                is_active=True
            ).order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        branches = cleaned_data.get('branches')
        is_admin = cleaned_data.get('is_admin')
        
        # ✅ VALIDACIÓN: Los administradores pueden tener sucursales específicas o todas
        if is_admin and branches and branches.count() == 0:
            # Si es admin pero no tiene sucursales seleccionadas, tendrá acceso a todas
            pass
        
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    """
    Formulario para perfil de usuario
    """
    class Meta:
        model = UserProfile
        fields = [
            'position', 'department', 'employee_code',
            'theme', 'sidebar_collapsed',
            'email_notifications', 'sms_notifications', 'system_notifications',
            'bio'
        ]
        widgets = {
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Cargo o posición')
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Departamento')
            }),
            'employee_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Código de empleado')
            }),
            'theme': forms.Select(attrs={'class': 'form-control'}),
            'sidebar_collapsed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'system_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Cuéntanos sobre ti...')
            }),
        }
    
    def clean_employee_code(self):
        employee_code = self.cleaned_data.get('employee_code')
        if employee_code:
            queryset = UserProfile.objects.filter(employee_code=employee_code)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError(_('Ya existe un usuario con este código de empleado.'))
        return employee_code


class BulkUserActionForm(forms.Form):
    """
    Formulario para acciones en lote sobre usuarios
    """
    ACTION_CHOICES = [
        ('activate', _('Activar usuarios')),
        ('deactivate', _('Desactivar usuarios')),
        ('add_role', _('Agregar rol')),
        ('remove_role', _('Quitar rol')),
        ('change_company', _('Cambiar empresa')),
        ('export', _('Exportar datos')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Acción')
    )
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label=_('Usuarios seleccionados')
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label=_('Rol')
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label=_('Empresa')
    )
    
    def __init__(self, *args, **kwargs):
        user_queryset = kwargs.pop('user_queryset', User.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['users'].queryset = user_queryset
        
        # ✅ MEJORADO: Personalizar querysets
        self.fields['role'].queryset = Role.objects.filter(is_active=True).order_by('name')
        self.fields['company'].queryset = Company.objects.filter(is_active=True).order_by('business_name')
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        users = cleaned_data.get('users')
        
        if not users:
            raise ValidationError(_('Debe seleccionar al menos un usuario.'))
        
        if action in ['add_role', 'remove_role'] and not cleaned_data.get('role'):
            raise ValidationError(_('Debe seleccionar un rol para esta acción.'))
        
        if action == 'change_company' and not cleaned_data.get('company'):
            raise ValidationError(_('Debe seleccionar una empresa para esta acción.'))
        
        return cleaned_data


class PasswordResetForm(forms.Form):
    """
    Formulario para reset de contraseña usando email
    """
    email = forms.EmailField(
        label=_('Email'),
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ingrese su email'),
            'autofocus': True,
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            if not User.objects.filter(email=email, is_active=True).exists():
                raise ValidationError(_('No existe un usuario activo con este email.'))
        return email


class ChangePasswordForm(forms.Form):
    """
    Formulario para cambiar contraseña
    """
    old_password = forms.CharField(
        label=_('Contraseña actual'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Contraseña actual')
        })
    )
    new_password1 = forms.CharField(
        label=_('Nueva contraseña'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nueva contraseña')
        })
    )
    new_password2 = forms.CharField(
        label=_('Confirmar nueva contraseña'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Confirmar nueva contraseña')
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError(_('La contraseña actual es incorrecta.'))
        return old_password
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        
        if password1 and password2:
            if password1 != password2:
                raise ValidationError(_('Las contraseñas no coinciden.'))
        
        return password2
    
    def save(self):
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        self.user.save()
        return self.user