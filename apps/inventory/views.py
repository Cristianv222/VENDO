# apps/inventory/views.py - VERSIÓN CORREGIDA

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.views import View
from django.db import models
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
import json
import logging  # AGREGADO
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings

# Configurar logger - AGREGADO
logger = logging.getLogger(__name__)

# Importar modelos y serializers
from .models import (
    Brand, Category, Supplier, Product, Stock, 
    StockMovement, StockAlert, ProductImage
)
from .serializers import (
    BrandSerializer, CategorySerializer, SupplierSerializer,
    ProductSerializer, ProductListSerializer, StockMovementSerializer,
    StockAlertSerializer, ProductImportSerializer, BarcodeGenerationSerializer
)

# Importar servicios - AGREGADO
from .services import ZebraPrinterService, BarcodeGeneratorService

# ==================== VISTAS PRINCIPALES ====================

class InventoryDashboardView(LoginRequiredMixin, View):
    """Dashboard principal del inventario"""
    
    def get(self, request):
        try:
            # Estadísticas del dashboard
            total_products = Product.objects.filter(is_active=True).count()
            
            # Productos con bajo stock
            low_stock_products = Product.objects.filter(
                is_active=True,
                track_stock=True
            ).annotate(
                stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
            ).filter(
                stock_quantity__lte=models.F('min_stock')
            ).count()
            
            # Productos sin stock
            out_of_stock = Product.objects.filter(
                is_active=True,
                track_stock=True
            ).annotate(
                stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
            ).filter(
                stock_quantity__lte=0
            ).count()
            
            total_categories = Category.objects.filter(is_active=True).count()
            total_brands = Brand.objects.filter(is_active=True).count()
            
            # Productos con bajo stock para mostrar en el dashboard
            low_stock_list = Product.objects.filter(
                is_active=True,
                track_stock=True
            ).annotate(
                stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
            ).filter(
                stock_quantity__lte=models.F('min_stock')
            ).select_related('category', 'brand')[:10]
            
            # Movimientos recientes
            recent_movements = StockMovement.objects.select_related(
                'product', 'user'
            ).order_by('-created_at')[:10]
            
            # Alertas activas
            active_alerts = StockAlert.objects.filter(
                is_active=True
            ).select_related('product')[:10]
            
        except Exception as e:
            # Si hay algún error con la BD, usar valores por defecto
            total_products = 0
            low_stock_products = 0
            out_of_stock = 0
            total_categories = 0
            total_brands = 0
            low_stock_list = []
            recent_movements = []
            active_alerts = []
        
        context = {
            'total_products': total_products,
            'low_stock_products': low_stock_products,
            'out_of_stock': out_of_stock,
            'total_categories': total_categories,
            'total_brands': total_brands,
            'low_stock_list': low_stock_list,
            'recent_movements': recent_movements,
            'active_alerts': active_alerts,
        }
        
        return render(request, 'inventory/dashboard.html', context)

# ==================== VISTAS DE PRODUCTOS ====================

