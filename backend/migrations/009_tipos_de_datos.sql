-- Auditoría de base de datos (7-10-26), sección 5.2 (tipos de datos) y 5.3.
--
--   * Fechas de registro, subida y modificación: datetime2(0) NOT NULL (hasta el
--     segundo). Las milésimas actuales se redondean al segundo más cercano.
--   * Montos: bigint (pesos enteros); la regla de no negativos va en la 010.
--   * Estados sí/no (cerrado, eliminado, completada, activo, usado...): bit NOT NULL;
--     sus valores predeterminados se crean en la 010.
--   * Quién registra o modifica: nvarchar(50), el mismo tipo de
--     usuario.nombre_usuario, para unirlos sin conversiones y crear la clave foránea.
--   * Huella del token de recuperación: char(64), lo que mide un SHA-256 en hexadecimal.
--   * Tutoriales: nvarchar(255) y nvarchar(500) en lugar de nvarchar(max).
--   * franja_horaria y modulo vuelven como columnas calculadas PERSISTED (BD-18).
--     Decisión de negocio: la franja mide la hora de DIGITACIÓN (fecha_registro).
--
-- Para cambiar el tipo de una columna no puede haber restricciones sobre ella: se
-- quitan todas las de los esquemas flota, proceso y usuario (salvo las claves
-- primarias) y la migración 010 las vuelve a crear con nombres legibles.
IF OBJECT_ID(N'flota.caso', N'U') IS NULL
    THROW 51091, 'Falta flota.caso; aplique primero la migración 008.', 1;

-- Valores que no cabrían en el tipo nuevo: se detiene y los lista.
DECLARE @problemas nvarchar(2048);
SELECT @problemas = STRING_AGG(CONVERT(nvarchar(200), detalle), N', ')
FROM (
    SELECT N'usuario de más de 50 caracteres en ' + origen AS detalle
    FROM (
        SELECT N'caso' AS origen, registrado_por AS valor FROM flota.caso
        UNION ALL SELECT N'gestion_operaciones', registrado_por FROM proceso.gestion_operaciones
        UNION ALL SELECT N'gestion_mantenimiento', registrado_por FROM proceso.gestion_mantenimiento
        UNION ALL SELECT N'gestion_seguridad_vial', registrado_por FROM proceso.gestion_seguridad_vial
        UNION ALL SELECT N'cierre_laboral', registrado_por FROM proceso.cierre_laboral
        UNION ALL SELECT N'seguimiento_laboral', registrado_por FROM proceso.seguimiento_laboral
        UNION ALL SELECT N'correccion', modificado_por FROM proceso.correccion
        UNION ALL SELECT N'intervencion', registrado_por FROM proceso.intervencion
    ) AS u
    WHERE LEN(valor) > 50
    GROUP BY origen
    UNION ALL
    SELECT N'fecha vacía en ' + origen
    FROM (
        SELECT N'caso' AS origen FROM flota.caso WHERE fecha_registro IS NULL
        UNION ALL SELECT N'archivo_caso' FROM flota.archivo_caso WHERE fecha_subida IS NULL
        UNION ALL SELECT N'gestion_operaciones' FROM proceso.gestion_operaciones WHERE fecha_registro IS NULL
        UNION ALL SELECT N'gestion_mantenimiento' FROM proceso.gestion_mantenimiento WHERE fecha_registro IS NULL
        UNION ALL SELECT N'cierre_laboral' FROM proceso.cierre_laboral WHERE fecha_registro IS NULL
        UNION ALL SELECT N'seguimiento_laboral' FROM proceso.seguimiento_laboral WHERE fecha_registro IS NULL
        UNION ALL SELECT N'correccion' FROM proceso.correccion WHERE fecha_modificacion IS NULL
        UNION ALL SELECT N'usuario' FROM usuario.usuario WHERE fecha_creacion IS NULL
        UNION ALL SELECT N'tutorial' FROM usuario.tutorial WHERE fecha_subida IS NULL
    ) AS f
    GROUP BY origen
    UNION ALL
    SELECT N'dato obligatorio vacío en ' + origen
    FROM (
        SELECT N'operador.codigo' AS origen FROM flota.operador WHERE codigo IS NULL
        UNION ALL SELECT N'movil' FROM flota.movil
            WHERE numero IS NULL OR unidad_funcional_id IS NULL OR tipologia IS NULL OR unidad_funcional_id NOT BETWEEN 0 AND 255
        UNION ALL SELECT N'tutorial' FROM usuario.tutorial WHERE nombre_archivo IS NULL OR ruta_archivo IS NULL
            OR LEN(nombre_archivo) > 255 OR LEN(ruta_archivo) > 500
        UNION ALL SELECT N'restablecimiento_contrasena' FROM usuario.restablecimiento_contrasena WHERE LEN(huella_token) <> 64
    ) AS o
    GROUP BY origen
) AS p;
IF @problemas IS NOT NULL
BEGIN
    SET @problemas = LEFT(N'Datos que no caben en los tipos nuevos: ' + @problemas + N'. Corríjalos antes de migrar.', 2047);
    THROW 51092, @problemas, 1;
