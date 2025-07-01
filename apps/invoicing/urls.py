from django.urls import path
from . import views

app_name = 'invoicing'

urlpatterns = [
    # Dashboard
    path('', views.InvoicingDashboardView.as_view(), name='dashboard'),
    
    # Configuración SRI
    path('sri-configuration/', views.SRIConfigurationView.as_view(), name='sri_configuration'),
    path('test-sri-connection/', views.test_sri_connection, name='test_sri_connection'),
    path('test-email-connection/', views.test_email_connection, name='test_email_connection'),
    
    # Facturas
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<uuid:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<uuid:invoice_id>/resend-sri/', views.resend_to_sri, name='resend_to_sri'),
    path('invoices/<uuid:invoice_id>/get-authorization/', views.get_authorization, name='get_authorization'),
    path('invoices/<uuid:invoice_id>/send-email/', views.send_invoice_email, name='send_invoice_email'),
    path('invoices/<uuid:invoice_id>/download-pdf/', views.download_invoice_pdf, name='download_invoice_pdf'),
    path('invoices/<uuid:invoice_id>/download-xml/', views.download_invoice_xml, name='download_invoice_xml'),
    
    # Clientes
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/search/', views.customer_search, name='customer_search'),
    
    # Productos
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/search/', views.product_search, name='product_search'),
]