class ProductListView(LoginRequiredMixin, ListView):
    """Lista de productos"""
    model = Product
    template_name = 'inventory/products/list.html'
    context_object_name = 'products'
    paginate_by = 25
    
    def get_queryset(self):
        try:
            queryset = Product.objects.select_related(
                'category', 'brand', 'supplier'
            ).annotate(
                stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
            )
            
            # Filtros
            search = self.request.GET.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(sku__icontains=search) |
                    Q(barcode__icontains=search)
                )
            
            category = self.request.GET.get('category')
            if category:
                queryset = queryset.filter(category_id=category)
            
            brand = self.request.GET.get('brand')
            if brand:
                queryset = queryset.filter(brand_id=brand)
            
            low_stock = self.request.GET.get('low_stock')
            if low_stock == 'true':
                queryset = queryset.filter(
                    stock_quantity__lte=models.F('min_stock')  # CAMBIO AQUÍ
                )
            
            return queryset.order_by('name')
        except Exception:
            return Product.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['categories'] = Category.objects.filter(is_active=True)
            context['brands'] = Brand.objects.filter(is_active=True)
        except Exception:
            context['categories'] = []
            context['brands'] = []
        
        context['search'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_brand'] = self.request.GET.get('brand', '')
        return context

class ProductCreateView(LoginRequiredMixin, CreateView):
    """Crear producto"""
    model = Product
    template_name = 'inventory/products/create.html'
    fields = [
        'name', 'description', 'category', 'brand', 'supplier',
        'cost_price', 'sale_price', 'unit', 'weight', 'dimensions',
        'image', 'track_stock', 'min_stock', 'max_stock'
    ]
    success_url = reverse_lazy('inventory:product_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['categories'] = Category.objects.filter(is_active=True)
            context['brands'] = Brand.objects.filter(is_active=True)
            context['suppliers'] = Supplier.objects.filter(is_active=True)
        except Exception:
            context['categories'] = []
            context['brands'] = []
            context['suppliers'] = []
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Producto "{self.object.name}" creado exitosamente.')
        
        # Crear movimiento inicial de stock si se especifica
        initial_stock = self.request.POST.get('initial_stock')
        if initial_stock and int(initial_stock) > 0:
            try:
                StockMovement.objects.create(
                    product=self.object,
                    movement_type='IN',
                    reason='INITIAL',
                    quantity=int(initial_stock),
                    unit_cost=self.object.cost_price,
                    user=self.request.user,
                    notes='Stock inicial'
                )
            except Exception as e:
                messages.warning(self.request, f'Producto creado, pero error al crear stock inicial: {e}')
        
        return response

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    """Editar producto"""
    model = Product
    template_name = 'inventory/products/edit.html'
    fields = [
        'name', 'description', 'category', 'brand', 'supplier',
        'cost_price', 'sale_price', 'unit', 'weight', 'dimensions',
        'image', 'track_stock', 'min_stock', 'max_stock', 'is_active'
    ]
    success_url = reverse_lazy('inventory:product_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['categories'] = Category.objects.filter(is_active=True)
            context['brands'] = Brand.objects.filter(is_active=True)
            context['suppliers'] = Supplier.objects.filter(is_active=True)
            context['stock_movements'] = self.object.stock_movements.order_by('-created_at')[:10]
        except Exception:
            context['categories'] = []
            context['brands'] = []
            context['suppliers'] = []
            context['stock_movements'] = []
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Producto "{self.object.name}" actualizado exitosamente.')
        return response

class ProductDetailView(LoginRequiredMixin, DetailView):
    """Detalle de producto"""
    model = Product
    template_name = 'inventory/products/detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['stock_movements'] = self.object.stock_movements.select_related(
                'user'
            ).order_by('-created_at')
            context['stock_alerts'] = self.object.stock_alerts.filter(
                is_active=True
            )
            # Usar la propiedad del modelo directamente
            context['current_stock'] = self.object.current_stock
        except Exception:
            context['stock_movements'] = []
            context['stock_alerts'] = []
            context['current_stock'] = 0
        return context

# ==================== VISTAS DE CATEGORÍAS ====================

class CategoryListView(LoginRequiredMixin, ListView):
    """Lista de categorías"""
    model = Category
    template_name = 'inventory/categories/list.html'
    context_object_name = 'categories'
    paginate_by = 25
    
    def get_queryset(self):
        try:
            queryset = Category.objects.annotate(
                products_count=Count('product')
            )
            
            search = self.request.GET.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(description__icontains=search)
                )
            
            parent = self.request.GET.get('parent')
            if parent == 'null':
                queryset = queryset.filter(parent__isnull=True)
            elif parent:
                queryset = queryset.filter(parent_id=parent)
            
            is_active = self.request.GET.get('is_active')
            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)
            
            return queryset.order_by('name')
        except Exception:
            return Category.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        
        try:
            context['total_categories'] = Category.objects.count()
            context['parent_categories'] = Category.objects.filter(parent__isnull=True).count()
            context['subcategories'] = Category.objects.filter(parent__isnull=False).count()
            context['avg_profit'] = Category.objects.aggregate(
                avg_profit=Avg('profit_percentage')
            )['avg_profit'] or 0
            context['parent_categories_list'] = Category.objects.filter(
                parent__isnull=True, is_active=True
            )
        except Exception:
            context['total_categories'] = 0
            context['parent_categories'] = 0
            context['subcategories'] = 0
            context['avg_profit'] = 0
            context['parent_categories_list'] = []
        
        return context

