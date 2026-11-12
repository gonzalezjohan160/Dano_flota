-- Auditoría de base de datos (7-10-26), sección 5.5 y hallazgo 1: nombres uniformes
-- y UF/tipología tomadas del móvil.
--
-- Convención: español, minúsculas con guion bajo, sin prefijo table_. Cada tabla
-- tiene su clave "id"; la columna que apunta a otra tabla se llama <tabla>_id
-- (caso_id, usuario_id...). Los catálogos usan su "nombre" como clave.
-- Quien registra se llama registrado_por en todas las tablas.
--
-- Decisión de negocio: la UF y la tipología de un caso son siempre las de su móvil
-- (un móvil no cambia de UF). Antes de quitarlas del caso y de la intervención se
-- verifica que coincidan con el maestro de móviles; si alguna difiere, se detiene.
IF OBJECT_ID(N'flota.table_damage_to_fleet', N'U') IS NULL
    THROW 51081, 'La base no tiene la estructura esperada (esquemas flota, proceso y usuario con los nombres del 5-nov-2026).', 1;

DECLARE @diferencias nvarchar(2048);
SELECT @diferencias = STRING_AGG(CONVERT(nvarchar(30), detalle), N', ')
FROM (
    SELECT N'caso ' + CONVERT(nvarchar(20), d.Id_damage) AS detalle
    FROM flota.table_damage_to_fleet AS d
    LEFT JOIN flota.table_Moviles AS m ON m.No_Movil = d.Movil
    WHERE m.Id IS NULL
       OR ISNULL(d.UF, '') <> CONVERT(varchar(10), m.UF)
       OR ISNULL(d.Tipologia, '') <> ISNULL(m.Tipologia_Movil, '')
    UNION ALL
    SELECT N'intervención ' + CONVERT(nvarchar(20), i.ID)
    FROM proceso.table_intervenciones AS i
    LEFT JOIN flota.table_Moviles AS m ON m.No_Movil = i.Movil
    WHERE m.Id IS NULL
       OR ISNULL(i.UF, '') <> CONVERT(varchar(10), m.UF)
       OR ISNULL(i.Tipologia, '') <> ISNULL(m.Tipologia_Movil, '')
) AS d;
IF @diferencias IS NOT NULL
BEGIN
    SET @diferencias = LEFT(N'Registros cuyo móvil no existe o cuya UF/tipología difiere del maestro de móviles: '
        + @diferencias + N'. Corríjalos antes de migrar.', 2047);
    THROW 51082, @diferencias, 1;
END;

-- Columnas calculadas: se recrean con los nombres nuevos en la migración 009.
ALTER TABLE flota.table_damage_to_fleet DROP COLUMN franja_horaria;
ALTER TABLE flota.table_damage_files DROP COLUMN Modulo;

ALTER TABLE flota.table_damage_to_fleet DROP COLUMN UF, Tipologia;
ALTER TABLE proceso.table_intervenciones DROP COLUMN UF, Tipologia;

-- ------------------------------------------------------------------ tablas ---
EXEC sp_rename N'flota.table_damage_to_fleet', N'caso', N'OBJECT';
EXEC sp_rename N'flota.table_damage_files', N'archivo_caso', N'OBJECT';
EXEC sp_rename N'flota.table_drivers', N'operador', N'OBJECT';
EXEC sp_rename N'flota.table_Moviles', N'movil', N'OBJECT';
EXEC sp_rename N'proceso.table_info_oper', N'gestion_operaciones', N'OBJECT';
EXEC sp_rename N'proceso.table_info_mtto', N'gestion_mantenimiento', N'OBJECT';
EXEC sp_rename N'proceso.table_info_svial', N'gestion_seguridad_vial', N'OBJECT';
EXEC sp_rename N'proceso.table_info_labora', N'cierre_laboral', N'OBJECT';
EXEC sp_rename N'proceso.table_info_laboral_mult', N'seguimiento_laboral', N'OBJECT';
EXEC sp_rename N'proceso.table_auditoria_correcciones', N'correccion', N'OBJECT';
EXEC sp_rename N'proceso.table_intervenciones', N'intervencion', N'OBJECT';
EXEC sp_rename N'proceso.table_intervenciones_files', N'archivo_intervencion', N'OBJECT';
EXEC sp_rename N'usuario.Table_usuarios', N'usuario', N'OBJECT';
EXEC sp_rename N'usuario.Table_permisos', N'permiso', N'OBJECT';
EXEC sp_rename N'usuario.Table_usuarios_permisos', N'usuario_permiso', N'OBJECT';
EXEC sp_rename N'usuario.Table_password_reset', N'restablecimiento_contrasena', N'OBJECT';
EXEC sp_rename N'usuario.table_tutoriales', N'tutorial', N'OBJECT';

