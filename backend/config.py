import pyodbc
import os
from dotenv import load_dotenv
from pathlib import Path
import platform
from plistlib import UID

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

# Crear carpetas automáticamente si no existen

for carpeta in UPLOAD_FOLDERS.values():
    carpeta.mkdir(parents=True, exist_ok=True)        

# 🔹 Función para crear la conexión a SQL Server
# 🔹 Configuración SQL Server

SQL_SERVER = os.getenv("DB_SERVER")
DATABASE = os.getenv("DB_DATABASE")
DRIVER = os.getenv("DB_DRIVER")
usurname = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")



def connect():
    conn_str = (
        f'DRIVER={DRIVER};'
        f'SERVER={SQL_SERVER};'
        f'DATABASE={DATABASE};'
        'Encrypt=yes;'
        f'UID={usurname};'
        f'PWD={password};'
        'TrustServerCertificate=yes;'
    )

    return pyodbc.connect(conn_str, timeout=10)
