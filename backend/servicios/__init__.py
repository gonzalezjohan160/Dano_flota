"""SERVICIOS: reglas de negocio que comparten varios controladores.

Solo va aquí lo que de verdad usan varios módulos. Las funciones reciben un
cursor ya abierto y los datos que necesitan; no usan request, session ni Flask,
y no abren ni cierran conexiones (eso lo hace el controlador).

  * flujo_caso.py — flujo del caso entre Operaciones, Mtto, Svial y RRLL
    (usado por el módulo unificado y por Histórico de daños).
"""
