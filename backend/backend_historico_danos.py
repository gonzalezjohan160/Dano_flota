from flask import Blueprint, render_template, request, jsonify, send_from_directory, send_file, abort
import os
from mimetypes import guess_type
from io import BytesIO
import pandas as pd
from config import connect
from datetime import datetime, timedelta
from backend_security import login_required, requiere_permiso
from config import BASE_DIR
from pathlib import Path
from config import UPLOAD_FOLDERS

Historico_danos = Blueprint(
    'Historico_danos',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)


# 🔹 Mostrar la tabla principal
@Historico_danos.route('/')
@login_required
@requiere_permiso('Ingresar_historico_danos')
def index():
    conn = connect()
    cursor = conn.cursor()

    # 🔹 Recibir fechas desde parámetros GET
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')

    # Si no envían fechas, por defecto traer los últimos 2 meses
    if not fecha_inicio_str or not fecha_fin_str:
        fecha_fin = datetime.today()
        fecha_inicio = fecha_fin - timedelta(days=62)
        fecha_inicio_str = fecha_inicio.strftime("%Y-%m-%d")
        fecha_fin_str = fecha_fin.strftime("%Y-%m-%d")
    else:
        fecha_inicio = datetime.fromisoformat(fecha_inicio_str)
        fecha_fin = datetime.fromisoformat(fecha_fin_str)
        # Validar máximo 2 meses
        if fecha_fin - fecha_inicio > timedelta(days=62):
            return "El rango de fechas no puede superar 2 meses", 400
        
    filtro_uf = request.args.get('filtro_uf', 'todos')
    filtro_estado = request.args.get('filtro_estado', 'todos')
    filtros = {
        'id': request.args.get('f_id', '').strip(),
        'fecha': request.args.get('f_fecha', '').strip(),
        'movil': request.args.get('f_movil', '').strip(),
        'codigo': request.args.get('f_codigo', '').strip(),
        'nombre': request.args.get('f_nombre', '').strip(),
    }
    try:
        pagina = max(1, int(request.args.get('pagina', 1)))
    except ValueError:
        pagina = 1
    registros_por_pagina = 30

    filtros_sql = ["d.Fecha_evento BETWEEN ? AND ?"]
    parametros = [fecha_inicio_str, fecha_fin_str]
    if filtro_uf in ('10', '16'):
        filtros_sql.append("d.UF = ?")
        parametros.append(filtro_uf)
    if filtro_estado == 'abiertos':
        filtros_sql.append("d.estado_caso = 0")
    elif filtro_estado == 'cerrados':
        filtros_sql.append("d.estado_caso = 1")
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

    # Solo se recupera la página solicitada. Los filtros se aplican antes
    # del OFFSET para no cargar todo el histórico en el navegador.
    query_main = f"""
            SELECT 
                d.Id, d.Fecha_evento, d.Movil, d.Fecha_registro, d.UF, d.Codigo, d.Nombre, d.Ruta,
                d.Tipologia, d.Direccion, d.Version_libre, d.Parte_afectada, d.Dano_ocasionado,
                d.Zona_dano, d.Registrador, d.Centro_operaciones, d.Area,
                (
                    (SELECT COUNT(*) FROM table_damage_files f WHERE f.DamageId = d.Id) +
                    (SELECT COUNT(*) FROM table_mtto_files f WHERE f.DamageToFleetId = d.Id) +
                    (SELECT COUNT(*) FROM table_svial_files f WHERE f.DamageId = d.Id) +
                    (SELECT COUNT(*) FROM table_laboral_files f WHERE f.DamageToFleetId = d.Id)
                ) AS archivos_count
            FROM table_damage_to_fleet d
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
        r['fecha'] = fecha.strftime("%Y-%m-%d") if fecha else None
        del r['Fecha_evento']

        # Fecha registro
        fecha_r = r.get('Fecha_registro')
        if isinstance(fecha_r, datetime):
            r['fecha_r'] = fecha_r.strftime("%d/%m/%Y %H:%M:%S")
        elif isinstance(fecha_r, str):
            try:
                fecha_obj_r = datetime.fromisoformat(fecha_r.split('.')[0])
                r['fecha_r'] = fecha_obj_r.strftime("%d/%m/%Y %H:%M:%S")
            except:
                r['fecha_r'] = r['fecha']  # fallback
        else:
            r['fecha_r'] = None
        del r['Fecha_registro']



    # 🔹 NUEVO: Traer oper, mtto y svial para cada registro
    for r in registros:
        registro_id = r['Id']
        pass
        
        # Operaciones
        cursor.execute("SELECT * FROM table_info_oper WHERE Id_damage_to_fleet = ?", registro_id)
        oper = cursor.fetchall()
        columnas_oper = [col[0] for col in cursor.description]
        r['oper'] = [dict(zip(columnas_oper, row)) for row in oper]  # lista vacía si no hay
        
        # Mantenimiento
        cursor.execute("SELECT * FROM table_info_mtto WHERE Id_damage_to_fleet = ?", registro_id)
        mtto = cursor.fetchall()
        columnas_mtto = [col[0] for col in cursor.description]
        r['mtto'] = [dict(zip(columnas_mtto, row)) for row in mtto]
        
        # Seguridad vial
        cursor.execute("SELECT * FROM table_info_svial WHERE Id_damage_to_fleet = ?", registro_id)
        svial = cursor.fetchall()
        columnas_svial = [col[0] for col in cursor.description]
        r['svial'] = [dict(zip(columnas_svial, row)) for row in svial]

        # Laboral unico
        cursor.execute("SELECT * FROM table_info_labora WHERE Id_damage_to_fleet = ?", registro_id)
        laboral = cursor.fetchall()
        columnas_labora = [col[0] for col in cursor.description]
        r['laboral'] = [dict(zip(columnas_labora, row)) for row in laboral]

        # Laboral multiple
        cursor.execute("SELECT * FROM table_info_laboral_mult WHERE Id_damage_to_fleet = ?", registro_id)
        laboralm = cursor.fetchall()
        columnas_laboralm = [col[0] for col in cursor.description]
        r['laboralm'] = [dict(zip(columnas_laboralm, row)) for row in laboralm]

        # Laboral multiple
        cursor.execute("SELECT * FROM table_auditoria_correcciones WHERE Id_damage = ?", registro_id)
        correcciones = cursor.fetchall()
        columnas_correcciones = [col[0] for col in cursor.description]
        r['correcciones'] = [dict(zip(columnas_correcciones, row)) for row in correcciones]

    conn.close()
    return render_template(
        "Front_historico_danos.html",
        registros=registros,
        pagina=pagina,
        total_registros=total_registros,
        fecha_inicio=fecha_inicio_str,
        fecha_fin=fecha_fin_str,
        filtro_uf=filtro_uf,
        filtro_estado=filtro_estado,
        filtros=filtros
    )
    # Traemos todos los archivos


@Historico_danos.route('/detalle/<int:id_damage>')
def detalle(id_damage):
    conn = connect()
    cursor = conn.cursor()

    # Traer registro principal
    cursor.execute("SELECT * FROM table_damage_to_fleet WHERE Id = ?", (id_damage,))
    registro_main = cursor.fetchone()
    columnas = [col[0] for col in cursor.description]
    registro = dict(zip(columnas, registro_main)) if registro_main else {}

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
        SELECT DamageId, FileName, FilePath, Fecha_subida
        FROM table_damage_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files = [col[0] for col in cursor.description]
    files = [dict(zip(columns_files, row)) for row in cursor.fetchall()]

        # ARCHIVOS LABORAL
    cursor.execute("""
        SELECT DamageToFleetId, FileName, FilePath, Fecha_subida
        FROM table_laboral_files
        WHERE DamageToFleetId = ?
    """, (id_damage,))
    columns_files_laboral = [col[0] for col in cursor.description]
    files_laboral = [dict(zip(columns_files_laboral, row)) for row in cursor.fetchall()]

        # ARCHIVOS MTTO
    cursor.execute("""
        SELECT DamageToFleetId, FileName, FilePath, Fecha_subida
        FROM table_mtto_files
        WHERE DamageToFleetId = ?
    """, (id_damage,))
    columns_files_mtto = [col[0] for col in cursor.description]
    files_mtto = [dict(zip(columns_files_mtto, row)) for row in cursor.fetchall()]

        # ARCHIVOS S. VIAL
    cursor.execute("""
        SELECT DamageId, FileName, FilePath, Fecha_subida
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