class CategoryCreateView(LoginRequiredMixin, CreateView):
    """Crear categoría"""
    model = Category
    template_name = 'inventory/categories/create.html'
    fields = ['name', 'description', 'parent', 'profit_percentage', 'is_active']
    success_url = reverse_lazy('inventory:category_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['parent_categories'] = Category.objects.filter(
                parent__isnull=True, is_active=True
            )
        except Exception:
            context['parent_categories'] = []
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Categoría "{self.object.name}" creada exitosamente.')
        return response

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Editar categoría"""
    model = Category
    template_name = 'inventory/categories/edit.html'
    fields = ['name', 'description', 'parent', 'profit_percentage', 'is_active']
    success_url = reverse_lazy('inventory:category_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['parent_categories'] = Category.objects.filter(
                parent__isnull=True, is_active=True
            ).exclude(pk=self.object.pk)
            context['category_products'] = self.object.product_set.filter(
                is_active=True
            )[:10]
            context['products_count'] = self.object.product_set.filter(
                is_active=True
            ).count()
        except Exception:
            context['parent_categories'] = []
            context['category_products'] = []
            context['products_count'] = 0
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Categoría "{self.object.name}" actualizada exitosamente.')
        return response

class CategoryDetailView(LoginRequiredMixin, DetailView):
    """Detalle de categoría"""
    model = Category
    template_name = 'inventory/categories/detail.html'
    context_object_name = 'category'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['products'] = self.object.product_set.filter(
                is_active=True
            ).select_related('brand', 'supplier')[:20]
            context['subcategories'] = self.object.subcategories.filter(
                is_active=True
            )
            context['total_products'] = self.object.product_set.filter(
                is_active=True
            ).count()
        except Exception:
            context['products'] = []
            context['subcategories'] = []
            context['total_products'] = 0
        return context

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar categoría"""
    model = Category
    template_name = 'inventory/categories/delete.html'
    success_url = reverse_lazy('inventory:category_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['products_count'] = self.object.product_set.count()
            context['subcategories_count'] = self.object.subcategories.count()
        except Exception:
            context['products_count'] = 0
            context['subcategories_count'] = 0
        return context
    
    def delete(self, request, *args, **kwargs):
        category = self.get_object()
        if category.product_set.exists():
            messages.error(
                request, 
                'No se puede eliminar la categoría porque tiene productos asociados.'
            )
            return redirect('inventory:category_detail', pk=category.pk)
        
        if category.subcategories.exists():
            messages.error(
                request, 
                'No se puede eliminar la categoría porque tiene subcategorías asociadas.'
            )
            return redirect('inventory:category_detail', pk=category.pk)
        
        messages.success(request, f'Categoría "{category.name}" eliminada exitosamente.')
        return super().delete(request, *args, **kwargs)

# ==================== VISTAS DE MARCAS ====================

class BrandListView(LoginRequiredMixin, ListView):
    """Lista de marcas"""
    model = Brand
    template_name = 'inventory/brands/list.html'
    context_object_name = 'brands'
    paginate_by = 25
    
    def get_queryset(self):
        try:
            queryset = Brand.objects.annotate(
                products_count=Count('product')
            )
            
            search = self.request.GET.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(description__icontains=search)
                )
            
            active_only = self.request.GET.get('active_only')
            if active_only == 'true':
                queryset = queryset.filter(is_active=True)
            
            return queryset.order_by('name')
        except Exception:
            return Brand.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        try:
            context['total_brands'] = Brand.objects.count()
            context['active_brands'] = Brand.objects.filter(is_active=True).count()
        except Exception:
            context['total_brands'] = 0
            context['active_brands'] = 0
        return context

class BrandCreateView(LoginRequiredMixin, CreateView):
    """Crear marca"""
    model = Brand
    template_name = 'inventory/brands/create.html'
    fields = ['name', 'description', 'logo', 'is_active']
    success_url = reverse_lazy('inventory:brand_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Marca "{self.object.name}" creada exitosamente.')
        return response

class BrandUpdateView(LoginRequiredMixin, UpdateView):
    """Editar marca"""
    model = Brand
    template_name = 'inventory/brands/edit.html'
    fields = ['name', 'description', 'logo', 'is_active']
    success_url = reverse_lazy('inventory:brand_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['brand_products'] = self.object.product_set.filter(
                is_active=True
            )[:10]
            context['products_count'] = self.object.product_set.filter(
                is_active=True
            ).count()
        except Exception:
            context['brand_products'] = []
            context['products_count'] = 0
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Marca "{self.object.name}" actualizada exitosamente.')
        return response

