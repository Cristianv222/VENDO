from django import forms
from .models import SRIConfiguration, Invoice, Customer, Product, InvoiceDetail, InvoicePayment
from apps.settings.models import SRIConfiguration

class SRIConfigurationForm(forms.ModelForm):
    certificate_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña del certificado P12'
        }),
        label='Contraseña del Certificado'
    )
    
    email_host_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña del email'
        }),
        label='Contraseña del Email'
    )
    
    class Meta:
        model = SRIConfiguration
        fields = [
            'certificate_file', 'certificate_password', 'environment',
            'email_host', 'email_port', 'email_host_user', 
            'email_host_password', 'email_use_tls'
        ]
        widgets = {
            'certificate_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.p12'
            }),
            'environment': forms.Select(attrs={
                'class': 'form-control'
            }),
            'email_host': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'email_port': forms.NumberInput(attrs={
                'class': 'form-control'
            }),
            'email_host_user': forms.EmailInput(attrs={
                'class': 'form-control'
            }),
            'email_use_tls': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['tipo_identificacion', 'identificacion', 'razon_social', 'direccion', 'email', 'telefono']
        widgets = {
            'tipo_identificacion': forms.Select(attrs={'class': 'form-control'}),
            'identificacion': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '300'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
        }
    
    def clean_identificacion(self):
        identificacion = self.cleaned_data['identificacion']
        tipo_identificacion = self.cleaned_data.get('tipo_identificacion')
        
        # Validaciones específicas por tipo de identificación
        if tipo_identificacion == '05':  # Cédula
            if len(identificacion) != 10:
                raise forms.ValidationError('La cédula debe tener 10 dígitos')
        elif tipo_identificacion == '04':  # RUC
            if len(identificacion) != 13:
                raise forms.ValidationError('El RUC debe tener 13 dígitos')
        
        return identificacion

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'codigo_principal', 'codigo_auxiliar', 'descripcion', 'precio_unitario',
            'tiene_iva', 'porcentaje_iva', 'tiene_ice', 'porcentaje_ice'
        ]
        widgets = {
            'codigo_principal': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '25'}),
            'codigo_auxiliar': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '25'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '300'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tiene_iva': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'porcentaje_iva': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tiene_ice': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'porcentaje_ice': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'observaciones']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class InvoiceDetailForm(forms.ModelForm):
    class Meta:
        model = InvoiceDetail
        fields = ['product', 'cantidad', 'precio_unitario', 'descuento']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class InvoicePaymentForm(forms.ModelForm):
    class Meta:
        model = InvoicePayment
        fields = ['forma_pago', 'valor', 'plazo', 'unidad_tiempo']
        widgets = {
            'forma_pago': forms.Select(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'plazo': forms.NumberInput(attrs={'class': 'form-control'}),
            'unidad_tiempo': forms.TextInput(attrs={'class': 'form-control'}),
        }