"""
Vistas del módulo Core - CORREGIDAS
"""
import json
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, 
    UpdateView, DeleteView, View
)
from django.urls import reverse_lazy, reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Company, Branch, AuditLog
from .permissions import (
    CompanyPermissionMixin, BranchPermissionMixin, 
    SettingsPermissionMixin, company_required
)
from .serializers import CompanySerializer, BranchSerializer, AuditLogSerializer
from .utils import get_client_ip


class DashboardView(LoginRequiredMixin, CompanyPermissionMixin, TemplateView):
    """
    Vista principal del dashboard (versión mínima)
    """
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if hasattr(self.request, 'company'):
            company = self.request.company
            
            # Solo datos básicos y seguros
            context.update({
                'company': company,
                'total_branches': company.branches.filter(is_active=True).count(),
                'total_users': 0,  # Fijo por ahora
                'recent_activities': [],  # Vacío por ahora
                'system_alerts': self.get_system_alerts_safe(),  # CORREGIDO: Método seguro
                'current_branch': getattr(self.request, 'current_branch', None),
                'available_branches': company.branches.filter(is_active=True).order_by('name'),
            })
        else:
            # Si no hay empresa, datos por defecto
            context.update({
                'company': None,
                'total_branches': 0,
                'total_users': 0,
                'recent_activities': [],
                'system_alerts': [],
                'current_branch': None,
                'available_branches': [],
            })
        
        return context
    
    def get_total_users(self):
        """
        Obtiene el total de usuarios de la empresa
        """
        try:
            # Esto se implementará cuando tengamos el módulo de usuarios
            return 0
        except Exception:
            return 0
    
    def get_recent_activities(self):
        """
        Obtiene actividades recientes
        """
        if hasattr(self.request, 'company'):
            return AuditLog.objects.filter(
                company=self.request.company
            ).select_related('user').order_by('-created_at')[:10]
        return []
    
    def get_system_alerts_safe(self):
        """
        Obtiene alertas del sistema de forma segura (SIN URLs problemáticas)
        """
        alerts = []
        
        # Verificar configuración de empresa
        if hasattr(self.request, 'company'):
            company = self.request.company
            
            if not company.sri_certificate:
                alerts.append({
                    'type': 'warning',
                    'message': _('No se ha configurado el certificado digital SRI'),
                    'action_url': '#',  # CORREGIDO: URL segura temporal
                    'action_text': _('Configurar')
                })
            
            if company.branches.filter(is_active=True).count() == 0:
                alerts.append({
                    'type': 'danger',
                    'message': _('No hay sucursales activas configuradas'),
                    'action_url': '#',  # CORREGIDO: URL segura temporal
                    'action_text': _('Crear sucursal')
                })
        
        return alerts


