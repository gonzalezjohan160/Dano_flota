IF OBJECT_ID(N'dbo.Table_usuarios', N'U') IS NULL
    THROW 51001, 'No existe la tabla dbo.Table_usuarios; ejecute primero el script de esquema base.', 1;

IF COL_LENGTH(N'dbo.Table_usuarios', N'Cambio_password_obligatorio') IS NULL
BEGIN
    ALTER TABLE dbo.Table_usuarios
        ADD Cambio_password_obligatorio bit NOT NULL
            CONSTRAINT DF_Table_usuarios_Cambio_password_obligatorio DEFAULT (0);
END
ELSE
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.Table_usuarios')
          AND c.name = N'Cambio_password_obligatorio'
          AND TYPE_NAME(c.user_type_id) = N'bit'
    )
        THROW 51002, 'dbo.Table_usuarios.Cambio_password_obligatorio debe ser BIT.', 1;

    DECLARE @default_cambio nvarchar(4000);
    SELECT @default_cambio = dc.definition
    FROM sys.default_constraints AS dc
    INNER JOIN sys.columns AS c
        ON c.object_id = dc.parent_object_id
       AND c.column_id = dc.parent_column_id
    WHERE c.object_id = OBJECT_ID(N'dbo.Table_usuarios')
      AND c.name = N'Cambio_password_obligatorio';

    IF @default_cambio IS NULL
        ALTER TABLE dbo.Table_usuarios ADD CONSTRAINT DF_Table_usuarios_Cambio_password_obligatorio
            DEFAULT (0) FOR Cambio_password_obligatorio;
    ELSE IF REPLACE(REPLACE(REPLACE(REPLACE(@default_cambio, N'(', N''), N')', N''), N' ', N''), N'+', N'') <> N'0'
        THROW 51003, 'El default de dbo.Table_usuarios.Cambio_password_obligatorio no es compatible.', 1;
END;