class BrandDetailView(LoginRequiredMixin, DetailView):
    """Detalle de marca"""
    model = Brand
    template_name = 'inventory/brands/detail.html'
    context_object_name = 'brand'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['products'] = self.object.product_set.filter(
                is_active=True
            ).select_related('category', 'supplier')[:20]
            context['total_products'] = self.object.product_set.filter(
                is_active=True
            ).count()
        except Exception:
            context['products'] = []
            context['total_products'] = 0
        return context

class BrandDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar marca"""
    model = Brand
    template_name = 'inventory/brands/delete.html'
    success_url = reverse_lazy('inventory:brand_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['products_count'] = self.object.product_set.count()
        except Exception:
            context['products_count'] = 0
        return context
    
    def delete(self, request, *args, **kwargs):
        brand = self.get_object()
        if brand.product_set.exists():
            messages.error(
                request, 
                'No se puede eliminar la marca porque tiene productos asociados.'
            )
            return redirect('inventory:brand_detail', pk=brand.pk)
        
        messages.success(request, f'Marca "{brand.name}" eliminada exitosamente.')
        return super().delete(request, *args, **kwargs)

# ==================== VISTAS DE PROVEEDORES ====================

class SupplierListView(LoginRequiredMixin, ListView):
    """Lista de proveedores"""
    model = Supplier
    template_name = 'inventory/suppliers/list.html'
    context_object_name = 'suppliers'
    paginate_by = 25
    
    def get_queryset(self):
        try:
            queryset = Supplier.objects.annotate(
                products_count=Count('product')
            )
            
            search = self.request.GET.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(ruc__icontains=search) |
                    Q(email__icontains=search) |
                    Q(contact_person__icontains=search)
                )
            
            active_only = self.request.GET.get('active_only')
            if active_only == 'true':
                queryset = queryset.filter(is_active=True)
            
            return queryset.order_by('name')
        except Exception:
            return Supplier.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        try:
            context['total_suppliers'] = Supplier.objects.count()
            context['active_suppliers'] = Supplier.objects.filter(is_active=True).count()
        except Exception:
            context['total_suppliers'] = 0
            context['active_suppliers'] = 0
        return context

class SupplierCreateView(LoginRequiredMixin, CreateView):
    """Crear proveedor"""
    model = Supplier
    template_name = 'inventory/suppliers/create.html'
    fields = ['name', 'ruc', 'email', 'phone', 'address', 'contact_person', 'is_active']
    success_url = reverse_lazy('inventory:supplier_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Proveedor "{self.object.name}" creado exitosamente.')
        return response

class SupplierUpdateView(LoginRequiredMixin, UpdateView):
    """Editar proveedor"""
    model = Supplier
    template_name = 'inventory/suppliers/edit.html'
    fields = ['name', 'ruc', 'email', 'phone', 'address', 'contact_person', 'is_active']
    success_url = reverse_lazy('inventory:supplier_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['supplier_products'] = self.object.product_set.filter(
                is_active=True
            )[:10]
            context['products_count'] = self.object.product_set.filter(
                is_active=True
            ).count()
        except Exception:
            context['supplier_products'] = []
            context['products_count'] = 0
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Proveedor "{self.object.name}" actualizado exitosamente.')
        return response

class SupplierDetailView(LoginRequiredMixin, DetailView):
    """Detalle de proveedor"""
    model = Supplier
    template_name = 'inventory/suppliers/detail.html'
    context_object_name = 'supplier'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['products'] = self.object.product_set.filter(
                is_active=True
            ).select_related('category', 'brand')[:20]
            context['total_products'] = self.object.product_set.filter(
                is_active=True
            ).count()
        except Exception:
            context['products'] = []
            context['total_products'] = 0
        return context

class SupplierDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar proveedor"""
    model = Supplier
    template_name = 'inventory/suppliers/delete.html'
    success_url = reverse_lazy('inventory:supplier_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['products_count'] = self.object.product_set.count()
        except Exception:
            context['products_count'] = 0
        return context
    
    def delete(self, request, *args, **kwargs):
        supplier = self.get_object()
        if supplier.product_set.exists():
            messages.error(
                request, 
                'No se puede eliminar el proveedor porque tiene productos asociados.'
            )
            return redirect('inventory:supplier_detail', pk=supplier.pk)
        
        messages.success(request, f'Proveedor "{supplier.name}" eliminado exitosamente.')
        return super().delete(request, *args, **kwargs)

# ==================== VISTAS DE STOCK ====================

class StockMovementView(LoginRequiredMixin, View):
    """Crear movimiento de stock"""
    
    def get(self, request):
        context = {}
        try:
            context['products'] = Product.objects.filter(is_active=True)[:50]
        except Exception:
            context['products'] = []
        return render(request, 'inventory/stock/movement.html', context)
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            movement_type = data.get('movement_type')
            quantity = int(data.get('quantity', 0))
            reason = data.get('reason')
            notes = data.get('notes', '')
            
            product = get_object_or_404(Product, id=product_id)
            
            # Validar cantidad para salidas
            if movement_type == 'OUT' and abs(quantity) > product.current_stock:
                return JsonResponse({
                    'success': False,
                    'message': 'No hay suficiente stock disponible'
                }, status=400)
            
            # Crear movimiento
            movement = StockMovement.objects.create(
                product=product,
                movement_type=movement_type,
                reason=reason,
                quantity=quantity if movement_type == 'IN' else -abs(quantity),
                unit_cost=product.cost_price,
                user=request.user,
                notes=notes
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Movimiento de stock registrado exitosamente',
                'new_stock': product.current_stock
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al registrar movimiento: {str(e)}'
            }, status=500)