class SelectCompanyView(LoginRequiredMixin, TemplateView):
    """
    Vista para seleccionar empresa
    """
    template_name = 'core/select_company.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Si ya tiene empresa seleccionada, redirigir al dashboard
        if hasattr(request, 'company'):
            return redirect('core:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener empresas disponibles para el usuario
        if self.request.user.is_superuser:
            available_companies = Company.objects.filter(is_active=True)
        else:
            # Por ahora permitir acceso a todas las empresas activas
            # Esto se modificará cuando implementemos el módulo de usuarios
            available_companies = Company.objects.filter(is_active=True)
        
        context['available_companies'] = available_companies
        return context

    def get(self, request, *args, **kwargs):
        # Verificar si hay empresas disponibles
        if request.user.is_superuser:
            available_companies = Company.objects.filter(is_active=True)
        else:
            available_companies = Company.objects.filter(is_active=True)
        
        if not available_companies.exists():
            messages.error(
                request,
                _('No hay empresas disponibles. Contacte al administrador.')
            )
            # CORREGIDO: Usar logout correcto en lugar de admin:logout
            return redirect('users:logout')
        
        # Si solo hay una empresa, seleccionarla automáticamente
        if available_companies.count() == 1:
            company = available_companies.first()
            request.session['company_id'] = str(company.id)
            messages.success(
                request,
                _('Empresa seleccionada automáticamente: %(company)s') % {
                    'company': company.business_name
                }
            )
            return redirect('core:dashboard')
        
        return super().get(request, *args, **kwargs)


class SwitchCompanyView(LoginRequiredMixin, View):
    """
    Vista para cambiar de empresa
    """
    
    def post(self, request, company_id):
        try:
            company = get_object_or_404(Company, id=company_id, is_active=True)
            
            # Verificar que el usuario tiene acceso a esta empresa
            if not request.user.is_superuser:
                # Aquí verificarías permisos específicos cuando implementes usuarios
                pass
            
            # Establecer empresa en sesión
            request.session['company_id'] = str(company.id)
            request.session.pop('current_branch_id', None)  # Limpiar sucursal
            
            messages.success(
                request, 
                _('Empresa cambiada a %(company)s') % {'company': company.business_name}
            )
            
            # Redirigir al dashboard o a la URL solicitada
            next_url = request.GET.get('next', 'core:dashboard')
            return redirect(next_url)
            
        except Exception as e:
            messages.error(
                request, 
                _('Error al cambiar de empresa: %(error)s') % {'error': str(e)}
            )
            return redirect('core:select_company')

    def get(self, request, company_id):
        """
        Permitir también GET para enlaces directos
        """
        return self.post(request, company_id)


class SwitchBranchView(LoginRequiredMixin, CompanyPermissionMixin, View):
    """
    Vista para cambiar de sucursal
    """
    
    def post(self, request, branch_id):
        try:
            branch = get_object_or_404(
                Branch, 
                id=branch_id, 
                company=request.company,
                is_active=True
            )
            
            # Establecer sucursal en sesión
            request.session['current_branch_id'] = str(branch.id)
            
            messages.success(
                request,
                _('Sucursal cambiada a %(branch)s') % {'branch': branch.name}
            )
            
            return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))
            
        except Exception as e:
            messages.error(request, _('Error al cambiar de sucursal: %(error)s') % {'error': str(e)})
            return redirect('core:dashboard')

    def get(self, request, branch_id):
        """
        Permitir también GET para enlaces directos
        """
        return self.post(request, branch_id)


# ===================================
# VISTAS DE EMPRESA
# ===================================

class CompanyListView(LoginRequiredMixin, SettingsPermissionMixin, ListView):
    """
    Lista de empresas
    """
    model = Company
    template_name = 'core/company_list.html'
    context_object_name = 'companies'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Company.objects.all().order_by('-created_at')
        
        # Filtros
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(business_name__icontains=search) |
                Q(trade_name__icontains=search) |
                Q(ruc__icontains=search)
            )
        
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset


class CompanyDetailView(LoginRequiredMixin, SettingsPermissionMixin, DetailView):
    """
    Detalle de empresa
    """
    model = Company
    template_name = 'core/company_detail.html'
    context_object_name = 'company'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.get_object()
        
        context.update({
            'branches': company.branches.all().order_by('name'),
            'recent_logs': AuditLog.objects.filter(
                company=company
            ).order_by('-created_at')[:10]
        })
        
        return context


class CompanyCreateView(LoginRequiredMixin, SettingsPermissionMixin, CreateView):
    """
    Crear empresa
    """
    model = Company
    template_name = 'core/company_form.html'
    fields = [
        'ruc', 'business_name', 'trade_name', 'email', 'phone', 'mobile',
        'address', 'city', 'province', 'postal_code', 'sri_environment',
        'logo'
    ]
    success_url = reverse_lazy('core:company_list')
    
    def form_valid(self, form):
        messages.success(self.request, _('Empresa creada exitosamente'))
        return super().form_valid(form)


