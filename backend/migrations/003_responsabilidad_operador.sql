IF OBJECT_ID(N'dbo.table_info_oper', N'U') IS NULL
    THROW 51021, 'No existe la tabla dbo.table_info_oper; ejecute primero el script de esquema base.', 1;

IF COL_LENGTH(N'dbo.table_info_oper', N'responsabilidad_operador') IS NULL
BEGIN
    ALTER TABLE dbo.table_info_oper ADD responsabilidad_operador varchar(20) NULL;
END
ELSE
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.table_info_oper')
          AND c.name = N'responsabilidad_operador'
          AND TYPE_NAME(c.user_type_id) = N'varchar'
    )
        THROW 51022, 'dbo.table_info_oper.responsabilidad_operador debe ser VARCHAR.', 1;

    IF EXISTS (
        SELECT 1
        FROM sys.default_constraints AS dc
        INNER JOIN sys.columns AS c
            ON c.object_id = dc.parent_object_id
           AND c.column_id = dc.parent_column_id
        WHERE c.object_id = OBJECT_ID(N'dbo.table_info_oper')
          AND c.name = N'responsabilidad_operador'
    )
        THROW 51023, 'dbo.table_info_oper.responsabilidad_operador no debe tener un default.', 1;

    -- Algunas bases se crearon con otra longitud. Se ajusta a VARCHAR(20) NULL
    -- solo si todos los datos existentes caben; si no, no se modifica nada.
    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.table_info_oper')
          AND c.name = N'responsabilidad_operador'
          AND c.max_length = 20
          AND c.is_nullable = 1
    )
    BEGIN
        DECLARE @max_responsabilidad int;
        EXEC sp_executesql
            N'SELECT @max = MAX(LEN(responsabilidad_operador)) FROM dbo.table_info_oper;',
            N'@max int OUTPUT', @max = @max_responsabilidad OUTPUT;

        IF ISNULL(@max_responsabilidad, 0) > 20
            THROW 51024, 'dbo.table_info_oper.responsabilidad_operador tiene datos de más de 20 caracteres; corríjalos antes de migrar.', 1;

        EXEC sp_executesql N'ALTER TABLE dbo.table_info_oper ALTER COLUMN responsabilidad_operador varchar(20) NULL;';
    END
END;
