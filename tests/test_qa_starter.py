import json
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from zipfile import ZipFile

from deploy.qa_starter import carga, media, paquete, sql
from deploy.qa_starter.politica import ARCHIVOS, CASOS, OPERADORES, USUARIOS, regla


def columna(nombre, tipo="int", longitud=4, identidad=False):
    return [nombre, tipo, longitud, 0, 0, False, identidad]


class StarterTests(unittest.TestCase):
    def setUp(self):
        temporal = TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name).resolve()
        self.paquete = self.raiz / "corte.starter.zip"
        self.esquema = {
            USUARIOS: [
                columna("consid", identidad=True), columna("username", "nvarchar", 100),
                columna("passwordhash", "nvarchar", 512), columna("email", "nvarchar", 200),
                columna("activo", "bit", 1), columna("cambio_password_obligatorio", "bit", 1),
                columna("idusuario"),
            ],
            CASOS: [
                columna("id_damage", identidad=True), columna("codigo", "varchar", 10),
                columna("version_libre", "nvarchar", -1), columna("fecha_evento", "date"),
            ],
            OPERADORES: [columna("codigo_obz", "varchar", 10)],
            ARCHIVOS: [
                columna("id", identidad=True), columna("id_damage"),
                columna("filename", "varchar", 80), columna("filepath", "nvarchar", 400),
            ],
        }
        self.filas = {
            USUARIOS: [(42, None, None, None, None, None, None)],
            CASOS: [(103, "100123", 1, "2026-05-19")],
            OPERADORES: [("100123",)],
            ARCHIVOS: [(9, 103, None, None, "Mantenimiento")],
        }

    def exportar(self):
        with patch.object(paquete, "leer_filas", side_effect=lambda _, tabla, __: self.filas[tabla]):
            return paquete.crear(Mock(), self.esquema, self.paquete)

    def test_exportar_y_materializar_conserva_relaciones_y_sustituye_datos(self):
        manifiesto = self.exportar()
        with ZipFile(self.paquete) as archivo:
            self.assertEqual(paquete.leer_manifiesto(archivo), manifiesto)
            paquete.comprobar(archivo, manifiesto)
            caso, = paquete.filas(archivo, manifiesto, CASOS)
            operador, = paquete.filas(archivo, manifiesto, OPERADORES)
            self.assertEqual(caso[1], operador[0])
            self.assertNotEqual(caso[1], "100123")
            self.assertEqual(caso[2:], ["Dato de QA", "2026-05-19"])
            usuario, = paquete.filas(archivo, manifiesto, USUARIOS)
            self.assertEqual(usuario, [42, "qa_42", None, "qa_42@example.invalid", False, True, 42])
            evidencia, = carga.materializar(archivo, manifiesto, ARCHIVOS, self.raiz, {}, set())
            self.assertEqual(evidencia[1], caso[0])
            ruta = Path(evidencia[3])
            self.assertEqual(ruta.parent, self.raiz / "Files" / "Files_mtto")
            self.assertEqual(ruta.read_bytes(), carga.imagen_qa())
            self.assertEqual(evidencia[2], ruta.name)
            encontrados = set()
            usuario, = carga.materializar(archivo, manifiesto, USUARIOS, self.raiz,
                                           {"qa_42": "hash-de-prueba"}, encontrados)
            self.assertEqual(encontrados, {"qa_42"})
            self.assertEqual(usuario[2:6], ["hash-de-prueba", "qa_42@example.invalid", True, True])

    def test_proyeccion_sql_omite_credenciales_texto_libre_y_rutas(self):
        cursor = Mock()
        cursor.__iter__ = Mock(return_value=iter([]))
        list(sql.leer_filas(cursor, USUARIOS, self.esquema[USUARIOS]))
        consulta = cursor.execute.call_args.args[0]
        self.assertNotIn("[passwordhash]", consulta)
        self.assertNotIn("[email]", consulta)
        list(sql.leer_filas(cursor, CASOS, self.esquema[CASOS]))
        self.assertIn("CASE WHEN [version_libre] IS NULL", cursor.execute.call_args.args[0])
        list(sql.leer_filas(cursor, ARCHIVOS, self.esquema[ARCHIVOS]))
        consulta = cursor.execute.call_args.args[0]
        self.assertNotIn("[filepath]", consulta)
        self.assertIn("[Modulo]", consulta)
        with self.assertRaisesRegex(ValueError, "documento"):
            regla(CASOS, columna("documento"))

    def test_rechaza_contenido_modificado_y_no_sobrescribe_un_paquete(self):
        manifiesto = self.exportar()
        with self.assertRaises(FileExistsError):
            self.exportar()
        ruta = self.raiz / "modificado.zip"
        with ZipFile(self.paquete) as origen, ZipFile(ruta, "w") as copia:
            for nombre in origen.namelist():
                copia.writestr(nombre, b"[103, null, null, null]\n"
                               if nombre == f"{CASOS}.jsonl" else origen.read(nombre))
        with ZipFile(ruta) as archivo, self.assertRaisesRegex(ValueError, "huella inválida"):
            paquete.comprobar(archivo, manifiesto)

    def test_carga_revierte_si_una_escritura_falla(self):
        manifiesto = self.exportar()
        conexion = Mock()
        with (ZipFile(self.paquete) as archivo,
              patch.object(sql, "orden_de_carga", return_value=(USUARIOS, CASOS)),
              patch.object(sql, "bloquear_carga"),
              patch.object(sql, "insertar", side_effect=[None, RuntimeError("falló lote")])):
            with self.assertRaisesRegex(RuntimeError, "falló lote"):
                carga.cargar(conexion, Mock(), archivo, manifiesto, self.esquema, self.raiz, {})
        conexion.rollback.assert_called_once()
        conexion.commit.assert_not_called()

    def test_solo_confirma_despues_de_consumir_lotes_y_verificar_conteos(self):
        manifiesto = self.exportar()
        conexion = Mock()
        orden = tuple(self.esquema)
        with (ZipFile(self.paquete) as archivo,
              patch.object(sql, "orden_de_carga", return_value=orden),
              patch.object(sql, "bloquear_carga"),
              patch.object(sql, "insertar", side_effect=lambda _, __, ___, lotes: list(lotes)),
              patch.object(sql, "verificar_conteo") as verificar):
            carga.cargar(conexion, Mock(), archivo, manifiesto, self.esquema, self.raiz, {})
        self.assertEqual([c.args[1] for c in verificar.call_args_list], list(orden))
        conexion.commit.assert_called_once()
        conexion.rollback.assert_not_called()

    def test_rechaza_destino_no_marcado_y_origen_escribible(self):
        cursor = Mock()
        cursor.fetchone.return_value = ("SQL", "dano_qa", "READ_WRITE", None)
        with self.assertRaisesRegex(ValueError, "marcada"):
            sql.identidad(cursor, "SQL", "dano_qa", True)
        with self.assertRaisesRegex(ValueError, "solo lectura"):
            sql.identidad(cursor, "SQL", "dano_qa", False)
        with self.assertRaisesRegex(ValueError, "identidad"):
            sql.identidad(cursor, "OTRO", "dano_qa", True)
        cursor.fetchone.return_value = ("SQL", "dano_qa", "READ_WRITE", "qa")
        sql.identidad(cursor, "SQL", "dano_qa", True)

    def test_conserva_precision_decimal(self):
        self.assertEqual(json.dumps(Decimal("9007199254740993.01"), default=paquete.codificar),
                         '"9007199254740993.01"')

    def test_respaldo_y_restauracion_de_adjuntos(self):
        origen = self.raiz / "origen"
        subcarpeta = origen / "Files" / "Files_ppal"
        subcarpeta.mkdir(parents=True)
        (subcarpeta / "evidencia.txt").write_bytes(b"simulado")
        respaldo = self.raiz / "corte.adjuntos.zip"
        destino = self.raiz / "restaurado"
        media.guardar(origen, respaldo)
        media.restaurar(respaldo, destino)
        self.assertEqual((destino / "Files" / "Files_ppal" / "evidencia.txt").read_bytes(), b"simulado")
        with self.assertRaises(FileExistsError):
            media.restaurar(respaldo, destino)

    def test_respaldo_rechaza_ruta_fuera_del_destino(self):
        respaldo = self.raiz / "malicioso.zip"
        with ZipFile(respaldo, "w") as archivo:
            archivo.writestr("../escape.txt", "simulado")
        destino = self.raiz / "restaurado"
        with self.assertRaisesRegex(ValueError, "ruta inválida"):
            media.restaurar(respaldo, destino)
        self.assertFalse(destino.exists())
        self.assertFalse((self.raiz / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()
