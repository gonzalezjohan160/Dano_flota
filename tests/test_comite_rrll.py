"""COMITE: almacenamiento, clasificacion y consulta del ultimo seguimiento."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from servicios.flujo_caso import normalizar_procesos_pendientes, caso_en_comite, estado_rrll_para_exportacion
from modelos.laboral import ULTIMO_PROCESO_LABORAL_SQL


class ComiteTests(unittest.TestCase):
    def test_guarda_comite_canonico_y_se_puede_combinar_con_areas(self):
        self.assertEqual(normalizar_procesos_pendientes(" comite ")[0], "COMITE")
        texto, procesos = normalizar_procesos_pendientes("COMITE, OPERACIONES")
        self.assertEqual(texto, "OPERACIONES, COMITE")
        self.assertTrue(caso_en_comite(texto))
        todos, _ = normalizar_procesos_pendientes("MANTENIMIENTO, OPERACIONES, SEGURIDAD VIAL, COMITE")
        self.assertLessEqual(len(todos), 50)

    def test_completo_sigue_siendo_exclusivo(self):
        with self.assertRaises(ValueError):
            normalizar_procesos_pendientes("COMPLETO, COMITE")

    def test_comite_es_token_completo_y_cerrado_tiene_prioridad(self):
        self.assertFalse(caso_en_comite("PRECOMITE"))
        self.assertFalse(caso_en_comite("COMITE", True))
        self.assertEqual(estado_rrll_para_exportacion(dict(pendiente_proceso_actual="COMITE")), "COMITE")
        self.assertEqual(estado_rrll_para_exportacion(dict(pendiente_proceso_actual="COMITE", estado_caso=1, cerrado_por_laboral=1)), "CERRADO")
        self.assertNotEqual(estado_rrll_para_exportacion(dict(pendiente_proceso_actual="COMPLETO")), "COMITE")

    def test_ultimo_seguimiento_desempata_por_id(self):
        self.assertIn("ORDER BY lm.Fecha_registro DESC, lm.Id_info_laboral DESC", ULTIMO_PROCESO_LABORAL_SQL)

    def test_ruta_rrll_persiste_comite_sin_reabrir_areas(self):
        import test_mvc_unificado_rutas as rutas
        rutas.RutasDelModuloUnificadoTests.setUpClass()
        pruebas = rutas.RutasDelModuloUnificadoTests()
        respuesta, conexiones = pruebas.pedir("POST", "/laboral/agregar_rl", rutas.caso(), data={
            "Id_damage_to_fleet": "7", "observaciones_1": "Pendiente de comite",
            "Estado_caso": "COMITE", "Revinf": "NO"})
        self.assertEqual(respuesta.status_code, 200)
        escrituras = pruebas.escrituras(conexiones[-1])
        self.assertEqual(len(escrituras), 1)
        self.assertEqual(escrituras[0][1][2], "COMITE")
        self.assertEqual(conexiones[-1].eventos, ["commit", "cursor.close", "close"])


if __name__ == "__main__":
    unittest.main()
