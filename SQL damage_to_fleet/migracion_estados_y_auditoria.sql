IF COL_LENGTH('dbo.table_auditoria_correcciones', 'Motivo_modificacion') IS NULL
    ALTER TABLE dbo.table_auditoria_correcciones ADD Motivo_modificacion nvarchar(max) NULL;
GO

IF COL_LENGTH('dbo.table_damage_to_fleet', 'estado_caso') IS NULL
    ALTER TABLE dbo.table_damage_to_fleet ADD estado_caso bit NOT NULL
        CONSTRAINT DF_table_damage_to_fleet_estado_caso DEFAULT (0);
GO

IF COL_LENGTH('dbo.table_info_oper', 'estado_oper') IS NULL
    ALTER TABLE dbo.table_info_oper ADD estado_oper bit NOT NULL
        CONSTRAINT DF_table_info_oper_estado_oper DEFAULT (0);
GO

IF COL_LENGTH('dbo.table_info_oper', 'costo_oper') IS NULL
    ALTER TABLE dbo.table_info_oper ADD costo_oper int NULL;
GO

IF COL_LENGTH('dbo.table_info_labora', 'Cerrado') IS NOT NULL
    ALTER TABLE dbo.table_info_labora DROP COLUMN Cerrado;
GO

-- La auditoría debe permanecer al eliminar el caso, por lo que no puede
-- conservar una FK que impida eliminar el registro principal.
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Auditoria_Damage')
    ALTER TABLE dbo.table_auditoria_correcciones DROP CONSTRAINT FK_Auditoria_Damage;
GO

IF COL_LENGTH('dbo.table_info_mtto', 'estado_mtto') IS NULL
    ALTER TABLE dbo.table_info_mtto ADD estado_mtto bit NOT NULL
        CONSTRAINT DF_table_info_mtto_estado_mtto DEFAULT (0);
GO

IF COL_LENGTH('dbo.table_info_svial', 'estado_svial') IS NULL
    ALTER TABLE dbo.table_info_svial ADD estado_svial bit NOT NULL
        CONSTRAINT DF_table_info_svial_estado_svial DEFAULT (0);
GO
