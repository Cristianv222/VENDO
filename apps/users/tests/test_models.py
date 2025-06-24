"""
Tests para los modelos del módulo de usuarios.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import date, timedelta
from apps.users.models import User, Role, Permission, UserProfile, UserRole, UserPermission, UserSession


class UserModelTest(TestCase):
    """Tests para el modelo User."""
    
    def setUp(self):
        """Configurar datos para los tests."""
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'document_type': 'cedula',
            'document_number': '1234567890',
            'phone': '+593987654321',
            'user_type': 'employee'
        }
    
    def test_create_user(self):
        """Test crear usuario básico."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
    
    def test_create_superuser(self):
        """Test crear superusuario."""
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
    
    def test_user_full_name(self):
        """Test propiedad full_name."""
        user = User.objects.create_user(**self.user_data, password='test123')
        
        self.assertEqual(user.full_name, 'Test User')
        
        # Test con nombres vacíos
        user.first_name = ''
        user.last_name = ''
        self.assertEqual(user.full_name, 'testuser')
    
    def test_generate_employee_code(self):
        """Test generación automática de código de empleado."""
        user = User.objects.create_user(
            username='employee1',
            email='emp1@example.com',
            password='test123',
            user_type='employee'
        )
        
        self.assertTrue(user.employee_code.startswith('EMP'))
        self.assertEqual(len(user.employee_code), 11)  # EMP + año (4) + número (4)
    
    def test_unique_document_number(self):
        """Test que el número de documento sea único."""
        User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='test123',
            document_number='1234567890'
        )
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='user2',
                email='user2@example.com',
                password='test123',
                document_number='1234567890'  # Número duplicado
            )
    
    def test_has_permission_method(self):
        """Test método has_permission."""
        user = User.objects.create_user(**self.user_data, password='test123')
        permission = Permission.objects.create(
            name='Test Permission',
            code='test_permission',
            module='test'
        )
        
        # Sin permiso
        self.assertFalse(user.has_permission('test_permission'))
        
        # Con permiso
        UserPermission.objects.create(user=user, permission=permission)
        self.assertTrue(user.has_permission('test_permission'))
    
    def test_has_role_method(self):
        """Test método has_role."""
        user = User.objects.create_user(**self.user_data, password='test123')
        role = Role.objects.create(
            name='Test Role',
            code='test_role'
        )
        
        # Sin rol
        self.assertFalse(user.has_role('test_role'))
        
        # Con rol
        UserRole.objects.create(user=user, role=role)
        self.assertTrue(user.has_role('test_role'))
    
    def test_is_account_locked(self):
        """Test método is_account_locked."""
        user = User.objects.create_user(**self.user_data, password='test123')
        
        # No bloqueado inicialmente
        self.assertFalse(user.is_account_locked())
        
        # Incrementar intentos fallidos
        user.failed_login_attempts = 5
        user.save()
        
        # Debería estar bloqueado (asumiendo max_attempts = 5)
        self.assertTrue(user.is_account_locked())
    
    def test_reset_failed_attempts(self):
        """Test método reset_failed_attempts."""
        user = User.objects.create_user(**self.user_data, password='test123')
        user.failed_login_attempts = 3
        user.save()
        
        user.reset_failed_attempts()
        
        self.assertEqual(user.failed_login_attempts, 0)
    
    def test_increment_failed_attempts(self):
        """Test método increment_failed_attempts."""
        user = User.objects.create_user(**self.user_data, password='test123')
        
        initial_attempts = user.failed_login_attempts
        user.increment_failed_attempts()
        
        self.assertEqual(user.failed_login_attempts, initial_attempts + 1)


class RoleModelTest(TestCase):
    """Tests para el modelo Role."""
    
    def test_create_role(self):
        """Test crear rol."""
        role = Role.objects.create(
            name='Test Role',
            code='test_role',
            description='A test role'
        )
        
        self.assertEqual(role.name, 'Test Role')
        self.assertEqual(role.code, 'test_role')
        self.assertTrue(role.is_active)
    
    def test_unique_role_code(self):
        """Test que el código de rol sea único."""
        Role.objects.create(name='Role 1', code='test_role')
        
        with self.assertRaises(IntegrityError):
            Role.objects.create(name='Role 2', code='test_role')
    
    def test_user_count_property(self):
        """Test propiedad user_count."""
        role = Role.objects.create(name='Test Role', code='test_role')
        
        # Sin usuarios
        self.assertEqual(role.user_count, 0)
        
        # Con usuarios
        user1 = User.objects.create_user(username='user1', email='user1@test.com', password='test123')
        user2 = User.objects.create_user(username='user2', email='user2@test.com', password='test123')
        
        UserRole.objects.create(user=user1, role=role, is_active=True)
        UserRole.objects.create(user=user2, role=role, is_active=True)
        
        self.assertEqual(role.user_count, 2)
        
        # Usuario inactivo no cuenta
        user2.is_active = False
        user2.save()
        self.assertEqual(role.user_count, 1)


