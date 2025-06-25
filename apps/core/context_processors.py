"""
Procesadores de contexto para el sistema VENDO
Añaden variables globales a todas las plantillas
"""
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

from .models import Company, Branch


def company_context(request):
    """
    Añade información de la empresa al contexto
    """
    context = {
        'current_company': None,
        'available_companies': [],
        'company_logo_url': None,
        'company_name': '',
        'company_ruc': '',
    }
    
    # Solo procesar si el usuario está autenticado
    if request.user.is_authenticated:
        # Empresa actual
        if hasattr(request, 'company') and request.company:
            company = request.company
            context.update({
                'current_company': company,
                'company_name': company.business_name,
                'company_ruc': company.ruc,
                'company_logo_url': company.logo.url if company.logo else None,
            })
        
        # Empresas disponibles para el usuario
        try:
            if request.user.is_superuser:
                # Superusuario ve todas las empresas activas
                available_companies = Company.objects.filter(is_active=True)
            else:
                # Usuario normal ve solo su empresa
                if hasattr(request.user, 'profile') and request.user.profile.company:
                    available_companies = [request.user.profile.company]
                else:
                    available_companies = []
            
            context['available_companies'] = available_companies
        except Exception:
            context['available_companies'] = []
    
    return context


def branch_context(request):
    """
    Añade información de sucursales al contexto
    """
    context = {
        'current_branch': None,
        'available_branches': [],
        'user_branches': [],
    }
    
    if request.user.is_authenticated and hasattr(request, 'company'):
        try:
            # Todas las sucursales de la empresa
            available_branches = Branch.objects.filter(
                company=request.company,
                is_active=True
            )
            context['available_branches'] = available_branches
            
            # Sucursales del usuario
            if hasattr(request.user, 'profile'):
                user_branches = request.user.profile.branches.filter(is_active=True)
                context['user_branches'] = user_branches
                
                # Si no tiene sucursales asignadas, puede ver todas
                if not user_branches.exists():
                    context['user_branches'] = available_branches
            
            # Sucursal actual (de la sesión o la principal)
            branch_id = request.session.get('current_branch_id')
            if branch_id:
                try:
                    current_branch = Branch.objects.get(
                        id=branch_id,
                        company=request.company,
                        is_active=True
                    )
                    context['current_branch'] = current_branch
                except Branch.DoesNotExist:
                    # Limpiar sesión si la sucursal no existe
                    request.session.pop('current_branch_id', None)
            
            # Si no hay sucursal actual, usar la principal
            if not context['current_branch']:
                main_branch = available_branches.filter(is_main=True).first()
                if main_branch:
                    context['current_branch'] = main_branch
                    request.session['current_branch_id'] = str(main_branch.id)
        
        except Exception:
            pass
    
    return context


def user_context(request):
    """
    Añade información del usuario al contexto
    """
    context = {
        'user_full_name': '',
        'user_roles': [],
        'user_permissions': [],
        'user_avatar_url': None,
        'is_admin': False,
        'is_supervisor': False,
    }
    
    if request.user.is_authenticated and not isinstance(request.user, AnonymousUser):
        user = request.user
        
        # Nombre completo
        if user.first_name or user.last_name:
            context['user_full_name'] = f"{user.first_name} {user.last_name}".strip()
        else:
            context['user_full_name'] = user.username
        
        # Verificar si es admin
        context['is_admin'] = user.is_superuser or user.is_staff
        
        # Información del perfil si existe
        if hasattr(user, 'profile'):
            profile = user.profile
            
            # Avatar
            if hasattr(profile, 'avatar') and profile.avatar:
                context['user_avatar_url'] = profile.avatar.url
            
            # Roles
            if hasattr(profile, 'roles'):
                user_roles = profile.roles.filter(is_active=True)
                context['user_roles'] = [role.name for role in user_roles]
                context['is_supervisor'] = 'supervisor' in context['user_roles']
            
            # Permisos
            if hasattr(profile, 'get_all_permissions'):
                context['user_permissions'] = profile.get_all_permissions()
    
    return context


def system_context(request):
    """
    Añade información del sistema al contexto
    """
    context = {
        'system_name': 'VENDO',
        'system_version': getattr(settings, 'VERSION', '1.0.0'),
        'debug_mode': settings.DEBUG,
        'current_year': timezone.now().year,
        'current_date': timezone.now().date(),
        'current_datetime': timezone.now(),
        'sri_environment': 'test',  # Por defecto
    }
    
    # Ambiente SRI de la empresa actual
    if (request.user.is_authenticated and 
        hasattr(request, 'company') and 
        request.company):
        context['sri_environment'] = request.company.sri_environment
    
    return context


def navigation_context(request):
    """
    Añade información de navegación al contexto
    """
    context = {
        'current_path': request.path,
        'current_app': '',
        'breadcrumbs': [],
        'active_module': '',
    }
    
    # Determinar aplicación actual
    path_parts = request.path.strip('/').split('/')
    if path_parts and path_parts[0]:
        context['current_app'] = path_parts[0]
        context['active_module'] = path_parts[0]
    
    # Generar breadcrumbs básicos
    breadcrumbs = []
    path_so_far = ''
    
    for part in path_parts:
        if part:
            path_so_far += f'/{part}'
            # Convertir nombres de URL a títulos legibles
            title = part.replace('_', ' ').replace('-', ' ').title()
            breadcrumbs.append({
                'title': title,
                'url': path_so_far,
                'is_active': path_so_far == request.path
            })
    
    context['breadcrumbs'] = breadcrumbs
    
    return context


def menu_context(request):
    """
    Añade información del menú al contexto
    """
    context = {
        'menu_items': [],
        'user_modules': [],
    }
    
    if request.user.is_authenticated:
        # Módulos disponibles para el usuario
        user_modules = []
        
        if request.user.is_superuser:
            # Superusuario tiene acceso a todos los módulos
            user_modules = [
                'core', 'pos', 'inventory', 'invoicing', 
                'purchases', 'accounting', 'reports', 'settings'
            ]
        elif hasattr(request.user, 'profile'):
            # Obtener módulos del perfil del usuario
            try:
                user_modules = request.user.profile.get_accessible_modules()
            except Exception:
                user_modules = []
        
        context['user_modules'] = user_modules
        
        # Generar elementos del menú basados en módulos disponibles
        menu_items = []
        
        module_definitions = {
            'core': {
                'title': 'Dashboard',
                'icon': 'fas fa-tachometer-alt',
                'url': 'core:dashboard',
                'order': 1
            },
        }
        
        for module in user_modules:
            if module in module_definitions:
                menu_items.append(module_definitions[module])
        
        # Ordenar por orden definido
        menu_items.sort(key=lambda x: x['order'])
        context['menu_items'] = menu_items
    
    return context


def notifications_context(request):
    """
    Añade notificaciones al contexto
    """
    context = {
        'unread_notifications': 0,
        'recent_notifications': [],
        'has_notifications': False,
    }
    
    if request.user.is_authenticated:
        try:
            # Aquí se implementarían las notificaciones reales
            # Por ahora, solo estructura básica
            context.update({
                'unread_notifications': 0,
                'recent_notifications': [],
                'has_notifications': False,
            })
        except Exception:
            pass
    
    return context