class StockMovementListView(LoginRequiredMixin, ListView):
    """Lista de movimientos de stock"""
    model = StockMovement
    template_name = 'inventory/stock/movements.html'
    context_object_name = 'movements'
    paginate_by = 50
    
    def get_queryset(self):
        try:
            queryset = StockMovement.objects.select_related(
                'product', 'user'
            ).order_by('-created_at')
            
            # Filtros
            search = self.request.GET.get('search')
            if search:
                queryset = queryset.filter(
                    Q(product__name__icontains=search) |
                    Q(product__sku__icontains=search) |
                    Q(reference_document__icontains=search) |
                    Q(notes__icontains=search)
                )
            
            movement_type = self.request.GET.get('movement_type')
            if movement_type:
                queryset = queryset.filter(movement_type=movement_type)
            
            reason = self.request.GET.get('reason')
            if reason:
                queryset = queryset.filter(reason=reason)
            
            product_id = self.request.GET.get('product')
            if product_id:
                queryset = queryset.filter(product_id=product_id)
            
            return queryset
        except Exception:
            return StockMovement.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['selected_movement_type'] = self.request.GET.get('movement_type', '')
        context['selected_reason'] = self.request.GET.get('reason', '')
        context['selected_product'] = self.request.GET.get('product', '')
        
        try:
            context['movement_types'] = StockMovement.MOVEMENT_TYPES
            context['movement_reasons'] = StockMovement.MOVEMENT_REASONS
            context['recent_products'] = Product.objects.filter(
                stock_movements__isnull=False
            ).distinct()[:20]
            
            # Estadísticas
            context['total_movements'] = StockMovement.objects.count()
            context['entries_today'] = StockMovement.objects.filter(
                movement_type='IN',
                created_at__date=timezone.now().date()
            ).count()
            context['exits_today'] = StockMovement.objects.filter(
                movement_type='OUT',
                created_at__date=timezone.now().date()
            ).count()
        except Exception:
            context['movement_types'] = []
            context['movement_reasons'] = []
            context['recent_products'] = []
            context['total_movements'] = 0
            context['entries_today'] = 0
            context['exits_today'] = 0
        
        return context

class StockMovementDetailView(LoginRequiredMixin, DetailView):
    """Detalle de movimiento de stock"""
    model = StockMovement
    template_name = 'inventory/stock/movement_detail.html'
    context_object_name = 'movement'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            # Otros movimientos del mismo producto
            context['related_movements'] = StockMovement.objects.filter(
                product=self.object.product
            ).exclude(pk=self.object.pk).order_by('-created_at')[:10]
        except Exception:
            context['related_movements'] = []
        return context

# ==================== VISTAS DE ALERTAS DE STOCK ====================

