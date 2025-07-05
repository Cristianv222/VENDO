import os

# Comentarios por nombre de archivo o carpeta
comentarios = {
    ".env": "Variables de entorno (credenciales seguras)",
    "requirements.txt": "Dependencias del proyecto",
    "manage.py": "Script de gestión Django",
    "README.md": "Documentación general",
    "INSTALL.md": "Instrucciones de instalación",
    "API.md": "Documentación de API",
    "settings.py": "Configuración de Django",
    "urls.py": "URLs principales",
    "wsgi.py": "Servidor WSGI",
    "asgi.py": "Servidor ASGI",
    "celery.py": "Configuración Celery",
    "db_router.py": "Router de esquemas PostgreSQL",
    "models.py": "Modelos de datos",
    "views.py": "Vistas Django",
    "serializers.py": "Serializadores DRF",
    "permissions.py": "Permisos personalizados",
    "tasks.py": "Tareas asíncronas",
    "utils.py": "Funciones utilitarias",
    "signals.py": "Señales Django",
    "tests": "Pruebas automáticas",
    "templates": "Plantillas HTML",
    "static": "Archivos estáticos (CSS, JS, imágenes)",
    "apps": "Aplicaciones Django modulares",
    "locale": "Archivos de traducción",
    "media": "Archivos subidos por usuarios",
    "logs": "Registros del sistema",
    "fixtures": "Datos iniciales para carga",
    "docs": "Documentación técnica",
    "services": "Servicios compartidos del sistema"
}

def estructura(ruta, prefijo='', salida=None):
    for elemento in sorted(os.listdir(ruta)):
        if elemento in ['__pycache__', 'env', 'venv', '.git', '.idea']:
            continue
        ruta_completa = os.path.join(ruta, elemento)
        linea = f"{prefijo}├── {elemento}"
        comentario = comentarios.get(elemento)
        if comentario:
            linea += f"  # {comentario}"
        salida.write(linea + '\n')
        if os.path.isdir(ruta_completa):
            estructura(ruta_completa, prefijo + "│   ", salida)

# Guardar en archivo de texto
with open("estructura_documentada.txt", "w", encoding="utf-8") as salida:
    estructura(".", "", salida)
