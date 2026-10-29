-- PENDIENTE: no la ejecuta `manage_db.py migrate` mientras esté en esta carpeta.
-- Cuando se hayan corregido los casos con Fecha_evento > Fecha_registro, muévala a
-- backend/migrations/ (git mv) y despliegue: el migrate habitual la aplicará.
--
-- Fechas del caso (dbo.table_damage_to_fleet):
--   * Fecha_registro pasa de datetime NULL a datetime2(0) NOT NULL DEFAULT SYSDATETIME(),
--     el mismo tipo de Fecha_evento. datetime2(0) guarda hasta el segundo: las
--     milésimas actuales se redondean al segundo más cercano.
--   * CHECK: el evento no puede ser posterior a su registro.
-- Solo esta tabla se unifica (decisión del proyecto): es la única con una regla entre fechas.
--
-- Requisito: haber corregido antes los casos con Fecha_evento > Fecha_registro
-- (lo hace quien registró, con "Editar" de Operaciones). Si quedan, la migración
-- se detiene y los lista; no corrige fechas por su cuenta.
--
-- franja_horaria (columna calculada PERSISTED, migración 006) depende de
-- Fecha_registro, así que se elimina y se vuelve a crear con la misma fórmula.
IF OBJECT_ID(N'dbo.table_damage_to_fleet', N'U') IS NULL
    THROW 51081, 'No existe la tabla dbo.table_damage_to_fleet; ejecute primero el script de esquema base.', 1;

DECLARE @pendientes nvarchar(2048);

SELECT @pendientes = STRING_AGG(CONVERT(nvarchar(20), Id), N', ')
FROM dbo.table_damage_to_fleet
WHERE Fecha_evento > Fecha_registro;

IF @pendientes IS NOT NULL
BEGIN
    SET @pendientes = LEFT(N'Casos con Fecha_evento posterior a Fecha_registro: ' + @pendientes
        + N'. Corríjalos con "Editar" de Operaciones y vuelva a ejecutar la migración.', 2047);
    THROW 51082, @pendientes, 1;
END;

SELECT @pendientes = STRING_AGG(CONVERT(nvarchar(20), Id), N', ')
FROM dbo.table_damage_to_fleet
WHERE Fecha_registro IS NULL;

IF @pendientes IS NOT NULL
BEGIN
    SET @pendientes = LEFT(N'Casos sin Fecha_registro: ' + @pendientes
        + N'. Defina su fecha de registro y vuelva a ejecutar la migración.', 2047);
    THROW 51083, @pendientes, 1;
END;

-- El valor por defecto actual (getdate()) tiene un nombre generado por SQL Server.
DECLARE @default_registro sysname;
SELECT @default_registro = dc.name
FROM sys.default_constraints AS dc
INNER JOIN sys.columns AS c ON c.object_id = dc.parent_object_id AND c.column_id = dc.parent_column_id
WHERE dc.parent_object_id = OBJECT_ID(N'dbo.table_damage_to_fleet') AND c.name = N'Fecha_registro';

IF @default_registro IS NOT NULL
BEGIN
    DECLARE @quitar_default nvarchar(400) =
        N'ALTER TABLE dbo.table_damage_to_fleet DROP CONSTRAINT ' + QUOTENAME(@default_registro) + N';';
    EXEC sys.sp_executesql @quitar_default;
END;

IF COL_LENGTH(N'dbo.table_damage_to_fleet', N'franja_horaria') IS NOT NULL
    ALTER TABLE dbo.table_damage_to_fleet DROP COLUMN franja_horaria;

ALTER TABLE dbo.table_damage_to_fleet ALTER COLUMN Fecha_registro datetime2(0) NOT NULL;

ALTER TABLE dbo.table_damage_to_fleet ADD CONSTRAINT DF_table_damage_to_fleet_Fecha_registro
    DEFAULT (SYSDATETIME()) FOR Fecha_registro;

ALTER TABLE dbo.table_damage_to_fleet ADD franja_horaria AS (
    CONVERT(varchar(11), CASE
        WHEN DATEPART(HOUR, Fecha_registro) BETWEEN 4 AND 9 THEN '04:00-10:00'
        WHEN DATEPART(HOUR, Fecha_registro) BETWEEN 10 AND 15 THEN '10:00-16:00'
        WHEN DATEPART(HOUR, Fecha_registro) BETWEEN 16 AND 21 THEN '16:00-22:00'
        ELSE '22:00-04:00'
    END)
) PERSISTED;

ALTER TABLE dbo.table_damage_to_fleet WITH CHECK ADD CONSTRAINT CK_table_damage_to_fleet_evento_antes_registro
    CHECK (Fecha_evento <= Fecha_registro);
