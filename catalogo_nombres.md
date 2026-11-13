# Catálogo de nombres de archivos y carpetas

Este documento fija la convención y registra las rutas propuestas para una eventual migración. La aplicación sigue usando las rutas de la columna **Ruta actual**.

## Convención

- Usar `snake_case` en minúscula para archivos y carpetas del proyecto. Usar letras ASCII, números y guiones bajos, con extensiones en minúscula. Ejemplos: `historico_danos.html`, `modulo_unificado` y `permisos_roles.css`.
- Nombrar cada archivo por su pantalla o responsabilidad. Usar `templates/` para Jinja, `static/js/` para JavaScript, `static/css/` para CSS y `static/images/` para imágenes. Estas carpetas hacen redundantes los prefijos `Front_`, `Script_` y `Style_`.
- Usar el nombre del módulo en minúscula en cada capa. Los módulos Python existentes ya siguen la convención, incluidos `backend_dashboard.py` y `backend/unificado/`. El prefijo `backend_` identifica los controladores existentes.
- Conservar el guion bajo inicial de los parciales Jinja y los nombres especiales de Python, como `__init__.py` y `__main__.py`. Conservar los prefijos `test_` y la numeración de las migraciones.
- Mantener los nombres de herramientas y configuración que se usan tal como están, como `.gitignore`, `.pre-commit-config.yaml`, `.env.example`, `requirements-dev.txt` y `gunicorn.conf.py`.

El catálogo incluye rutas de código, recursos y archivos de despliegue del repositorio. Los entornos virtuales, las cachés y los archivos generados o cargados en ejecución quedan fuera del inventario. Cada ruta de archivo muestra su destino completo, incluso cuando el único cambio es la carpeta que lo contiene.


## Carpetas

| Ruta actual | Ruta propuesta |
| --- | --- |
| `frontend` | `templates` |
| `frontend/parciales` | `templates/parciales` |
| `frontend/parciales/modulo_unificado` | `templates/parciales/modulo_unificado` |
| `Static` | `static` |
| `Static/Script` | `static/js` |
| `Static/Style` | `static/css` |
| `Static/Images` | `static/images` |
| `SQL damage_to_fleet` | `sql` |
| `Static/Script/Capturador` | `static/js/capturador` |
| `Static/Script/Capturador_reparaciones` | `static/js/capturador_reparaciones` |
| `Static/Script/Historico_danos` | `static/js/historico_danos` |
| `Static/Script/Historicos_comun` | `static/js/historicos_comun` |
| `Static/Script/Modulo_unificado` | `static/js/modulo_unificado` |

## Plantillas HTML

| Ruta actual | Ruta propuesta |
| --- | --- |
| `frontend/Capturador_reparaciones.html` | `templates/capturador_reparaciones.html` |
| `frontend/Formulario.html` | `templates/capturador.html` |
| `frontend/Front_dashboard.html` | `templates/dashboard.html` |
| `frontend/Front_error.html` | `templates/error.html` |
| `frontend/Front_historico_danos.html` | `templates/historico_danos.html` |
| `frontend/Front_historico_movil.html` | `templates/historico_movil.html` |
| `frontend/Front_login.html` | `templates/login.html` |
| `frontend/Front_olvido_contrasena.html` | `templates/olvido_contrasena.html` |
| `frontend/Front_permisos_roles.html` | `templates/permisos_roles.html` |
| `frontend/Front_profile.html` | `templates/profile.html` |
| `frontend/Front_resetear_contrasena.html` | `templates/resetear_contrasena.html` |
| `frontend/Front_usuarios.html` | `templates/usuarios.html` |
| `frontend/Interfaz.html` | `templates/interfaz.html` |
| `frontend/Modulo_unificado.html` | `templates/modulo_unificado.html` |
| `frontend/tutoriales.html` | `templates/tutoriales.html` |
| `frontend/parciales/modulo_unificado/_filtros.html` | `templates/parciales/modulo_unificado/_filtros.html` |
| `frontend/parciales/modulo_unificado/_flujo_operaciones.html` | `templates/parciales/modulo_unificado/_flujo_operaciones.html` |
| `frontend/parciales/modulo_unificado/_lightbox.html` | `templates/parciales/modulo_unificado/_lightbox.html` |
| `frontend/parciales/modulo_unificado/_modal_detalle.html` | `templates/parciales/modulo_unificado/_modal_detalle.html` |
| `frontend/parciales/modulo_unificado/_modal_gestion.html` | `templates/parciales/modulo_unificado/_modal_gestion.html` |
| `frontend/parciales/modulo_unificado/_scripts.html` | `templates/parciales/modulo_unificado/_scripts.html` |
| `frontend/parciales/modulo_unificado/_tabla.html` | `templates/parciales/modulo_unificado/_tabla.html` |