-- ---------------------------------------------------------------- columnas ---
CREATE TABLE #columnas (tabla nvarchar(128), anterior sysname, nueva sysname);
INSERT INTO #columnas (tabla, anterior, nueva) VALUES
    (N'flota.caso', N'Id_damage', N'id'),
    (N'flota.caso', N'Fecha_evento', N'fecha_evento'),
    (N'flota.caso', N'Movil', N'movil'),
    (N'flota.caso', N'Codigo', N'codigo_operador'),
    (N'flota.caso', N'Nombre', N'nombre_operador'),
    (N'flota.caso', N'Ruta', N'ruta'),
    (N'flota.caso', N'Direccion', N'direccion'),
    (N'flota.caso', N'Version_libre', N'version_libre'),
    (N'flota.caso', N'Parte_afectada', N'parte_afectada'),
    (N'flota.caso', N'Dano_ocasionado', N'tipo_dano'),
    (N'flota.caso', N'Zona_dano', N'zona_dano'),
    (N'flota.caso', N'Registrador', N'registrado_por'),
    (N'flota.caso', N'Centro_operaciones', N'centro_operacion'),
    (N'flota.caso', N'Fecha_registro', N'fecha_registro'),
    (N'flota.caso', N'Area', N'area'),
    (N'flota.caso', N'estado_caso', N'cerrado'),
    (N'flota.archivo_caso', N'Id', N'id'),
    (N'flota.archivo_caso', N'Id_damage', N'caso_id'),
    (N'flota.archivo_caso', N'FileName', N'nombre_archivo'),
    (N'flota.archivo_caso', N'FilePath', N'ruta_archivo'),
    (N'flota.archivo_caso', N'Fecha_subida', N'fecha_subida'),
    (N'flota.operador', N'Id', N'id'),
    (N'flota.operador', N'Codigo_OBZ', N'codigo'),
    (N'flota.operador', N'Nombre_OBZ', N'nombre'),
    (N'flota.movil', N'Id', N'id'),
    (N'flota.movil', N'UF', N'unidad_funcional_id'),
    (N'flota.movil', N'No_Movil', N'numero'),
    (N'flota.movil', N'Tipologia_Movil', N'tipologia'),
    (N'proceso.gestion_operaciones', N'Id', N'id'),
    (N'proceso.gestion_operaciones', N'Id_damage', N'caso_id'),
    (N'proceso.gestion_operaciones', N'Observaciones_operaciones', N'observaciones'),
    (N'proceso.gestion_operaciones', N'Usuario_registro_oper', N'registrado_por'),
    (N'proceso.gestion_operaciones', N'Fecha_registro', N'fecha_registro'),
    (N'proceso.gestion_operaciones', N'Observaciones_correctivos', N'observaciones_correctivos'),
    (N'proceso.gestion_operaciones', N'rev_error', N'informacion_correcta'),
    (N'proceso.gestion_operaciones', N'costo_oper', N'costo'),
    (N'proceso.gestion_operaciones', N'estado_oper', N'completada'),
    (N'proceso.gestion_mantenimiento', N'Id', N'id'),
    (N'proceso.gestion_mantenimiento', N'Id_damage', N'caso_id'),
    (N'proceso.gestion_mantenimiento', N'Costo', N'costo'),
    (N'proceso.gestion_mantenimiento', N'Usuario_registro_mtto', N'registrado_por'),
    (N'proceso.gestion_mantenimiento', N'Fecha_registro', N'fecha_registro'),
    (N'proceso.gestion_mantenimiento', N'estado_mtto', N'completada'),
    (N'proceso.gestion_seguridad_vial', N'Id', N'id'),
    (N'proceso.gestion_seguridad_vial', N'Id_damage', N'caso_id'),
    (N'proceso.gestion_seguridad_vial', N'Observaciones_svial', N'observaciones'),
    (N'proceso.gestion_seguridad_vial', N'Usuario_registro_svial', N'registrado_por'),
    (N'proceso.gestion_seguridad_vial', N'Fecha_registro', N'fecha_registro'),
    (N'proceso.gestion_seguridad_vial', N'estado_svial', N'completada'),
    (N'proceso.cierre_laboral', N'Id', N'id'),
    (N'proceso.cierre_laboral', N'Id_damage', N'caso_id'),
    (N'proceso.cierre_laboral', N'Tipo_cerrado', N'tipo_cierre'),
    (N'proceso.cierre_laboral', N'Valor_conciliado', N'valor_conciliado'),
    (N'proceso.cierre_laboral', N'Usuario_registro_labora', N'registrado_por'),
    (N'proceso.cierre_laboral', N'Fecha_registro', N'fecha_registro'),
    (N'proceso.seguimiento_laboral', N'Id_info_laboral', N'id'),
    (N'proceso.seguimiento_laboral', N'Id_damage', N'caso_id'),
    (N'proceso.seguimiento_laboral', N'Fecha_presentacion', N'fecha_presentacion'),
    (N'proceso.seguimiento_laboral', N'Pendiente_proceso', N'pendiente_proceso'),
    (N'proceso.seguimiento_laboral', N'Observaciones_rrll', N'observaciones'),
    (N'proceso.seguimiento_laboral', N'Usuario_registro_laboral', N'registrado_por'),
    (N'proceso.seguimiento_laboral', N'Fecha_registro', N'fecha_registro'),
    (N'proceso.correccion', N'Id', N'id'),
    (N'proceso.correccion', N'Id_damage', N'caso_id'),
    (N'proceso.correccion', N'Tabla_Afectada', N'tabla_afectada'),
    (N'proceso.correccion', N'Campo_Modificado', N'campo_modificado'),
    (N'proceso.correccion', N'Valor_Anterior', N'valor_anterior'),
    (N'proceso.correccion', N'Valor_Nuevo', N'valor_nuevo'),
    (N'proceso.correccion', N'Usuario_Modifica', N'modificado_por'),
    (N'proceso.correccion', N'Fecha_Modificacion', N'fecha_modificacion'),
    (N'proceso.correccion', N'Motivo_modificacion', N'motivo'),
    (N'proceso.intervencion', N'ID', N'id'),
    (N'proceso.intervencion', N'Movil', N'movil'),
    (N'proceso.intervencion', N'Zona_intervenida', N'zona_intervenida'),
    (N'proceso.intervencion', N'Parte_intervenida', N'parte_intervenida'),
    (N'proceso.intervencion', N'Costo_intervencion', N'costo'),
    (N'proceso.intervencion', N'Usuario_registro', N'registrado_por'),
    (N'proceso.intervencion', N'Fecha_registro', N'fecha_registro'),
    (N'proceso.archivo_intervencion', N'Id', N'id'),
    (N'proceso.archivo_intervencion', N'RepairId', N'intervencion_id'),
    (N'proceso.archivo_intervencion', N'FileName', N'nombre_archivo'),
    (N'proceso.archivo_intervencion', N'FilePath', N'ruta_archivo'),
    (N'proceso.archivo_intervencion', N'Fecha_subida', N'fecha_subida'),
    (N'usuario.usuario', N'ConsID', N'id'),
    (N'usuario.usuario', N'Username', N'nombre_usuario'),
    (N'usuario.usuario', N'PasswordHash', N'hash_contrasena'),
    (N'usuario.usuario', N'Nombre', N'nombre'),
    (N'usuario.usuario', N'Email', N'correo'),
    (N'usuario.usuario', N'FechaCreacion', N'fecha_creacion'),
    (N'usuario.usuario', N'Activo', N'activo'),
    (N'usuario.usuario', N'IDusuario', N'identificacion'),
    (N'usuario.usuario', N'UF', N'alcance_uf'),
    (N'usuario.usuario', N'Cambio_password_obligatorio', N'cambio_contrasena_obligatorio'),
    (N'usuario.permiso', N'PermisoID', N'id'),
    (N'usuario.permiso', N'Nombre', N'nombre'),
    (N'usuario.permiso', N'Descripcion', N'descripcion'),
    (N'usuario.usuario_permiso', N'UserID', N'usuario_id'),
    (N'usuario.usuario_permiso', N'PermisoID', N'permiso_id'),
    (N'usuario.restablecimiento_contrasena', N'Id', N'id'),
    (N'usuario.restablecimiento_contrasena', N'UserId', N'usuario_id'),
    (N'usuario.restablecimiento_contrasena', N'Token', N'huella_token'),
    (N'usuario.restablecimiento_contrasena', N'Expiration', N'vence'),
    (N'usuario.restablecimiento_contrasena', N'Used', N'usado'),
    (N'usuario.tutorial', N'FileName', N'nombre_archivo'),
    (N'usuario.tutorial', N'FilePath', N'ruta_archivo'),
    (N'usuario.tutorial', N'Fecha_subida', N'fecha_subida'),
    (N'usuario.tutorial', N'Titulo', N'titulo');

