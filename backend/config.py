import pyodbc
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import timedelta

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/media/emapp/dano_flota"))


# Carpeta principal

FILES_DIR = MEDIA_DIR / "Files"

# Carpetas de cada módulo

UPLOAD_FOLDERS = {

    "Operaciones": FILES_DIR / "Files_ppal",

    "laboral": FILES_DIR / "Files_laboral",

    "Mtto": FILES_DIR / "Files_mtto",

    "Reparaciones": FILES_DIR / "Files_reparaciones",

    "Svial": FILES_DIR / "Files_svial",

    "Tutoriales": FILES_DIR / "Files_tutoriales"
}



def crear_carpetas_media():
    """Crea las carpetas de adjuntos. Se ejecuta en el arranque o el despliegue
    (python manage_db.py preparar-carpetas), nunca al importar este módulo."""
    for carpeta in UPLOAD_FOLDERS.values():
        carpeta.mkdir(parents=True, exist_ok=True)


# 🔹 Configuración por entorno, seleccionada con APP_ENV en el .env

class BaseConfig:
    """Valores comunes; cada entorno cambia solo lo que difiere."""
    NOMBRE_ENTORNO = None
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # La cookie de sesión solo viaja por HTTPS (los navegadores aceptan además http://localhost).
    SESSION_COOKIE_SECURE = True
    # Cinco archivos de 5 MB permiten hasta 25 MB de contenido, más la sobrecarga
    # del formato multipart; también deja espacio para videos tutoriales de hasta 20 MB.
    MAX_CONTENT_LENGTH = 26 * 1024 * 1024


class DevConfig(BaseConfig):
    NOMBRE_ENTORNO = "dev"
    DEBUG = True
    # Permite probar por http://<IP del equipo>:8090 en la red local.
    SESSION_COOKIE_SECURE = False


class QAConfig(BaseConfig):
    # QA replica producción para que lo probado allí se comporte igual.
    NOMBRE_ENTORNO = "qa"


class ProdConfig(BaseConfig):
    NOMBRE_ENTORNO = "prod"


CONFIGURACIONES = {"dev": DevConfig, "qa": QAConfig, "prod": ProdConfig}


def configuracion_activa():
    """Clase de configuración según APP_ENV. Sin APP_ENV se usa producción,
    la más estricta, para que un .env incompleto nunca relaje la seguridad."""
    entorno = (os.getenv("APP_ENV") or "prod").strip().lower()
    if entorno not in CONFIGURACIONES:
        raise RuntimeError(f"APP_ENV={entorno!r} no es válido. Use dev, qa o prod.")
    return CONFIGURACIONES[entorno]

# 🔹 Función para crear la conexión a SQL Server
# 🔹 Configuración SQL Server

SQL_SERVER = os.getenv("DB_SERVER")
DATABASE = os.getenv("DB_DATABASE")
DRIVER = os.getenv("DB_DRIVER")
usurname = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")


# Segundos máximos para establecer la conexión. Con la base caída, la petición
# responde 503 en ese tiempo en lugar de dejar el hilo bloqueado.
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "3"))

# La conexión va cifrada y se valida el certificado de SQL Server contra las CA
# de confianza del servidor de la app. Solo un entorno de desarrollo con un
# certificado autofirmado debería usar DB_TRUST_SERVER_CERTIFICATE=yes.
def leer_trust_server_certificate(valor):
    """Solo un "yes" explícito desactiva la validación; cualquier otro valor la deja activa."""
    return "yes" if (valor or "").strip().lower() == "yes" else "no"


DB_TRUST_SERVER_CERTIFICATE = leer_trust_server_certificate(os.getenv("DB_TRUST_SERVER_CERTIFICATE"))


class BaseDatosNoDisponible(Exception):
    """No fue posible conectar con SQL Server (la app responde 503 genérico)."""


def connect():
    conn_str = (
        f'DRIVER={DRIVER};'
        f'SERVER={SQL_SERVER};'
        f'DATABASE={DATABASE};'
        'Encrypt=yes;'
        f'UID={usurname};'
        f'PWD={password};'
        f'TrustServerCertificate={DB_TRUST_SERVER_CERTIFICATE};'
    )

    try:
        return pyodbc.connect(conn_str, timeout=DB_CONNECT_TIMEOUT)
    except pyodbc.Error as exc:
        raise BaseDatosNoDisponible("No fue posible conectar con SQL Server.") from exc

