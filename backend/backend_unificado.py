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
import json
from mimetypes import guess_type
from datetime import datetime
from pathlib import Path
from config import connect
from backend_security import login_required, requiere_permiso
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
        "secciones_visibles": ["oper","mtto", "svial"],
        "mostrar_revision": False,
        "mostrar_observaciones": False,
    },

    "Svial": {
        "titulo": "SEGURIDAD VIAL",
        "tipo": "svial",
        "permiso": "Ingresar_modulo__svial",
        "campo_principal_label": "OBSERVACIONES SEGURIDAD VIAL",
        "propia": "svial",
        "secciones_visibles": ["oper", "mtto","svial"],
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


PROCESOS_PENDIENTES_RRLL = (
    "MANTENIMIENTO",
    "OPERACIONES",
    "SEGURIDAD VIAL",
    "COMPLETO",
)


def normalizar_procesos_pendientes(valor, validar=True):
    """Normaliza la selección múltiple de Pendiente_proceso y valida COMPLETO."""
    procesos = {
        parte.strip().upper()
        for parte in (valor or "").split(",")
        if parte.strip()
    }
    if validar:
        desconocidos = procesos.difference(PROCESOS_PENDIENTES_RRLL)
        if desconocidos:
            raise ValueError("El proceso pendiente seleccionado no es válido.")
        if "COMPLETO" in procesos and len(procesos) > 1:
            raise ValueError("COMPLETO no puede combinarse con otros procesos pendientes.")

    return ", ".join(proceso for proceso in PROCESOS_PENDIENTES_RRLL if proceso in procesos), procesos


def evento_pendiente_para_modulo(evento, modulo):
    """Indica si un evento RRLL debe mostrarse al módulo pendiente indicado."""
    proceso_modulo = {
        "Operaciones": "OPERACIONES",
        "Mtto": "MANTENIMIENTO",
        "Svial": "SEGURIDAD VIAL",
    }.get(modulo)
    if not proceso_modulo:
        return False

    _, procesos = normalizar_procesos_pendientes(
        evento.get("Pendiente_proceso"), validar=False
    )
    return proceso_modulo in procesos


def cerrar_caso_automaticamente(cursor, codigo, usuario):
    """Cierra el caso cuando hayan finalizado todas las gestiones requeridas."""
    cursor.execute("""
        SELECT TOP 1 o.responsabilidad_operador, o.conciliacion,
               ISNULL(o.estado_oper, 0), ISNULL(m.estado_mtto, 0),
               ISNULL(s.estado_svial, 0),
               CASE WHEN EXISTS (
                   SELECT 1 FROM table_info_labora l
                   WHERE l.Id_damage_to_fleet = o.Id_damage_to_fleet
                     AND NULLIF(LTRIM(RTRIM(l.Tipo_cerrado)), '') IS NOT NULL
               ) THEN 1 ELSE 0 END
        FROM table_info_oper o
        LEFT JOIN table_info_mtto m ON m.Id_damage_to_fleet = o.Id_damage_to_fleet
        LEFT JOIN table_info_svial s ON s.Id_damage_to_fleet = o.Id_damage_to_fleet
        WHERE o.Id_damage_to_fleet = ?
    """, [codigo])
    fila = cursor.fetchone()
    if not fila:
        return

    responsabilidad, conciliacion, estado_oper, estado_mtto, estado_svial, estado_laboral = fila
    gestiones_iniciales_completas = estado_oper == 1 and estado_mtto == 1 and estado_svial == 1
    if not gestiones_iniciales_completas:
        return

    # Solo estos dos desenlaces terminan en Operaciones. Los demás llegan
    # a Relaciones Laborales: costo > $2M, no aceptación, no conciliación
    # o reincidencia (la conciliación queda vacía por la regla vigente).
    requiere_laboral = not (
        responsabilidad == "NO APLICA"
        or (responsabilidad == "SI" and conciliacion == "SI")
    )
    puede_cerrar = not requiere_laboral or estado_laboral == 1
    if not puede_cerrar:
        return
    cursor.execute("UPDATE table_damage_to_fleet SET estado_caso = 1 WHERE Id = ?", [codigo])


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
        "puedeReabrirCaso": {
            "Operaciones": "Reabrir_caso_oper",
            "laboral": "Reabrir_caso_rr_ll",
        }.get(modulo) in session.get("permisos", []),
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
        # Operaciones, Mantenimiento y Seguridad Vial muestran ambas
        # bandejas; el filtro Estado del cliente decide si se ven los
        # pendientes o los gestionados. 
        "Operaciones": "1 = 1",
        "Mtto": "1 = 1",
        "Svial": "1 = 1",
        "laboral": """
            NOT (
                estado_caso = 0
                AND EXISTS (
                    SELECT 1 FROM table_info_oper o_terminal
                    WHERE o_terminal.Id_damage_to_fleet = base.Id
                      AND (
                          o_terminal.responsabilidad_operador = 'NO APLICA'
                          OR (
                              o_terminal.responsabilidad_operador = 'SI'
                              AND o_terminal.conciliacion = 'SI'
                              -- costo_oper solo se guarda cuando no_supera es verdadero.
                              AND o_terminal.costo_oper IS NOT NULL
                          )
                      )
                    )
            )
            AND (
                EXISTS (
                    SELECT 1 FROM table_info_laboral_mult lm
                    WHERE lm.Id_damage_to_fleet = base.Id
                )
                OR (
                    tiene_oper = 1 AND tiene_svial = 1 AND estado_caso = 0
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
                ISNULL(d.estado_caso, 0) AS estado_caso,

                (
                    (SELECT COUNT(*) FROM table_damage_files  f  WHERE f.DamageId = d.Id) +
                    (SELECT COUNT(*) FROM table_mtto_files    fm WHERE fm.DamageToFleetId = d.Id) +
                    (SELECT COUNT(*) FROM table_svial_files   fs WHERE fs.DamageId = d.Id) +
                    (SELECT COUNT(*) FROM table_laboral_files fl WHERE fl.DamageToFleetId = d.Id)
                ) AS archivos_count,

                (SELECT COUNT(*) FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id) AS tiene_oper,
                (SELECT COUNT(*) FROM table_info_mtto m WHERE m.Id_damage_to_fleet = d.Id) AS tiene_mtto,
                (SELECT COUNT(*) FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id) AS tiene_svial,
                (SELECT COUNT(*) FROM table_info_labora l WHERE l.Id_damage_to_fleet = d.Id) AS tiene_laboral,
                
                (
                    SELECT TOP 1 lm.Pendiente_proceso
                    FROM table_info_laboral_mult lm
                    WHERE lm.Id_damage_to_fleet = d.Id
                    ORDER BY lm.Fecha_registro DESC
                ) AS pendiente_proceso_actual,
                
                ISNULL((SELECT TOP 1 estado_oper FROM table_info_oper o WHERE o.Id_damage_to_fleet = d.Id), 0) AS estado_oper,
                ISNULL((SELECT TOP 1 estado_mtto FROM table_info_mtto m WHERE m.Id_damage_to_fleet = d.Id), 0) AS estado_mtto,
                ISNULL((SELECT TOP 1 estado_svial FROM table_info_svial s WHERE s.Id_damage_to_fleet = d.Id), 0) AS estado_svial,
                ISNULL(d.estado_caso, 0) AS caso_cerrado,
                CASE WHEN EXISTS (
                    SELECT 1 FROM table_info_laboral_mult lm WHERE lm.Id_damage_to_fleet = d.Id
                ) AND EXISTS (
                    SELECT 1 FROM table_info_labora l WHERE l.Id_damage_to_fleet = d.Id
                ) THEN 1 ELSE 0 END AS cerrado_por_laboral,

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
            AND (
                '{modulo}' != 'laboral'
                OR (
                estado_oper = 1
                AND estado_mtto = 1
                AND estado_svial = 1
            )
        )
        ORDER BY Id DESC
    """

    cursor.execute(query, parametros)
    columnas = [c[0] for c in cursor.description]
    registros = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

    for r in registros:

        fecha = r.get("Fecha_evento")
        r["fecha"] = fecha.strftime("%Y-%m-%dT%H:%M") if fecha else None
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
        r["tiene_laboral"] = bool(r["tiene_laboral"])
        r["caso_cerrado"] = bool(r["caso_cerrado"])
        r["cerrado_por_laboral"] = bool(r["cerrado_por_laboral"])
        campo_estado = {"Operaciones": "estado_oper", "Mtto": "estado_mtto", "Svial": "estado_svial"}.get(modulo)
        r["estado_modulo"] = bool(r[campo_estado]) if campo_estado else None

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
            d.UF, d.Movil, d.Codigo, d.Nombre, d.Area, d.Ruta, d.Tipologia, d.Version_libre,
            d.Zona_dano, d.Parte_afectada, d.Dano_ocasionado,
            d.Centro_operaciones, d.Registrador, d.Direccion,
            o.Observaciones_operaciones, o.rev_error,
            o.Observaciones_correctivos, o.responsabilidad_operador,
            o.conciliacion,
            o.costo_oper AS CostoDelDanoOper,
            CASE
                WHEN o.conciliacion = 'SI' OR o.responsabilidad_operador = 'NO APLICA'
                THEN l.Valor_conciliado
            END AS ValorConciliadoOper,
            m.Costo AS CostoMtto,
            m.observaciones AS observaciones_mtto,
            m.dano_adicional,
            s.Observaciones_svial,
            l.Tipo_cerrado,
            l.Valor_conciliado AS Valor_conciliado_laboral
        FROM table_damage_to_fleet d
        OUTER APPLY (
            SELECT TOP 1 Observaciones_operaciones, rev_error,
                   Observaciones_correctivos, responsabilidad_operador, conciliacion, costo_oper
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
            SELECT TOP 1 Tipo_cerrado, Valor_conciliado
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
            "UF", "Movil", "Codigo", "Nombre", "Area", "Ruta", "Tipologia", "Version_libre",
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
        "Valor_conciliado": detalle_principal.get("Valor_conciliado_laboral")
    }

    t_etapa = time.perf_counter()
    cursor.nextset()
    laboral_eventos = filas_a_lista(cursor, cursor.fetchall())
    laboral_pendientes = [
        evento for evento in laboral_eventos
        if evento_pendiente_para_modulo(evento, modulo)
    ]
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
            "estado": laboral_estado,
            "pendientes": laboral_pendientes,
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


@Modulo_unificado.route("/<modulo>/opciones_evento")
@login_required
def opciones_evento(modulo):
    verificar_acceso_modulo(modulo)
    if modulo not in ("Operaciones", "Mtto", "Svial"):
        abort(404)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT Movil FROM table_damage_to_fleet WHERE Movil IS NOT NULL ORDER BY Movil")
    moviles = [fila[0] for fila in cursor.fetchall()]
    conn.close()
    return jsonify({"moviles": moviles})


@Modulo_unificado.route("/<modulo>/actualizar_evento/<int:id>", methods=["POST"])
@login_required
def actualizar_evento(modulo, id):
    verificar_acceso_modulo(modulo)
    if modulo != "Operaciones":
        abort(404)

    datos = request.get_json(silent=True) or {}
    if not datos:
        try:
            datos = {
                "evento": json.loads(request.form.get("evento", "{}")),
                "motivo_modificacion": request.form.get("motivo_modificacion", "")
            }
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Los datos del evento no son válidos."}), 400
    cambios = datos.get("evento") or {}
    motivo = (datos.get("motivo_modificacion") or "").strip()
    if not motivo:
        return jsonify({"status": "error", "message": "El motivo del cambio es obligatorio."}), 400

    campos_permitidos = {
        "Fecha_evento", "UF", "Movil", "Codigo", "Nombre", "Area", "Ruta", "Tipologia",
        "Direccion", "Version_libre", "Parte_afectada", "Dano_ocasionado",
        "Zona_dano", "Centro_operaciones"
    }
    cambios = {campo: valor for campo, valor in cambios.items() if campo in campos_permitidos}
    tiene_archivos = any(archivo.filename for archivo in request.files.getlist("archivos"))
    if not cambios and not tiene_archivos:
        return jsonify({"status": "success", "message": "No hay cambios para guardar."})

    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM table_damage_to_fleet WHERE Id = ?", [id])
        actual = fila_a_dict(cursor, cursor.fetchone())
        if not actual:
            return jsonify({"status": "error", "message": "No se encontró el evento."}), 404

        # La UI calcula estos valores, pero se validan y recalculan también
        # en el servidor para impedir guardar datos incoherentes.
        uf = str(cambios.get("UF", actual.get("UF") or "")).strip()
        movil = str(cambios.get("Movil", actual.get("Movil") or "")).strip().upper()
        prefijos_uf = {"10": "Z32-", "16": "Z34-"}
        if uf not in prefijos_uf:
            return jsonify({"status": "error", "message": "La UF debe ser 10 o 16."}), 400
        if not movil.startswith(prefijos_uf[uf]) or not movil[len(prefijos_uf[uf]):].isdigit() or len(movil[len(prefijos_uf[uf]):]) != 4:
            return jsonify({"status": "error", "message": "El móvil debe conservar el prefijo de la UF y cuatro dígitos."}), 400
        cambios["UF"] = uf
        cambios["Movil"] = movil
        primer_digito = movil.split("-", 1)[1][0]
        cambios["Tipologia"] = "PADRÓN" if primer_digito == "7" else "BUSETÓN" if primer_digito == "4" else ""

        codigo = str(cambios.get("Codigo", actual.get("Codigo") or "")).strip()
        areas_especiales = {
            "1": "MANTENIMIENTO", "2": "OPERACIONES", "3": "LAVADO",
            "4": "CAPACITACION OBZ", "5": "TERCERO", "6": "TANQUEO",
            "7": "ADMINISTRATIVO"
        }
        cambios["Codigo"] = codigo
        if codigo in areas_especiales:
            cambios["Area"] = areas_especiales[codigo]
        else:
            cursor.execute("SELECT TOP 1 Nombre_OBZ FROM table_drivers WHERE Codigo_OBZ = ?", (codigo,))
            conductor = cursor.fetchone()
            cambios["Area"] = "OBZ"
            if conductor:
                cambios["Nombre"] = conductor[0]

        centros_operaciones = {"GAITANA", "SAN ÁNDRES", "BILBAO", "SAN BERNARDINO"}
        centro = str(cambios.get("Centro_operaciones", actual.get("Centro_operaciones") or "")).strip().upper()
        if centro not in centros_operaciones:
            return jsonify({"status": "error", "message": "El centro de operaciones no es válido."}), 400
        cambios["Centro_operaciones"] = centro

        def valor_comparable(campo, valor):
            if campo == "Fecha_evento" and isinstance(valor, datetime):
                return valor.strftime("%Y-%m-%d")
            return str(valor if valor is not None else "")

        cambios_reales = {
            campo: valor for campo, valor in cambios.items()
            if valor_comparable(campo, actual.get(campo)) != valor_comparable(campo, valor)
        }
        usuario = session.get("usuario", "")
        for campo, valor in cambios_reales.items():
            print(">>> CAMPO:", campo)
            print(">>> VALOR:", repr(valor))
            print(">>> TIPO:", type(valor))
            
            if campo == "Fecha_evento" and isinstance(valor, str):
                valor = datetime.strptime(valor, "%Y-%m-%dT%H:%M")
            
            cursor.execute(f"UPDATE table_damage_to_fleet SET {campo} = ? WHERE Id = ?", (valor, id))
            cursor.execute("""
                INSERT INTO table_auditoria_correcciones
                (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
                 Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (id, "table_damage_to_fleet", campo, str(actual.get(campo) or ""),
                  str(valor or ""), usuario, datetime.now(), motivo))
            
            
        guardar_archivos(cursor, id, "table_damage_files", "DamageId", UPLOAD_FOLDERS["Operaciones"])
        conn.commit()
        return jsonify({"status": "success", "message": "Información del evento actualizada.", "cambios": len(cambios_reales)})
    except Exception as error:
        conn.rollback()
        return jsonify({"status": "error", "message": str(error)}), 500
    finally:
        conn.close()


@Modulo_unificado.route("/Operaciones/operador/<codigo>")
@login_required
def consultar_operador(codigo):
    verificar_acceso_modulo("Operaciones")

    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT TOP 1 Nombre_OBZ FROM table_drivers WHERE Codigo_OBZ = ?", (codigo.strip(),))
        conductor = cursor.fetchone()
        return jsonify({"existe": bool(conductor), "nombre": conductor[0] if conductor else ""})
    finally:
        conn.close()


@Modulo_unificado.route("/Operaciones/eliminar_evento/<int:id>", methods=["POST"])
@login_required
def eliminar_evento(id):
    verificar_acceso_modulo("Operaciones")
    datos = request.get_json(silent=True) or {}
    motivo = (datos.get("motivo_modificacion") or "").strip()
    if not motivo:
        return jsonify({"status": "error", "message": "El motivo del cambio es obligatorio."}), 400

    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM table_damage_to_fleet WHERE Id = ?", [id])
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "No se encontró el evento."}), 404

        usuario = session.get("usuario", "")
        cursor.execute("""
            INSERT INTO table_auditoria_correcciones
                (Id_damage, Tabla_Afectada, Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
            VALUES (?, ?, ?, ?, ?)
        """, (id, "table_damage_to_fleet", usuario, datetime.now(), motivo))
        for tabla, campo in (
            ("table_damage_files", "DamageId"), ("table_mtto_files", "DamageToFleetId"),
            ("table_svial_files", "DamageId"), ("table_laboral_files", "DamageToFleetId"),
            ("table_info_laboral_mult", "Id_damage_to_fleet"), ("table_info_labora", "Id_damage_to_fleet"),
            ("table_info_svial", "Id_damage_to_fleet"), ("table_info_mtto", "Id_damage_to_fleet"),
            ("table_info_oper", "Id_damage_to_fleet")
        ):
            cursor.execute(f"DELETE FROM {tabla} WHERE {campo} = ?", [id])
        cursor.execute("DELETE FROM table_damage_to_fleet WHERE Id = ?", [id])
        conn.commit()
        return jsonify({"status": "success", "message": "Caso eliminado correctamente."})
    except Exception as error:
        conn.rollback()
        return jsonify({"status": "error", "message": str(error)}), 500
    finally:
        conn.close()


def reabrir_caso(id, modulo):
    """Reabre un caso cerrado sin alterar las gestiones ya registradas."""
    verificar_acceso_modulo(modulo)
    datos = request.get_json(silent=True) or {}
    motivo = (datos.get("motivo_modificacion") or "").strip()
    if not motivo:
        return jsonify({"status": "error", "message": "El motivo de reapertura es obligatorio."}), 400

    conn = connect()
    cursor = conn.cursor()
    try:
        if modulo == "laboral":
            cursor.execute("""
                SELECT d.estado_caso,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM table_info_laboral_mult lm
                           WHERE lm.Id_damage_to_fleet = d.Id
                       ) AND EXISTS (
                           SELECT 1 FROM table_info_labora l
                           WHERE l.Id_damage_to_fleet = d.Id
                       ) THEN 1 ELSE 0 END
                FROM table_damage_to_fleet d
                WHERE d.Id = ?
            """, [id])
        else:
            cursor.execute("SELECT estado_caso, 1 FROM table_damage_to_fleet WHERE Id = ?", [id])
        caso = cursor.fetchone()
        if not caso:
            return jsonify({"status": "error", "message": "No se encontró el evento."}), 404
        if not caso[0]:
            return jsonify({"status": "error", "message": "El caso ya se encuentra abierto."}), 409
        if modulo == "laboral" and not caso[1]:
            return jsonify({"status": "error", "message": "El caso no fue cerrado por Relaciones Laborales."}), 409

        usuario = session.get("usuario", "")
        cursor.execute("UPDATE table_damage_to_fleet SET estado_caso = 0 WHERE Id = ?", [id])
        cursor.execute("""
            INSERT INTO table_auditoria_correcciones
                (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
                 Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (id, "table_damage_to_fleet", "estado_caso", "1", "0",
              usuario, datetime.now(), motivo))
        conn.commit()
        return jsonify({"status": "success", "message": "Caso reabierto correctamente."})
    except Exception as error:
        conn.rollback()
        return jsonify({"status": "error", "message": str(error)}), 500
    finally:
        conn.close()


@Modulo_unificado.route("/Operaciones/reabrir_evento/<int:id>", methods=["POST"])
@login_required
@requiere_permiso("Reabrir_caso_oper")
def reabrir_evento(id):
    return reabrir_caso(id, "Operaciones")


@Modulo_unificado.route("/laboral/reabrir_evento/<int:id>", methods=["POST"])
@login_required
@requiere_permiso("Reabrir_caso_rr_ll")
def reabrir_evento_laboral(id):
    return reabrir_caso(id, "laboral")


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
    motivo_modificacion = (request.form.get("Motivo_modificacion") or "").strip()

    def auditar_cambio(tabla, campo, anterior, nuevo):
        if not motivo_modificacion or str(anterior if anterior is not None else "") == str(nuevo if nuevo is not None else ""):
            return
        cursor.execute("""
            INSERT INTO table_auditoria_correcciones
            (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
             Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_registro, tabla, campo, str(anterior or ""), str(nuevo or ""),
              usuario, datetime.now(), motivo_modificacion))

    try:
        # Mantenimiento puede tener un costo preliminar registrado por
        # Operaciones. En ese caso se completa la misma fila y se marca la
        # gestión, en vez de intentar crear un duplicado.
        if modulo == "Mtto":
            cursor.execute("SELECT 1 FROM table_info_mtto WHERE Id_damage_to_fleet = ?", [id_registro])
            if cursor.fetchone():
                cursor.execute("SELECT Costo, dano_adicional, observaciones FROM table_info_mtto WHERE Id_damage_to_fleet = ?", [id_registro])
                anterior = cursor.fetchone()
                for campo, viejo, nuevo in zip(("Costo", "dano_adicional", "observaciones"), anterior, valores[1:4]):
                    auditar_cambio("table_info_mtto", campo, viejo, nuevo)
                cursor.execute("""
                    UPDATE table_info_mtto
                    SET Costo = ?, dano_adicional = ?, observaciones = ?,
                        Usuario_registro_mtto = ?, estado_mtto = 1
                    WHERE Id_damage_to_fleet = ?
                """, (valores[1], valores[2], valores[3], valores[4], id_registro))
            else:
                cursor.execute(ICFG["sql"], valores)
                cursor.execute("UPDATE table_info_mtto SET estado_mtto = 1 WHERE Id_damage_to_fleet = ?", [id_registro])
        elif modulo == "Svial":
            cursor.execute("SELECT 1 FROM table_info_svial WHERE Id_damage_to_fleet = ?", [id_registro])
            if cursor.fetchone():
                cursor.execute("""
                    SELECT Observaciones_svial, conciliado_a_favor, valor_conciliado_terceros
                    FROM table_info_svial WHERE Id_damage_to_fleet = ?
                """, [id_registro])
                anterior = cursor.fetchone()
                for campo, viejo, nuevo in zip(
                    ("Observaciones_svial", "conciliado_a_favor", "valor_conciliado_terceros"),
                    anterior, (valores[1], valores[3], valores[4])
                ):
                    auditar_cambio("table_info_svial", campo, viejo, nuevo)
                cursor.execute("""
                    UPDATE table_info_svial
                    SET Observaciones_svial = ?, Usuario_registro_svial = ?,
                        conciliado_a_favor = ?, valor_conciliado_terceros = ?, estado_svial = 1
                    WHERE Id_damage_to_fleet = ?
                """, (valores[1], valores[2], valores[3], valores[4], id_registro))
            else:
                cursor.execute(ICFG["sql"], valores)
                cursor.execute("UPDATE table_info_svial SET estado_svial = 1 WHERE Id_damage_to_fleet = ?", [id_registro])
        else:
            cursor.execute(ICFG["sql"], valores)
        guardar_archivos(cursor, id_registro, ICFG["tabla_files"], ICFG["campo_files"], UPLOAD_FOLDERS[modulo])
        if modulo in ("Mtto", "Svial"):
            cerrar_caso_automaticamente(cursor, id_registro, usuario)
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
        try:
            pendiente_proceso, procesos_pendientes = normalizar_procesos_pendientes(
                request.form.get("Estado_caso")
            )
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400
        motivo_modificacion = (request.form.get("Motivo_modificacion") or "").strip()

        rev_inf = request.form.get("Revinf", "NO")
        tipo_cerrado = request.form.get("Tipo_cerrado_input", "")
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
        """, (codigo, fecha_presentacion, pendiente_proceso, observaciones_1, usuario, datetime.now()))

        # Un caso puede quedar pendiente por varios procesos. Solo se
        # restablecen los estados de los módulos expresamente seleccionados;
        # COMPLETO equivale a todo bien
        estados_por_proceso = {
            "MANTENIMIENTO": ("table_info_mtto", "estado_mtto"),
            "OPERACIONES": ("table_info_oper", "estado_oper"),
            "SEGURIDAD VIAL": ("table_info_svial", "estado_svial"),
        }
        for proceso, (tabla, campo_estado) in estados_por_proceso.items():
            if proceso in procesos_pendientes:
                cursor.execute(
                    f"UPDATE {tabla} SET {campo_estado} = 0 WHERE Id_damage_to_fleet = ?",
                    (codigo,)
                )

        if rev_inf == "SI":
            cursor.execute(
                "SELECT Tipo_cerrado, Valor_conciliado FROM table_info_labora WHERE Id_damage_to_fleet = ?",
                (codigo,)
            )
            registro_existente = cursor.fetchone()

            if registro_existente:
                campos = {
                    "Tipo_cerrado": (registro_existente[0], tipo_cerrado),
                    "Valor_conciliado": (str(registro_existente[1]), str(costo))
                }

                hubo_cambio = False
                for campo, valores in campos.items():
                    valor_anterior, valor_nuevo = valores
                    if str(valor_nuevo) != str(valor_anterior):
                        hubo_cambio = True
                        cursor.execute("""
                            INSERT INTO table_auditoria_correcciones
                            (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
                             Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (codigo, "table_info_labora", campo, str(valor_anterior), str(valor_nuevo),
                              usuario, datetime.now(), motivo_modificacion))

                if hubo_cambio:
                    cursor.execute("""
                        UPDATE table_info_labora
                        SET Tipo_cerrado = ?, Valor_conciliado = ?, Usuario_registro_labora = ?
                        WHERE Id_damage_to_fleet = ?
                    """, (tipo_cerrado, costo, usuario, codigo))
            else:
                cursor.execute("""
                    INSERT INTO table_info_labora
                    (Id_damage_to_fleet, Tipo_cerrado, Valor_conciliado, Usuario_registro_labora)
                    VALUES (?, ?, ?, ?)
                """, (codigo, tipo_cerrado, costo, usuario))

            # En Relaciones Laborales, Tipo_cerrado confirma que esta es la
            # gestión final del caso.
            if tipo_cerrado:
                cursor.execute(
                    "UPDATE table_damage_to_fleet SET estado_caso = 1 WHERE Id = ?",
                    [codigo]
                )

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
        print(">>> ENTRE A AGREGAR_OPERACIONES")
        codigo = request.form.get("Id_damage_to_fleet")
        observaciones_1 = request.form.get("observaciones_1")
        usuario = request.form.get("Usuario_registro_oper")
        observaciones_extra = request.form.get("observacionesExtra")
        rev_inf = request.form.get("Revinf", "SI")
        motivo_modificacion = (request.form.get("Motivo_modificacion") or "").strip()

        # Pregunta 1: ¿el costo del daño supera $2.000.000?
        costo_supera_2m = request.form.get("costo_supera_2m")  # "SI" / "NO"
        costo_valor = request.form.get("costo_valor")          # solo si NO

        # Solo aplica cuando el costo NO supera los $2.000.000
        responsabilidad_operador = request.form.get("responsabilidad_operador")  # SI / NO / NO APLICA
        conciliacion = request.form.get("conciliacion")  # SI / NO (solo si responsabilidad = SI y no hay reincidencia)
        valor_conciliado_oper = request.form.get("valor_conciliado_oper")  # solo si conciliacion = SI
        motivo_cierre_oper = request.form.get("motivo_cierre_oper", "")
        if valor_conciliado_oper:
            valor_conciliado_oper = int(
            valor_conciliado_oper.replace(".", "").replace(",", "")
        )

        if not codigo or not observaciones_1 or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."}), 400

        no_supera = (costo_supera_2m == "NO")

        if responsabilidad_operador == "NO APLICA":
            conciliacion = None
            if motivo_cierre_oper not in ("RETIRO", "EXONERACIÓN"):
                return jsonify({"status": "error", "message": "Completa este campo"}), 400

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
            SELECT Observaciones_operaciones, Usuario_registro_oper,
                   Observaciones_correctivos, rev_error, responsabilidad_operador,
                   conciliacion, costo_oper
            FROM table_info_oper WITH (UPDLOCK, HOLDLOCK)
            WHERE Id_damage_to_fleet = ?
        """, [codigo])
        registro_oper_anterior = cursor.fetchone()

        if registro_oper_anterior and not motivo_modificacion:
            conn.close()
            return jsonify({
                "status": "error",
                "message": "El motivo del cambio es obligatorio."
            }), 400

        valores_oper = (
            observaciones_1,
            usuario,
            observaciones_extra,
            rev_inf,
            responsabilidad_operador if no_supera else None,
            conciliacion if (no_supera and responsabilidad_operador == "SI") else None,
            costo_valor if no_supera else None
        )

        if registro_oper_anterior:
            if motivo_modificacion:
                for campo, anterior, nuevo in zip(
                    ("Observaciones_operaciones", "Usuario_registro_oper", "Observaciones_correctivos",
                     "rev_error", "responsabilidad_operador", "conciliacion", "costo_oper"),
                    registro_oper_anterior, valores_oper
                ):
                    if str(anterior if anterior is not None else "") != str(nuevo if nuevo is not None else ""):
                        cursor.execute("""
                            INSERT INTO table_auditoria_correcciones
                            (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
                             Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (codigo, "table_info_oper", campo, str(anterior or ""), str(nuevo or ""),
                              usuario, datetime.now(), motivo_modificacion))
            cursor.execute("""
                UPDATE table_info_oper
                SET Observaciones_operaciones = ?,
                    Usuario_registro_oper = ?,
                    Observaciones_correctivos = ?,
                    rev_error = ?,
                    responsabilidad_operador = ?,
                    conciliacion = ?,
                    costo_oper = ?,
                    estado_oper = 1
                WHERE Id_damage_to_fleet = ?
            """, valores_oper + (codigo,))
        else:
            cursor.execute("""
                INSERT INTO table_info_oper
                    (Id_damage_to_fleet, Observaciones_operaciones, Usuario_registro_oper,
                     Observaciones_correctivos, rev_error, responsabilidad_operador, conciliacion, costo_oper, estado_oper)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (codigo,) + valores_oper + (1,))

        # Si hubo conciliación, o si el operador respondió "NO APLICA"
        # (mismo tratamiento: el caso termina en Operaciones), el valor
        # se guarda reutilizando exactamente la misma columna que usa
        # Relaciones Laborales (table_info_labora.Valor_conciliado), tal
        # como pide el requerimiento -- no se crea una columna nueva.
        termina_en_operaciones = not bloqueado_reincidencia and no_supera and (
            (responsabilidad_operador == "SI" and conciliacion == "SI")
            or responsabilidad_operador == "NO APLICA"
        )
        
        if responsabilidad_operador == "NO APLICA":
            tipo_cerrado = motivo_cierre_oper
        else:
            tipo_cerrado = "CONCILIACIÓN"

        if termina_en_operaciones:
            cursor.execute(
                "SELECT Id_damage_to_fleet FROM table_info_labora WHERE Id_damage_to_fleet = ?",
                [codigo]
            )
            existe_labora = cursor.fetchone()
             

            if existe_labora:
                cursor.execute("""
                    UPDATE table_info_labora SET Valor_conciliado = ? , Tipo_cerrado = ? WHERE Id_damage_to_fleet = ?
                """, (valor_conciliado_oper, tipo_cerrado,codigo))
            else:
                cursor.execute("""
                    INSERT INTO table_info_labora
                        (Id_damage_to_fleet, Tipo_cerrado, Valor_conciliado, Usuario_registro_labora)
                    VALUES (?, ?, ?, ?)
                """, (codigo, tipo_cerrado, valor_conciliado_oper, usuario))
        print(">>> ANTES DE GUARDAR ARCHIVOS")
        
        guardar_archivos(cursor, codigo, "table_damage_files", "DamageId", UPLOAD_FOLDERS["Operaciones"])
        
        print(">>> DESPUÉS DE GUARDAR ARCHIVOS")
        if termina_en_operaciones:
            cerrar_caso_automaticamente(cursor, codigo, usuario)
        else:
            # Al reabrir y modificar Operaciones, una decisión nueva que
            # requiere RRLL no puede reutilizar un cierre histórico de
            # table_info_labora. Si ese registro provino de un cierre previo
            # de Operaciones (sin historial en RRLL), se retira para que el
            # caso ingrese como pendiente; la eliminación queda auditada.
            cursor.execute("""
                SELECT Tipo_cerrado, Valor_conciliado
                FROM table_info_labora l
                WHERE l.Id_damage_to_fleet = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM table_info_laboral_mult lm
                      WHERE lm.Id_damage_to_fleet = l.Id_damage_to_fleet
                  )
            """, [codigo])
            cierre_operaciones_anterior = cursor.fetchone()
            if cierre_operaciones_anterior:
                cursor.execute("""
                    INSERT INTO table_auditoria_correcciones
                    (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo,
                     Usuario_Modifica, Fecha_Modificacion, Motivo_modificacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    codigo, "table_info_labora", "Cierre previo de Operaciones",
                    f"Tipo: {cierre_operaciones_anterior[0] or ''}; Valor: {cierre_operaciones_anterior[1] or ''}",
                    "", usuario, datetime.now(), motivo_modificacion
                ))
                cursor.execute("DELETE FROM table_info_labora WHERE Id_damage_to_fleet = ?", [codigo])

            # Se preservan los demás registros; solo se mantiene abierto el
            # caso para que el filtro vigente de RRLL evalúe los datos nuevos.
            cursor.execute(
                "UPDATE table_damage_to_fleet SET estado_caso = 0 WHERE Id = ?",
                [codigo]
            )

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
