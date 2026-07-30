from flask import (
    Blueprint,
    render_template,
    session,
    request,
    jsonify,
    send_file,
    abort
)
import traceback
import os
import time
from mimetypes import guess_type
from datetime import datetime
from pathlib import Path
from config import connect
from backend_security import login_required
from config import BASE_DIR
from config import UPLOAD_FOLDERS

Modulo_unificado = Blueprint(
    "Modulo_unificado",
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)

# ==========================================================
# CONFIGURACIÓN GENERAL DE LOS MÓDULOS
# ==========================================================

MODULOS = {

    "Operaciones": {
        "titulo": "CONTROL OPERACIONAL",
        "tipo": "oper",
        "permiso": "Ingresar_modulo__oper",
        "campo_principal_label": "CONCEPTO OPERACIONAL DEL DAÑO",
        "propia": "oper",
        "secciones_visibles": ["oper", "mtto", "svial"],
        "mostrar_revision": True,
        "mostrar_observaciones": True,
    },

    "Mtto": {
        "titulo": "MANTENIMIENTO",
        "tipo": "mtto",
        "permiso": "Ingresar_modulo__mtto",
        "campo_principal_label": "COSTO DEL DAÑO",
        "propia": "mtto",
        "secciones_visibles": ["oper", "svial"],
        "mostrar_revision": False,
        "mostrar_observaciones": False,
    },

    "Svial": {
        "titulo": "SEGURIDAD VIAL",
        "tipo": "svial",
        "permiso": "Ingresar_modulo__svial",
        "campo_principal_label": "OBSERVACIONES SEGURIDAD VIAL",
        "propia": "svial",
        "secciones_visibles": ["oper", "mtto"],
        "mostrar_revision": False,
        "mostrar_observaciones": False,
    },

    "laboral": {
        "titulo": "RELACIONES LABORALES",
        "tipo": "laboral",
        "permiso": "Ingresar_modulo__laboral",
        "campo_principal_label": "CONCEPTO RELACIONES LABORALES",
        "propia": "laboral",
        "secciones_visibles": ["oper", "mtto", "svial", "laboral"],
        "mostrar_revision": True,
        "mostrar_observaciones": False,
    }

}


# ==========================================================
# CONFIGURACIÓN DE INSERTS
# ==========================================================

INSERT_CONFIG = {

    # La ruta "agregar_oper" de Operaciones no usa esta config
    # genérica -- ahora tiene lógica propia (ver agregar_operaciones)
    # por el nuevo flujo (valor del daño / responsabilidad / conciliación)
    
    "Operaciones": {
        "ruta": "agregar_oper",
        "sql": """
            INSERT INTO table_info_oper
                (Id_damage_to_fleet, Observaciones_operaciones, Usuario_registro_oper,
                 Observaciones_correctivos, rev_error)
            VALUES(?,?,?,?,?)
        """,
        "campos": [
            {"origen": "id"},
            {"origen": "observaciones_1"},
            {"origen": "usuario"},
            {"origen": "observacionesExtra"},
            {"origen": "Revinf"}
        ],
        # No existe una tabla dedicada de archivos para Operaciones, así
        # que sus evidencias se guardan en la galería general del caso.
        "tabla_files": "table_damage_files",
        "campo_files": "DamageId"
    },

    "Mtto": {
        "ruta": "agregar_mtto",
        "sql": """
            INSERT INTO table_info_mtto
                (Id_damage_to_fleet, Costo, dano_adicional, observaciones, Usuario_registro_mtto)
            VALUES(?,?,?,?,?)
        """,
        "campos": [
            {"origen": "id"},
            {"origen": "Costo"},
            {"origen": "dano_adicional"},
            {"origen": "observaciones"},
            {"origen": "usuario"}
        ],
        "tabla_files": "table_mtto_files",
        "campo_files": "DamageToFleetId"
    },

    "Svial": {
        "ruta": "agregar_svial",
        "sql": """
            INSERT INTO table_info_svial
                (Id_damage_to_fleet, Observaciones_svial, Usuario_registro_svial,
                 conciliado_a_favor, valor_conciliado_terceros)
            VALUES(?,?,?,?,?)
        """,
        "campos": [
            {"origen": "id"},
            {"origen": "Observaciones_svial"},
            {"origen": "usuario"},
            {"origen": "conciliado_a_favor"},
            {"origen": "valor_conciliado_terceros"}
        ],
        "tabla_files": "table_svial_files",
        "campo_files": "DamageId"
    }

}


# ==========================================================
# HELPERS
# ==========================================================

def obtener_filtro_uf():
    user_uf = session.get("UF")
    if user_uf == "TRANSVERSAL":
        return "d.UF IN (10,16)", []
    return "d.UF = ?", [user_uf]


