"""
Vistas del módulo Users
"""
import json
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, 
    UpdateView, DeleteView, View, FormView
)
from django.urls import reverse_lazy, reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import Company, Branch
from apps.core.permissions import (
    CompanyPermissionMixin, SettingsPermissionMixin, company_required
)
from .models import User, Role, Permission, UserCompany, UserProfile, UserSession
from .serializers import UserSerializer, RoleSerializer, PermissionSerializer
from .permissions import RoleRequiredMixin, PermissionRequiredMixin
from .forms import (
    CustomUserCreationForm, UserUpdateForm, RoleForm, 
    UserCompanyForm, CustomAuthenticationForm
)


# ===================================
# VISTAS DE AUTENTICACIÓN
# ===================================

class CustomLoginView(FormView):
    """
    Vista personalizada de login
    """
    template_name = 'users/login.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('core:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        # Si ya está autenticado, redirigir
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        remember_me = form.cleaned_data.get('remember_me', False)
        
        user = authenticate(self.request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(self.request, user)
                
                # Configurar duración de sesión
                if not remember_me:
                    self.request.session.set_expiry(0)  # Expirar al cerrar navegador
                else:
                    self.request.session.set_expiry(30 * 24 * 60 * 60)  # 30 días
                
                # Registrar la sesión
                self.register_user_session(user)
                
                # Actualizar última actividad
                user.last_activity = timezone.now()
                user.save(update_fields=['last_activity'])
                
                # Mensaje de bienvenida
                messages.success(
                    self.request, 
                    _('Bienvenido %(name)s') % {'name': user.get_full_name()}
                )
                
                # Verificar si necesita seleccionar empresa
                if not user.is_system_admin and user.get_companies().count() > 1:
                    return redirect('core:select_company')
                elif user.get_companies().count() == 1:
                    # Auto-seleccionar empresa si solo tiene una
                    company = user.get_companies().first()
                    self.request.session['company_id'] = str(company.id)
                
                return redirect(self.get_success_url())
            else:
                messages.error(self.request, _('Su cuenta está desactivada'))
        else:
            messages.error(self.request, _('Credenciales incorrectas'))
        
        return self.form_invalid(form)
    
    def register_user_session(self, user):
        """Registra la sesión del usuario"""
        try:
            UserSession.objects.create(
                user=user,
                session_key=self.request.session.session_key,
                ip_address=self.get_client_ip(),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception:
            pass  # No fallar el login por problemas de registro de sesión
    
    def get_client_ip(self):
        """Obtiene la IP del cliente"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class CustomLogoutView(View):
    """
    Vista personalizada de logout
    """
    
    def get(self, request):
        return self.post(request)
    
    def post(self, request):
        if request.user.is_authenticated:
            # Marcar la sesión como cerrada
            try:
                session = UserSession.objects.get(
                    user=request.user,
                    session_key=request.session.session_key,
                    logout_at__isnull=True
                )
                session.logout_at = timezone.now()
                session.save()
            except UserSession.DoesNotExist:
                pass
            
            user_name = request.user.get_full_name()
            logout(request)
            messages.success(request, _('Sesión cerrada correctamente. ¡Hasta luego!'))
        
        return redirect('users:login')


class PasswordChangeView(LoginRequiredMixin, FormView):
    """
    Vista para cambiar contraseña
    """
    template_name = 'users/password_change.html'
    form_class = PasswordChangeForm
    success_url = reverse_lazy('users:profile')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        user = form.save()
        user.password_changed_at = timezone.now()
        user.force_password_change = False
        user.save(update_fields=['password_changed_at', 'force_password_change'])
        
        messages.success(self.request, _('Contraseña cambiada exitosamente'))
        return super().form_valid(form)


# ===================================
# VISTAS DE USUARIOS
# ===================================

class UserListView(LoginRequiredMixin, SettingsPermissionMixin, ListView):
    """
    Lista de usuarios
    """
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = User.objects.select_related('profile').prefetch_related('companies')
        
        # Filtros por empresa si no es admin del sistema
        if not self.request.user.is_system_admin and hasattr(self.request, 'company'):
            queryset = queryset.filter(companies=self.request.company)
        
        # Filtros de búsqueda
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(username__icontains=search) |
                Q(document_number__icontains=search)
            )
        
        # Filtro por estado
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Filtro por rol
        role_filter = self.request.GET.get('role')
        if role_filter:
            queryset = queryset.filter(usercompany__roles__id=role_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_roles'] = Role.objects.filter(is_active=True)
        return context


class UserDetailView(LoginRequiredMixin, SettingsPermissionMixin, DetailView):
    """
    Detalle de usuario
    """
    model = User
    template_name = 'users/user_detail.html'
    context_object_name = 'user_obj'
    
    def get_queryset(self):
        queryset = User.objects.select_related('profile').prefetch_related(
            'companies', 'usercompany_set__roles', 'usercompany_set__branches'
        )
        
        if not self.request.user.is_system_admin and hasattr(self.request, 'company'):
            queryset = queryset.filter(companies=self.request.company)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.get_object()
        
        # Información de empresas y roles
        if hasattr(self.request, 'company'):
            try:
                user_company = UserCompany.objects.get(
                    user=user_obj, 
                    company=self.request.company
                )
                context['user_company'] = user_company
                context['user_roles'] = user_company.roles.all()
                context['user_branches'] = user_company.branches.all()
            except UserCompany.DoesNotExist:
                context['user_company'] = None
        
        # Sesiones recientes
        context['recent_sessions'] = UserSession.objects.filter(
            user=user_obj
        ).order_by('-login_at')[:10]
        
        return context


class UserCreateView(LoginRequiredMixin, SettingsPermissionMixin, CreateView):
    """
    Crear usuario
    """
    model = User
    form_class = CustomUserCreationForm
    template_name = 'users/user_form.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Crear perfil automáticamente
        UserProfile.objects.get_or_create(user=self.object)
        
        # Asignar a empresa actual si existe
        if hasattr(self.request, 'company'):
            UserCompany.objects.create(
                user=self.object,
                company=self.request.company
            )
        
        messages.success(self.request, _('Usuario creado exitosamente'))
        return response
    
    def get_success_url(self):
        return reverse('users:user_detail', kwargs={'pk': self.object.pk})


class UserUpdateView(LoginRequiredMixin, SettingsPermissionMixin, UpdateView):
    """
    Actualizar usuario
    """
    model = User
    form_class = UserUpdateForm
    template_name = 'users/user_form.html'
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        if not self.request.user.is_system_admin and hasattr(self.request, 'company'):
            queryset = queryset.filter(companies=self.request.company)
        
        return queryset
    
    def form_valid(self, form):
        messages.success(self.request, _('Usuario actualizado exitosamente'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('users:user_detail', kwargs={'pk': self.object.pk})


class UserDeleteView(LoginRequiredMixin, SettingsPermissionMixin, DeleteView):
    """
    Eliminar usuario
    """
    model = User
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('users:user_list')
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        if not self.request.user.is_system_admin and hasattr(self.request, 'company'):
            queryset = queryset.filter(companies=self.request.company)
        
        return queryset
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Usuario eliminado exitosamente'))
        return super().delete(request, *args, **kwargs)


# ===================================
# VISTAS DE ROLES
# ===================================

class RoleListView(LoginRequiredMixin, SettingsPermissionMixin, ListView):
    """
    Lista de roles
    """
    model = Role
    template_name = 'users/role_list.html'
    context_object_name = 'roles'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Role.objects.prefetch_related('permissions').annotate(
            users_count=Count('user_companies__user', distinct=True)
        )
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset.order_by('name')


class RoleDetailView(LoginRequiredMixin, SettingsPermissionMixin, DetailView):
    """
    Detalle de rol
    """
    model = Role
    template_name = 'users/role_detail.html'
    context_object_name = 'role'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.get_object()
        
        # Usuarios con este rol
        if hasattr(self.request, 'company'):
            context['role_users'] = User.objects.filter(
                usercompany__roles=role,
                usercompany__company=self.request.company
            ).distinct()
        else:
            context['role_users'] = User.objects.filter(
                usercompany__roles=role
            ).distinct()
        
        return context


class RoleCreateView(LoginRequiredMixin, SettingsPermissionMixin, CreateView):
    """
    Crear rol
    """
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    
    def form_valid(self, form):
        messages.success(self.request, _('Rol creado exitosamente'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('users:role_detail', kwargs={'pk': self.object.pk})


class RoleUpdateView(LoginRequiredMixin, SettingsPermissionMixin, UpdateView):
    """
    Actualizar rol
    """
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    
    def form_valid(self, form):
        messages.success(self.request, _('Rol actualizado exitosamente'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('users:role_detail', kwargs={'pk': self.object.pk})


class RoleDeleteView(LoginRequiredMixin, SettingsPermissionMixin, DeleteView):
    """
    Eliminar rol
    """
    model = Role
    template_name = 'users/role_confirm_delete.html'
    success_url = reverse_lazy('users:role_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Rol eliminado exitosamente'))
        return super().delete(request, *args, **kwargs)


# ===================================
# VISTAS DE PERFIL
# ===================================

class UserProfileView(LoginRequiredMixin, DetailView):
    """
    Vista del perfil del usuario actual
    """
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'user_obj'
    
    def get_object(self):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        
        # Obtener o crear perfil
        profile, created = UserProfile.objects.get_or_create(user=user)
        context['profile'] = profile
        
        # Empresas del usuario
        context['user_companies'] = UserCompany.objects.filter(
            user=user
        ).select_related('company').prefetch_related('roles', 'branches')
        
        # Sesiones recientes
        context['recent_sessions'] = UserSession.objects.filter(
            user=user
        ).order_by('-login_at')[:5]
        
        return context


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    """
    Actualizar perfil del usuario
    """
    model = User
    fields = [
        'first_name', 'last_name', 'email', 'phone', 'mobile',
        'birth_date', 'address', 'language', 'timezone', 'avatar'
    ]
    template_name = 'users/profile_form.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, _('Perfil actualizado exitosamente'))
        return super().form_valid(form)


# ===================================
# VISTAS DE GESTIÓN DE ACCESOS
# ===================================

class UserCompanyManageView(LoginRequiredMixin, CompanyPermissionMixin, UpdateView):
    """
    Gestionar acceso de usuario a empresa
    """
    model = UserCompany
    form_class = UserCompanyForm
    template_name = 'users/user_company_form.html'
    
    def get_object(self):
        user_id = self.kwargs.get('user_id')
        user = get_object_or_404(User, id=user_id)
        user_company, created = UserCompany.objects.get_or_create(
            user=user,
            company=self.request.company
        )
        return user_company
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_obj'] = self.get_object().user
        return context
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            _('Accesos del usuario actualizados exitosamente')
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('users:user_detail', kwargs={'pk': self.get_object().user.pk})


# ===================================
# VISTAS DE SESIONES
# ===================================

class UserSessionListView(LoginRequiredMixin, SettingsPermissionMixin, ListView):
    """
    Lista de sesiones de usuarios
    """
    model = UserSession
    template_name = 'users/session_list.html'
    context_object_name = 'sessions'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = UserSession.objects.select_related('user', 'company', 'branch')
        
        if hasattr(self.request, 'company'):
            queryset = queryset.filter(company=self.request.company)
        
        # Filtros
        user_id = self.request.GET.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        active_only = self.request.GET.get('active_only')
        if active_only:
            queryset = queryset.filter(logout_at__isnull=True, is_expired=False)
        
        return queryset.order_by('-login_at')


# ===================================
# API VIEWS
# ===================================

class UserAPIView(generics.ListCreateAPIView):
    """
    API para usuarios
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = User.objects.select_related('profile')
        
        if not self.request.user.is_system_admin and hasattr(self.request, 'company'):
            queryset = queryset.filter(companies=self.request.company)
        
        return queryset


class RoleAPIView(generics.ListCreateAPIView):
    """
    API para roles
    """
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    queryset = Role.objects.prefetch_related('permissions')


class PermissionAPIView(generics.ListAPIView):
    """
    API para permisos
    """
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    queryset = Permission.objects.all()