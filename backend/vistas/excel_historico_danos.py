"""Excel de Histórico de daños (general y de RRLL) a partir de datos ya consultados."""
from io import BytesIO

import pandas as pd


def construir_fila(r, laboralm, es_exportacion_laboral):
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


def crear_excel_historico(registros, laboral_por_caso, es_exportacion_laboral):
    """Libro .xlsx en memoria (BytesIO) con una fila por caso."""
    filas_excel = [construir_fila(r, laboral_por_caso.get(r["Id"], []), es_exportacion_laboral) for r in registros]
    # Con cero resultados se conservan los encabezados.
    df = pd.DataFrame(filas_excel, columns=list(construir_fila({}, [], es_exportacion_laboral).keys()))

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
    return output
