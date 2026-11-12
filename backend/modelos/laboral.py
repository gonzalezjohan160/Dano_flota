"""Consultas de la gestión de Relaciones Laborales.

Historial de seguimientos (proceso.table_info_laboral_mult), cierre del caso por RRLL
(proceso.table_info_labora) y procesos que RRLL devuelve a pendiente.
"""

TABLA_CIERRE = "proceso.table_info_labora"

# Compartido por bandeja y Excel; el ID desempata seguimientos con la misma fecha.
ULTIMO_PROCESO_LABORAL_SQL = """(SELECT TOP (1) lm.Pendiente_proceso
    FROM proceso.v_BD6_table_info_laboral_mult lm
    WHERE lm.Id_damage = d.Id_damage
    ORDER BY lm.Fecha_registro DESC, lm.Id_info_laboral DESC)"""
COMITE_RRLL_SQL = f"""(d.estado_caso = 0 AND
    CHARINDEX(',COMITE,', ',' + REPLACE(UPPER(COALESCE({ULTIMO_PROCESO_LABORAL_SQL}, '')), ' ', '') + ',') > 0)"""

# Proceso pendiente -> tabla de la gestión que se devuelve a pendiente. Son nombres
# fijos de este archivo: nunca llegan de la petición.
GESTION_POR_PROCESO = {
    "MANTENIMIENTO": ("proceso.table_info_mtto", "estado_mtto"),
    "OPERACIONES": ("proceso.table_info_oper", "estado_oper"),
    "SEGURIDAD VIAL": ("proceso.table_info_svial", "estado_svial"),
}


def registrar_seguimiento(cursor, id_caso, fecha_presentacion, pendiente_proceso, observaciones, usuario, fecha):
    """Agrega un evento al historial de RRLL del caso."""
    cursor.execute("""
            INSERT INTO proceso.table_info_laboral_mult
                (Id_damage, Fecha_presentacion, Pendiente_proceso,
                 Observaciones_rrll, usuario_id, Fecha_registro)
            VALUES (?, ?, NULLIF(?, ''), ?, ?, ?)
        """, (id_caso, fecha_presentacion, pendiente_proceso, observaciones, usuario, fecha))


def devolver_proceso_a_pendiente(cursor, proceso, id_caso):
    """Deja pendiente la gestión del proceso indicado (MANTENIMIENTO, OPERACIONES
    o SEGURIDAD VIAL)."""
    tabla, columna_estado = GESTION_POR_PROCESO[proceso]
    cursor.execute(f"UPDATE {tabla} SET {columna_estado} = 0 WHERE Id_damage = ?", (id_caso,))


def buscar_cierre(cursor, id_caso):
    """Fila (tipo_cierre, valor_conciliado) del cierre del caso, o None."""
    cursor.execute(
        "SELECT Tipo_cerrado, Valor_conciliado FROM proceso.v_BD6_table_info_labora WHERE Id_damage = ?",
        (id_caso,)
    )
    return cursor.fetchone()


def actualizar_cierre(cursor, id_caso, tipo_cierre, valor_conciliado, usuario):
    cursor.execute("""
                        UPDATE proceso.table_info_labora
                        SET Tipo_cerrado = NULLIF(?, ''), Valor_conciliado = ?, usuario_id = ?
                        WHERE Id_damage = ?
                    """, (tipo_cierre, valor_conciliado, usuario, id_caso))


def crear_cierre(cursor, id_caso, tipo_cierre, valor_conciliado, usuario):
    cursor.execute("""
                    INSERT INTO proceso.table_info_labora
                    (Id_damage, Tipo_cerrado, Valor_conciliado, usuario_id)
                    VALUES (?, NULLIF(?, ''), ?, ?)
                """, (id_caso, tipo_cierre, valor_conciliado, usuario))
