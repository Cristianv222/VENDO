from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, CreateView, DetailView
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from apps.settings.models import SRIConfiguration
from .models import Invoice, Customer, Product, SRILog
from .forms import SRIConfigurationForm, InvoiceForm, CustomerForm, ProductForm
from .services import InvoiceService, CustomerService, ProductService
from .sri_client import SRIClient
from .email_service import EmailService
import json
import logging

logger = logging.getLogger(__name__)

# ===================== CONFIGURACIÓN SRI =====================

@method_decorator(login_required, name='dispatch')
class SRIConfigurationView(TemplateView):
    template_name = 'invoicing/sri_configuration.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            sri_config = SRIConfiguration.objects.get(company=self.request.user.company)
            context['sri_config'] = sri_config
            context['certificate_info'] = sri_config.validate_certificate() if hasattr(sri_config, 'validate_certificate') else None
        except SRIConfiguration.DoesNotExist:
            context['sri_config'] = None
            context['certificate_info'] = None
        
        context['form'] = SRIConfigurationForm()
        return context
    
    def post(self, request, *args, **kwargs):
        form = SRIConfigurationForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                sri_config, created = SRIConfiguration.objects.get_or_create(
                    company=request.user.company
                )
                
                # Actualizar campos
                for field, value in form.cleaned_data.items():
                    setattr(sri_config, field, value)
                
                sri_config.save()
                
                messages.success(request, 'Configuración SRI guardada exitosamente')
                return redirect('invoicing:sri_configuration')
                
            except Exception as e:
                messages.error(request, f'Error guardando configuración: {str(e)}')
        else:
            messages.error(request, 'Error en el formulario')
        
        return self.get(request, *args, **kwargs)

@csrf_exempt
@login_required
def test_sri_connection(request):
    """Prueba la conexión con el SRI"""
    if request.method == 'POST':
        try:
            sri_config = SRIConfiguration.objects.get(company=request.user.company)
            sri_client = SRIClient(request.user.company)
            certificate_info = sri_client.validate_certificate()
            
            return JsonResponse({
                'success': True,
                'message': 'Conexión exitosa con el SRI',
                'certificate_info': certificate_info
            })
            
        except SRIConfiguration.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'No existe configuración del SRI'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error conectando con el SRI: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@csrf_exempt
@login_required
def test_email_connection(request):
    """Prueba la conexión de email"""
    if request.method == 'POST':
        try:
            email_service = EmailService(request.user.company)
            result = email_service.test_email_connection()
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

# ===================== FACTURAS =====================

@method_decorator(login_required, name='dispatch')
class InvoiceListView(ListView):
    model = Invoice
    template_name = 'invoicing/invoices/list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Invoice.objects.filter(company=self.request.user.company).order_by('-created_at')
        
        # Filtros
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_factura__icontains=search) |
                Q(customer__razon_social__icontains=search) |
                Q(customer__identificacion__icontains=search)
            )
        
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado_sri=estado)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['estado'] = self.request.GET.get('estado', '')
        context['estados'] = ['PENDIENTE', 'ENVIADO', 'AUTORIZADO', 'RECHAZADO']
        return context

