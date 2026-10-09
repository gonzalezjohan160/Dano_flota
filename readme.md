# Proyecto Emasivo Daño a Flota

Aplicación web para la gestión de daños a flota en Emasivo.

# Instalación

## Requisitos previos

Para la instalación y ejecución de la aplicación se requiere:

* Ubuntu 24.04.5 LTS
* Python 3.12.3
* SQL Server
* ODBC Driver 17 for SQL Server
* Git
* Gunicorn 26.x

La aplicación requiere Python 3.12.x y no debe ejecutarse con versiones diferentes a la especificada.

## Clonar el repositorio


git clone https://github.com/gonzalezjohan160/Dano_flota.git
cd Dano_flota


## Crear y activar el entorno virtual

Se recomienda utilizar un entorno virtual para instalar las dependencias de la aplicación.


python3.12 -m venv ~/.venvs/dano_flota
source ~/.venvs/dano_flota/bin/activate


Verificar la versión de Python:


python --version


Debe mostrar una versión 3.12.x.

## Instalar dependencias

Con el entorno virtual activado:

pip install -r requirements.txt


Las dependencias de la aplicación se encuentran especificadas en `requirements.txt`.

# Variables de entorno

La aplicación utiliza un archivo `.env` para almacenar la configuración necesaria para conectarse a la base de datos, gestionar la seguridad de la aplicación y utilizar el servicio de correo electrónico.

El archivo `.env` debe configurarse en el servidor y no debe incluirse en el repositorio Git, ya que contiene información sensible.

## Configuración de base de datos


DB_SERVER=
DB_DATABASE=
DB_DRIVER=
DB_USER=
DB_PASSWORD=


* `DB_SERVER`: servidor o instancia de SQL Server.
* `DB_DATABASE`: nombre de la base de datos.
* `DB_DRIVER`: controlador ODBC utilizado para la conexión.
* `DB_USER`: usuario de conexión a la base de datos.
* `DB_PASSWORD`: contraseña del usuario de base de datos.

Para el entorno definido se utiliza:


DB_DRIVER={ODBC Driver 17 for SQL Server}


## Seguridad de la aplicación


SECRET_KEY=
APP_BASE_URL=


* `SECRET_KEY`: clave utilizada por Flask para la seguridad de las sesiones y otros mecanismos de seguridad de la aplicación.
* `APP_BASE_URL`: URL pública del aplicativo con `https://`, sin barra final ni ruta (por ejemplo `https://gfd.emasivosas.com.co`). Se usa para construir el enlace de restablecimiento de contraseña; si falta o no usa `https://`, no se envía el correo y el error queda en el log.

Esta clave debe ser privada y no debe almacenarse en el repositorio.

## Configuración de correo electrónico


SMTP_USER=
SMTP_PASSWORD=


* `SMTP_USER`: usuario utilizado para la autenticación del servicio SMTP.
* `SMTP_PASSWORD`: contraseña utilizada para la autenticación del servicio SMTP.

Los valores reales de estas variables deben ser proporcionados y configurados de acuerdo con el servicio de correo autorizado.

# Ejecución en Windows

Esta sección corresponde principalmente al entorno de desarrollo local.

## 1. Activar el entorno virtual

Desde PowerShell:


.\venv\Scripts\Activate.ps1


Desde CMD:


.\venv\Scripts\activate


## 2. Ir al directorio del backend


cd backend


## 3. Ejecutar la aplicación


python backend_interfaz.py


## 4. Abrir la aplicación

Abrir en el navegador:

http://localhost:5000

# Ejecución local en Linux / WSL

Esta configuración corresponde a la ejecución local utilizada durante el desarrollo y las pruebas.

## 1. Activar el entorno virtual


source ~/.venvs/dano_flota/bin/activate


## 2. Ir al directorio del backend


cd /mnt/c/Dano_flota/backend


## 3. Ejecutar la aplicación con Gunicorn


gunicorn --workers 3 --timeout 180 --bind 0.0.0.0:8090 backend_interfaz:Interfaz


## 4. Abrir la aplicación

Abrir en el navegador:

http://localhost:8090

# Despliegue en servidor Linux

El despliegue de producción debe realizarse sobre Ubuntu 24.04.5 LTS y utilizando Gunicorn como servidor WSGI.

## 1. Activar el entorno virtual


source ~/.venvs/dano_flota/bin/activate


## 2. Verificar la versión de Python


python --version


Debe corresponder a Python 3.12.x.

## 3. Instalar las dependencias


pip install -r requirements.txt


## 4. Configuración de Gunicorn

La aplicación debe exponerse mediante el punto de entrada WSGI:


wsgi:app


La ejecución de Gunicorn en producción debe utilizar un socket Unix en lugar de exponer directamente el puerto de la aplicación.

Ejemplo:


gunicorn \
    --workers 3 \
    --timeout 120 \
    --bind unix:/var/www/dano_flota/ipc.sock \
    wsgi:app


El número de workers y el timeout deben ajustarse de acuerdo con la configuración definida para el servidor.

## 5. Acceso a la aplicación

En producción, Gunicorn no debe exponerse directamente mediante un puerto HTTP público.

La aplicación debe ser atendida mediante el servidor web/proxy configurado por TI, utilizando el socket Unix:


/var/www/dano_flota/ipc.sock




