"""Consulta del detalle cruzado de un caso (todas las gestiones y sus adjuntos)."""
from modelos.casos import CASO_CON_MOVIL


def _fila_como_diccionario(cursor, fila):
    if fila is None:
        return {}
    columnas = [c[0] for c in cursor.description]
    return dict(zip(columnas, fila))


def _filas_como_lista(cursor, filas):
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in filas]


def buscar_detalle_del_caso(cursor, id_caso):
    """Detalle del caso en una sola ida a la base.

    Devuelve un diccionario con: "principal" (caso y gestiones, columnas planas),
    "eventos_laborales" y las listas de adjuntos "archivos", "archivos_mtto",
    "archivos_svial" y "archivos_laboral".
    """
    cursor.execute(f"""
        SET NOCOUNT ON;

        SELECT
            CAST(m.UF AS varchar(3)) AS UF, d.movil AS Movil,
            d.Codigo AS Codigo, d.Nombre AS Nombre, d.area AS Area,
            d.ruta AS Ruta, m.Tipologia_Movil AS Tipologia, d.version_libre AS Version_libre,
            d.zona_dano AS Zona_dano, d.parte_afectada AS Parte_afectada,
            d.Dano_ocasionado AS Dano_ocasionado, d.Centro_operaciones AS Centro_operaciones,
            d.Registrador AS Registrador, d.direccion AS Direccion,
            o.Observaciones_operaciones AS Observaciones_operaciones, o.rev_error AS rev_error,
            o.observaciones_correctivos AS Observaciones_correctivos, o.responsabilidad_operador,
            o.conciliacion,
            o.costo_oper AS CostoDelDanoOper,
            CASE
                WHEN o.conciliacion = 'SI' OR o.responsabilidad_operador = 'NO APLICA'
                THEN l.Valor_conciliado
            END AS ValorConciliadoOper,
            mt.Costo AS CostoMtto,
            mt.observaciones AS observaciones_mtto,
            mt.dano_adicional,
            s.Observaciones_svial AS Observaciones_svial,
            l.Tipo_cerrado AS Tipo_cerrado,
            l.Valor_conciliado AS Valor_conciliado_laboral
        FROM {CASO_CON_MOVIL}
        LEFT JOIN proceso.v_BD6_table_info_oper AS o ON o.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_mtto AS mt ON mt.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_svial AS s ON s.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_labora AS l ON l.Id_damage = d.Id_damage
        WHERE d.Id_damage = ?;

        SELECT Fecha_presentacion AS Fecha_presentacion, Pendiente_proceso AS Pendiente_proceso,
               Observaciones_rrll AS Observaciones_rrll, Usuario_registro_laboral AS Usuario_registro_laboral,
               Fecha_registro AS Fecha_registro
        FROM proceso.v_BD6_table_info_laboral_mult
        WHERE Id_damage = ?
        ORDER BY Fecha_registro ASC;

        SELECT Id AS Id, FileName AS FileName, 'operaciones' AS TipoArchivo
        FROM flota.table_damage_files WHERE Id_damage = ? AND Modulo = 'Operaciones';
        SELECT Id AS Id, FileName AS FileName, 'mtto' AS TipoArchivo
        FROM flota.table_damage_files WHERE Id_damage = ? AND Modulo = 'Mantenimiento';
        SELECT Id AS Id, FileName AS FileName, 'svial' AS TipoArchivo
        FROM flota.table_damage_files WHERE Id_damage = ? AND Modulo = 'Seguridad vial';
        SELECT Id AS Id, FileName AS FileName, 'laboral' AS TipoArchivo
        FROM flota.table_damage_files WHERE Id_damage = ? AND Modulo = 'Laboral';
    """, [id_caso] * 6)

    detalle = {"principal": _fila_como_diccionario(cursor, cursor.fetchone())}
    for clave in ("eventos_laborales", "archivos", "archivos_mtto", "archivos_svial", "archivos_laboral"):
        cursor.nextset()
        detalle[clave] = _filas_como_lista(cursor, cursor.fetchall())
    return detalle
