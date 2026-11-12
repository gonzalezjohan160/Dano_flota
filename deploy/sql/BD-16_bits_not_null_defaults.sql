-- BD-16 autorizado: BIT NOT NULL y DEFAULT 0, excepto Activo DEFAULT 1.
-- Se conservan nombres y valores 0/1 existentes. Solo NULL se reemplaza.
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF DB_NAME() <> N'damage_to_fleet'
    THROW 51700, 'Seleccione damage_to_fleet antes de aplicar BD-16.', 1;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @bits TABLE (orden int PRIMARY KEY, esquema sysname, tabla sysname, columna sysname, defecto bit);
    INSERT INTO @bits VALUES
        (1, N'flota', N'table_damage_to_fleet', N'estado_caso', 0),
        (2, N'flota', N'table_damage_to_fleet', N'eliminado', 0),
        (3, N'proceso', N'table_info_mtto', N'estado_mtto', 0),
        (4, N'proceso', N'table_info_oper', N'estado_oper', 0),
        (5, N'proceso', N'table_info_svial', N'estado_svial', 0),
        (6, N'usuario', N'Table_password_reset', N'Used', 0),
        (7, N'usuario', N'Table_usuarios', N'Cambio_password_obligatorio', 0),
        (8, N'usuario', N'Table_usuarios', N'Activo', 1);

    DECLARE @orden int = 1, @esquema sysname, @tabla sysname, @columna sysname,
            @defecto bit, @objeto int, @tipo int, @nullable bit,
            @default_nombre sysname, @definicion nvarchar(max), @nombre nvarchar(520),
            @sql nvarchar(max), @mensaje nvarchar(2048), @nulos bigint;
    WHILE @orden <= 8
    BEGIN
        SELECT @esquema=esquema, @tabla=tabla, @columna=columna, @defecto=defecto
        FROM @bits WHERE orden=@orden;
        SET @nombre=QUOTENAME(@esquema)+N'.'+QUOTENAME(@tabla);
        SET @objeto=OBJECT_ID(@nombre,N'U');
        SET @tipo=NULL;
        SET @default_nombre=NULL;
        SET @definicion=NULL;
        SELECT @tipo=c.system_type_id, @nullable=c.is_nullable,
               @default_nombre=dc.name, @definicion=dc.definition
        FROM sys.columns c
        LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id
        WHERE c.object_id=@objeto AND c.name=@columna;
        IF @tipo IS NULL OR @tipo<>104
        BEGIN
            SET @mensaje=N'Se esperaba una columna BIT: '+@nombre+N'.'+@columna;
            THROW 51701,@mensaje,1;
        END;

        -- La limpieza y el ALTER se realizan bajo el mismo bloqueo/transaccion.
        IF @nullable=1
        BEGIN
            SET @sql=N'SELECT @n=COUNT_BIG(*) FROM '+@nombre+N' WITH (TABLOCKX,HOLDLOCK)'
                    +N' WHERE '+QUOTENAME(@columna)+N' IS NULL;';
            EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT',@n=@nulos OUTPUT;
            IF @nulos>0
            BEGIN
                SET @sql=N'UPDATE '+@nombre+N' SET '
                        +QUOTENAME(@columna)+N'='+CONVERT(nvarchar(1),@defecto)
                        +N' WHERE '+QUOTENAME(@columna)+N' IS NULL;';
                EXEC sys.sp_executesql @sql;
            END;
            SET @sql=N'ALTER TABLE '+@nombre+N' ALTER COLUMN '+QUOTENAME(@columna)+N' bit NOT NULL;';
            EXEC sys.sp_executesql @sql;
        END;

        IF @definicion IS NOT NULL
            SET @definicion=REPLACE(REPLACE(REPLACE(@definicion,N'(',N''),N')',N''),N' ',N'');
        IF @definicion IS NULL OR @definicion<>CONVERT(nvarchar(1),@defecto)
        BEGIN
            IF @default_nombre IS NOT NULL
            BEGIN
                SET @sql=N'ALTER TABLE '+@nombre+N' DROP CONSTRAINT '+QUOTENAME(@default_nombre)+N';';
                EXEC sys.sp_executesql @sql;
            END;
            SET @default_nombre=N'DF_BD16_'+@tabla+N'_'+@columna;
            SET @sql=N'ALTER TABLE '+@nombre+N' ADD CONSTRAINT '+QUOTENAME(@default_nombre)
                    +N' DEFAULT ('+CONVERT(nvarchar(1),@defecto)+N') FOR '+QUOTENAME(@columna)+N';';
            EXEC sys.sp_executesql @sql;
        END;
        SET @orden+=1;
    END;
    COMMIT TRANSACTION;
    PRINT N'BD-16 aplicado: ocho BIT NOT NULL; DEFAULT 0 salvo Activo DEFAULT 1.';
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
