"""Eliminacion de imagenes: pertenencia, auditoria y conservacion ante errores."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from servicios import edicion_imagenes as servicio


class ImagenesTests(unittest.TestCase):
    def test_identificadores_son_enteros_validos_y_sin_duplicados(self):
        self.assertEqual(servicio.validar_ids_imagenes([1, 1, 2]), [1, 2])
        for valores in (None, "1", [True], ["1"], [-1], [2_147_483_648], list(range(101))):
            with self.subTest(valores=str(valores)[:50]), self.assertRaises(ValueError):
                servicio.validar_ids_imagenes(valores)

    def test_rechaza_archivo_ajeno_o_de_otro_modulo_y_no_imagenes(self):
        for fila in (None, (9, "video.mp4", "/video.mp4"), (9, "doc.pdf", "/doc.pdf")):
            with patch.object(servicio.archivos, "buscar_imagen_de_operaciones", return_value=fila) as buscar:
                with self.assertRaises(ValueError):
                    servicio.preparar_eliminacion(MagicMock(), 7, [9])
                self.assertEqual(buscar.call_args.args[1:], (7, 9))

    def test_modelo_restringe_consulta_y_borrado_a_caso_y_operaciones(self):
        from modelos import archivos
        c = MagicMock(rowcount=1)
        for funcion in (archivos.buscar_imagen_de_operaciones, archivos.eliminar_imagen_de_operaciones):
            funcion(c, 7, 9)
            sql, valores = c.execute.call_args.args
            self.assertIn("Id_damage = ?", sql)
            self.assertIn("Modulo = 'Operaciones'", sql)
            self.assertEqual(valores, (9, 7))

    def test_eliminar_registro_no_borra_disco_antes_de_confirmar(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "foto.jpg"
            ruta.write_bytes(b"foto")
            imagen = dict(Id=9, FileName="foto.jpg", FilePath=str(ruta))
            with patch.object(servicio.archivos, "eliminar_imagen_de_operaciones"), \
                    patch.object(servicio.archivos, "ruta_tiene_referencias", return_value=False), \
                    patch.object(servicio.auditoria, "registrar_correccion") as auditar:
                rutas = servicio.eliminar_en_transaccion(MagicMock(), 7, [imagen], 3, "Imagen equivocada", directorio)
                self.assertEqual(rutas, [ruta.resolve()])
                self.assertTrue(ruta.exists())
                self.assertEqual(auditar.call_args.args[1:4], (7, "flota.table_damage_files", "imagen_eliminada"))
                self.assertEqual(auditar.call_args.args[6], 3)
                self.assertEqual(auditar.call_args.args[-1], "Imagen equivocada")

    def test_no_borra_rutas_compartidas_ni_fuera_de_carpeta(self):
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio) / "operaciones"
            base.mkdir()
            for compartida, ruta in ((True, base / "foto.jpg"), (False, Path(directorio) / "ajena.jpg")):
                with patch.object(servicio.archivos, "eliminar_imagen_de_operaciones"), \
                        patch.object(servicio.archivos, "ruta_tiene_referencias", return_value=compartida), \
                        patch.object(servicio.auditoria, "registrar_correccion"):
                    rutas = servicio.eliminar_en_transaccion(MagicMock(), 7,
                        [dict(Id=9, FileName="foto.jpg", FilePath=str(ruta))], 3, "motivo", base)
                    self.assertEqual(rutas, [])


class RutasImagenesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_mvc_operaciones as rutas
        cls.rutas = rutas
        rutas.MigracionOperacionesTests.setUpClass()

    def pedir(self, ids, motivo="Eliminar duplicada", falla=None):
        from unificado import operaciones_evento
        pruebas = self.rutas.MigracionOperacionesTests()
        with patch.object(operaciones_evento, "preparar_eliminacion", return_value=[dict(Id=9)]), \
                patch.object(operaciones_evento, "eliminar_en_transaccion", return_value=[Path("foto.jpg")]) as eliminar, \
                patch.object(operaciones_evento, "guardar_archivos"), \
                patch.object(operaciones_evento, "borrar_archivos") as borrar:
            if falla:
                eliminar.side_effect = RuntimeError("fallo simulado")
            respuesta, conexiones = pruebas.pedir("POST", "/Operaciones/actualizar_evento/7",
                json=dict(evento={}, archivos_eliminar=ids, motivo_modificacion=motivo))
            return respuesta, conexiones, eliminar, borrar

    def test_eliminacion_sola_confirma_y_limpia_despues(self):
        respuesta, conexiones, eliminar, borrar = self.pedir([9])
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json()["archivos_eliminados"], 1)
        self.assertEqual(conexiones[-1].eventos, ["commit", "close"])
        self.assertEqual(eliminar.call_args.args[1], 7)
        borrar.assert_called_once_with([Path("foto.jpg")])

    def test_fallo_revierte_y_no_borra_original(self):
        respuesta, conexiones, eliminar, borrar = self.pedir([9], falla=True)
        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(conexiones[-1].eventos, ["rollback", "close"])
        borrar.assert_called_once_with([])  # solo posibles subidas nuevas, nunca las originales

    def test_fallo_al_confirmar_no_borra_original(self):
        with patch.object(self.rutas.Conexion, "commit", side_effect=RuntimeError("commit")):
            respuesta, conexiones, _, borrar = self.pedir([9])
        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(conexiones[-1].eventos, ["rollback", "close"])
        borrar.assert_called_once_with([])

    def test_archivo_ajeno_responde_400_sin_escribir(self):
        pruebas = self.rutas.MigracionOperacionesTests()
        with patch.object(servicio.archivos, "buscar_imagen_de_operaciones", return_value=None):
            respuesta, conexiones = pruebas.pedir("POST", "/Operaciones/actualizar_evento/7",
                json=dict(evento={}, archivos_eliminar=[999], motivo_modificacion="motivo"))
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(any(sql.startswith(("INSERT", "UPDATE", "DELETE"))
                             for c in conexiones for sql, _ in c.consultas))

    def test_motivo_e_ids_invalidos_se_rechazan(self):
        for ids, motivo in (([9], ""), (["9"], "motivo"), ([-1], "motivo")):
            respuesta, _, eliminar, _ = self.pedir(ids, motivo)
            self.assertEqual(respuesta.status_code, 400)
            eliminar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
