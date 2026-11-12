"""Registro de correcciones en proceso.table_auditoria_correcciones.

La misma inserción se repite en todos los módulos de gestión; aquí vive una sola
vez. "tabla" y "campo" son los nombres de la base (por ejemplo
"proceso.table_info_mtto" y "costo"), los mismos que usa el historial.
"""


def registrar_correccion(cursor, id_caso, tabla, campo, valor_anterior, valor_nuevo,
                         usuario, fecha, motivo):
    """Deja constancia de un cambio: qué campo de qué tabla pasó de qué valor a cuál."""
    cursor.execute("""
                INSERT INTO proceso.table_auditoria_correcciones
                (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
                usuario_id, Fecha_Modificacion, Motivo_modificacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (id_caso, tabla, campo, valor_anterior, valor_nuevo, usuario, fecha, motivo))