class StockAlertListView(LoginRequiredMixin, ListView):
    """Lista de alertas de stock"""
    model = StockAlert
    template_name = 'inventory/stock/alerts.html'
    context_object_name = 'alerts'
    paginate_by = 25
    
    def get_queryset(self):
        try:
            queryset = StockAlert.objects.select_related('product').order_by('-created_at')
            
            # Filtros
            search = self.request.GET.get('search')
            if search:
                queryset = queryset.filter(
                    Q(product__name__icontains=search) |
                    Q(product__sku__icontains=search)
                )
            
            alert_type = self.request.GET.get('alert_type')
            if alert_type:
                queryset = queryset.filter(alert_type=alert_type)
            
            is_active = self.request.GET.get('is_active')
            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)
            
            return queryset
        except Exception:
            return StockAlert.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['selected_alert_type'] = self.request.GET.get('alert_type', '')
        context['selected_is_active'] = self.request.GET.get('is_active', '')
        
        try:
            context['alert_types'] = StockAlert.ALERT_TYPES
            
            # Estadísticas
            context['total_alerts'] = StockAlert.objects.count()
            context['active_alerts'] = StockAlert.objects.filter(is_active=True).count()
            context['resolved_alerts'] = StockAlert.objects.filter(is_active=False).count()
            context['critical_alerts'] = StockAlert.objects.filter(
                alert_type='OUT_OF_STOCK',
                is_active=True
            ).count()
        except Exception:
            context['alert_types'] = []
            context['total_alerts'] = 0
            context['active_alerts'] = 0
            context['resolved_alerts'] = 0
            context['critical_alerts'] = 0
        
        return context

class StockAlertDetailView(LoginRequiredMixin, DetailView):
    """Detalle de alerta de stock"""
    model = StockAlert
    template_name = 'inventory/stock/alert_detail.html'
    context_object_name = 'alert'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            # Historial de alertas del mismo producto
            context['product_alerts'] = StockAlert.objects.filter(
                product=self.object.product
            ).exclude(pk=self.object.pk).order_by('-created_at')[:10]
            
            # Movimientos recientes del producto
            context['recent_movements'] = self.object.product.stock_movements.order_by(
                '-created_at'
            )[:10]
        except Exception:
            context['product_alerts'] = []
            context['recent_movements'] = []
        return context

# ==================== VISTA DE REPORTES ====================

class ReportsView(LoginRequiredMixin, TemplateView):
    """Vista de reportes"""
    template_name = 'inventory/reports/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Estadísticas generales
            context['total_products'] = Product.objects.filter(is_active=True).count()
            context['total_categories'] = Category.objects.filter(is_active=True).count()
            context['total_brands'] = Brand.objects.filter(is_active=True).count()
            context['total_suppliers'] = Supplier.objects.filter(is_active=True).count()
            
            # Productos con stock bajo
            context['low_stock_count'] = Product.objects.filter(
                is_active=True,
                track_stock=True
            ).annotate(
                stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
            ).filter(
                stock_quantity__lte=models.F('min_stock')
            ).count()
            
            # Productos sin stock
            context['out_of_stock_count'] = Product.objects.filter(
                is_active=True,
                track_stock=True
            ).annotate(
                stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
            ).filter(
                stock_quantity__lte=0
            ).count()
            
            # Movimientos del último mes
            last_month = timezone.now() - timezone.timedelta(days=30)
            context['recent_movements'] = StockMovement.objects.filter(
                created_at__gte=last_month
            ).count()
            
            # Alertas activas
            context['active_alerts'] = StockAlert.objects.filter(is_active=True).count()
            
            # Top categorías con más productos
            context['top_categories'] = Category.objects.annotate(
                products_count=Count('product')
            ).filter(
                products_count__gt=0
            ).order_by('-products_count')[:5]
            
            # Top marcas con más productos
            context['top_brands'] = Brand.objects.annotate(
                products_count=Count('product')
            ).filter(
                products_count__gt=0
            ).order_by('-products_count')[:5]
            
        except Exception as e:
            # En caso de error, valores por defecto
            context.update({
                'total_products': 0,
                'total_categories': 0,
                'total_brands': 0,
                'total_suppliers': 0,
                'low_stock_count': 0,
                'out_of_stock_count': 0,
                'recent_movements': 0,
                'active_alerts': 0,
                'top_categories': [],
                'top_brands': [],
            })
        
        return context

# ==================== VISTAS AJAX ====================

