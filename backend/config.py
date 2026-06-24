import pyodbc

# 🔹 Función para crear la conexión a SQL Server
# 🔹 Configuración SQL Server
SQL_SERVER = r'***REMOVED***\SQLEXPRESS'
DATABASE = 'damage_to_fleet'
DRIVER = '{ODBC Driver 18 for SQL Server}'

def connect():
    conn_str = (
        f'DRIVER={DRIVER};'
        f'SERVER={SQL_SERVER};'
        f'DATABASE={DATABASE};'
        'Trusted_Connection=yes;'
        'Encrypt=no;'
        'TrustServerCertificate=yes;'
    )
    return pyodbc.connect(conn_str)