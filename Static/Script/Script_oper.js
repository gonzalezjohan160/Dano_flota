//======================================================
// VARIABLES GLOBALES
//======================================================

let inputAdjuntos = null;
let listaAdjuntos = null;
let adjuntosSeleccionados = [];

let registros = [];
let movilSeleccionado = "";

// Paginación de la tabla principal (estilo Gmail: 30 filas por página).
const FILAS_POR_PAGINA = 30;
let paginaActual = 1;
let listaTablaActual = []; // lista (ya filtrada) que se está paginando


//======================================================
// CONFIGURACIÓN DE TABLAS DEL MODAL (detalle cruzado)
//======================================================

const DETAIL_CONFIG = {

    general: [
        { key: "fecha", label: "FECHA EVENTO" },
        { key: "Movil", label: "MÓVIL" },
        { key: "Codigo", label: "CÓDIGO" },
        { key: "Nombre", label: "NOMBRE" },
        { key: "Area", label: "ÁREA" },
        { key: "Ruta", label: "RUTA" },
        { key: "Version_libre", label: "VERSIÓN LIBRE" },
        { key: "Zona_dano", label: "ZONA DEL DAÑO" },
        { key: "Parte_afectada", label: "PARTE AFECTADA" },
        { key: "Dano_ocasionado", label: "DAÑO OCASIONADO POR" },
        { key: "Centro_operaciones", label: "CENTRO OPERACIONAL" },
        { key: "Registrador", label: "RESPONSABLE DILIGENCIAMIENTO" },
        { key: "fecha_r", label: "FECHA REGISTRO" },
        { key: "Direccion", label: "DIRECCIÓN" }
    ],

    oper: [
        { key: "Observaciones_operaciones", label: "OBSERVACIONES OPERACIONALES" },
        { key: "rev_error", label: "INFO. CORRECTA" },
        { key: "Observaciones_correctivos", label: "OBSERVACIONES ADICIONALES" }
    ],

    mtto: [
        { key: "Costo", label: "COSTO", formato: "moneda" },
        { key: "dano_adicional", label: "DAÑO ADICIONAL" },
        { key: "dano_adicional_detalle", label: "DESCRIPCIÓN DEL DAÑO ADICIONAL" },
        { key: "observaciones", label: "OBSERVACIONES" }
    ],

    svial: [
        { key: "Observaciones_svial", label: "OBSERVACIONES" }
    ],

    laboral_estado: [
        { key: "Tipo_cerrado", label: "TIPO DE CIERRE" },
        { key: "Cerrado", label: "CERRADO" },
        { key: "Valor_conciliado", label: "VALOR CONCILIADO", formato: "moneda" }
    ]

};


//======================================================
// CONFIGURACIÓN DE FORMULARIOS (por sección "propia")
//======================================================

const FORM_CONFIG = {

    oper: {
        endpoint: "agregar_oper",
        campos: [
            { id: "campo_principal", nombre: "observaciones_1" },
            { id: "observaciones", nombre: "observacionesExtra" }
        ]
    },

    mtto: {
        endpoint: "agregar_mtto",
        campos: [
            { id: "campo_principal", nombre: "Costo" }
        ]
    },

    svial: {
        endpoint: "agregar_svial",
        campos: [
            { id: "campo_principal", nombre: "Observaciones_svial" }
        ]
    },

    laboral: {
        endpoint: "agregar_rl",
        campos: [
            { id: "campo_principal", nombre: "observaciones_1" },
            { id: "fecha_presentacion", nombre: "Fecha_presentacion_input" },
            { id: "estado_caso", nombre: "Estado_caso" },
            { id: "valor_conciliado", nombre: "Costo" }
        ]
    }

};

const NOMBRE_SECCION = {
    oper: "OPERACIONAL",
    mtto: "MANTENIMIENTO",
    svial: "SEGURIDAD VIAL",
    laboral: "RELACIONES LABORALES"
};


//======================================================
// DOM READY
//======================================================

