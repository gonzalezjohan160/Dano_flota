-- BD-6 autorizado. Requiere desplegar el codigo adaptado a usuario_id y vistas v_BD6.
-- Las vistas exponen Username solo para presentacion; no almacenan referencias textuales.
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
IF DB_NAME()<>N'damage_to_fleet'
    THROW 52000, 'Seleccione damage_to_fleet para aplicar BD-6.', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @r TABLE (orden int PRIMARY KEY, esquema sysname, tabla sysname, anterior sysname, nulo bit);
    INSERT INTO @r VALUES
        (1,N'flota',N'table_damage_to_fleet',N'Registrador',1),
        (2,N'proceso',N'table_info_oper',N'Usuario_registro_oper',0),
        (3,N'proceso',N'table_info_mtto',N'Usuario_registro_mtto',1),
        (4,N'proceso',N'table_info_svial',N'Usuario_registro_svial',0),
        (5,N'proceso',N'table_info_labora',N'Usuario_registro_labora',0),
        (6,N'proceso',N'table_info_laboral_mult',N'Usuario_registro_laboral',1),
        (7,N'proceso',N'table_auditoria_correcciones',N'Usuario_Modifica',1),
        (8,N'proceso',N'table_intervenciones',N'Usuario_registro',0);

    IF EXISTS (SELECT Username FROM usuario.Table_usuarios WITH (TABLOCKX,HOLDLOCK)
               GROUP BY Username HAVING COUNT_BIG(*)>1)
        THROW 52001, 'Username ambiguo: se requiere correspondencia unica.', 1;
    DECLARE @i int=1,@s sysname,@t sysname,@vieja sysname,@nulo bit,@obj int,
            @nombre nvarchar(520),@sql nvarchar(max),@cantidad bigint,
            @fk sysname,@ix sysname,@columnas nvarchar(max),@vista nvarchar(520);
    WHILE @i<=8
    BEGIN
        SELECT @s=esquema,@t=tabla,@vieja=anterior,@nulo=nulo FROM @r WHERE orden=@i;
        SET @nombre=QUOTENAME(@s)+N'.'+QUOTENAME(@t);
        SET @obj=OBJECT_ID(@nombre,N'U');
        IF @obj IS NULL THROW 52002, 'Falta una tabla de referencias de usuarios.', 1;
        IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=@obj AND name=N'usuario_id')
        BEGIN
            SET @sql=N'ALTER TABLE '+@nombre+N' ADD usuario_id int NULL;';
            EXEC sys.sp_executesql @sql;
        END;
        IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=@obj AND name=N'usuario_id' AND system_type_id=56)
            THROW 52003, 'usuario_id debe ser INT; no se convertira silenciosamente.', 1;

        IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=@obj AND name=@vieja)
        BEGIN
            SET @sql=N'SELECT @n=COUNT_BIG(*) FROM '+@nombre+N' t WITH (TABLOCKX,HOLDLOCK)'
              +N' LEFT JOIN usuario.Table_usuarios u ON u.Username COLLATE DATABASE_DEFAULT='
              +N'CONVERT(nvarchar(max),t.'+QUOTENAME(@vieja)+N') COLLATE DATABASE_DEFAULT'
              +N' WHERE t.'+QUOTENAME(@vieja)+N' IS NOT NULL AND u.ConsID IS NULL;';
            EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT',@n=@cantidad OUTPUT;
            IF @cantidad>0 THROW 52004, 'Referencia textual sin usuario: no se retiraron columnas.', 1;
            SET @sql=N'SELECT @n=COUNT_BIG(*) FROM '+@nombre+N' t'
              +N' LEFT JOIN usuario.Table_usuarios u ON u.Username COLLATE DATABASE_DEFAULT='
              +N'CONVERT(nvarchar(max),t.'+QUOTENAME(@vieja)+N') COLLATE DATABASE_DEFAULT'
              +N' WHERE t.usuario_id IS NOT NULL AND (u.ConsID IS NULL OR t.usuario_id<>u.ConsID);';
            EXEC sys.sp_executesql @sql,N'@n bigint OUTPUT',@n=@cantidad OUTPUT;
            IF @cantidad>0 THROW 52005, 'Conflicto entre usuario_id existente y el texto. Revise antes de continuar.', 1;
            SET @sql=N'UPDATE t SET usuario_id=u.ConsID FROM '+@nombre+N' t'
              +N' JOIN usuario.Table_usuarios u ON u.Username COLLATE DATABASE_DEFAULT='
              +N'CONVERT(nvarchar(max),t.'+QUOTENAME(@vieja)+N') COLLATE DATABASE_DEFAULT'
              +N' WHERE t.usuario_id IS NULL;';
            EXEC sys.sp_executesql @sql;
        END;
        IF @nulo=0
        BEGIN
            SET @sql=N'ALTER TABLE '+@nombre+N' ALTER COLUMN usuario_id int NOT NULL;';
            EXEC sys.sp_executesql @sql;
        END;
        SET @fk=N'FK_BD6_'+@t+N'_usuario';
        IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=@obj AND name=@fk)
        BEGIN
            SET @sql=N'ALTER TABLE '+@nombre+N' WITH CHECK ADD CONSTRAINT '+QUOTENAME(@fk)
              +N' FOREIGN KEY (usuario_id) REFERENCES usuario.Table_usuarios(ConsID);';
            EXEC sys.sp_executesql @sql;
        END;
        SET @sql=N'ALTER TABLE '+@nombre+N' WITH CHECK CHECK CONSTRAINT '+QUOTENAME(@fk)+N';';
        EXEC sys.sp_executesql @sql;
        SET @ix=N'IX_'+@t+N'_usuario_id';
        IF NOT EXISTS (SELECT 1 FROM sys.indexes i JOIN sys.index_columns ic
                       ON ic.object_id=i.object_id AND ic.index_id=i.index_id
                       JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                       WHERE i.object_id=@obj AND i.is_disabled=0 AND i.has_filter=0
                         AND ic.key_ordinal=1 AND c.name=N'usuario_id')
        BEGIN
            SET @sql=N'CREATE NONCLUSTERED INDEX '+QUOTENAME(@ix)+N' ON '+@nombre+N'(usuario_id);';
            EXEC sys.sp_executesql @sql;
        END;

        IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=@obj AND name=@vieja)
        BEGIN
            SET @sql=N'ALTER TABLE '+@nombre+N' DROP COLUMN '+QUOTENAME(@vieja)+N';';
            EXEC sys.sp_executesql @sql;
        END;
        SELECT @columnas=STRING_AGG(CONVERT(nvarchar(max),N't.'+QUOTENAME(name)),N',')
               WITHIN GROUP (ORDER BY column_id)
        FROM sys.columns WHERE object_id=@obj;
        SET @vista=QUOTENAME(@s)+N'.'+QUOTENAME(N'v_BD6_'+@t);
        SET @sql=N'CREATE OR ALTER VIEW '+@vista+N' AS SELECT '+@columnas
          +N',u.Username AS '+QUOTENAME(@vieja)+N' FROM '+@nombre+N' t'
          +N' LEFT JOIN usuario.Table_usuarios u ON u.ConsID=t.usuario_id;';
        EXEC sys.sp_executesql @sql;
        SET @i+=1;
    END;
    COMMIT TRANSACTION;
    PRINT N'BD-6 aplicado: ocho FK numericas indexadas y columnas textuales retiradas.';
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
