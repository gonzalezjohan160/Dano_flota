"""Listas de formulario construidas con las tablas físicas disponibles.

La base instalada no tiene el esquema `catalogo`; los casos conservan las listas
de ruta, área, centro, zona y tipo, y los móviles son la fuente de UF y prefijos.
"""


_RUTAS_INICIALES_POR_UF = {
    "10": ("CG147", "DG208", "CA127", "CH131", "CA129", "CA124", "TRANSITO A PATIO", "PATIO"),
    "16": ("CL149", "CB144", "CG137", "CA134", "CB138", "CA151", "CF154", "CA153", "CB145", "TRANSITO A PATIO", "PATIO"),
}

_AREAS_POR_CODIGO = {
    "1": "MANTENIMIENTO",
    "2": "OPERACIONES",
    "3": "LAVADO",
    "4": "CAPACITACIÓN OBZ",
    "5": "TERCERO",
    "6": "TANQUEO",
    "7": "ADMINISTRATIVO",
}

_CENTROS_INICIALES = ("GAITANA", "SAN ANDRÉS", "BILBAO", "SAN BERNARDINO")
_ZONAS_INICIALES = (
    "LATERAL IZQUIERDO", "LATERAL DERECHO", "FRONTAL", "POSTERIOR", "TECHO",
    "ESPEJOS", "PUERTAS", "VIDRIOS", "LLANTAS", "ITS", "SIRCI",
    "CARROCERÍA INTERNA", "TREN MOTRIZ", "CHASIS",
)
_TIPOS_INICIALES = (
    "CONDUCTA OPERACIONAL", "INFRAESTRUCTURA PATIO", "INFRAESTRUCTURA VIAL",
    "VANDALISMO", "MECÁNICO", "SINIESTRO VIAL", "ALISTAMIENTO",
)


def listar_unidades_funcionales(cursor):
    """Lista de (UF, prefijo) observados en la tabla maestra de móviles."""
    cursor.execute("""
        SELECT UF, LEFT(No_Movil, 4) AS prefijo_movil
        FROM flota.table_Moviles
        WHERE UF IS NOT NULL AND No_Movil IS NOT NULL
        GROUP BY UF, LEFT(No_Movil, 4)
        ORDER BY UF, prefijo_movil
    """)
    return [(int(fila[0]), fila[1]) for fila in cursor.fetchall()]


def listar_rutas_por_uf(cursor):
    """Incluye rutas iniciales y las rutas históricas usadas por cada UF."""
    rutas = {uf: list(valores) for uf, valores in _RUTAS_INICIALES_POR_UF.items()}
    cursor.execute("""
        SELECT DISTINCT TRY_CONVERT(varchar(3), UF), LTRIM(RTRIM(Ruta))
        FROM flota.v_BD6_table_damage_to_fleet
        WHERE TRY_CONVERT(int, UF) IS NOT NULL
          AND NULLIF(LTRIM(RTRIM(Ruta)), '') IS NOT NULL
        ORDER BY TRY_CONVERT(varchar(3), UF), LTRIM(RTRIM(Ruta))
    """)
    for uf, ruta in cursor.fetchall():
        key = str(uf)
        rutas.setdefault(key, [])
        if ruta not in rutas[key]:
            rutas[key].append(ruta)
    return rutas


def listar_areas(cursor):
    """Devuelve códigos de área presentes en casos, conservando etiquetas conocidas."""
    cursor.execute("""
        SELECT DISTINCT LTRIM(RTRIM(CONVERT(varchar(50), Area)))
        FROM flota.v_BD6_table_damage_to_fleet
        WHERE NULLIF(LTRIM(RTRIM(CONVERT(varchar(50), Area))), '') IS NOT NULL
        ORDER BY LTRIM(RTRIM(CONVERT(varchar(50), Area)))
    """)
    areas = dict(_AREAS_POR_CODIGO)
    for (codigo,) in cursor.fetchall():
        areas.setdefault(str(codigo), str(codigo))
    return "OBZ", areas


def _listar_valores_de_casos(cursor, columna, iniciales):
    # `columna` solo se invoca con nombres constantes definidos en este módulo.
    cursor.execute(f"""
        SELECT DISTINCT LTRIM(RTRIM({columna}))
        FROM flota.v_BD6_table_damage_to_fleet
        WHERE NULLIF(LTRIM(RTRIM({columna})), '') IS NOT NULL
        ORDER BY LTRIM(RTRIM({columna}))
    """)
    valores = list(iniciales)
    for (valor,) in cursor.fetchall():
        if valor not in valores:
            valores.append(valor)
    return valores


def listar_centros_operacion(cursor):
    return _listar_valores_de_casos(cursor, "Centro_operaciones", _CENTROS_INICIALES)


def listar_zonas_dano(cursor):
    return _listar_valores_de_casos(cursor, "Zona_dano", _ZONAS_INICIALES)


def listar_tipos_dano(cursor):
    return _listar_valores_de_casos(cursor, "Dano_ocasionado", _TIPOS_INICIALES)


def cargar_listas_del_caso(cursor):
    """Todas las listas que usan el capturador y la edición del evento."""
    area_por_defecto, areas_por_codigo = listar_areas(cursor)
    return {
        "unidades_funcionales": listar_unidades_funcionales(cursor),
        "rutas_por_uf": listar_rutas_por_uf(cursor),
        "area_por_defecto": area_por_defecto,
        "areas_por_codigo": areas_por_codigo,
        "centros_operacion": listar_centros_operacion(cursor),
        "zonas_dano": listar_zonas_dano(cursor),
        "tipos_dano": listar_tipos_dano(cursor),
    }


def listas_para_el_navegador(listas):
    """Las listas en la forma que usa el JavaScript de los formularios."""
    return {
        "prefijos_movil": {str(uf): prefijo for uf, prefijo in listas["unidades_funcionales"]},
        "rutas_por_uf": listas["rutas_por_uf"],
        "areas_por_codigo": listas["areas_por_codigo"],
        "area_por_defecto": listas["area_por_defecto"],
        "centros_operacion": listas["centros_operacion"],
        "zonas_dano": listas["zonas_dano"],
        "tipos_dano": listas["tipos_dano"],
    }