DECLARE @tabla nvarchar(128), @anterior sysname, @nueva sysname, @objeto nvarchar(400);
DECLARE renombrar CURSOR LOCAL FAST_FORWARD FOR SELECT tabla, anterior, nueva FROM #columnas;
OPEN renombrar;
FETCH NEXT FROM renombrar INTO @tabla, @anterior, @nueva;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF COL_LENGTH(@tabla, @anterior) IS NULL
        THROW 51083, 'Falta una columna esperada; revise el esquema antes de migrar.', 1;
    -- Mayúsculas distintas con la misma letra (Id -> id): sp_rename no lo detecta como
    -- cambio en una intercalación que no distingue mayúsculas, así que se pasa por un
    -- nombre intermedio.
    SET @objeto = @tabla + N'.' + QUOTENAME(@anterior);
    IF LOWER(@anterior) = LOWER(@nueva)
    BEGIN
        EXEC sp_rename @objeto, N'columna_en_renombre', N'COLUMN';
        SET @objeto = @tabla + N'.columna_en_renombre';
    END;
    EXEC sp_rename @objeto, @nueva, N'COLUMN';
    FETCH NEXT FROM renombrar INTO @tabla, @anterior, @nueva;
END;
CLOSE renombrar;
DEALLOCATE renombrar;

