from flask import Blueprint, render_template, request, jsonify, send_file, abort, session
from io import BytesIO
import pandas as pd
from config import connect
from datetime import datetime
from fechas import FechaInvalida, leer_rango_fechas, parse_fecha
from logger import logger
from backend_security import (
    login_required,
    requiere_permiso,
    usuario_puede_acceder_uf,
    ufs_autorizadas_sesion,
    puede_ver_adjuntos_laborales,
)
from config import BASE_DIR

Historico_danos = Blueprint(
    'Historico_danos',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)


ESTADOS_HISTORICO = ('abiertos', 'cerrados', 'eliminados')
# Al abrir el módulo no se muestran los casos eliminados.
ESTADOS_POR_DEFECTO = ('abiertos', 'cerrados')
CONDICION_ESTADO = {
    'abiertos': "(ISNULL(d.eliminado, 0) = 0 AND ISNULL(d.estado_caso, 0) = 0)",
    'cerrados': "(ISNULL(d.eliminado, 0) = 0 AND d.estado_caso = 1)",
    'eliminados': "(ISNULL(d.eliminado, 0) = 1)",
}


# Filtro con formato incorrecto; el mensaje se puede mostrar al usuario.
FiltroInvalido = FechaInvalida


def _leer_fechas():
    """Fechas opcionales del evento (AAAA-MM-DD). Vacías = sin filtro de fecha."""
    return leer_rango_fechas(request.args)


def _leer_estados():
    """Estados marcados en las casillas; si no llega ninguno se usan los de por defecto."""
    estados = [e for e in request.args.getlist('estado') if e in ESTADOS_HISTORICO]
    return list(dict.fromkeys(estados)) or list(ESTADOS_POR_DEFECTO)


def _agregar_filtro_fechas(filtros_sql, parametros, fecha_inicio, fecha_fin):
    if fecha_inicio:
        filtros_sql.append("d.Fecha_evento >= ?")
        parametros.append(fecha_inicio)
    if fecha_fin:
        # Incluye todo el día final.
        filtros_sql.append("d.Fecha_evento < DATEADD(day, 1, CAST(? AS date))")
        parametros.append(fecha_fin)


def _agregar_filtro_estados(filtros_sql, estados):
    condiciones = [CONDICION_ESTADO[e] for e in ESTADOS_HISTORICO if e in estados]
    filtros_sql.append("(" + " OR ".join(condiciones) + ")" if condiciones else "1 = 0")


