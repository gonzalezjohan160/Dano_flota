from flask import (
    Blueprint,
    render_template,
    session,
    request,
    jsonify,
    send_file,
    abort
)

import os
from mimetypes import guess_type
from datetime import datetime

from config import connect
from backend_security import login_required


Modulo_unificado = Blueprint(
    "Modulo_unificado",
    __name__,
    template_folder=r"..\frontend",
    static_folder=r"..\Static"
)


UPLOAD_FOLDERS = {
    "Operaciones": r"C:\media\emapp\dano_flota\Files\Files_ppal",
    "Mtto": r"C:\media\emapp\dano_flota\Files\Files_mtto",
    "Svial": r"C:\media\emapp\dano_flota\Files\Files_svial",
    "laboral": r"C:\media\emapp\dano_flota\Files\Files_laboral",
}

for carpeta in UPLOAD_FOLDERS.values():
    os.makedirs(carpeta, exist_ok=True)


# ==========================================================
# CONFIGURACIÓN GENERAL DE LOS MÓDULOS
#
# Esta es la ÚNICA fuente de verdad sobre qué puede ver y
# hacer cada módulo. Se envía tal cual al HTML (como JSON) y
# el JS unificado (Script_oper.js) la usa para pintar la
# tabla, el modal de detalle y el formulario, en vez de tener
# una copia hardcodeada separada que se puede desincronizar.
#
# claves de "secciones": las mismas 4 que existen en la BD:
#   oper | mtto | svial | laboral
#
# "secciones_visibles" -> qué secciones puede VER el módulo en
#                          el modal de detalle (solo lectura,
#                          salvo la propia)
# "propia"              -> la sección que este módulo diligencia
#                          (habilita su formulario de "Añadir info")
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
        "secciones_visibles": ["oper", "mtto", "svial"],
        "mostrar_revision": False,
        "mostrar_observaciones": False,
    },

    "Svial": {
        "titulo": "SEGURIDAD VIAL",
        "tipo": "svial",
        "permiso": "Ingresar_modulo__svial",
        "campo_principal_label": "OBSERVACIONES SEGURIDAD VIAL",
        "propia": "svial",
        "secciones_visibles": ["oper", "mtto", "svial"],
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
# CONFIGURACIÓN DE INSERTS (secciones "simples": oper, mtto,
# svial). RelacionesLaborales (clave "laboral") tiene su propia
# lógica más abajo porque hace upsert + auditoría.
# ==========================================================

INSERT_CONFIG = {

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
                (Id_damage_to_fleet, Costo, Usuario_registro_mtto)
            VALUES(?,?,?)
        """,
        "campos": [
            {"origen": "id"},
            {"origen": "Costo"},
            {"origen": "usuario"}
        ],
        "tabla_files": "table_mtto_files",
        "campo_files": "DamageToFleetId"
    },

    "Svial": {
        "ruta": "agregar_svial",
        "sql": """
            INSERT INTO table_info_svial
                (Id_damage_to_fleet, Observaciones_svial, Usuario_registro_svial)
            VALUES(?,?,?)
        """,
        "campos": [
            {"origen": "id"},
            {"origen": "Observaciones_svial"},
            {"origen": "usuario"}
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
#
# A diferencia de la versión anterior, aquí YA NO se excluyen
# los registros que ya tienen info de un módulo: la tabla
# muestra TODO. Las restricciones de qué puede hacer cada
# módulo se aplican en el frontend usando la config de arriba
# y los indicadores "tiene_oper/tiene_mtto/tiene_svial/
# laboral_cerrado" que se calculan aquí.
# ==========================================================

@Modulo_unificado.route("/<modulo>")
@login_required
def index(modulo):

    verificar_acceso_modulo(modulo)

    CFG = MODULOS[modulo]

    conn = connect()
    cursor = conn.cursor()

    filtro_sql, parametros = obtener_filtro_uf()

    # Una vez que el módulo dueño de una sección ya diligenció su
    # información, el registro deja de aparecer en SU tabla (ya queda
    # visible en el histórico de daños). En Relaciones Laborales el
    # criterio es distinto: el registro sigue apareciendo mientras el
    # caso siga abierto, y desaparece solo cuando se cierra.
    FILTRO_PENDIENTE_MODULO = {
        "Operaciones": "tiene_oper = 0",
        "Mtto": "tiene_mtto = 0",
        "Svial": "tiene_svial = 0",
        "laboral": "laboral_cerrado = 0",
    }
    filtro_modulo = FILTRO_PENDIENTE_MODULO[modulo]

    query = f"""
        WITH base AS (
            SELECT
                d.Id, d.Fecha_evento, d.Movil, d.Fecha_registro, d.UF, d.Codigo, d.Nombre, d.Ruta,
                d.Tipologia, d.Direccion, d.Version_libre, d.Parte_afectada, d.Dano_ocasionado,
                d.Zona_dano, d.Registrador, d.Centro_operaciones, d.Area,

                (SELECT COUNT(*) FROM table_damage_files f WHERE f.DamageId = d.Id) AS archivos_count,

                (SELECT COUNT(*) FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id) AS tiene_oper,
                (SELECT COUNT(*) FROM table_info_mtto m WHERE m.Id_damage_to_fleet = d.Id) AS tiene_mtto,
                (SELECT COUNT(*) FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id) AS tiene_svial,
                (SELECT COUNT(*) FROM table_info_labora l WHERE l.Id_damage_to_fleet = d.Id AND l.Cerrado = 'SI') AS laboral_cerrado

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
# DETALLE DE UN REGISTRO (modal de adjuntos / info cruzada)
#
# Siempre devuelve las 4 secciones (oper, mtto, svial,
# laboral); el frontend decide, según "seccionesVisibles" de
# la config del módulo, cuáles pintar.
# ==========================================================

@Modulo_unificado.route("/<modulo>/detalle/<int:id>")
@login_required
def detalle(modulo, id):

    verificar_acceso_modulo(modulo)

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            Movil, Codigo, Nombre, Area, Ruta, Version_libre, Zona_dano,
            Parte_afectada, Dano_ocasionado, Centro_operaciones, Registrador, Direccion
        FROM table_damage_to_fleet
        WHERE Id = ?
    """, [id])
    registro = fila_a_dict(cursor, cursor.fetchone())

    cursor.execute("""
        SELECT Observaciones_operaciones, rev_error, Observaciones_correctivos
        FROM table_info_oper WHERE Id_damage_to_fleet = ?
    """, [id])
    oper = fila_a_dict(cursor, cursor.fetchone())

    cursor.execute("""
        SELECT Costo, observaciones, dano_adicional
        FROM table_info_mtto WHERE Id_damage_to_fleet = ?
    """, [id])
    mtto = fila_a_dict(cursor, cursor.fetchone())

    cursor.execute("""
        SELECT Observaciones_svial
        FROM table_info_svial WHERE Id_damage_to_fleet = ?
    """, [id])
    svial = fila_a_dict(cursor, cursor.fetchone())

    # Relaciones laborales: tabla de eventos múltiples + estado de cierre
    cursor.execute("""
        SELECT Fecha_presentacion, Pendiente_proceso, Observaciones_rrll,
               Usuario_registro_laboral, Fecha_registro
        FROM table_info_laboral_mult
        WHERE Id_damage_to_fleet = ?
        ORDER BY Fecha_registro ASC
    """, [id])
    laboral_eventos = filas_a_lista(cursor, cursor.fetchall())

    cursor.execute("""
        SELECT Tipo_cerrado, Cerrado, Valor_conciliado
        FROM table_info_labora WHERE Id_damage_to_fleet = ?
    """, [id])
    laboral_estado = fila_a_dict(cursor, cursor.fetchone())

    cursor.execute("""
        SELECT FileName, FilePath FROM table_damage_files WHERE DamageId = ?
    """, [id])
    archivos = filas_a_lista(cursor, cursor.fetchall())

    cursor.execute("""
        SELECT FileName, FilePath FROM table_mtto_files WHERE DamageToFleetId = ?
    """, [id])
    archivos_mtto = filas_a_lista(cursor, cursor.fetchall())

    cursor.execute("""
        SELECT FileName, FilePath FROM table_svial_files WHERE DamageId = ?
    """, [id])
    archivos_svial = filas_a_lista(cursor, cursor.fetchall())

    cursor.execute("""
        SELECT FileName, FilePath FROM table_laboral_files WHERE DamageToFleetId = ?
    """, [id])
    archivos_laboral = filas_a_lista(cursor, cursor.fetchall())

    conn.close()

    return jsonify({
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
    })


# ==========================================================
# VER ARCHIVO
# ==========================================================

@Modulo_unificado.route("/<modulo>/ver_archivo")
@login_required
def ver_archivo(modulo):

    verificar_acceso_modulo(modulo)

    ruta = request.args.get("path")
    if not ruta:
        abort(400)

    ruta_normalizada = os.path.normpath(ruta)

    # Solo se sirven archivos que estén dentro de alguna de las
    # carpetas de subida conocidas (evita que "path" apunte a
    # cualquier archivo del sistema).
    dentro_de_carpeta_permitida = any(
        ruta_normalizada.startswith(os.path.normpath(carpeta))
        for carpeta in UPLOAD_FOLDERS.values()
    )
    if not dentro_de_carpeta_permitida:
        abort(403)

    if not os.path.isfile(ruta_normalizada):
        abort(404)

    mime, _ = guess_type(ruta_normalizada)

    try:
        if mime and any(t in mime for t in ["image", "video", "audio"]):
            return send_file(ruta_normalizada, mimetype=mime)
        return send_file(ruta_normalizada, as_attachment=True)
    except Exception:
        abort(500)


# ==========================================================
# GUARDAR ARCHIVOS (usada por los inserts)
# ==========================================================

def guardar_archivos(cursor, codigo, tabla_files, campo_id, carpeta_base):
    carpeta = os.path.join(carpeta_base, str(codigo))
    os.makedirs(carpeta, exist_ok=True)

    archivos = request.files.getlist("archivos")

    for archivo in archivos:
        if not archivo.filename:
            continue

        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre = f"{os.path.splitext(archivo.filename)[0]}_{fecha}{os.path.splitext(archivo.filename)[1]}"
        ruta = os.path.join(carpeta, nombre)
        archivo.save(ruta)

        cursor.execute(f"""
            INSERT INTO {tabla_files} ({campo_id}, FileName, FilePath, Fecha_subida)
            VALUES(?,?,?,?)
        """, (codigo, archivo.filename, ruta, datetime.now()))


# ==========================================================
# INSERT GENÉRICO — oper / mtto / svial
# ==========================================================

@Modulo_unificado.route("/<modulo>/<accion>", methods=["POST"])
@login_required
def agregar(modulo, accion):

    verificar_acceso_modulo(modulo)

    if modulo == "laboral" and accion == "agregar_rl":
        return agregar_relaciones_laborales()

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
            valores.append(request.form.get(origen))

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute(ICFG["sql"], valores)
        guardar_archivos(cursor, id_registro, ICFG["tabla_files"], ICFG["campo_files"], UPLOAD_FOLDERS[modulo])
        conn.commit()
    except Exception as error:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(error)}), 500

    conn.close()
    return jsonify({"status": "success", "message": "Registro guardado correctamente."})


# ==========================================================
# INSERT RELACIONES LABORALES (upsert + auditoría)
# Traído tal cual de backend_laboral.py, adaptado a la ruta
# unificada /laboral/agregar_rl
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