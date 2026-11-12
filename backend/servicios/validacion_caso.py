"""Validación de los datos de un caso contra los catálogos de la base.

La usan el Capturador de daños (caso nuevo) y Operaciones (Editar), para que las
dos pantallas apliquen las mismas reglas. "listas" es el diccionario de
modelos.catalogos.cargar_listas_del_caso.
"""


def area_del_operador(listas, codigo):
    """Área que le corresponde al código: los códigos especiales (1 a 7) son áreas;
    cualquier otro código es el área por defecto (OBZ)."""
    return listas["areas_por_codigo"].get(str(codigo or "").strip(), listas["area_por_defecto"])


def prefijo_movil_de_la_uf(listas, uf):
    """Prefijo del número de móvil de la UF (por ejemplo 'Z32-'), o None si la UF no existe."""
    return dict((str(id_uf), prefijo) for id_uf, prefijo in listas["unidades_funcionales"]).get(str(uf))


def error_de_catalogo(listas, uf=None, ruta=None, zona_dano=None, tipo_dano=None, centro_operacion=None):
    """Mensaje del primer valor que no está en su catálogo, o None si todos son válidos.

    Solo se revisan los valores que se pasan (None = no se revisa).
    """
    if uf is not None and prefijo_movil_de_la_uf(listas, uf) is None:
        return "La UF no es válida."
    if ruta is not None and ruta not in listas["rutas_por_uf"].get(str(uf), []):
        return "La ruta no corresponde a la UF seleccionada."
    if zona_dano is not None and zona_dano not in listas["zonas_dano"]:
        return "La zona del daño no es válida."
    if tipo_dano is not None and tipo_dano not in listas["tipos_dano"]:
        return "La causa del daño no es válida."
    if centro_operacion is not None and centro_operacion not in listas["centros_operacion"]:
        return "El centro de operaciones no es válido."
    return None
