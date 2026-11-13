# Proyecto Emasivo Daño a Flota

Aplicación web (Flask + SQL Server) para la gestión de daños a flota en Emasivo.

Contenido:

1. [Requisitos](#1-requisitos)
2. [Variables de entorno](#2-variables-de-entorno)
3. [Instalación en un servidor nuevo (producción o QA)](#3-instalación-en-un-servidor-nuevo-producción-o-qa)
4. [Procedimiento de actualización](#4-procedimiento-de-actualización)
5. [Desarrollo local](#5-desarrollo-local)
6. [Esquema SQL Server y migraciones](#6-esquema-sql-server-y-migraciones)
7. [Archivos de despliegue](#7-archivos-de-despliegue)
8. [Pruebas](#8-pruebas)

# 1. Requisitos

| Componente | Versión |
|---|---|
| Sistema operativo del servidor | Ubuntu 24.04.5 LTS |
| Python | 3.12.x (no use otra versión) |
| SQL Server | Instancia accesible desde el servidor |
| Controlador ODBC | ODBC Driver 17 for SQL Server (`msodbcsql17`) |
| Servidor web / proxy | nginx con certificado HTTPS |
| Supervisor de procesos | Supervisor |
| Otros | Git, `envsubst` (paquete `gettext-base`) |

Las dependencias de Python (Flask, Gunicorn, etc.) están fijadas en
`requirements.txt` y se instalan con `pip`; no se instalan a mano.

En Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv nginx supervisor gettext-base unixodbc
```

El controlador `msodbcsql17` se instala desde el repositorio de Microsoft,
siguiendo su guía "Install the Microsoft ODBC driver for SQL Server (Linux)"
para Ubuntu 24.04.

# 2. Variables de entorno

La configuración vive en un archivo `.env` en la raíz del repositorio. Se crea
copiando `.env.example` y completando los valores. El `.env` contiene claves:
**nunca se sube a Git** (ya está en `.gitignore`) y en el servidor solo lo puede
leer el usuario de la aplicación.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `APP_ENV` | Recomendada | `prod`, `qa` o `dev`. Sin valor se usa `prod`, la más estricta. `dev` permite la cookie de sesión por http y solo se usa en equipos de desarrollo. |
| `SECRET_KEY` | Sí | Clave larga y aleatoria para firmar las sesiones. Genérela con `python3 -c "import secrets; print(secrets.token_hex(32))"`. La app no arranca sin ella. |
| `APP_BASE_URL` | Sí | URL pública con `https://`, sin barra final (ej. `https://gfd.emasivosas.com.co`). Se usa en el enlace de recuperación de contraseña. |
| `DB_SERVER` | Sí | Servidor o instancia de SQL Server. |
| `DB_DATABASE` | Sí | Nombre de la base (`damage_to_fleet`). |
| `DB_DRIVER` | Sí | `{ODBC Driver 17 for SQL Server}` |
| `DB_USER` / `DB_PASSWORD` | Sí | Usuario y contraseña de SQL Server para la app. |
| `DB_TRUST_SERVER_CERTIFICATE` | No | `no` (por defecto): la conexión va cifrada y se valida el certificado de SQL Server. `yes` solo en desarrollo con un certificado autofirmado; nunca en QA ni producción. |
| `DB_CONNECT_TIMEOUT` | No | Segundos para conectar con SQL Server (por defecto `3`). Con la base caída, la app responde "Servicio no disponible" en ese tiempo. |
| `SMTP_HOST` / `SMTP_PORT` | No | Servidor de correo (por defecto `smtp.gmail.com` y `587`). |
| `SMTP_USER` / `SMTP_PASSWORD` | Sí | Cuenta que envía los correos de recuperación de contraseña. |
| `APP_LOG_DIR` | No | Carpeta del `app.log`. Por defecto `backend/logs`. El archivo rota al llegar a 10 MB y se conservan 5 anteriores (`app.log.1` … `app.log.5`). |
| `RATELIMIT_STORAGE_URI` | Obligatoria con varios workers | Configure un Redis accesible (ej. `redis://localhost:6379`) para compartir el contador de intentos de login. Con un solo worker se admite dejarla vacía. |
| `GUNICORN_BIND` | No | Por defecto `unix:/var/www/dano_flota/ipc.sock`. |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` / `GUNICORN_TIMEOUT` | No | Por defecto `3` procesos con `4` hilos cada uno y `120` segundos. |

# 3. Instalación en un servidor nuevo (producción o QA)

La app corre con Gunicorn como un **usuario de servicio** (nunca root), en una
carpeta fuera de `/home`, administrada por Supervisor y detrás de nginx, que
termina el HTTPS. Gunicorn escucha en un socket Unix y no se expone en ningún
puerto público.

Ejecute los pasos en orden con un usuario de TI que tenga `sudo`.

## 3.1 Valores del servidor

Ajuste estos valores y déjelos definidos en la terminal; los pasos siguientes
los usan.

```bash
export APP_DIR=/opt/dano_flota            # raíz del repositorio (fuera de /home)
export APP_USER=dano_flota                # usuario de servicio que ejecuta Gunicorn
export DEPLOY_USER=$USER                  # usuario de TI que hace git pull y pip install
export VENV_DIR=$APP_DIR/venv             # entorno virtual
export MEDIA_DIR=/media/emapp/dano_flota  # igual a MEDIA_DIR de backend/config.py
export LOG_DIR=/var/log/dano_flota        # logs de Supervisor
export SERVER_NAME=gfd.emasivosas.com.co  # dominio público
export SSL_CERT=/ruta/al/certificado.pem
export SSL_KEY=/ruta/a/la/llave.pem
export GUNICORN_SOCKET=/var/www/dano_flota/ipc.sock   # igual a GUNICORN_BIND del .env
```

## 3.2 Usuario de servicio

Usuario sin shell ni carpeta personal. `www-data` también sería válido, pero un
usuario propio evita que un fallo en nginx dé acceso a la app.

```bash
sudo adduser --system --group --no-create-home --shell /usr/sbin/nologin "$APP_USER"
```

## 3.3 Código, entorno virtual y dependencias

```bash
sudo mkdir -p "$APP_DIR" && sudo chown "$DEPLOY_USER" "$APP_DIR"
git clone https://github.com/gonzalezjohan160/Dano_flota.git "$APP_DIR"
cd "$APP_DIR"

python3.12 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" --version          # debe mostrar 3.12.x
"$VENV_DIR/bin/pip" install -r requirements.txt
```

## 3.4 Certificado de SQL Server

La app cifra la conexión con SQL Server y **valida su certificado**. Pida al DBA
el certificado de la CA que firmó el de SQL Server (o el propio certificado si
es autofirmado), en formato PEM, e instálelo en el almacén de confianza:

```bash
sudo cp ca_sqlserver.crt /usr/local/share/ca-certificates/ca_sqlserver.crt
sudo update-ca-certificates
```

`DB_SERVER` debe ser el mismo nombre que aparece en el certificado (no una IP
si el certificado se emitió para un nombre). Si la conexión falla por el
certificado, la app responde "Servicio no disponible" y la causa queda en
`backend/logs/app.log`.

## 3.5 Archivo .env

```bash
cp .env.example .env
nano .env        # APP_ENV=prod (o qa) y el resto de valores de la sección 2
```

## 3.6 Base de datos

En una instalación nueva, la base se crea una sola vez con
`SQL damage_to_fleet/script.sql` y luego se aplican las migraciones (detalle en
la [sección 6](#6-esquema-sql-server-y-migraciones)):

```bash
cd "$APP_DIR/backend"
"$VENV_DIR/bin/python" manage_db.py migrate
"$VENV_DIR/bin/python" manage_db.py validate
```

## 3.7 Permisos

La app solo **escribe** en sus logs (`backend/logs`) y en la carpeta de adjuntos
(`MEDIA_DIR`); el código, el entorno virtual y el `.env` son de solo lectura
para ella.

```bash
# Código y venv: los actualiza TI; la app solo los lee.
sudo chown -R "$DEPLOY_USER":"$APP_USER" "$APP_DIR"
sudo chmod -R u=rwX,g=rX,o= "$APP_DIR"
# setgid en las carpetas: lo que traiga un git pull hereda el grupo de la app.
sudo find "$APP_DIR" -type d -exec chmod g+s {} +

# .env: solo lectura para la app, nada para otros.
sudo chmod 640 "$APP_DIR/.env"

# Únicos lugares donde la app escribe: sus logs y los adjuntos.
sudo mkdir -p "$APP_DIR/backend/logs" "$MEDIA_DIR"
sudo chown -R "$APP_USER":"$APP_USER" "$APP_DIR/backend/logs" "$MEDIA_DIR"
sudo chmod -R u=rwX,g=rX,o= "$APP_DIR/backend/logs" "$MEDIA_DIR"

# Subcarpetas de adjuntos, creadas como el usuario de la app.
cd "$APP_DIR/backend" && sudo -u "$APP_USER" "$VENV_DIR/bin/python" manage_db.py preparar-carpetas

# Carpeta del socket: el socket hereda el grupo www-data para que nginx lo use.
sudo mkdir -p "$(dirname "$GUNICORN_SOCKET")" "$LOG_DIR"
sudo chown "$APP_USER":www-data "$(dirname "$GUNICORN_SOCKET")"
sudo chmod 2770 "$(dirname "$GUNICORN_SOCKET")"
```

Si un servidor existente pasa de ejecutar la app como root a hacerlo con el
usuario de servicio, haga estos `chown` **antes** de reiniciar: el `app.log` y
los adjuntos creados por root impedirían arrancar o subir archivos.

## 3.8 Supervisor y nginx

Para M-12, la matriz de despliegue debe indicar un máximo de **11 MB por
petición**, igual que `client_max_body_size 11m` en nginx y
`MAX_CONTENT_LENGTH` en Flask. El valor deja 1 MB de margen para los campos
y el formato multipart. Capturador, Reparaciones, Control Operacional,
Mantenimiento, Seguridad Vial y Relaciones Laborales permiten, por envío,
un video de hasta 5 MB y hasta cuatro archivos adicionales que sumen como
máximo 5 MB. Tutoriales admite un video de hasta 10 MB por carga.

Las plantillas de `deploy/` se completan con los valores de la sección 3.1.
`envsubst` recibe la lista explícita de variables para no tocar las propias de
nginx (`$host`, `$scheme`...).

```bash
cd "$APP_DIR"

envsubst '${APP_DIR} ${APP_USER} ${VENV_DIR} ${LOG_DIR}' \
  < deploy/supervisor/dano_flota.conf.template \
  | sudo tee /etc/supervisor/conf.d/dano_flota.conf > /dev/null

envsubst '${SERVER_NAME} ${SSL_CERT} ${SSL_KEY} ${GUNICORN_SOCKET}' \
  < deploy/nginx/dano_flota.conf.template \
  | sudo tee /etc/nginx/sites-available/dano_flota.conf > /dev/null
sudo ln -sf /etc/nginx/sites-available/dano_flota.conf /etc/nginx/sites-enabled/

sudo nginx -t && sudo systemctl reload nginx
sudo supervisorctl reread && sudo supervisorctl update
```

Supervisor ejecuta `gunicorn -c gunicorn.conf.py wsgi:app` desde `APP_DIR` con
el usuario de servicio, lo reinicia si se cae y guarda su salida en
`$LOG_DIR/gunicorn.log`.

## 3.9 Verificación

```bash
sudo supervisorctl status dano_flota          # RUNNING
ps -o user= -p $(pgrep -d, -f gunicorn)       # solo el usuario de servicio, nunca root
curl -I https://$SERVER_NAME/                 # 200 y cabeceras de seguridad
```

En el navegador, la página de login debe abrir por `https://`. Si responde
"Servicio no disponible temporalmente", la causa está en
`$APP_DIR/backend/logs/app.log` (normalmente la base no es accesible o faltan
migraciones).

# 4. Procedimiento de actualización

Siga los pasos en este orden. Reiniciar antes de instalar las dependencias deja
los workers fallando con `ModuleNotFoundError` y la aplicación caída.

1. Haga un respaldo de SQL Server y verifique que pueda restaurarse. Este
   procedimiento no realiza ni verifica un respaldo.
2. Ponga la aplicación en mantenimiento si el procedimiento operativo lo exige.
   No ejecute `script.sql` sobre la base existente.
3. Con el usuario de TI que despliega (no con root ni con el usuario de
   servicio), descargue el código:

   ```bash
   cd /opt/dano_flota && git pull
   ```

4. Instale las dependencias, aunque el cambio no parezca agregar ninguna:

   ```bash
   /opt/dano_flota/venv/bin/pip install -r requirements.txt
   ```

5. Aplique las migraciones, valide el esquema y prepare las carpetas de adjuntos:

   ```bash
   cd /opt/dano_flota/backend
   ../venv/bin/python manage_db.py migrate
   ../venv/bin/python manage_db.py status
   ../venv/bin/python manage_db.py validate
   sudo -u dano_flota ../venv/bin/python manage_db.py preparar-carpetas
   ```

6. Si el `.env.example` trae variables nuevas, agréguelas al `.env`.
7. Reinicie y confirme que quedó en `RUNNING`:

   ```bash
   sudo supervisorctl restart dano_flota
   sudo supervisorctl status dano_flota
   ```

8. Compruebe login, cambio obligatorio de contraseña, rutas protegidas, borrado
   lógico y registro/consulta de Operaciones.

Si una migración falla, el comando identifica el archivo y se detiene: no
continúe con el despliegue (ver [sección 6](#6-esquema-sql-server-y-migraciones)).

**Primera actualización desde la versión sin archivos de despliegue:** si el
servidor tenía `wsgi.py`, `gunicorn.conf.py` o `deploy/` sin commit, compárelos
con los del repositorio y muévalos fuera del proyecto antes del `git pull`; si
no, Git se detiene con *"untracked working tree files would be overwritten"*.
Luego aplique las secciones 3.2, 3.4, 3.7 y 3.8.

# 5. Desarrollo local

En el `.env` local use `APP_ENV=dev` y una base de desarrollo, nunca la de
producción. Si su SQL Server local usa un certificado autofirmado, agregue
`DB_TRUST_SERVER_CERTIFICATE=yes` solo en ese `.env` local.

**Linux / WSL**, desde la raíz del repositorio:

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env            # APP_ENV=dev, GUNICORN_BIND=127.0.0.1:8090
venv/bin/python backend/manage_db.py preparar-carpetas
venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
```

Abra `http://localhost:8090`.

**Windows (nativo, sin WSL)**, en PowerShell desde la raíz del repositorio
(`C:\Dano_flota`). Gunicorn no funciona en Windows: se usa el servidor de Flask.

```powershell
py -3.12 -m venv venv                        # solo la primera vez
.\venv\Scripts\Activate
python -m pip install -r requirements.txt   # la primera vez y tras cada git pull
python backend\manage_db.py preparar-carpetas
python backend\backend_interfaz.py
```

Abra `https://localhost:5000` (certificado autofirmado de desarrollo: acepte la
advertencia del navegador).

El `.env` puede estar en `backend\.env` o en la raíz. Para desarrollo en Windows:

* **Carpeta de adjuntos:** `backend/config.py` trae fija la del servidor de TI
  (`MEDIA_DIR = Path("/media/emapp/dano_flota")`). Para trabajar en tu equipo, comenta esa
  línea y descomenta `# MEDIA_DIR = BASE_DIR` (archivos en `C:\Dano_flota\Files`). **Antes de
  subir al repositorio, deja otra vez la línea de TI**: en Windows la ruta de TI sería
  `C:\media\emapp\dano_flota`.
* `DB_TRUST_SERVER_CERTIFICATE=yes` si el SQL Server local usa un certificado autofirmado.

La base guarda la ruta completa de cada adjunto y la app la usa tal cual (siempre que
quede dentro de la carpeta de su módulo). Los adjuntos subidos en el servidor de TI no se
abren en tu equipo de desarrollo, y al revés.

**Rutas nuevas:** toda ruta debe declararse en `backend/autorizacion.py` (mapa
`REGLAS`, ruta → permiso). Una ruta que no esté allí responde 403 a todos los
usuarios, y la prueba `test_toda_ruta_tiene_regla_en_el_mapa_central` falla
hasta que se declare.

# 6. Esquema SQL Server y migraciones

Para respaldar el origen y preparar un punto de inicio reproducible de pruebas,
consulte la [guía del starter de QA](deploy/starter_qa.md).

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

Comandos de `manage_db.py` (desde `backend`):

| Comando | Qué hace |
|---|---|
| `migrate` | Aplica las migraciones pendientes y valida el esquema |
| `validate` | Solo valida que el esquema tenga lo que el código requiere |
| `status` | Lista las migraciones aplicadas |
| `preparar-carpetas` | Crea las carpetas de adjuntos en `MEDIA_DIR` (no usa la base) |

## Migraciones pendientes

`backend/migrations/pendientes/` guarda migraciones que **todavía no deben aplicarse**
porque esperan una corrección de datos; `migrate` no lee esa carpeta. Cada archivo
indica qué falta. Cuando se cumpla, se mueve a `backend/migrations/` (`git mv`) y se
despliega como siempre.

* `008_fechas_caso.sql`: espera que se corrijan los casos con `Fecha_evento`
  posterior a `Fecha_registro` (con "Editar" de Operaciones).

## Instalación nueva de la base

1. Prepare la instancia SQL Server y confirme que todavía no exista la base
   `damage_to_fleet`: el script la crea en las carpetas de datos por defecto de
   la instancia (no contiene rutas de archivo). Ejecútelo una sola vez desde
   SSMS o una herramienta compatible con los separadores `GO`.
2. `SQL damage_to_fleet/script.sql` crea el esquema con las columnas requeridas,
   sus tipos y defaults, incluida `dbo.table_tutoriales`. También contiene una
   conversión de permisos legados que transfiere asignaciones y elimina los
   permisos antiguos. Por eso el archivo es exclusivamente para una base nueva;
   no lo ejecute sobre una base operativa existente ni lo vuelva a ejecutar.
3. Configure el `.env` para que apunte a esa base.
4. Desde `backend`, ejecute `python manage_db.py migrate`. En una base recién
   creada, cada migración verifica que la columna del script base sea compatible
   y registra individualmente la versión en `dbo.SchemaMigrations`; no se
   estampan versiones sin comprobar el esquema.
5. Ejecute `python manage_db.py validate` y confirme que el esquema es válido.

## Si una migración falla

Revise el tipo/default existente y el error del servidor SQL sin compartir
secretos. Corrija el esquema incompatible con un procedimiento revisado,
restaure el respaldo si corresponde y vuelva a ejecutar la migración. No borre
filas de `dbo.SchemaMigrations` manualmente para forzar una repetición. Los
archivos de migración aplicados son inmutables: un cambio de nombre, versión o
contenido se detecta contra el historial y detiene el ejecutor.

## Validación al arrancar

La importación del módulo Flask no abre una conexión. Antes de procesar la
primera petición, cada worker de Gunicorn valida el esquema una vez. Si SQL
Server no está disponible o falta una columna, las peticiones reciben HTTP 503
con el mensaje genérico "Servicio no disponible temporalmente"; el detalle
(tablas, columnas y comando a ejecutar) queda solo en `backend/logs/app.log`.
Si el fallo es de conexión (SQL Server aún no responde o hubo un corte), el
worker reintenta en la siguiente petición y se recupera solo cuando la base
vuelve. Si el esquema es incompatible, el resultado se guarda en caché: aplique
las migraciones y reinicie la app. Este control solo valida; nunca aplica
migraciones automáticamente.

# 7. Archivos de despliegue

| Archivo | Uso |
|---|---|
| `wsgi.py` | Punto de entrada WSGI (`wsgi:app`) |
| `gunicorn.conf.py` | Socket, workers, timeout y logs de Gunicorn (lee `GUNICORN_*` del `.env`); se niega a arrancar como root |
| `deploy/supervisor/dano_flota.conf.template` | Programa de Supervisor |
| `deploy/nginx/dano_flota.conf.template` | Sitio nginx con HTTPS y cabeceras `X-Forwarded-*` |
| `.env.example` | Plantilla del `.env` con todas las variables |

Ningún archivo versionado contiene usuarios, rutas ni claves de un servidor
concreto; se completan con los valores de la sección 3.1 y el `.env`.

# 7.1 Estructura del código (MVC)

La convención de nombres y las rutas propuestas están en el [catálogo de nombres](catalogo_nombres.md).

| Capa | Dónde | Qué hace |
|---|---|---|
| Controlador | `backend/backend_*.py` (blueprints) | Lee la petición, aplica permisos y UF, abre y cierra la conexión con `closing(connect())`, llama al modelo y responde |
| Modelo | `backend/modelos/` | Único lugar con SQL. Recibe un cursor y parámetros; no usa Flask |
| Vista | `frontend/` (plantillas), `Static/` (JS y CSS), `backend/vistas/` (Excel) | Presenta los datos; no consulta la base |

Todos los módulos web siguen esta separación. El SQL solo vive en `backend/modelos/`; fuera de ahí
solo lo ejecutan las herramientas de esquema (`manage_db.py`, `schema_migrations.py`). Cada conexión y
cada cursor se abren con `closing()`, que los cierra aunque ocurra un error. `tests/test_arquitectura.py`
hace cumplir estas reglas, el límite de 350 líneas por archivo de Python, JavaScript y plantilla, y las
reglas de las vistas: sin `<style>` ni `<script>` en línea, sin `on*`, y `style=""` solo para `display`.

| Módulo | Controlador | Modelos | Otras capas |
|---|---|---|---|
| Histórico móvil | `backend_historico_movil.py` | `historico_movil.py` | `vistas/excel.py` |
| Histórico de daños | `backend_historico_danos.py` | `historico_danos.py`, `historico_danos_exportacion.py` | `vistas/excel_historico_danos.py`; estado de RRLL en `servicios/flujo_caso.py` |
| Dashboard | `backend_dashboard.py` | `dashboard.py` | |
| Usuarios, permisos y perfil | `backend_usuarios.py`, `backend_permisos_roles.py`, `backend_profile.py` | `usuarios.py` | |
| Tutoriales | `backend_tutoriales.py` | `tutoriales.py` | |
| Capturador y reparaciones | `backend_capturador.py`, `backend_reparaciones.py` | `capturador.py`, `reparaciones.py`, `flota.py` | |
| Autenticación y sesión | `backend_login.py`, `backend_interfaz.py`, `backend_security.py` | `autenticacion.py` | |
| Sincronización de operadores | `sincronizar_operadores.py` (tarea) | `sincronizacion_operadores.py` | |

JavaScript y CSS: cada pantalla carga sus archivos en orden desde su plantilla. Los grandes están
divididos por responsabilidad en carpetas de `Static/Script/` (`Modulo_unificado/`, `Capturador/`,
`Capturador_reparaciones/`, `Historico_danos/` e `Historicos_comun/`, compartido por los dos
históricos). Los estilos que estaban en las plantillas están en `Static/Style/` (uno por pantalla), y
los antiguos atributos `style=""` son clases `u-*` de `Style_utilidades.css`.

**Módulo unificado** (Operaciones, Mantenimiento, Seguridad Vial y RRLL), dividido en archivos de
menos de 350 líneas:

| Capa | Archivos |
|---|---|
| Fachada | `backend/backend_unificado.py`: crea el blueprint `Modulo_unificado`, conserva `connect` y `verificar_acceso_uf_caso` y registra una sola vez las rutas de `backend/unificado/` |
| Controladores | `backend/unificado/`: `bandeja`, `detalle`, `archivos`, `gestiones` (ruta `/<modulo>/<accion>`), `operaciones`, `operaciones_evento`, `mantenimiento`, `seguridad_vial`, `laboral`, `reapertura`; `configuracion` y `comun` sin rutas |
| Modelos | `modelos/casos.py`, `bandeja.py`, `detalle_caso.py`, `archivos.py`, `operaciones.py`, `mantenimiento.py`, `seguridad_vial.py`, `laboral.py`, `auditoria.py` |
| Servicio | `servicios/flujo_caso.py`: cierre automático, cuándo interviene RRLL y procesos pendientes (regla compartida por los cuatro módulos) |
| Vista | `frontend/Modulo_unificado.html` con parciales en `frontend/parciales/modulo_unificado/`; CSS en `Static/Style/Style_modulo_unificado.css`; JS en `Static/Script/Modulo_unificado/` (13 archivos que se cargan en el orden de `_scripts.html`; `inicio.js` los arranca) |

Los controladores llaman a `fachada.connect()` para que las pruebas sustituyan la conexión en un solo
lugar. `servicios/` se reserva para reglas que de verdad comparten varios controladores.

# 8. Pruebas

En los equipos de desarrollo instale también las herramientas de
`requirements-dev.txt` (no van al servidor) y active la revisión previa a cada
commit, que rechaza imports y variables sin uso:

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/pre-commit install
```

Desde la raíz del repositorio, con el entorno virtual:

```bash
venv/bin/python -m unittest discover -s tests -p "test_*.py"
venv/bin/pyflakes backend/ wsgi.py gunicorn.conf.py   # sin salida = sin código muerto
```

Las pruebas usan dobles de prueba y no necesitan SQL Server. No validan la
sintaxis ni el comportamiento real de SQL Server: la verificación de
transacciones T-SQL, `sp_getapplock`, tipos, defaults, instalación desde cero y
rollback requiere una instancia de pruebas aislada. No apunte las pruebas a
producción.

## Catálogo de responsabilidad del operador

En Control Operacional, el campo `responsabilidad_operador` se interpreta así:

| Valor guardado | Cuándo corresponde |
| --- | --- |
| `SI` | El costo no supera $2.000.000 y el operador acepta la responsabilidad. |
| `NO` | El costo no supera $2.000.000 y el operador no acepta la responsabilidad. |
| `NO APLICA` | El costo no supera $2.000.000 y se selecciona esta opción con un motivo de cierre de retiro o exoneración. |
| `NULL` | Operaciones indica que el costo supera $2.000.000. El formulario omite la pregunta y el caso continúa hacia Relaciones Laborales. |

Si el costo es exactamente $2.000.000, se exige una de las tres opciones del
formulario.

## Catálogo de conciliación

En Control Operacional, el campo `conciliacion` se interpreta así:

| Valor guardado | Cuándo corresponde |
| --- | --- |
| `SI` | El operador acepta la responsabilidad y acepta conciliar el daño. |
| `NO` | El operador acepta la responsabilidad y rechaza la conciliación. |
| `NULL` | La conciliación no se registra. Aplica cuando `responsabilidad_operador` es `NO` o `NO APLICA`, cuando el costo supera $2.000.000 o cuando la regla de reincidencia impide conciliar. |

Si Operaciones indica que el costo supera $2.000.000, tanto
`responsabilidad_operador` como `conciliacion` se guardan como `NULL`.

## Catálogo de conciliación en Seguridad Vial

| Valor de `conciliado_a_favor` | Cuándo corresponde |
| --- | --- |
| `empresa` | La empresa recibe dinero por una conciliación derivada de un evento en vía. |
| `terceros` | La empresa entrega dinero a un tercero por una conciliación derivada de un evento en vía. |
| `NULL` | No hubo conciliación en vía. |

## Catálogo de unidades funcionales y alcance de usuarios (BD-12)

| Valor | Unidad o alcance |
| --- | --- |
| `10` | Unidad Funcional 10. Como alcance, autoriza únicamente la UF 10. |
| `16` | Unidad Funcional 16. Como alcance, autoriza únicamente la UF 16. |
| `TRANSVERSAL` | Autoriza las UF 10 y 16. Solo se registra en `usuario.Table_usuarios.Alcance_UF` como texto. |

La columna `UF` de móviles, daños e intervenciones usa `tinyint` y
referencia `catalogo.unidad_funcional(id)`. El catálogo físico contiene
las unidades 10 y 16. `Alcance_UF` admite `varchar(20)` y `nvarchar(20)`.

En una base con las tablas `flota.table_Moviles`, `flota.table_damage_to_fleet`,
`proceso.table_intervenciones` y `usuario.Table_usuarios`, ejecute
[`BD-12_unidad_funcional.sql`](deploy/sql/BD-12_unidad_funcional.sql)
después de los cambios de tipo y nombre de columna. El script crea o completa
el catálogo y valida las tres claves foráneas contra los datos existentes.
La migración 008 corresponde a otro esquema que elimina la UF duplicada de
casos e intervenciones y renombra las tablas.

# Modificaciones

1. cambio llamar formato de Fecha registro
2. Adicionar al modulo de rrll imegenes de mtto y svial
3. Adicionar la funcion descargar archivos (xlsx) y llamar de acuerdo a los filtros
4. Mejorar la sidebar de interfaz
5. Las correcciones se realizan directamente desde cada módulo
