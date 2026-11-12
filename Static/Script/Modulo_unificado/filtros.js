// Módulo unificado — Carga de registros, filtros de la tabla y columnas visibles.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

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
        const enComite = CFG.propia === "laboral" && esCasoComite(registro);

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

        if (filtroEstado === "pendientes") {
            if (enComite) return false;
            if (registro.caso_cerrado) return false;
            if (CFG.propia === "mtto") {
                if (registro.tiene_mtto) return false;
            } else if (CFG.propia === "laboral"
                ? String(registro.pendiente_proceso_actual ?? "").trim().toUpperCase() === "COMPLETO"
                : registro.estado_modulo) {
                return false;
            }
        }

        if (filtroEstado === "gestionados" && (
            registro.caso_cerrado || (CFG.propia === "laboral"
            ? String(registro.pendiente_proceso_actual ?? "").trim().toUpperCase() !== "COMPLETO"
            : !registro.estado_modulo)
        )) return false;

        if (filtroEstado === "pendiente_ot" && (
            CFG.propia !== "mtto" ||
            !registro.tiene_mtto ||
            !registro.pendiente_ot ||
            registro.caso_cerrado
        )) return false;

        if (filtroEstado === "comite" && !enComite) return false;

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


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarFiltros() {
    //======================================================
    // CARGAR REGISTROS
    //======================================================

    try {
        const script = document.getElementById("registros-json");
        registros = JSON.parse(script.textContent);
        console.log("REGISTROS RRLL:", registros.map(r => ({
            Id: r.Id,
            estado_caso: r.estado_caso,
            estado_oper: r.estado_oper,
            estado_mtto: r.estado_mtto,
            estado_svial: r.estado_svial,
            pendiente_proceso_actual: r.pendiente_proceso_actual,
            caso_cerrado: r.caso_cerrado,
            cerrado_por_laboral: r.cerrado_por_laboral,
            tiene_ot: r.tiene_ot,
            requiere_laboral: r.requiere_laboral
        })));
    } catch (error) {
        console.error(error);
    }

    aplicarVisibilidadColumnas();
}