# 🔹 Abrir y visualizar archivos adjuntos
@Historico_danos.route('/ver_archivo')
def ver_archivo():
    path = request.args.get('path')
    print(f"[DEBUG] Ruta recibida: {path}")

    if not path:
        return abort(400, "Ruta de archivo no especificada")

    # # Convertir a Path
    path = Path(path).resolve()
    
     # Verificar que pertenezca a alguna carpeta permitida
    permitido = any(
        carpeta.resolve() in path.parents
        for carpeta in UPLOAD_FOLDERS.values()
    )

    if not permitido:
        abort(403)
        
    if not path.is_file():
        print(f"⚠️ Archivo no encontrado: {path}")
        abort(404, description="Archivo no encontrado")

    # Detectar tipo MIME según la extensión
    mime_type, _ = guess_type(str(path))

    try:
        # Si es imagen, video o audio: mostrar directamente en el navegador
        if mime_type and any(t in mime_type for t in ['image', 'video', 'audio']):
            return send_file(path, mimetype=mime_type)
        else:
            # Si es otro tipo (PDF, DOC, ZIP, etc.), ofrecer descarga
            return send_file(path, as_attachment=True)
    except Exception as e:
        print(f"⚠️ Error al enviar archivo: {e}")
        return abort(500, description="Error al abrir el archivo")

