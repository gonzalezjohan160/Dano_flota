-- Autorizado: BIGINT y CHECK >= 0. No cambia los ceros ni los NULL existentes.
-- Se conservan nombres de tablas/columnas y nulabilidad. Aplicacion atomica.
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF DB_NAME() <> N'damage_to_fleet'
    THROW 51600, 'Seleccione damage_to_fleet antes de aplicar la correccion de montos.', 1;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @montos TABLE (orden int PRIMARY KEY, tabla sysname, columna sysname, permite_null bit);
    INSERT INTO @montos VALUES
        (1, N'table_info_mtto', N'Costo', 0),
        (2, N'table_info_oper', N'costo_oper', 1),
        (3, N'table_info_labora', N'Valor_conciliado', 1),
        (4, N'table_info_svial', N'valor_conciliado_terceros', 1),
        (5, N'table_intervenciones', N'Costo_intervencion', 1);

    DECLARE @orden int = 1, @tabla sysname, @columna sysname, @permite_null bit,
            @objeto int, @tipo sysname, @nulabilidad bit, @sql nvarchar(max),
            @negativos bigint, @restriccion sysname, @definicion nvarchar(max),
            @mensaje nvarchar(2048);
    WHILE @orden <= 5
    BEGIN
        SELECT @tabla = tabla, @columna = columna, @permite_null = permite_null
        FROM @montos WHERE orden = @orden;
        SET @objeto = OBJECT_ID(N'proceso.' + @tabla, N'U');
        SET @tipo = NULL;
        SELECT @tipo = TYPE_NAME(system_type_id), @nulabilidad = is_nullable
        FROM sys.columns WHERE object_id = @objeto AND name = @columna;
        IF @tipo IS NULL OR @tipo NOT IN (N'int', N'bigint') OR @nulabilidad <> @permite_null
        BEGIN
            SET @mensaje = N'Estructura inesperada en proceso.' + @tabla + N'.' + @columna
                         + N'. No se cambiaron datos; revise el esquema.';
            THROW 51601, @mensaje, 1;
        END;

        SET @sql = N'SELECT @n=COUNT_BIG(*) FROM [proceso].' + QUOTENAME(@tabla)
                 + N' WITH (TABLOCKX,HOLDLOCK) WHERE ' + QUOTENAME(@columna) + N'<0;';
        EXEC sys.sp_executesql @sql, N'@n bigint OUTPUT', @n = @negativos OUTPUT;
        IF @negativos > 0
        BEGIN
            SET @mensaje = N'Hay montos negativos en proceso.' + @tabla + N'.' + @columna
                         + N'. Se requiere revision; no se corrigieron registros automaticamente.';
            THROW 51602, @mensaje, 1;
        END;

        IF @tipo <> N'bigint'
        BEGIN
            SET @sql = N'ALTER TABLE [proceso].' + QUOTENAME(@tabla)
                     + N' ALTER COLUMN ' + QUOTENAME(@columna) + N' bigint '
                     + CASE WHEN @permite_null = 1 THEN N'NULL;' ELSE N'NOT NULL;' END;
            EXEC sys.sp_executesql @sql;
        END;

        SET @restriccion = N'CK_BD_' + @tabla + N'_' + @columna + N'_no_negativo';
        SET @definicion = NULL;
        SELECT @definicion = definition FROM sys.check_constraints
        WHERE parent_object_id = @objeto AND name = @restriccion;
        IF @definicion IS NOT NULL
        BEGIN
            SET @definicion = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                @definicion, N'[', N''), N']', N''), N'(', N''), N')', N''), N' ', N'');
            IF LOWER(@definicion) <> LOWER(@columna + N'>=0')
                THROW 51603, 'Existe un CHECK con el nombre previsto pero otra regla; requiere revision.', 1;
        END
        ELSE
        BEGIN
            SET @sql = N'ALTER TABLE [proceso].' + QUOTENAME(@tabla)
                     + N' WITH CHECK ADD CONSTRAINT ' + QUOTENAME(@restriccion)
                     + N' CHECK (' + QUOTENAME(@columna) + N'>=0);';
            EXEC sys.sp_executesql @sql;
        END;
        SET @sql = N'ALTER TABLE [proceso].' + QUOTENAME(@tabla)
                 + N' WITH CHECK CHECK CONSTRAINT ' + QUOTENAME(@restriccion) + N';';
        EXEC sys.sp_executesql @sql;
        SET @orden += 1;
    END;
    COMMIT TRANSACTION;
    PRINT N'Montos: las cinco columnas son BIGINT con CHECK >= 0 habilitado y validado.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
