-- BD-17: reutiliza id INT IDENTITY existente, crea PK y limita nombre/ruta.
-- No renombra columnas, no genera otros IDs y conserva la nulabilidad actual.
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF DB_NAME() <> N'damage_to_fleet'
    THROW 51800, 'Seleccione damage_to_fleet antes de aplicar BD-17.', 1;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @objeto int=OBJECT_ID(N'usuario.table_tutoriales',N'U');
    IF @objeto IS NULL
        THROW 51801, 'No existe usuario.table_tutoriales.', 1;
    IF NOT EXISTS (
        SELECT 1 FROM sys.columns WHERE object_id=@objeto AND name=N'id'
          AND system_type_id=56 AND is_identity=1 AND is_nullable=0
    )
        THROW 51802, 'Se esperaba id INT IDENTITY NOT NULL. Revise antes de crear otra identidad.', 1;
    IF (SELECT COUNT(*) FROM sys.columns WHERE object_id=@objeto
        AND name IN (N'FileName',N'FilePath') AND system_type_id=231 AND is_nullable=1)<>2
        THROW 51803, 'Se esperaba FileName y FilePath NVARCHAR NULL. Revise el esquema.', 1;

    -- Bloqueo transaccional para evitar cambios entre validacion y ALTER.
    DECLARE @filas bigint;
    SELECT @filas=COUNT_BIG(*) FROM usuario.table_tutoriales WITH (TABLOCKX,HOLDLOCK);
    IF EXISTS (SELECT id FROM usuario.table_tutoriales GROUP BY id HAVING COUNT_BIG(*)>1)
        THROW 51804, 'Hay IDs repetidos. No se elimino ni renumero ningun registro.', 1;
    -- DATALENGTH incluye espacios finales y comprueba capacidad UTF-16 en bytes.
    IF EXISTS (SELECT 1 FROM usuario.table_tutoriales
               WHERE DATALENGTH(FileName)>510 OR DATALENGTH(FilePath)>1000)
        THROW 51805, 'Hay nombres o rutas que exceden los limites. No se truncaron valores.', 1;

    IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE parent_object_id=@objeto AND type=N'PK')
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM sys.key_constraints kc
            WHERE kc.parent_object_id=@objeto AND kc.type=N'PK'
              AND (SELECT COUNT(*) FROM sys.index_columns ic
                   WHERE ic.object_id=@objeto AND ic.index_id=kc.unique_index_id AND ic.key_ordinal>0)=1
              AND EXISTS (SELECT 1 FROM sys.index_columns ic
                          JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                          WHERE ic.object_id=@objeto AND ic.index_id=kc.unique_index_id
                            AND ic.key_ordinal=1 AND c.name=N'id')
        )
            THROW 51806, 'Existe una PK diferente de id. No se modifico.', 1;
    END
    ELSE
    BEGIN
        IF EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=@objeto AND type=1)
            THROW 51807, 'Existe un indice clustered no previsto. Revise la PK antes de continuar.', 1;
        ALTER TABLE usuario.table_tutoriales
            ADD CONSTRAINT PK_table_tutoriales PRIMARY KEY CLUSTERED (id);
    END;

    ALTER TABLE usuario.table_tutoriales ALTER COLUMN FileName nvarchar(255) NULL;
    ALTER TABLE usuario.table_tutoriales ALTER COLUMN FilePath nvarchar(500) NULL;
    COMMIT TRANSACTION;
    PRINT N'BD-17 aplicado: PK sobre id existente, FileName NVARCHAR(255), FilePath NVARCHAR(500).';
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