# 🔹 Mostrar la tabla principal
@Historico_danos.route('/')
@login_required
@requiere_permiso('Ingresar_historico_danos')
def index():
    try:
        fecha_inicio, fecha_fin = _leer_fechas()
        fecha_exacta = parse_fecha(request.args.get('f_fecha'), "la columna Fecha")
    except FiltroInvalido as error:
        return str(error), 400
    estados = _leer_estados()

    conn = connect()
    cursor = conn.cursor()

    filtro_uf = request.args.get('filtro_uf', 'todos')
    filtros = {
        'id': request.args.get('f_id', '').strip(),
        'fecha': fecha_exacta.isoformat() if fecha_exacta else '',
        'movil': request.args.get('f_movil', '').strip(),
        'codigo': request.args.get('f_codigo', '').strip(),
        'nombre': request.args.get('f_nombre', '').strip(),
    }
    try:
        pagina = max(1, int(request.args.get('pagina', 1)))
    except ValueError:
        pagina = 1
    registros_por_pagina = 30

    filtros_sql = []
    parametros = []
    _agregar_filtro_fechas(filtros_sql, parametros, fecha_inicio, fecha_fin)
    ufs = ufs_autorizadas_sesion()
    if ufs:
        marcadores = ", ".join("?" for _ in ufs)
        filtros_sql.append(f"d.UF IN ({marcadores})")
        parametros.extend(ufs)
    else:
        filtros_sql.append("1 = 0")
    if filtro_uf in ('10', '16'):
        filtros_sql.append("d.UF = ?")
        parametros.append(filtro_uf)
    _agregar_filtro_estados(filtros_sql, estados)
    if filtros['id']:
        filtros_sql.append("CAST(d.Id AS varchar(20)) LIKE ?")
        parametros.append(f"%{filtros['id']}%")
    if filtros['fecha']:
        filtros_sql.append("CAST(d.Fecha_evento AS date) = ?")
        parametros.append(filtros['fecha'])
    if filtros['movil']:
        filtros_sql.append("d.Movil LIKE ?")
        parametros.append(f"%{filtros['movil']}%")
    if filtros['codigo']:
        filtros_sql.append("d.Codigo LIKE ?")
        parametros.append(f"%{filtros['codigo']}%")
    if filtros['nombre']:
        filtros_sql.append("d.Nombre LIKE ?")
        parametros.append(f"%{filtros['nombre']}%")
    where_sql = " AND ".join(filtros_sql)

    cursor.execute(f"SELECT COUNT(*) FROM table_damage_to_fleet d WHERE {where_sql}", parametros)
    total_registros = cursor.fetchone()[0]
    total_paginas = max(1, (total_registros + registros_por_pagina - 1) // registros_por_pagina)
    pagina = min(pagina, total_paginas)
    desplazamiento = (pagina - 1) * registros_por_pagina

    # Los documentos de RRLL solo cuentan para quien puede abrirlos (M-17).
    conteo_laboral = (
        "(SELECT COUNT(*) FROM table_laboral_files f WHERE f.DamageToFleetId = d.Id)"
        if puede_ver_adjuntos_laborales() else "0"
    )

    # Solo se recupera la página solicitada, en UNA consulta y con las columnas
    # que muestra la tabla (B-12). Los filtros se aplican antes del OFFSET para
    # no cargar todo el histórico; el resto de cada caso lo trae /detalle/<id>.
    query_main = f"""
            SELECT 
                d.Id, d.Fecha_evento, d.Movil, d.Fecha_registro, d.UF, d.Codigo, d.Nombre,
                ISNULL(d.estado_caso, 0) AS estado_caso,
                ISNULL(d.eliminado, 0) AS eliminado,
                CASE WHEN EXISTS (SELECT 1 FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id)
                     THEN 1 ELSE 0 END AS tiene_oper,
                CASE WHEN EXISTS (SELECT 1 FROM table_info_mtto m WHERE m.Id_damage_to_fleet = d.Id)
                     THEN 1 ELSE 0 END AS tiene_mtto,
                CASE WHEN EXISTS (SELECT 1 FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id)
                     THEN 1 ELSE 0 END AS tiene_svial,
                CASE WHEN ISNULL(d.estado_caso, 0) = 1 THEN COALESCE(
                    (SELECT MAX(l.Fecha_registro) FROM table_info_labora l WHERE l.Id_damage_to_fleet = d.Id),
                    cierre_modulos.Fecha_cierre
                ) END AS Fecha_cierre,
                (
                    (SELECT COUNT(*) FROM table_damage_files f WHERE f.DamageId = d.Id) +
                    (SELECT COUNT(*) FROM table_mtto_files f WHERE f.DamageToFleetId = d.Id) +
                    (SELECT COUNT(*) FROM table_svial_files f WHERE f.DamageId = d.Id) +
                    {conteo_laboral}
                ) AS archivos_count
            FROM table_damage_to_fleet d
            OUTER APPLY (
                SELECT MAX(fecha_registro) AS Fecha_cierre
                FROM (
                    SELECT o.Fecha_registro FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id
                    UNION ALL
                    SELECT m.Fecha_registro FROM table_info_mtto m WHERE m.Id_damage_to_fleet = d.Id
                    UNION ALL
                    SELECT s.Fecha_registro FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id
                ) AS fechas_modulos
            ) AS cierre_modulos
            WHERE {where_sql}
            ORDER BY d.Id ASC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cursor.execute(query_main, parametros + [desplazamiento, registros_por_pagina])
    columns = [column[0] for column in cursor.description] 
    registros = [dict(zip(columns, row)) for row in cursor.fetchall()]


    for r in registros:
        # Fecha evento
        fecha = r.get('Fecha_evento')
        r['fecha'] = fecha.strftime("%Y-%m-%d %H:%M:%S") if fecha else None
        r['fecha_datetime'] = fecha

        # Fecha registro
        fecha_r = r.get('Fecha_registro')
        if isinstance(fecha_r, datetime):
            r['fecha_r'] = fecha_r.strftime("%d/%m/%Y %H:%M:%S")
        elif isinstance(fecha_r, str):
            try:
                fecha_obj_r = datetime.fromisoformat(fecha_r.split('.')[0])
                r['fecha_r'] = fecha_obj_r.strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                logger.warning("historico_fecha_registro_invalida id=%s", r.get('Id'))
                r['fecha_r'] = r['fecha']  # se muestra la fecha del evento
        else:
            r['fecha_r'] = None
        del r['Fecha_registro']

        fecha_cierre = r.get('Fecha_cierre')
        if isinstance(fecha_cierre, datetime):
            r['fecha_cierre'] = fecha_cierre.strftime("%d/%m/%Y %H:%M:%S")
        elif isinstance(fecha_cierre, str):
            try:
                fecha_obj_cierre = datetime.fromisoformat(fecha_cierre.split('.')[0])
                r['fecha_cierre'] = fecha_obj_cierre.strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                logger.warning("historico_fecha_cierre_invalida id=%s", r.get('Id'))
                r['fecha_cierre'] = None
        else:
            r['fecha_cierre'] = None
        del r['Fecha_cierre']



    conn.close()
    return render_template(
        "Front_historico_danos.html",
        registros=registros,
        pagina=pagina,
        total_registros=total_registros,
        fecha_inicio=fecha_inicio.isoformat() if fecha_inicio else "",
        fecha_fin=fecha_fin.isoformat() if fecha_fin else "",
        filtro_uf=filtro_uf,
        estados=estados,
        filtros=filtros
    )
    # Traemos todos los archivos


@Historico_danos.route('/detalle/<int:id_damage>')
@login_required
@requiere_permiso('Ingresar_historico_danos')
def detalle(id_damage):
    conn = connect()
    cursor = conn.cursor()

    # Traer registro principal
    cursor.execute("SELECT * FROM table_damage_to_fleet WHERE Id = ?", (id_damage,))
    registro_main = cursor.fetchone()
    columnas = [col[0] for col in cursor.description]
    registro = dict(zip(columnas, registro_main)) if registro_main else {}
    if not registro:
        conn.close()
        abort(404)
    if not usuario_puede_acceder_uf(registro.get("UF")):
        conn.close()
        abort(403)

    # OPERACIONES
    cursor.execute("""
        SELECT Observaciones_operaciones, rev_error, Observaciones_correctivos,
               responsabilidad_operador, conciliacion, costo_oper,
               Fecha_registro, Usuario_registro_oper
        FROM table_info_oper
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    oper = cursor.fetchone()
    if oper:
        oper = dict(zip([col[0] for col in cursor.description], oper))

    # SEGURIDAD VIAL
    cursor.execute("""
        SELECT Observaciones_svial, valor_conciliado_terceros, conciliado_a_favor,
               Fecha_registro, Usuario_registro_svial
        FROM table_info_svial
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    svial = cursor.fetchone()
    if svial:
        svial = dict(zip([col[0] for col in cursor.description], svial))

    # MANTENIMIENTO
    cursor.execute("""
        SELECT Costo, observaciones, dano_adicional, Fecha_registro, Usuario_registro_mtto
        FROM table_info_mtto
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    mtto = cursor.fetchone()
    if mtto:
        mtto = dict(zip([col[0] for col in cursor.description], mtto))

    # LABORAL UNICO
    cursor.execute("""
        SELECT Tipo_cerrado, Valor_conciliado, Fecha_registro, Usuario_registro_labora
        FROM table_info_labora
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    laboral = cursor.fetchone()
    if laboral:
        laboral = dict(zip([col[0] for col in cursor.description], laboral))

    # LABORAL MULTIPLE
    cursor.execute("""
        SELECT Fecha_presentacion, Pendiente_proceso, Observaciones_rrll, Fecha_registro, Usuario_registro_laboral
        FROM table_info_laboral_mult
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))

    columnas_laboralm = [col[0] for col in cursor.description]
    laboralm = [
        dict(zip(columnas_laboralm, row))
        for row in cursor.fetchall()
    ]

    # CORRECCIONES
    cursor.execute("""
        SELECT Tabla_afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo, Usuario_Modifica, Fecha_Modificacion
        FROM table_auditoria_correcciones
        WHERE Id_damage = ?
    """, (id_damage,))

    columnas_correcciones = [col[0] for col in cursor.description]
    correcciones = [
        dict(zip(columnas_correcciones, row))
        for row in cursor.fetchall()
    ]

    # ARCHIVOS
    cursor.execute("""
        SELECT Id, 'operaciones' AS TipoArchivo, FileName, Fecha_subida
        FROM table_damage_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files = [col[0] for col in cursor.description]
    files = [dict(zip(columns_files, row)) for row in cursor.fetchall()]

        # ARCHIVOS LABORAL
    cursor.execute("""
        SELECT Id, 'laboral' AS TipoArchivo, FileName, Fecha_subida
        FROM table_laboral_files
        WHERE DamageToFleetId = ?
    """, (id_damage,))
    columns_files_laboral = [col[0] for col in cursor.description]
    files_laboral = [dict(zip(columns_files_laboral, row)) for row in cursor.fetchall()]
    # Los documentos de Relaciones Laborales solo se listan a RRLL.
    if not puede_ver_adjuntos_laborales():
        files_laboral = []

        # ARCHIVOS MTTO
    cursor.execute("""
        SELECT Id, 'mtto' AS TipoArchivo, FileName, Fecha_subida
        FROM table_mtto_files
        WHERE DamageToFleetId = ?
    """, (id_damage,))
    columns_files_mtto = [col[0] for col in cursor.description]
    files_mtto = [dict(zip(columns_files_mtto, row)) for row in cursor.fetchall()]

        # ARCHIVOS S. VIAL
    cursor.execute("""
        SELECT Id, 'svial' AS TipoArchivo, FileName, Fecha_subida
        FROM table_svial_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files_svial = [col[0] for col in cursor.description]
    files_svial = [dict(zip(columns_files_svial, row)) for row in cursor.fetchall()]


    conn.close()


    return jsonify({
        "registro": registro,
        "oper": oper,
        "svial": svial,
        "mtto": mtto,
        "laboral": laboral,
        "laboralm": laboralm,
        "correcciones": correcciones,
        "archivos": files,
        "archivos_laboral": files_laboral,
        "archivos_mtto": files_mtto,
        "archivos_svial": files_svial
    })




@Historico_danos.route('/exportar_excel')
@login_required
@requiere_permiso('Ingresar_historico_danos')
def exportar_excel():

    es_exportacion_laboral = request.args.get('modulo') == 'laboral'
    if es_exportacion_laboral and 'Ingresar_modulo__laboral' not in session.get('permisos', []):
        abort(403)

    try:
        fecha_inicio, fecha_fin = _leer_fechas()
    except FiltroInvalido as error:
        return str(error), 400

    filtro_uf = request.args.get('filtro_uf', 'todos')
    # Solo RRLL usa filtro_estado (pendientes / gestionados / cerrados).
    filtro_estado = request.args.get('filtro_estado', 'todos')

    # Los casos eliminados nunca se exportan.
    filtros_sql = ["ISNULL(d.eliminado, 0) = 0"]
    parametros = []
    _agregar_filtro_fechas(filtros_sql, parametros, fecha_inicio, fecha_fin)
    ufs = ufs_autorizadas_sesion()
    if ufs:
        marcadores = ", ".join("?" for _ in ufs)
        filtros_sql.append(f"d.UF IN ({marcadores})")
        parametros.extend(ufs)
    else:
        filtros_sql.append("1 = 0")
    if filtro_uf in ('10', '16'):
        filtros_sql.append("d.UF = ?")
        parametros.append(filtro_uf)

    if es_exportacion_laboral:
        # Mismo universo de RRLL que backend_unificado.index(): casos con
        # entrada registrada en RRLL o candidatos pendientes del flujo actual.
        # Se usan EXISTS para no duplicar un caso con varias gestiones RRLL.
        filtros_sql.append("""(
        NOT (
            ISNULL(d.estado_caso, 0) = 0
            AND EXISTS (
                SELECT 1 FROM table_info_oper o_terminal
                WHERE o_terminal.Id_damage_to_fleet = d.Id
                  AND (
                      o_terminal.responsabilidad_operador = 'NO APLICA'
                      OR (
                          o_terminal.responsabilidad_operador = 'SI'
                          AND o_terminal.conciliacion = 'SI'
                          AND o_terminal.costo_oper IS NOT NULL
                      )
                  )
            )
        )
        AND (
            EXISTS (
                SELECT 1 FROM table_info_laboral_mult lm
                WHERE lm.Id_damage_to_fleet = d.Id
            ) OR (
                EXISTS (SELECT 1 FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id)
                AND EXISTS (SELECT 1 FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id)
                AND ISNULL(d.estado_caso, 0) = 0
                AND (
                    EXISTS (
                        SELECT 1 FROM table_info_mtto m2
                        WHERE m2.Id_damage_to_fleet = d.Id
                          AND m2.Usuario_registro_mtto IS NOT NULL
                    )
                    OR EXISTS (
                        SELECT 1 FROM table_info_oper o3
                        WHERE o3.Id_damage_to_fleet = d.Id
                          AND o3.responsabilidad_operador = 'NO'
                    )
                    OR EXISTS (
                        SELECT 1 FROM table_info_oper o4
                        WHERE o4.Id_damage_to_fleet = d.Id
                          AND o4.responsabilidad_operador = 'SI'
                          AND (o4.conciliacion IS NULL OR o4.conciliacion = 'NO')
                    )
                )
            )
        ))""")
    else:
        estados = [e for e in _leer_estados() if e != 'eliminados']
        if not estados:
            return "Los casos eliminados no se incluyen en el Excel. Seleccione Abiertos o Cerrados.", 400
        _agregar_filtro_estados(filtros_sql, estados)

    where_sql = " AND ".join(filtros_sql)

    # Columnas que solo necesita el cálculo del estado de RRLL.
    columnas_laboral = """,
               CASE WHEN EXISTS (
                   SELECT 1 FROM table_info_laboral_mult lm WHERE lm.Id_damage_to_fleet = d.Id
               ) AND EXISTS (
                   SELECT 1 FROM table_info_labora l2 WHERE l2.Id_damage_to_fleet = d.Id
               ) THEN 1 ELSE 0 END AS cerrado_por_laboral,
               ISNULL((SELECT TOP 1 estado_oper FROM table_info_oper o2
                       WHERE o2.Id_damage_to_fleet = d.Id ORDER BY o2.Id DESC), 0) AS estado_oper,
               ISNULL((SELECT TOP 1 estado_mtto FROM table_info_mtto m2
                       WHERE m2.Id_damage_to_fleet = d.Id ORDER BY m2.Fecha_registro DESC), 0) AS estado_mtto,
               ISNULL((SELECT TOP 1 estado_svial FROM table_info_svial s2
                       WHERE s2.Id_damage_to_fleet = d.Id ORDER BY s2.Fecha_registro DESC), 0) AS estado_svial,
               (SELECT TOP 1 lm.Pendiente_proceso FROM table_info_laboral_mult lm
                WHERE lm.Id_damage_to_fleet = d.Id ORDER BY lm.Fecha_registro DESC) AS pendiente_proceso_actual,
               CASE WHEN EXISTS (
                   SELECT 1 FROM table_mtto_files mf WHERE mf.DamageToFleetId = d.Id
               ) THEN 1 ELSE 0 END AS tiene_ot,
               (SELECT MAX(mf.Fecha_subida) FROM table_mtto_files mf
                WHERE mf.DamageToFleetId = d.Id) AS fecha_r_laborales""" if es_exportacion_laboral else ""

    conn = connect()
    try:
        cursor = conn.cursor()
        # Una sola consulta con OUTER APPLY en vez de seis consultas por caso.
        cursor.execute(f"""
            SELECT d.Id, d.Fecha_evento, d.Movil, d.Codigo, d.Nombre, d.Area, d.Ruta,
                   d.Version_libre, d.Zona_dano, d.Parte_afectada, d.Dano_ocasionado,
                   d.Centro_operaciones, d.Registrador, d.Fecha_registro, d.Direccion,
                   ISNULL(d.estado_caso, 0) AS estado_caso,
                   o.Observaciones_operaciones AS oper_observaciones, o.rev_error AS oper_rev_error,
                   o.Observaciones_correctivos AS oper_correctivos, o.costo_oper AS oper_costo,
                   o.responsabilidad_operador AS oper_responsabilidad, o.conciliacion AS oper_conciliacion,
                   o.Fecha_registro AS oper_fecha, o.Usuario_registro_oper AS oper_usuario,
                   m.Costo AS mtto_costo, m.observaciones AS mtto_observaciones,
                   m.dano_adicional AS mtto_dano_adicional, m.Fecha_registro AS mtto_fecha,
                   m.Usuario_registro_mtto AS mtto_usuario,
                   s.Observaciones_svial AS svial_observaciones,
                   s.valor_conciliado_terceros AS svial_valor_terceros,
                   s.conciliado_a_favor AS svial_a_favor, s.Fecha_registro AS svial_fecha,
                   s.Usuario_registro_svial AS svial_usuario,
                   l.Tipo_cerrado AS lab_tipo_cerrado, l.Valor_conciliado AS lab_valor_conciliado,
                   l.Fecha_registro AS lab_fecha, l.Usuario_registro_labora AS lab_usuario
                   {columnas_laboral}
            FROM table_damage_to_fleet d
            OUTER APPLY (
                SELECT TOP 1 Observaciones_operaciones, rev_error, Observaciones_correctivos, costo_oper,
                       responsabilidad_operador, conciliacion, Fecha_registro, Usuario_registro_oper
                FROM table_info_oper WHERE Id_damage_to_fleet = d.Id
            ) o
            OUTER APPLY (
                SELECT TOP 1 Costo, observaciones, dano_adicional, Fecha_registro, Usuario_registro_mtto
                FROM table_info_mtto WHERE Id_damage_to_fleet = d.Id
            ) m
            OUTER APPLY (
                SELECT TOP 1 Observaciones_svial, valor_conciliado_terceros, conciliado_a_favor,
                       Fecha_registro, Usuario_registro_svial
                FROM table_info_svial WHERE Id_damage_to_fleet = d.Id
            ) s
            OUTER APPLY (
                SELECT TOP 1 Tipo_cerrado, Valor_conciliado, Fecha_registro, Usuario_registro_labora
                FROM table_info_labora WHERE Id_damage_to_fleet = d.Id
            ) l
            WHERE {where_sql}
            ORDER BY d.Id ASC
        """, parametros)
        columnas = [col[0] for col in cursor.description]
        registros = [dict(zip(columnas, row)) for row in cursor.fetchall()]

        # Historial de RRLL de todos los casos exportados, en una sola consulta.
        cursor.execute(f"""
            SELECT lm.Id_damage_to_fleet, lm.Fecha_presentacion, lm.Pendiente_proceso,
                   lm.Observaciones_rrll, lm.Fecha_registro, lm.Usuario_registro_laboral
            FROM table_info_laboral_mult lm
            WHERE lm.Id_damage_to_fleet IN (SELECT d.Id FROM table_damage_to_fleet d WHERE {where_sql})
            ORDER BY lm.Id_damage_to_fleet, lm.Fecha_registro
        """, parametros)
        columnas_lab = [col[0] for col in cursor.description]
        laboral_por_caso = {}
        for row in cursor.fetchall():
            item = dict(zip(columnas_lab, row))
            laboral_por_caso.setdefault(item["Id_damage_to_fleet"], []).append(item)
    finally:
        conn.close()

    def estado_rrll(registro):
        caso_cerrado = bool(registro.get("estado_caso"))
        cerrado_por_laboral = bool(registro.get("cerrado_por_laboral"))

        estado_oper = bool(registro.get("estado_oper"))
        estado_mtto = bool(registro.get("estado_mtto"))
        estado_svial = bool(registro.get("estado_svial"))
        tiene_ot = bool(registro.get("tiene_ot"))

        pendiente_proceso = str(
            registro.get("pendiente_proceso_actual") or ""
        ).strip().upper()

        # =========================
        # CERRADOS
        # =========================
        if caso_cerrado and cerrado_por_laboral:
            return "CERRADO"

        # =========================
        # GESTIONADOS
        # =========================
        if (
            not caso_cerrado
            and estado_oper
            and estado_mtto
            and estado_svial
            and pendiente_proceso == "COMPLETO"
        ):
            return "GESTIONADO"

        # =========================
        # PENDIENTES
        # =========================
        if (
            not caso_cerrado
            and estado_oper
            and estado_mtto
            and estado_svial
            and tiene_ot
            and pendiente_proceso != "COMPLETO"
        ):
            return "PENDIENTE"

        # Si no cumple ninguna condición de RRLL,
        # no debe aparecer en la exportación.
        return None

    if es_exportacion_laboral:
        for registro in registros:
            registro["estado_excel"] = estado_rrll(registro)

        estado_por_filtro = {
            "pendientes": "PENDIENTE",
            "gestionados": "GESTIONADO",
            "cerrados": "CERRADO",
        }
        estado_solicitado = estado_por_filtro.get(filtro_estado)
        if estado_solicitado:
            registros = [
                registro for registro in registros
                if registro["estado_excel"] == estado_solicitado
            ]

    def construir_fila(r, laboralm):
        proceso_texto = ""
        for item in laboralm:
            proceso_texto += (
                f"FECHA REGISTRO: {item.get('Fecha_registro','-')} | "
                f"FECHA PRESENTACIÓN: {item.get('Fecha_presentacion','-')} | "
                f"PENDIENTE: {item.get('Pendiente_proceso','-')} | "
                f"OBS: {item.get('Observaciones_rrll','-')} | "
                f"USUARIO: {item.get('Usuario_registro_laboral','-')}\n"
            )

        fila = {
            # PRINCIPAL
            "ID": r.get("Id"),
            "FECHA EVENTO": r.get("Fecha_evento"),
            "MÓVIL": r.get("Movil"),
            "CÓDIGO": r.get("Codigo"),
            "NOMBRE": r.get("Nombre"),
            "ÁREA": r.get("Area"),
            "RUTA": r.get("Ruta"),
            "VERSIÓN LIBRE": r.get("Version_libre"),
            "ZONA DEL DAÑO": r.get("Zona_dano"),
            "PARTE AFECTADA": r.get("Parte_afectada"),
            "DAÑO OCASIONADO POR": r.get("Dano_ocasionado"),
            "CENTRO OPERACIONAL": r.get("Centro_operaciones"),
            "RESPONSABLE DILIGENCIAMIENTO": r.get("Registrador"),
            "FECHA REGISTRO": r.get("Fecha_registro"),
            "DIRECCIÓN": r.get("Direccion"),

            # OPER
            "OBSERVACIÓNES TECNICAS CONTROL OPERACIONAL": r.get("oper_observaciones"),
            "LA INFORMACIÓN CARGADA ES CORRECTA?": r.get("oper_rev_error"),
            "OBSERVACIÓNES DE DILIGENCIAMIENTO ERRONEO": r.get("oper_correctivos"),
            "FECHA REGISTRO OPERACIONES": r.get("oper_fecha"),
            "USUARIO OPERACIONES": r.get("oper_usuario"),

            "COSTO DEL DAÑO OPERACIONES": r.get("oper_costo"),
            "RESPONSABILIDAD DEL OPERADOR": r.get("oper_responsabilidad"),
            "CONCILIACIÓN OPERACIONES": r.get("oper_conciliacion"),

            # MTTO
            "COSTO DE MANTENIMIENTO": r.get("mtto_costo"),
            "DAÑO ADICIONAL": r.get("mtto_dano_adicional"),
            "OBSERVACIONES MTTO": r.get("mtto_observaciones"),
            "FECHA REGISTRO COSTO": r.get("mtto_fecha"),
            "USUARIO MTTO": r.get("mtto_usuario"),

            # SVIAL
            "OBSERVACIONES S. VIAL": r.get("svial_observaciones"),
            "FECHA REGISTRO S. VIAL": r.get("svial_fecha"),
            "USUARIO S. VIAL": r.get("svial_usuario"),

            "VALOR CONCILIADO TERCEROS": r.get("svial_valor_terceros"),
            "CONCILIADO A FAVOR DE": r.get("svial_a_favor"),

            # LABORAL
            "VALOR CONCILIADO CON OPERADOR": r.get("lab_valor_conciliado"),
            "TIPO DE CIERRE": r.get("lab_tipo_cerrado"),
            "FECHA REGISTRO DEBIDO PROCESO": r.get("lab_fecha"),
            "USUARIO LABORAL": r.get("lab_usuario"),
            "FECHA R. LABORALES": r.get("fecha_r_laborales"),
            "PROCESO LABORAL MÚLTIPLE": proceso_texto.strip()
        }

        # ESTADO va al final: el de RRLL en su exportación; Abierto/Cerrado en el histórico.
        if es_exportacion_laboral:
            fila["ESTADO"] = r.get("estado_excel")
        else:
            fila["ESTADO"] = "Cerrado" if r.get("estado_caso") == 1 else "Abierto"
        return fila

    filas_excel = [construir_fila(r, laboral_por_caso.get(r["Id"], [])) for r in registros]
    # Con cero resultados se conservan los encabezados.
    df = pd.DataFrame(filas_excel, columns=list(construir_fila({}, []).keys()))

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Historico_Danos")
        # openpyxl convierte en fórmula todo texto que empiece por "=". Los datos
        # capturados por usuarios se guardan siempre como texto (inyección de fórmulas).
        for fila in writer.sheets["Historico_Danos"].iter_rows():
            for celda in fila:
                if celda.data_type == "f":
                    celda.data_type = "s"

    output.seek(0)

    return send_file(
        output,
        download_name="Historico_Danos.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
