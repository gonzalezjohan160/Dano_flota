-- Auditoría de base de datos (7-10-26), sección 5.6: permisos mínimos.
--
-- La aplicación no debe conectarse como sa ni como db_owner. Este rol tiene solo
-- lo que usa: leer, insertar y actualizar en sus esquemas, leer los catálogos y
-- borrar únicamente donde la aplicación borra. No puede borrar casos (el borrado
-- es lógico), gestiones ni correcciones, ni cambiar la estructura.
--
-- TI crea el login de la aplicación y lo agrega al rol (no va en el repositorio
-- porque lleva contraseña):
--   CREATE LOGIN <login_app> WITH PASSWORD = '<contraseña>';
--   CREATE USER <login_app> FOR LOGIN <login_app>;
--   ALTER ROLE rol_aplicacion_dano_flota ADD MEMBER <login_app>;
-- La sincronización de operadores además necesita SELECT sobre
-- [emoperation].[dbo].[em_view_employees].
IF DATABASE_PRINCIPAL_ID(N'rol_aplicacion_dano_flota') IS NULL
    CREATE ROLE rol_aplicacion_dano_flota AUTHORIZATION dbo;

GRANT SELECT, INSERT, UPDATE ON SCHEMA::flota TO rol_aplicacion_dano_flota;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::proceso TO rol_aplicacion_dano_flota;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::usuario TO rol_aplicacion_dano_flota;
GRANT SELECT ON SCHEMA::catalogo TO rol_aplicacion_dano_flota;
GRANT SELECT ON OBJECT::dbo.SchemaMigrations TO rol_aplicacion_dano_flota;

-- Únicos borrados físicos de la aplicación.
GRANT DELETE ON OBJECT::usuario.restablecimiento_contrasena TO rol_aplicacion_dano_flota;  -- enlaces vencidos
GRANT DELETE ON OBJECT::usuario.usuario_permiso TO rol_aplicacion_dano_flota;              -- reasignar permisos
GRANT DELETE ON OBJECT::usuario.tutorial TO rol_aplicacion_dano_flota;                     -- borrar un video
GRANT DELETE ON OBJECT::flota.operador TO rol_aplicacion_dano_flota;                       -- sincronización
GRANT DELETE ON OBJECT::proceso.cierre_laboral TO rol_aplicacion_dano_flota;               -- Operaciones retira su cierre