END;

-- Restricciones de los esquemas de la aplicación (no las claves primarias).
DECLARE @sql nvarchar(max) = N'';
SELECT @sql += N'ALTER TABLE ' + QUOTENAME(SCHEMA_NAME(t.schema_id)) + N'.' + QUOTENAME(t.name)
    + N' DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + NCHAR(10)
FROM sys.foreign_keys AS fk
INNER JOIN sys.tables AS t ON t.object_id = fk.parent_object_id
WHERE SCHEMA_NAME(t.schema_id) IN (N'flota', N'proceso', N'usuario');
EXEC sys.sp_executesql @sql;

SET @sql = N'';
SELECT @sql += N'ALTER TABLE ' + QUOTENAME(SCHEMA_NAME(t.schema_id)) + N'.' + QUOTENAME(t.name)
    + N' DROP CONSTRAINT ' + QUOTENAME(o.name) + N';' + NCHAR(10)
FROM sys.objects AS o
INNER JOIN sys.tables AS t ON t.object_id = o.parent_object_id
WHERE o.type IN ('D', 'C', 'UQ')
  AND SCHEMA_NAME(t.schema_id) IN (N'flota', N'proceso', N'usuario');
EXEC sys.sp_executesql @sql;

SET @sql = N'';
SELECT @sql += N'DROP INDEX ' + QUOTENAME(i.name) + N' ON '
    + QUOTENAME(SCHEMA_NAME(t.schema_id)) + N'.' + QUOTENAME(t.name) + N';' + NCHAR(10)
FROM sys.indexes AS i
INNER JOIN sys.tables AS t ON t.object_id = i.object_id
WHERE i.is_primary_key = 0 AND i.is_unique_constraint = 0 AND i.type > 0
  AND SCHEMA_NAME(t.schema_id) IN (N'flota', N'proceso', N'usuario');
EXEC sys.sp_executesql @sql;

-- --------------------------------------------------------------- flota ---
ALTER TABLE flota.caso ALTER COLUMN fecha_evento datetime2(0) NOT NULL;
ALTER TABLE flota.caso ALTER COLUMN fecha_registro datetime2(0) NOT NULL;
ALTER TABLE flota.caso ALTER COLUMN registrado_por nvarchar(50) NULL;
ALTER TABLE flota.caso ALTER COLUMN cerrado bit NOT NULL;
ALTER TABLE flota.caso ALTER COLUMN eliminado bit NOT NULL;
ALTER TABLE flota.archivo_caso ALTER COLUMN fecha_subida datetime2(0) NOT NULL;
ALTER TABLE flota.operador ALTER COLUMN codigo varchar(10) NOT NULL;
ALTER TABLE flota.movil ALTER COLUMN numero varchar(10) NOT NULL;
ALTER TABLE flota.movil ALTER COLUMN unidad_funcional_id tinyint NOT NULL;
ALTER TABLE flota.movil ALTER COLUMN tipologia varchar(20) NOT NULL;

