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


* `SECRET_KEY`: clave utilizada por Flask para la seguridad de las sesiones y otros mecanismos de seguridad de la aplicación.

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

