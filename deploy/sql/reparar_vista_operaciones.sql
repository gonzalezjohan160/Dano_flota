-- Mantiene el contrato de lectura de BD-6 después de retirar los campos del formulario.
CREATE OR ALTER VIEW proceso.v_BD6_table_info_oper
AS
SELECT t.Id, t.Id_damage, t.Observaciones_operaciones, t.Fecha_registro,
       CAST(NULL AS varchar(max)) AS observaciones_correctivos,
       CAST(NULL AS varchar(2)) AS rev_error,
       t.responsabilidad_operador, t.conciliacion, t.costo_oper, t.estado_oper,
       t.usuario_id, u.Username AS Usuario_registro_oper
FROM proceso.table_info_oper AS t
LEFT JOIN usuario.Table_usuarios AS u ON u.ConsID = t.usuario_id;