document.addEventListener("DOMContentLoaded", () => {

    //--------------------------------------------------
    // CARGAR CONFIG DEL MÓDULO (enviada por el backend)
    //--------------------------------------------------

    let CFG = null;

    try {
        const scriptCfg = document.getElementById("modulo-config-json");
        CFG = JSON.parse(scriptCfg.textContent);
    } catch (error) {
        console.error("No se pudo leer la configuración del módulo:", error);
        return;
    }

    if (!CFG) {
        console.error("No existe configuración para:", MODULO);
        return;
    }

    // Set de secciones visibles para consultas rápidas
    const SECCIONES_VISIBLES = new Set(CFG.seccionesVisibles || []);

    // Las columnas ESTADO OPER./MTTO./SVIAL de la tabla principal solo
    // tienen sentido en Relaciones Laborales (es el único módulo que
    // necesita ver, de un vistazo, si las demás áreas ya diligenciaron
    // su parte). En Operaciones/Mtto/Svial no deben mostrarse, aunque
    // esas secciones sí sigan siendo visibles dentro del modal de
    // detalle ("Ver archivos"), que usa SECCIONES_VISIBLES aparte.
    const MOSTRAR_COLUMNAS_ESTADO = CFG.propia === "laboral";


    //======================================================
    // CONFIGURAR MÓDULO (aplica las restricciones)
    //======================================================

    function configurarModulo() {

        document.getElementById("lblCampoPrincipal").textContent =
            CFG.campoPrincipalLabel;

        const esLaboral = CFG.propia === "laboral";

        // Activa el nuevo look (tarjetas, toggle NO/SÍ, campos de cierre)
        // solo para RRLL; los demás módulos conservan la apariencia de
        // siempre porque las reglas CSS nuevas están scoped a esta clase.
        document.getElementById("formModal").classList.toggle("form-laboral", esLaboral);

        document.getElementById("cardCierre").style.display =
            CFG.mostrarRevision ? "block" : "none";

        document.getElementById("lblRevision").textContent = esLaboral
            ? "¿SE GENERA CIERRE DEL CASO?"
            : "¿LA INFORMACIÓN CARGADA ES CORRECTA?";

        document.getElementById("bloqueObservaciones").style.display =
            CFG.mostrarObservaciones ? "block" : "none";

        document.getElementById("bloqueCamposLaboral").style.display =
            esLaboral ? "block" : "none";

        document.getElementById("bloqueLaboralCierre").style.display =
            esLaboral ? "block" : "none";

        // En RRLL el caso arranca como "no cerrado"; en los demás módulos
        // se conserva el default original (SI = información correcta).
        if (esLaboral) {
            document.querySelector("input[name='Revinf'][value='NO']").checked = true;
            document.getElementById("motivo_cierre").disabled = true;
            document.getElementById("valor_conciliado_display").disabled = true;
        }

        // Mantenimiento: "Costo del daño" es un valor monetario, así que
        // se usa el input con formato de miles en vez del textarea libre
        // que usan los demás módulos (concepto/observaciones de texto).
        const esMtto = CFG.propia === "mtto";
        const campoPrincipalTextarea = document.getElementById("campo_principal");
        const campoPrincipalCosto = document.getElementById("campo_principal_costo_display");

        campoPrincipalTextarea.style.display = esMtto ? "none" : "";
        campoPrincipalCosto.style.display = esMtto ? "" : "none";
        campoPrincipalTextarea.required = !esMtto;
        campoPrincipalCosto.required = esMtto;

        // Mantenimiento: pregunta "¿Existe algún daño más asociado
        // al evento?" (toggle NO/SÍ), justo debajo del costo del daño.
        document.getElementById("bloqueDanoAdicional").style.display =
            esMtto ? "block" : "none";

        // Mostrar/ocultar secciones del modal de detalle según permisos
        document.querySelectorAll("[data-seccion]").forEach(el => {
            const seccion = el.dataset.seccion;
            const visible = SECCIONES_VISIBLES.has(seccion);
            el.style.display = visible ? "" : "none";
        });

    }

    configurarModulo();


    //======================================================
    // FORMATO DE MILES PARA "COSTO DEL DAÑO" (solo Mantenimiento)
    // Se ve "1.500.000" en el input visible mientras se escribe, y el
    // número limpio "1500000" queda en el textarea oculto #campo_principal,
    // que es el que realmente lee construirFormData() al guardar.
    //======================================================

    if (CFG.propia === "mtto") {
        const campoPrincipalCosto = document.getElementById("campo_principal_costo_display");
        const campoPrincipalTextarea = document.getElementById("campo_principal");

        campoPrincipalCosto.addEventListener("input", () => {
            const soloDigitos = campoPrincipalCosto.value.replace(/\D/g, "");

            campoPrincipalCosto.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";

            campoPrincipalTextarea.value = soloDigitos;
        });
    }


    //======================================================
    // UTILIDADES
    //======================================================

    function formatoCOP(valor) {
        if (!valor) return "-";
        return new Intl.NumberFormat("es-CO", {
            style: "currency",
            currency: "COP",
            minimumFractionDigits: 0
        }).format(valor);
    }

    // Convierte el valor crudo guardado en "Pendiente_proceso"
    // (ej: "MANTENIMIENTO, OPERACIONES") en el texto que se muestra
    // en el histórico de eventos del detalle de Relaciones Laborales.
    const TEXTO_ESTADO_CASO = {
        "MANTENIMIENTO": "pendiente por mantenimiento",
        "OPERACIONES": "pendiente por operaciones",
        "SEGURIDAD VIAL": "pendiente por seguridad vial",
        "COMPLETO": "completo"
    };

    function formatearEstadoCaso(valorCrudo) {
        if (!valorCrudo) return "-";

        const partes = String(valorCrudo)
            .split(",")
            .map(p => p.trim().toUpperCase())
            .filter(Boolean);

        if (partes.includes("COMPLETO")) return "completo";

        return partes.map(p => TEXTO_ESTADO_CASO[p] || p).join(", ");
    }

    function construirTabla(datos, campos) {
        return campos.map(campo => {
            let valor = datos?.[campo.key];
            if (campo.formato === "moneda") {
                valor = formatoCOP(valor);
            }
            if (valor === undefined || valor === null || valor === "") {
                valor = "-";
            }
            return `<tr><td>${campo.label}</td><td>${valor}</td></tr>`;
        }).join("");
    }

    function iconoEstado(hecho) {
        return hecho
            ? `<span class="icono-estado icono-ok">✓</span>`
            : `<span class="icono-estado icono-pendiente">✗</span>`;
    }

    // Interpreta las fechas tal como las manda el backend:
    // 'fecha' (evento) llega como "YYYY-MM-DD" y 'fecha_r' (registro)
    // como "DD/MM/YYYY HH:MM:SS". Se deja un fallback por si acaso.
    function parseFechaBackend(valor) {
        if (!valor) return null;

        const str = String(valor).trim();

        let m = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (m) {
            return new Date(+m[1], +m[2] - 1, +m[3]);
        }

        m = str.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
        if (m) {
            return new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0));
        }

        const fallback = new Date(str);
        return isNaN(fallback.getTime()) ? null : fallback;
    }

    function formatearFechaRegistro(fecha) {
        const d = parseFechaBackend(fecha);
        if (!d) return "-";

        const dd = String(d.getDate()).padStart(2, "0");
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const yyyy = d.getFullYear();

        return `${dd}/${mm}/${yyyy}`;
    }
    window.formatearFechaRegistro = formatearFechaRegistro;

    //======================================================
    // FESTIVOS COLOMBIA 🇨🇴 (para el cálculo de duración hábil)
    //======================================================

    const festivosPorAnio = {};

    function calcularPascua(year) {
        const a = year % 19;
        const b = Math.floor(year / 100);
        const c = year % 100;
        const d = Math.floor(b / 4);
        const e = b % 4;
        const f = Math.floor((b + 8) / 25);
        const g = Math.floor((b - f + 1) / 3);
        const h = (19 * a + b - d - g + 15) % 30;
        const i = Math.floor(c / 4);
        const k = c % 4;
        const l = (32 + 2 * e + 2 * i - h - k) % 7;
        const m = Math.floor((a + 11 * h + 22 * l) / 451);
        const month = Math.floor((h + l - 7 * m + 114) / 31);
        const day = ((h + l - 7 * m + 114) % 31) + 1;
        return new Date(year, month - 1, day);
    }

    function moverALunes(fecha) {
        const d = fecha.getDay();
        if (d === 1) return fecha;
        const f = new Date(fecha);
        f.setDate(fecha.getDate() + ((8 - d) % 7));
        return f;
    }

    function generarFestivosColombia(year) {
        const festivos = [];

        festivos.push(new Date(year, 0, 1));    // Año Nuevo
        festivos.push(new Date(year, 4, 1));    // Día del Trabajo
        festivos.push(new Date(year, 6, 20));   // Independencia
        festivos.push(new Date(year, 7, 7));    // Boyacá
        festivos.push(new Date(year, 11, 8));   // Inmaculada
        festivos.push(new Date(year, 11, 25));  // Navidad

        festivos.push(moverALunes(new Date(year, 0, 6)));   // Reyes
        festivos.push(moverALunes(new Date(year, 2, 19)));  // San José
        festivos.push(moverALunes(new Date(year, 5, 29)));  // San Pedro y San Pablo
        festivos.push(moverALunes(new Date(year, 7, 15)));  // Asunción
        festivos.push(moverALunes(new Date(year, 9, 12)));  // Raza
        festivos.push(moverALunes(new Date(year, 10, 1)));  // Todos los Santos
        festivos.push(moverALunes(new Date(year, 10, 11))); // Cartagena

        const pascua = calcularPascua(year);
        festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 3)); // Jueves Santo
        festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 2)); // Viernes Santo
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 43))); // Ascensión
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 64))); // Corpus
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 71))); // Sagrado

        return festivos.map(f => f.toISOString().split("T")[0]);
    }

    function obtenerFestivosColombia(year) {
        if (!festivosPorAnio[year]) {
            festivosPorAnio[year] = generarFestivosColombia(year);
        }
        return festivosPorAnio[year];
    }

    function esDiaHabil(fecha) {
        const dia = fecha.getDay();
        if (dia === 0 || dia === 6) return false; // domingo o sábado

        const iso = fecha.toISOString().split("T")[0];
        const festivos = obtenerFestivosColombia(fecha.getFullYear());

        return !festivos.includes(iso);
    }

    // Diferencia entre `inicio` y `fin` contando solo tiempo dentro de
    // días hábiles (se descarta por completo el tiempo transcurrido en
    // fines de semana y festivos colombianos).
    function calcularDuracionHabil(inicio, fin) {
        let actual = new Date(inicio);
        let totalMs = 0;

        while (actual < fin) {
            if (esDiaHabil(actual)) {
                let finDia = new Date(actual);
                finDia.setHours(23, 59, 59, 999);
                if (finDia > fin) finDia = fin;
                totalMs += (finDia - actual);
            }
            actual.setDate(actual.getDate() + 1);
            actual.setHours(0, 0, 0, 0);
        }

        const dias = Math.floor(totalMs / 86400000);
        const horas = Math.floor((totalMs % 86400000) / 3600000);
        const minutos = Math.floor((totalMs % 3600000) / 60000);

        return { dias, horas, minutos };
    }

    function calcularDiferencia(fechaValor) {
        const inicio = parseFechaBackend(fechaValor);
        if (!inicio) return null;

        const ahora = new Date();
        const { dias, horas, minutos } = calcularDuracionHabil(inicio, ahora > inicio ? ahora : inicio);

        let texto;
        if (dias > 0) texto = `${dias} d ${horas} h`;
        else if (horas > 0) texto = `${horas} h ${minutos} min`;
        else texto = `${minutos} min`;

        return { dias, horas, minutos, texto };
    }

    // Devuelve la duración desde que se registró el evento y desde que
    // ocurrió el evento en sí. `t` (usado para pintar la fila en rojo si
    // llevan 2+ días sin resolver) se basa en la fecha del EVENTO, que es
    // la que refleja qué tan urgente/atrasado está el caso.
    function calcularDuracionesRegistro(registro) {
        const tRegistro = calcularDiferencia(registro.fecha_r);
        const tEvento = calcularDiferencia(registro.fecha);

        return {
            duracion: tRegistro ? tRegistro.texto : "-",
            duracionEvento: tEvento ? tEvento.texto : "-",
            t: tEvento
        };
    }
    window.calcularDuracionesRegistro = calcularDuracionesRegistro;


    //======================================================
    // CARGAR REGISTROS
    //======================================================

    try {
        const script = document.getElementById("registros-json");
        registros = JSON.parse(script.textContent);
    } catch (error) {
        console.error(error);
    }


    //======================================================
    // FILTROS
    //======================================================

    // Filtra el array `registros` según los inputs del encabezado
    // (data-col) y el select #filtroUF, y vuelve a pintar la tabla.
    function filtrarTabla() {

        const filtros = {};
        document.querySelectorAll("thead th input").forEach(input => {
            if (input.disabled || input.dataset.col === undefined) return;
            filtros[input.dataset.col] = input.value.trim().toLowerCase();
        });

        const filtroUF = document.getElementById("filtroUF")?.value || "todos";

        const filtrados = registros.filter(registro => {

            if (filtroUF !== "todos" && String(registro.UF) !== filtroUF) {
                return false;
            }

            if (filtros["0"] &&
                !String(registro.Id ?? "").toLowerCase().includes(filtros["0"])) {
                return false;
            }

            if (filtros["1"]) {
                const fechaISO = registro.fecha
                    ? new Date(registro.fecha).toISOString().slice(0, 10)
                    : "";
                if (fechaISO !== filtros["1"]) return false;
            }

            if (filtros["2"] &&
                !String(registro.Movil ?? "").toLowerCase().includes(filtros["2"])) {
                return false;
            }

            if (filtros["3"] &&
                !String(registro.Codigo ?? "").toLowerCase().includes(filtros["3"])) {
                return false;
            }

            if (filtros["4"] &&
                !String(registro.Nombre ?? "").toLowerCase().includes(filtros["4"])) {
                return false;
            }

            return true;
        });

        renderTabla(filtrados);
    }

    // Evita que se dupliquen los listeners: renderTabla() llama a
    // activarFiltros() en cada render, así que solo se enganchan una vez.
    let filtrosActivados = false;

    window.activarFiltros = function () {
        if (filtrosActivados) return;
        filtrosActivados = true;

        document.querySelectorAll("thead th input").forEach(input => {
            if (input.disabled) return;
            input.addEventListener("input", filtrarTabla);
            input.addEventListener("change", filtrarTabla);
        });

        document
            .getElementById("filtroUF")
            ?.addEventListener("change", filtrarTabla);
    };


    //======================================================
    // OCULTAR COLUMNAS DE ESTADO SEGÚN PERMISOS
    //======================================================

    function aplicarVisibilidadColumnas() {
        document.querySelectorAll("th.col-estado").forEach(th => {
            th.style.display = MOSTRAR_COLUMNAS_ESTADO ? "" : "none";
        });
    }

    aplicarVisibilidadColumnas();


    //======================================================
    // TABLA PRINCIPAL
    //======================================================

    function renderTabla(lista, opciones = {}) {

        listaTablaActual = lista;

        if (!opciones.mantenerPagina) {
            paginaActual = 1;
        }

        const totalPaginas = Math.max(1, Math.ceil(listaTablaActual.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;

        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const paginaDatos = listaTablaActual.slice(inicio, inicio + FILAS_POR_PAGINA);

        const tbody = document.getElementById("tablaRegistros");
        tbody.innerHTML = "";

        activarFiltros();
        aplicarVisibilidadColumnas();

        paginaDatos.forEach(registro => {

            const fechaFormateada =
                window.formatearFechaRegistro(registro.fecha);

            const { duracion, duracionEvento, t } =
                window.calcularDuracionesRegistro(registro);

            const tr = document.createElement("tr");

            tr.classList.add(t && t.dias >= 2 ? "row-danger" : "row-ok");
            tr.dataset.uf = registro.UF;

            const celdaOper = MOSTRAR_COLUMNAS_ESTADO
                ? `<td class="col-estado">${iconoEstado(registro.tiene_oper)}</td>`
                : "";
            const celdaMtto = MOSTRAR_COLUMNAS_ESTADO
                ? `<td class="col-estado">${iconoEstado(registro.tiene_mtto)}</td>`
                : "";
            const celdaSvial = MOSTRAR_COLUMNAS_ESTADO
                ? `<td class="col-estado">${iconoEstado(registro.tiene_svial)}</td>`
                : "";

            const celdaAdjuntos = registro.archivos_count > 0
                ? `<button class="btn" onclick="mostrarAdjuntos('${registro.Id}')">
                        Ver archivos (${registro.archivos_count})
                   </button>`
                : `<span style="color:#777">Sin archivos</span>`;

            const celdaAcciones = construirCeldaAcciones(registro);

            tr.innerHTML = `
                <td>${registro.Id}</td>
                <td>${fechaFormateada}</td>
                <td>${registro.Movil}</td>
                <td>${registro.Codigo}</td>
                <td>${registro.Nombre}</td>
                <td>${duracion}</td>
                <td>${duracionEvento}</td>
                ${celdaOper}
                ${celdaMtto}
                ${celdaSvial}
                <td>${celdaAdjuntos}</td>
                <td>${celdaAcciones}</td>
            `;

            tbody.appendChild(tr);
        });

        renderControlesPaginacion();
    }

    //--------------------------------------------------
    // Controles de paginación (estilo Gmail: "1–30 de 245"
    // + flechas anterior/siguiente).
    //--------------------------------------------------

    function renderControlesPaginacion() {

        const total = listaTablaActual.length;
        const totalPaginas = Math.max(1, Math.ceil(total / FILAS_POR_PAGINA));

        const inicio = total === 0 ? 0 : (paginaActual - 1) * FILAS_POR_PAGINA + 1;
        const fin = Math.min(paginaActual * FILAS_POR_PAGINA, total);

        const info = document.getElementById("paginacionInfo");
        if (info) info.textContent = `${inicio}–${fin} de ${total}`;

        const btnAnterior = document.getElementById("btnPaginaAnterior");
        const btnSiguiente = document.getElementById("btnPaginaSiguiente");

        if (btnAnterior) btnAnterior.disabled = paginaActual <= 1;
        if (btnSiguiente) btnSiguiente.disabled = paginaActual >= totalPaginas;
    }

    // Se enganchan una sola vez: los botones ya existen en el HTML y
    // solo cambian de estado (disabled), no se regeneran en cada render.
    document.getElementById("btnPaginaAnterior")?.addEventListener("click", () => {
        if (paginaActual > 1) {
            paginaActual--;
            renderTabla(listaTablaActual, { mantenerPagina: true });
        }
    });

    document.getElementById("btnPaginaSiguiente")?.addEventListener("click", () => {
        const totalPaginas = Math.max(1, Math.ceil(listaTablaActual.length / FILAS_POR_PAGINA));
        if (paginaActual < totalPaginas) {
            paginaActual++;
            renderTabla(listaTablaActual, { mantenerPagina: true });
        }
    });

    //--------------------------------------------------
    // Botón de acción según si ya se diligenció la
    // sección PROPIA de este módulo para ese registro.
    // Relaciones laborales permite reabrir mientras no
    // esté cerrado; los demás son de un único registro.
    //--------------------------------------------------

    function construirCeldaAcciones(registro) {

        const propia = CFG.propia;

        if (propia === "laboral") {
            if (registro.laboral_cerrado) {
                return `<span class="badge badge-ok">Caso cerrado</span>`;
            }
            return `<button class="btn btn-success" onclick="abrirModal('${registro.Id}')">
                        Añadir info
                    </button>`;
        }

        const yaTiene = registro["tiene_" + propia];

        if (yaTiene) {
            return `<span class="badge badge-ok">Ya registrado</span>`;
        }

        return `<button class="btn btn-success" onclick="abrirModal('${registro.Id}')">
                    Añadir info
                </button>`;
    }

    renderTabla(registros);

    window.renderTabla = renderTabla;


    //======================================================
    // MAPA DEL MODAL DE DETALLE (Leaflet + geocodificación OSM)
    //======================================================

    let mapaModal = null;
    let markerModal = null;
    const cacheCoordsDireccion = {};

    // Geocodifica una dirección de texto a {lat, lng} usando el servicio
    // gratuito de Nominatim (OpenStreetMap). Cachea por dirección para no
    // repetir peticiones; devuelve null si no hay dirección o no se
    // encuentra resultado. Nota: Nominatim pide máx. 1 petición/seg. y no
    // es apto para volúmenes altos; para producción intensiva conviene
    // un proveedor con SLA (Google Geocoding, Mapbox, etc.).
    async function obtenerCoordsDesdeDireccion(direccion) {
        if (!direccion) return null;

        if (direccion in cacheCoordsDireccion) {
            return cacheCoordsDireccion[direccion];
        }

        // El campo "Direccion" a veces ya viene con coordenadas GPS en
        // formato "lat,lng" (ej: "4.6562,-74.1200") en vez de una
        // dirección de texto. En ese caso no hay nada que geocodificar:
        // se usan directamente y se evita la llamada a Nominatim (que
        // nunca encuentra resultados para un texto que en realidad son
        // números).
        const coordMatch = String(direccion).trim().match(
            /^(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)$/
        );

        if (coordMatch) {
            const coords = { lat: parseFloat(coordMatch[1]), lng: parseFloat(coordMatch[2]) };
            cacheCoordsDireccion[direccion] = coords;
            return coords;
        }

        try {
            const query = encodeURIComponent(`${direccion}, Colombia`);
            const resp = await fetch(
                `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${query}`
            );
            const resultados = await resp.json();

            const coords = resultados.length
                ? { lat: parseFloat(resultados[0].lat), lng: parseFloat(resultados[0].lon) }
                : null;

            cacheCoordsDireccion[direccion] = coords;
            return coords;

        } catch (error) {
            console.error("No se pudo geocodificar la dirección:", error);
            return null;
        }
    }

    function initMapaModal() {
        if (mapaModal) return;

        mapaModal = L.map("map").setView([4.7110, -74.0721], 11); // Bogotá por defecto

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap contributors",
            maxZoom: 19
        }).addTo(mapaModal);
    }

    function actualizarMapaModal(coords) {
        if (!mapaModal) return;

        mapaModal.setView([coords.lat, coords.lng], 16);

        if (markerModal) {
            mapaModal.removeLayer(markerModal);
        }
        markerModal = L.marker([coords.lat, coords.lng]).addTo(mapaModal);

        // El modal estaba oculto cuando Leaflet calculó el tamaño del
        // contenedor; sin esto el mapa puede verse gris o cortado.
        setTimeout(() => mapaModal.invalidateSize(), 100);
    }


    //======================================================
    // RENDER TABLAS DEL MODAL
    //======================================================

    async function renderDetalle(registro, data) {

        const registroDetalle = data.registro ?? {};
        const oper = data.oper ?? {};
        const mtto = data.mtto ?? {};
        const svial = data.svial ?? {};
        const laboral = data.laboral ?? { eventos: [], estado: {} };

        //--------------------------------------------------
        // TABLA GENERAL
        //--------------------------------------------------

        const datosGeneral = {
            fecha: registro.fecha,
            fecha_r: registro.fecha_r,
            ...registroDetalle
        };

        document.getElementById("infoEventoBody").innerHTML =
            construirTabla(datosGeneral, DETAIL_CONFIG.general);

        //--------------------------------------------------
        // OPERACIONAL
        //--------------------------------------------------

        if (SECCIONES_VISIBLES.has("oper")) {
            document.getElementById("infoEventooper").innerHTML =
                construirTabla(oper, DETAIL_CONFIG.oper);
        }

        //--------------------------------------------------
        // MANTENIMIENTO
        //--------------------------------------------------

        if (SECCIONES_VISIBLES.has("mtto")) {
            document.getElementById("infoEventomtto").innerHTML =
                construirTabla(mtto, DETAIL_CONFIG.mantenimiento || DETAIL_CONFIG.mtto);
        }

        //--------------------------------------------------
        // SEGURIDAD VIAL
        //--------------------------------------------------

        if (SECCIONES_VISIBLES.has("svial")) {
            document.getElementById("infoEventosvial").innerHTML =
                construirTabla(svial, DETAIL_CONFIG.svial);
        }

        //--------------------------------------------------
        // RELACIONES LABORALES (estado + histórico de eventos)
        //--------------------------------------------------

        if (SECCIONES_VISIBLES.has("laboral")) {

            let filasEventos = "";

            if (laboral.eventos && laboral.eventos.length) {
                filasEventos = laboral.eventos.map(ev => `
                    <tr>
                        <td>Fecha presentación</td>
                        <td>${ev.Fecha_presentacion ?? "-"}</td>
                    </tr>
                    <tr>
                        <td>Estado del caso</td>
                        <td>${formatearEstadoCaso(ev.Pendiente_proceso)}</td>
                    </tr>
                    <tr>
                        <td>Observaciones</td>
                        <td>${ev.Observaciones_rrll ?? "-"}</td>
                    </tr>
                `).join("<tr><td colspan='2'><hr></td></tr>");
            } else {
                filasEventos = `<tr><td colspan="2">Sin eventos registrados</td></tr>`;
            }

            document.getElementById("infoEventolaboral").innerHTML =
                filasEventos + construirTabla(laboral.estado, DETAIL_CONFIG.laboral_estado);
        }

        //--------------------------------------------------
        // MAPA
        //--------------------------------------------------

        const coords = await obtenerCoordsDesdeDireccion(registroDetalle.Direccion);

        initMapaModal();

        if (coords) {
            actualizarMapaModal(coords);
        } else {
            // Sin coordenadas válidas: se deja el mapa con la vista por
            // defecto, pero igual se fuerza el recálculo de tamaño para
            // que no se vea gris/cortado (el modal estaba oculto cuando
            // Leaflet lo inicializó).
            setTimeout(() => mapaModal.invalidateSize(), 100);
        }
    }


    //======================================================
    // RENDER GALERÍA
    //======================================================

    function renderGaleria(archivos) {

        const galeria = document.getElementById("galeriaAdjuntos");
        galeria.innerHTML = "";

        if (!archivos.length) {
            galeria.innerHTML = `<p style="text-align:center;color:#777">Sin archivos adjuntos</p>`;
            return;
        }

        archivos.forEach(file => {

            const div = document.createElement("div");
            div.className = "adjunto-item";

            const ext = file.FileName.split(".").pop().toLowerCase();

            const url = `/${CFG.modulo}/ver_archivo?path=${encodeURIComponent(file.FilePath)}`;

            if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext)) {
                const img = document.createElement("img");
                img.src = url;
                img.onclick = () => abrirLightbox(url);
                div.appendChild(img);
            } else if (["mp4", "avi", "mov", "webm"].includes(ext)) {
                const video = document.createElement("video");
                video.src = url;
                video.controls = true;
                div.appendChild(video);
            } else {
                const a = document.createElement("a");
                a.href = url;
                a.target = "_blank";
                a.textContent = file.FileName;
                div.appendChild(a);
            }

            galeria.appendChild(div);
        });
    }


    //======================================================
    // MODAL ADJUNTOS
    //======================================================

    window.mostrarAdjuntos = function (id) {

        const registro = registros.find(r => r.Id == id);
        if (!registro) return;

        movilSeleccionado = id;

        document.getElementById("modalAdjuntos").style.display = "block";
        document.getElementById("modal_registro1").textContent = id;

        fetch(`/${CFG.modulo}/detalle/${id}`)
            .then(r => r.json())
            .then(data => {
                renderDetalle(registro, data);

                // Junta los 4 conjuntos de archivos que puede ver el módulo
                const todosArchivos = [
                    ...(data.archivos ?? []),
                    ...(SECCIONES_VISIBLES.has("mtto") ? (data.archivos_mtto ?? []) : []),
                    ...(SECCIONES_VISIBLES.has("svial") ? (data.archivos_svial ?? []) : []),
                    ...(SECCIONES_VISIBLES.has("laboral") ? (data.archivos_laboral ?? []) : [])
                ];

                renderGaleria(todosArchivos);
            })
            .catch(error => {
                console.error(error);
                alert("Error cargando el evento.");
            });
    };

    window.cerrarModalAdjuntos = function () {
        document.getElementById("modalAdjuntos").style.display = "none";
    };


    //======================================================
    // MODAL FORMULARIO ("Añadir info" de la sección propia)
    //======================================================

    window.abrirModal = function (id) {

        movilSeleccionado = id;
        document.getElementById("modal_registro").textContent = id;
        document.getElementById("miModal").style.display = "block";

        inputAdjuntos = document.getElementById("evidencia");
        listaAdjuntos = document.getElementById("lista_adjuntos");

        inputAdjuntos.value = "";
        adjuntosSeleccionados = [];
        actualizarListaAdjuntos();

        inputAdjuntos.onchange = () => {
            const nuevos = [...inputAdjuntos.files];
            nuevos.forEach(a => adjuntosSeleccionados.push(a));
            inputAdjuntos.value = "";
            actualizarListaAdjuntos();
        };
    };

    window.cerrarModal = function () {
        document.getElementById("miModal").style.display = "none";
        movilSeleccionado = "";
        adjuntosSeleccionados = [];
        actualizarListaAdjuntos();
        limpiarFormulario();
    };


    //======================================================
    // LIMPIAR FORMULARIO
    //======================================================

    function limpiarFormulario() {
        document.getElementById("campo_principal").value = "";
        document.getElementById("campo_principal_costo_display").value = "";
        document.getElementById("observaciones").value = "";
        document.getElementById("observaciones").disabled = true;

        document.querySelectorAll("input[name='DanoAdicional']").forEach(r => {
            r.checked = r.value === "NO";
        });

        const danoAdicionalDetalle = document.getElementById("dano_adicional_detalle");
        const bloqueDanoAdicionalDetalle = document.getElementById("bloqueDanoAdicionalDetalle");
        if (danoAdicionalDetalle) {
            danoAdicionalDetalle.value = "";
            danoAdicionalDetalle.required = false;
        }
        if (bloqueDanoAdicionalDetalle) bloqueDanoAdicionalDetalle.style.display = "none";

        const fp = document.getElementById("fecha_presentacion");
        if (fp) fp.value = "";

        if (estadoCasoOpciones) {
            estadoCasoOpciones.querySelectorAll("input[type='checkbox']").forEach(cb => {
                cb.checked = false;
            });
            estadoCasoOpciones.classList.remove("abierto");
            sincronizarEstadoCaso();
        }

        const mc = document.getElementById("motivo_cierre");
        const vc = document.getElementById("valor_conciliado");
        const vcDisplay = document.getElementById("valor_conciliado_display");
        if (mc) { mc.value = ""; mc.disabled = true; }
        if (vc) { vc.value = ""; }
        if (vcDisplay) { vcDisplay.value = ""; vcDisplay.disabled = true; }

        // RRLL arranca en "NO" (caso no cerrado); los demás módulos
        // conservan su default original ("SI" = información correcta).
        const defaultRevinf = CFG.propia === "laboral" ? "NO" : "SI";
        document.querySelectorAll("input[name='Revinf']").forEach(r => {
            r.checked = r.value === defaultRevinf;
        });
    }


    //======================================================
    // RADIO BUTTONS
    //======================================================

    const textareaObs = document.getElementById("observaciones");
    const motivoCierre = document.getElementById("motivo_cierre");
    const valorConciliado = document.getElementById("valor_conciliado"); // input oculto: valor numérico limpio
    const valorConciliadoDisplay = document.getElementById("valor_conciliado_display"); // input visible: con formato de miles


    //======================================================
    // FORMATO DE MILES PARA "VALOR CONCILIADO"
    // (se ve "1.500.000" en el input mientras se escribe, y se
    // envía el número limpio "1500000" al backend)
    //======================================================

    if (valorConciliadoDisplay && valorConciliado) {

        valorConciliadoDisplay.addEventListener("input", () => {
            const soloDigitos = valorConciliadoDisplay.value.replace(/\D/g, "");

            valorConciliadoDisplay.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";

            valorConciliado.value = soloDigitos;
        });
    }


    //======================================================
    // MULTISELECT DE CASILLAS: "CASO PENDIENTE POR EL PROCESO"
    // (Mantenimiento / S.Vial / Operaciones / Completo)
    //======================================================

    const estadoCasoToggle = document.getElementById("estado_caso_toggle");
    const estadoCasoOpciones = document.getElementById("estado_caso_opciones");
    const estadoCasoLabel = document.getElementById("estado_caso_label");
    const estadoCasoHidden = document.getElementById("estado_caso");

    function sincronizarEstadoCaso() {
        if (!estadoCasoOpciones) return;

        const marcados = Array.from(
            estadoCasoOpciones.querySelectorAll("input[type='checkbox']:checked")
        ).map(cb => cb.value);

        estadoCasoHidden.value = marcados.join(", ");
        estadoCasoLabel.textContent = marcados.length
            ? marcados.join(", ")
            : "Seleccione estados";
    }

    if (estadoCasoToggle && estadoCasoOpciones) {

        estadoCasoToggle.addEventListener("click", e => {
            e.stopPropagation();
            estadoCasoOpciones.classList.toggle("abierto");
        });

        estadoCasoOpciones.addEventListener("change", sincronizarEstadoCaso);

        // Cierra el desplegable al hacer click fuera de él
        document.addEventListener("click", e => {
            if (!document.getElementById("estado_caso_multiselect").contains(e.target)) {
                estadoCasoOpciones.classList.remove("abierto");
            }
        });
    }

    document.querySelectorAll("input[name='Revinf']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            if (CFG.propia === "laboral") {
                // Motivo del cierre y valor conciliado solo aplican
                // cuando SÍ se genera el cierre del caso.
                const seCierra = radio.value === "SI";

                motivoCierre.disabled = !seCierra;
                motivoCierre.required = seCierra;
                valorConciliadoDisplay.disabled = !seCierra;
                valorConciliadoDisplay.required = seCierra;

                if (!seCierra) {
                    motivoCierre.value = "";
                    valorConciliadoDisplay.value = "";
                    valorConciliado.value = "";
                }
                return;
            }

            if (radio.value === "NO") {
                textareaObs.disabled = false;
                textareaObs.required = true;
            } else if (radio.value === "SI") {
                textareaObs.disabled = true;
                textareaObs.required = false;
                textareaObs.value = "";
            }
        });
    });

    //======================================================
    // TOGGLE "¿EXISTE ALGÚN DAÑO MÁS ASOCIADO AL EVENTO?"
    // (solo Mantenimiento): muestra el textarea de descripción
    // cuando se elige SÍ.
    //======================================================

    const bloqueDanoAdicionalDetalle = document.getElementById("bloqueDanoAdicionalDetalle");
    const danoAdicionalDetalle = document.getElementById("dano_adicional_detalle");

    document.querySelectorAll("input[name='DanoAdicional']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            const hayDanoAdicional = radio.value === "SI";

            bloqueDanoAdicionalDetalle.style.display = hayDanoAdicional ? "block" : "none";
            danoAdicionalDetalle.required = hayDanoAdicional;

            if (!hayDanoAdicional) {
                danoAdicionalDetalle.value = "";
            }
        });
    });


    //======================================================
    // CONSTRUIR FORMDATA
    //======================================================

    function construirFormData() {

        const formData = new FormData();

        formData.append("Id_damage_to_fleet", movilSeleccionado);
        formData.append("Usuario_registro_oper", document.body.dataset.usuario);

        const formulario = FORM_CONFIG[CFG.propia];

        formulario.campos.forEach(campo => {
            const control = document.getElementById(campo.id);
            if (control) {
                formData.append(campo.nombre, control.value);
            }
        });

        if (CFG.mostrarRevision) {
            const revision = document.querySelector("input[name='Revinf']:checked").value;
            formData.append("Revinf", revision);

            // Para Relaciones Laborales, "Cerrado_input" viaja al backend
            // como el TIPO/MOTIVO del cierre (así lo lee
            // agregar_relaciones_laborales), no como un simple "SI"/"NO".
            if (CFG.propia === "laboral") {
                formData.append(
                    "Cerrado_input",
                    revision === "SI" ? document.getElementById("motivo_cierre").value : ""
                );
            }
        }

        // Mantenimiento: "¿Existe algún daño más asociado al evento?"
        if (CFG.propia === "mtto") {
            const danoAdicional = document.querySelector("input[name='DanoAdicional']:checked");
            const valorDanoAdicional = danoAdicional ? danoAdicional.value : "NO";
            formData.append("dano_adicional", valorDanoAdicional);
            formData.append(
                "dano_adicional_detalle",
                valorDanoAdicional === "SI" ? document.getElementById("dano_adicional_detalle").value : ""
            );
        }

        adjuntosSeleccionados.forEach(file => {
            formData.append("archivos", file);
        });

        return formData;
    }


    //======================================================
    // VALIDAR FORMULARIO
    //======================================================

    function validarFormulario() {

        if (!movilSeleccionado) {
            alert("Seleccione un registro.");
            return false;
        }

        if (CFG.mostrarRevision) {
            const revision = document.querySelector("input[name='Revinf']:checked").value;

            if (CFG.mostrarObservaciones && revision === "NO" && !textareaObs.value.trim()) {
                alert("Debe ingresar observaciones.");
                return false;
            }

            if (CFG.propia === "laboral" && revision === "SI") {
                if (!motivoCierre.value) {
                    alert("Seleccione el motivo del cierre.");
                    return false;
                }
                if (!valorConciliado.value) {
                    alert("Ingrese el valor conciliado.");
                    return false;
                }
            }
        }

        if (CFG.propia === "mtto") {
            const danoAdicional = document.querySelector("input[name='DanoAdicional']:checked");
            if (danoAdicional && danoAdicional.value === "SI" &&
                !document.getElementById("dano_adicional_detalle").value.trim()) {
                alert("Describa el daño adicional.");
                return false;
            }
        }

        return true;
    }


    //======================================================
    // ACTUALIZAR ESTADO LOCAL TRAS GUARDAR (sin quitar la fila,
    // solo refleja que la sección propia quedó registrada)
    //======================================================

    function actualizarEstadoLocal(id) {

        const registro = registros.find(r => r.Id == id);
        if (!registro) return;

        let debeOcultarse = false;

        if (CFG.propia === "laboral") {
            const revision = document.querySelector("input[name='Revinf']:checked")?.value;
            if (revision === "SI") {
                registro.laboral_cerrado = true;
                debeOcultarse = true;
            }
        } else {
            registro["tiene_" + CFG.propia] = true;
            debeOcultarse = true;
        }

        // Ya diligenció su parte (o, en RRLL, ya cerró el caso): deja de
        // aparecer en esta tabla, igual que hará el backend en el
        // próximo recargue — así no hay que esperar a refrescar la página.
        if (debeOcultarse) {
            registros = registros.filter(r => r.Id != id);
        }

        renderTabla(registros);
    }


    //======================================================
    // SUBMIT GENERAL
    //======================================================

    async function enviarFormulario() {

        if (!validarFormulario()) return;

        const formulario = FORM_CONFIG[CFG.propia];
        const endpoint = `/${CFG.modulo}/${formulario.endpoint}`;
        const idGuardado = movilSeleccionado;

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                body: construirFormData()
            });

            const result = await response.json();

            if (result.status === "success") {
                alert(result.message);
                actualizarEstadoLocal(idGuardado);
                cerrarModal();
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error(error);
            alert("Error enviando formulario.");
        }
    }


    //======================================================
    // EVENTO SUBMIT
    //======================================================

    document.getElementById("formModal").addEventListener("submit", e => {
        e.preventDefault();
        enviarFormulario();
    });


    //======================================================
    // UTILIDADES ADJUNTOS
    //======================================================

    function actualizarListaAdjuntos() {

        if (!listaAdjuntos) return;
        listaAdjuntos.innerHTML = "";

        adjuntosSeleccionados.forEach((archivo, index) => {

            const div = document.createElement("div");
            div.className = "archivo-item";
            div.innerHTML = `
                <span>${archivo.name}</span>
                <button type="button" class="btn btn-danger btn-sm">✕</button>
            `;

            div.querySelector("button").onclick = () => {
                adjuntosSeleccionados.splice(index, 1);
                actualizarListaAdjuntos();
            };

            listaAdjuntos.appendChild(div);
        });
    }


    //======================================================
    // CERRAR MODALES AL HACER CLICK AFUERA
    //======================================================

    window.onclick = function (event) {
        const modalFormulario = document.getElementById("miModal");
        const modalAdjuntos = document.getElementById("modalAdjuntos");

        if (event.target === modalFormulario) cerrarModal();
        if (event.target === modalAdjuntos) cerrarModalAdjuntos();
    };


    //======================================================
    // ESC CERRAR MODAL
    //======================================================

    document.addEventListener("keydown", e => {
        if (e.key === "Escape") {
            cerrarModal();
            cerrarModalAdjuntos();
        }
    });


    //======================================================
    // LIGHTBOX
    //======================================================

    window.abrirLightbox = function (url) {
        document.getElementById("lightbox").style.display = "block";
        document.getElementById("lightbox-img").src = url;
    };

    window.cerrarLightbox = function () {
        document.getElementById("lightbox").style.display = "none";
    };


    //======================================================
    // INICIALIZACIÓN
    //======================================================

    console.log("===================================");
    console.log("Módulo cargado:", CFG.modulo);
    console.log("Sección propia:", CFG.propia);
    console.log("Secciones visibles:", CFG.seccionesVisibles);
    console.log("===================================");

});