-- Auditoría de base de datos (7-10-26), hallazgo 3 y sección 5.4: índices.
--
-- Toda clave foránea queda indexada (las que encabezan una clave primaria o una
-- restricción UNIQUE ya lo están: gestiones por caso_id, archivo_caso,
-- usuario_permiso.usuario_id y ruta_unidad_funcional.ruta). Además, los filtros
-- típicos de las pantallas: rango de fecha del evento, móvil, operador (la
-- reincidencia busca por código y fecha) y casos abiertos no eliminados.
IF OBJECT_ID(N'flota.FK_caso_movil', N'F') IS NULL
    THROW 51111, 'Aplique primero la migración 010.', 1;

-- flota
CREATE INDEX IX_caso_fecha_evento ON flota.caso (fecha_evento)
    INCLUDE (movil, cerrado, eliminado);
CREATE INDEX IX_caso_movil ON flota.caso (movil, fecha_evento);
CREATE INDEX IX_caso_codigo_operador ON flota.caso (codigo_operador, fecha_evento);
CREATE INDEX IX_caso_abiertos ON flota.caso (id) INCLUDE (movil, fecha_evento)
    WHERE cerrado = 0 AND eliminado = 0;
CREATE INDEX IX_caso_registrado_por ON flota.caso (registrado_por);
CREATE INDEX IX_caso_area ON flota.caso (area);
CREATE INDEX IX_caso_ruta ON flota.caso (ruta);
CREATE INDEX IX_caso_tipo_dano ON flota.caso (tipo_dano);
CREATE INDEX IX_caso_zona_dano ON flota.caso (zona_dano);
CREATE INDEX IX_caso_centro_operacion ON flota.caso (centro_operacion);
CREATE INDEX IX_movil_unidad_funcional_id ON flota.movil (unidad_funcional_id) INCLUDE (numero);
CREATE INDEX IX_movil_tipologia ON flota.movil (tipologia);

-- proceso
CREATE INDEX IX_gestion_operaciones_registrado_por ON proceso.gestion_operaciones (registrado_por);
CREATE INDEX IX_gestion_mantenimiento_registrado_por ON proceso.gestion_mantenimiento (registrado_por);
CREATE INDEX IX_gestion_seguridad_vial_registrado_por ON proceso.gestion_seguridad_vial (registrado_por);
CREATE INDEX IX_cierre_laboral_registrado_por ON proceso.cierre_laboral (registrado_por);
CREATE INDEX IX_seguimiento_laboral_caso_id ON proceso.seguimiento_laboral (caso_id, fecha_registro);
CREATE INDEX IX_seguimiento_laboral_registrado_por ON proceso.seguimiento_laboral (registrado_por);
CREATE INDEX IX_correccion_caso_id ON proceso.correccion (caso_id);
CREATE INDEX IX_correccion_modificado_por ON proceso.correccion (modificado_por);
CREATE INDEX IX_intervencion_movil ON proceso.intervencion (movil, fecha_registro);
CREATE INDEX IX_intervencion_registrado_por ON proceso.intervencion (registrado_por);
CREATE INDEX IX_archivo_intervencion_intervencion_id ON proceso.archivo_intervencion (intervencion_id);

-- usuario
CREATE INDEX IX_usuario_permiso_permiso_id ON usuario.usuario_permiso (permiso_id);
CREATE INDEX IX_restablecimiento_contrasena_usuario_id ON usuario.restablecimiento_contrasena (usuario_id);

-- catalogo
CREATE INDEX IX_ruta_unidad_funcional_unidad_funcional_id ON catalogo.ruta_unidad_funcional (unidad_funcional_id);