class CompanyUpdateView(LoginRequiredMixin, SettingsPermissionMixin, UpdateView):
    """
    Actualizar empresa
    """
    model = Company
    template_name = 'core/company_form.html'
    fields = [
        'business_name', 'trade_name', 'email', 'phone', 'mobile',
        'address', 'city', 'province', 'postal_code', 'sri_environment',
        'logo', 'sri_certificate', 'is_active'
    ]
    
    def get_success_url(self):
        return reverse('core:company_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, _('Empresa actualizada exitosamente'))
        return super().form_valid(form)


class CompanyDeleteView(LoginRequiredMixin, SettingsPermissionMixin, DeleteView):
    """
    Eliminar empresa
    """
    model = Company
    template_name = 'core/company_confirm_delete.html'
    success_url = reverse_lazy('core:company_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Empresa eliminada exitosamente'))
        return super().delete(request, *args, **kwargs)


# ===================================
# VISTAS DE SUCURSAL
# ===================================

class BranchListView(LoginRequiredMixin, CompanyPermissionMixin, ListView):
    """
    Lista de sucursales
    """
    model = Branch
    template_name = 'core/branch_list.html'
    context_object_name = 'branches'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Branch.objects.filter(
            company=self.request.company
        ).order_by('-is_main', 'name')
        
        # Filtros
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(city__icontains=search)
            )
        
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset


class BranchDetailView(LoginRequiredMixin, CompanyPermissionMixin, DetailView):
    """
    Detalle de sucursal
    """
    model = Branch
    template_name = 'core/branch_detail.html'
    context_object_name = 'branch'
    
    def get_queryset(self):
        return Branch.objects.filter(company=self.request.company)


class BranchCreateView(LoginRequiredMixin, CompanyPermissionMixin, CreateView):
    """
    Crear sucursal
    """
    model = Branch
    template_name = 'core/branch_form.html'
    fields = [
        'code', 'name', 'email', 'phone', 'address', 'city', 'province',
        'sri_establishment_code', 'is_main'
    ]
    
    def form_valid(self, form):
        form.instance.company = self.request.company
        messages.success(self.request, _('Sucursal creada exitosamente'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('core:branch_detail', kwargs={'pk': self.object.pk})


class BranchUpdateView(LoginRequiredMixin, CompanyPermissionMixin, UpdateView):
    """
    Actualizar sucursal
    """
    model = Branch
    template_name = 'core/branch_form.html'
    fields = [
        'name', 'email', 'phone', 'address', 'city', 'province',
        'sri_establishment_code', 'is_main', 'is_active'
    ]
    
    def get_queryset(self):
        return Branch.objects.filter(company=self.request.company)
    
    def get_success_url(self):
        return reverse('core:branch_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, _('Sucursal actualizada exitosamente'))
        return super().form_valid(form)


class BranchDeleteView(LoginRequiredMixin, CompanyPermissionMixin, DeleteView):
    """
    Eliminar sucursal
    """
    model = Branch
    template_name = 'core/branch_confirm_delete.html'
    success_url = reverse_lazy('core:branch_list')
    
    def get_queryset(self):
        return Branch.objects.filter(company=self.request.company)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Sucursal eliminada exitosamente'))
        return super().delete(request, *args, **kwargs)


# ===================================
# VISTAS DE AUDITORÍA
# ===================================

class AuditLogListView(LoginRequiredMixin, SettingsPermissionMixin, ListView):
    """
    Lista de logs de auditoría
    """
    model = AuditLog
    template_name = 'core/audit_log_list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = AuditLog.objects.filter(
            company=self.request.company
        ).select_related('user', 'content_type').order_by('-created_at')
        
        # Filtros
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        user_id = self.request.GET.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset


class AuditLogDetailView(LoginRequiredMixin, SettingsPermissionMixin, DetailView):
    """
    Detalle de log de auditoría
    """
    model = AuditLog
    template_name = 'core/audit_log_detail.html'
    context_object_name = 'audit_log'
    
    def get_queryset(self):
        return AuditLog.objects.filter(company=self.request.company)


# ===================================
# VISTAS DE PERFIL
# ===================================

class UserProfileView(LoginRequiredMixin, TemplateView):
    """
    Perfil del usuario
    """
    template_name = 'core/user_profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'user_companies': Company.objects.filter(is_active=True) if self.request.user.is_superuser else Company.objects.filter(is_active=True),
            'current_company': getattr(self.request, 'company', None),
        })
        return context