@method_decorator(login_required, name='dispatch')
class InvoiceCreateView(TemplateView):
    template_name = 'invoicing/invoices/create.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = InvoiceForm()
        context['customers'] = Customer.objects.filter(company=self.request.user.company)
        context['products'] = Product.objects.filter(company=self.request.user.company)
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            
            # Validar configuración SRI
            try:
                sri_config = SRIConfiguration.objects.get(company=request.user.company)
            except SRIConfiguration.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe configurar el SRI antes de crear facturas'
                })
            
            # Crear factura
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.complete_invoice_process(data)
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': result['message'],
                    'invoice_id': str(result['invoice'].id),
                    'numero_factura': result['invoice'].numero_factura
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Datos JSON inválidos'
            })
        except Exception as e:
            logger.error(f"Error creando factura: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            })

@method_decorator(login_required, name='dispatch')
class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = 'invoicing/invoices/detail.html'
    context_object_name = 'invoice'
    
    def get_queryset(self):
        return Invoice.objects.filter(company=self.request.user.company)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detalles'] = self.object.invoicedetail_set.all()
        context['pagos'] = self.object.invoicepayment_set.all()
        context['logs'] = SRILog.objects.filter(invoice=self.object).order_by('-created_at')
        return context

@login_required
def resend_to_sri(request, invoice_id):
    """Reenvía una factura al SRI"""
    if request.method == 'POST':
        try:
            invoice = get_object_or_404(Invoice, id=invoice_id, company=request.user.company)
            
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.process_electronic_invoice(invoice)
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
def get_authorization(request, invoice_id):
    """Obtiene la autorización de una factura"""
    if request.method == 'POST':
        try:
            invoice = get_object_or_404(Invoice, id=invoice_id, company=request.user.company)
            
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.get_authorization(invoice)
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
def send_invoice_email(request, invoice_id):
    """Envía una factura por email"""
    if request.method == 'POST':
        try:
            invoice = get_object_or_404(Invoice, id=invoice_id, company=request.user.company)
            
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.send_invoice_email(invoice)
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
def download_invoice_pdf(request, invoice_id):
    """Descarga el PDF de una factura"""
    try:
        invoice = get_object_or_404(Invoice, id=invoice_id, company=request.user.company)
        
        from .pdf_generators import PDFGenerator
        pdf_generator = PDFGenerator()
        pdf_content = pdf_generator.generate_invoice_pdf(invoice, invoice.xml_autorizado)
        
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Factura_{invoice.numero_factura}.pdf"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error generando PDF: {str(e)}')
        return redirect('invoicing:invoice_detail', pk=invoice_id)

@login_required
def download_invoice_xml(request, invoice_id):
    """Descarga el XML de una factura"""
    try:
        invoice = get_object_or_404(Invoice, id=invoice_id, company=request.user.company)
        
        if not invoice.xml_autorizado:
            messages.error(request, 'La factura no tiene XML autorizado')
            return redirect('invoicing:invoice_detail', pk=invoice_id)
        
        response = HttpResponse(invoice.xml_autorizado, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="Factura_{invoice.numero_factura}.xml"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error descargando XML: {str(e)}')
        return redirect('invoicing:invoice_detail', pk=invoice_id)

# ===================== CLIENTES =====================

@method_decorator(login_required, name='dispatch')
class CustomerListView(ListView):
    model = Customer
    template_name = 'invoicing/customers/list.html'
    context_object_name = 'customers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Customer.objects.filter(company=self.request.user.company).order_by('razon_social')
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(razon_social__icontains=search) |
                Q(identificacion__icontains=search) |
                Q(email__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context

@method_decorator(login_required, name='dispatch')
class CustomerCreateView(CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'invoicing/customers/create.html'
    
    def form_valid(self, form):
        customer_service = CustomerService(self.request.user.company)
        result = customer_service.create_or_update_customer(form.cleaned_data)
        
        if result['success']:
            messages.success(self.request, result['message'])
            return redirect('invoicing:customer_list')
        else:
            messages.error(self.request, result['message'])
            return self.form_invalid(form)

@csrf_exempt
@login_required
def customer_search(request):
    """Búsqueda AJAX de clientes"""
    if request.method == 'GET':
        search = request.GET.get('search', '')
        customers = Customer.objects.filter(
            company=request.user.company,
            razon_social__icontains=search
        )[:10]
        
        results = []
        for customer in customers:
            results.append({
                'id': str(customer.id),
                'identificacion': customer.identificacion,
                'razon_social': customer.razon_social,
                'direccion': customer.direccion,
                'email': customer.email,
                'telefono': customer.telefono,
                'tipo_identificacion': customer.tipo_identificacion
            })
        
        return JsonResponse({'customers': results})
    
    return JsonResponse({'customers': []})

# ===================== PRODUCTOS =====================

@method_decorator(login_required, name='dispatch')
class ProductListView(ListView):
    model = Product
    template_name = 'invoicing/products/list.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Product.objects.filter(company=self.request.user.company).order_by('descripcion')
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(descripcion__icontains=search) |
                Q(codigo_principal__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context

@method_decorator(login_required, name='dispatch')
class ProductCreateView(CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'invoicing/products/create.html'
    
    def form_valid(self, form):
        product_service = ProductService(self.request.user.company)
        result = product_service.create_or_update_product(form.cleaned_data)
        
        if result['success']:
            messages.success(self.request, result['message'])
            return redirect('invoicing:product_list')
        else:
            messages.error(self.request, result['message'])
            return self.form_invalid(form)

@csrf_exempt
@login_required
def product_search(request):
    """Búsqueda AJAX de productos"""
    if request.method == 'GET':
        search = request.GET.get('search', '')
        products = Product.objects.filter(
            company=request.user.company,
            descripcion__icontains=search
        )[:10]
        
        results = []
        for product in products:
            results.append({
                'id': str(product.id),
                'codigo_principal': product.codigo_principal,
                'codigo_auxiliar': product.codigo_auxiliar,
                'descripcion': product.descripcion,
                'precio_unitario': str(product.precio_unitario),
                'porcentaje_iva': str(product.porcentaje_iva),
                'porcentaje_ice': str(product.porcentaje_ice)
            })
        
        return JsonResponse({'products': results})
    
    return JsonResponse({'products': []})

# ===================== DASHBOARD =====================

@method_decorator(login_required, name='dispatch')
class InvoicingDashboardView(TemplateView):
    template_name = 'invoicing/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        company = self.request.user.company
        
        # Estadísticas
        total_facturas = Invoice.objects.filter(company=company).count()
        facturas_pendientes = Invoice.objects.filter(company=company, estado_sri='PENDIENTE').count()
        facturas_autorizadas = Invoice.objects.filter(company=company, estado_sri='AUTORIZADO').count()
        facturas_rechazadas = Invoice.objects.filter(company=company, estado_sri='RECHAZADO').count()
        
        # Facturas recientes
        facturas_recientes = Invoice.objects.filter(
            company=company
        ).order_by('-created_at')[:5]
        
        # Verificar configuración SRI
        try:
            sri_config = SRIConfiguration.objects.get(company=company)
            sri_configurado = True
        except SRIConfiguration.DoesNotExist:
            sri_configurado = False
        
        context.update({
            'total_facturas': total_facturas,
            'facturas_pendientes': facturas_pendientes,
            'facturas_autorizadas': facturas_autorizadas,
            'facturas_rechazadas': facturas_rechazadas,
            'facturas_recientes': facturas_recientes,
            'sri_configurado': sri_configurado
        })
        
        return context