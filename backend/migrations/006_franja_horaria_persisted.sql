-- BD-18: franja_horaria pasa a ser PERSISTED (se guarda en la fila en vez de
-- calcularse en cada consulta, y así se puede indexar si algún día se filtra por ella).
--
-- Decisión de negocio: la franja sigue midiendo la hora de DIGITACIÓN (Fecha_registro).
--
-- La fórmula original comparaba CONVERT(TIME, ...) con textos como '04:00:00'; esa
-- conversión de texto es no determinista para SQL Server y no admite PERSISTED.
-- DATEPART(HOUR, ...) da exactamente las mismas franjas (verificado minuto a minuto,
-- bordes incluidos y NULL -> '22:00-04:00') y sí es determinista.
--
-- Una columna calculada no se puede modificar: se elimina y se vuelve a crear.
-- No guarda datos propios (se calcula desde Fecha_registro), así que no se pierde nada.
IF OBJECT_ID(N'dbo.table_damage_to_fleet', N'U') IS NULL
    THROW 51061, 'No existe la tabla dbo.table_damage_to_fleet; ejecute primero el script de esquema base.', 1;

IF COL_LENGTH(N'dbo.table_damage_to_fleet', N'Fecha_registro') IS NULL
    THROW 51062, 'No existe la columna dbo.table_damage_to_fleet.Fecha_registro.', 1;

DECLARE @columna_id int = COLUMNPROPERTY(OBJECT_ID(N'dbo.table_damage_to_fleet'), N'franja_horaria', 'ColumnId');

IF @columna_id IS NOT NULL
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM sys.computed_columns
        WHERE object_id = OBJECT_ID(N'dbo.table_damage_to_fleet') AND column_id = @columna_id
    )
        THROW 51063, 'dbo.table_damage_to_fleet.franja_horaria existe pero no es una columna calculada; revise el esquema antes de migrar.', 1;

    -- Índices o estadísticas creados a mano sobre la columna impedirían eliminarla.
    IF EXISTS (
        SELECT 1 FROM sys.index_columns
        WHERE object_id = OBJECT_ID(N'dbo.table_damage_to_fleet') AND column_id = @columna_id
    ) OR EXISTS (
        SELECT 1 FROM sys.stats_columns AS sc
        INNER JOIN sys.stats AS st ON st.object_id = sc.object_id AND st.stats_id = sc.stats_id
        WHERE sc.object_id = OBJECT_ID(N'dbo.table_damage_to_fleet') AND sc.column_id = @columna_id
          AND st.auto_created = 0
    )
        THROW 51064, 'Hay índices o estadísticas sobre franja_horaria; elimínelos antes de migrar y vuelva a crearlos después.', 1;

    ALTER TABLE dbo.table_damage_to_fleet DROP COLUMN franja_horaria;
END;

ALTER TABLE dbo.table_damage_to_fleet ADD franja_horaria AS (
    CONVERT(varchar(11), CASE
        WHEN DATEPART(HOUR, Fecha_registro) BETWEEN 4 AND 9 THEN '04:00-10:00'
        WHEN DATEPART(HOUR, Fecha_registro) BETWEEN 10 AND 15 THEN '10:00-16:00'
        WHEN DATEPART(HOUR, Fecha_registro) BETWEEN 16 AND 21 THEN '16:00-22:00'
        ELSE '22:00-04:00'
    END)
) PERSISTED;