def fila_a_dict(cursor, fila):
    if fila is None:
        return {}
    columnas = [c[0] for c in cursor.description]
    return dict(zip(columnas, fila))


def filas_a_lista(cursor, filas):
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in filas]


def config_publica_modulo(modulo):
    """Config del módulo, apta para mandar al frontend como JSON."""
    cfg = MODULOS[modulo]
    return {
        "modulo": modulo,
        "titulo": cfg["titulo"],
        "tipo": cfg["tipo"],
        "campoPrincipalLabel": cfg["campo_principal_label"],
        "propia": cfg["propia"],
        "seccionesVisibles": cfg["secciones_visibles"],
        "mostrarRevision": cfg["mostrar_revision"],
        "mostrarObservaciones": cfg["mostrar_observaciones"],
    }


def verificar_acceso_modulo(modulo):
    """
    Reemplaza al decorador @requiere_permiso, que no sirve aquí porque
    la ruta es genérica ("/<modulo>") y el decorador se evalúa una sola
    vez al cargar el archivo -- recibiría literalmente el string
    "/<modulo>" en vez del módulo real de cada request.

    Se llama al INICIO de cada vista, después de resolver "modulo".
    Aborta con 404 si el módulo no existe y con 403 si el usuario no
    tiene el permiso correspondiente en sesión.
    """
    if modulo not in MODULOS:
        abort(404)

    permisos = session.get("permisos", [])
    permiso_requerido = MODULOS[modulo]["permiso"]

    if permiso_requerido not in permisos:
        abort(403)


# ==========================================================
# PANTALLA PRINCIPAL — TABLA CON TODOS LOS REGISTROS
# ==========================================================

@Modulo_unificado.route("/<modulo>")
@login_required
def index(modulo):

    verificar_acceso_modulo(modulo)

    CFG = MODULOS[modulo]

    conn = connect()
    cursor = conn.cursor()

    filtro_sql, parametros = obtener_filtro_uf()

   # Filtros a los modulos dependiente del nuevo flujo del proceso de daño a flota


    FILTRO_PENDIENTE_MODULO = {
        "Operaciones": """
            (
                tiene_oper = 0
            )
            OR
            (
                tiene_oper = 1
                AND EXISTS (
                    SELECT 1 FROM table_info_oper o2
                    WHERE o2.Id_damage_to_fleet = base.Id
                      AND (o2.conciliacion = 'SI' OR o2.responsabilidad_operador = 'NO APLICA')
                )
                AND NOT EXISTS (
                    SELECT 1 FROM table_info_labora lb
                    WHERE lb.Id_damage_to_fleet = base.Id AND lb.Cerrado = 'SI'
                )
            )
        """,
        "Mtto": """
            tiene_mtto = 0
            AND EXISTS (
                SELECT 1 FROM table_info_oper om
                WHERE om.Id_damage_to_fleet = base.Id AND om.responsabilidad_operador IS NULL
            )
        """,
        "Svial": "tiene_svial = 0",
        "laboral": """
            tiene_oper = 1 AND tiene_svial = 1 AND laboral_cerrado = 0
            AND (
                EXISTS (
                    SELECT 1 FROM table_info_mtto m2
                    WHERE m2.Id_damage_to_fleet = base.Id AND m2.Usuario_registro_mtto IS NOT NULL
                )
                OR EXISTS (
                    SELECT 1 FROM table_info_oper o3
                    WHERE o3.Id_damage_to_fleet = base.Id AND o3.responsabilidad_operador = 'NO'
                )
                OR EXISTS (
                    SELECT 1 FROM table_info_oper o4
                    WHERE o4.Id_damage_to_fleet = base.Id
                      AND o4.responsabilidad_operador = 'SI'
                      AND (o4.conciliacion IS NULL OR o4.conciliacion = 'NO')
                )
            )
        """,
    }
    filtro_modulo = FILTRO_PENDIENTE_MODULO[modulo]

    query = f"""
        WITH base AS (
            SELECT
                d.Id, d.Fecha_evento, d.Movil, d.Fecha_registro, d.UF, d.Codigo, d.Nombre, d.Ruta,
                d.Tipologia, d.Direccion, d.Version_libre, d.Parte_afectada, d.Dano_ocasionado,
                d.Zona_dano, d.Registrador, d.Centro_operaciones, d.Area,

                (
                    (SELECT COUNT(*) FROM table_damage_files  f  WHERE f.DamageId = d.Id) +
                    (SELECT COUNT(*) FROM table_mtto_files    fm WHERE fm.DamageToFleetId = d.Id) +
                    (SELECT COUNT(*) FROM table_svial_files   fs WHERE fs.DamageId = d.Id) +
                    (SELECT COUNT(*) FROM table_laboral_files fl WHERE fl.DamageToFleetId = d.Id)
                ) AS archivos_count,

                (SELECT COUNT(*) FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id) AS tiene_oper,
                (SELECT COUNT(*) FROM table_info_mtto m WHERE m.Id_damage_to_fleet = d.Id) AS tiene_mtto,
                (SELECT COUNT(*) FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id) AS tiene_svial,
                (SELECT COUNT(*) FROM table_info_labora l WHERE l.Id_damage_to_fleet = d.Id AND l.Cerrado = 'SI') AS laboral_cerrado,

                -- Fecha R. Laborales: la más reciente de las 3 fechas de
                -- registro (Operaciones, Mtto, S.Vial). Solo tiene sentido
                -- una vez que las 3 ya existen (ver filtro de "laboral").
                (
                    SELECT MAX(fecha) FROM (
                        SELECT o.Fecha_registro AS fecha FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id
                        UNION ALL
                        SELECT m.Fecha_registro FROM table_info_mtto m WHERE m.Id_damage_to_fleet = d.Id
                        UNION ALL
                        SELECT s.Fecha_registro FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id
                    ) AS fechas_gestion
                ) AS Fecha_r_laboral

            FROM table_damage_to_fleet d
            WHERE {filtro_sql}
        )
        SELECT * FROM base
        WHERE {filtro_modulo}
        ORDER BY Id DESC
    """

    cursor.execute(query, parametros)
    columnas = [c[0] for c in cursor.description]
    registros = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

    for r in registros:

        fecha = r.get("Fecha_evento")
        r["fecha"] = fecha.strftime("%Y-%m-%d") if fecha else None
        del r["Fecha_evento"]

        fecha_r = r.get("Fecha_registro")
        if isinstance(fecha_r, datetime):
            r["fecha_r"] = fecha_r.strftime("%d/%m/%Y %H:%M:%S")
        else:
            r["fecha_r"] = None
        del r["Fecha_registro"]

        r["tiene_oper"] = bool(r["tiene_oper"])
        r["tiene_mtto"] = bool(r["tiene_mtto"])
        r["tiene_svial"] = bool(r["tiene_svial"])
        r["laboral_cerrado"] = bool(r["laboral_cerrado"])

        fecha_rl = r.get("Fecha_r_laboral")
        if isinstance(fecha_rl, datetime):
            r["fecha_r_laboral"] = fecha_rl.strftime("%d/%m/%Y %H:%M:%S")
        else:
            r["fecha_r_laboral"] = None
        del r["Fecha_r_laboral"]

    conn.close()

    return render_template(
        "Modulo_unificado.html",
        registros=registros,
        titulo_modulo=CFG["titulo"],
        tipo_modulo=CFG["tipo"],
        modulo=modulo,
        modulo_config=config_publica_modulo(modulo)
    )


