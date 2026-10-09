-- Tabla del módulo de Tutoriales. Reemplaza el script suelto
-- agregar_titulo_table_tutoriales.sql, que exigía que la tabla ya existiera.
IF OBJECT_ID(N'dbo.table_tutoriales', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.table_tutoriales (
        id int IDENTITY(1,1) NOT NULL CONSTRAINT PK_table_tutoriales PRIMARY KEY,
        FileName nvarchar(max) NULL,
        FilePath nvarchar(max) NULL,
        Fecha_subida datetime2 NULL,
        Titulo nvarchar(200) NULL
    );
END
ELSE
BEGIN
    IF COL_LENGTH(N'dbo.table_tutoriales', N'Titulo') IS NULL
        ALTER TABLE dbo.table_tutoriales ADD Titulo nvarchar(200) NULL;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.table_tutoriales')
          AND c.name = N'Titulo'
          AND TYPE_NAME(c.user_type_id) = N'nvarchar'
          AND c.max_length >= 400
    )
        THROW 51041, 'dbo.table_tutoriales.Titulo debe ser NVARCHAR(200) o mayor.', 1;

    IF COL_LENGTH(N'dbo.table_tutoriales', N'id') IS NULL
       OR COL_LENGTH(N'dbo.table_tutoriales', N'FileName') IS NULL
       OR COL_LENGTH(N'dbo.table_tutoriales', N'FilePath') IS NULL
       OR COL_LENGTH(N'dbo.table_tutoriales', N'Fecha_subida') IS NULL
        THROW 51042, 'dbo.table_tutoriales no tiene las columnas id, FileName, FilePath y Fecha_subida.', 1;
END;
