-- Auditoría de base de datos (7-10-26): limpieza de datos que impedirían crear
-- las reglas de las migraciones 007 a 013. Parte de la estructura con esquemas
-- flota, proceso y usuario (5-nov-2026) y usa sus nombres de ese momento.
--
-- Decisiones de negocio aprobadas:
--   * Intervenciones de prueba (UF 'PRUEBA'): se borran con sus adjuntos.
--   * Adjuntos duplicados (mismo archivo dos veces en el mismo caso): se conserva
--     el primero. El archivo físico no se toca.
--   * Centro «SAN ÁNDRES» (tilde mal puesta): se corrige a «SAN ANDRÉS».
--   * S. Vial con dos gestiones para un caso: se conserva la más reciente y la
--     descartada se copia completa a la auditoría de correcciones.
--   * Los casos borrados físicamente antes del borrado lógico no se recuperan.
IF OBJECT_ID(N'flota.table_damage_to_fleet', N'U') IS NULL
   OR OBJECT_ID(N'proceso.table_info_svial', N'U') IS NULL
   OR OBJECT_ID(N'usuario.Table_usuarios', N'U') IS NULL
    THROW 51061, 'La base no tiene la estructura esperada (esquemas flota, proceso y usuario con los nombres del 5-nov-2026).', 1;

-- Gestiones duplicadas sin criterio de negocio: se detiene para depurarlas a mano.
DECLARE @duplicados nvarchar(2048);
SELECT @duplicados = STRING_AGG(CONVERT(nvarchar(200), detalle), N', ')
FROM (
    SELECT N'Operaciones caso ' + CONVERT(nvarchar(20), Id_damage) AS detalle
    FROM proceso.table_info_oper GROUP BY Id_damage HAVING COUNT(*) > 1
    UNION ALL
    SELECT N'Mantenimiento caso ' + CONVERT(nvarchar(20), Id_damage)
    FROM proceso.table_info_mtto GROUP BY Id_damage HAVING COUNT(*) > 1
    UNION ALL
    SELECT N'RRLL caso ' + CONVERT(nvarchar(20), Id_damage)
    FROM proceso.table_info_labora GROUP BY Id_damage HAVING COUNT(*) > 1
) AS d;
IF @duplicados IS NOT NULL
BEGIN
    SET @duplicados = LEFT(N'Gestiones duplicadas sin criterio de depuración: ' + @duplicados
        + N'. Defina con negocio qué fila conservar, depúrelas y vuelva a ejecutar la migración.', 2047);
    THROW 51062, @duplicados, 1;
END;