# ==========================================================
# DETALLE DE UN REGISTRO
# ==========================================================

@Modulo_unificado.route("/<modulo>/detalle/<int:id>")
@login_required
def detalle(modulo, id):

    verificar_acceso_modulo(modulo)

    t0 = time.perf_counter()
    t_etapa = time.perf_counter()
    conn = connect()
    print(f"[DETALLE] Conexión SQL: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")
    cursor = conn.cursor()

    t_etapa = time.perf_counter()
    cursor.execute("""
        SET NOCOUNT ON;

        SELECT
            d.Movil, d.Codigo, d.Nombre, d.Area, d.Ruta, d.Version_libre,
            d.Zona_dano, d.Parte_afectada, d.Dano_ocasionado,
            d.Centro_operaciones, d.Registrador, d.Direccion,
            o.Observaciones_operaciones, o.rev_error,
            o.Observaciones_correctivos, o.responsabilidad_operador,
            o.conciliacion,
            CASE WHEN o.responsabilidad_operador IS NOT NULL THEN m.Costo END AS CostoDelDanoOper,
            CASE
                WHEN o.conciliacion = 'SI' OR o.responsabilidad_operador = 'NO APLICA'
                THEN l.Valor_conciliado
            END AS ValorConciliadoOper,
            m.Costo AS CostoMtto,
            m.observaciones AS observaciones_mtto,
            m.dano_adicional,
            s.Observaciones_svial,
            l.Tipo_cerrado, l.Cerrado,
            l.Valor_conciliado AS Valor_conciliado_laboral
        FROM table_damage_to_fleet d
        OUTER APPLY (
            SELECT TOP 1 Observaciones_operaciones, rev_error,
                   Observaciones_correctivos, responsabilidad_operador, conciliacion
            FROM table_info_oper
            WHERE Id_damage_to_fleet = d.Id
        ) o
        OUTER APPLY (
            SELECT TOP 1 Costo, observaciones, dano_adicional
            FROM table_info_mtto
            WHERE Id_damage_to_fleet = d.Id
        ) m
        OUTER APPLY (
            SELECT TOP 1 Observaciones_svial
            FROM table_info_svial
            WHERE Id_damage_to_fleet = d.Id
        ) s
        OUTER APPLY (
            SELECT TOP 1 Tipo_cerrado, Cerrado, Valor_conciliado
            FROM table_info_labora
            WHERE Id_damage_to_fleet = d.Id
        ) l
        WHERE d.Id = ?;

        SELECT Fecha_presentacion, Pendiente_proceso, Observaciones_rrll,
               Usuario_registro_laboral, Fecha_registro
        FROM table_info_laboral_mult
        WHERE Id_damage_to_fleet = ?
        ORDER BY Fecha_registro ASC;

        SELECT FileName, FilePath FROM table_damage_files WHERE DamageId = ?;
        SELECT FileName, FilePath FROM table_mtto_files WHERE DamageToFleetId = ?;
        SELECT FileName, FilePath FROM table_svial_files WHERE DamageId = ?;
        SELECT FileName, FilePath FROM table_laboral_files WHERE DamageToFleetId = ?;
    """, [id, id, id, id, id, id])
    print(f"[DETALLE] Execute SQL: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    t_etapa = time.perf_counter()
    detalle_principal = fila_a_dict(cursor, cursor.fetchone())
    print(f"[DETALLE] fetch principal: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    registro = {
        campo: detalle_principal.get(campo)
        for campo in (
            "Movil", "Codigo", "Nombre", "Area", "Ruta", "Version_libre",
            "Zona_dano", "Parte_afectada", "Dano_ocasionado",
            "Centro_operaciones", "Registrador", "Direccion"
        )
    }
    oper = {
        campo: detalle_principal.get(campo)
        for campo in (
            "Observaciones_operaciones", "rev_error", "Observaciones_correctivos",
            "responsabilidad_operador",
            "conciliacion", "CostoDelDanoOper", "ValorConciliadoOper"
        )
    }
    mtto = {
        "Costo": detalle_principal.get("CostoMtto"),
        "observaciones": detalle_principal.get("observaciones_mtto"),
        "dano_adicional": detalle_principal.get("dano_adicional")
    }
    svial = {"Observaciones_svial": detalle_principal.get("Observaciones_svial")}
    laboral_estado = {
        "Tipo_cerrado": detalle_principal.get("Tipo_cerrado"),
        "Cerrado": detalle_principal.get("Cerrado"),
        "Valor_conciliado": detalle_principal.get("Valor_conciliado_laboral")
    }

    t_etapa = time.perf_counter()
    cursor.nextset()
    laboral_eventos = filas_a_lista(cursor, cursor.fetchall())
    print(f"[DETALLE] fetch laboral: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    t_etapa = time.perf_counter()
    cursor.nextset()
    archivos = filas_a_lista(cursor, cursor.fetchall())
    print(f"[DETALLE] fetch archivos daño: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    t_etapa = time.perf_counter()
    cursor.nextset()
    archivos_mtto = filas_a_lista(cursor, cursor.fetchall())
    print(f"[DETALLE] fetch archivos mtto: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    t_etapa = time.perf_counter()
    cursor.nextset()
    archivos_svial = filas_a_lista(cursor, cursor.fetchall())
    print(f"[DETALLE] fetch archivos svial: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    t_etapa = time.perf_counter()
    cursor.nextset()
    archivos_laboral = filas_a_lista(cursor, cursor.fetchall())
    print(f"[DETALLE] fetch archivos laboral: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    conn.close()

    t_etapa = time.perf_counter()
    respuesta = {
        "registro": registro,
        "oper": oper,
        "mtto": mtto,
        "svial": svial,
        "laboral": {
            "eventos": laboral_eventos,
            "estado": laboral_estado
        },
        "archivos": archivos,
        "archivos_mtto": archivos_mtto,
        "archivos_svial": archivos_svial,
        "archivos_laboral": archivos_laboral
    }
    print(f"[DETALLE] construir JSON: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")

    t_etapa = time.perf_counter()
    respuesta_json = jsonify(respuesta)
    print(f"[DETALLE] jsonify: {(time.perf_counter() - t_etapa) * 1000:.2f} ms")
    print(f"[DETALLE] TOTAL: {(time.perf_counter() - t0) * 1000:.2f} ms")

    return respuesta_json


# ==========================================================
# VER ARCHIVO
# ==========================================================

@Modulo_unificado.route("/<modulo>/ver_archivo")
@login_required
def ver_archivo(modulo):

    verificar_acceso_modulo(modulo)
    
    

    ruta = request.args.get("path")
    print("[ARCHIVO] ruta recibida:", ruta)
    if not ruta:
        abort(400)
        
    # Convertir rutas guardadas en Windows para que funcionen en Ubuntu/WSL
    if ruta.startswith("C:\\media\\"):
        ruta = "/" + ruta[3:].replace("\\", "/")
    
    print("[ARCHIVO] ruta convertida:", ruta)        

     # Convertir la ruta recibida en un objeto Path y obtener la ruta absoluta
    ruta_archivo = Path(ruta).resolve()
    
    print("[ARCHIVO] ruta resuelta:", ruta_archivo)
    print("[ARCHIVO] existe:", ruta_archivo.is_file())
    
    

    # Verificar que el archivo pertenezca a alguna de las carpetas permitidas
    permitido = any(
        carpeta.resolve() in ruta_archivo.parents
        for carpeta in UPLOAD_FOLDERS.values()
    )
    
    print("[ARCHIVO] permitido:", permitido)
    
    if not permitido:
        abort(403)

    # Verificar que el archivo exista
    if not ruta_archivo.is_file():
        abort(404)

    mime, _ = guess_type(str(ruta_archivo))
   
    try:
        if mime and any(t in mime for t in ["image", "video", "audio"]):
            return send_file(str(ruta_archivo), mimetype=mime)

        return send_file(str(ruta_archivo), as_attachment=True)

    except Exception:
        abort(500)

# ==========================================================
# GUARDAR ARCHIVOS (usada por los inserts)
# ==========================================================

def guardar_archivos(cursor, codigo, tabla_files, campo_id, carpeta_base):
    carpeta = carpeta_base/str(codigo)
    carpeta.mkdir(parents=True, exist_ok=True)

    archivos = request.files.getlist("archivos")

    for archivo in archivos:
        if not archivo.filename:
            continue

        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre = f"{os.path.splitext(archivo.filename)[0]}_{fecha}{os.path.splitext(archivo.filename)[1]}"
        ruta = carpeta / nombre
        archivo.save(str(ruta))

        cursor.execute(f"""
            INSERT INTO {tabla_files} ({campo_id}, FileName, FilePath, Fecha_subida)
            VALUES(?,?,?,?)
        """, (codigo, archivo.filename, str(ruta), datetime.now()))


# ==========================================================
# VERIFICAR REINCIDENCIA DEL OPERADOR (últimos 2 meses)
# ==========================================================
#
# Se consulta desde el formulario de Operaciones cuando la
# responsabilidad del operador es SI o NO (ambas cuentan como
# responsabilidad del operador; "NO APLICA" nunca llama a este
# endpoint), tal como pide el requerimiento.
#
# NOTA: la resta de 2 meses está escrita para SQL Server
# (DATEADD/GETDATE). Si el motor de base de datos real es otro
# (MySQL/Postgres/SQLite), ajustar esta única consulta a la sintaxis
# correspondiente; el resto de la lógica no depende del motor.

def obtener_reincidencia_operador(cursor, id_dano):
    """Cuenta los antecedentes únicos e incluye el evento actual."""
    cursor.execute("""
        SELECT Codigo, Fecha_evento
        FROM table_damage_to_fleet
        WHERE Id = ?
    """, [id_dano])
    fila = cursor.fetchone()

    if not fila or not fila[0] or not fila[1]:
        return 0

    codigo_operador, fecha_evento_actual = fila

    cursor.execute("""
        SELECT COUNT(DISTINCT d.Id)
        FROM table_info_oper o
        JOIN table_damage_to_fleet d ON d.Id = o.Id_damage_to_fleet
        WHERE d.Codigo = ?
          AND d.Id <> ?
          AND o.responsabilidad_operador = 'SI'
          AND d.Fecha_evento >= DATEADD(month, -2, ?)
          AND d.Fecha_evento <= ?
    """, [codigo_operador, id_dano, fecha_evento_actual, fecha_evento_actual])

    # El evento actual se cuenta una vez, incluso antes de guardarse.
    return cursor.fetchone()[0] + 1


@Modulo_unificado.route("/Operaciones/verificar_reincidencia/<int:id>")
@login_required
def verificar_reincidencia_operador(id):

    verificar_acceso_modulo("Operaciones")

    conn = connect()
    cursor = conn.cursor()

    total = obtener_reincidencia_operador(cursor, id)

    conn.close()

    return jsonify({"eventos": total, "bloqueado": total >= 3})


# ==========================================================
# INSERT GENÉRICO — oper / mtto / svial
# ==========================================================

@Modulo_unificado.route("/<modulo>/<accion>", methods=["POST"])
@login_required
def agregar(modulo, accion):

    verificar_acceso_modulo(modulo)

    if modulo == "laboral" and accion == "agregar_rl":
        return agregar_relaciones_laborales()

    if modulo == "Operaciones" and accion == "agregar_oper":
        return agregar_operaciones()

    if modulo == "Operaciones" and accion == "cerrar_caso_oper":
        return cerrar_caso_operaciones()

    if modulo not in INSERT_CONFIG:
        abort(404)

    ICFG = INSERT_CONFIG[modulo]

    if accion != ICFG["ruta"]:
        abort(404)

    id_registro = request.form.get("Id_damage_to_fleet")
    usuario = request.form.get("Usuario_registro_oper")

    if not id_registro:
        return jsonify({"status": "error", "message": "Falta el identificador del registro."}), 400

    valores = []
    for campo in ICFG["campos"]:
        origen = campo["origen"]
        if origen == "id":
            valores.append(id_registro)
        elif origen == "usuario":
            valores.append(usuario)
        else:
            valor = request.form.get(origen)
            if origen == "valor_conciliado_terceros" and valor:
                valor = int(valor.replace(".", "").replace(",", ""))

            valores.append(valor)

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute(ICFG["sql"], valores)
        guardar_archivos(cursor, id_registro, ICFG["tabla_files"], ICFG["campo_files"], UPLOAD_FOLDERS[modulo])
        conn.commit()
    except Exception as error:
        conn.rollback()
        print("\n" + "=" * 80)
        traceback.print_exc()
        print("=" * 80 + "\n")
        conn.close()
        return jsonify({
        "status": "error",
        "message": str(error)
        }), 500
        return jsonify({"status": "error", "message": str(error)}), 500

    conn.close()
    return jsonify({"status": "success", "message": "Registro guardado correctamente."})


# ==========================================================
# INSERT RELACIONES LABORALES (upsert + auditoría)
# ==========================================================

def agregar_relaciones_laborales():
    try:
        codigo = request.form.get("Id_damage_to_fleet")
        observaciones_1 = request.form.get("observaciones_1")
        usuario = request.form.get("Usuario_registro_oper")
        fecha_presentacion = request.form.get("Fecha_presentacion_input")
        estado_caso = request.form.get("Estado_caso")

        rev_inf = request.form.get("Revinf", "NO")
        cerrado = request.form.get("Cerrado_input", "")
        costo = request.form.get("Costo")

        if not codigo or not observaciones_1 or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."})

        conn = connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO table_info_laboral_mult
                (Id_damage_to_fleet, Fecha_presentacion, Pendiente_proceso,
                 Observaciones_rrll, Usuario_registro_laboral, Fecha_registro)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (codigo, fecha_presentacion, estado_caso, observaciones_1, usuario, datetime.now()))

        if rev_inf == "SI":
            cursor.execute(
                "SELECT Tipo_cerrado, Cerrado, Valor_conciliado FROM table_info_labora WHERE Id_damage_to_fleet = ?",
                (codigo,)
            )
            registro_existente = cursor.fetchone()

            if registro_existente:
                campos = {
                    "Tipo_cerrado": (registro_existente[0], cerrado),
                    "Cerrado": (registro_existente[1], rev_inf),
                    "Valor_conciliado": (str(registro_existente[2]), str(costo))
                }

                hubo_cambio = False
                for campo, valores in campos.items():
                    valor_anterior, valor_nuevo = valores
                    if str(valor_nuevo) != str(valor_anterior):
                        hubo_cambio = True
                        cursor.execute("""
                            INSERT INTO table_auditoria_correcciones
                            (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo, Usuario_Modifica, Fecha_Modificacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (codigo, "table_info_labora", campo, str(valor_anterior), str(valor_nuevo), usuario, datetime.now()))

                if hubo_cambio:
                    cursor.execute("""
                        UPDATE table_info_labora
                        SET Tipo_cerrado = ?, Cerrado = ?, Valor_conciliado = ?, Usuario_registro_labora = ?
                        WHERE Id_damage_to_fleet = ?
                    """, (cerrado, rev_inf, costo, usuario, codigo))
            else:
                cursor.execute("""
                    INSERT INTO table_info_labora
                        (Id_damage_to_fleet, Tipo_cerrado, Cerrado, Valor_conciliado, Usuario_registro_labora)
                    VALUES (?, ?, ?, ?, ?)
                """, (codigo, cerrado, rev_inf, costo, usuario))

        conn.commit()

        guardar_archivos(cursor, codigo, "table_laboral_files", "DamageToFleetId", UPLOAD_FOLDERS["laboral"])
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "✅ Información de RRLL y archivos guardados correctamente."})

    except Exception as e:
        print("⚠️ Error al agregar relaciones laborales:", e)
        return jsonify({"status": "error", "message": str(e)})


# ==========================================================
# INSERT OPERACIONES (flujo nuevo: valor del daño / responsabilidad /
# conciliación)
# ==========================================================
#
# Reemplaza el uso de INSERT_CONFIG["Operaciones"] porque el nuevo
# formulario tiene inserts condicionales (a veces se crea/actualiza
# table_info_mtto, a veces no) que el mecanismo genérico no soporta.

def agregar_operaciones():
    try:
        codigo = request.form.get("Id_damage_to_fleet")
        observaciones_1 = request.form.get("observaciones_1")
        usuario = request.form.get("Usuario_registro_oper")
        observaciones_extra = request.form.get("observacionesExtra")
        rev_inf = request.form.get("Revinf", "SI")

        # Pregunta 1: ¿el costo del daño supera $2.000.000?
        costo_supera_2m = request.form.get("costo_supera_2m")  # "SI" / "NO"
        costo_valor = request.form.get("costo_valor")          # solo si NO

        # Solo aplica cuando el costo NO supera los $2.000.000
        responsabilidad_operador = request.form.get("responsabilidad_operador")  # SI / NO / NO APLICA
        conciliacion = request.form.get("conciliacion")  # SI / NO (solo si responsabilidad = SI y no hay reincidencia)
        valor_conciliado_oper = request.form.get("valor_conciliado_oper")  # solo si conciliacion = SI
        if valor_conciliado_oper:
            valor_conciliado_oper = int(
            valor_conciliado_oper.replace(".", "").replace(",", "")
        )

        if not codigo or not observaciones_1 or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."}), 400

        no_supera = (costo_supera_2m == "NO")

        if responsabilidad_operador == "NO APLICA":
            valor_conciliado_oper = None

        conn = None
        conn = connect()
        cursor = conn.cursor()

        bloqueado_reincidencia = (
            no_supera
            and responsabilidad_operador in ("SI", "NO")
            and obtener_reincidencia_operador(cursor, codigo) >= 3
        )

        # La regla se valida nuevamente en el servidor. Aunque el cliente
        # envíe conciliación, un tercer evento no puede terminar allí.
        if bloqueado_reincidencia:
            conciliacion = None

        # La misma gestión puede reenviarse antes de recibir respuesta del
        # navegador. El bloqueo se conserva hasta el commit para que solo
        # exista un registro de Operaciones por cada daño.
        cursor.execute("""
            SELECT 1
            FROM table_info_oper WITH (UPDLOCK, HOLDLOCK)
            WHERE Id_damage_to_fleet = ?
        """, [codigo])
        existe_oper = cursor.fetchone()

        valores_oper = (
            observaciones_1,
            usuario,
            observaciones_extra,
            rev_inf,
            responsabilidad_operador if no_supera else None,
            conciliacion if (no_supera and responsabilidad_operador == "SI") else None
        )

        if existe_oper:
            cursor.execute("""
                UPDATE table_info_oper
                SET Observaciones_operaciones = ?,
                    Usuario_registro_oper = ?,
                    Observaciones_correctivos = ?,
                    rev_error = ?,
                    responsabilidad_operador = ?,
                    conciliacion = ?
                WHERE Id_damage_to_fleet = ?
            """, valores_oper + (codigo,))
        else:
            cursor.execute("""
                INSERT INTO table_info_oper
                    (Id_damage_to_fleet, Observaciones_operaciones, Usuario_registro_oper,
                     Observaciones_correctivos, rev_error, responsabilidad_operador, conciliacion)
                VALUES (?,?,?,?,?,?,?)
            """, (codigo,) + valores_oper)

        # Si el costo NO supera los $2.000.000, Operaciones guarda (o
        # reutiliza) el costo en table_info_mtto. Esto NO implica que el
        # caso vaya a Mantenimiento -- de hecho, al existir ya el
        # registro, el filtro de la bandeja de Mantenimiento
        # (tiene_mtto = 0) lo excluye automáticamente.
        if no_supera:
            cursor.execute(
                "SELECT Id_damage_to_fleet FROM table_info_mtto WHERE Id_damage_to_fleet = ?",
                [codigo]
            )
            existe_mtto = cursor.fetchone()

            if existe_mtto:
                cursor.execute("""
                    UPDATE table_info_mtto SET Costo = ? WHERE Id_damage_to_fleet = ?
                """, (costo_valor, codigo))
            else:
                cursor.execute("""
                    INSERT INTO table_info_mtto (Id_damage_to_fleet, Costo)
                    VALUES (?, ?)
                """, (codigo, costo_valor))

        # Si hubo conciliación, o si el operador respondió "NO APLICA"
        # (mismo tratamiento: el caso termina en Operaciones), el valor
        # se guarda reutilizando exactamente la misma columna que usa
        # Relaciones Laborales (table_info_labora.Valor_conciliado), tal
        # como pide el requerimiento -- no se crea una columna nueva.
        termina_en_operaciones = not bloqueado_reincidencia and no_supera and (
            (responsabilidad_operador == "SI" and conciliacion == "SI")
            or responsabilidad_operador == "NO APLICA"
        )

        if termina_en_operaciones:
            cursor.execute(
                "SELECT Id_damage_to_fleet FROM table_info_labora WHERE Id_damage_to_fleet = ?",
                [codigo]
            )
            existe_labora = cursor.fetchone()

            if existe_labora:
                cursor.execute("""
                    UPDATE table_info_labora SET Valor_conciliado = ? WHERE Id_damage_to_fleet = ?
                """, (valor_conciliado_oper, codigo))
            else:
                cursor.execute("""
                    INSERT INTO table_info_labora
                        (Id_damage_to_fleet, Tipo_cerrado, Cerrado, Valor_conciliado, Usuario_registro_labora)
                    VALUES (?, ?, ?, ?, ?)
                """, (codigo, "CONCILIACIÓN", "NO", valor_conciliado_oper, usuario))

        guardar_archivos(cursor, codigo, "table_damage_files", "DamageId", UPLOAD_FOLDERS["Operaciones"])

        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Registro guardado correctamente.",
            "bloqueado_reincidencia": bloqueado_reincidencia
        })

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        print("⚠️ Error al agregar operaciones:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================================
# CERRAR CASO DESDE OPERACIONES (solo cuando hubo conciliación)
# ==========================================================
#
# Reutiliza exactamente la misma tabla/lógica de cierre que usa hoy
# Relaciones Laborales (table_info_labora), tal como pide el
# requerimiento -- no se crea una lógica de cierre distinta.

def cerrar_caso_operaciones():
    try:
        codigo = request.form.get("Id_damage_to_fleet")
        usuario = request.form.get("Usuario_registro_oper")

        if not codigo or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."}), 400

        conn = None
        conn = connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 1 responsabilidad_operador
            FROM table_info_oper
            WHERE Id_damage_to_fleet = ?
        """, [codigo])
        fila_oper = cursor.fetchone()
        responsabilidad_operador = fila_oper[0] if fila_oper else None

        if (responsabilidad_operador in ("SI", "NO") and
                obtener_reincidencia_operador(cursor, codigo) >= 3):
            conn.close()
            return jsonify({
                "status": "error",
                "message": "El operador ya registra 3 eventos con responsabilidad dentro de un período de 2 meses. El caso debe ser remitido a Relaciones Laborales."
            })

        # Seguridad Vial debe haber dado su concepto antes de poder
        # cerrar el caso desde Operaciones. Si no, el caso permanece
        # exactamente igual (no se realiza ningún cambio).
        cursor.execute(
            "SELECT 1 FROM table_info_svial WHERE Id_damage_to_fleet = ?",
            [codigo]
        )
        if not cursor.fetchone():
            conn.close()
            return jsonify({"status": "error", "message": "No es posible cerrar el caso porque Seguridad Vial aún no ha emitido un concepto."})

        cursor.execute(
            "SELECT Id_damage_to_fleet, Valor_conciliado FROM table_info_labora WHERE Id_damage_to_fleet = ?",
            [codigo]
        )
        existente = cursor.fetchone()

        # El valor conciliado ya fue guardado por Operaciones al llegar a
        # conciliación (o al responder "NO APLICA"), reutilizando la misma
        # columna que usa Relaciones Laborales. Si el usuario lo modificó
        # justo antes de cerrar (sin pasar antes por "Guardar
        # información"), se usa ese valor recién enviado. Si por algún
        # motivo no hay ninguno, se usa como respaldo el costo del daño
        # ya registrado (comportamiento anterior).
        valor_conciliado_form = request.form.get("valor_conciliado_oper")

        if valor_conciliado_form:
            valor_conciliado = valor_conciliado_form
        elif existente and existente[1] is not None:
            valor_conciliado = existente[1]
        else:
            cursor.execute(
                "SELECT Costo FROM table_info_mtto WHERE Id_damage_to_fleet = ?",
                [codigo]
            )
            fila_costo = cursor.fetchone()
            valor_conciliado = fila_costo[0] if fila_costo else None

        if existente:
            cursor.execute("""
                UPDATE table_info_labora
                SET Tipo_cerrado = ?, Cerrado = ?, Valor_conciliado = ?, Usuario_registro_labora = ?
                WHERE Id_damage_to_fleet = ?
            """, ("CONCILIACIÓN", "SI", valor_conciliado, usuario, codigo))
        else:
            cursor.execute("""
                INSERT INTO table_info_labora
                    (Id_damage_to_fleet, Tipo_cerrado, Cerrado, Valor_conciliado, Usuario_registro_labora)
                VALUES (?, ?, ?, ?, ?)
            """, (codigo, "CONCILIACIÓN", "SI", valor_conciliado, usuario))

        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "✅ Caso cerrado correctamente."})

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        print("⚠️ Error al cerrar caso desde Operaciones:", e)
        return jsonify({"status": "error", "message": str(e)}), 500