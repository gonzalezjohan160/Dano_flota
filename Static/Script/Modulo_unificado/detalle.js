// Módulo unificado — Detalle cruzado del caso: mapa de ubicación y secciones de cada módulo.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

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
    mapaModal.attributionControl.setPrefix(false);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; OpenStreetMap contributors &middot; Open Database License (ODbL)',
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


    const mttoParaTabla = mtto;

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
                    <td>${escaparHtml(ev.Fecha_presentacion ?? "-")}</td>
                </tr>
                <tr>
                    <td>Estado del caso</td>
                    <td>${escaparHtml(formatearEstadoCaso(ev.Pendiente_proceso))}</td>
                </tr>
                <tr>
                    <td>Observaciones</td>
                    <td>${escaparHtml(ev.Observaciones_rrll ?? "-")}</td>
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


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarDetalle() {
    // Esta parte no tiene acciones de arranque.
}
