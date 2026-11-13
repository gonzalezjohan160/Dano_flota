-- DBA: ejecutar desde master en la instancia aislada de recuperación.
-- Antes de completar los MOVE, inspeccionar RESTORE FILELISTONLY.
SET NOCOUNT ON;
DECLARE @servidor_esperado sysname = NULL;
DECLARE @base_nueva sysname = NULL;
DECLARE @archivo nvarchar(4000) = NULL;
DECLARE @movimientos table (logico sysname PRIMARY KEY, fisico nvarchar(4000) NOT NULL);

-- Agregar una fila por cada archivo lógico del respaldo.
-- INSERT INTO @movimientos VALUES
--     (N'DatosLogicos', N'D:\Recuperacion\dano_corte.mdf'),
--     (N'LogLogico', N'D:\Recuperacion\dano_corte_log.ldf');

IF @servidor_esperado IS NULL OR NULLIF(@base_nueva, N'') IS NULL
   OR NULLIF(@archivo, N'') IS NULL OR NOT EXISTS (SELECT 1 FROM @movimientos)
    THROW 52210, 'Complete la instancia, la base nueva, el respaldo y los MOVE.', 1;

IF DB_NAME() <> N'master' OR
   ISNULL(CONVERT(sysname, SERVERPROPERTY('ServerName')), N'') <> @servidor_esperado
    THROW 52211, 'Conéctese a master de la instancia aislada indicada.', 1;

IF DB_ID(@base_nueva) IS NOT NULL
    THROW 52212, 'El nombre de la base de restauración ya existe.', 1;

IF EXISTS (SELECT fisico FROM @movimientos GROUP BY fisico HAVING COUNT(*) > 1)
    THROW 52213, 'Cada archivo lógico requiere una ruta física distinta.', 1;

DECLARE @movidas nvarchar(max);
SELECT @movidas = STRING_AGG(
    CONVERT(nvarchar(max), N'MOVE N''') + REPLACE(logico, N'''', N'''''') + N''' TO N''' +
    REPLACE(CONVERT(nvarchar(max), fisico), N'''', N'''''') + N'''', N', ')
FROM @movimientos;

DECLARE @verificar nvarchar(max) =
    N'RESTORE VERIFYONLY FROM DISK = @bak WITH FILE = 1, CHECKSUM, ' + @movidas;
DECLARE @restaurar nvarchar(max) =
    N'RESTORE DATABASE ' + QUOTENAME(@base_nueva) +
    N' FROM DISK = @bak WITH FILE = 1, CHECKSUM, RECOVERY, STATS = 10, ' + @movidas;
BEGIN TRY
    EXEC sys.sp_executesql @verificar, N'@bak nvarchar(4000)', @bak = @archivo;
    EXEC sys.sp_executesql @restaurar, N'@bak nvarchar(4000)', @bak = @archivo;
END TRY
BEGIN CATCH
    THROW;
END CATCH;
