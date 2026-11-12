"""Consultas del Capturador de daños: registro de un caso nuevo y sus adjuntos."""
from modelos import archivos as modelo_archivos


def contar_eventos_iguales(cursor, fecha_evento, movil, codigo, zona_dano):
    """Cuántos casos hay del mismo día, móvil, código de operador y zona del daño."""
    cursor.execute("""
            SELECT COUNT(*)
            FROM flota.v_BD6_table_damage_to_fleet
            WHERE CONVERT(date, Fecha_evento) = CONVERT(date, ?)
            AND Movil = ?
            AND Codigo = ?
            AND Zona_dano = ?
        """, (fecha_evento, movil, codigo, zona_dano))
    return cursor.fetchone()[0]


def crear_caso(cursor, datos):
    """Inserta el caso en flota.table_damage_to_fleet y devuelve su id.

    datos: diccionario con las claves fecha_evento, movil, uf, codigo, nombre, area,
    ruta, direccion, version_libre, parte_afectada, dano_ocasionado, zona_dano,
    registrador, centro_operaciones y fecha_registro. La UF se valida contra el móvil.
    """
    cursor.execute("""
            INSERT INTO flota.table_damage_to_fleet
            (Fecha_evento, Movil, UF, Codigo, Nombre, Area, Ruta, Direccion,
             Version_libre, Parte_afectada, Dano_ocasionado, Zona_dano, usuario_id,
             Centro_operaciones, Fecha_registro)
            OUTPUT INSERTED.Id_damage
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datos["fecha_evento"], datos["movil"], datos["uf"], datos["codigo"], datos["nombre"],
              datos["area"], datos["ruta"], datos["direccion"],
              datos["version_libre"], datos["parte_afectada"], datos["dano_ocasionado"],
              datos["zona_dano"], datos["registrador"], datos["centro_operaciones"],
              datos["fecha_registro"]))
    return cursor.fetchone()[0]


def registrar_adjunto_del_caso(cursor, id_caso, nombre_archivo, ruta_archivo):
    """Registra un adjunto del caso ya guardado en disco (carpeta Files_ppal)."""
    modelo_archivos.registrar_adjunto_del_caso(cursor, id_caso, nombre_archivo, ruta_archivo)