class ProductSearchView(LoginRequiredMixin, View):
    """Vista para búsqueda de productos via AJAX"""
    
    def get(self, request):
        query = request.GET.get('q', '')
        limit = int(request.GET.get('limit', 10))
        
        results = []
        if query:
            try:
                products = Product.objects.filter(
                    Q(name__icontains=query) |
                    Q(sku__icontains=query) |
                    Q(barcode__icontains=query),
                    is_active=True
                ).select_related('category', 'brand')[:limit]
                
                for product in products:
                    results.append({
                        'id': product.id,
                        'name': product.name,
                        'sku': product.sku,
                        'barcode': product.barcode,
                        'category': product.category.name if product.category else '',
                        'brand': product.brand.name if product.brand else '',
                        'sale_price': float(product.sale_price),
                        'current_stock': product.current_stock,  # Usar la propiedad del modelo
                        'image_url': product.image.url if product.image else None
                    })
            except Exception:
                pass
        
        return JsonResponse({'results': results})

class CategoryProfitView(LoginRequiredMixin, View):
    """Vista para obtener el porcentaje de ganancia de una categoría"""
    
    def get(self, request):
        category_id = request.GET.get('category_id')
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                return JsonResponse({
                    'profit_percentage': float(category.profit_percentage)
                })
            except Category.DoesNotExist:
                pass
        
        return JsonResponse({'profit_percentage': 0})

# ==================== VIEWSETS PARA API ====================