-- ------------------------------------------------------------- proceso ---
ALTER TABLE proceso.gestion_operaciones ALTER COLUMN registrado_por nvarchar(50) NOT NULL;
ALTER TABLE proceso.gestion_operaciones ALTER COLUMN fecha_registro datetime2(0) NOT NULL;
ALTER TABLE proceso.gestion_operaciones ALTER COLUMN costo bigint NULL;
ALTER TABLE proceso.gestion_operaciones ALTER COLUMN completada bit NOT NULL;
ALTER TABLE proceso.gestion_mantenimiento ALTER COLUMN costo bigint NOT NULL;
ALTER TABLE proceso.gestion_mantenimiento ALTER COLUMN registrado_por nvarchar(50) NULL;
ALTER TABLE proceso.gestion_mantenimiento ALTER COLUMN fecha_registro datetime2(0) NOT NULL;
ALTER TABLE proceso.gestion_mantenimiento ALTER COLUMN completada bit NOT NULL;
ALTER TABLE proceso.gestion_seguridad_vial ALTER COLUMN registrado_por nvarchar(50) NOT NULL;
ALTER TABLE proceso.gestion_seguridad_vial ALTER COLUMN fecha_registro datetime2(0) NOT NULL;
ALTER TABLE proceso.gestion_seguridad_vial ALTER COLUMN valor_conciliado_terceros bigint NULL;
ALTER TABLE proceso.gestion_seguridad_vial ALTER COLUMN completada bit NOT NULL;
ALTER TABLE proceso.cierre_laboral ALTER COLUMN valor_conciliado bigint NULL;
ALTER TABLE proceso.cierre_laboral ALTER COLUMN registrado_por nvarchar(50) NOT NULL;
ALTER TABLE proceso.cierre_laboral ALTER COLUMN fecha_registro datetime2(0) NOT NULL;
ALTER TABLE proceso.seguimiento_laboral ALTER COLUMN registrado_por nvarchar(50) NULL;
ALTER TABLE proceso.seguimiento_laboral ALTER COLUMN fecha_registro datetime2(0) NOT NULL;
ALTER TABLE proceso.correccion ALTER COLUMN modificado_por nvarchar(50) NULL;
ALTER TABLE proceso.correccion ALTER COLUMN fecha_modificacion datetime2(0) NOT NULL;
ALTER TABLE proceso.intervencion ALTER COLUMN costo bigint NULL;
ALTER TABLE proceso.intervencion ALTER COLUMN registrado_por nvarchar(50) NOT NULL;
ALTER TABLE proceso.intervencion ALTER COLUMN fecha_registro datetime2(0) NOT NULL;
ALTER TABLE proceso.archivo_intervencion ALTER COLUMN fecha_subida datetime2(0) NOT NULL;

-- ------------------------------------------------------------- usuario ---
ALTER TABLE usuario.usuario ALTER COLUMN fecha_creacion datetime2(0) NOT NULL;
ALTER TABLE usuario.usuario ALTER COLUMN activo bit NOT NULL;
ALTER TABLE usuario.usuario ALTER COLUMN cambio_contrasena_obligatorio bit NOT NULL;
ALTER TABLE usuario.restablecimiento_contrasena ALTER COLUMN huella_token char(64) NOT NULL;
ALTER TABLE usuario.restablecimiento_contrasena ALTER COLUMN vence datetime2(0) NOT NULL;
ALTER TABLE usuario.restablecimiento_contrasena ALTER COLUMN usado bit NOT NULL;
ALTER TABLE usuario.tutorial ALTER COLUMN nombre_archivo nvarchar(255) NOT NULL;
ALTER TABLE usuario.tutorial ALTER COLUMN ruta_archivo nvarchar(500) NOT NULL;
ALTER TABLE usuario.tutorial ALTER COLUMN fecha_subida datetime2(0) NOT NULL;

-- ------------------------------------------------- columnas calculadas ---
ALTER TABLE flota.caso ADD franja_horaria AS (
    CONVERT(varchar(11), CASE
        WHEN DATEPART(HOUR, fecha_registro) BETWEEN 4 AND 9 THEN '04:00-10:00'
        WHEN DATEPART(HOUR, fecha_registro) BETWEEN 10 AND 15 THEN '10:00-16:00'
        WHEN DATEPART(HOUR, fecha_registro) BETWEEN 16 AND 21 THEN '16:00-22:00'
        ELSE '22:00-04:00'
    END)
) PERSISTED;

-- El módulo que subió el adjunto sale de su carpeta (Files_ppal, Files_mtto...).
ALTER TABLE flota.archivo_caso ADD modulo AS (
    CONVERT(varchar(14), CASE
        WHEN ruta_archivo LIKE N'%ppal%' THEN 'Operaciones'
        WHEN ruta_archivo LIKE N'%svial%' THEN 'Seguridad vial'
        WHEN ruta_archivo LIKE N'%mtto%' THEN 'Mantenimiento'
        WHEN ruta_archivo LIKE N'%laboral%' THEN 'Laboral'
        ELSE 'Sin clasificar'
    END)
) PERSISTED;
