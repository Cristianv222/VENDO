from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from .models import Invoice, Customer, Product, SRILog, SRIConfiguration
from .serializers import (
    InvoiceSerializer, InvoiceCreateSerializer, CustomerSerializer, 
    ProductSerializer, SRILogSerializer, SRIConfigurationSerializer,
    InvoiceActionResponseSerializer, SRITestResponseSerializer, EmailTestResponseSerializer
)
from .permissions import (
    IsInvoiceOwner, CanCreateInvoice, CanSendToSRI, CanConfigureSRI,
    CanManageCustomers, CanManageProducts
)
from .services import InvoiceService, CustomerService, ProductService
from .sri_client import SRIClient
from .email_service import EmailService
from .tasks import process_invoice_async, complete_invoice_process_async
import logging

logger = logging.getLogger(__name__)

class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsInvoiceOwner]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['estado_sri', 'customer', 'fecha_emision']
    search_fields = ['numero_factura', 'customer__razon_social', 'customer__identificacion']
    ordering_fields = ['fecha_emision', 'created_at', 'importe_total']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Invoice.objects.filter(
            company=self.request.user.company
        ).select_related('customer').prefetch_related('invoicedetail_set', 'invoicepayment_set')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, CanCreateInvoice]
        else:
            permission_classes = [IsAuthenticated, IsInvoiceOwner]
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Verificar configuración SRI
            try:
                SRIConfiguration.objects.get(company=request.user.company)
            except SRIConfiguration.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Debe configurar el SRI antes de crear facturas'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Crear factura usando el servicio
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.create_invoice(serializer.validated_data)
            
            if result['success']:
                # Procesar de forma asíncrona
                process_invoice_async.delay(str(result['invoice'].id))
                
                return Response({
                    'success': True,
                    'message': 'Factura creada y enviada a procesamiento',
                    'invoice': InvoiceSerializer(result['invoice']).data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': result['message']
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error creando factura: {str(e)}")
            return Response({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanSendToSRI])
    def resend_to_sri(self, request, pk=None):
        """Reenvía una factura al SRI"""
        invoice = self.get_object()
        
        try:
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.process_electronic_invoice(invoice)
            
            serializer = InvoiceActionResponseSerializer(data=result)
            serializer.is_valid()
            
            return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def get_authorization(self, request, pk=None):
        """Obtiene la autorización del SRI"""
        invoice = self.get_object()
        
        try:
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.get_authorization(invoice)
            
            serializer = InvoiceActionResponseSerializer(data=result)
            serializer.is_valid()
            
            return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """Envía la factura por email"""
        invoice = self.get_object()
        
        try:
            invoice_service = InvoiceService(request.user.company)
            result = invoice_service.send_invoice_email(invoice)
            
            serializer = InvoiceActionResponseSerializer(data=result)
            serializer.is_valid()
            
            return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Descarga el PDF de la factura"""
        invoice = self.get_object()
        
        try:
            from .pdf_generators import PDFGenerator
            from django.http import HttpResponse
            
            pdf_generator = PDFGenerator()
            pdf_content = pdf_generator.generate_invoice_pdf(invoice, invoice.xml_autorizado)
            
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Factura_{invoice.numero_factura}.pdf"'
            
            return response
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error generando PDF: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def download_xml(self, request, pk=None):
        """Descarga el XML de la factura"""
        invoice = self.get_object()
        
        try:
            from django.http import HttpResponse
            
            if not invoice.xml_autorizado:
                return Response({
                    'success': False,
                    'message': 'La factura no tiene XML autorizado'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            response = HttpResponse(invoice.xml_autorizado, content_type='application/xml')
            response['Content-Disposition'] = f'attachment; filename="Factura_{invoice.numero_factura}.xml"'
            
            return response
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error descargando XML: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Estadísticas de facturación"""
        try:
            company = request.user.company
            invoices = self.get_queryset()
            
            stats = {
                'total_facturas': invoices.count(),
                'facturas_pendientes': invoices.filter(estado_sri='PENDIENTE').count(),
                'facturas_enviadas': invoices.filter(estado_sri='ENVIADO').count(),
                'facturas_autorizadas': invoices.filter(estado_sri='AUTORIZADO').count(),
                'facturas_rechazadas': invoices.filter(estado_sri='RECHAZADO').count(),
                'total_facturado': sum(inv.importe_total for inv in invoices),
                'facturas_hoy': invoices.filter(fecha_emision__date=timezone.now().date()).count()
            }
            
            return Response(stats)
            
        except Exception as e:
            return Response({
                'error': f'Error obteniendo estadísticas: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, CanManageCustomers]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tipo_identificacion']
    search_fields = ['razon_social', 'identificacion', 'email']
    ordering_fields = ['razon_social', 'created_at']
    ordering = ['razon_social']
    
    def get_queryset(self):
        return Customer.objects.filter(company=self.request.user.company)
    
    def perform_create(self, serializer):
        customer_service = CustomerService(self.request.user.company)
        result = customer_service.create_or_update_customer(serializer.validated_data)
        
        if not result['success']:
            raise serializers.ValidationError(result['message'])
        
        return result['customer']
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Búsqueda rápida de clientes"""
        search = request.query_params.get('q', '')
        if not search:
            return Response({'customers': []})
        
        customers = self.get_queryset().filter(
            Q(razon_social__icontains=search) |
            Q(identificacion__icontains=search)
        )[:10]
        
        serializer = self.get_serializer(customers, many=True)
        return Response({'customers': serializer.data})

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, CanManageProducts]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tiene_iva', 'tiene_ice']
    search_fields = ['descripcion', 'codigo_principal', 'codigo_auxiliar']
    ordering_fields = ['descripcion', 'precio_unitario', 'created_at']
    ordering = ['descripcion']
    
    def get_queryset(self):
        return Product.objects.filter(company=self.request.user.company)
    
    def perform_create(self, serializer):
        product_service = ProductService(self.request.user.company)
        result = product_service.create_or_update_product(serializer.validated_data)
        
        if not result['success']:
            raise serializers.ValidationError(result['message'])
        
        return result['product']
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Búsqueda rápida de productos"""
        search = request.query_params.get('q', '')
        if not search:
            return Response({'products': []})
        
        products = self.get_queryset().filter(
            Q(descripcion__icontains=search) |
            Q(codigo_principal__icontains=search)
        )[:10]
        
        serializer = self.get_serializer(products, many=True)
        return Response({'products': serializer.data})

class SRILogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SRILogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['proceso', 'estado', 'invoice']
    search_fields = ['clave_acceso', 'error_message']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return SRILog.objects.filter(company=self.request.user.company)

class SRIConfigurationViewSet(viewsets.ModelViewSet):
    serializer_class = SRIConfigurationSerializer
    permission_classes = [IsAuthenticated, CanConfigureSRI]
    
    def get_queryset(self):
        return SRIConfiguration.objects.filter(company=self.request.user.company)
    
    def get_object(self):
        try:
            return SRIConfiguration.objects.get(company=self.request.user.company)
        except SRIConfiguration.DoesNotExist:
            # Crear configuración vacía si no existe
            return SRIConfiguration(company=self.request.user.company)
    
    @action(detail=False, methods=['post'])
    def test_sri_connection(self, request):
        """Prueba la conexión con el SRI"""
        try:
            sri_config = SRIConfiguration.objects.get(company=request.user.company)
            sri_client = SRIClient(request.user.company)
            certificate_info = sri_client.validate_certificate()
            
            response_data = {
                'success': True,
                'message': 'Conexión exitosa con el SRI',
                'certificate_info': certificate_info
            }
            
            serializer = SRITestResponseSerializer(data=response_data)
            serializer.is_valid()
            
            return Response(serializer.data)
            
        except SRIConfiguration.DoesNotExist:
            return Response({
                'success': False,
                'message': 'No existe configuración del SRI'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error conectando con el SRI: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def test_email_connection(self, request):
        """Prueba la conexión de email"""
        try:
            email_service = EmailService(request.user.company)
            result = email_service.test_email_connection()
            
            serializer = EmailTestResponseSerializer(data=result)
            serializer.is_valid()
            
            return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)