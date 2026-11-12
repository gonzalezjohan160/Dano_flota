// Módulo unificado — Tabla principal: filas, paginación y botones de acción.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

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

        console.log("FECHA ORIGINAL:", registro.fecha);
        console.log("REGISTRO MODULO:", registro);

        const fechaFormateada =
            window.formatearFechaRegistro(registro.fecha);

        const { duracion, duracionEvento, t } =
            window.calcularDuracionesRegistro(registro);

        const tr = document.createElement("tr");

        tr.classList.add(t && t.dias >= 2 ? "row-danger" : "row-ok");
        tr.dataset.uf = registro.UF;

        const celdaFechaLaboral = MOSTRAR_COLUMNA_FECHA_LABORAL
            ? `<td class="col-fecha-laboral">${escaparHtml(window.formatearFechaRegistro(registro.fecha_r_laboral))}</td>`
            : "";

        const celdaAdjuntos = registro.archivos_count > 0
            ? `<button class="btn" data-oper-accion="mostrar-adjuntos" data-id="${escaparHtml(registro.Id)}">
                    Ver archivos (${escaparHtml(registro.archivos_count)})
               </button>`
            : `<span style="color:#777">Sin archivos</span>`;

        const celdaAcciones = construirCeldaAcciones(registro);

        tr.innerHTML = `
            <td>${escaparHtml(registro.Id)}</td>
            <td>${escaparHtml(fechaFormateada)}</td>
            <td>${escaparHtml(registro.Movil)}</td>
            <td>${escaparHtml(registro.Codigo)}</td>
            <td>${escaparHtml(registro.Nombre)}</td>
            <td>${escaparHtml(duracion)}</td>
            <td>${escaparHtml(duracionEvento)}</td>
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

//--------------------------------------------------
// Relaciones laborales permite reabrir mientras no esté cerrado
//--------------------------------------------------

function construirCeldaAcciones(registro) {

    const propia = CFG.propia;

    if (propia === "laboral") {
        if (registro.caso_cerrado) {
            return registro.cerrado_por_laboral && CFG.puedeReabrirCaso
                ? ` <button class="btn btn-success" data-oper-accion="reabrir-caso" data-id="${escaparHtml(registro.Id)}">Reabrir caso</button>`
                : "";
        }
        return `<button class="btn btn-success" data-oper-accion="abrir-modal" data-id="${escaparHtml(registro.Id)}">
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
                ? ` <button class="btn btn-success" data-oper-accion="reabrir-caso" data-id="${escaparHtml(registro.Id)}">Reabrir caso</button>`
                : "";
            return botonReabrir;
        }
        return `<button class="btn btn-success" data-oper-accion="abrir-modal" data-id="${escaparHtml(registro.Id)}">
                    Añadir info
                </button>`;
    }

    if (registro.caso_cerrado) {
        return "";
    }

    if (propia === "mtto" || propia === "svial") {
        return `<button class="btn btn-success" data-oper-accion="abrir-modal" data-id="${escaparHtml(registro.Id)}">
                    Añadir info
                </button>`;
    }

    const yaTiene = registro["tiene_" + propia];

    if (yaTiene) {
        return `<span class="badge badge-ok">Ya registrado</span>`;
    }

    return `<button class="btn btn-success" data-oper-accion="abrir-modal" data-id="${escaparHtml(registro.Id)}">
                Añadir info
            </button>`;
}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarTabla() {
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

    filtrarTabla();

    document.getElementById("tablaRegistros").addEventListener("click", event => {
        const boton = event.target.closest("[data-oper-accion]");
        if (!boton) return;

        const { operAccion, id } = boton.dataset;
        if (operAccion === "mostrar-adjuntos") window.mostrarAdjuntos(id);
        if (operAccion === "abrir-modal") window.abrirModal(id);
        if (operAccion === "reabrir-caso") window.reabrirCaso(id);
    });

    window.renderTabla = renderTabla;
}
