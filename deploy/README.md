# Plantillas de despliegue

| Archivo | Uso |
|---|---|
| `supervisor/dano_flota.conf.template` | Programa de Supervisor (Gunicorn con el usuario de servicio) |
| `nginx/dano_flota.conf.template` | Sitio nginx con HTTPS y cabeceras `X-Forwarded-*` |

Las variables `${...}` se completan con `envsubst`. El procedimiento completo
(usuario de servicio, permisos, generación de estas plantillas y verificación)
está en el `readme.md` de la raíz, sección 3 "Instalación en un servidor nuevo".
