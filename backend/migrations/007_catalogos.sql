-- Auditoría de base de datos (7-10-26), hallazgo 1 y sección 4 (3FN): catálogos.
--
-- UF, tipología, ruta, área, centro de operaciones, zona y tipo de daño se
-- guardaban como texto repetido en cada caso. Ahora viven en el esquema catalogo y
-- los casos los referencian con claves foráneas (migración 011, con ON UPDATE
-- CASCADE: corregir un nombre es cambiar una sola fila del catálogo).
--
-- Se llenan con las listas que usaban los formularios y con los valores que ya
-- tienen los casos. Los valores históricos que el formulario ya no ofrece quedan
-- con activo = 0: siguen siendo válidos para los casos viejos pero no se listan.
-- Los formularios leen estas tablas (activo = 1, en el orden de "orden").
IF SCHEMA_ID(N'catalogo') IS NULL
    EXEC (N'CREATE SCHEMA catalogo AUTHORIZATION dbo;');

CREATE TABLE catalogo.unidad_funcional (
    id tinyint NOT NULL CONSTRAINT PK_unidad_funcional PRIMARY KEY,
    prefijo_movil varchar(5) NOT NULL CONSTRAINT UQ_unidad_funcional_prefijo_movil UNIQUE
);

CREATE TABLE catalogo.tipologia (
    nombre varchar(20) NOT NULL CONSTRAINT PK_tipologia PRIMARY KEY
);

CREATE TABLE catalogo.ruta (
    nombre varchar(40) NOT NULL CONSTRAINT PK_ruta PRIMARY KEY,
    activo bit NOT NULL CONSTRAINT DF_ruta_activo DEFAULT (1)
);

-- Una ruta puede servir a varias UF (PATIO y TRANSITO A PATIO están en las dos).
CREATE TABLE catalogo.ruta_unidad_funcional (
    ruta varchar(40) NOT NULL
        CONSTRAINT FK_ruta_unidad_funcional_ruta REFERENCES catalogo.ruta (nombre) ON UPDATE CASCADE,
    unidad_funcional_id tinyint NOT NULL
        CONSTRAINT FK_ruta_unidad_funcional_unidad_funcional REFERENCES catalogo.unidad_funcional (id),
    orden smallint NOT NULL,
    CONSTRAINT PK_ruta_unidad_funcional PRIMARY KEY (ruta, unidad_funcional_id)
);

-- Los códigos de operador del 1 al 7 no son personas sino áreas; el resto es OBZ.
CREATE TABLE catalogo.area (
    nombre varchar(50) NOT NULL CONSTRAINT PK_area PRIMARY KEY,
    codigo_operador varchar(10) NULL,
    orden smallint NOT NULL,
    activo bit NOT NULL CONSTRAINT DF_area_activo DEFAULT (1)
);

CREATE TABLE catalogo.centro_operacion (
    nombre varchar(40) NOT NULL CONSTRAINT PK_centro_operacion PRIMARY KEY,
    orden smallint NOT NULL,
    activo bit NOT NULL CONSTRAINT DF_centro_operacion_activo DEFAULT (1)
);

CREATE TABLE catalogo.zona_dano (
    nombre varchar(40) NOT NULL CONSTRAINT PK_zona_dano PRIMARY KEY,
    orden smallint NOT NULL,
    activo bit NOT NULL CONSTRAINT DF_zona_dano_activo DEFAULT (1)
);

CREATE TABLE catalogo.tipo_dano (
    nombre varchar(40) NOT NULL CONSTRAINT PK_tipo_dano PRIMARY KEY,
    orden smallint NOT NULL,
    activo bit NOT NULL CONSTRAINT DF_tipo_dano_activo DEFAULT (1)
);

INSERT INTO catalogo.unidad_funcional (id, prefijo_movil) VALUES (10, 'Z32-'), (16, 'Z34-');

INSERT INTO catalogo.tipologia (nombre) VALUES ('PADRÓN'), ('BUSETÓN');
INSERT INTO catalogo.tipologia (nombre)
SELECT DISTINCT LTRIM(RTRIM(m.Tipologia_Movil))
FROM flota.table_Moviles AS m
WHERE NULLIF(LTRIM(RTRIM(m.Tipologia_Movil)), '') IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM catalogo.tipologia AS t WHERE t.nombre = LTRIM(RTRIM(m.Tipologia_Movil)));

