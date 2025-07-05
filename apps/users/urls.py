"""
URLs del módulo Users - SIN IMPORT CIRCULAR
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # ===================================
    # AUTENTICACIÓN
    # ===================================
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('password-change/', views.PasswordChangeView.as_view(), name='password_change'),
    
    # Password Reset URLs
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             subject_template_name='users/password_reset_subject.txt'
         ), 
         name='password_reset'),
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # ===================================
    # GESTIÓN DE USUARIOS
    # ===================================
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/<uuid:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<uuid:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    
    # ===================================
    # GESTIÓN DE ACCESOS A EMPRESA
    # ===================================
    path('users/<uuid:user_id>/company-access/', views.UserCompanyManageView.as_view(), name='user_company_manage'),
    
    # ===================================
    # GESTIÓN DE ROLES
    # ===================================
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<uuid:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<uuid:pk>/edit/', views.RoleUpdateView.as_view(), name='role_edit'),
    path('roles/<uuid:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    
    # ===================================
    # PERFIL DE USUARIO
    # ===================================
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/edit/', views.UserProfileUpdateView.as_view(), name='profile_edit'),
    
    # ===================================
    # SESIONES DE USUARIO
    # ===================================
    path('sessions/', views.UserSessionListView.as_view(), name='session_list'),
    
    # ===================================
    # API ENDPOINTS
    # ===================================
    path('api/users/', views.UserAPIView.as_view(), name='api_users'),
    path('api/roles/', views.RoleAPIView.as_view(), name='api_roles'),
    path('api/permissions/', views.PermissionAPIView.as_view(), name='api_permissions'),
     path('waiting-room/', views.WaitingRoomView.as_view(), name='waiting_room'),
    
    # Vista para usuarios rechazados
    path('account-rejected/', views.AccountRejectedView.as_view(), name='account_rejected'),
    
    # Vista para administradores - gestionar usuarios pendientes
    path('pending-approval/', views.PendingUsersView.as_view(), name='pending_users'),
    
    # APIs AJAX para aprobación/rechazo
    path('approve/<uuid:user_id>/', views.approve_user_ajax, name='approve_user'),
    path('reject/<uuid:user_id>/', views.reject_user_ajax, name='reject_user'),
    
    # API para obtener conteo de usuarios pendientes
    path('api/pending-count/', views.pending_users_count_ajax, name='pending_count'),
]

# NOTA: Se eliminó la línea problemática:
# path('', include('apps.core.urls')) que causaba import circular