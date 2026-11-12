-- Auditoría de base de datos (7-10-26): integridad referencial (5.1), reglas de
-- valores (5.2), claves naturales únicas (BCNF) y nombres legibles (5.4).
--
-- Nombres: PK_<tabla>, FK_<tabla>_<columna>, UQ_<tabla>_<columna>,
-- CK_<tabla>_<columna>, DF_<tabla>_<columna>.
--
-- Decisiones de negocio:
--   * El móvil y quien registra son claves foráneas. Los usuarios ya no se borran
--     (se inactivan) y si cambia el nombre de usuario se actualiza en cascada.
--   * El código del operador NO es clave foránea: el maestro de operadores solo
--     tiene a los activos y se sincroniza con la vista de empleados, así que los
--     casos de operadores retirados conservan su código y nombre como histórico.
--   * La auditoría de correcciones conserva 27 filas de casos borrados antes del
--     borrado lógico: su clave foránea se crea WITH NOCHECK (vale para lo nuevo).
--   * No hay regla fecha_evento <= fecha_registro: se justificó en la auditoría.
IF OBJECT_ID(N'flota.caso', N'U') IS NULL OR COL_LENGTH(N'flota.caso', N'franja_horaria') IS NULL
    THROW 51101, 'Aplique primero las migraciones 008 y 009.', 1;

-- -------------------------------------------- claves primarias legibles ---
DECLARE @sql nvarchar(max) = N'';
SELECT @sql += N'EXEC sp_rename N''' + SCHEMA_NAME(t.schema_id) + N'.' + kc.name
    + N''', N''PK_' + t.name + N''', N''OBJECT'';' + NCHAR(10)
FROM sys.key_constraints AS kc
INNER JOIN sys.tables AS t ON t.object_id = kc.parent_object_id
WHERE kc.type = 'PK'
  AND SCHEMA_NAME(t.schema_id) IN (N'flota', N'proceso', N'usuario')
  AND kc.name <> N'PK_' + t.name;
EXEC sys.sp_executesql @sql;

ALTER TABLE usuario.tutorial ADD CONSTRAINT PK_tutorial PRIMARY KEY CLUSTERED (id);

-- ------------------------------------------------ valores predeterminados ---
ALTER TABLE flota.caso ADD
    CONSTRAINT DF_caso_fecha_registro DEFAULT (SYSDATETIME()) FOR fecha_registro,
    CONSTRAINT DF_caso_cerrado DEFAULT (0) FOR cerrado,
    CONSTRAINT DF_caso_eliminado DEFAULT (0) FOR eliminado;
ALTER TABLE flota.archivo_caso ADD CONSTRAINT DF_archivo_caso_fecha_subida DEFAULT (SYSDATETIME()) FOR fecha_subida;
ALTER TABLE proceso.gestion_operaciones ADD
    CONSTRAINT DF_gestion_operaciones_fecha_registro DEFAULT (SYSDATETIME()) FOR fecha_registro,
    CONSTRAINT DF_gestion_operaciones_completada DEFAULT (0) FOR completada;
ALTER TABLE proceso.gestion_mantenimiento ADD
    CONSTRAINT DF_gestion_mantenimiento_fecha_registro DEFAULT (SYSDATETIME()) FOR fecha_registro,
    CONSTRAINT DF_gestion_mantenimiento_completada DEFAULT (0) FOR completada;
ALTER TABLE proceso.gestion_seguridad_vial ADD
    CONSTRAINT DF_gestion_seguridad_vial_fecha_registro DEFAULT (SYSDATETIME()) FOR fecha_registro,
    CONSTRAINT DF_gestion_seguridad_vial_completada DEFAULT (0) FOR completada;
ALTER TABLE proceso.cierre_laboral ADD CONSTRAINT DF_cierre_laboral_fecha_registro DEFAULT (SYSDATETIME()) FOR fecha_registro;
ALTER TABLE proceso.seguimiento_laboral ADD CONSTRAINT DF_seguimiento_laboral_fecha_registro DEFAULT (SYSDATETIME()) FOR fecha_registro;
ALTER TABLE proceso.correccion ADD CONSTRAINT DF_correccion_fecha_modificacion DEFAULT (SYSDATETIME()) FOR fecha_modificacion;
ALTER TABLE proceso.intervencion ADD CONSTRAINT DF_intervencion_fecha_registro DEFAULT (SYSDATETIME()) FOR fecha_registro;
ALTER TABLE proceso.archivo_intervencion ADD CONSTRAINT DF_archivo_intervencion_fecha_subida DEFAULT (SYSDATETIME()) FOR fecha_subida;
ALTER TABLE usuario.usuario ADD
    CONSTRAINT DF_usuario_fecha_creacion DEFAULT (SYSDATETIME()) FOR fecha_creacion,
    CONSTRAINT DF_usuario_activo DEFAULT (1) FOR activo,
    CONSTRAINT DF_usuario_cambio_contrasena_obligatorio DEFAULT (0) FOR cambio_contrasena_obligatorio;
