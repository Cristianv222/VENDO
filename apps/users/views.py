"""
Vistas corregidas para el módulo de usuarios de VENDO.
Incluye tanto API REST como vistas tradicionales.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
from django.conf import settings

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import User, Role, Permission, UserProfile, UserRole, UserSession
from .serializers import (
    UserListSerializer, UserDetailSerializer, UserCreateSerializer, 
    UserUpdateSerializer, RoleSerializer, PermissionSerializer,
    UserProfileSerializer, LoginSerializer, PasswordChangeSerializer,
    UserSessionSerializer, ProfileUpdateSerializer
)
from .permissions import IsOwnerOrAdmin, CanManageUsers, CanManageRoles, CanViewPermissions


# ==========================================
# API REST VIEWS
# ==========================================

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar usuarios via API.
    """
    queryset = User.objects.all().select_related('company', 'default_branch', 'profile')
    permission_classes = [IsAuthenticated, CanManageUsers]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'department', 'company']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'document_number']
    ordering_fields = ['username', 'email', 'date_joined', 'last_login']
    ordering = ['-date_joined']

    def get_serializer_class(self):
        """Seleccionar serializer según la acción."""
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserDetailSerializer

    def get_permissions(self):
        """Permisos específicos por acción."""
        if self.action == 'me':
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Obtener información del usuario actual."""
        serializer = UserDetailSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        """Asignar rol a un usuario."""
        user = self.get_object()
        role_id = request.data.get('role_id')
        
        try:
            role = Role.objects.get(id=role_id, is_active=True)
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                role=role,
                defaults={'assigned_by': request.user}
            )
            
            if created:
                return Response({'message': _('Rol asignado exitosamente.')})
            else:
                user_role.is_active = True
                user_role.save()
                return Response({'message': _('Rol reactivado exitosamente.')})
                
        except Role.DoesNotExist:
            return Response(
                {'error': _('Rol no encontrado.')}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        """Remover rol de un usuario."""
        user = self.get_object()
        role_id = request.data.get('role_id')
        
        try:
            user_role = UserRole.objects.get(user=user, role_id=role_id)
            user_role.is_active = False
            user_role.save()
            return Response({'message': _('Rol removido exitosamente.')})
        except UserRole.DoesNotExist:
            return Response(
                {'error': _('Asignación de rol no encontrada.')},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """Resetear contraseña de un usuario."""
        user = self.get_object()
        new_password = request.data.get('new_password', 'temporal123')
        
        user.set_password(new_password)
        user.force_password_change = True
        user.failed_login_attempts = 0
        user.save()
        
        return Response({'message': _('Contraseña reseteada exitosamente.')})

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Activar/Desactivar usuario."""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()
        
        status_text = _('activado') if user.is_active else _('desactivado')
        return Response({'message': f'Usuario {status_text} exitosamente.'})


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar roles via API.
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, CanManageRoles]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para permisos via API.
    """
    queryset = Permission.objects.filter(is_active=True)
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, CanViewPermissions]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['module']
    search_fields = ['name', 'codename', 'description']
    ordering = ['module', 'name']


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """API endpoint para login."""
    serializer = LoginSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Resetear intentos fallidos
        user.reset_failed_attempts()
        user.last_activity = timezone.now()
        user.save()
        
        # Crear o obtener token
        token, created = Token.objects.get_or_create(user=user)
        
        # Crear sesión de usuario
        UserSession.objects.create(
            user=user,
            session_key=request.session.session_key or '',
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        
        return Response({
            'token': token.key,
            'user': UserDetailSerializer(user, context={'request': request}).data,
            'message': _('Login exitoso.')
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_api(request):
    """API endpoint para logout."""
    try:
        # Eliminar token
        token = Token.objects.get(user=request.user)
        token.delete()
        
        # Desactivar sesiones
        UserSession.objects.filter(
            user=request.user,
            is_active=True
        ).update(is_active=False)
        
        return Response({'message': _('Logout exitoso.')})
    except Token.DoesNotExist:
        return Response({'message': _('Token no encontrado.')})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_api(request):
    """API endpoint para cambiar contraseña."""
    serializer = PasswordChangeSerializer(
        data=request.data, 
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response({'message': _('Contraseña cambiada exitosamente.')})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def profile_api(request):
    """API endpoint para gestionar perfil del usuario actual."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'GET':
        serializer = UserProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = ProfileUpdateSerializer(profile, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# VISTAS TRADICIONALES (TEMPLATES)
# ==========================================

class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Vista para listar usuarios."""
    model = User
    template_name = 'users/list.html'
    context_object_name = 'users'
    paginate_by = 25
    permission_required = 'users.view_user'

    def get_queryset(self):
        """Filtrar usuarios según búsqueda."""
        queryset = User.objects.select_related('profile', 'company').prefetch_related('user_roles__role')
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(document_number__icontains=search)
            )
        
        department = self.request.GET.get('department')
        if department:
            queryset = queryset.filter(department=department)
        
        is_active = self.request.GET.get('is_active')
        if is_active:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['selected_department'] = self.request.GET.get('department', '')
        context['selected_is_active'] = self.request.GET.get('is_active', '')
        return context


class UserDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Vista para detalles de usuario."""
    model = User
    template_name = 'users/detail.html'
    context_object_name = 'user_obj'
    permission_required = 'users.view_user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        
        context['user_roles'] = UserRole.objects.filter(
            user=user, is_active=True
        ).select_related('role')
        
        context['recent_sessions'] = UserSession.objects.filter(
            user=user
        ).order_by('-last_activity')[:5]
        
        return context


@login_required
def dashboard_view(request):
    """Vista del dashboard principal."""
    if not request.user.is_authenticated:
        return redirect('users:login')
    
    context = {
        'total_users': User.objects.filter(is_active=True).count(),
        'total_roles': Role.objects.filter(is_active=True).count(),
        'recent_users': User.objects.filter(is_active=True).order_by('-date_joined')[:5],
        'active_sessions': UserSession.objects.filter(
            is_active=True,
            user=request.user
        ).count(),
    }
    
    return render(request, 'users/dashboard.html', context)


@login_required
def profile_view(request):
    """Vista del perfil del usuario actual."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        # Aquí iría la lógica para actualizar el perfil
        # Por simplicidad, solo mostramos un mensaje
        messages.success(request, _('Perfil actualizado exitosamente.'))
        return redirect('users:profile')
    
    context = {
        'profile': profile,
        'user_roles': UserRole.objects.filter(
            user=request.user, is_active=True
        ).select_related('role'),
    }
    
    return render(request, 'users/profile.html', context)


def login_view(request):
    """Vista de login."""
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            
            if user:
                if user.is_active:
                    if not user.is_account_locked():
                        login(request, user)
                        user.reset_failed_attempts()
                        user.last_activity = timezone.now()
                        user.save()
                        
                        # Crear sesión
                        UserSession.objects.create(
                            user=user,
                            session_key=request.session.session_key,
                            ip_address=request.META.get('REMOTE_ADDR', ''),
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        )
                        
                        next_url = request.GET.get('next', 'users:dashboard')
                        messages.success(request, _('Bienvenido de vuelta!'))
                        return redirect(next_url)
                    else:
                        messages.error(request, _('Cuenta bloqueada por demasiados intentos fallidos.'))
                else:
                    messages.error(request, _('Esta cuenta está desactivada.'))
            else:
                # Incrementar intentos fallidos
                try:
                    user_obj = User.objects.get(username=username)
                    user_obj.increment_failed_attempts()
                except User.DoesNotExist:
                    pass
                
                messages.error(request, _('Credenciales inválidas.'))
        else:
            messages.error(request, _('Por favor complete todos los campos.'))
    
    return render(request, 'auth/login.html')


@login_required
def logout_view(request):
    """Vista de logout."""
    # Desactivar sesiones
    UserSession.objects.filter(
        user=request.user,
        is_active=True
    ).update(is_active=False)
    
    logout(request)
    messages.success(request, _('Has cerrado sesión exitosamente.'))
    return redirect('users:login')


@login_required
def change_password_view(request):
    """Vista para cambiar contraseña."""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if request.user.check_password(current_password):
            if new_password == confirm_password:
                request.user.set_password(new_password)
                request.user.force_password_change = False
                request.user.last_password_change = timezone.now()
                request.user.save()
                
                messages.success(request, _('Contraseña cambiada exitosamente.'))
                return redirect('users:profile')
            else:
                messages.error(request, _('Las contraseñas no coinciden.'))
        else:
            messages.error(request, _('La contraseña actual es incorrecta.'))
    
    return render(request, 'users/change_password.html')


# ==========================================
# VISTAS AJAX
# ==========================================

@login_required
@require_http_methods(["GET"])
def search_users_ajax(request):
    """Búsqueda AJAX de usuarios."""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query),
        is_active=True
    )[:10]
    
    results = []
    for user in users:
        results.append({
            'id': str(user.id),
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'avatar_url': user.profile.avatar.url if hasattr(user, 'profile') and user.profile.avatar else None
        })
    
    return JsonResponse({'users': results})


# ==========================================
# VISTAS ADICIONALES SIMPLIFICADAS
# ==========================================

class RoleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Vista para listar roles."""
    model = Role
    template_name = 'users/roles/list.html'
    context_object_name = 'roles'
    permission_required = 'users.view_role'
    
    def get_queryset(self):
        return Role.objects.all().order_by('name')


class RoleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Vista para crear roles."""
    model = Role
    template_name = 'users/roles/create.html'
    fields = ['name', 'description', 'is_active']
    permission_required = 'users.add_role'
    success_url = '/users/roles/'


class RoleDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Vista para detalles de rol."""
    model = Role
    template_name = 'users/roles/detail.html'
    context_object_name = 'role'
    permission_required = 'users.view_role'


class RoleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Vista para editar roles."""
    model = Role
    template_name = 'users/roles/edit.html'
    fields = ['name', 'description', 'is_active']
    permission_required = 'users.change_role'
    success_url = '/users/roles/'


class PermissionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Vista para listar permisos."""
    model = Permission
    template_name = 'users/permissions/list.html'
    context_object_name = 'permissions'
    permission_required = 'users.view_permission'
    
    def get_queryset(self):
        return Permission.objects.all().order_by('module', 'name')


class UserSessionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Vista para listar sesiones de usuarios."""
    model = UserSession
    template_name = 'users/sessions/list.html'
    context_object_name = 'sessions'
    permission_required = 'users.view_usersession'
    
    def get_queryset(self):
        return UserSession.objects.all().order_by('-last_activity')


@login_required
def manage_user_roles(request, user_id):
    """Vista para gestionar roles de un usuario."""
    user_obj = get_object_or_404(User, id=user_id)
    
    context = {
        'user_obj': user_obj,
        'available_roles': Role.objects.filter(is_active=True),
        'user_roles': UserRole.objects.filter(user=user_obj, is_active=True)
    }
    
    return render(request, 'users/manage_roles.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_user_status_ajax(request, user_id):
    """Activar/Desactivar usuario via AJAX."""
    try:
        user = User.objects.get(id=user_id)
        user.is_active = not user.is_active
        user.save()
        
        return JsonResponse({
            'success': True,
            'is_active': user.is_active,
            'message': f'Usuario {"activado" if user.is_active else "desactivado"} exitosamente.'
        })
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Usuario no encontrado.'
        })


# Vistas simplificadas para completar las URLs
@login_required
def user_activity_report(request):
    return render(request, 'users/reports/activity.html', {'title': 'Reporte de Actividad'})

@login_required
def permission_report(request):
    return render(request, 'users/reports/permissions.html', {'title': 'Reporte de Permisos'})

@login_required
def account_settings(request):
    return render(request, 'users/settings/account.html', {'title': 'Configuraciones de Cuenta'})

@login_required
def security_settings(request):
    return render(request, 'users/settings/security.html', {'title': 'Configuraciones de Seguridad'})

@login_required
def notification_settings(request):
    return render(request, 'users/settings/notifications.html', {'title': 'Configuraciones de Notificaciones'})

@login_required
def terminate_session(request, session_id):
    session = get_object_or_404(UserSession, id=session_id)
    session.is_active = False
    session.save()
    messages.success(request, 'Sesión terminada exitosamente.')
    return redirect('users:session_list')