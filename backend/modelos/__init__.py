"""MODELOS: el acceso a datos de la aplicación (consultas SQL a SQL Server).

Reglas de esta carpeta:
  * Aquí vive el SQL: consultas parametrizadas con "?" y nada de texto del usuario
    pegado dentro de la consulta.
  * Las funciones reciben un cursor ya abierto y los datos que necesitan (filtros,
    UF autorizadas, identificadores). No usan request, session ni nada de Flask.
  * Quien llama (el controlador) abre la conexión, decide permisos y respuestas, y
    cierra la conexión pase lo que pase.

Módulos migrados:
  * historico_movil.py — Histórico móvil (etapa 1).
  * dashboard.py — consultas del Dashboard (etapa 2).
  * usuarios.py — usuarios, permisos y perfil.
  * tutoriales.py — consultas de tutoriales.
  * flota.py — vehículos y conductores, compartido por los dos capturadores.
  * capturador.py — registro de un caso nuevo y sus adjuntos.
  * reparaciones.py — registro de una reparación y sus adjuntos.
  * auditoria.py — registro de correcciones (compartido por los módulos de gestión).
  * Módulo unificado (controladores en unificado/):
      casos.py — estado, cierre y reapertura del caso;
      bandeja.py — tabla principal de cada módulo y móviles;
      detalle_caso.py — detalle cruzado y adjuntos del caso;
      archivos.py — adjuntos (solo tablas de la lista permitida);
      operaciones.py, mantenimiento.py, seguridad_vial.py, laboral.py — gestión de cada módulo.
  * autenticacion.py — login, estado de la sesión, permisos y recuperación de contraseña
    (huellas de token, nunca el token).
  * historico_danos.py y historico_danos_exportacion.py — tabla, detalle y Excel de Histórico de daños.
  * sincronizacion_operadores.py — table_drivers contra la vista de empleados (tarea programada).
"""
