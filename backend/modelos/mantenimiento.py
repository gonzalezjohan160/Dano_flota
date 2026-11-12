"""Consultas de la gestión de Mantenimiento (proceso.table_info_mtto)."""

TABLA = "proceso.table_info_mtto"


def existe_gestion(cursor, id_caso):
    """True si el caso ya tiene gestión de Mantenimiento (por ejemplo, un costo
    preliminar registrado por Operaciones)."""
    cursor.execute("SELECT 1 FROM proceso.v_BD6_table_info_mtto WHERE Id_damage = ?", [id_caso])
    return cursor.fetchone() is not None


def buscar_gestion(cursor, id_caso):
    """Fila (costo, dano_adicional, observaciones) de la gestión, o None."""
    cursor.execute(
        "SELECT Costo, dano_adicional, observaciones FROM proceso.v_BD6_table_info_mtto WHERE Id_damage = ?",
        [id_caso],
    )
    return cursor.fetchone()


def actualizar_gestion(cursor, id_caso, costo, dano_adicional, observaciones, usuario):
    """Completa la fila existente y marca la gestión como hecha."""
    cursor.execute("""
                    UPDATE proceso.table_info_mtto
                    SET Costo = ?, dano_adicional = NULLIF(?, ''), observaciones = ?,
                        usuario_id = ?, estado_mtto = 1
                    WHERE Id_damage = ?
                """, (costo, dano_adicional, observaciones, usuario, id_caso))


def crear_gestion(cursor, valores):
    """Inserta la gestión. valores: [id_caso, costo, dano_adicional, observaciones, usuario]."""
    cursor.execute("""
            INSERT INTO proceso.table_info_mtto
                (Id_damage, Costo, dano_adicional, observaciones, usuario_id)
            VALUES (?, ?, NULLIF(?, ''), ?, ?)
        """, valores)


def marcar_gestion_hecha(cursor, id_caso):
    cursor.execute("UPDATE proceso.table_info_mtto SET estado_mtto = 1 WHERE Id_damage = ?", [id_caso])


def buscar_estado_tras_guardar(cursor, id_caso):
    """Fila (completada, id del caso en Operaciones o None, responsabilidad, conciliacion)."""
    cursor.execute("""
            SELECT m.estado_mtto, o.Id_damage,
                   o.responsabilidad_operador,
                   o.conciliacion
            FROM proceso.v_BD6_table_info_mtto m
            LEFT JOIN proceso.v_BD6_table_info_oper o ON o.Id_damage = m.Id_damage
            WHERE m.Id_damage = ?
        """, [id_caso])
    return cursor.fetchone()