-- S. Vial duplicada: auditoría de la fila descartada y luego se borra.
WITH ordenadas AS (
    SELECT s.*, ROW_NUMBER() OVER (
        PARTITION BY s.Id_damage ORDER BY s.Fecha_registro DESC, s.Id DESC
    ) AS orden
    FROM proceso.table_info_svial AS s
)
INSERT INTO proceso.table_auditoria_correcciones
    (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
     Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
SELECT o.Id_damage, N'proceso.gestion_seguridad_vial', N'(fila completa)',
       (SELECT o.Id, o.Id_damage, o.Observaciones_svial, o.Usuario_registro_svial,
               o.Fecha_registro, o.valor_conciliado_terceros, o.conciliado_a_favor, o.estado_svial
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
       NULL, NULL, GETDATE(),
       N'Auditoría de base de datos: gestión de S. Vial duplicada; se conserva la más reciente.'
FROM ordenadas AS o
WHERE o.orden > 1;

WITH ordenadas AS (
    SELECT ROW_NUMBER() OVER (
        PARTITION BY Id_damage ORDER BY Fecha_registro DESC, Id DESC
    ) AS orden
    FROM proceso.table_info_svial
)
DELETE FROM ordenadas WHERE orden > 1;

-- Intervenciones de prueba y sus adjuntos.
DELETE f
FROM proceso.table_intervenciones_files AS f
INNER JOIN proceso.table_intervenciones AS i ON i.ID = f.RepairId
WHERE i.UF = 'PRUEBA';

DELETE FROM proceso.table_intervenciones WHERE UF = 'PRUEBA';

-- Adjuntos duplicados en el mismo caso: se conserva el de menor Id.
WITH repetidos AS (
    SELECT ROW_NUMBER() OVER (PARTITION BY Id_damage, FilePath ORDER BY Id) AS orden
    FROM flota.table_damage_files
)
DELETE FROM repetidos WHERE orden > 1;

-- Textos guardados como 'NULL' o vacíos donde la aplicación quiso decir «sin dato».
UPDATE proceso.table_info_oper SET conciliacion = NULL WHERE conciliacion IN ('NULL', '');
UPDATE proceso.table_info_oper SET rev_error = NULL WHERE rev_error = '';
UPDATE proceso.table_info_oper SET responsabilidad_operador = NULL WHERE responsabilidad_operador = '';
UPDATE proceso.table_info_mtto SET dano_adicional = NULL WHERE dano_adicional = '';
UPDATE proceso.table_info_svial SET conciliado_a_favor = NULL WHERE conciliado_a_favor = '';
UPDATE proceso.table_info_labora SET Tipo_cerrado = NULL WHERE LTRIM(RTRIM(Tipo_cerrado)) = '';
UPDATE proceso.table_info_laboral_mult SET Pendiente_proceso = NULL WHERE LTRIM(RTRIM(Pendiente_proceso)) = '';

-- Espacios sobrantes al inicio o al final (agrupaban mal los reportes).
UPDATE flota.table_damage_to_fleet
SET Parte_afectada = NULLIF(LTRIM(RTRIM(Parte_afectada)), '')
WHERE DATALENGTH(Parte_afectada) <> DATALENGTH(LTRIM(RTRIM(Parte_afectada)));

UPDATE flota.table_damage_to_fleet
SET Ruta = NULLIF(LTRIM(RTRIM(Ruta)), ''),
    Area = NULLIF(LTRIM(RTRIM(Area)), ''),
    Dano_ocasionado = NULLIF(LTRIM(RTRIM(Dano_ocasionado)), ''),
    Zona_dano = NULLIF(LTRIM(RTRIM(Zona_dano)), ''),
    Centro_operaciones = NULLIF(LTRIM(RTRIM(Centro_operaciones)), '')
WHERE DATALENGTH(ISNULL(Ruta, '')) <> DATALENGTH(LTRIM(RTRIM(ISNULL(Ruta, ''))))
   OR DATALENGTH(ISNULL(Area, '')) <> DATALENGTH(LTRIM(RTRIM(ISNULL(Area, ''))))
   OR DATALENGTH(ISNULL(Dano_ocasionado, '')) <> DATALENGTH(LTRIM(RTRIM(ISNULL(Dano_ocasionado, ''))))
   OR DATALENGTH(ISNULL(Zona_dano, '')) <> DATALENGTH(LTRIM(RTRIM(ISNULL(Zona_dano, ''))))
   OR DATALENGTH(ISNULL(Centro_operaciones, '')) <> DATALENGTH(LTRIM(RTRIM(ISNULL(Centro_operaciones, ''))))
   OR Ruta = '' OR Area = '' OR Dano_ocasionado = '' OR Zona_dano = '' OR Centro_operaciones = '';

-- Centro de operaciones con la tilde mal puesta.
UPDATE flota.table_damage_to_fleet
SET Centro_operaciones = 'SAN ANDRÉS'
WHERE Centro_operaciones IN ('SAN ÁNDRES', 'SAN ANDRES');

-- Enlaces de recuperación de contraseña vencidos, usados o guardados en claro
-- (los anteriores a la huella SHA-256 miden 43 caracteres): ya no sirven.
DELETE FROM usuario.Table_password_reset
WHERE Expiration < GETDATE() OR ISNULL(Used, 0) = 1 OR LEN(Token) <> 64;
