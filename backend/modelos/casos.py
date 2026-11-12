"""Consultas sobre el caso (flota.table_damage_to_fleet) que comparten los módulos de gestión.

Estado del caso para validar UF y apertura, estado de las gestiones para el cierre
automático, cierre y reapertura del caso.

La UF y la tipología no se guardan en el caso: son las de su móvil (flota.table_Moviles).
"""

# Caso unido a su móvil, para leer la UF y la tipología.
CASO_CON_MOVIL = "flota.v_BD6_table_damage_to_fleet AS d INNER JOIN flota.table_Moviles AS m ON m.No_Movil = d.movil"

# Columnas del caso con los nombres que usan las pantallas, el JSON y el Excel
# (los mismos de antes del cambio de nombres de la base; ver migración 008).
COLUMNAS_DEL_CASO = """
    d.Id_damage AS Id, d.fecha_evento AS Fecha_evento, CAST(m.UF AS varchar(3)) AS UF,
    d.movil AS Movil, d.Codigo AS Codigo, d.Nombre AS Nombre, d.ruta AS Ruta,
    m.Tipologia_Movil AS Tipologia, d.direccion AS Direccion, d.version_libre AS Version_libre,
    d.parte_afectada AS Parte_afectada, d.Dano_ocasionado AS Dano_ocasionado, d.zona_dano AS Zona_dano,
    d.Registrador AS Registrador, d.Centro_operaciones AS Centro_operaciones,
    d.fecha_registro AS Fecha_registro, d.area AS Area, d.franja_horaria,
    d.estado_caso AS estado_caso, d.eliminado"""

# Archivo de un caso según el módulo que lo subió (columna calculada flota.table_damage_files.modulo).
MODULO_DE_ARCHIVO = {
    "operaciones": "Operaciones",
    "mtto": "Mantenimiento",
    "svial": "Seguridad vial",
    "laboral": "Laboral",
}


def buscar_estado_del_caso(cursor, id_caso):
    """Fila (UF, eliminado, cerrado) del caso, o None si no existe."""
    cursor.execute(f"""
            SELECT CAST(m.UF AS varchar(3)), d.eliminado, d.estado_caso
            FROM {CASO_CON_MOVIL}
            WHERE d.Id_damage = ?
        """, [id_caso])
    return cursor.fetchone()


def buscar_estado_de_gestiones(cursor, id_caso):
    """Fila (responsabilidad, conciliacion, estado_oper, estado_mtto, estado_svial,
    tiene_ot, tiene_cierre_laboral) del caso, o None si Operaciones no lo ha gestionado."""
    cursor.execute("""
        SELECT o.responsabilidad_operador, o.conciliacion,
               o.estado_oper, ISNULL(m.estado_mtto, 0),
               ISNULL(s.estado_svial, 0),
               CASE WHEN EXISTS (
                   SELECT 1 FROM flota.table_damage_files mf
                   WHERE mf.Id_damage = o.Id_damage AND mf.Modulo = 'Mantenimiento'
               ) THEN 1 ELSE 0 END,
               CASE WHEN EXISTS (
                   SELECT 1 FROM proceso.v_BD6_table_info_labora l
                   WHERE l.Id_damage = o.Id_damage
                     AND NULLIF(LTRIM(RTRIM(l.Tipo_cerrado)), '') IS NOT NULL
               ) THEN 1 ELSE 0 END
        FROM proceso.v_BD6_table_info_oper o
        LEFT JOIN proceso.v_BD6_table_info_mtto m ON m.Id_damage = o.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_svial s ON s.Id_damage = o.Id_damage
        WHERE o.Id_damage = ?
    """, [id_caso])
    return cursor.fetchone()


def marcar_mantenimiento_pendiente_de_ot(cursor, id_caso):
    """Devuelve la gestión de Mantenimiento a pendiente (falta la orden de trabajo)."""
    cursor.execute(
        "UPDATE proceso.table_info_mtto SET estado_mtto = 0 WHERE Id_damage = ?",
        [id_caso]
    )


def marcar_caso_cerrado(cursor, id_caso):
    """Deja el caso cerrado."""
    cursor.execute("UPDATE flota.table_damage_to_fleet SET estado_caso = 1 WHERE Id_damage = ?", [id_caso])


def marcar_caso_abierto(cursor, id_caso):
    """Deja el caso abierto."""
    cursor.execute("UPDATE flota.table_damage_to_fleet SET estado_caso = 0 WHERE Id_damage = ?", [id_caso])


def buscar_estado_para_reabrir(cursor, id_caso, desde_laboral):
    """Fila (UF, cerrado, cerrado_por_laboral) de un caso no eliminado, o None.

    Desde Operaciones la tercera columna siempre vale 1; desde RRLL indica si el
    cierre lo hizo Relaciones Laborales (tiene historial y registro de cierre).
    """
    if desde_laboral:
        cursor.execute(f"""
                SELECT CAST(m.UF AS varchar(3)), d.estado_caso,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM proceso.v_BD6_table_info_laboral_mult lm
                           WHERE lm.Id_damage = d.Id_damage
                       ) AND EXISTS (
                           SELECT 1 FROM proceso.v_BD6_table_info_labora l
                           WHERE l.Id_damage = d.Id_damage
                       ) THEN 1 ELSE 0 END
                FROM {CASO_CON_MOVIL}
                WHERE d.Id_damage = ? AND d.eliminado = 0
            """, [id_caso])
    else:
        cursor.execute(f"""
                SELECT CAST(m.UF AS varchar(3)), d.estado_caso, 1
                FROM {CASO_CON_MOVIL}
                WHERE d.Id_damage = ? AND d.eliminado = 0
            """, [id_caso])
    return cursor.fetchone()


def buscar_caso_completo(cursor, id_caso):
    """Caso y UF de su movil; diccionario vacio si no existe."""
    cursor.execute(
        f"SELECT {COLUMNAS_DEL_CASO} FROM {CASO_CON_MOVIL} WHERE d.Id_damage = ?",
        (id_caso,),
    )
    fila = cursor.fetchone()
    return dict(zip((c[0] for c in cursor.description), fila)) if fila else {}
