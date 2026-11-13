# Punto de inicio de QA de Dano_flota

TI entrega tres elementos por versión: el respaldo recuperable del origen, el paquete enmascarado para cargar QA y el respaldo del punto de inicio validado en QA. Registre el identificador de entrega, la revisión de código, el ambiente de origen, la fecha y hora de corte con zona horaria, quién operó el procedimiento y dónde se custodia cada archivo.

## 1. Respaldar el origen

1. El DBA y el responsable de la aplicación acuerdan la ventana del corte. Detenga las escrituras en la aplicación y las tareas que escriben en SQL Server o en adjuntos durante ambos respaldos, o use instantáneas coordinadas de infraestructura. Confirme que ya terminaron las escrituras en curso.
2. El DBA ejecuta [qa_starter_respaldo.sql](sql/qa_starter_respaldo.sql) con los tres parámetros del origen. El script genera un `.bak` nativo `COPY_ONLY` con checksum y ejecuta `RESTORE VERIFYONLY`. La ruta es la que ve el servicio de SQL Server y debe ser nueva.
3. Desde el servidor que contiene los archivos, con Python 3.12 y desde la raíz del repositorio, respalde el `MEDIA_DIR` activo en una carpeta protegida que ya exista. Conserve el ZIP junto al respaldo SQL del mismo corte.

   ```powershell
   python -m deploy.qa_starter respaldar-adjuntos 'C:\Dano_flota\Files' 'D:\Resguardos\corte.adjuntos.zip'
   Get-FileHash 'D:\Resguardos\corte.bak', 'D:\Resguardos\corte.adjuntos.zip' -Algorithm SHA256
   ```

4. Antes de dar por recuperable el respaldo, compruebe las huellas y restaure el `.bak` en una instancia aislada administrada por TI. Use `RESTORE FILELISTONLY` para identificar **cada** archivo lógico y complete [qa_starter_restaurar.sql](sql/qa_starter_restaurar.sql) con un nombre de base y rutas físicas nuevas. El script verifica y restaura con `CHECKSUM`, sin `REPLACE`. Ejecute `DBCC CHECKDB` sobre la restauración. Si el origen usa TDE, TI debe contar con su certificado y clave de recuperación en la instancia aislada. [Opciones de restauración de SQL Server](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-arguments-transact-sql)
5. Ensaye la recuperación de adjuntos en un directorio nuevo. Para recuperar una aplicación, restablezca el `MEDIA_DIR` y la estructura de rutas que espera esa copia de la base. Si las rutas son absolutas y cambia la ubicación, valide y ajuste las referencias antes de abrir la aplicación.

   ```powershell
   python -m deploy.qa_starter restaurar-adjuntos 'D:\Resguardos\corte.adjuntos.zip' 'D:\Recuperacion\AdjuntosCorte'
   ```

El `.bak` y el ZIP de adjuntos contienen información real. Custódielos en almacenamiento cifrado y con acceso restringido a los responsables de recuperación. El entorno temporal con el respaldo restaurado tiene la misma clasificación que el origen.

## 2. Generar el paquete de QA

1. Deje la **restauración aislada** en `READ_ONLY` antes de exportar. Use una cuenta de lectura sobre las tablas incluidas, con visibilidad de metadatos. Configure `DANO_STARTER_ORIGEN_ODBC` en la sesión del operador mediante el mecanismo de secretos de TI. La cadena ODBC debe especificar base, cifrado y validación del certificado. No use las credenciales de la aplicación. El nombre de instancia indicado debe coincidir con `SERVERPROPERTY('ServerName')`.
2. Revise el plan de tablas y columnas. Confirme que los campos que la política conserva, como fechas, montos, números de móvil y catálogos, se pueden usar en QA. Si una columna funcional contiene datos personales o una nueva columna requiere una regla, ajuste [la política](qa_starter/politica.py) y repita el plan.

   ```powershell
   python -m deploy.qa_starter plan --servidor SQL-STAGING --base dano_corte
   python -m deploy.qa_starter exportar --servidor SQL-STAGING --base dano_corte 'D:\Resguardos\corte.starter.zip'
   python -m deploy.qa_starter verificar 'D:\Resguardos\corte.starter.zip'
   python -m deploy.qa_starter cuentas 'D:\Resguardos\corte.starter.zip'
   Get-FileHash 'D:\Resguardos\corte.starter.zip' -Algorithm SHA256
   ```

