"""Consultas del Capturador de reparaciones: registro de una intervención y sus adjuntos."""


def crear_reparacion(cursor, datos):
    """Inserta la reparación en proceso.table_intervenciones y devuelve su id.

    datos: diccionario con las claves movil, uf, zona_intervenida, parte_intervenida,
    costo, registrador y fecha_registro. La UF se valida contra el móvil.
    """
    cursor.execute("""
            INSERT INTO proceso.table_intervenciones
            (Movil, UF, Zona_intervenida, Parte_intervenida, Costo_intervencion, usuario_id, Fecha_registro, Tipologia)
            OUTPUT INSERTED.ID
            VALUES (?, ?, ?, ?, ?, ?, ?,
                    (SELECT Tipologia_Movil FROM flota.table_Moviles WHERE No_Movil = ? AND UF = ?))
        """, (
            datos["movil"], datos["uf"], datos["zona_intervenida"], datos["parte_intervenida"],
            datos["costo"], datos["registrador"], datos["fecha_registro"], datos["movil"], datos["uf"]
        ))
    return cursor.fetchone()[0]


def registrar_adjunto_de_reparacion(cursor, id_reparacion, nombre_archivo, ruta_archivo):
    """Registra en proceso.table_intervenciones_files un adjunto ya guardado en disco."""
    cursor.execute("""
                    INSERT INTO proceso.table_intervenciones_files
                    (RepairId, FileName, FilePath)
                    VALUES (?, ?, ?)
                """, (id_reparacion, nombre_archivo, ruta_archivo))
