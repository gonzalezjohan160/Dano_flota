-- Auditoria 4.09: indices de FK y filtros del dashboard con nombres actuales.
-- Aplicar solo con autorizacion. No modifica datos, reglas ni relaciones.
-- Reutiliza los cuatro UNIQUE de BD-5 y la PK que cubre UserID de permisos.
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET ARITHABORT ON;
SET NUMERIC_ROUNDABORT OFF;
IF DB_NAME()<>N'damage_to_fleet'
    THROW 51900, 'Seleccione damage_to_fleet antes de crear los indices.', 1;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @indices TABLE (
        orden int PRIMARY KEY, esquema sysname, tabla sysname, nombre sysname,
        clave1 sysname, clave2 sysname NULL, incluir nvarchar(1000) NULL,
        filtro nvarchar(1000) NULL
    );
    INSERT INTO @indices VALUES
        (1,N'flota',N'table_damage_files',N'IX_table_damage_files_Id_damage',N'Id_damage',NULL,NULL,NULL),
        (2,N'proceso',N'table_info_laboral_mult',N'IX_table_info_laboral_mult_Id_damage_Fecha_registro',N'Id_damage',N'Fecha_registro',NULL,NULL),
        (3,N'proceso',N'table_intervenciones_files',N'IX_table_intervenciones_files_RepairId',N'RepairId',NULL,NULL,NULL),
        (4,N'usuario',N'Table_password_reset',N'IX_Table_password_reset_UserId',N'UserId',NULL,NULL,NULL),
        (5,N'usuario',N'Table_usuarios_permisos',N'IX_Table_usuarios_permisos_PermisoID',N'PermisoID',NULL,NULL,NULL),
        (6,N'flota',N'table_damage_to_fleet',N'IX_table_damage_to_fleet_Fecha_evento',N'Fecha_evento',NULL,N'[Movil],[estado_caso],[eliminado]',NULL),
        (7,N'flota',N'table_damage_to_fleet',N'IX_table_damage_to_fleet_Movil_Fecha_evento',N'Movil',N'Fecha_evento',NULL,NULL),
        (8,N'flota',N'table_damage_to_fleet',N'IX_table_damage_to_fleet_Codigo_Fecha_evento',N'Codigo',N'Fecha_evento',NULL,NULL),
        (9,N'flota',N'table_damage_to_fleet',N'IX_table_damage_to_fleet_casos_abiertos',N'Fecha_evento',N'Movil',N'[Codigo]',N'[estado_caso]=0 AND [eliminado]=0'),
        (10,N'flota',N'table_Moviles',N'IX_table_Moviles_UF_No_Movil',N'UF',N'No_Movil',N'[Tipologia_Movil]',NULL);

    DECLARE @orden int=1, @esquema sysname, @tabla sysname, @nombre sysname,
            @clave1 sysname, @clave2 sysname, @incluir nvarchar(1000),
            @filtro nvarchar(1000), @objeto int, @sql nvarchar(max),
            @filtro_normalizado nvarchar(1000), @mensaje nvarchar(2048);
    WHILE @orden<=10
    BEGIN
        SELECT @esquema=esquema,@tabla=tabla,@nombre=nombre,@clave1=clave1,
               @clave2=clave2,@incluir=incluir,@filtro=filtro
        FROM @indices WHERE orden=@orden;
        SET @objeto=OBJECT_ID(QUOTENAME(@esquema)+N'.'+QUOTENAME(@tabla),N'U');
        IF @objeto IS NULL OR NOT EXISTS (
            SELECT 1 FROM sys.columns WHERE object_id=@objeto AND name=@clave1
        ) OR (@clave2 IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM sys.columns WHERE object_id=@objeto AND name=@clave2
        ))
        BEGIN
            SET @mensaje=N'Estructura inesperada para '+@nombre+N'. Se revierte la migracion.';
            THROW 51901,@mensaje,1;
        END;
        SET @filtro_normalizado=LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            ISNULL(@filtro,N''),N'(',N''),N')',N''),N'[',N''),N']',N''),N' ',N''));

        -- Un indice sin filtro sirve de cobertura general para la FK.
        -- Para el indice de abiertos se exige el mismo predicado filtrado.
        -- Se comparan claves iniciales; no se duplica un acceso ya disponible.
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes i
            WHERE i.object_id=@objeto AND i.type IN (1,2)
              AND i.is_disabled=0 AND i.is_hypothetical=0
              AND ((@filtro IS NULL AND i.has_filter=0) OR
                   (@filtro IS NOT NULL AND i.has_filter=1 AND
                    LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    i.filter_definition,N'(',N''),N')',N''),N'[',N''),N']',N''),N' ',N''))=@filtro_normalizado))
              AND EXISTS (SELECT 1 FROM sys.index_columns ic JOIN sys.columns c
                          ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                          WHERE ic.object_id=@objeto AND ic.index_id=i.index_id
                            AND ic.key_ordinal=1 AND c.name=@clave1)
              AND (@clave2 IS NULL OR EXISTS (
                   SELECT 1 FROM sys.index_columns ic JOIN sys.columns c
                   ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                   WHERE ic.object_id=@objeto AND ic.index_id=i.index_id
                     AND ic.key_ordinal=2 AND c.name=@clave2))
        )
        BEGIN
            IF EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=@objeto AND name=@nombre)
                THROW 51902, 'Existe un indice con el nombre previsto pero otra definicion. Revise antes de sustituirlo.', 1;
            SET @sql=N'CREATE NONCLUSTERED INDEX '+QUOTENAME(@nombre)
                    +N' ON '+QUOTENAME(@esquema)+N'.'+QUOTENAME(@tabla)
                    +N' ('+QUOTENAME(@clave1)
                    +CASE WHEN @clave2 IS NULL THEN N'' ELSE N','+QUOTENAME(@clave2) END+N')'
                    +CASE WHEN @incluir IS NULL THEN N'' ELSE N' INCLUDE ('+@incluir+N')' END
                    +CASE WHEN @filtro IS NULL THEN N'' ELSE N' WHERE '+@filtro END+N';';
            EXEC sys.sp_executesql @sql;
            PRINT N'Creado: '+@nombre;
        END
        ELSE PRINT N'Cobertura existente, omitido: '+@nombre;
        SET @orden+=1;
    END;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
