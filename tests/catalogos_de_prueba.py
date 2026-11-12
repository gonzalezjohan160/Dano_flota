"""Catálogos de prueba: las mismas listas que antes estaban fijas en el código.

Las pruebas no se conectan a SQL Server; reemplazan
modelos.catalogos.cargar_listas_del_caso por estas listas.
"""
from unittest.mock import patch

LISTAS = {
    "unidades_funcionales": [(10, "Z32-"), (16, "Z34-")],
    "rutas_por_uf": {
        "10": ["CG147", "DG208", "CA127", "CH131", "CA129", "CA124", "TRANSITO A PATIO", "PATIO"],
        "16": ["CL149", "CB144", "CG137", "CA134", "CB138", "CA151", "CF154", "CA153", "CB145",
               "TRANSITO A PATIO", "PATIO"],
    },
    "area_por_defecto": "OBZ",
    "areas_por_codigo": {
        "1": "MANTENIMIENTO", "2": "OPERACIONES", "3": "LAVADO", "4": "CAPACITACIÓN OBZ",
        "5": "TERCERO", "6": "TANQUEO", "7": "ADMINISTRATIVO",
    },
    "centros_operacion": ["GAITANA", "SAN ANDRÉS", "BILBAO", "SAN BERNARDINO"],
    "zonas_dano": [
        "LATERAL IZQUIERDO", "LATERAL DERECHO", "FRONTAL", "POSTERIOR", "TECHO", "ESPEJOS", "PUERTAS",
        "VIDRIOS", "LLANTAS", "ITS", "SIRCI", "CARROCERÍA INTERNA", "TREN MOTRIZ", "CHASIS",
    ],
    "tipos_dano": [
        "CONDUCTA OPERACIONAL", "INFRAESTRUCTURA PATIO", "INFRAESTRUCTURA VIAL", "VANDALISMO",
        "MECÁNICO", "SINIESTRO VIAL", "ALISTAMIENTO",
    ],
}


def parchar_catalogos():
    """Parche (sin iniciar) que hace que la aplicación lea LISTAS en vez de la base."""
    return patch("modelos.catalogos.cargar_listas_del_caso", return_value=LISTAS)
