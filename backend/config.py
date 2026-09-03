import pyodbc
import os
from pathlib import Path
import platform
from plistlib import UID

BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/media/emapp/dano_flota"))


# Carpeta principal

FILES_DIR = MEDIA_DIR / "Files"

# Carpetas de cada módulo

print("MEDIA_DIR:", MEDIA_DIR)
print("FILES_DIR:", FILES_DIR)

UPLOAD_FOLDERS = {

    "Operaciones": FILES_DIR / "Files_ppal",

    "laboral": FILES_DIR / "Files_laboral",

    "Mtto": FILES_DIR / "Files_mtto",

    "Reparaciones": FILES_DIR / "Files_reparaciones",

    "Svial": FILES_DIR / "Files_svial"
}

# Crear carpetas automáticamente si no existen

for carpeta in UPLOAD_FOLDERS.values():
    carpeta.mkdir(parents=True, exist_ok=True)        

# 🔹 Función para crear la conexión a SQL Server
# 🔹 Configuración SQL Server


SQL_SERVER = '***REMOVED***'
DATABASE = 'damage_to_fleet'
DRIVER = '{ODBC Driver 18 for SQL Server}'
usurname = '***REMOVED***'
password = '***REMOVED***'

"""
SQL_SERVER = '127.0.0.1,1433'
DATABASE = 'damage_to_fleet'
DRIVER = '{ODBC Driver 18 for SQL Server}'
usurname = '***REMOVED***'
password = '***REMOVED***'
"""


def connect():
    conn_str = (
        f'DRIVER={DRIVER};'
        f'SERVER={SQL_SERVER};'
        f'DATABASE={DATABASE};'
        'Encrypt=no;'
        f'UID={usurname};'
        f'PWD={password};'
        'TrustServerCertificate=yes;'
    )

    return pyodbc.connect(conn_str, timeout=10)