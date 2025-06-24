"""
URLs del módulo Core
"""
from django.urls import path, include
from django.views.generic import TemplateView

from . import views

app_name = 'core'

urlpatterns = [
    # Dashboard principal
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Gestión de empresas
    path('companies/', views.CompanyListView.as_view(), name='company_list'),
    path('companies/create/', views.CompanyCreateView.as_view(), name='company_create'),
    path('companies/<uuid:pk>/', views.CompanyDetailView.as_view(), name='company_detail'),
    path('companies/<uuid:pk>/edit/', views.CompanyUpdateView.as_view(), name='company_update'),
    path('companies/<uuid:pk>/delete/', views.CompanyDeleteView.as_view(), name='company_delete'),
    
    # Selección de empresa
    path('select-company/', views.SelectCompanyView.as_view(), name='select_company'),
    path('switch-company/<uuid:company_id>/', views.SwitchCompanyView.as_view(), name='switch_company'),
    
    # Gestión de sucursales
    path('branches/', views.BranchListView.as_view(), name='branch_list'),
    path('branches/create/', views.BranchCreateView.as_view(), name='branch_create'),
    path('branches/<uuid:pk>/', views.BranchDetailView.as_view(), name='branch_detail'),
    path('branches/<uuid:pk>/edit/', views.BranchUpdateView.as_view(), name='branch_update'),
    path('branches/<uuid:pk>/delete/', views.BranchDeleteView.as_view(), name='branch_delete'),
    
    # Selección de sucursal
    path('switch-branch/<uuid:branch_id>/', views.SwitchBranchView.as_view(), name='switch_branch'),
    
    # Auditoría
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_log_list'),
    path('audit-logs/<uuid:pk>/', views.AuditLogDetailView.as_view(), name='audit_log_detail'),
    
    # Perfil de usuario
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('profile/edit/', views.UserProfileUpdateView.as_view(), name='user_profile_update'),
    
    # API endpoints
    path('api/', include([
        path('companies/', views.CompanyAPIView.as_view(), name='api_companies'),
        path('branches/', views.BranchAPIView.as_view(), name='api_branches'),
        path('audit-logs/', views.AuditLogAPIView.as_view(), name='api_audit_logs'),
        path('dashboard-data/', views.DashboardDataAPIView.as_view(), name='api_dashboard_data'),
    ])),
    
    # Utilidades
    path('health-check/', views.HealthCheckView.as_view(), name='health_check'),
    path('system-info/', views.SystemInfoView.as_view(), name='system_info'),
    
    # Páginas de error personalizadas
    path('403/', TemplateView.as_view(template_name='core/errors/403.html'), name='error_403'),
    path('404/', TemplateView.as_view(template_name='core/errors/404.html'), name='error_404'),
    path('500/', TemplateView.as_view(template_name='core/errors/500.html'), name='error_500'),
]