ALTER TABLE usuario.restablecimiento_contrasena ADD CONSTRAINT DF_restablecimiento_contrasena_usado DEFAULT (0) FOR usado;
ALTER TABLE usuario.tutorial ADD CONSTRAINT DF_tutorial_fecha_subida DEFAULT (SYSDATETIME()) FOR fecha_subida;

-- ------------------------------------------------ claves naturales únicas ---
ALTER TABLE flota.movil ADD CONSTRAINT UQ_movil_numero UNIQUE (numero);
ALTER TABLE flota.operador ADD CONSTRAINT UQ_operador_codigo UNIQUE (codigo);
ALTER TABLE usuario.usuario ADD CONSTRAINT UQ_usuario_nombre_usuario UNIQUE (nombre_usuario);
CREATE UNIQUE INDEX UQ_usuario_correo ON usuario.usuario (correo) WHERE correo IS NOT NULL;
CREATE UNIQUE INDEX UQ_usuario_identificacion ON usuario.usuario (identificacion) WHERE identificacion IS NOT NULL;
ALTER TABLE usuario.permiso ADD CONSTRAINT UQ_permiso_nombre UNIQUE (nombre);
ALTER TABLE usuario.restablecimiento_contrasena ADD CONSTRAINT UQ_restablecimiento_contrasena_huella_token UNIQUE (huella_token);
-- Relación 1:1 entre el caso y cada gestión (hallazgo 5).
ALTER TABLE proceso.gestion_operaciones ADD CONSTRAINT UQ_gestion_operaciones_caso_id UNIQUE (caso_id);
ALTER TABLE proceso.gestion_mantenimiento ADD CONSTRAINT UQ_gestion_mantenimiento_caso_id UNIQUE (caso_id);
ALTER TABLE proceso.gestion_seguridad_vial ADD CONSTRAINT UQ_gestion_seguridad_vial_caso_id UNIQUE (caso_id);
ALTER TABLE proceso.cierre_laboral ADD CONSTRAINT UQ_cierre_laboral_caso_id UNIQUE (caso_id);
-- Un mismo archivo no se registra dos veces en el mismo caso.
ALTER TABLE flota.archivo_caso ADD CONSTRAINT UQ_archivo_caso_caso_id_ruta_archivo UNIQUE (caso_id, ruta_archivo);

-- ---------------------------------------------------- reglas de valores ---
-- DATALENGTH porque "=" ignora los espacios finales.
ALTER TABLE flota.caso ADD CONSTRAINT CK_caso_parte_afectada
    CHECK (parte_afectada <> '' AND DATALENGTH(parte_afectada) = DATALENGTH(LTRIM(RTRIM(parte_afectada))));
ALTER TABLE proceso.gestion_operaciones ADD
    CONSTRAINT CK_gestion_operaciones_informacion_correcta CHECK (informacion_correcta IN ('SI', 'NO')),
    CONSTRAINT CK_gestion_operaciones_responsabilidad_operador CHECK (responsabilidad_operador IN ('SI', 'NO', 'NO APLICA')),
    CONSTRAINT CK_gestion_operaciones_conciliacion CHECK (conciliacion IN ('SI', 'NO')),
    CONSTRAINT CK_gestion_operaciones_costo CHECK (costo >= 0);
ALTER TABLE proceso.gestion_mantenimiento ADD
    CONSTRAINT CK_gestion_mantenimiento_dano_adicional CHECK (dano_adicional IN ('SI', 'NO')),
    CONSTRAINT CK_gestion_mantenimiento_costo CHECK (costo >= 0);
ALTER TABLE proceso.gestion_seguridad_vial ADD
    CONSTRAINT CK_gestion_seguridad_vial_conciliado_a_favor CHECK (conciliado_a_favor IN ('terceros', 'empresa')),
    CONSTRAINT CK_gestion_seguridad_vial_valor_conciliado_terceros CHECK (valor_conciliado_terceros >= 0);
ALTER TABLE proceso.cierre_laboral ADD
    CONSTRAINT CK_cierre_laboral_tipo_cierre CHECK (tipo_cierre IN (
        'RECOMENDACIÓN DE T.H', 'LLAMADO DE ATENCIÓN', 'SUSPENSIÓN', 'TERMINACIÓN DE CONTRATO',
        'CONCILIACIÓN', 'CONCILIACIÓN Y DISCIPLINARIOS', 'EXTEMPORÁNEO', 'EXTEMPORÁNEO_CONCILIACIÓN',
        'EXONERACIÓN', 'RETIRO')),
    CONSTRAINT CK_cierre_laboral_valor_conciliado CHECK (valor_conciliado >= 0);
