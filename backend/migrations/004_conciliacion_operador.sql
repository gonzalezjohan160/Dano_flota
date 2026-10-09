IF OBJECT_ID(N'dbo.table_info_oper', N'U') IS NULL
    THROW 51031, 'No existe la tabla dbo.table_info_oper; ejecute primero el script de esquema base.', 1;

IF COL_LENGTH(N'dbo.table_info_oper', N'conciliacion') IS NULL
BEGIN
    ALTER TABLE dbo.table_info_oper ADD conciliacion varchar(10) NULL;
END
ELSE
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.table_info_oper')
          AND c.name = N'conciliacion'
          AND TYPE_NAME(c.user_type_id) = N'varchar'
    )
        THROW 51032, 'dbo.table_info_oper.conciliacion debe ser VARCHAR.', 1;

    IF EXISTS (
        SELECT 1
        FROM sys.default_constraints AS dc
        INNER JOIN sys.columns AS c
            ON c.object_id = dc.parent_object_id
           AND c.column_id = dc.parent_column_id
        WHERE c.object_id = OBJECT_ID(N'dbo.table_info_oper')
          AND c.name = N'conciliacion'
    )
        THROW 51033, 'dbo.table_info_oper.conciliacion no debe tener un default.', 1;

    -- Algunas bases se crearon con otra longitud. Se ajusta a VARCHAR(10) NULL
    -- solo si todos los datos existentes caben; si no, no se modifica nada.
    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.table_info_oper')
          AND c.name = N'conciliacion'
          AND c.max_length = 10
          AND c.is_nullable = 1
    )
    BEGIN
        DECLARE @max_conciliacion int;
        EXEC sp_executesql
            N'SELECT @max = MAX(LEN(conciliacion)) FROM dbo.table_info_oper;',
            N'@max int OUTPUT', @max = @max_conciliacion OUTPUT;

        IF ISNULL(@max_conciliacion, 0) > 10
            THROW 51034, 'dbo.table_info_oper.conciliacion tiene datos de más de 10 caracteres; corríjalos antes de migrar.', 1;

        EXEC sp_executesql N'ALTER TABLE dbo.table_info_oper ALTER COLUMN conciliacion varchar(10) NULL;';
    END
END;
