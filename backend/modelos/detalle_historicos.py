"""Lectura y proyeccion comunes del detalle de los dos historicos.

Las proyecciones mantienen las columnas publicas propias de cada pantalla.
La autorizacion de UF y de adjuntos laborales permanece en el controlador.
"""
def _una_fila(cursor):
    fila = cursor.fetchone()
    return dict(zip([col[0] for col in cursor.description], fila)) if fila else None


def _todas_las_filas(cursor):
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def _archivos(cursor, id_damage, modulo, tipo):
    # "modulo" y "tipo" solo llegan de buscar_gestiones_y_adjuntos.
    cursor.execute("""
        SELECT Id AS Id, ? AS TipoArchivo, FileName AS FileName, Fecha_subida AS Fecha_subida
        FROM flota.table_damage_files
        WHERE Id_damage = ? AND Modulo = ?
    """, (tipo, id_damage, modulo))
    return _todas_las_filas(cursor)


def buscar_gestiones_basicas(cursor, id_damage):
    """Operaciones, Seguridad Vial y Mantenimiento, con sus columnas completas."""
    cursor.execute("""
        SELECT Observaciones_operaciones AS Observaciones_operaciones, rev_error AS rev_error,
               observaciones_correctivos AS observaciones_correctivos,
               responsabilidad_operador, conciliacion, costo_oper AS costo_oper,
               Fecha_registro AS Fecha_registro, Usuario_registro_oper AS Usuario_registro_oper
        FROM proceso.v_BD6_table_info_oper
        WHERE Id_damage = ?
    """, (id_damage,))
    oper = _una_fila(cursor)

    cursor.execute("""
        SELECT Observaciones_svial AS Observaciones_svial, valor_conciliado_terceros, conciliado_a_favor,
               Fecha_registro AS Fecha_registro, Usuario_registro_svial AS Usuario_registro_svial
        FROM proceso.v_BD6_table_info_svial
        WHERE Id_damage = ?
    """, (id_damage,))
    svial = _una_fila(cursor)

    cursor.execute("""
        SELECT Costo AS Costo, observaciones, dano_adicional,
               Fecha_registro AS Fecha_registro, Usuario_registro_mtto AS Usuario_registro_mtto
        FROM proceso.v_BD6_table_info_mtto
        WHERE Id_damage = ?
    """, (id_damage,))
    mtto = _una_fila(cursor)

    return {"oper": oper, "svial": svial, "mtto": mtto}


CAMPOS_MOVIL = {
    "oper": ("Observaciones_operaciones", "rev_error", "observaciones_correctivos", "Fecha_registro"),
    "svial": ("Observaciones_svial", "Fecha_registro"),
    "mtto": ("Costo", "observaciones", "dano_adicional", "Fecha_registro"),
}


def detalle_para_movil(cursor, id_damage):
    gestiones = buscar_gestiones_basicas(cursor, id_damage)
    resultado = {
        modulo: {campo: fila.get(campo) for campo in CAMPOS_MOVIL[modulo]} if fila else None
        for modulo, fila in gestiones.items()
    }
    resultado["archivos"] = _archivos(cursor, id_damage, "Operaciones", "operaciones")
    return resultado