ALTER TABLE proceso.intervencion ADD CONSTRAINT CK_intervencion_costo CHECK (costo >= 0);
ALTER TABLE usuario.usuario ADD CONSTRAINT CK_usuario_alcance_uf CHECK (alcance_uf IN ('TRANSVERSAL', '10', '16'));
ALTER TABLE usuario.restablecimiento_contrasena ADD CONSTRAINT CK_restablecimiento_contrasena_huella_token
    CHECK (huella_token NOT LIKE '%[^0-9a-f]%');

-- ------------------------------------------------------ claves foráneas ---
ALTER TABLE flota.movil ADD
    CONSTRAINT FK_movil_unidad_funcional FOREIGN KEY (unidad_funcional_id) REFERENCES catalogo.unidad_funcional (id),
    CONSTRAINT FK_movil_tipologia FOREIGN KEY (tipologia) REFERENCES catalogo.tipologia (nombre) ON UPDATE CASCADE;

ALTER TABLE flota.caso ADD
    CONSTRAINT FK_caso_movil FOREIGN KEY (movil) REFERENCES flota.movil (numero) ON UPDATE CASCADE,
    CONSTRAINT FK_caso_registrado_por FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE,
    CONSTRAINT FK_caso_area FOREIGN KEY (area) REFERENCES catalogo.area (nombre) ON UPDATE CASCADE,
    CONSTRAINT FK_caso_ruta FOREIGN KEY (ruta) REFERENCES catalogo.ruta (nombre) ON UPDATE CASCADE,
    CONSTRAINT FK_caso_tipo_dano FOREIGN KEY (tipo_dano) REFERENCES catalogo.tipo_dano (nombre) ON UPDATE CASCADE,
    CONSTRAINT FK_caso_zona_dano FOREIGN KEY (zona_dano) REFERENCES catalogo.zona_dano (nombre) ON UPDATE CASCADE,
    CONSTRAINT FK_caso_centro_operacion FOREIGN KEY (centro_operacion) REFERENCES catalogo.centro_operacion (nombre) ON UPDATE CASCADE;

ALTER TABLE flota.archivo_caso ADD CONSTRAINT FK_archivo_caso_caso FOREIGN KEY (caso_id) REFERENCES flota.caso (id);

ALTER TABLE proceso.gestion_operaciones ADD
    CONSTRAINT FK_gestion_operaciones_caso FOREIGN KEY (caso_id) REFERENCES flota.caso (id),
    CONSTRAINT FK_gestion_operaciones_registrado_por FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE;
ALTER TABLE proceso.gestion_mantenimiento ADD
    CONSTRAINT FK_gestion_mantenimiento_caso FOREIGN KEY (caso_id) REFERENCES flota.caso (id),
    CONSTRAINT FK_gestion_mantenimiento_registrado_por FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE;
ALTER TABLE proceso.gestion_seguridad_vial ADD
    CONSTRAINT FK_gestion_seguridad_vial_caso FOREIGN KEY (caso_id) REFERENCES flota.caso (id),
    CONSTRAINT FK_gestion_seguridad_vial_registrado_por FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE;
ALTER TABLE proceso.cierre_laboral ADD
    CONSTRAINT FK_cierre_laboral_caso FOREIGN KEY (caso_id) REFERENCES flota.caso (id),
    CONSTRAINT FK_cierre_laboral_registrado_por FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE;
ALTER TABLE proceso.seguimiento_laboral ADD
    CONSTRAINT FK_seguimiento_laboral_caso FOREIGN KEY (caso_id) REFERENCES flota.caso (id),
    CONSTRAINT FK_seguimiento_laboral_registrado_por FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE;

ALTER TABLE proceso.correccion WITH NOCHECK ADD
    CONSTRAINT FK_correccion_caso FOREIGN KEY (caso_id) REFERENCES flota.caso (id);
ALTER TABLE proceso.correccion ADD
    CONSTRAINT FK_correccion_modificado_por FOREIGN KEY (modificado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE;

ALTER TABLE proceso.intervencion ADD
    CONSTRAINT FK_intervencion_movil FOREIGN KEY (movil) REFERENCES flota.movil (numero) ON UPDATE CASCADE,
    CONSTRAINT FK_intervencion_registrado_por FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE;
ALTER TABLE proceso.archivo_intervencion ADD
    CONSTRAINT FK_archivo_intervencion_intervencion FOREIGN KEY (intervencion_id) REFERENCES proceso.intervencion (id);

ALTER TABLE usuario.usuario_permiso ADD
    CONSTRAINT FK_usuario_permiso_usuario FOREIGN KEY (usuario_id) REFERENCES usuario.usuario (id),
    CONSTRAINT FK_usuario_permiso_permiso FOREIGN KEY (permiso_id) REFERENCES usuario.permiso (id);
ALTER TABLE usuario.restablecimiento_contrasena ADD
    CONSTRAINT FK_restablecimiento_contrasena_usuario FOREIGN KEY (usuario_id) REFERENCES usuario.usuario (id);
