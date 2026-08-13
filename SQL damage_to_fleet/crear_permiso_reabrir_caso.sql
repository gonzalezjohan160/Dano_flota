-- Integra el permiso solicitado sin modificar columnas ni permisos existentes.
IF NOT EXISTS (SELECT 1 FROM dbo.Table_permisos WHERE Nombre = N'reabrir caso')
BEGIN
    INSERT INTO dbo.Table_permisos (Nombre, Descripcion)
    VALUES (N'reabrir caso', N'Permite reabrir casos cerrados desde Control Operacional.');
END;
GO
