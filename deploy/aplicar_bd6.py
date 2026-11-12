"""Ejecuta BD-6 autorizado, con respaldo de autores y verificacion de contenido."""
import hashlib
import json
import sys
from contextlib import closing
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
from config import connect

REFERENCIAS = {
    "flota.table_damage_to_fleet": "Registrador",
    "proceso.table_info_oper": "Usuario_registro_oper",
    "proceso.table_info_mtto": "Usuario_registro_mtto",
    "proceso.table_info_svial": "Usuario_registro_svial",
    "proceso.table_info_labora": "Usuario_registro_labora",
    "proceso.table_info_laboral_mult": "Usuario_registro_laboral",
    "proceso.table_auditoria_correcciones": "Usuario_Modifica",
    "proceso.table_intervenciones": "Usuario_registro",
}


def leer(cursor, objeto, pk):
    cursor.execute(f"SELECT * FROM {objeto} ORDER BY [{pk}]")
    columnas = [c[0] for c in cursor.description]
    return [{k: v for k, v in zip(columnas, fila) if k != "usuario_id"} for fila in cursor.fetchall()]


def huella(filas):
    return hashlib.sha256(json.dumps(filas, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def aplicar():
    respaldo, estados, claves = {}, {}, {}
    with closing(connect()) as conexion, closing(conexion.cursor()) as cursor:
        conexion.timeout = 90
        try:
            cursor.execute("SET LOCK_TIMEOUT 15000; IF @@TRANCOUNT=0 BEGIN TRANSACTION;")
            for tabla, anterior in REFERENCIAS.items():
                cursor.execute("""SELECT c.name FROM sys.key_constraints kc
                                  JOIN sys.index_columns ic ON ic.object_id=kc.parent_object_id AND ic.index_id=kc.unique_index_id
                                  JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                                  WHERE kc.parent_object_id=OBJECT_ID(?) AND kc.type='PK' AND ic.key_ordinal>0""", tabla)
                pk = [f[0] for f in cursor.fetchall()]
                assert len(pk) == 1, (tabla, pk)
                claves[tabla] = pk[0]
                filas = leer(cursor, tabla, pk[0])
                cursor.execute(f"""SELECT t.[{pk[0]}],u.ConsID,u.Username FROM {tabla} t
                                   LEFT JOIN usuario.Table_usuarios u
                                   ON u.Username COLLATE DATABASE_DEFAULT=
                                   CONVERT(nvarchar(max),t.[{anterior}]) COLLATE DATABASE_DEFAULT""")
                correspondencias = {f[0]: (f[1], f[2]) for f in cursor.fetchall()}
                respaldo[tabla] = dict(columna_original=anterior, pk=pk[0],
                                      autores=[dict(pk=f[pk[0]], usuario=f[anterior],
                                                    usuario_id=correspondencias[f[pk[0]]][0]) for f in filas])
                normalizadas = 0
                for fila in filas:
                    usuario_id, nombre_actual = correspondencias[fila[pk[0]]]
                    assert fila[anterior] is None or usuario_id is not None, "Autor sin correspondencia"
                    normalizadas += fila[anterior] != nombre_actual
                    fila[anterior] = nombre_actual
                estados[tabla] = dict(filas=len(filas), sha256_antes=huella(filas),
                                     nombres_canonicos=normalizadas)
            destino = RAIZ / "docs" / "auditoria"
            (destino / "BD-6_respaldo_autores.json").write_text(
                json.dumps(respaldo, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            cursor.execute((RAIZ / "deploy" / "sql" / "BD-6_usuarios_id.sql").read_text(encoding="utf-8"))
            while cursor.nextset():
                pass
            for tabla, anterior in REFERENCIAS.items():
                esquema, nombre = tabla.split(".")
                filas = leer(cursor, esquema + ".v_BD6_" + nombre, claves[tabla])
                actual = huella(filas)
                assert len(filas) == estados[tabla]["filas"] and actual == estados[tabla]["sha256_antes"], \
                    f"Cambio de contenido visible en {tabla}: se revierte BD-6"
                estados[tabla]["sha256_despues"] = actual
            conexion.commit()
        except BaseException:
            conexion.rollback()
            raise
    (RAIZ / "docs" / "auditoria" / "BD-6_contenido.json").write_text(
        json.dumps(estados, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BD-6 confirmado: 8 columnas textuales retiradas, FK e indices creados.")
    print("Filas y contenido visible conservados:", sum(r["filas"] for r in estados.values()))


if __name__ == "__main__":
    aplicar()