El paquete conserva claves, relaciones, estados y los datos funcionales que muestra el plan. Los operadores reciben códigos de prueba consistentes dentro del paquete. Se sustituyen nombres de usuario, identificaciones, correos, nombres de operadores, direcciones y texto libre. Las contraseñas, los tokens, los tutoriales originales y el contenido de evidencias se excluyen. Las referencias de evidencias de casos y reparaciones se convierten en PNG sintéticos para probar la galería y las descargas. Las pruebas de audio, video y tutoriales requieren archivos de prueba propios.

El archivo ZIP contiene un manifiesto con versión, fecha, estructura, conteo y SHA-256 por tabla. La huella externa del ZIP debe compararse con la registrada por TI antes de cargar. Las huellas del manifiesto detectan alteraciones accidentales y la huella custodiada permite comprobar que se recibió el paquete acordado. El paquete conserva identificadores internos y datos operativos, por lo que se maneja como información de acceso restringido.

## 3. Cargar QA

1. El DBA prepara una **base nueva y vacía** con sufijo `_qa`. Use el esquema físico del mismo despliegue, incluidas vistas, restricciones, objetos y el historial de migraciones que correspondan. Genere el DDL desde la versión de referencia si el script base del repositorio aún no refleja ese esquema. Deje vacías las tablas que el starter repuebla, incluidos catálogos, usuarios y permisos. Valide el esquema de la aplicación con `python backend/manage_db.py validate` apuntando a QA. Asegure que la aplicación QA tenga su propia raíz de adjuntos y que las tareas de sincronización y el correo de QA usen destinos de prueba.
2. En esa base nueva, el DBA agrega la marca para autorizar el uso del cargador. La cuenta de carga debe poder leer el esquema y las filas de QA, insertar en las tablas del paquete y usar `IDENTITY_INSERT`. Configure `DANO_STARTER_QA_ODBC` con una credencial de QA en la sesión del operador.

   ```sql
   EXEC sys.sp_addextendedproperty @name = N'DanoFlotaStarterDestino', @value = N'qa';
   ```

3. Compruebe el destino, seleccione en el inventario los aliases con los permisos y UF requeridos, y cargue. Puede repetir `--activar` para cada cuenta aprobada. La herramienta pide la clave temporal individual en la terminal y el primer ingreso obliga a cambiarla. Sin `--activar`, todas quedan inactivas. Indique la raíz `MEDIA_DIR` efectiva de la aplicación QA y ejecute la carga en el servidor que sirve esos archivos, con permisos de escritura en esa raíz. Las rutas del ejemplo corresponden a una instalación de QA en un host Windows separado.

   ```powershell
   python -m deploy.qa_starter plan --destino --servidor SQL-QA --base dano_flota_qa
   python -m deploy.qa_starter cargar --servidor SQL-QA --base dano_flota_qa --media 'C:\Dano_flota\Files' --activar qa_42 'D:\Resguardos\corte.starter.zip'
   ```

La carga exige que coincidan la instancia, la base, la marca de QA y las columnas del paquete. Conserva las restricciones activas y carga las tablas según las claves foráneas. Comprueba conteos y confirma todo SQL en una sola transacción. Si la transacción falla, es posible repetir sobre el destino vacío. Pueden quedar PNG sintéticos reutilizables del mismo paquete. La herramienta rehúsa cargar sobre una base con filas en las tablas del starter. Si se pierde la conexión al confirmar, compruebe el estado del destino antes de repetir.

## 4. Aceptar y recuperar el punto de inicio

1. QA compara los conteos con el manifiesto. Comprueba ingreso, cambio de contraseña, permisos por UF, casos de muestra con su historial, gestiones de cada módulo y descarga de evidencias sintéticas. Registre los casos revisados, el resultado y las excepciones.
2. Con QA en pausa, haga un **nuevo respaldo de la base QA y de sus adjuntos** con el procedimiento de la sección 1. Etiquételos con la revisión, el identificador del paquete y la fecha de aceptación. Este par recupera el punto de inicio ya validado con las cuentas, los archivos y los cambios de configuración que quedaron en la base.
3. Para repetir pruebas, restaure ese par en un ambiente aislado con las rutas correctas. También puede reconstruir los datos del starter sobre otra base QA vacía y seleccionar de nuevo las cuentas. Conserve el QA anterior si contiene evidencias de ejecución que deben archivarse.