@Historico_danos.route('/exportar_excel')
def exportar_excel():

    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')

    if not fecha_inicio_str or not fecha_fin_str:
        return "Debe enviar fecha_inicio y fecha_fin", 400

    # Convertir a datetime
    fecha_inicio = datetime.fromisoformat(fecha_inicio_str)
    fecha_fin = datetime.fromisoformat(fecha_fin_str)

    # Validar que no supere 2 meses
    if fecha_fin - fecha_inicio > timedelta(days=62):  # ~2 meses
        return "El rango de fechas no puede superar 2 meses", 400

    filtro_estado = request.args.get('filtro_estado', 'todos')

    conn = connect()
    cursor = conn.cursor()

    filtros_sql = ["Fecha_evento BETWEEN ? AND ?"]
    parametros = [fecha_inicio_str, fecha_fin_str]
    if filtro_estado == 'abiertos':
        filtros_sql.append("estado_caso = 0")
    elif filtro_estado == 'cerrados':
        filtros_sql.append("estado_caso = 1")

    query = f"""
        SELECT *
        FROM table_damage_to_fleet
        WHERE {' AND '.join(filtros_sql)}
        ORDER BY Id ASC
    """

    cursor.execute(query, parametros)
    columnas = [col[0] for col in cursor.description]
    registros = [dict(zip(columnas, row)) for row in cursor.fetchall()]

    filas_excel = []

    for r in registros:
        registro_id = r["Id"]

        # ================= OPER =================
        cursor.execute("""
            SELECT Observaciones_operaciones, rev_error,
                   Observaciones_correctivos, costo_oper,
                   responsabilidad_operador, conciliacion, Fecha_registro,
                   Usuario_registro_oper
            FROM table_info_oper
            WHERE Id_damage_to_fleet = ?
        """, (registro_id,))
        oper = cursor.fetchone()
        oper = dict(zip([col[0] for col in cursor.description], oper)) if oper else {}

        # ================= MTTO =================
        cursor.execute("""
            SELECT Costo, observaciones, dano_adicional,
                   Fecha_registro, Usuario_registro_mtto
            FROM table_info_mtto
            WHERE Id_damage_to_fleet = ?
        """, (registro_id,))
        mtto = cursor.fetchone()
        mtto = dict(zip([col[0] for col in cursor.description], mtto)) if mtto else {}

        # ================= SVIAL =================
        cursor.execute("""
            SELECT Observaciones_svial, valor_conciliado_terceros,
                   conciliado_a_favor, Fecha_registro,
                   Usuario_registro_svial
            FROM table_info_svial
            WHERE Id_damage_to_fleet = ?
        """, (registro_id,))
        svial = cursor.fetchone()
        svial = dict(zip([col[0] for col in cursor.description], svial)) if svial else {}

        # ================= LABORAL ÚNICO =================
        cursor.execute("""
            SELECT Tipo_cerrado, Valor_conciliado,
                   Fecha_registro, Usuario_registro_labora
            FROM table_info_labora
            WHERE Id_damage_to_fleet = ?
        """, (registro_id,))
        laboral = cursor.fetchone()
        laboral = dict(zip([col[0] for col in cursor.description], laboral)) if laboral else {}

        # ================= LABORAL MÚLTIPLE =================
        cursor.execute("""
            SELECT Fecha_presentacion, Pendiente_proceso,
                   Observaciones_rrll, Fecha_registro,
                   Usuario_registro_laboral
            FROM table_info_laboral_mult
            WHERE Id_damage_to_fleet = ?
        """, (registro_id,))
        columnas_lab = [col[0] for col in cursor.description]
        laboralm = [dict(zip(columnas_lab, row)) for row in cursor.fetchall()]

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
            "OBSERVACIÓNES TECNICAS CONTROL OPERACIONAL": oper.get("Observaciones_operaciones"),
            "LA INFORMACIÓN CARGADA ES CORRECTA?": oper.get("rev_error"),
            "OBSERVACIÓNES DE DILIGENCIAMIENTO ERRONEO": oper.get("Observaciones_correctivos"),
            "FECHA REGISTRO OPERACIONES": oper.get("Fecha_registro"),
            "USUARIO OPERACIONES": oper.get("Usuario_registro_oper"),

            "COSTO DEL DAÑO OPERACIONES": oper.get("costo_oper"),
            "RESPONSABILIDAD DEL OPERADOR": oper.get("responsabilidad_operador"),
            "CONCILIACIÓN OPERACIONES": oper.get("conciliacion"),

            # MTTO
            "COSTO": mtto.get("Costo"),
            "COSTO DE MANTENIMIENTO": mtto.get("Costo"),
            "DAÑO ADICIONAL": mtto.get("dano_adicional"),
            "OBSERVACIONES MTTO": mtto.get("observaciones"),
            "FECHA REGISTRO COSTO": mtto.get("Fecha_registro"),
            "USUARIO MTTO": mtto.get("Usuario_registro_mtto"),

            # SVIAL
            "OBSERVACIONES S. VIAL": svial.get("Observaciones_svial"),
            "FECHA REGISTRO S. VIAL": svial.get("Fecha_registro"),
            "USUARIO S. VIAL": svial.get("Usuario_registro_svial"),

            "VALOR CONCILIADO TERCEROS": svial.get("valor_conciliado_terceros"),
            "CONCILIADO A FAVOR DE": svial.get("conciliado_a_favor"),

            # LABORAL
            "VALOR CONCILIADO": laboral.get("Valor_conciliado"),
            "TIPO DE CIERRE": laboral.get("Tipo_cerrado"),
            "FECHA REGISTRO DEBIDO PROCESO": laboral.get("Fecha_registro"),
            "USUARIO LABORAL": laboral.get("Usuario_registro_labora"),
            "PROCESO LABORAL MÚLTIPLE": proceso_texto.strip()
        }

        filas_excel.append(fila)

    conn.close()

    df = pd.DataFrame(filas_excel)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Historico_Danos")

    output.seek(0)

    return send_file(
        output,
        download_name="Historico_Danos.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

