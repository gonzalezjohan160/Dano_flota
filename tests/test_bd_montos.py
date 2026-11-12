"""Montos enteros no negativos: validacion compartida y respuestas HTTP 400."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from servicios.montos import leer_valor_monetario, MAXIMO_MONTO_APLICACION


class MontosTests(unittest.TestCase):
    def test_cero_enteros_grandes_y_miles_correctos(self):
        for texto, esperado in [("0", 0), (0, 0), ("2147483648", 2147483648),
                                ("$ 1.500.000", 1500000), ("$ 2,000", 2000),
                                (" 350000 ", 350000), (str(MAXIMO_MONTO_APLICACION), MAXIMO_MONTO_APLICACION)]:
            with self.subTest(texto=texto):
                self.assertEqual(leer_valor_monetario(texto, "Monto"), esperado)

    def test_rechaza_negativos_decimales_y_agrupaciones_invalidas(self):
        for texto in ("-1", "abc", "1,50", "1.50", "1.234,50", "1,234.50", "1e6",
                      "１２", "1..000", "1,00,000", "$", "$ $ 1", "1 50", True, 1.5):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                leer_valor_monetario(texto, "Monto")

    def test_limites_y_entradas_desmesuradas(self):
        for texto in (str(MAXIMO_MONTO_APLICACION + 1), "9223372036854775808", "9" * 10000):
            with self.subTest(longitud=len(texto)), self.assertRaises(ValueError):
                leer_valor_monetario(texto, "Monto")

    def test_vacios_opcionales_son_null_obligatorios_se_rechazan(self):
        for texto in (None, "", "   "):
            with self.subTest(texto=texto):
                self.assertIsNone(leer_valor_monetario(texto, "Monto"))
                with self.assertRaises(ValueError):
                    leer_valor_monetario(texto, "Monto", obligatorio=True)


class RutasMontosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_mvc_capturador_reparaciones as capturadores
        import test_mvc_unificado_rutas as unificado
        cls.capturadores = capturadores
        cls.unificado = unificado
        capturadores.MigracionCapturadorReparacionesTests.setUpClass()
        unificado.RutasDelModuloUnificadoTests.setUpClass()

    def test_reparaciones_rechaza_montos_invalidos_sin_abrir_conexion(self):
        pruebas = self.capturadores.MigracionCapturadorReparacionesTests()
        for valor in ("-1", "abc", "1,50", "9223372036854775808"):
            with self.subTest(valor=valor):
                respuesta, conexiones = pruebas.pedir(
                    self.capturadores.backend_reparaciones, "POST", "/Capturador_rep/submit",
                    pruebas.formulario_reparacion(costo=valor))
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(conexiones, [])

    def test_reparaciones_conserva_cero_y_montos_superiores_a_int(self):
        pruebas = self.capturadores.MigracionCapturadorReparacionesTests()
        for valor in ("0", "2147483648", "$ 1.500.000"):
            with self.subTest(valor=valor):
                respuesta, conexiones = pruebas.pedir(
                    self.capturadores.backend_reparaciones, "POST", "/Capturador_rep/submit",
                    pruebas.formulario_reparacion(costo=valor))
                self.assertEqual(respuesta.status_code, 200)
                inserciones = [(sql, args) for sql, args in conexiones[0].consultas
                               if sql.startswith("INSERT INTO proceso.table_intervenciones ")]
                self.assertEqual(inserciones[0][1][0][1], 10)
                self.assertEqual(inserciones[0][1][0][4], leer_valor_monetario(valor, "Monto"))
                self.assertEqual(conexiones[0].commits, 1)

    def test_areas_rechazan_montos_invalidos_antes_de_escribir(self):
        pruebas = self.unificado.RutasDelModuloUnificadoTests()
        for url, campo, extra in (
            ("/Mtto/agregar_mtto", "Costo", {}),
            ("/Svial/agregar_svial", "valor_conciliado_terceros", {"Observaciones_svial": "s"}),
            ("/laboral/agregar_rl", "Costo", {"observaciones_1": "o", "Estado_caso": "COMPLETO"}),
            ("/Operaciones/agregar_oper", "valor_conciliado_oper", {"observaciones_1": "o"}),
            ("/Operaciones/agregar_oper", "costo_valor", {"observaciones_1": "o"}),
        ):
            for valor in ("-1", "abc", "1,50"):
                with self.subTest(url=url, campo=campo, valor=valor):
                    datos = dict(extra, Id_damage_to_fleet="7")
                    datos[campo] = valor
                    respuesta, conexiones = pruebas.pedir("POST", url, self.unificado.caso(), data=datos)
                    self.assertEqual(respuesta.status_code, 400)
                    self.assertTrue(all(not pruebas.escrituras(c) for c in conexiones))


if __name__ == "__main__":
    unittest.main()
