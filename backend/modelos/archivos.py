"""Consultas de los adjuntos de los casos (flota.table_damage_files) y de las
reparaciones (proceso.table_intervenciones_files).

Todos los adjuntos de un caso viven en una sola tabla; la columna calculada
"modulo" dice qué módulo lo subió (sale de su carpeta: Files_ppal, Files_mtto...).
Por eso la descarga filtra por módulo: un adjunto de RRLL no se puede pedir como
si fuera de Operaciones.
"""
from modelos.casos import MODULO_DE_ARCHIVO


def buscar_imagen_de_operaciones(cursor, id_caso, id_archivo):
    """Solo adjuntos del caso y modulo permitidos; bloquea mientras se edita."""
    cursor.execute("""
        SELECT Id, FileName, FilePath FROM flota.table_damage_files WITH (UPDLOCK, HOLDLOCK)
        WHERE Id = ? AND Id_damage = ? AND Modulo = 'Operaciones'
    """, (id_archivo, id_caso))
    return cursor.fetchone()


def eliminar_imagen_de_operaciones(cursor, id_caso, id_archivo):
    cursor.execute("""
        DELETE FROM flota.table_damage_files
        WHERE Id = ? AND Id_damage = ? AND Modulo = 'Operaciones'
    """, (id_archivo, id_caso))
    if cursor.rowcount != 1:
        raise ValueError("La imagen ya no está disponible para eliminar.")


def ruta_tiene_referencias(cursor, ruta):
    cursor.execute("SELECT TOP (1) 1 FROM flota.table_damage_files WHERE FilePath = ?", (ruta,))
    return cursor.fetchone() is not None


def registrar_adjunto_del_caso(cursor, id_caso, nombre, ruta, fecha=None):
    """Anota un adjunto del caso ya escrito en disco (sin fecha: la de la base)."""
    cursor.execute("""
                INSERT INTO flota.table_damage_files (Id_damage, FileName, FilePath, Fecha_subida)
                VALUES (?, ?, ?, COALESCE(?, SYSDATETIME()))
            """, (id_caso, nombre, ruta, fecha))


def buscar_adjunto(cursor, tipo, id_archivo):
    """Fila (ruta_archivo, nombre_archivo, UF de su dueño) del adjunto, o None.

    tipo: operaciones, mtto, svial, laboral (adjuntos del caso) o reparaciones.
    """
    if tipo == "reparaciones":
        cursor.execute("""
                SELECT f.FilePath, f.FileName, CAST(m.UF AS varchar(3))
                FROM proceso.table_intervenciones_files as f
                INNER JOIN proceso.v_BD6_table_intervenciones as i ON i.ID = f.RepairId
                INNER JOIN flota.table_Moviles as m ON m.No_Movil = i.Movil
                WHERE f.Id = ?
            """, (id_archivo,))
        return cursor.fetchone()
    if tipo not in MODULO_DE_ARCHIVO:
        raise ValueError(f"El tipo de adjunto {tipo!r} no es válido.")
    cursor.execute("""
            SELECT f.FilePath, f.FileName, CAST(m.UF AS varchar(3))
            FROM flota.table_damage_files as f
            INNER JOIN flota.v_BD6_table_damage_to_fleet as d ON d.Id_damage = f.Id_damage
            INNER JOIN flota.table_Moviles as m ON m.No_Movil = d.Movil
            WHERE f.Id = ? AND f.Modulo = ?
        """, (id_archivo, MODULO_DE_ARCHIVO[tipo]))
    return cursor.fetchone()
