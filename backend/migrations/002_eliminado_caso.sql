IF OBJECT_ID(N'dbo.table_damage_to_fleet', N'U') IS NULL
    THROW 51011, 'No existe la tabla dbo.table_damage_to_fleet; ejecute primero el script de esquema base.', 1;

IF COL_LENGTH(N'dbo.table_damage_to_fleet', N'eliminado') IS NULL
BEGIN
    ALTER TABLE dbo.table_damage_to_fleet
        ADD eliminado bit NOT NULL
            CONSTRAINT DF_table_damage_to_fleet_eliminado DEFAULT (0);
END
ELSE
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM sys.columns AS c
        WHERE c.object_id = OBJECT_ID(N'dbo.table_damage_to_fleet')
          AND c.name = N'eliminado'
          AND TYPE_NAME(c.user_type_id) = N'bit'
    )
        THROW 51012, 'dbo.table_damage_to_fleet.eliminado debe ser BIT.', 1;

    DECLARE @default_eliminado nvarchar(4000);
    SELECT @default_eliminado = dc.definition
    FROM sys.default_constraints AS dc
    INNER JOIN sys.columns AS c
        ON c.object_id = dc.parent_object_id
       AND c.column_id = dc.parent_column_id
    WHERE c.object_id = OBJECT_ID(N'dbo.table_damage_to_fleet')
      AND c.name = N'eliminado';

    IF @default_eliminado IS NULL
        ALTER TABLE dbo.table_damage_to_fleet ADD CONSTRAINT DF_table_damage_to_fleet_eliminado
            DEFAULT (0) FOR eliminado;
    ELSE IF REPLACE(REPLACE(REPLACE(REPLACE(@default_eliminado, N'(', N''), N')', N''), N' ', N''), N'+', N'') <> N'0'
        THROW 51013, 'El default de dbo.table_damage_to_fleet.eliminado no es compatible.', 1;
END;
