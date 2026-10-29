from flask import abort

from backend_unificado import ARCHIVOS_POR_TIPO, MODULOS


class Regla:
    """Qué exige una ruta. publica: sin sesión; sesion: cualquier usuario con sesión."""

    def __init__(self, descripcion, publica=False, sesion=False, todos=(), alguno=(), por_modulo=False):
        self.descripcion = descripcion
        self.publica = publica
        self.sesion = sesion
        self.todos = frozenset(todos)
        self.alguno = frozenset(alguno)
        self.por_modulo = por_modulo

    def permite(self, permisos, view_args):
        if self.publica or self.sesion:
            return True
        permisos = set(permisos or ())
        requeridos = set(self.todos)
        if self.por_modulo:
            modulo = (view_args or {}).get("modulo")
            if modulo not in MODULOS:
                abort(404)
            requeridos.add(MODULOS[modulo]["permiso"])
        if not requeridos.issubset(permisos):
            return False
        return not self.alguno or bool(self.alguno & permisos)

    def __repr__(self):
        return f"Regla({self.descripcion})"


PUBLICA = Regla("pública", publica=True)
SESION = Regla("cualquier sesión", sesion=True)
POR_MODULO = Regla("permiso del módulo de la URL", por_modulo=True)


def permiso(*permisos):
    return Regla(" y ".join(permisos), todos=permisos)


def alguno(*permisos):
    return Regla("alguno de " + ", ".join(sorted(permisos)), alguno=permisos)


OPERACIONES = "Ingresar_modulo__oper"
RRLL = "Ingresar_modulo__laboral"

# Cualquier permiso que permita abrir algún tipo de adjunto; /archivo valida
# además el permiso del tipo concreto y la UF del caso.
PERMISOS_ALGUN_ADJUNTO = sorted({p for cfg in ARCHIVOS_POR_TIPO.values() for p in cfg["permiso"]})

REGLAS = {
    # Acceso y sesión
    "Modulo_login.login": PUBLICA,
    "Modulo_login.forgot_password": PUBLICA,
    "Modulo_login.reset_password": PUBLICA,
    "Modulo_login.logout": SESION,
    "index": SESION,
    "Profile.index": SESION,
    "Profile.cambiar_password": SESION,
    "Tutoriales.index": SESION,
    "Tutoriales.ver_video": SESION,
    "Tutoriales.subir": permiso("Subir_videos"),
    "Tutoriales.eliminar": permiso("Eliminar_videos"),

    # Tablero e históricos
    "Front_dashboard.index": permiso("Ingresar_dashboard"),
    "Historico_danos.index": permiso("Ingresar_historico_danos"),
    "Historico_danos.detalle": permiso("Ingresar_historico_danos"),
    "Historico_danos.exportar_excel": permiso("Ingresar_historico_danos"),
    "Historico_movil.index": permiso("Ingresar_danos_vs_reparaciones"),
    "Historico_movil.detalle": permiso("Ingresar_danos_vs_reparaciones"),
    "Historico_movil.detalle_reparacion": permiso("Ingresar_danos_vs_reparaciones"),
    "Historico_movil.exportar_excel": permiso("Ingresar_danos_vs_reparaciones"),

    # Capturadores
    "Capturador.index": permiso("Ingresar_captur_danos"),
    "Capturador.geocode": permiso("Ingresar_captur_danos"),
    "Capturador.get_conductor": permiso("Ingresar_captur_danos"),
    "Capturador.get_flota": permiso("Ingresar_captur_danos"),
    "Capturador.validar_duplicado": permiso("Ingresar_captur_danos"),
    "Capturador.submit_form": permiso("Ingresar_captur_danos"),
    "Capturador_rep.index": permiso("Ingresar_captur_reparaciones"),
    "Capturador_rep.get_flota": permiso("Ingresar_captur_reparaciones"),
    "Capturador_rep.submit_form": permiso("Ingresar_captur_reparaciones"),

    # Módulos de gestión (/Operaciones, /Mtto, /Svial, /laboral)
    "Modulo_unificado.index": POR_MODULO,
    "Modulo_unificado.detalle": POR_MODULO,
    "Modulo_unificado.opciones_evento": POR_MODULO,
    "Modulo_unificado.actualizar_evento": POR_MODULO,
    "Modulo_unificado.agregar": POR_MODULO,
    "Modulo_unificado.consultar_operador": permiso(OPERACIONES),
    "Modulo_unificado.verificar_reincidencia_operador": permiso(OPERACIONES),
    "Modulo_unificado.eliminar_evento": permiso(OPERACIONES, "Eliminar_evento"),
    "Modulo_unificado.reabrir_evento": permiso(OPERACIONES, "Reabrir_caso_oper"),
    "Modulo_unificado.reabrir_evento_laboral": permiso(RRLL, "Reabrir_caso_rr_ll"),
    "Modulo_unificado.descargar_archivo": alguno(*PERMISOS_ALGUN_ADJUNTO),

    # Administración de usuarios
    "Modulo_usuario.crear_usuario": permiso("Ingresar_crear_usuario"),
    "Modulo_usuario.editar_usuario": permiso("Ingresar_crear_usuario", "Ingresar_asignar_permisos"),
    "Modulo_permisos_roles.asignar_permisos": permiso("Ingresar_asignar_permisos"),
    "Modulo_permisos_roles.eliminar_usuario": permiso("Ingresar_asignar_permisos"),
    "Modulo_permisos_roles.permisos_usuario": permiso("Ingresar_asignar_permisos"),
    "Modulo_permisos_roles.forzar_cambio_password": permiso("Ingresar_asignar_permisos"),
    "Modulo_permisos_roles.quitar_cambio_password": permiso("Ingresar_asignar_permisos"),
}


def regla_para(endpoint):
    """Regla de la ruta; los archivos estáticos son públicos. None = sin regla (se niega)."""
    if endpoint == "static" or (endpoint or "").endswith(".static"):
        return PUBLICA
    return REGLAS.get(endpoint)
