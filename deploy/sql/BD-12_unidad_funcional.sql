-- Para el esquema con flota.table_Moviles y usuario.Table_usuarios.
-- Requiere las conversiones a tinyint y el renombre a Alcance_UF.
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF NOT EXISTS (
        SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID(N'usuario.Table_usuarios', N'U')
          AND name = N'Alcance_UF'
          AND ((TYPE_NAME(user_type_id) = N'varchar' AND max_length = 20)
            OR (TYPE_NAME(user_type_id) = N'nvarchar' AND max_length = 40))
    )
        THROW 51120, 'Se requiere usuario.Table_usuarios.Alcance_UF varchar(20) o nvarchar(20).', 1;

    IF SCHEMA_ID(N'catalogo') IS NULL
        EXEC(N'CREATE SCHEMA catalogo');

    IF OBJECT_ID(N'catalogo.unidad_funcional', N'U') IS NULL
        CREATE TABLE catalogo.unidad_funcional (
            id tinyint NOT NULL CONSTRAINT PK_unidad_funcional PRIMARY KEY,
            prefijo_movil varchar(5) NOT NULL CONSTRAINT UQ_unidad_funcional_prefijo_movil UNIQUE
        );

    IF COL_LENGTH(N'catalogo.unidad_funcional', N'nombre') IS NULL
        ALTER TABLE catalogo.unidad_funcional ADD nombre varchar(40) NULL;

    EXEC sys.sp_executesql N'
        UPDATE catalogo.unidad_funcional SET nombre = ''Unidad Funcional 10'' WHERE id = 10;
        IF @@ROWCOUNT = 0
            INSERT INTO catalogo.unidad_funcional (id, prefijo_movil, nombre)
            VALUES (10, ''Z32-'', ''Unidad Funcional 10'');
        UPDATE catalogo.unidad_funcional SET nombre = ''Unidad Funcional 16'' WHERE id = 16;
        IF @@ROWCOUNT = 0
            INSERT INTO catalogo.unidad_funcional (id, prefijo_movil, nombre)
            VALUES (16, ''Z34-'', ''Unidad Funcional 16'');
        ALTER TABLE catalogo.unidad_funcional ALTER COLUMN nombre varchar(40) NOT NULL;
    ';

    DECLARE @tablas table (tabla nvarchar(128), fk sysname);
    INSERT INTO @tablas VALUES
        (N'flota.table_Moviles', N'FK_table_Moviles_unidad_funcional'),
        (N'flota.table_damage_to_fleet', N'FK_table_damage_to_fleet_unidad_funcional'),
        (N'proceso.table_intervenciones', N'FK_table_intervenciones_unidad_funcional');

    DECLARE @tabla nvarchar(128), @fk sysname, @sql nvarchar(max), @mensaje nvarchar(2048);
    WHILE EXISTS (SELECT 1 FROM @tablas)
    BEGIN
        SELECT TOP (1) @tabla = tabla, @fk = fk FROM @tablas ORDER BY tabla;

        IF NOT EXISTS (
            SELECT 1 FROM sys.columns
            WHERE object_id = OBJECT_ID(@tabla, N'U') AND name = N'UF'
              AND TYPE_NAME(user_type_id) = N'tinyint'
        )
        BEGIN
            SET @mensaje = N'Se requiere ' + @tabla + N'.UF tinyint.';
            THROW 51121, @mensaje, 1;
        END;

        IF NOT EXISTS (
            SELECT 1 FROM sys.foreign_keys
            WHERE parent_object_id = OBJECT_ID(@tabla) AND name = @fk
        )
        BEGIN
            SET @sql = N'ALTER TABLE ' + @tabla + N' WITH CHECK ADD CONSTRAINT ' + QUOTENAME(@fk)
                + N' FOREIGN KEY (UF) REFERENCES catalogo.unidad_funcional(id);';
            EXEC sys.sp_executesql @sql;
        END;

        SET @sql = N'ALTER TABLE ' + @tabla + N' WITH CHECK CHECK CONSTRAINT ' + QUOTENAME(@fk) + N';';
        EXEC sys.sp_executesql @sql;
        DELETE FROM @tablas WHERE tabla = @tabla;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