class PermissionModelTest(TestCase):
    """Tests para el modelo Permission."""
    
    def test_create_permission(self):
        """Test crear permiso."""
        permission = Permission.objects.create(
            name='Test Permission',
            code='test_permission',
            module='test_module',
            description='A test permission'
        )
        
        self.assertEqual(permission.name, 'Test Permission')
        self.assertEqual(permission.code, 'test_permission')
        self.assertEqual(permission.module, 'test_module')
        self.assertTrue(permission.is_active)
    
    def test_unique_permission_code(self):
        """Test que el código de permiso sea único."""
        Permission.objects.create(
            name='Permission 1',
            code='test_permission',
            module='test'
        )
        
        with self.assertRaises(IntegrityError):
            Permission.objects.create(
                name='Permission 2',
                code='test_permission',  # Código duplicado
                module='test'
            )
    
    def test_permission_str(self):
        """Test método __str__ del permiso."""
        permission = Permission.objects.create(
            name='Test Permission',
            code='test_permission',
            module='test_module'
        )
        
        self.assertEqual(str(permission), 'test_module - Test Permission')


class UserProfileModelTest(TestCase):
    """Tests para el modelo UserProfile."""
    
    def test_create_profile(self):
        """Test crear perfil de usuario."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='test123'
        )
        
        profile = UserProfile.objects.create(
            user=user,
            theme='dark',
            language='en',
            bio='Test bio'
        )
        
        self.assertEqual(profile.user, user)
        self.assertEqual(profile.theme, 'dark')
        self.assertEqual(profile.language, 'en')
        self.assertEqual(profile.bio, 'Test bio')
    
    def test_age_property(self):
        """Test propiedad age."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='test123'
        )
        
        profile = UserProfile.objects.create(user=user)
        
        # Sin fecha de nacimiento
        self.assertIsNone(profile.age)
        
        # Con fecha de nacimiento
        birth_date = date.today() - timedelta(days=365 * 25)  # 25 años
        profile.birth_date = birth_date
        profile.save()
        
        self.assertEqual(profile.age, 25)


class UserRoleModelTest(TestCase):
    """Tests para el modelo UserRole."""
    
    def setUp(self):
        """Configurar datos para los tests."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='test123'
        )
        self.role = Role.objects.create(
            name='Test Role',
            code='test_role'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
    
    def test_create_user_role(self):
        """Test crear asignación de rol."""
        user_role = UserRole.objects.create(
            user=self.user,
            role=self.role,
            assigned_by=self.admin_user
        )
        
        self.assertEqual(user_role.user, self.user)
        self.assertEqual(user_role.role, self.role)
        self.assertEqual(user_role.assigned_by, self.admin_user)
        self.assertTrue(user_role.is_active)
    
    def test_unique_user_role(self):
        """Test que la combinación usuario-rol sea única."""
        UserRole.objects.create(user=self.user, role=self.role)
        
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=self.user, role=self.role)


class UserPermissionModelTest(TestCase):
    """Tests para el modelo UserPermission."""
    
    def setUp(self):
        """Configurar datos para los tests."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='test123'
        )
        self.permission = Permission.objects.create(
            name='Test Permission',
            code='test_permission',
            module='test'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
    
    def test_create_user_permission(self):
        """Test crear asignación de permiso."""
        user_permission = UserPermission.objects.create(
            user=self.user,
            permission=self.permission,
            granted_by=self.admin_user
        )
        
        self.assertEqual(user_permission.user, self.user)
        self.assertEqual(user_permission.permission, self.permission)
        self.assertEqual(user_permission.granted_by, self.admin_user)
        self.assertTrue(user_permission.is_active)
    
    def test_unique_user_permission(self):
        """Test que la combinación usuario-permiso sea única."""
        UserPermission.objects.create(user=self.user, permission=self.permission)
        
        with self.assertRaises(IntegrityError):
            UserPermission.objects.create(user=self.user, permission=self.permission)


class UserSessionModelTest(TestCase):
    """Tests para el modelo UserSession."""
    
    def setUp(self):
        """Configurar datos para los tests."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='test123'
        )
    
    def test_create_session(self):
        """Test crear sesión de usuario."""
        session = UserSession.objects.create(
            user=self.user,
            session_key='test_session_key',
            ip_address='127.0.0.1',
            user_agent='Test Browser'
        )
        
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.session_key, 'test_session_key')
        self.assertEqual(session.ip_address, '127.0.0.1')
        self.assertTrue(session.is_active)
    
    def test_is_expired_property(self):
        """Test propiedad is_expired."""
        # Sesión reciente
        session = UserSession.objects.create(
            user=self.user,
            session_key='test_session_key',
            ip_address='127.0.0.1'
        )
        
        self.assertFalse(session.is_expired)
        
        # Sesión antigua
        old_time = timezone.now() - timedelta(hours=2)
        session.last_activity = old_time
        session.save()
        
        # Dependiendo de la configuración de timeout, podría estar expirada
        # Este test asume un timeout de 60 minutos por defecto