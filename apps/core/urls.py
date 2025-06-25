# apps/core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # ===================================
    # DASHBOARD Y SELECCIÓN DE EMPRESA
    # ===================================
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('select-company/', views.SelectCompanyView.as_view(), name='select_company'),
    
    # AHORA DISPONIBLES - Funciones implementadas en views
    path('switch-company/<uuid:company_id>/', views.SwitchCompanyView.as_view(), name='switch_company'),
    path('switch-branch/<uuid:branch_id>/', views.SwitchBranchView.as_view(), name='switch_branch'),
    
    # ===================================
    # GESTIÓN DE EMPRESAS
    # ===================================
    path('companies/', views.CompanyListView.as_view(), name='company_list'),
    path('companies/create/', views.CompanyCreateView.as_view(), name='company_create'),
    path('companies/<uuid:pk>/', views.CompanyDetailView.as_view(), name='company_detail'),
    path('companies/<uuid:pk>/edit/', views.CompanyUpdateView.as_view(), name='company_edit'),
    path('companies/<uuid:pk>/delete/', views.CompanyDeleteView.as_view(), name='company_delete'),
    
    # ===================================
    # GESTIÓN DE SUCURSALES
    # ===================================
    path('branches/', views.BranchListView.as_view(), name='branch_list'),
    path('branches/create/', views.BranchCreateView.as_view(), name='branch_create'),
    path('branches/<uuid:pk>/', views.BranchDetailView.as_view(), name='branch_detail'),
    path('branches/<uuid:pk>/edit/', views.BranchUpdateView.as_view(), name='branch_edit'),
    path('branches/<uuid:pk>/delete/', views.BranchDeleteView.as_view(), name='branch_delete'),
    
    # ===================================
    # AUDITORÍA Y LOGS
    # ===================================
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_log_list'),
    path('audit-logs/<uuid:pk>/', views.AuditLogDetailView.as_view(), name='audit_log_detail'),
    
    # ===================================
    # PERFIL DE USUARIO
    # ===================================
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('profile/edit/', views.UserProfileUpdateView.as_view(), name='user_profile_edit'),
    
    # ===================================
    # UTILIDADES Y SISTEMA
    # ===================================
    
    # AHORA DISPONIBLE - Función implementada
    path('health/', views.health_check, name='health_check'),
    path('system-info/', views.SystemInfoView.as_view(), name='system_info'),
    
    # ===================================
    # VISTAS DE SALUD Y MONITOREO
    # ===================================
    path('health-check/', views.HealthCheckView.as_view(), name='health_check_detailed'),
    
    # ===================================
    # API ENDPOINTS - AHORA DISPONIBLES
    # ===================================
    path('api/companies/', views.CompanyAPIView.as_view(), name='api_companies'),
    path('api/branches/', views.BranchAPIView.as_view(), name='api_branches'),
    path('api/audit-logs/', views.AuditLogAPIView.as_view(), name='api_audit_logs'),
    
    # ===================================
    # AJAX VIEWS PARA CAMBIOS RÁPIDOS (En desarrollo futuro)
    # ===================================
    # NOTA: Estas se implementarán cuando tengamos JavaScript avanzado
    # path('ajax/quick-company-switch/', views.quick_company_switch, name='ajax_quick_company_switch'),
    # path('ajax/quick-branch-switch/', views.quick_branch_switch, name='ajax_quick_branch_switch'),
]