-- La auditoría de correcciones nombra la tabla y el campo que cambió: se traducen
-- a los nombres nuevos para que el historial y los registros nuevos coincidan.
CREATE TABLE #traduccion (tabla_anterior nvarchar(100), tabla_nueva nvarchar(100));
INSERT INTO #traduccion VALUES
    (N'table_damage_to_fleet', N'flota.caso'),
    (N'table_info_oper', N'proceso.gestion_operaciones'),
    (N'table_info_mtto', N'proceso.gestion_mantenimiento'),
    (N'table_info_svial', N'proceso.gestion_seguridad_vial'),
    (N'table_info_labora', N'proceso.cierre_laboral'),
    (N'table_info_laboral_mult', N'proceso.seguimiento_laboral');

-- Va como SQL dinámico porque las columnas nuevas no existen cuando se compila el lote.
EXEC (N'
    UPDATE c
    SET campo_modificado = col.nueva
    FROM proceso.correccion AS c
    INNER JOIN #traduccion AS t ON t.tabla_anterior = c.tabla_afectada
    INNER JOIN #columnas AS col ON col.tabla = t.tabla_nueva AND col.anterior = c.campo_modificado;

    UPDATE c
    SET tabla_afectada = t.tabla_nueva
    FROM proceso.correccion AS c
    INNER JOIN #traduccion AS t ON t.tabla_anterior = c.tabla_afectada;');

DROP TABLE #traduccion;
DROP TABLE #columnas;
