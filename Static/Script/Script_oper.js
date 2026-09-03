//======================================================
// VARIABLES GLOBALES
//======================================================

let inputAdjuntos = null;
let listaAdjuntos = null;
let adjuntosSeleccionados = [];

let registros = [];
let movilSeleccionado = "";

// Paginación de la tabla principal (30 filas por página).
const FILAS_POR_PAGINA = 30;
let paginaActual = 1;
let listaTablaActual = []; // lista que se está paginando


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
        { key: "Observaciones_correctivos", label: "OBSERVACIONES ADICIONALES" },
        { key: "responsabilidad_operador", label: "ACEPTA LA RESPONSABILIDAD EL OPERADOR" },
        { key: "conciliacion", label: "CONCILIACIÓN" },
        { key: "CostoDelDanoOper", label: "COSTO DEL DAÑO", formato: "moneda" },
        { key: "ValorConciliadoOper", label: "VALOR CONCILIADO", formato: "moneda" }
    ],

    // Vista reducida de Operaciones: la usa Mantenimiento en "Ver
    // archivos", donde los controles propios del flujo de Operaciones
    // (responsabilidad, conciliación, costo, valor conciliado) no
    // aplican -- Mantenimiento solo ve casos del camino > $2.000.000.
    oper_basico: [
        { key: "Observaciones_operaciones", label: "OBSERVACIONES OPERACIONALES" },
        { key: "rev_error", label: "INFO. CORRECTA" },
        { key: "Observaciones_correctivos", label: "OBSERVACIONES ADICIONALES" }
    ],

    mtto: [
        { key: "Costo", label: "COSTO", formato: "moneda" },
        { key: "dano_adicional", label: "DAÑO ADICIONAL" },
        { key: "observaciones", label: "OBSERVACIONES" }
    ],

    svial: [
        { key: "Observaciones_svial", label: "OBSERVACIONES" }
    ],

    laboral_estado: [
        { key: "Tipo_cerrado", label: "TIPO DE CIERRE" },
        { key: "Valor_conciliado", label: "VALOR CONCILIADO", formato: "moneda" }
    ]

};