INSERT INTO catalogo.ruta (nombre) VALUES
    ('CG147'), ('DG208'), ('CA127'), ('CH131'), ('CA129'), ('CA124'),
    ('CL149'), ('CB144'), ('CG137'), ('CA134'), ('CB138'), ('CA151'), ('CF154'), ('CA153'), ('CB145'),
    ('TRANSITO A PATIO'), ('PATIO');
INSERT INTO catalogo.ruta_unidad_funcional (ruta, unidad_funcional_id, orden) VALUES
    ('CG147', 10, 1), ('DG208', 10, 2), ('CA127', 10, 3), ('CH131', 10, 4), ('CA129', 10, 5),
    ('CA124', 10, 6), ('TRANSITO A PATIO', 10, 7), ('PATIO', 10, 8),
    ('CL149', 16, 1), ('CB144', 16, 2), ('CG137', 16, 3), ('CA134', 16, 4), ('CB138', 16, 5),
    ('CA151', 16, 6), ('CF154', 16, 7), ('CA153', 16, 8), ('CB145', 16, 9),
    ('TRANSITO A PATIO', 16, 10), ('PATIO', 16, 11);
INSERT INTO catalogo.ruta (nombre, activo)
SELECT DISTINCT d.Ruta, 0
FROM flota.table_damage_to_fleet AS d
WHERE d.Ruta IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM catalogo.ruta AS r WHERE r.nombre = d.Ruta);

INSERT INTO catalogo.area (nombre, codigo_operador, orden) VALUES
    ('OBZ', NULL, 0), ('MANTENIMIENTO', '1', 1), ('OPERACIONES', '2', 2), ('LAVADO', '3', 3),
    ('CAPACITACIÓN OBZ', '4', 4), ('TERCERO', '5', 5), ('TANQUEO', '6', 6), ('ADMINISTRATIVO', '7', 7);
INSERT INTO catalogo.area (nombre, codigo_operador, orden, activo)
SELECT DISTINCT d.Area, NULL, 99, 0
FROM flota.table_damage_to_fleet AS d
WHERE d.Area IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM catalogo.area AS a WHERE a.nombre = d.Area);
CREATE UNIQUE INDEX UQ_area_codigo_operador ON catalogo.area (codigo_operador)
    WHERE codigo_operador IS NOT NULL;

INSERT INTO catalogo.centro_operacion (nombre, orden) VALUES
    ('GAITANA', 1), ('SAN ANDRÉS', 2), ('BILBAO', 3), ('SAN BERNARDINO', 4);
INSERT INTO catalogo.centro_operacion (nombre, orden, activo)
SELECT DISTINCT d.Centro_operaciones, 99, 0
FROM flota.table_damage_to_fleet AS d
WHERE d.Centro_operaciones IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM catalogo.centro_operacion AS c WHERE c.nombre = d.Centro_operaciones);

INSERT INTO catalogo.zona_dano (nombre, orden) VALUES
    ('LATERAL IZQUIERDO', 1), ('LATERAL DERECHO', 2), ('FRONTAL', 3), ('POSTERIOR', 4),
    ('TECHO', 5), ('ESPEJOS', 6), ('PUERTAS', 7), ('VIDRIOS', 8), ('LLANTAS', 9), ('ITS', 10),
    ('SIRCI', 11), ('CARROCERÍA INTERNA', 12), ('TREN MOTRIZ', 13), ('CHASIS', 14);
INSERT INTO catalogo.zona_dano (nombre, orden, activo)
SELECT DISTINCT d.Zona_dano, 99, 0
FROM flota.table_damage_to_fleet AS d
WHERE d.Zona_dano IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM catalogo.zona_dano AS z WHERE z.nombre = d.Zona_dano);

INSERT INTO catalogo.tipo_dano (nombre, orden) VALUES
    ('CONDUCTA OPERACIONAL', 1), ('INFRAESTRUCTURA PATIO', 2), ('INFRAESTRUCTURA VIAL', 3),
    ('VANDALISMO', 4), ('MECÁNICO', 5), ('SINIESTRO VIAL', 6), ('ALISTAMIENTO', 7);
INSERT INTO catalogo.tipo_dano (nombre, orden, activo)
SELECT DISTINCT d.Dano_ocasionado, 99, 0
FROM flota.table_damage_to_fleet AS d
WHERE d.Dano_ocasionado IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM catalogo.tipo_dano AS t WHERE t.nombre = d.Dano_ocasionado);
