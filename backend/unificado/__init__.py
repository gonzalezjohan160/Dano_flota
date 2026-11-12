"""CONTROLADORES del módulo unificado, uno por dominio.

  * configuracion.py — módulos, gestiones de Mtto/Svial y tipos de adjunto.
  * comun.py — acceso al módulo, config pública, adjuntos y valores en pesos.
  * bandeja.py — tabla principal de cada módulo y lista de móviles.
  * detalle.py — detalle cruzado de un caso.
  * archivos.py — guardar, borrar y descargar adjuntos.
  * operaciones_evento.py — editar, consultar operador y eliminar el evento.
  * operaciones.py — gestión de Operaciones y reincidencia del operador.
  * gestiones.py — ruta genérica "/<modulo>/<accion>" que reparte cada gestión.
  * mantenimiento.py y seguridad_vial.py — gestión de Mtto y de Svial.
  * laboral.py — gestión de Relaciones Laborales.
  * reapertura.py — reabrir un caso desde Operaciones o RRLL.

El blueprint, la conexión y la verificación de UF del caso viven en la fachada
backend_unificado.py, que registra estas rutas una sola vez. Los controladores
llaman a la sesion de repositories/ y fachada.verificar_acceso_uf_caso() para que sustituirlos
en la fachada (pruebas) los afecte a todos.
"""
# Si alguien importa primero un controlador (unificado.x), la fachada se carga
# antes, completa, y es ella quien importa y registra cada controlador.
import importlib

importlib.import_module("backend_unificado")