## JavaScript

| Ruta actual | Ruta propuesta |
| --- | --- |
| `Static/Script/Capturador/adjuntos_envio.js` | `static/js/capturador/adjuntos_envio.js` |
| `Static/Script/Capturador/camara_fotos.js` | `static/js/capturador/camara_fotos.js` |
| `Static/Script/Capturador/formulario.js` | `static/js/capturador/formulario.js` |
| `Static/Script/Capturador/video_audio.js` | `static/js/capturador/video_audio.js` |
| `Static/Script/Capturador_reparaciones/adjuntos_envio.js` | `static/js/capturador_reparaciones/adjuntos_envio.js` |
| `Static/Script/Capturador_reparaciones/formulario_fotos.js` | `static/js/capturador_reparaciones/formulario_fotos.js` |
| `Static/Script/Capturador_reparaciones/video_audio.js` | `static/js/capturador_reparaciones/video_audio.js` |
| `Static/Script/Historico_danos/detalle.js` | `static/js/historico_danos/detalle.js` |
| `Static/Script/Historico_danos/tabla.js` | `static/js/historico_danos/tabla.js` |
| `Static/Script/Historicos_comun/duraciones_galeria.js` | `static/js/historicos_comun/duraciones_galeria.js` |
| `Static/Script/Historicos_comun/festivos_adjuntos.js` | `static/js/historicos_comun/festivos_adjuntos.js` |
| `Static/Script/Historicos_comun/lightbox_mapa.js` | `static/js/historicos_comun/lightbox_mapa.js` |
| `Static/Script/Modulo_unificado/adjuntos.js` | `static/js/modulo_unificado/adjuntos.js` |
| `Static/Script/Modulo_unificado/configuracion.js` | `static/js/modulo_unificado/configuracion.js` |
| `Static/Script/Modulo_unificado/detalle.js` | `static/js/modulo_unificado/detalle.js` |
| `Static/Script/Modulo_unificado/edicion_evento.js` | `static/js/modulo_unificado/edicion_evento.js` |
| `Static/Script/Modulo_unificado/envio.js` | `static/js/modulo_unificado/envio.js` |
| `Static/Script/Modulo_unificado/filtros.js` | `static/js/modulo_unificado/filtros.js` |
| `Static/Script/Modulo_unificado/flujo_operaciones.js` | `static/js/modulo_unificado/flujo_operaciones.js` |
| `Static/Script/Modulo_unificado/formulario.js` | `static/js/modulo_unificado/formulario.js` |
| `Static/Script/Modulo_unificado/formulario_campos.js` | `static/js/modulo_unificado/formulario_campos.js` |
| `Static/Script/Modulo_unificado/inicio.js` | `static/js/modulo_unificado/inicio.js` |
| `Static/Script/Modulo_unificado/tabla.js` | `static/js/modulo_unificado/tabla.js` |
| `Static/Script/Modulo_unificado/utilidades.js` | `static/js/modulo_unificado/utilidades.js` |
| `Static/Script/Modulo_unificado/validacion.js` | `static/js/modulo_unificado/validacion.js` |
| `Static/Script/Script_dashboard.js` | `static/js/dashboard.js` |
| `Static/Script/Script_historico_movil.js` | `static/js/historico_movil.js` |
| `Static/Script/Script_interfaz.js` | `static/js/interfaz.js` |
| `Static/Script/Script_permisos_roles.js` | `static/js/permisos_roles.js` |
| `Static/Script/Script_profile.js` | `static/js/profile.js` |
| `Static/Script/script_tutoriales.js` | `static/js/tutoriales.js` |
| `Static/Script/Script_utils.js` | `static/js/utils.js` |

## Hojas de estilo

