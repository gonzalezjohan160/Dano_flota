// ================= VARIABLES GLOBALES =================
let inputAdjuntos = null;
let listaAdjuntos = null;
let adjuntosSeleccionados = [];
let registros = [];
let movilSeleccionado = "";


document.addEventListener("DOMContentLoaded", () => {



    const jsonTag = document.getElementById("registros-json");


    if (!jsonTag) {
        console.error("❌ NO existe el script registros-json");
        return;
    }

    const data = JSON.parse(jsonTag.textContent);

    // ================= ESTADO DE FILTROS / PAGINACIÓN =================
    let estadoHistorico = {
        movil: "",
        tipo: "todos",
        uf: "todos",
        fecha_inicio: "",
        fecha_fin: "",
        pagina_actual: 1,
        total_paginas: 0,
        total_registros: 0
    };

    try {
        const estadoTag = document.getElementById("estado-historico-json");
        if (estadoTag) {
            estadoHistorico = { ...estadoHistorico, ...JSON.parse(estadoTag.textContent) };
        }
    } catch (e) {
        console.error("❌ Error al parsear estado de filtros:", e);
    }

    // Restaurar los controles de filtro con el estado actual (para que persistan al paginar/filtrar)
    const elTipo = document.getElementById("filtroTipo");
    const elUF = document.getElementById("filtroUF");
    const elFechaInicio = document.getElementById("filtroFechaInicio");
    const elFechaFin = document.getElementById("filtroFechaFin");

    if (elTipo) elTipo.value = estadoHistorico.tipo || "todos";
    if (elUF) elUF.value = estadoHistorico.uf || "todos";
    if (elFechaInicio) elFechaInicio.value = estadoHistorico.fecha_inicio || "";
    if (elFechaFin) elFechaFin.value = estadoHistorico.fecha_fin || "";

    function actualizarInfoPaginacion() {
        const info = document.getElementById("infoPaginacion");
        const btnAnterior = document.getElementById("btnPaginaAnterior");
        const btnSiguiente = document.getElementById("btnPaginaSiguiente");
        if (!info) return;

        info.textContent = `Página ${estadoHistorico.pagina_actual} de ${estadoHistorico.total_paginas || 1} (${estadoHistorico.total_registros} registros)`;
        if (btnAnterior) { btnAnterior.disabled = estadoHistorico.pagina_actual <= 1; }
        if (btnSiguiente) { btnSiguiente.disabled = estadoHistorico.pagina_actual >= estadoHistorico.total_paginas; }
    }

    actualizarInfoPaginacion();

    function construirQueryHistorico(page) {
        const inputMovil = document.getElementById("buscarMovil");
        const movil = inputMovil ? inputMovil.value.trim() : "";
        const tipo = elTipo?.value || "todos";
        const uf = elUF?.value || "todos";
        const fechaInicio = elFechaInicio?.value || "";
        const fechaFin = elFechaFin?.value || "";

        const params = new URLSearchParams();
        if (movil) params.set("movil", movil);
        params.set("tipo", tipo);
        params.set("uf", uf);
        if (fechaInicio) params.set("fecha_inicio", fechaInicio);
        if (fechaFin) params.set("fecha_fin", fechaFin);
        params.set("page", page || 1);
        return params.toString();
    }

    window.ejecutarBusqueda = function () {
        const movil = document.getElementById("buscarMovil").value.trim();
        if (movil) {
            // Buscar el móvil indicado
            window.location.href = `/Historico_movil/?${construirQueryHistorico(1)}`;
        } else {
            //volver a mostrar todo el historial
            window.location.href = `/Historico_movil/?${construirQueryHistorico(1)}`;
        }
    };

    // Permitir que funcione al presionar "Enter"
    document.getElementById("buscarMovil")?.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            ejecutarBusqueda();
        }
    });

    // ================= FILTRO POR TIPO / FECHAS / UF =================
    window.aplicarFiltrosHistorico = function () {
        window.location.href = `/Historico_movil/?${construirQueryHistorico(1)}`;
    };

    // ================= PAGINACIÓN =================
    window.irPaginaAnterior = function () {
        if (estadoHistorico.pagina_actual > 1) {
            window.location.href = `/Historico_movil/?${construirQueryHistorico(estadoHistorico.pagina_actual - 1)}`;
        }
    };

    window.irPaginaSiguiente = function () {
        if (estadoHistorico.pagina_actual < estadoHistorico.total_paginas) {
            window.location.href = `/Historico_movil/?${construirQueryHistorico(estadoHistorico.pagina_actual + 1)}`;
        }
    };

    // ================= DESCARGAR EXCEL =================
    window.descargarExcelHistorico = function () {
        const params = construirQueryHistorico(1); // la exportación no pagina, trae todo lo filtrado
        window.location.href = `/Historico_movil/exportar_excel?${params}`;
    };

    // ================= CARGAR REGISTROS =================
    try {
        const script = document.getElementById("registros-json");
        registros = JSON.parse(script.textContent);
    } catch (e) {
        console.error("❌ Error al parsear registros:", e);
    }

    window.activarFiltros = function () {
        document.querySelectorAll("thead th input").forEach(input => {
            if (!input.disabled) {
                input.addEventListener("input", filtrarTabla);
                input.addEventListener("change", filtrarTabla);
            }
        });

    };

    // ================= TABLA =================
    function renderTabla(lista) {
        const tbody = document.getElementById("tablaRegistros");
        tbody.innerHTML = "";
        activarFiltros();


        lista.forEach(registro => {

            const tr = document.createElement("tr");
            tr.dataset.uf = registro.UF || "";
            const fechaFormateadacombi = formatoFecha(registro?.fecha);
            const formatoCOP = v =>
                v ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", minimumFractionDigits: 0 }).format(v) : "-";

            tr.innerHTML = `
                <td>${fechaFormateadacombi || "-"}</td>
                <td>${registro.Movil || "-"}</td>
                <td>${registro.tipo || "-"}</td>
                <td>${formatoCOP(registro.costo) ?? "-"}</td>
                <td>
                    <button class="btn" onclick="mostrarAdjuntos('${registro.tipo}', ${registro.id})">
                        Info
                    </button>
                </td>
            `;

            tbody.appendChild(tr);
        });
    }

    renderTabla(registros);


    // ================= MODAL ADJUNTOS =================
    window.mostrarAdjuntos = (tipo, id) => {


        if (tipo === "DAÑO") {

            document.getElementById("modalAdjuntos_danos").style.display = "block";
            document.getElementById("modal_danos").textContent = id;

            fetch(`/Historico_movil/detalle/${id}`)
                .then(res => res.json())
                .then(data => cargarModalDanios(data))
                .catch(err => {
                    console.error("Error cargando daño:", err);
                    alert("Error cargando daño");
                });

        } else if (tipo === "REPARACIÓN") {

            document.getElementById("modalAdjuntos_reparaciones").style.display = "block";
            document.getElementById("modal_reparaciones").textContent = id;

            fetch(`/Historico_movil/detalle_reparacion/${id}`)
                .then(res => res.json())
                .then(data => cargarModalReparaciones(data))
                .catch(err => {
                    console.error("Error cargando reparación:", err);
                    alert("Error cargando reparación");
                });
        }
    };


    // ================= FORMULARIO ADJUNTOS =================

    function cargarModalDanios(data) {


        const galeria = document.getElementById("galeriaAdjuntos");
        const infoBody = document.getElementById("infoEventoBody");
        const infomtto = document.getElementById("infoEventomtto");
        const infosvial = document.getElementById("infoEventosvial");
        const infosoper = document.getElementById("infoEventooper");

        const registroDetalle = data.registro || {};
        const mtto = data.mtto || null;
        const svial = data.svial || null;
        const oper = data.oper || null;



        // Obtener coordenadas desde la dirección
        const coords = obtenerCoordsDesdeDireccion(registroDetalle.Direccion);



        // ================= CARGA DE MAPA =================      
        if (coords && window.initMapaModal && window.actualizarMapaModal) {
            window.initMapaModal();
            window.actualizarMapaModal(coords);
        }

        const fechaFormateadaoper = formatoFechaHora(oper?.Fecha_registro);
        const fechaFormateadamtto = formatoFechaHora(mtto?.Fecha_registro);
        const fechaFormateadasvial = formatoFechaHora(svial?.Fecha_registro);
        const fechaFormateadascapt = formatoFechaHora(registroDetalle?.Fecha_registro);
        const fechaFormateadaevento = formatoFecha(registroDetalle?.Fecha_evento);

        const formatoCOP = v =>
            v ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", minimumFractionDigits: 0 }).format(v) : "-";

        infoBody.innerHTML = `
                        <tr><td>FECHA EVENTO</td><td>${fechaFormateadaevento || "-"}</td></tr>
                        <tr><td>MÓVIL</td><td>${registroDetalle.Movil || "-"}</td></tr>
                        <tr><td>CÓDIGO</td><td>${registroDetalle.Codigo || "-"}</td></tr>
                        <tr><td>NOMBRE</td><td>${registroDetalle.Nombre || "-"}</td></tr>
                        <tr><td>ÁREA</td><td>${registroDetalle.Area || "-"}</td></tr>
                        <tr><td>RUTA</td><td>${registroDetalle.Ruta || "-"}</td></tr>
                        <tr><td>VERSIÓN LIBRE</td><td>${registroDetalle.Version_libre || "-"}</td></tr>
                        <tr><td>ZONA DEL DAÑO</td><td>${registroDetalle.Zona_dano || "-"}</td></tr>
                        <tr><td>PARTE AFECTADA</td><td>${registroDetalle.Parte_afectada || "-"}</td></tr>
                        <tr><td>DAÑO OCASIONADO POR</td><td>${registroDetalle.Dano_ocasionado || "-"}</td></tr>
                        <tr><td>CENTRO OPERACIONAL</td><td>${registroDetalle.Centro_operaciones || "-"}</td></tr>
                        <tr><td>RESPONSABLE DILIGENCIAMIENTO</td><td>${registroDetalle.Registrador || "-"}</td></tr>
                        <tr><td>FECHA REGISTRO</td><td>${fechaFormateadascapt || "-"}</td></tr>
                        <tr><td>DIRECCIÓN</td><td>${registroDetalle.Direccion || "-"}</td></tr>
                    `;

        infosoper.innerHTML = `
                        <tr><td>OBSERVACIÓNES TECNICAS CONTROL OPERACIONAL</td><td>${oper ? oper.Observaciones_operaciones : '-'}</td></tr>
                        <tr><td>LA INFORMACIÓN CARGADA ES CORRECTA?</td><td>${oper ? oper.rev_error : '-'}</td></tr>
                        <tr><td>OBSERVACIÓNES DE DILIGENCIAMIENTO ERRONEO</td><td>${oper ? oper.Observaciones_correctivos : '-'}</td></tr>
                        <tr><td>FECHA REGISTRO OPERACIONES</td><td>${oper ? fechaFormateadaoper : '-'}</td></tr>
                    `;

        infomtto.innerHTML = `
                        <tr><td>COSTO</td><td>${mtto ? formatoCOP(mtto.Costo) : "-"}</td></tr>
                        <tr><td>DAÑO ADICIONAL</td><td>${mtto?.dano_adicional || "-"}</td></tr>
                        <tr><td>OBSERVACIONES</td><td>${mtto?.observaciones || "-"}</td></tr>
                        <tr><td>FECHA REGISTRO MANTENIMIENTO</td><td>${fechaFormateadamtto || "-"}</td></tr>
                    `;

        infosvial.innerHTML = `
                        <tr><td>OBSERVACIONES</td><td>${svial?.Observaciones_svial || "-"}</td></tr>
                        <tr><td>FECHA REGISTRO S. VIAL</td><td>${fechaFormateadasvial || "-"}</td></tr>
                    `;

        // Galería de archivos
        renderGaleria(galeria, data.archivos);

    };




    function cargarModalReparaciones(data) {

        const body = document.getElementById("inforeparacionesBody");
        const galeria = document.getElementById("galeriaAdjuntos_r");

        const registro = data.registro || {};
        const archivos = data.archivos || [];

        const fechaFormateadarep = formatoFechaHora(registro?.Fecha_registro);
        const formatoCOP = v =>
            v ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", minimumFractionDigits: 0 }).format(v) : "-";

        body.innerHTML = `
                <tr><td>FECHA</td><td>${fechaFormateadarep || "-"}</td></tr>
                <tr><td>MÓVIL</td><td>${registro.Movil || "-"}</td></tr>
                <tr><td>COSTO</td><td>${formatoCOP(registro.Costo_intervencion) || "-"}</td></tr>
                <tr><td>ZONA INTERVENIDA</td><td>${registro.Zona_intervenida || "-"}</td></tr>
                <tr><td>PARTE INTERVENIDA</td><td>${registro.Parte_intervenida || "-"}</td></tr>
            `;

        renderGaleria(galeria, data.archivos);
    }

    window.cerrarModalAdjuntos = () => {
        document.getElementById("modalAdjuntos_danos").style.display = "none";
        document.getElementById("modalAdjuntos_reparaciones").style.display = "none";
    }
})