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
# apps/users/views.py - AGREGAR ESTAS VISTAS AL ARCHIVO EXISTENTE

"""
Vistas adicionales para sala de espera y aprobación de usuarios
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.urls import reverse
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone

from .models import User
from .services import UserApprovalService


class WaitingRoomView(TemplateView):
    """
    Vista para usuarios que están en espera de aprobación
    """
    template_name = 'users/waiting_room.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Solo usuarios autenticados pueden acceder
        if not request.user.is_authenticated:
            return redirect('users:login')
        
        # Si el usuario ya está aprobado, redirigir al dashboard
        if request.user.is_approved():
            return redirect('core:dashboard')
        
        # Si el usuario está rechazado, mostrar página de rechazo
        if request.user.is_rejected():
            return redirect('users:account_rejected')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        context.update({
            'user': user,
            'approval_status': user.approval_status,
            'created_at': user.created_at,
            'waiting_time': timezone.now() - user.created_at,
            'contact_email': settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'admin@vendo.com',
        })
        
        return context


class AccountRejectedView(TemplateView):
    """
    Vista para usuarios cuya cuenta ha sido rechazada
    """
    template_name = 'users/account_rejected.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        
        # Solo usuarios rechazados pueden ver esta página
        if not request.user.is_rejected():
            if request.user.is_approved():
                return redirect('core:dashboard')
            else:
                return redirect('users:waiting_room')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        context.update({
            'user': user,
            'rejection_reason': user.rejection_reason,
            'rejected_at': user.approved_at,
            'rejected_by': user.approved_by,
            'contact_email': settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'admin@vendo.com',
        })
        
        return context


@method_decorator([login_required, staff_member_required], name='dispatch')
class PendingUsersView(TemplateView):
    """
    Vista para administradores para gestionar usuarios pendientes
    """
    template_name = 'users/pending_users.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener usuarios pendientes
        pending_users = UserApprovalService.get_pending_users()
        
        # Paginación
        paginator = Paginator(pending_users, 25)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estadísticas
        stats = {
            'pending_count': pending_users.count(),
            'approved_today': User.objects.filter(
                approval_status='approved',
                approved_at__date=timezone.now().date()
            ).count(),
            'rejected_today': User.objects.filter(
                approval_status='rejected',
                approved_at__date=timezone.now().date()
            ).count(),
        }
        
        context.update({
            'pending_users': page_obj,
            'stats': stats,
            'is_paginated': page_obj.has_other_pages(),
            'page_obj': page_obj,
        })
        
        return context


# ==========================================
# VISTAS FUNCIONALES PARA AJAX
# ==========================================

@login_required
@staff_member_required
@require_POST
@csrf_protect
def approve_user_ajax(request, user_id):
    """
    Vista AJAX para aprobar un usuario
    """
    try:
        user_to_approve = get_object_or_404(User, pk=user_id)
        
        # Verificar que el usuario puede ser aprobado
        if not user_to_approve.is_pending_approval():
            return JsonResponse({
                'success': False,
                'message': 'El usuario no está pendiente de aprobación'
            }, status=400)
        
        # Aprobar usuario
        success, message = UserApprovalService.approve_user(
            user_to_approve=user_to_approve,
            approved_by_user=request.user
        )
        
        if success:
            return JsonResponse({
                'success': True,
                'message': f'Usuario {user_to_approve.get_full_name()} aprobado exitosamente',
                'user_id': str(user_to_approve.pk),
                'new_status': 'approved'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }, status=500)


@login_required
@staff_member_required
@require_POST
@csrf_protect
def reject_user_ajax(request, user_id):
    """
    Vista AJAX para rechazar un usuario
    """
    try:
        user_to_reject = get_object_or_404(User, pk=user_id)
        
        # Verificar que el usuario puede ser rechazado
        if not user_to_reject.is_pending_approval():
            return JsonResponse({
                'success': False,
                'message': 'El usuario no está pendiente de aprobación'
            }, status=400)
        
        # Obtener razón del rechazo
        reason = request.POST.get('reason', '').strip()
        if not reason:
            return JsonResponse({
                'success': False,
                'message': 'Debe proporcionar una razón para el rechazo'
            }, status=400)
        
        # Rechazar usuario
        success, message = UserApprovalService.reject_user(
            user_to_reject=user_to_reject,
            rejected_by_user=request.user,
            reason=reason
        )
        
        if success:
            return JsonResponse({
                'success': True,
                'message': f'Usuario {user_to_reject.get_full_name()} rechazado exitosamente',
                'user_id': str(user_to_reject.pk),
                'new_status': 'rejected'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }, status=500)


@login_required
@staff_member_required
def pending_users_count_ajax(request):
    """
    Vista AJAX para obtener el conteo de usuarios pendientes
    """
    try:
        count = UserApprovalService.get_pending_users_count()
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# ==========================================
# DECORADORES AUXILIARES
# ==========================================

def is_system_admin(user):
    """
    Verifica si el usuario es administrador del sistema
    """
    return user.is_authenticated and (user.is_superuser or user.is_system_admin)


def approved_user_required(view_func):
    """
    Decorador que requiere que el usuario esté aprobado
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        
        if request.user.is_pending_approval():
            return redirect('users:waiting_room')
        
        if request.user.is_rejected():
            return redirect('users:account_rejected')
        
        if not request.user.is_approved():
            return HttpResponseForbidden("Acceso denegado")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# ==========================================
# MODIFICACIÓN DE LA VISTA DE LOGIN EXISTENTE
# ==========================================