class UserProfileUpdateView(LoginRequiredMixin, TemplateView):
    """
    Actualizar perfil del usuario
    """
    template_name = 'core/user_profile_form.html'


# ===================================
# VISTAS DE UTILIDAD - SIMPLIFICADAS
# ===================================

class HealthCheckView(View):
    """
    Vista de verificación de salud del sistema
    """
    
    def get(self, request):
        """
        Verifica el estado del sistema
        """
        try:
            # Verificar base de datos
            Company.objects.first()
            
            # Verificar configuraciones básicas
            status_data = {
                'status': 'ok',
                'timestamp': timezone.now().isoformat(),
                'version': getattr(settings, 'VERSION', '1.0.0'),
                'database': 'connected',
                'debug_mode': settings.DEBUG,
                'companies_count': Company.objects.filter(is_active=True).count(),
            }
            
            return JsonResponse(status_data)
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat(),
            }, status=500)


class SystemInfoView(LoginRequiredMixin, SettingsPermissionMixin, TemplateView):
    """
    Información del sistema
    """
    template_name = 'core/system_info.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'version': getattr(settings, 'VERSION', '1.0.0'),
            'debug_mode': settings.DEBUG,
            'database_engine': settings.DATABASES['default']['ENGINE'],
            'language_code': settings.LANGUAGE_CODE,
            'time_zone': settings.TIME_ZONE,
            'total_companies': Company.objects.count(),
            'active_companies': Company.objects.filter(is_active=True).count(),
            'total_branches': Branch.objects.count(),
            'active_branches': Branch.objects.filter(is_active=True).count(),
        })
        
        return context


# ===================================
# HANDLERS DE ERROR PERSONALIZADOS
# ===================================

def custom_400(request, exception=None):
    """
    Handler personalizado para error 400 (Bad Request)
    """
    return render(request, 'core/errors/400.html', {
        'exception': exception,
        'error_code': 400,
        'error_message': _('Solicitud incorrecta.')
    }, status=400)


def custom_403(request, exception=None):
    """
    Handler personalizado para error 403 (Forbidden)
    """
    return render(request, 'core/errors/403.html', {
        'exception': exception,
        'error_code': 403,
        'error_message': _('No tiene permisos para acceder a esta página.')
    }, status=403)


def custom_404(request, exception=None):
    """
    Handler personalizado para error 404 (Not Found)
    """
    return render(request, 'core/errors/404.html', {
        'exception': exception,
        'error_code': 404,
        'error_message': _('La página solicitada no fue encontrada.')
    }, status=404)


def custom_500(request):
    """
    Handler personalizado para error 500 (Internal Server Error)
    """
    return render(request, 'core/errors/500.html', {
        'error_code': 500,
        'error_message': _('Ha ocurrido un error interno del servidor.')
    }, status=500)


# ===================================
# API VIEWS - SIMPLIFICADAS
# ===================================

class CompanyAPIView(generics.ListCreateAPIView):
    """
    API para empresas
    """
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return Company.objects.all()
        return Company.objects.filter(is_active=True)


class BranchAPIView(generics.ListCreateAPIView):
    """
    API para sucursales
    """
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request, 'company'):
            return Branch.objects.filter(company=self.request.company)
        return Branch.objects.none()


class AuditLogAPIView(generics.ListAPIView):
    """
    API para logs de auditoría
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request, 'company'):
            return AuditLog.objects.filter(company=self.request.company)
        return AuditLog.objects.none()


# ===================================
# FUNCIONES BÁSICAS - SIMPLIFICADAS
# ===================================

@login_required
def health_check(request):
    """
    Función simple de health check
    """
    return JsonResponse({
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
        'message': 'Sistema funcionando correctamente'
    })
@login_required
def health_check(request):
    """
    Función simple de health check
    """
    from .utils import check_system_health
    
    try:
        health_data = check_system_health()
        health_data.update({
            'user': request.user.username,
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'method': request.method,
        })
        
        return JsonResponse(health_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)

# NOTA: Se eliminaron las funciones problemáticas quick_company_switch y quick_branch_switch
# Se implementarán cuando las URLs estén correctamente configuradas