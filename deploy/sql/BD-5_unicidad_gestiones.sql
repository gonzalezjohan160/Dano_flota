-- BD-5: como maximo una gestion de cada area por caso.
-- Base verificada: damage_to_fleet, nombres actuales sin renombrar tablas.
-- No elimina ni actualiza registros. No impone que todo caso tenga gestion.
-- Ejecutar solo con autorizacion. Los cuatro indices se crean atomicamente.
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_NAME() <> N'damage_to_fleet'
    THROW 51500, 'Seleccione la base damage_to_fleet antes de ejecutar BD-5.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @tablas TABLE (orden int PRIMARY KEY, nombre sysname);
    INSERT INTO @tablas VALUES
        (1, N'table_info_oper'), (2, N'table_info_mtto'),
        (3, N'table_info_svial'), (4, N'table_info_labora');

    DECLARE @orden int = 1, @tabla sysname, @objeto int,
            @indice sysname, @sql nvarchar(max), @duplicados bigint,
            @mensaje nvarchar(2048);

    WHILE @orden <= 4
    BEGIN
        SELECT @tabla = nombre FROM @tablas WHERE orden = @orden;
        SET @objeto = OBJECT_ID(N'proceso.' + @tabla, N'U');
        SET @indice = N'UX_' + @tabla + N'_Id_damage';

        IF @objeto IS NULL OR NOT EXISTS (
            SELECT 1 FROM sys.columns
            WHERE object_id = @objeto AND name = N'Id_damage' AND is_nullable = 0
        )
        BEGIN
            SET @mensaje = N'Estructura inesperada en proceso.' + @tabla
                         + N': se requiere Id_damage NOT NULL. No se aplico BD-5.';
            THROW 51501, @mensaje, 1;
        END;

        -- Bloqueo hasta el commit para impedir nuevas filas entre la revision
        -- de duplicados y la creacion del indice. No se descarta ninguna fila.
        SET @sql = N'SELECT @cantidad = COUNT_BIG(*) FROM ('
                 + N'SELECT [Id_damage] FROM [proceso].' + QUOTENAME(@tabla)
                 + N' WITH (TABLOCKX, HOLDLOCK) GROUP BY [Id_damage]'
                 + N' HAVING COUNT_BIG(*) > 1) AS repetidos;';
        EXEC sys.sp_executesql @sql, N'@cantidad bigint OUTPUT', @cantidad = @duplicados OUTPUT;
        IF @duplicados > 0
        BEGIN
            SET @mensaje = N'Hay casos duplicados en proceso.' + @tabla
                         + N'. Requieren revision de negocio; no se elimino ninguna fila.';
            THROW 51502, @mensaje, 1;
        END;

        -- Solo un indice habilitado, sin filtro y cuya unica columna de clave
        -- sea Id_damage garantiza la unicidad requerida para TODOS los casos.
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes AS i
            WHERE i.object_id = @objeto AND i.is_unique = 1
              AND i.is_disabled = 0 AND i.is_hypothetical = 0
              AND i.has_filter = 0 AND i.ignore_dup_key = 0
              AND (SELECT COUNT(*) FROM sys.index_columns AS k
                   WHERE k.object_id = i.object_id AND k.index_id = i.index_id
                     AND k.key_ordinal > 0) = 1
              AND EXISTS (
                  SELECT 1 FROM sys.index_columns AS k
                  JOIN sys.columns AS c ON c.object_id = k.object_id AND c.column_id = k.column_id
                  WHERE k.object_id = i.object_id AND k.index_id = i.index_id
                    AND k.key_ordinal = 1 AND c.name = N'Id_damage'
              )
        )
        BEGIN
            IF EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = @objeto AND name = @indice)
                THROW 51503, 'Existe un indice con el nombre previsto pero no garantiza BD-5. Revise su definicion.', 1;
            SET @sql = N'CREATE UNIQUE NONCLUSTERED INDEX ' + QUOTENAME(@indice)
                     + N' ON [proceso].' + QUOTENAME(@tabla)
                     + N' ([Id_damage]) WITH (IGNORE_DUP_KEY = OFF);';
            EXEC sys.sp_executesql @sql;
        END;
        SET @orden += 1;
    END;

    COMMIT TRANSACTION;
    PRINT N'BD-5 aplicado: unicidad por caso garantizada en las cuatro tablas.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
