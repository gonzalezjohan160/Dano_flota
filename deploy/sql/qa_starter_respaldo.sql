-- DBA: ejecutar en la instancia y base acordadas durante el corte.
-- Usar una ruta nueva en el almacenamiento protegido de SQL Server.
SET NOCOUNT ON;
DECLARE @servidor_esperado sysname = NULL;
DECLARE @base_esperada sysname = NULL;
DECLARE @archivo nvarchar(4000) = NULL;

IF @servidor_esperado IS NULL OR @base_esperada IS NULL OR NULLIF(@archivo, N'') IS NULL
    THROW 52200, 'Complete los tres parámetros del respaldo.', 1;

IF ISNULL(CONVERT(sysname, SERVERPROPERTY('ServerName')), N'') <> @servidor_esperado
   OR DB_NAME() <> @base_esperada OR DB_ID() <= 4
    THROW 52201, 'La conexión no corresponde a la base de la aplicación indicada.', 1;

DECLARE @existe int;
EXEC master.dbo.xp_fileexist @archivo, @existe OUTPUT;
IF @existe <> 0
    THROW 52202, 'El archivo de respaldo ya existe. Use una ruta nueva.', 1;

BEGIN TRY
    BACKUP DATABASE @base_esperada TO DISK = @archivo
        WITH COPY_ONLY, CHECKSUM, NOINIT, STATS = 10;
    RESTORE VERIFYONLY FROM DISK = @archivo WITH FILE = 1, CHECKSUM;
END TRY
BEGIN CATCH
    THROW;
END CATCH;
