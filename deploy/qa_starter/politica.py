"""Alcance del starter para el esquema físico que usa la aplicación."""

USUARIOS = "usuario.table_usuarios"
CASOS = "flota.table_damage_to_fleet"
OPERADORES = "flota.table_drivers"
ARCHIVOS = "flota.table_damage_files"
REPARACIONES_ARCHIVOS = "proceso.table_intervenciones_files"
EXCLUIDAS = ("usuario.table_password_reset", "usuario.table_tutoriales")

REQUERIDAS = (
    USUARIOS, "usuario.table_permisos", "usuario.table_usuarios_permisos",
    "flota.table_moviles", OPERADORES, CASOS, ARCHIVOS,
    "proceso.table_info_oper", "proceso.table_info_mtto", "proceso.table_info_svial",
    "proceso.table_info_labora", "proceso.table_info_laboral_mult",
    "proceso.table_auditoria_correcciones", "proceso.table_intervenciones",
    REPARACIONES_ARCHIVOS,
)
OPCIONALES = ("catalogo.unidad_funcional", "usuario.table_roles", "dbo.table_roles")

# Texto funcional utilizado para filtros, catálogos y permisos.
CONSERVAR = {
    USUARIOS: "alcance_uf",
    "usuario.table_permisos": "nombre",
    "usuario.table_roles": "nombre",
    "dbo.table_roles": "nombre",
    "catalogo.unidad_funcional": "nombre prefijo_movil",
    "flota.table_moviles": "no_movil uf tipologia_movil",
    CASOS: "movil uf ruta tipologia dano_ocasionado zona_dano centro_operaciones area",
    "proceso.table_info_oper": "rev_error responsabilidad_operador conciliacion",
    "proceso.table_info_mtto": "dano_adicional",
    "proceso.table_info_svial": "conciliado_a_favor",
    "proceso.table_info_labora": "tipo_cerrado cerrado",
    "proceso.table_info_laboral_mult": "pendiente_proceso",
    "proceso.table_intervenciones": "movil uf tipologia zona_intervenida",
}
CARPETAS = {
    "Operaciones": "Files_ppal",
    "Mantenimiento": "Files_mtto",
    "Seguridad vial": "Files_svial",
    "Laboral": "Files_laboral",
    "Reparaciones": "Files_reparaciones",
}
TIPOS_TEXTO = {"char", "nchar", "varchar", "nvarchar", "text", "ntext"}
TIPOS_SIMPLES = {
    "bit", "tinyint", "smallint", "int", "bigint", "decimal", "numeric", "money",
    "smallmoney", "real", "float", "date", "datetime", "datetime2", "smalldatetime", "time",
}
CONSERVAR_NO_TEXTO = {
    "id", "id_damage", "id_damage_to_fleet", "damagetofleetid",
    "damageid", "repairid", "id_info_laboral", "usuario_id", "consid", "userid",
    "rolid", "permisoid", "uf", "fecha_evento", "fecha_registro", "fecha_presentacion",
    "fecha_subida", "fecha_modificacion", "fechacreacion", "estado_caso", "estado_oper",
    "estado_mtto", "estado_svial", "eliminado", "costo", "costo_oper", "costo_intervencion",
    "valor_conciliado", "valor_conciliado_terceros", "conciliado_a_favor",
    "responsabilidad_operador", "conciliacion", "rev_error", "dano_adicional",
}


def regla(tabla, columna):
    nombre, tipo = columna[:2]
    if tabla == USUARIOS:
        especiales = {
            "username": "usuario", "nombre": "usuario", "email": "correo",
            "passwordhash": "clave", "idusuario": "identificacion",
            "activo": "inactivo", "cambio_password_obligatorio": "cambio",
        }
        if nombre in especiales:
            return especiales[nombre]
    if tabla in {ARCHIVOS, REPARACIONES_ARCHIVOS} and nombre in {"filename", "filepath"}:
        return "adjunto"
    if (tabla, nombre) in {(OPERADORES, "codigo_obz"), (CASOS, "codigo")}:
        return "codigo"
    if tipo in TIPOS_TEXTO:
        return "conservar" if nombre in CONSERVAR.get(tabla, "").split() else "ocultar"
    if tipo in TIPOS_SIMPLES and nombre in CONSERVAR_NO_TEXTO:
        return "conservar"
    raise ValueError(f"Columna fuera de la política del starter: {tabla}.{nombre} ({tipo}).")


def valor_proyectado(columna, accion):
    """Reduce los datos sensibles que salen de SQL Server durante la exportación."""
    nombre = f"[{columna[0].replace(']', ']]')}]"
    if accion in {"usuario", "clave", "identificacion", "inactivo", "cambio", "adjunto", "correo"}:
        return "NULL"
    if accion == "ocultar":
        return f"CASE WHEN {nombre} IS NULL THEN NULL ELSE 1 END"
    if columna[1] in {"date", "datetime", "datetime2", "smalldatetime", "time"}:
        return f"CONVERT(varchar(40), {nombre}, 126)"
    return nombre