//======================================================
// CONFIGURACIÓN DE FORMULARIOS
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
            { id: "campo_principal", nombre: "Costo" },
            { id: "observaciones", nombre: "observaciones" }
        ]
    },

    svial: {
        endpoint: "agregar_svial",
        campos: [
            { id: "campo_principal", nombre: "Observaciones_svial" },
            { id: "conciliado_a_favor", nombre: "conciliado_a_favor" },
            { id: "valor_conciliado_terceros", nombre: "valor_conciliado_terceros" }
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

    // FECHA R. LABORALES 
    const MOSTRAR_COLUMNA_FECHA_LABORAL = CFG.propia === "laboral";


    //======================================================
    // CONFIGURAR MÓDULO (aplica las restricciones)
    //======================================================

    function configurarModulo() {

        document.getElementById("lblCampoPrincipal").textContent =
            CFG.campoPrincipalLabel;

        const esLaboral = CFG.propia === "laboral";
        const esMtto = CFG.propia === "mtto";
        const esOper = CFG.propia === "oper";
        const esSvial = CFG.propia === "svial";

        // Nuevo flujo de Operaciones (valor del daño / responsabilidad / conciliación)
        document.getElementById("cardFlujoOper").style.display = esOper ? "block" : "none";
        document.getElementById("bloqueConciliadoFavor").style.display = esSvial ? "block" : "none";

        // Activa el nuevo look (tarjetas, toggle NO/SÍ, campos de cierre)
        // solo para RRLL.
        document.getElementById("formModal").classList.toggle("form-laboral", esLaboral);

        document.getElementById("cardCierre").style.display =
            CFG.mostrarRevision ? "block" : "none";

        document.getElementById("lblRevision").textContent = esLaboral
            ? "¿SE GENERA CIERRE DEL CASO?"
            : "¿LA INFORMACIÓN CARGADA ES CORRECTA?";


        const textareaObsInicial = document.getElementById("observaciones");
        document.getElementById("bloqueObservaciones").style.display =
            (CFG.mostrarObservaciones || esMtto) ? "block" : "none";

        if (esMtto) {
            textareaObsInicial.disabled = false;
        }

        document.getElementById("bloqueCamposLaboral").style.display =
            esLaboral ? "block" : "none";

        document.getElementById("bloqueLaboralCierre").style.display =
            esLaboral ? "block" : "none";

        // En RRLL el caso arranca como "no cerrado".
        if (esLaboral) {
            document.querySelector("input[name='Revinf'][value='NO']").checked = true;
            document.getElementById("motivo_cierre").disabled = true;
            document.getElementById("valor_conciliado_display").disabled = true;
        }

        // Mantenimiento: "Costo del daño" es un valor monetario, así que
        // se usa el input con formato de miles
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

        if (esMtto) {
            actualizarObservacionesPorDanoAdicional();
        }

        // Mostrar/ocultar secciones del modal de detalle según permisos
        document.querySelectorAll("[data-seccion]").forEach(el => {
            const seccion = el.dataset.seccion;
            const visible = SECCIONES_VISIBLES.has(seccion);
            el.style.display = visible ? "" : "none";
        });

    }

    configurarModulo();


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


    // Histórico de eventos del detalle de Relaciones Laborales.
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

    function construirAvisosPendienteLaboral(eventos) {
        if (!eventos?.length) return "";

        return eventos.map(ev => `
            <tr>
                <td colspan="2"><strong>Relaciones Laborales — caso ${formatearEstadoCaso(ev.Pendiente_proceso)}</strong></td>
            </tr>
            <tr>
                <td>Fecha presentación</td>
                <td>${ev.Fecha_presentacion ?? "-"}</td>
            </tr>
            <tr>
                <td>Observaciones de Relaciones Laborales</td>
                <td>${ev.Observaciones_rrll ?? "-"}</td>
            </tr>
        `).join("<tr><td colspan='2'><hr></td></tr>");
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

    // fecha de evento llega como "YYYY-MM-DD" y fecha registro
    // como "DD/MM/YYYY HH:MM:SS". 
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
    // FESTIVOS COLOMBIA 
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

    // Diferencia entre inicio y fin contando solo tiempo dentro de días hábiles
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

    // Duración desde que se registró el evento y desde que ocurrió el evento en si. 
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

    function filtrarTabla() {

        const filtros = {};
        document.querySelectorAll("thead th input").forEach(input => {
            if (input.disabled || input.dataset.col === undefined) return;
            filtros[input.dataset.col] = input.value.trim().toLowerCase();
        });

        const filtroUF = document.getElementById("filtroUF")?.value || "todos";
        const filtroEstado = document.getElementById("filtroEstado")?.value || "todos";
        const fechaDesde = document.getElementById("filtroFechaDesde")?.value || "";
        const fechaHasta = document.getElementById("filtroFechaHasta")?.value || "";

        const filtrados = registros.filter(registro => {

            if (filtroUF !== "todos" && String(registro.UF) !== filtroUF) {
                return false;
            }

            // En RRLL el rango se aplica exclusivamente a Fecha_evento.
            const fechaEvento = String(registro.fecha ?? "").slice(0, 10);
            if (fechaDesde && (!fechaEvento || fechaEvento < fechaDesde)) return false;
            if (fechaHasta && (!fechaEvento || fechaEvento > fechaHasta)) return false;

            if (filtroEstado === "cerrados" && (
                !registro.caso_cerrado || (CFG.propia === "laboral" && !registro.cerrado_por_laboral)
            )) return false;
            if (filtroEstado === "pendientes" && (
                registro.caso_cerrado || (CFG.propia === "laboral" ? registro.tiene_laboral : registro.estado_modulo)
            )) return false;
            if (filtroEstado === "gestionados" && (
                registro.caso_cerrado || !(CFG.propia === "laboral" ? registro.tiene_laboral : registro.estado_modulo)
            )) return false;

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
        document
            .getElementById("filtroEstado")
            ?.addEventListener("change", filtrarTabla);
        document
            .getElementById("filtroFechaDesde")
            ?.addEventListener("change", filtrarTabla);
        document
            .getElementById("filtroFechaHasta")
            ?.addEventListener("change", filtrarTabla);

        document.getElementById("btnExportarLaboral")?.addEventListener("click", () => {
            const fechaInicio = document.getElementById("filtroFechaDesde").value;
            const fechaFin = document.getElementById("filtroFechaHasta").value;

            if (!fechaInicio || !fechaFin) {
                alert("Seleccione Fecha desde y Fecha hasta para exportar.");
                return;
            }
            if (fechaInicio > fechaFin) {
                alert("La Fecha desde no puede ser posterior a la Fecha hasta.");
                return;
            }

            const params = new URLSearchParams({
                fecha_inicio: fechaInicio,
                fecha_fin: fechaFin,
                filtro_uf: document.getElementById("filtroUF").value,
                filtro_estado: document.getElementById("filtroEstado").value,
                modulo: "laboral"
            });
            window.location.href = `/Historico_danos/exportar_excel?${params.toString()}`;
        });
    };


    //======================================================
    // OCULTAR COLUMNAS DE ESTADO SEGÚN PERMISOS
    //======================================================

    function aplicarVisibilidadColumnas() {
        document.querySelectorAll("th.col-fecha-laboral").forEach(th => {
            th.style.display = MOSTRAR_COLUMNA_FECHA_LABORAL ? "" : "none";
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

            const celdaFechaLaboral = MOSTRAR_COLUMNA_FECHA_LABORAL
                ? `<td class="col-fecha-laboral">${window.formatearFechaRegistro(registro.fecha_r_laboral)}</td>`
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
                ${celdaFechaLaboral}
                <td>${celdaAdjuntos}</td>
                <td>${celdaAcciones}</td>
            `;

            tbody.appendChild(tr);
        });

        renderControlesPaginacion();
    }

    //--------------------------------------------------
    // Controles de paginación
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
    // Relaciones laborales permite reabrir mientras no esté cerrado
    //--------------------------------------------------

    function construirCeldaAcciones(registro) {

        const propia = CFG.propia;

        if (propia === "laboral") {
            if (registro.caso_cerrado) {
                return registro.cerrado_por_laboral && CFG.puedeReabrirCaso
                    ? ` <button class="btn btn-success" onclick="reabrirCaso('${registro.Id}')">Reabrir caso</button>`
                    : "";
            }
            return `<button class="btn btn-success" onclick="abrirModal('${registro.Id}')">
                        Añadir info
                    </button>`;
        }

        // Operaciones: el backend ya filtra la bandeja para que solo
        // aparezcan casos nuevos o casos que reaparecen únicamente para
        // cerrarse (conciliación SI + Seguridad Vial finalizado), así
        // que "tiene_oper" no debe usarse aquí para ocultar el botón.
        if (propia === "oper") {
            if (registro.caso_cerrado) {
                const botonReabrir = CFG.puedeReabrirCaso
                    ? ` <button class="btn btn-success" onclick="reabrirCaso('${registro.Id}')">Reabrir caso</button>`
                    : "";
                return botonReabrir;
            }
            return `<button class="btn btn-success" onclick="abrirModal('${registro.Id}')">
                        Añadir info
                    </button>`;
        }

        if (registro.caso_cerrado) {
            return "";
        }

        if (propia === "mtto" || propia === "svial") {
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

    filtrarTabla();

    window.renderTabla = renderTabla;


    //======================================================
    // MAPA DEL MODAL DE DETALLE (Leaflet + geocodificación OSM)
    //======================================================

    let mapaModal = null;
    let markerModal = null;
    let edicionUbicacionMapaActiva = false;
    const cacheCoordsDireccion = {};
    let solicitudDetalleActual = 0;

    // Geocodifica una dirección de texto a lat, lng 
    async function obtenerCoordsDesdeDireccion(direccion) {
        if (!direccion) return null;

        if (direccion in cacheCoordsDireccion) {
            return cacheCoordsDireccion[direccion];
        }

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

        // Reutiliza el formato de Capturador: la ubicación manual se guarda
        // como "latitud,longitud" en Direccion, sin crear nuevas columnas.
        mapaModal.on("click", evento => {
            if (!edicionUbicacionMapaActiva) return;

            const { lat, lng } = evento.latlng;
            const direccion = document.getElementById("evento_direccion");
            if (!direccion) return;

            direccion.value = `${lat.toFixed(6)},${lng.toFixed(6)}`;
            actualizarMapaModal({ lat, lng });
        });
    }

    function actualizarMapaModal(coords) {
        if (!mapaModal) return;

        mapaModal.setView([coords.lat, coords.lng], 16);

        if (markerModal) {
            mapaModal.removeLayer(markerModal);
        }
        markerModal = L.marker([coords.lat, coords.lng]).addTo(mapaModal);

        setTimeout(() => mapaModal.invalidateSize(), 100);
    }


    //======================================================
    // RENDER TABLAS DEL MODAL
    //======================================================

    async function renderDetalle(registro, data) {

        const inicioProcesamiento = performance.now();
        const registroDetalle = data.registro ?? {};    
        const oper = data.oper ?? {};
        const mtto = data.mtto ?? {};
        const svial = data.svial ?? {};
        const laboral = data.laboral ?? { eventos: [], estado: {} };
        const laboralPendientes = laboral.pendientes ?? [];
        const seccionLaboralPendiente = document.getElementById("seccionLaboralPendiente");
        const detalleLaboralPendiente = document.getElementById("infoEventoLaboralPendiente");
        const hayPendienteLaboral = laboralPendientes.length > 0;

        seccionLaboralPendiente.style.display = hayPendienteLaboral ? "" : "none";
        detalleLaboralPendiente.innerHTML = hayPendienteLaboral
            ? construirAvisosPendienteLaboral(laboralPendientes)
            : "";

        const modalRegistro = document.getElementById("modal_registro1");
        if (modalRegistro) {modalRegistro.textContent = ` #${registro.Id}`;}
        console.log(`[Ver archivos] Procesar JSON: ${(performance.now() - inicioProcesamiento).toFixed(2)} ms`);

        //--------------------------------------------------
        // TABLA GENERAL
        //--------------------------------------------------

        const datosGeneral = {
            fecha: registro.fecha,
            fecha_r: registro.fecha_r,
            ...registroDetalle
        };

        const inicioGeneral = performance.now();
        const htmlGeneral = construirTabla(datosGeneral, DETAIL_CONFIG.general);
        const inicioDomGeneral = performance.now();
        document.getElementById("infoEventoBody").innerHTML = htmlGeneral;
        console.log(`[Ver archivos] General - construir: ${(inicioDomGeneral - inicioGeneral).toFixed(2)} ms; DOM: ${(performance.now() - inicioDomGeneral).toFixed(2)} ms`);

        //--------------------------------------------------
        // OPERACIONAL
        //--------------------------------------------------

        // El costo del daño digitado por Operaciones (cuando el valor no
        // superó $2.000.000) se guarda en table_info_mtto.Costo, y el
        // valor conciliado que Operaciones haya registrado (conciliación
        // SI, o responsabilidad NO APLICA) se guarda en
        // table_info_labora.Valor_conciliado -- ambas columnas ya
        // existentes, reutilizadas aquí solo para mostrarlas dentro de
        // la sección de Operaciones.
        const costoRegistradoPorOper = !!oper.responsabilidad_operador;
        const operRegistroConciliacion =
            oper.conciliacion === "SI" || oper.responsabilidad_operador === "NO APLICA";

        const operParaTabla = {
            ...oper,
            CostoDelDanoOper: oper.CostoDelDanoOper,
            ValorConciliadoOper: operRegistroConciliacion ? laboral.estado?.Valor_conciliado : null
        };

        // Mantenimiento solo ve casos del camino > $2.000.000, donde los
        // controles propios de Operaciones (responsabilidad, conciliación,
        // costo, valor conciliado) no aplican -- se usa la vista reducida.
        const configOper = CFG.propia === "mtto" ? DETAIL_CONFIG.oper_basico : DETAIL_CONFIG.oper;

        if (SECCIONES_VISIBLES.has("oper")) {
            const inicioOper = performance.now();
            const htmlOper = construirTabla(operParaTabla, configOper);
            const inicioDomOper = performance.now();
            document.getElementById("infoEventooper").innerHTML = htmlOper;
            console.log(`[Ver archivos] Operaciones - construir: ${(inicioDomOper - inicioOper).toFixed(2)} ms; DOM: ${(performance.now() - inicioDomOper).toFixed(2)} ms`);
        }

        //--------------------------------------------------
        // MANTENIMIENTO
        //--------------------------------------------------

        // Si el costo fue registrado por Operaciones, ya se muestra en su
        // propia sección -- no se duplica aquí.
        const mttoParaTabla = costoRegistradoPorOper ? { ...mtto, Costo: null } : mtto;

        if (SECCIONES_VISIBLES.has("mtto")) {
            const inicioMtto = performance.now();
            const htmlMtto = construirTabla(mttoParaTabla, DETAIL_CONFIG.mantenimiento || DETAIL_CONFIG.mtto);
            const inicioDomMtto = performance.now();
            document.getElementById("infoEventomtto").innerHTML = htmlMtto;
            console.log(`[Ver archivos] Mantenimiento - construir: ${(inicioDomMtto - inicioMtto).toFixed(2)} ms; DOM: ${(performance.now() - inicioDomMtto).toFixed(2)} ms`);
        }

        //--------------------------------------------------
        // SEGURIDAD VIAL
        //--------------------------------------------------

        if (SECCIONES_VISIBLES.has("svial")) {
            const inicioSvial = performance.now();
            const htmlSvial = construirTabla(svial, DETAIL_CONFIG.svial);
            const inicioDomSvial = performance.now();
            document.getElementById("infoEventosvial").innerHTML = htmlSvial;
            console.log(`[Ver archivos] Seguridad Vial - construir: ${(inicioDomSvial - inicioSvial).toFixed(2)} ms; DOM: ${(performance.now() - inicioDomSvial).toFixed(2)} ms`);
        }

        //--------------------------------------------------
        // RELACIONES LABORALES (estado + histórico de eventos)
        //--------------------------------------------------

        if (SECCIONES_VISIBLES.has("laboral")) {

            const inicioLaboral = performance.now();

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

            // Si el valor conciliado fue registrado por Operaciones (ya se
            // muestra en esa sección), no se duplica aquí -- cada módulo
            // únicamente muestra el valor conciliado que realmente registró.
            const estadoParaTabla = operRegistroConciliacion
                ? { ...laboral.estado, Valor_conciliado: null }
                : laboral.estado;

            const htmlLaboral = filasEventos + construirTabla(estadoParaTabla, DETAIL_CONFIG.laboral_estado);
            const inicioDomLaboral = performance.now();
            document.getElementById("infoEventolaboral").innerHTML = htmlLaboral;
            console.log(`[Ver archivos] Relaciones Laborales - construir: ${(inicioDomLaboral - inicioLaboral).toFixed(2)} ms; DOM: ${(performance.now() - inicioDomLaboral).toFixed(2)} ms`);
        }

        //--------------------------------------------------
        // MAPA
        //--------------------------------------------------

        const inicioMapa = performance.now();
        const coords = await obtenerCoordsDesdeDireccion(registroDetalle.Direccion);

        initMapaModal();

        if (coords) {
            actualizarMapaModal(coords);
        } else {
            // Sin coordenadas válidas: se deja el mapa con la vista por defecto
            setTimeout(() => mapaModal.invalidateSize(), 100);
        }
        console.log(`[Ver archivos] Mapa/geocodificación: ${(performance.now() - inicioMapa).toFixed(2)} ms`);
    }

    //======================================================
    // EDICIÓN DE INFORMACIÓN DEL EVENTO (solo gestionados)
    //======================================================

    let eventoEdicionActual = null;
    let archivosEdicionSeleccionados = [];
    const RUTAS_POR_UF = {
        "10": ["CG147", "DG208", "CA127", "CH131", "CA129", "CA124", "TRANSITO A PATIO", "PATIO"],
        "16": ["CL149", "CB144", "CG137", "CA134", "CB138", "CA151", "CF154", "CA153", "CB145", "TRANSITO A PATIO", "PATIO"]
    };
    const ZONAS_DANO = ["LATERAL IZQUIERDO", "LATERAL DERECHO", "FRONTAL", "POSTERIOR", "TECHO", "ESPEJOS", "PUERTAS", "VIDRIOS", "LLANTAS", "ITS", "SIRCI", "CARROCERÍA INTERNA", "TREN MOTRIZ", "CHASIS"];
    const DANOS_OCASIONADOS = ["CONDUCTA OPERACIONAL", "INFRAESTRUCTURA PATIO", "INFRAESTRUCTURA VIAL", "VANDALISMO", "MECÁNICO", "SINIESTRO VIAL", "ALISTAMIENTO"];

    function escaparHtml(valor) {
        return String(valor ?? "").replace(/[&<>'"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]);
    }

    function opcionesSelect(valores, seleccionado) {
        return valores.map(valor => `<option value="${escaparHtml(valor)}" ${String(valor) === String(seleccionado ?? "") ? "selected" : ""}>${escaparHtml(valor)}</option>`).join("");
    }

    const AREAS_ESPECIALES = {
        "1": "MANTENIMIENTO", "2": "OPERACIONES", "3": "LAVADO",
        "4": "CAPACITACION OBZ", "5": "TERCERO", "6": "TANQUEO", "7": "ADMINISTRATIVO"
    };
    const CENTROS_OPERACIONES = ["GAITANA", "SAN ÁNDRES", "BILBAO", "SAN BERNARDINO"];

    function mostrarAccionesEdicion(editando) {
        edicionUbicacionMapaActiva = editando && CFG.propia === "oper";

        const mensajeMapaEdicion = document.getElementById("mensajeMapaEdicion");
        if (mensajeMapaEdicion) {
            mensajeMapaEdicion.style.display = edicionUbicacionMapaActiva ? "block" : "none";
        }
        document.getElementById("seccionMotivoModificacion").style.display = editando ? "block" : "none";

        const casoCerrado = Boolean(eventoEdicionActual?.registro?.caso_cerrado);

        document.getElementById("btn_editar_informacion").style.display =
        !editando && !casoCerrado ? "inline-block" : "none";

        document.getElementById("btn_eliminar_evento").style.display =
            editando ? "inline-block" : "none";

        document.getElementById("btn_guardar_modificacion").style.display =
            editando ? "inline-block" : "none";

        document.getElementById("btn_elegir_archivos_edicion").style.display =
            editando ? "inline-block" : "none";

        document.getElementById("btn_cancelar_modificacion").style.display =
            editando ? "inline-block" : "none";
    }

    function actualizarListaArchivosEdicion() {
        const lista = document.getElementById("lista_archivos_edicion");
        lista.innerHTML = "";
        lista.style.display = archivosEdicionSeleccionados.length ? "block" : "none";

        archivosEdicionSeleccionados.forEach((archivo, indice) => {
            const item = document.createElement("div");
            item.style.cssText = "display:flex; align-items:center; gap:10px; padding:9px 0; border-bottom:1px solid #ddd;";

            const nombre = document.createElement("span");
            nombre.textContent = `📄 ${archivo.name}`;
            nombre.style.flex = "1";

            const eliminar = document.createElement("button");
            eliminar.type = "button";
            eliminar.className = "btn";
            eliminar.textContent = "❌";
            eliminar.onclick = () => {
                archivosEdicionSeleccionados.splice(indice, 1);
                actualizarListaArchivosEdicion();
            };

            item.append(nombre, eliminar);
            lista.appendChild(item);
        });
    }

    function prepararEdicionEvento(registro, detalle, data) {
        const habilitado = CFG.propia === "oper";
        document.getElementById("accionesModificacion").style.display = habilitado ? "block" : "none";
        if (!habilitado) return;
        eventoEdicionActual = { registro, detalle, data };
        mostrarAccionesEdicion(false);
    }

    function actualizarMovilYTipologia() {
        const uf = document.getElementById("evento_uf").value;
        const movil = document.getElementById("evento_movil");
        const prefijo = uf === "10" ? "Z32-" : "Z34-";
        const digitos = movil.value.replace(/^Z(?:32|34)-/i, "").replace(/\D/g, "").slice(0, 4);
        movil.value = prefijo + digitos;
        const primerDigito = digitos.charAt(0);
        document.getElementById("evento_tipologia").value = primerDigito === "7" ? "PADRÓN" : primerDigito === "4" ? "BUSETÓN" : "";
    }

    async function actualizarOperador() {
        const codigo = document.getElementById("evento_codigo").value.trim();
        const area = document.getElementById("evento_area");
        if (AREAS_ESPECIALES[codigo]) {
            area.value = AREAS_ESPECIALES[codigo];
            return;
        }
        area.value = "OBZ";
        if (!codigo) return;
        try {
            const respuesta = await fetch(`/Operaciones/operador/${encodeURIComponent(codigo)}`);
            const operador = await respuesta.json();
            if (operador.existe) document.getElementById("evento_nombre").value = operador.nombre;
        } catch (error) {
            console.error("No se pudo consultar el operador:", error);
        }
    }

    function entrarModoEdicionEvento() {
        if (!eventoEdicionActual) return;
        const { registro, detalle } = eventoEdicionActual;
        const rutas = RUTAS_POR_UF[detalle.UF] || [];
        const centroActual = CENTROS_OPERACIONES.includes(detalle.Centro_operaciones)
            ? detalle.Centro_operaciones
            : "";
        document.getElementById("infoEventoBody").innerHTML = `
            <tr><td>FECHA EVENTO</td><td><input type="date" id="evento_fecha" value="${escaparHtml(registro.fecha)}"></td></tr>
            <tr><td>UF</td><td><select id="evento_uf">${opcionesSelect(["10", "16"], detalle.UF)}</select></td></tr>
            <tr><td>MÓVIL</td><td><input id="evento_movil" inputmode="numeric" value="${escaparHtml(detalle.Movil)}"></td></tr>
            <tr><td>CÓDIGO</td><td><input id="evento_codigo" value="${escaparHtml(detalle.Codigo)}"></td></tr>
            <tr><td>NOMBRE</td><td><input id="evento_nombre" value="${escaparHtml(detalle.Nombre)}"></td></tr>
            <tr><td>ÁREA</td><td><input id="evento_area" value="${escaparHtml(detalle.Area)}" readonly></td></tr>
            <tr><td>RUTA</td><td><select id="evento_ruta">${opcionesSelect(rutas, detalle.Ruta)}</select></td></tr>
            <tr><td>TIPOLOGÍA</td><td><input id="evento_tipologia" value="${escaparHtml(detalle.Tipologia)}" readonly></td></tr>
            <tr><td>VERSIÓN LIBRE</td><td><input id="evento_version" value="${escaparHtml(detalle.Version_libre)}"></td></tr>
            <tr><td>ZONA DEL DAÑO</td><td><select id="evento_zona">${opcionesSelect(ZONAS_DANO, detalle.Zona_dano)}</select></td></tr>
            <tr><td>PARTE AFECTADA</td><td><input id="evento_parte" value="${escaparHtml(detalle.Parte_afectada)}"></td></tr>
            <tr><td>DAÑO OCASIONADO POR</td><td><select id="evento_dano">${opcionesSelect(DANOS_OCASIONADOS, detalle.Dano_ocasionado)}</select></td></tr>
            <tr><td>CENTRO OPERACIONAL</td><td><select id="evento_centro">${centroActual ? "" : '<option value="" selected disabled>Seleccione un centro</option>'}${opcionesSelect(CENTROS_OPERACIONES, centroActual)}</select></td></tr>
            <tr><td>RESPONSABLE DILIGENCIAMIENTO</td><td>${escaparHtml(detalle.Registrador)}</td></tr>
            <tr><td>FECHA REGISTRO</td><td>${escaparHtml(registro.fecha_r)}</td></tr>
            <tr><td>DIRECCIÓN</td><td><input id="evento_direccion" value="${escaparHtml(detalle.Direccion)}"></td></tr>`;

        document.getElementById("evento_uf").addEventListener("change", e => {
            document.getElementById("evento_ruta").innerHTML = opcionesSelect(RUTAS_POR_UF[e.target.value] || [], "");
            actualizarMovilYTipologia();
        });
        document.getElementById("evento_movil").addEventListener("input", actualizarMovilYTipologia);
        document.getElementById("evento_codigo").addEventListener("change", actualizarOperador);
        document.getElementById("evento_direccion").addEventListener("input", async e => {
            const coords = await obtenerCoordsDesdeDireccion(e.target.value);
            if (coords) actualizarMapaModal(coords);
        });
        const inputArchivos = document.getElementById("archivos_edicion");
        archivosEdicionSeleccionados = [];
        inputArchivos.value = "";
        inputArchivos.onchange = () => {
            archivosEdicionSeleccionados.push(...inputArchivos.files);
            inputArchivos.value = "";
            actualizarListaArchivosEdicion();
        };
        actualizarListaArchivosEdicion();
        actualizarMovilYTipologia();
        actualizarOperador();
        mostrarAccionesEdicion(true);
        setTimeout(() => mapaModal?.invalidateSize(), 100);
    }

    document.getElementById("btn_guardar_modificacion")?.addEventListener("click", async () => {
        if (!eventoEdicionActual) return;
        const campoMotivo = document.getElementById("motivo_modificacion");
        if (!campoMotivo.reportValidity()) return;
        const motivo = campoMotivo.value.trim();
        const evento = {
            Fecha_evento: document.getElementById("evento_fecha").value,
            UF: document.getElementById("evento_uf").value,
            Movil: document.getElementById("evento_movil").value,
            Codigo: document.getElementById("evento_codigo").value,
            Nombre: document.getElementById("evento_nombre").value,
            Area: document.getElementById("evento_area").value,
            Ruta: document.getElementById("evento_ruta").value,
            Tipologia: document.getElementById("evento_tipologia").value,
            Version_libre: document.getElementById("evento_version").value,
            Zona_dano: document.getElementById("evento_zona").value,
            Parte_afectada: document.getElementById("evento_parte").value,
            Dano_ocasionado: document.getElementById("evento_dano").value,
            Centro_operaciones: document.getElementById("evento_centro").value,
            Direccion: document.getElementById("evento_direccion").value
        };
        const formData = new FormData();
        formData.append("evento", JSON.stringify(evento));
        formData.append("motivo_modificacion", motivo);
        archivosEdicionSeleccionados.forEach(archivo => {
            formData.append("archivos", archivo);
        });
        const response = await fetch(`/${CFG.modulo}/actualizar_evento/${eventoEdicionActual.registro.Id}`, {
            method: "POST",
            body: formData
        });
        const resultado = await response.json();
        alert(resultado.message);
        if (resultado.status === "success"){
            archivosEdicionSeleccionados = [];
            document.getElementById("archivos_edicion").value = "";
            actualizarListaArchivosEdicion();
            mostrarAccionesEdicion(false);
            cerrarModalAdjuntos()} ;
    });

    document.getElementById("btn_cancelar_modificacion")?.addEventListener("click", () => {
        if (!eventoEdicionActual) return;
        const { registro, data } = eventoEdicionActual;
        renderDetalle(registro, data);
        archivosEdicionSeleccionados = [];
        actualizarListaArchivosEdicion();
        mostrarAccionesEdicion(false);
    });

    document.getElementById("btn_editar_informacion")?.addEventListener("click", entrarModoEdicionEvento);

    document.getElementById("btn_eliminar_evento")?.addEventListener("click", async () => {
        if (!eventoEdicionActual) return;
        const campoMotivo = document.getElementById("motivo_modificacion");
        if (!campoMotivo.reportValidity()) return;
        const motivo = campoMotivo.value.trim();
        if (!confirm("¿Confirma que desea eliminar este caso? Esta acción no se puede deshacer.")) return;
        const response = await fetch(`/Operaciones/eliminar_evento/${eventoEdicionActual.registro.Id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ motivo_modificacion: motivo })
        });
        const resultado = await response.json();
        alert(resultado.message);
        if (resultado.status === "success") {
            registros = registros.filter(registro => registro.Id != eventoEdicionActual.registro.Id);
            filtrarTabla();
            cerrarModalAdjuntos();
        }
    });

    window.reabrirCaso = async function (id) {
        const motivo = (prompt("Motivo obligatorio de reapertura:") || "").trim();
        if (!motivo) {
            alert("El motivo de reapertura es obligatorio.");
            return;
        }
        if (!confirm("¿Confirma que desea reabrir este caso?")) return;
        const response = await fetch(`/${CFG.modulo}/reabrir_evento/${id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ motivo_modificacion: motivo })
        });
        const resultado = await response.json();
        alert(resultado.message);
        if (resultado.status === "success") {
            const registro = registros.find(registro => registro.Id == id);
            if (registro) registro.caso_cerrado = false;
            filtrarTabla();
        }
    };

    document.getElementById("btn_reabrir_evento")?.addEventListener("click", async () => {
        if (!eventoEdicionActual) return;
        const motivo = (prompt("Motivo obligatorio de reapertura:") || "").trim();
        if (!motivo) {
            alert("El motivo de reapertura es obligatorio.");
            return;
        }
        if (!confirm("¿Confirma que desea reabrir este caso?")) return;
        const response = await fetch(`/${CFG.modulo}/reabrir_evento/${eventoEdicionActual.registro.Id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ motivo_modificacion: motivo })
        });
        const resultado = await response.json();
        alert(resultado.message);
        if (resultado.status === "success") {
            eventoEdicionActual.registro.caso_cerrado = false;
            filtrarTabla();
            cerrarModalAdjuntos();
        }
    });


    //======================================================
    // RENDER GALERÍA
    //======================================================

    function renderGaleria(archivos) {

        const inicioArchivos = performance.now();
        const galeria = document.getElementById("galeriaAdjuntos");
        galeria.innerHTML = "";

        if (!archivos.length) {
            galeria.innerHTML = `<p style="text-align:center;color:#777">Sin archivos adjuntos</p>`;
            console.log(`[Ver archivos] Archivos - construir e insertar DOM: ${(performance.now() - inicioArchivos).toFixed(2)} ms (sin archivos)`);
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

        console.log(`[Ver archivos] Archivos - construir e insertar DOM: ${(performance.now() - inicioArchivos).toFixed(2)} ms (${archivos.length} archivos)`);
    }


    //======================================================
    // MODAL ADJUNTOS
    //======================================================

    window.mostrarAdjuntos = async function (id) {

        const inicioTotal = performance.now();
        // Si el usuario abre otro evento, la carga anterior queda invalidada.
        const solicitudActual = ++solicitudDetalleActual;

        const registro = registros.find(r => r.Id == id);
        if (!registro) return;

        movilSeleccionado = id;

        const inicioModal = performance.now();
        const modal = document.getElementById("modalAdjuntos");
        const tituloRegistro = document.getElementById("modal_registro1");

        if (!modal) {
            console.error("[Ver archivos] No existe #modalAdjuntos en el DOM");
            return;
        }

        if (!tituloRegistro) {
            console.error("[Ver archivos] No existe #modal_registro1 en el DOM");
            return;
        }

        modal.style.display = "block";
        tituloRegistro.textContent = `#${registro.Id}`;


        console.log(`[Ver archivos] Abrir modal: ${id}:${(performance.now() - inicioModal).toFixed(2)} ms`);

        try {
            const inicioFetch = performance.now();
            const response = await fetch(`/${CFG.modulo}/detalle/${id}`);

            console.log(
            `[Ver archivos] Fetch #${id}: ${(performance.now() - inicioFetch).toFixed(2)} ms (HTTP ${response.status})`);
            
            if(!response.ok){throw new Error(`HTTP ${response.status}`);}
            const inicioJson = performance.now();
            const data = await response.json();

            console.log(`[Ver archivos] response.json() #${id}: ${(performance.now() - inicioJson).toFixed(2)} ms`);

            //Si mientras esperábamos la respuesta el usuario
            // abrió otro evento, esta respuesta ya no sirve.
            
            if (solicitudActual !== solicitudDetalleActual){console.log(`[Ver archivos] Respuesta ignorada. ` + `Evento #${id} ya no es el evento activo.`);
            return;
            }
            const inicioRender = performance.now();

             // renderDetalle es async, por lo tanto debemos esperar
            // a que termine antes de continuar.
            await renderDetalle(registro, data);

            // Volvemos a comprobar porque renderDetalle()
            // contiene operaciones asíncronas (geocodificación).
            if (solicitudActual !== solicitudDetalleActual){console.log(`[Ver archivos] Render ignorado. ` + `Evento #${id} ya no es el evento activo.`);
            return;
            }
            prepararEdicionEvento(registro,data.registro ?? {},data);

            // Junta los 4 conjuntos de archivos que puede ver el módulo

            const todosArchivos = [
            ...(data.archivos ?? []),
            ...(SECCIONES_VISIBLES.has("mtto")
                ? (data.archivos_mtto ?? [])
                : []),
            ...(SECCIONES_VISIBLES.has("svial")
                ? (data.archivos_svial ?? [])
                : []),
            ...(SECCIONES_VISIBLES.has("laboral")
                ? (data.archivos_laboral ?? [])
                : [])
            ];

            renderGaleria(todosArchivos);

            console.log(
            `[Ver archivos] Render completo #${id}: ` +
            `${(performance.now() - inicioRender).toFixed(2)} ms`
            );

            console.log(
            `[Ver archivos] Total #${id}: ` +
            `${(performance.now() - inicioTotal).toFixed(2)} ms`
            );

        } catch (error) {
            if (solicitudActual !== solicitudDetalleActual) {
            console.log(`[Ver archivos] Error de solicitud anterior ignorado para #${id}`);
            return;
            }  
            console.error( `[Ver archivos] Error cargando evento #${id}:`,error);
            alert("Error cargando el evento.");
        }
    };

    window.cerrarModalAdjuntos = function () {
        document.getElementById("modalAdjuntos").style.display = "none";
    };


    //======================================================
    // MODAL FORMULARIO ("Añadir info" de la sección propia)
    //======================================================

    // Para Operaciones, si el registro llega a la bandeja con tiene_oper
    // ya en true, solo puede ser porque el caso termina en Operaciones
    // (conciliación = 'SI' o responsabilidad = 'NO APLICA') y todavía no
    // se ha cerrado -- el backend solo devuelve esos casos en la bandeja
    // de Operaciones (ver FILTRO_PENDIENTE_MODULO). En ese escenario el
    // formulario se precarga con lo ya guardado, para que el usuario
    // pueda seguir usando "Guardar información" o pasar a "Cerrar caso".
    function esModoCierreOperaciones(id) {
        if (CFG.propia !== "oper") return false;
        const registro = registros.find(r => r.Id == id);
        return !!(registro && registro.tiene_oper);
    }

    // Recuerda si el caso ya estaba guardado al abrir el modal (reabierto
    // únicamente para poder cerrarse), para que "Cerrar caso" solo envíe
    // la orden de cierre en vez de repetir el guardado.
    let modoCierreActivo = false;
    let envioOperacionesEnCurso = false;
    let reincidenciaBloqueada = false;
    let modoCorreccionGestion = false;

    function configurarModoOperaciones(modoCierre) {
        if (CFG.propia !== "oper") return;
        modoCierreActivo = modoCierre;
    }

    // Precarga en el formulario la información que Operaciones ya había
    // guardado, sin ocultar ni bloquear nada -- el usuario puede seguir
    // editando y usando "Guardar información" o "Cerrar caso" con
    // normalidad.
    async function precargarFormularioOperaciones(id) {
        try {
            const resp = await fetch(`/${CFG.modulo}/detalle/${id}`);
            const data = await resp.json();

            const oper = data.oper ?? {};
            const mtto = data.mtto ?? {};
            const laboral = data.laboral?.estado ?? {};

            document.getElementById("campo_principal").value = oper.Observaciones_operaciones ?? "";
            document.getElementById("observaciones").value = oper.Observaciones_correctivos ?? "";

            document.querySelectorAll("input[name='Revinf']").forEach(r => {
                r.checked = r.value === (oper.rev_error ?? "SI");
            });

            // Se conserva la respuesta ya guardada. Un costo vacío en
            // table_info_oper representa el camino que supera el límite,
            // porque solo se almacena costo_oper cuando no lo supera.
            const noSupera = oper.CostoDelDanoOper != null;
            document.querySelectorAll("input[name='CostoSupera2M']").forEach(r => {
                r.checked = r.value === (noSupera ? "NO" : "SI");
            });
            bloqueCostoDano.style.display = noSupera ? "block" : "none";
            bloqueResponsabilidad.style.display = noSupera ? "block" : "none";

            if (noSupera) {
                costoDanoDisplay.value = new Intl.NumberFormat("es-CO").format(Number(oper.CostoDelDanoOper));
                costoDanoHidden.value = oper.CostoDelDanoOper;
                document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => {
                    r.checked = r.value === oper.responsabilidad_operador;
                });
            } else {
                document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => {
                    r.checked = false;
                });
                document.querySelectorAll("input[name='Conciliacion']").forEach(r => {
                    r.checked = false;
                });
            }

            if (noSupera && oper.responsabilidad_operador === "NO APLICA") {
                bloqueValorConciliadoOper.style.display = "block";
                document.getElementById("lblValorConciliadoOper").textContent =
                    "VALOR CONCILIADO CON TERCEROS";
                bloqueMotivoCierreOper.style.display = "block";
                motivoCierreOper.required = true;
                motivoCierreOper.value = laboral.Tipo_cerrado ?? "";

                if (laboral.Valor_conciliado != null) {
                    valorConciliadoOperDisplay.value =
                        new Intl.NumberFormat("es-CO").format(Number(laboral.Valor_conciliado));
                    valorConciliadoOperHidden.value = laboral.Valor_conciliado;
                }
            }

            if (noSupera && oper.responsabilidad_operador === "SI" && oper.conciliacion === "SI") {
                bloqueConciliacion.style.display = "block";

                document.querySelectorAll("input[name='Conciliacion']").forEach(r => {
                    r.checked = r.value === "SI";
                });

                bloqueValorConciliadoOper.style.display = "block";

                if (laboral.Valor_conciliado != null) {
                    valorConciliadoOperDisplay.value =
                        new Intl.NumberFormat("es-CO").format(Number(laboral.Valor_conciliado));
                    valorConciliadoOperHidden.value = laboral.Valor_conciliado;
                }
            }

            actualizarVisibilidadCerrarCaso();
        } catch (error) {
            console.error("No se pudo precargar la información previa del caso:", error);
        }
    }

    async function precargarFormularioGestion(id) {
        if (CFG.propia === "oper") return precargarFormularioOperaciones(id);
        try {
            const resp = await fetch(`/${CFG.modulo}/detalle/${id}`);
            const data = await resp.json();
            if (CFG.propia === "mtto") {
                const mtto = data.mtto ?? {};
                const costo = mtto.Costo ?? "";
                document.getElementById("campo_principal").value = costo;
                document.getElementById("campo_principal_costo_display").value = costo
                    ? new Intl.NumberFormat("es-CO").format(Number(costo)) : "";
                document.getElementById("observaciones").value = mtto.observaciones ?? "";
                document.querySelectorAll("input[name='DanoAdicional']").forEach(r => {
                    r.checked = r.value === (mtto.dano_adicional ?? "NO");
                });
            }
            if (CFG.propia === "svial") {
                const svial = data.svial ?? {};
                document.getElementById("campo_principal").value = svial.Observaciones_svial ?? "";
            }
            if (CFG.propia === "laboral") {
                const laboral = data.laboral?.estado ?? {};
                document.getElementById("campo_principal").value = laboral.Observaciones_rrll ?? "";
            }
        } catch (error) {
            console.error("No se pudo precargar la gestión:", error);
        }
    }

    window.abrirModal = function (id) {

        reincidenciaBloqueada = false;
        movilSeleccionado = id;
        document.getElementById("modal_registro").textContent = id;
        document.getElementById("miModal").style.display = "block";

        const modoCierre = esModoCierreOperaciones(id);
        configurarModoOperaciones(modoCierre);

        const registro = registros.find(r => r.Id == id);
        modoCorreccionGestion = !!registro && !registro.caso_cerrado && (
            CFG.propia === "oper" ? registro.tiene_oper :
                CFG.propia === "laboral" ? registro.tiene_laboral : registro.estado_modulo
        );
        document.getElementById("bloqueMotivoGestion").style.display = modoCorreccionGestion ? "block" : "none";
        const motivoGestion = document.getElementById("motivo_gestion");
        motivoGestion.value = "";
        motivoGestion.required = modoCorreccionGestion;

        if (modoCorreccionGestion) {
            precargarFormularioGestion(id);
        }

        if (CFG.propia === "svial") {
            configurarConciliacionTercerosSvial(id);
        }

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
        modoCorreccionGestion = false;
        document.getElementById("motivo_gestion").required = false;
        limpiarFormulario();
    };


    //======================================================
    // LIMPIAR FORMULARIO
    //======================================================

    function limpiarFormulario() {
        document.getElementById("campo_principal").value = "";
        document.getElementById("campo_principal_costo_display").value = "";
        document.getElementById("observaciones").value = "";
        document.getElementById("observaciones").disabled = CFG.propia !== "mtto";
        document.getElementById("observaciones").required = false;

        document.querySelectorAll("input[name='DanoAdicional']").forEach(r => {
            r.checked = r.value === "NO";
        });

        if (CFG.propia === "mtto") {
            actualizarObservacionesPorDanoAdicional();
        }

        if (CFG.propia === "oper") {
            document.querySelectorAll("input[name='CostoSupera2M']").forEach(r => r.checked = false);
            document.getElementById("costo_dano_display").value = "";
            document.getElementById("costo_dano").value = "";
            document.getElementById("bloqueCostoDano").style.display = "none";
            document.getElementById("bloqueResponsabilidad").style.display = "none";
            document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => r.checked = false);
            document.querySelectorAll("input[name='Conciliacion']").forEach(r => r.checked = false);
            document.getElementById("mensajeReincidencia").style.display = "none";
            document.getElementById("mensajeReincidencia").textContent = "";
            document.getElementById("bloqueConciliacion").style.display = "none";
            document.getElementById("bloqueValorConciliadoOper").style.display = "none";
            document.getElementById("bloqueMotivoCierreOper").style.display = "none";
            document.getElementById("valor_conciliado_oper_display").value = "";
            document.getElementById("valor_conciliado_oper").value = "";
            document.getElementById("motivo_cierre_oper").value = "";
            document.getElementById("motivo_cierre_oper").required = false;
            const msgCosto = document.getElementById("msgCostoDano");
            if (msgCosto) { msgCosto.style.display = "none"; msgCosto.textContent = ""; }
        }

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

        if (CFG.propia === "svial") {
            resetConciliacionTercerosSvial();
        }

        // RRLL arranca en "NO" (caso no cerrado)
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
    // FORMATO DE MILES PARA VALOR CONCILIADO
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

        const completo = estadoCasoOpciones.querySelector("input[value='COMPLETO']");
        const procesosIndividuales = Array.from(
            estadoCasoOpciones.querySelectorAll("input[type='checkbox']:not([value='COMPLETO'])")
        );

        if (completo?.checked) {
            procesosIndividuales.forEach(cb => {
                cb.checked = false;
                cb.disabled = true;
            });
        } else {
            procesosIndividuales.forEach(cb => {
                cb.disabled = false;
            });
        }

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
    // (solo Mantenimiento).
    //======================================================

    function actualizarObservacionesPorDanoAdicional() {
        const radioSeleccionado = document.querySelector("input[name='DanoAdicional']:checked");
        const hayDanoAdicional = radioSeleccionado ? radioSeleccionado.value === "SI" : false;

        const lblObservaciones = document.querySelector("#bloqueObservaciones label[for='observaciones']");
        const textareaObservaciones = document.getElementById("observaciones");

        lblObservaciones.textContent = hayDanoAdicional
            ? "DESCRIBA EL DAÑO ADICIONAL:"
            : "OBSERVACIONES:";

        textareaObservaciones.required = hayDanoAdicional;
    }

    document.querySelectorAll("input[name='DanoAdicional']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;
            actualizarObservacionesPorDanoAdicional();
        });
    });


    //======================================================
    // NUEVO FLUJO DE OPERACIONES
    // (¿costo > $2.000.000? / responsabilidad / reincidencia / conciliación)
    //======================================================

    const costoDanoDisplay = document.getElementById("costo_dano_display");
    const costoDanoHidden = document.getElementById("costo_dano");
    const bloqueCostoDano = document.getElementById("bloqueCostoDano");
    const bloqueResponsabilidad = document.getElementById("bloqueResponsabilidad");
    const mensajeReincidencia = document.getElementById("mensajeReincidencia");
    const bloqueConciliacion = document.getElementById("bloqueConciliacion");
    const msgCostoDano = document.getElementById("msgCostoDano");
    const bloqueValorConciliadoOper = document.getElementById("bloqueValorConciliadoOper");
    const valorConciliadoOperDisplay = document.getElementById("valor_conciliado_oper_display");
    const valorConciliadoOperHidden = document.getElementById("valor_conciliado_oper");
    const bloqueMotivoCierreOper = document.getElementById("bloqueMotivoCierreOper");
    const motivoCierreOper = document.getElementById("motivo_cierre_oper");
    const bloqueConciliacionTercerosSvial = document.getElementById("bloqueConciliadoFavor");
    const conciliadoAFavor = document.getElementById("conciliado_a_favor");
    const valorConciliadoTercerosSvial = document.getElementById("valor_conciliado_terceros");

    // Límite máximo permitido para "Costo del daño"
    const LIMITE_COSTO_DANO = 2000000;

    // Formato de miles para "Costo del daño" + validación en tiempo real
    // (si supera el límite, se bloquea el guardado desde validarFormulario)
    if (costoDanoDisplay && costoDanoHidden) {
        costoDanoDisplay.addEventListener("input", () => {
            const soloDigitos = costoDanoDisplay.value.replace(/\D/g, "");
            costoDanoDisplay.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";
            costoDanoHidden.value = soloDigitos;

            const superaLimite = Number(soloDigitos || 0) > LIMITE_COSTO_DANO;
            if (msgCostoDano) {
                msgCostoDano.textContent = superaLimite
                    ? "Valor supera el monto máximo permitido de $2.000.000"
                    : "";
                msgCostoDano.style.display = superaLimite ? "block" : "none";
            }
        });
    }

    // Formato de miles para "Valor conciliado" (mismo patrón que "Costo del daño")
    if (valorConciliadoOperDisplay && valorConciliadoOperHidden) {
        valorConciliadoOperDisplay.addEventListener("input", () => {
            const soloDigitos = valorConciliadoOperDisplay.value.replace(/\D/g, "");
            valorConciliadoOperDisplay.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";
            valorConciliadoOperHidden.value = soloDigitos;
        });
    }

    function resetConciliacionTercerosSvial() {
        if (!bloqueConciliacionTercerosSvial) return;
        bloqueConciliacionTercerosSvial.style.display = CFG.propia === "svial" ? "block" : "none";
        conciliadoAFavor.value = "";
        valorConciliadoTercerosSvial.value = "";
        valorConciliadoTercerosSvial.disabled = true;
    }

    function actualizarValorConciliadoTercerosSvial() {
        const haySeleccion = !!conciliadoAFavor.value;
        valorConciliadoTercerosSvial.disabled = !haySeleccion;
        if (!haySeleccion) valorConciliadoTercerosSvial.value = "";
    }

    async function configurarConciliacionTercerosSvial(id) {
        resetConciliacionTercerosSvial();
    }

    if (conciliadoAFavor && valorConciliadoTercerosSvial) {
        conciliadoAFavor.addEventListener("change", actualizarValorConciliadoTercerosSvial);
        valorConciliadoTercerosSvial.addEventListener("input", () => {
            const soloDigitos = valorConciliadoTercerosSvial.value.replace(/\D/g, "");
            valorConciliadoTercerosSvial.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";
        });
    }

    function resetResponsabilidadYConciliacion() {
        reincidenciaBloqueada = false;
        document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => r.checked = false);
        document.querySelectorAll("input[name='Conciliacion']").forEach(r => r.checked = false);
        mensajeReincidencia.style.display = "none";
        mensajeReincidencia.textContent = "";
        bloqueConciliacion.style.display = "none";
        bloqueValorConciliadoOper.style.display = "none";
        bloqueMotivoCierreOper.style.display = "none";
        valorConciliadoOperDisplay.value = "";
        valorConciliadoOperHidden.value = "";
        motivoCierreOper.value = "";
        motivoCierreOper.required = false;
        actualizarVisibilidadCerrarCaso();
    }

    // Muestra/oculta "Cerrar caso" en tiempo real, únicamente cuando el
    // flujo actual del formulario termina en Operaciones: responsabilidad
    // = SI y conciliación = SI, o responsabilidad = NO APLICA. En
    // cualquier otro caso el botón permanece oculto y solo existe
    // "Guardar información".
    function actualizarVisibilidadCerrarCaso() {
        // Operaciones ya no tiene cierre manual: el cierre es automático
        // cuando finalizan las tres gestiones requeridas.
        return;

        if (reincidenciaBloqueada) {
            document.getElementById("btnCerrarCaso")?.style && (document.getElementById("btnCerrarCaso").style.display = "none");
            return;
        }

        const responsabilidad = document.querySelector("input[name='ResponsabilidadOperador']:checked");
        const conciliacion = document.querySelector("input[name='Conciliacion']:checked");

        const terminaEnOperaciones =
            (responsabilidad?.value === "SI" && conciliacion?.value === "SI") ||
            responsabilidad?.value === "NO APLICA";

        const btnCerrarCaso = document.getElementById("btnCerrarCaso");
        if (btnCerrarCaso) {
            btnCerrarCaso.style.display = terminaEnOperaciones ? "inline-block" : "none";
        }
    }

    // Pregunta 1: ¿el costo del daño supera $2.000.000?
    document.querySelectorAll("input[name='CostoSupera2M']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            const superaValor = radio.value === "SI";

            bloqueCostoDano.style.display = superaValor ? "none" : "block";
            bloqueResponsabilidad.style.display = superaValor ? "none" : "block";

            if (superaValor) {
                costoDanoDisplay.value = "";
                costoDanoHidden.value = "";
                if (msgCostoDano) {
                    msgCostoDano.style.display = "none";
                    msgCostoDano.textContent = "";
                }
            }

            resetResponsabilidadYConciliacion();
        });
    });

    // Pregunta: ¿operador acepta la responsabilidad?
    document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(radio => {
        radio.addEventListener("change", async () => {
            if (!radio.checked) return;

            reincidenciaBloqueada = false;
            mensajeReincidencia.style.display = "none";
            mensajeReincidencia.textContent = "";
            bloqueConciliacion.style.display = "none";
            bloqueValorConciliadoOper.style.display = "none";
            bloqueMotivoCierreOper.style.display = "none";
            valorConciliadoOperDisplay.value = "";
            valorConciliadoOperHidden.value = "";
            motivoCierreOper.value = "";
            motivoCierreOper.required = false;
            document.querySelectorAll("input[name='Conciliacion']").forEach(r => r.checked = false);
            actualizarVisibilidadCerrarCaso();

            document.getElementById("lblValorConciliadoOper").textContent =
                "VALOR CONCILIADO";

            if (radio.value === "NO APLICA") {
                document.getElementById("lblValorConciliadoOper").textContent =
                    "VALOR CONCILIADO CON TERCEROS";
                bloqueValorConciliadoOper.style.display = "block";
                bloqueMotivoCierreOper.style.display = "block";
                motivoCierreOper.required = true;
                return;
            }

            // La validación de reincidencia aplica tanto si el operador
            // acepta la responsabilidad (SI) como si no la acepta (NO):
            // ambas cuentan como responsabilidad del operador. "NO
            // APLICA" ya retornó arriba y nunca llega aquí.
            if (radio.value !== "SI" && radio.value !== "NO") return;

            if (!movilSeleccionado) return;

            try {
                const resp = await fetch(`/Operaciones/verificar_reincidencia/${movilSeleccionado}`);
                const data = await resp.json();

                // Si el usuario cambió de respuesta mientras se consultaba,
                // no se aplica una respuesta anterior.
                if (!radio.checked) return;

                if (data.bloqueado) {
                    reincidenciaBloqueada = true;
                    mensajeReincidencia.textContent =
                        "El operador ya registra 3 eventos con responsabilidad dentro de un período de 2 meses. " +
                        "El caso debe ser remitido a Relaciones Laborales.";
                    mensajeReincidencia.style.display = "block";
                    bloqueConciliacion.style.display = "none";
                    document.getElementById("btnCerrarCaso")?.style && (document.getElementById("btnCerrarCaso").style.display = "none");
                } else if (radio.value === "SI") {
                    // La pregunta de conciliación solo existe cuando la
                    // responsabilidad es SI; para NO el flujo continúa
                    // igual que hoy (sin este bloque).
                    bloqueConciliacion.style.display = "block";
                }
            } catch (error) {
                console.error("No se pudo verificar la reincidencia del operador:", error);
                alert("No se pudo verificar el historial del operador. Intente nuevamente.");
            }
        });
    });

    // Pregunta: ¿se llega a conciliación? Si es SI, aparece "Valor
    // conciliado" (mismo patrón que "Costo del daño") y puede aparecer
    // "Cerrar caso".
    document.querySelectorAll("input[name='Conciliacion']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            const esSi = radio.value === "SI";

            bloqueValorConciliadoOper.style.display = esSi ? "block" : "none";
            if (!esSi) {
                valorConciliadoOperDisplay.value = "";
                valorConciliadoOperHidden.value = "";
            }

            actualizarVisibilidadCerrarCaso();
        });
    });


    //======================================================
    // CONSTRUIR FORMDATA
    //======================================================

    function construirFormData() {

        const formData = new FormData();

        formData.append("Id_damage_to_fleet", movilSeleccionado);
        formData.append("Usuario_registro_oper", document.body.dataset.usuario);
        if (modoCorreccionGestion) {
            formData.append("Motivo_modificacion", document.getElementById("motivo_gestion").value.trim());
        }

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

            if (CFG.propia === "laboral") {
                formData.append(
                    "Tipo_cerrado_input",
                    revision === "SI" ? document.getElementById("motivo_cierre").value : ""
                );
            }
        }

        // Mantenimiento: "¿Existe algún daño más asociado al evento?"
        if (CFG.propia === "mtto") {
            const danoAdicional = document.querySelector("input[name='DanoAdicional']:checked");
            formData.append("dano_adicional", danoAdicional ? danoAdicional.value : "NO");
        }

        if (CFG.propia === "svial" && conciliadoAFavor.value) {
            formData.append("conciliado_a_favor", conciliadoAFavor.value);
            formData.append(
                "valor_conciliado_terceros",
                valorConciliadoTercerosSvial.value.replace(/\D/g, "")
            );
        }

        // Operaciones: nuevo flujo (costo del daño / responsabilidad / conciliación)
        if (CFG.propia === "oper") {
            const costoSupera = document.querySelector("input[name='CostoSupera2M']:checked");
            formData.append("costo_supera_2m", costoSupera ? costoSupera.value : "");

            if (costoSupera && costoSupera.value === "NO") {
                formData.append("costo_valor", document.getElementById("costo_dano").value);

                const responsabilidad = document.querySelector("input[name='ResponsabilidadOperador']:checked");
                formData.append("responsabilidad_operador", responsabilidad ? responsabilidad.value : "");

                if (responsabilidad && responsabilidad.value === "NO APLICA") {
                    formData.append("conciliacion", "");
                    formData.append("motivo_cierre_oper", motivoCierreOper.value);

                    formData.append(
                        "valor_conciliado_oper",
                        document.getElementById("valor_conciliado_oper").value
                    );

                } else if (
                    responsabilidad &&
                    responsabilidad.value === "SI" &&
                    document.getElementById("bloqueConciliacion").style.display !== "none"
                ) {

                    const conciliacion = document.querySelector("input[name='Conciliacion']:checked");
                    formData.append("conciliacion", conciliacion ? conciliacion.value : "");

                    if (conciliacion && conciliacion.value === "SI") {
                        formData.append("valor_conciliado_oper", document.getElementById("valor_conciliado_oper").value);
                    }
                }
            }
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
        if (modoCorreccionGestion) {
            const motivoCambio = document.getElementById("motivo_gestion");

            if (!motivoCambio.reportValidity()) return false;
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
                !document.getElementById("observaciones").value.trim()) {
                alert("Describa el daño adicional.");
                return false;
            }
        }

        if (CFG.propia === "oper") {
            const costoSupera = document.querySelector("input[name='CostoSupera2M']:checked");
            if (!costoSupera) {
                alert("Responda si el costo del daño supera $2.000.000.");
                return false;
            }

            if (costoSupera.value === "NO") {
                if (!document.getElementById("costo_dano").value) {
                    alert("Ingrese el costo del daño.");
                    return false;
                }

                // Mientras el mensaje de "supera el monto máximo" esté
                // visible, no se permite guardar la información.
                if (Number(document.getElementById("costo_dano").value || 0) > LIMITE_COSTO_DANO) {
                    return false;
                }

                const responsabilidad = document.querySelector("input[name='ResponsabilidadOperador']:checked");
                if (!responsabilidad) {
                    alert("Responda si el operador acepta la responsabilidad.");
                    return false;
                }

                if (responsabilidad.value === "NO APLICA" && !motivoCierreOper.reportValidity()) {
                    return false;
                }

                if (responsabilidad.value === "SI" &&
                    document.getElementById("bloqueConciliacion").style.display !== "none") {
                    const conciliacion = document.querySelector("input[name='Conciliacion']:checked");
                    if (!conciliacion) {
                        alert("Responda si se llega a conciliación.");
                        return false;
                    }

                    if (conciliacion.value === "SI" && !document.getElementById("valor_conciliado_oper").value) {
                        alert("Ingrese el valor conciliado.");
                        return false;
                    }
                }
            }
        }

        return true;
    }


    //======================================================
    // ACTUALIZAR ESTADO LOCAL TRAS GUARDAR 
    //======================================================

    function actualizarEstadoLocal(id) {

        const registro = registros.find(r => r.Id == id);
        if (!registro) return;

        let debeOcultarse = false;

        if (["oper", "mtto", "svial"].includes(CFG.propia)) {
            registro["tiene_" + CFG.propia] = true;
            registro.estado_modulo = true;
            filtrarTabla();
            return;
        }


        if (CFG.propia === "laboral") {
            const revision = document.querySelector("input[name='Revinf']:checked")?.value;
            if (revision === "SI") {
                registro.caso_cerrado = true;
                registro.tiene_laboral = true;
                // El filtro "Cerrados" debe mostrar inmediatamente el caso
                // que RRLL acaba de cerrar; los otros filtros lo excluirán
                // según estado_caso sin retirar su historial de la lista.
                filtrarTabla();
                return;
            }
        } else {
            registro["tiene_" + CFG.propia] = true;
            debeOcultarse = true;
        }

        // Ya diligenció su parte 
        if (debeOcultarse) {
            registros = registros.filter(r => r.Id != id);
        }

        renderTabla(registros);
    }


    //======================================================
    // SUBMIT GENERAL
    //======================================================

    async function enviarFormulario() {

        if (CFG.propia === "oper" && envioOperacionesEnCurso) return;

        if (!validarFormulario()) return;

        const formulario = FORM_CONFIG[CFG.propia];
        const endpoint = `/${CFG.modulo}/${formulario.endpoint}`;
        const idGuardado = movilSeleccionado;

        if (CFG.propia === "oper") {
            envioOperacionesEnCurso = true;
            document.getElementById("btnGuardar").disabled = true;
        }

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                body: construirFormData()
            });

            const result = await response.json();

            if (result.status === "success") {
                if (CFG.propia === "oper" && result.bloqueado_reincidencia) {
                    reincidenciaBloqueada = true;
                    bloqueConciliacion.style.display = "none";
                    document.getElementById("btnCerrarCaso")?.style && (document.getElementById("btnCerrarCaso").style.display = "none");
                }
                alert(result.message);
                actualizarEstadoLocal(idGuardado);
                cerrarModal();
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error(error);
            alert("Error enviando formulario.");
        } finally {
            if (CFG.propia === "oper") {
                envioOperacionesEnCurso = false;
                document.getElementById("btnGuardar").disabled = false;
            }
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
    // CERRAR CASO (solo Operaciones, cuando hubo conciliación)
    //======================================================

    // Envía únicamente la orden de cierre (Id + usuario). Se usa tanto en
    // "modo cierre" (la info ya se guardó antes) como al final del flujo
    // de guardar+cerrar del formulario nuevo.
    async function enviarCierreCaso(idGuardado) {
        const formData = new FormData();
        formData.append("Id_damage_to_fleet", idGuardado);
        formData.append("Usuario_registro_oper", document.body.dataset.usuario);

        const response = await fetch(`/${CFG.modulo}/cerrar_caso_oper`, {
            method: "POST",
            body: formData
        });

        return response.json();
    }

    document.getElementById("btnCerrarCaso")?.addEventListener("click", async () => {

        if (!movilSeleccionado) {
            alert("Seleccione un registro.");
            return;
        }

        const idGuardado = movilSeleccionado;

        // Modo cierre: el caso ya fue guardado antes (reapareció en la
        // bandeja únicamente para cerrarse). Solo se envía la orden de
        // cierre, exactamente como ya funcionaba.
        if (modoCierreActivo) {

            if (!confirm("¿Confirma que desea cerrar este caso? Esta acción no se puede deshacer.")) {
                return;
            }

            try {
                const result = await enviarCierreCaso(idGuardado);

                if (result.status === "success") {
                    alert(result.message);
                    registros = registros.filter(r => r.Id != idGuardado);
                    renderTabla(registros);
                    cerrarModal();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error(error);
                alert("Error cerrando el caso.");
            }
            return;
        }

        // Formulario nuevo: el caso termina en Operaciones (responsabilidad
        // SI + conciliación SI). "Cerrar caso" primero guarda toda la
        // información (igual que "Guardar información", reutilizando el
        // mismo endpoint) y, si el guardado es exitoso, envía la orden de
        // cierre reutilizando la misma lógica del modo cierre.
        if (!validarFormulario()) return;

        if (!confirm("¿Confirma que desea cerrar este caso? Esta acción no se puede deshacer.")) {
            return;
        }

        try {
            const responseGuardar = await fetch(`/${CFG.modulo}/${FORM_CONFIG[CFG.propia].endpoint}`, {
                method: "POST",
                body: construirFormData()
            });

            const resultGuardar = await responseGuardar.json();

            if (resultGuardar.status !== "success") {
                alert(resultGuardar.message);
                return;
            }

            actualizarEstadoLocal(idGuardado);

            const resultCierre = await enviarCierreCaso(idGuardado);

            if (resultCierre.status === "success") {
                alert(resultCierre.message);
                registros = registros.filter(r => r.Id != idGuardado);
                renderTabla(registros);
            } else {
                alert(resultCierre.message);
            }

            cerrarModal();
        } catch (error) {
            console.error(error);
            alert("Error cerrando el caso.");
        }
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

    let imagenesLightbox = [];
    let indiceImagenLightbox = -1;

    function actualizarLightbox() {
        document.getElementById("lightbox-img").src = imagenesLightbox[indiceImagenLightbox];
        document.getElementById("lightbox-anterior").style.display = indiceImagenLightbox > 0 ? "" : "none";
        document.getElementById("lightbox-siguiente").style.display = indiceImagenLightbox < imagenesLightbox.length - 1 ? "" : "none";
        document.getElementById("lightbox").style.display = "flex";
    }

    window.abrirLightbox = function (url) {
        imagenesLightbox = Array.from(document.querySelectorAll(".galeria img")).map(img => img.src);
        indiceImagenLightbox = imagenesLightbox.indexOf(new URL(url, window.location.origin).href);
        if (indiceImagenLightbox < 0) {
            imagenesLightbox = [url];
            indiceImagenLightbox = 0;
        }
        actualizarLightbox();
    };

    window.navegarLightbox = function (direccion) {
        const siguienteIndice = indiceImagenLightbox + direccion;
        if (siguienteIndice < 0 || siguienteIndice >= imagenesLightbox.length) return;
        indiceImagenLightbox = siguienteIndice;
        actualizarLightbox();
    };

    window.cerrarLightbox = function () {
        document.getElementById("lightbox").style.display = "none";
        document.getElementById("lightbox-img").src = "";
        imagenesLightbox = [];
        indiceImagenLightbox = -1;
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