# MODIFICAR CustomLoginView existente - Agregar esta lógica al método form_valid:

def custom_login_form_valid_modification(self, form):
    """
    Modificación para la vista de login existente - agregar al método form_valid
    """
    # ... código existente hasta user.save() ...
    
    # NUEVA LÓGICA: Verificar estado de aprobación
    if user.is_pending_approval():
        # Usuario pendiente - llevarlo a sala de espera
        login(self.request, user)  # Permitir login para que vea la sala de espera
        messages.info(
            self.request, 
            _('Tu cuenta está pendiente de aprobación. Te notificaremos cuando sea revisada.')
        )
        return redirect('users:waiting_room')
    
    elif user.is_rejected():
        # Usuario rechazado - llevarlo a página de rechazo
        login(self.request, user)  # Permitir login para que vea el rechazo
        messages.warning(
            self.request, 
            _('Tu cuenta ha sido rechazada. Contacta al administrador para más información.')
        )
        return redirect('users:account_rejected')
    
    elif not user.is_approved():
        # Estado desconocido
        messages.error(self.request, _('Tu cuenta tiene un estado desconocido. Contacta al administrador.'))
        return self.form_invalid(form)
    
    # ... resto del código existente ...

# ===================================
# VISTAS DE AUTENTICACIÓN
# ===================================

# apps/users/views.py - REEMPLAZAR LA CLASE CustomLoginView EXISTENTE

class CustomLoginView(FormView):
    """
    Vista personalizada de login con gestión de sala de espera
    """
    template_name = 'users/login.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('core:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        # Si ya está autenticado, verificar su estado de aprobación
        if request.user.is_authenticated:
            if request.user.is_pending_approval():
                return redirect('users:waiting_room')
            elif request.user.is_rejected():
                return redirect('users:account_rejected')
            elif request.user.is_approved():
                return redirect(self.get_success_url())
            else:
                # Estado desconocido, cerrar sesión y continuar con login
                logout(request)
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        remember_me = form.cleaned_data.get('remember_me', False)
        
        user = authenticate(self.request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                # Verificar estado de aprobación ANTES de hacer login completo
                if user.is_pending_approval():
                    # Hacer login temporal para que pueda ver la sala de espera
                    login(self.request, user)
                    
                    # Configurar sesión temporal (más corta)
                    self.request.session.set_expiry(3600)  # 1 hora
                    
                    # Registrar la sesión
                    self.register_user_session(user)
                    
                    messages.info(
                        self.request, 
                        _('Tu cuenta está pendiente de aprobación. Te notificaremos cuando sea revisada.')
                    )
                    return redirect('users:waiting_room')
                
                elif user.is_rejected():
                    # Hacer login temporal para que pueda ver la página de rechazo
                    login(self.request, user)
                    
                    # Configurar sesión temporal (más corta)
                    self.request.session.set_expiry(3600)  # 1 hora
                    
                    # Registrar la sesión
                    self.register_user_session(user)
                    
                    messages.warning(
                        self.request, 
                        _('Tu cuenta ha sido rechazada. Contacta al administrador para más información.')
                    )
                    return redirect('users:account_rejected')
                
                elif not user.is_approved():
                    # Estado desconocido - no permitir login
                    messages.error(
                        self.request, 
                        _('Tu cuenta tiene un estado desconocido. Contacta al administrador.')
                    )
                    return self.form_invalid(form)
                
                # Usuario aprobado - login normal
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
    
    def get_context_data(self, **kwargs):
        """Agregar contexto adicional"""
        context = super().get_context_data(**kwargs)
        
        # Agregar información para debugging en desarrollo
        if settings.DEBUG:
            context.update({
                'debug_info': {
                    'pending_users': User.objects.filter(approval_status='pending').count(),
                    'total_users': User.objects.count(),
                }
            })
        
        return context


# TAMBIÉN AGREGAR ESTA NUEVA VISTA PARA REGISTRO CON APROBACIÓN

class CustomUserCreateView(CreateView):
    """
    Vista de registro personalizada con aprobación automática
    """
    model = User
    form_class = CustomUserCreationForm
    template_name = 'users/register.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Si ya está autenticado, redirigir según su estado
        if request.user.is_authenticated:
            if request.user.is_pending_approval():
                return redirect('users:waiting_room')
            elif request.user.is_rejected():
                return redirect('users:account_rejected')
            elif request.user.is_approved():
                return redirect('core:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        # Crear usuario
        response = super().form_valid(form)
        
        # El usuario se crea en estado 'pending' por defecto (ver modelo)
        user = self.object
        
        # Crear perfil automáticamente
        UserProfile.objects.get_or_create(user=user)
        
        # Mensaje informativo sobre el estado
        if user.is_pending_approval():
            messages.info(
                self.request,
                _('Tu cuenta ha sido creada exitosamente. Está pendiente de aprobación y recibirás una notificación cuando sea revisada.')
            )
            
            # Auto-login temporal para que vea la sala de espera
            login(self.request, user)
            return redirect('users:waiting_room')
        
        elif user.is_approved():
            # Usuario auto-aprobado (superuser, etc.)
            messages.success(
                self.request,
                _('Tu cuenta ha sido creada y aprobada exitosamente. ¡Bienvenido!')
            )
            
            # Auto-login
            login(self.request, user)
            return redirect('core:dashboard')
        
        else:
            # Estado inesperado
            messages.warning(
                self.request,
                _('Tu cuenta ha sido creada pero tiene un estado inesperado. Contacta al administrador.')
            )
            return redirect('users:login')
    
    def get_success_url(self):
        return reverse('users:waiting_room')


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