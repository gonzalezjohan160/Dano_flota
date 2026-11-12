"""Configuración fija del módulo unificado: módulos, gestiones y tipos de adjunto."""
from backend_security import PERMISO_ADJUNTOS_LABORALES

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
        "mostrar_revision": False,
        "mostrar_observaciones": False,
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
# GESTIONES DE MANTENIMIENTO Y SEGURIDAD VIAL
# ==========================================================
#
# Ruta de cada gestión y campos del formulario en el orden en que se guardan (sus
# adjuntos van a flota.table_damage_files, desde la carpeta del módulo). Operaciones (agregar_oper) y RRLL (agregar_rl) tienen
# controlador propio. El SQL de cada gestión está en modelos/mantenimiento.py y
# modelos/seguridad_vial.py.

CONFIG_GESTIONES = {

    "Mtto": {
        "ruta": "agregar_mtto",
        "campos": [
            {"origen": "id"},
            {"origen": "Costo"},
            {"origen": "dano_adicional"},
            {"origen": "observaciones"},
            {"origen": "usuario"}
        ],
    },

    "Svial": {
        "ruta": "agregar_svial",
        "campos": [
            {"origen": "id"},
            {"origen": "Observaciones_svial"},
            {"origen": "usuario"},
            {"origen": "conciliado_a_favor"},
            {"origen": "valor_conciliado_terceros"}
        ],
    }

}


# ==========================================================
# ADJUNTOS POR TIPO (descarga por identificador)
# ==========================================================

# Los adjuntos de Operaciones (incluido el capturador), Mantenimiento y Seguridad
# Vial los ve cualquier usuario con acceso a una pantalla de casos, sin importar
# qué módulo los subió (regla de negocio). Los de Relaciones Laborales solo los ve
# RRLL. Se exige además la UF del caso, para que un usuario sin acceso a casos no
# pueda descargarlos recorriendo identificadores.
PERMISOS_VER_ADJUNTOS_CASO = (
    "Ingresar_modulo__oper", "Ingresar_modulo__mtto", "Ingresar_modulo__svial",
    "Ingresar_modulo__laboral", "Ingresar_historico_danos",
    "Ingresar_danos_vs_reparaciones", "Ingresar_captur_danos",
)

# Tipo de adjunto -> quién lo puede ver y en qué carpeta debe estar. Los del caso
# están en flota.table_damage_files (el tipo filtra por su columna "modulo"); los de las
# reparaciones, en proceso.table_intervenciones_files (ver modelos/archivos.py).
ARCHIVOS_POR_TIPO = {
    "operaciones": {"permiso": PERMISOS_VER_ADJUNTOS_CASO, "carpeta": "Operaciones"},
    "mtto": {"permiso": PERMISOS_VER_ADJUNTOS_CASO, "carpeta": "Mtto"},
    "svial": {"permiso": PERMISOS_VER_ADJUNTOS_CASO, "carpeta": "Svial"},
    "laboral": {"permiso": (PERMISO_ADJUNTOS_LABORALES,), "carpeta": "laboral"},
    "reparaciones": {
        "permiso": ("Ingresar_captur_reparaciones", "Ingresar_danos_vs_reparaciones"),
        "carpeta": "Reparaciones",
    },
}