# Modificaciones 
1. cambio llamar formato de Fecha registro
2. Adicionar al modulo de rrll imegenes de mtto y svial
3. Adicionar la funcion descargar archivos (xlsx) y llamar de acuerdo a los filtros
4. Mejorar la sidebar de interfaz
5. Las correcciones se realizan directamente desde cada módulo

# Esquema SQL Server y migraciones

El código requiere estas columnas: `dbo.Table_usuarios.Cambio_password_obligatorio`,
`dbo.table_damage_to_fleet.eliminado`, `dbo.table_info_oper.responsabilidad_operador`,
`dbo.table_info_oper.conciliacion` y `dbo.table_tutoriales.Titulo` (la migración 005
crea la tabla de tutoriales si no existe). Las migraciones versionadas están en
`backend/migrations/`; el historial queda en `dbo.SchemaMigrations` e incluye la
versión, nombre de archivo, SHA-256 del contenido y fecha UTC.

El comando `manage_db.py migrate` es explícito: no se ejecuta al importar Flask,
al atender peticiones ni al iniciar Gunicorn. Cada archivo se ejecuta como un
único batch T-SQL, sin `GO`; el cambio de esquema y la fila de historial se
confirman en una transacción por migración. Un bloqueo de aplicación SQL Server
serializa ejecutores concurrentes. Si una migración falla, se revierte esa
transacción y el proceso se detiene sin registrar esa versión.

## Instalación nueva

1. Prepare la instancia SQL Server y confirme que todavía no exista la base
   `damage_to_fleet`: el script la crea en las carpetas de datos por defecto de
   la instancia (no contiene rutas de archivo). Ejecútelo una sola vez en una
   instalación nueva desde SSMS o una herramienta compatible con los separadores `GO`.
2. `SQL damage_to_fleet/script.sql` conserva el esquema existente y crea las
   columnas requeridas con sus tipos y defaults, incluida `dbo.table_tutoriales`. También contiene una
   conversión de permisos legados que transfiere asignaciones y elimina los
   permisos antiguos. Por eso el archivo es exclusivamente para una base nueva;
   no lo ejecute sobre una base operativa existente ni lo vuelva a ejecutar.
3. Configure las variables de entorno descritas arriba para que `config.py`
   apunte a esa base. No guarde el archivo `.env` en Git.
4. Desde `backend`, ejecute `python manage_db.py migrate`. En una base recién
   creada, cada migración verifica que la columna del script base sea compatible
   y registra individualmente la versión en `dbo.SchemaMigrations`; no se
   estampan versiones sin comprobar el esquema.
5. Ejecute `python manage_db.py validate` y confirme que informa que el esquema
   requerido es válido.
6. Inicie Flask/Gunicorn como se indica arriba.

## Actualización de una base existente

1. Antes del despliegue, realice un respaldo de SQL Server y verifique que pueda
   restaurarse. Este procedimiento no realiza ni verifica un respaldo.
2. Ponga la aplicación en mantenimiento si el procedimiento operativo lo exige.
   No ejecute `script.sql` sobre la base existente.
3. Con las variables de entorno apuntando explícitamente a la base autorizada,
   ejecute `python manage_db.py migrate`. Revise cada versión que el comando
   informe como aplicada o ya aplicada.
4. Consulte el historial con `python manage_db.py status` y valide con
   `python manage_db.py validate`.
5. Reinicie Gunicorn y compruebe login, cambio obligatorio de contraseña,
   rutas protegidas, borrado lógico y registro/consulta de Operaciones.

Si una migración falla, el comando identifica el archivo y se detiene; no
continúe con el despliegue. Revise el tipo/default existente y el error del
servidor SQL sin compartir secretos. Corrija el esquema incompatible con un
procedimiento revisado, restaure el respaldo si corresponde y vuelva a ejecutar
la migración. No borre filas de `dbo.SchemaMigrations` manualmente para forzar
una repetición. Los archivos de migración aplicados son inmutables: un cambio
de nombre, versión o contenido se detecta contra el historial y detiene el
ejecutor.

## Comandos por entorno

Windows PowerShell, desde la raíz del repositorio:

```powershell
Set-Location .\backend
..\venv\Scripts\python.exe manage_db.py migrate
..\venv\Scripts\python.exe manage_db.py validate
..\venv\Scripts\python.exe manage_db.py status
```

WSL/Linux, desde la raíz montada o clonada:

```bash
cd /mnt/c/Dano_flota/backend  # ajuste si el repositorio está en otra ruta
python3 manage_db.py migrate
python3 manage_db.py validate
python3 manage_db.py status
```

La importación del módulo Flask no abre una conexión. Antes de procesar la
primera petición, cada proceso Gunicorn valida el esquema una vez; como los
workers son procesos aislados, cada worker hace esa comprobación una vez. Si
SQL Server no está disponible o falta una columna, las peticiones reciben HTTP
503 con un mensaje accionable y ese worker conserva el fallo en caché para no
reintentar una conexión en cada petición. Tras corregir la base, reinicie los
workers. Este control solo valida: nunca aplica migraciones automáticamente.

## Pruebas

Las pruebas unitarias del ejecutor/validador se pueden correr con:

```bash
python -m unittest discover -s tests -p 'test_n09_schema_migrations.py' -v
```

Estas pruebas usan dobles de prueba y no validan sintaxis ni comportamiento real
de SQL Server. La verificación de transacciones T-SQL, `sp_getapplock`, tipos,
defaults, instalación desde cero y rollback requiere una instancia SQL Server
de pruebas aislada. No se debe apuntar el comando de prueba a producción.

