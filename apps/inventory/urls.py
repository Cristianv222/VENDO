# apps/inventory/urls.py - VERSIÓN ACTUALIZADA CON ZEBRA

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'inventory'

# Router para API
router = DefaultRouter()
router.register(r'brands', views.BrandViewSet, basename='brand')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'stock-movements', views.StockMovementViewSet, basename='stockmovement')
router.register(r'stock-alerts', views.StockAlertViewSet, basename='stockalert')

urlpatterns = [
    # Dashboard principal
    path('', views.InventoryDashboardView.as_view(), name='dashboard'),
    
    # ==================== PRODUCTOS ====================
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<uuid:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<uuid:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    
    # ==================== CATEGORÍAS ====================
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<uuid:pk>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('categories/<uuid:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<uuid:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    
    # ==================== MARCAS ====================
    path('brands/', views.BrandListView.as_view(), name='brand_list'),
    path('brands/create/', views.BrandCreateView.as_view(), name='brand_create'),
    path('brands/<uuid:pk>/', views.BrandDetailView.as_view(), name='brand_detail'),
    path('brands/<uuid:pk>/edit/', views.BrandUpdateView.as_view(), name='brand_edit'),
    path('brands/<uuid:pk>/delete/', views.BrandDeleteView.as_view(), name='brand_delete'),
    
    # ==================== PROVEEDORES ====================
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('suppliers/<uuid:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<uuid:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_edit'),
    path('suppliers/<uuid:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier_delete'),
    
    # ==================== STOCK ====================
    path('stock/movement/', views.StockMovementView.as_view(), name='stock_movement'),
    path('stock/movements/', views.StockMovementListView.as_view(), name='stock_movements'),
    path('stock/movements/<uuid:pk>/', views.StockMovementDetailView.as_view(), name='stock_movement_detail'),
    
    # ==================== ALERTAS ====================
    path('stock/alerts/', views.StockAlertListView.as_view(), name='stock_alerts'),
    path('stock/alerts/<uuid:pk>/', views.StockAlertDetailView.as_view(), name='stock_alert_detail'),
    path('stock/alerts/<uuid:pk>/resolve/', views.resolve_stock_alert, name='resolve_stock_alert'),
    
    # ==================== REPORTES ====================
    path('reports/', views.ReportsView.as_view(), name='reports'),
    
    # ==================== AJAX ====================
    path('ajax/product-search/', views.ProductSearchView.as_view(), name='product_search'),
    path('ajax/category-profit/', views.CategoryProfitView.as_view(), name='ajax_category_profit'),
    
    # ==================== CÓDIGOS DE BARRAS Y ZEBRA USB ====================
    path('ajax/generate-barcode/', views.generate_barcode_ajax, name='generate_barcode_ajax'),
    path('ajax/print-barcode-zebra/', views.print_barcode_zebra, name='print_barcode_zebra'),
    path('ajax/test-zebra-printer/', views.test_zebra_printer, name='test_zebra_printer'),
    path('ajax/printer-status/', views.get_printer_status, name='printer_status'),
    path('ajax/available-ports/', views.get_available_ports, name='available_ports'),
    path('zebra-config/', views.zebra_config_view, name='zebra_config'),
    
    # ==================== API CON NAMESPACE ====================
    path('api/', include((router.urls, 'api'), namespace='api')),
]