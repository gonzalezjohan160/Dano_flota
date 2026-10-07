USE [damage_to_fleet];
GO

IF OBJECT_ID(N'dbo.table_tutoriales', N'U') IS NULL
BEGIN
    THROW 50001, 'No existe dbo.table_tutoriales; no se creó ni reemplazó ninguna tabla.', 1;
END;
GO

IF COL_LENGTH(N'dbo.table_tutoriales', N'Titulo') IS NULL
BEGIN
    ALTER TABLE dbo.table_tutoriales
        ADD Titulo NVARCHAR(200) NULL;
END;
GO
