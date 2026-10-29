-- Relaciones 1:1 entre el caso y cada gestión (Operaciones, Mantenimiento,
-- S. Vial y RRLL): la base garantiza una sola fila por caso con un índice UNIQUE.
--
-- Duplicados existentes:
--   * S. Vial: decisión de negocio, se conserva el registro más reciente de cada
--     caso (Fecha_registro y, si empatan, el Id mayor). Cada fila descartada se
--     copia completa a table_auditoria_correcciones antes de borrarla.
--   * Operaciones, Mantenimiento y RRLL: no hay criterio de negocio; si existen
--     duplicados la migración se detiene y los lista para depurarlos a mano.
IF OBJECT_ID(N'dbo.table_info_oper', N'U') IS NULL
   OR OBJECT_ID(N'dbo.table_info_mtto', N'U') IS NULL
   OR OBJECT_ID(N'dbo.table_info_svial', N'U') IS NULL
   OR OBJECT_ID(N'dbo.table_info_labora', N'U') IS NULL
   OR OBJECT_ID(N'dbo.table_auditoria_correcciones', N'U') IS NULL
    THROW 51071, 'Faltan tablas de gestión o de auditoría; ejecute primero el script de esquema base.', 1;

DECLARE @duplicados nvarchar(2048);

SELECT @duplicados = STRING_AGG(CONVERT(nvarchar(200), detalle), N', ')
FROM (
    SELECT N'Operaciones caso ' + CONVERT(nvarchar(20), Id_damage_to_fleet) AS detalle
    FROM dbo.table_info_oper GROUP BY Id_damage_to_fleet HAVING COUNT(*) > 1
    UNION ALL
    SELECT N'Mantenimiento caso ' + CONVERT(nvarchar(20), Id_damage_to_fleet)
    FROM dbo.table_info_mtto GROUP BY Id_damage_to_fleet HAVING COUNT(*) > 1
    UNION ALL
    SELECT N'RRLL caso ' + CONVERT(nvarchar(20), Id_damage_to_fleet)
    FROM dbo.table_info_labora GROUP BY Id_damage_to_fleet HAVING COUNT(*) > 1
) AS d;

IF @duplicados IS NOT NULL
BEGIN
    SET @duplicados = LEFT(N'Gestiones duplicadas sin criterio de depuración: ' + @duplicados
        + N'. Defina con negocio qué fila conservar, depúrelas y vuelva a ejecutar la migración.', 2047);
    THROW 51072, @duplicados, 1;
END;

-- S. Vial: auditoría de las filas que se descartan.
WITH ordenadas AS (
    SELECT s.*, ROW_NUMBER() OVER (
        PARTITION BY s.Id_damage_to_fleet ORDER BY s.Fecha_registro DESC, s.Id DESC
    ) AS orden
    FROM dbo.table_info_svial AS s
)
INSERT INTO dbo.table_auditoria_correcciones
    (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
     Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
SELECT o.Id_damage_to_fleet, N'table_info_svial', N'(fila completa)',
       (SELECT o.Id, o.Id_damage_to_fleet, o.Observaciones_svial, o.Usuario_registro_svial,
               o.Fecha_registro, o.valor_conciliado_terceros, o.conciliado_a_favor, o.estado_svial
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
       N'', N'migracion_007', GETDATE(),
       N'Depuración de gestión duplicada de S. Vial (relación 1:1): se conserva el registro más reciente por decisión de negocio.'
FROM ordenadas AS o
WHERE o.orden > 1;

-- S. Vial: se conserva solo el registro más reciente de cada caso.
WITH ordenadas AS (
    SELECT ROW_NUMBER() OVER (
        PARTITION BY Id_damage_to_fleet ORDER BY Fecha_registro DESC, Id DESC
    ) AS orden
    FROM dbo.table_info_svial
)
DELETE FROM ordenadas WHERE orden > 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_table_info_oper_caso' AND object_id = OBJECT_ID(N'dbo.table_info_oper'))
    CREATE UNIQUE INDEX UX_table_info_oper_caso ON dbo.table_info_oper (Id_damage_to_fleet);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_table_info_mtto_caso' AND object_id = OBJECT_ID(N'dbo.table_info_mtto'))
    CREATE UNIQUE INDEX UX_table_info_mtto_caso ON dbo.table_info_mtto (Id_damage_to_fleet);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_table_info_svial_caso' AND object_id = OBJECT_ID(N'dbo.table_info_svial'))
    CREATE UNIQUE INDEX UX_table_info_svial_caso ON dbo.table_info_svial (Id_damage_to_fleet);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_table_info_labora_caso' AND object_id = OBJECT_ID(N'dbo.table_info_labora'))
    CREATE UNIQUE INDEX UX_table_info_labora_caso ON dbo.table_info_labora (Id_damage_to_fleet);
