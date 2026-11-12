"""Consultas de la gestión de Seguridad Vial (proceso.table_info_svial)."""

TABLA = "proceso.table_info_svial"


def existe_gestion(cursor, id_caso):
    """True si el caso ya tiene gestión de Seguridad Vial."""
    cursor.execute("SELECT 1 FROM proceso.v_BD6_table_info_svial WHERE Id_damage = ?", [id_caso])
    return cursor.fetchone() is not None


def buscar_gestion(cursor, id_caso):
    """Fila (observaciones, conciliado_a_favor, valor_conciliado_terceros), o None."""
    cursor.execute("""
                    SELECT Observaciones_svial, conciliado_a_favor, valor_conciliado_terceros
                    FROM proceso.v_BD6_table_info_svial WHERE Id_damage = ?
                """, [id_caso])
    return cursor.fetchone()


def actualizar_gestion(cursor, id_caso, observaciones, usuario, conciliado_a_favor, valor_conciliado):
    """Reemplaza la gestión existente y la marca como hecha."""
    cursor.execute("""
                    UPDATE proceso.table_info_svial
                    SET Observaciones_svial = ?, usuario_id = ?,
                        conciliado_a_favor = NULLIF(?, ''), valor_conciliado_terceros = ?, estado_svial = 1
                    WHERE Id_damage = ?
                """, (observaciones, usuario, conciliado_a_favor, valor_conciliado, id_caso))


def crear_gestion(cursor, valores):
    """Inserta la gestión. valores: [id_caso, observaciones, usuario,
    conciliado_a_favor, valor_conciliado_terceros]."""
    cursor.execute("""
            INSERT INTO proceso.table_info_svial
                (Id_damage, Observaciones_svial, usuario_id,
                 conciliado_a_favor, valor_conciliado_terceros)
            VALUES (?, ?, ?, NULLIF(?, ''), ?)
        """, valores)


def marcar_gestion_hecha(cursor, id_caso):
    cursor.execute("UPDATE proceso.table_info_svial SET estado_svial = 1 WHERE Id_damage = ?", [id_caso])