| Ruta actual | Ruta propuesta |
| --- | --- |
| `Static/Style/Style_captur.css` | `static/css/capturador.css` |
| `Static/Style/Style_dashboard.css` | `static/css/dashboard.css` |
| `Static/Style/Style_historico_danos.css` | `static/css/historico_danos.css` |
| `Static/Style/Style_interfaz.css` | `static/css/interfaz.css` |
| `Static/Style/Style_login.css` | `static/css/login.css` |
| `Static/Style/Style_login_fondo.css` | `static/css/login_fondo.css` |
| `Static/Style/Style_modulo_unificado.css` | `static/css/modulo_unificado.css` |
| `Static/Style/Style_modulos.css` | `static/css/modulos.css` |
| `Static/Style/Style_permisos_roles.css` | `static/css/permisos_roles.css` |
| `Static/Style/Style_roles.css` | `static/css/roles.css` |
| `Static/Style/Style_tutoriales.css` | `static/css/tutoriales.css` |
| `Static/Style/Style_usuario.css` | `static/css/usuario.css` |
| `Static/Style/Style_utilidades.css` | `static/css/utilidades.css` |

## Imágenes

| Ruta actual | Ruta propuesta |
| --- | --- |
| `Static/Images/Bus.png` | `static/images/bus.png` |
| `Static/Images/Dashboard.png` | `static/images/dashboard.png` |
| `Static/Images/favicon.png` | `static/images/favicon.png` |
| `Static/Images/Fondo_login.jpg` | `static/images/fondo_login.jpg` |
| `Static/Images/laboral.png` | `static/images/laboral.png` |
| `Static/Images/Logo.png` | `static/images/logo.png` |
| `Static/Images/Logout.png` | `static/images/logout.png` |
| `Static/Images/Mtto.png` | `static/images/mtto.png` |
| `Static/Images/Svial.png` | `static/images/svial.png` |
| `Static/Images/T_I.png` | `static/images/t_i.png` |
| `Static/Images/Tabla_codigos.jpg` | `static/images/tabla_codigos.jpg` |
| `Static/Images/usuario.png` | `static/images/usuario.png` |
| `Static/Images/videos.png` | `static/images/videos.png` |

## SQL, despliegue y archivos de raíz

| Ruta actual | Ruta propuesta |
| --- | --- |
| `arquitectura-g-fleetdamage.png` | `arquitectura_g_fleetdamage.png` |
| `deploy/README.md` | `deploy/readme.md` |
| `deploy/sql/BD-12_unidad_funcional.sql` | `deploy/sql/bd_12_unidad_funcional.sql` |
| `deploy/sql/BD-16_bits_not_null_defaults.sql` | `deploy/sql/bd_16_bits_not_null_defaults.sql` |
| `deploy/sql/BD-17_tutoriales_pk_longitudes.sql` | `deploy/sql/bd_17_tutoriales_pk_longitudes.sql` |
| `deploy/sql/BD-5_unicidad_gestiones.sql` | `deploy/sql/bd_5_unicidad_gestiones.sql` |
| `deploy/sql/BD-6_usuarios_id.sql` | `deploy/sql/bd_6_usuarios_id.sql` |
| `deploy/sql/BD_indices_fk_dashboard.sql` | `deploy/sql/bd_indices_fk_dashboard.sql` |
| `deploy/sql/BD_montos_bigint_no_negativos.sql` | `deploy/sql/bd_montos_bigint_no_negativos.sql` |
| `SQL damage_to_fleet/script.sql` | `sql/script.sql` |

## Rutas que ya cumplen

Se mantienen las rutas de `backend/` y `tests/`, incluidas las migraciones en `backend/migrations/`. Las demás rutas que no aparecen en las tablas conservan su nombre y ubicación.

## Verificación para una futura migración

1. Aplicar los renombres por grupos en commits dedicados. En Windows, usar un nombre intermedio al cambiar únicamente las mayúsculas de una ruta.
2. Actualizar las referencias del grupo en Flask (`static_folder`, `template_folder`, `render_template` y `url_for`), Jinja (`extends` e `include`), URLs directas, imports, pruebas y documentación, según corresponda.
3. Verificar en un entorno sensible a mayúsculas y minúsculas que las pantallas carguen sus plantillas, estilos, scripts e imágenes. Revisar las rutas con `git ls-files` y ejecutar las pruebas del repositorio.

La entrega actual cubre la convención y el catálogo. La conformidad de las rutas se verificará cuando se ejecuten los renombres.