class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['is_active']

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['parent', 'is_active']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Devuelve las categorías en estructura de árbol"""
        categories = Category.objects.filter(parent=None, is_active=True)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'ruc', 'email']
    filterset_fields = ['is_active']

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category', 'brand', 'supplier').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'sku', 'barcode', 'description']
    filterset_fields = ['category', 'brand', 'supplier', 'is_active', 'is_for_sale']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Productos con stock bajo"""
        products = self.queryset.annotate(
            stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
        ).filter(
            track_stock=True,
            stock_quantity__lte=models.F('min_stock')
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Productos sin stock"""
        products = self.queryset.annotate(
            stock_quantity=Sum('stock_movements__quantity')  # CAMBIO AQUÍ
        ).filter(
            track_stock=True,
            stock_quantity__lte=0
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def stock_movement(self, request, pk=None):
        """Registrar movimiento de stock"""
        product = self.get_object()
        serializer = StockMovementSerializer(data=request.data)
        
        if serializer.is_valid():
            movement = serializer.save(
                product=product,
                user=request.user
            )
            return Response(
                StockMovementSerializer(movement).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related('product', 'user').all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['product__name', 'product__sku', 'reference_document']
    filterset_fields = ['movement_type', 'reason', 'product']
    ordering = ['-created_at']

class StockAlertViewSet(viewsets.ModelViewSet):
    queryset = StockAlert.objects.select_related('product').all()
    serializer_class = StockAlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['alert_type', 'is_active', 'product']
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolver una alerta"""
        alert = self.get_object()
        alert.resolve(request.user)
        return Response({'message': 'Alerta resuelta exitosamente'})
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Alertas activas"""
        alerts = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)
    
@login_required
@require_http_methods(["POST"])
def resolve_stock_alert(request, pk):
    """Vista para resolver una alerta de stock via AJAX"""
    try:
        alert = get_object_or_404(StockAlert, pk=pk)
        
        if not alert.is_active:
            return JsonResponse({
                'success': False,
                'message': 'Esta alerta ya fue resuelta'
            }, status=400)
        
        alert.resolve(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Alerta de {alert.product.name} resuelta exitosamente'
        })
        
    except StockAlert.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Alerta no encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al resolver la alerta: {str(e)}'
        }, status=500)
@login_required
@require_http_methods(["POST"])
@csrf_exempt
def print_barcode_zebra(request):
    """Vista para imprimir código de barras en impresora Zebra USB"""
    try:
        data = json.loads(request.body)
        barcode = data.get('barcode', '')
        product_name = data.get('product_name', '')
        sale_price = data.get('sale_price', '')
        copies = int(data.get('copies', 1))
        
        if not barcode:
            return JsonResponse({
                'success': False,
                'message': 'Código de barras requerido'
            }, status=400)
        
        # Validar código de barras
        from .services import BarcodeGeneratorService
        is_valid, message = BarcodeGeneratorService.validate_barcode(barcode)
        if not is_valid:
            return JsonResponse({
                'success': False,
                'message': message
            }, status=400)
        
        # Crear servicio de impresora Zebra
        zebra_service = ZebraPrinterService()
        
        # Imprimir
        success, message = zebra_service.print_barcode(
            barcode=barcode,
            product_name=product_name,
            sale_price=sale_price,
            copies=copies
        )
        
        if success:
            # Registrar en log de auditoría (opcional)
            logger.info(f"Usuario {request.user.username} imprimió código de barras {barcode}")
            
            return JsonResponse({
                'success': True,
                'message': message
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos JSON inválidos'
        }, status=400)
    except Exception as e:
        logger.error(f"Error en print_barcode_zebra: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def generate_barcode_ajax(request):
    """Vista AJAX para generar nuevo código de barras"""
    try:
        # Generar código de barras único
        barcode = BarcodeGeneratorService.generate_unique_barcode()
        
        return JsonResponse({
            'success': True,
            'barcode': barcode
        })
        
    except Exception as e:
        logger.error(f"Error generando código de barras: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error al generar código: {str(e)}'
        }, status=500)

@login_required
def test_zebra_printer(request):
    """Vista para probar conexión con impresora Zebra USB"""
    try:
        zebra_service = ZebraPrinterService()
        
        # Probar conexión
        success, message = zebra_service.test_connection()
        
        if request.headers.get('Content-Type') == 'application/json' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({
                'success': success,
                'message': message
            })
        else:
            if success:
                messages.success(request, f'Prueba de impresora exitosa: {message}')
            else:
                messages.error(request, f'Error en prueba de impresora: {message}')
            return redirect('inventory:dashboard')
            
    except Exception as e:
        logger.error(f"Error en test de impresora: {str(e)}")
        if request.headers.get('Content-Type') == 'application/json' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
        else:
            messages.error(request, f'Error en prueba: {str(e)}')
            return redirect('inventory:dashboard')

@login_required
@require_http_methods(["GET"])
def get_printer_status(request):
    """Vista para obtener el estado de la impresora Zebra USB"""
    try:
        zebra_service = ZebraPrinterService()
        
        # Obtener puertos disponibles
        available_ports = zebra_service.get_available_ports()
        
        # Buscar puerto de Zebra
        zebra_port = zebra_service.find_zebra_port()
        
        return JsonResponse({
            'success': True,
            'zebra_port': zebra_port,
            'available_ports': available_ports,
            'configured_port': zebra_service.port,
            'printer_name': zebra_service.printer_name
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error verificando estado: {str(e)}'
        }, status=500)

@login_required
def zebra_config_view(request):
    """Vista para configurar la impresora Zebra"""
    if request.method == 'GET':
        zebra_service = ZebraPrinterService()
        available_ports = zebra_service.get_available_ports()
        zebra_port = zebra_service.find_zebra_port()
        
        context = {
            'available_ports': available_ports,
            'zebra_port': zebra_port,
            'configured_port': zebra_service.port,
            'printer_name': zebra_service.printer_name,
        }
        
        return render(request, 'inventory/zebra_config.html', context)
    
    elif request.method == 'POST':
        # Guardar configuración (esto requeriría un modelo de configuración)
        # Por ahora solo mostrar la información
        messages.info(request, 'La configuración se guarda en settings.py')
        return redirect('inventory:zebra_config')

@login_required
@require_http_methods(["GET"])
def get_available_ports(request):
    """Vista AJAX para obtener puertos seriales disponibles"""
    try:
        zebra_service = ZebraPrinterService()
        ports = zebra_service.get_available_ports()
        
        return JsonResponse({
            'success': True,
            'ports': ports
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)
@login_required
@require_http_methods(["POST"])
@csrf_exempt
def resolve_stock_alert(request, pk):
    """Vista para resolver una alerta de stock via AJAX"""
    try:
        alert = get_object_or_404(StockAlert, pk=pk)
        
        if not alert.is_active:
            return JsonResponse({
                'success': False,
                'message': 'Esta alerta ya fue resuelta'
            }, status=400)
        
        alert.resolve(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Alerta de {alert.product.name} resuelta exitosamente'
        })
        
    except StockAlert.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Alerta no encontrada'
        }, status=404)
    except Exception as e:
        logger.error(f"Error resolviendo alerta: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error al resolver la alerta: {str(e)}'
        }, status=500)