// Histórico de daños — filtros, exportación, paginación y tabla principal.
// Antes formaba parte de Script_historico_danos.js; el detalle del caso está en detalle.js.

// ================= VARIABLES GLOBALES =================
    let inputAdjuntos = null;
    let listaAdjuntos = null;
    let adjuntosSeleccionados = [];
    let registros = [];
    let movilSeleccionado = "";


document.addEventListener("DOMContentLoaded", () => {
    const escaparHtml = window.escaparHtml;


    const jsonTag = document.getElementById("registros-json");

    if (!jsonTag) {
        console.error("❌ NO existe el script registros-json");
        return;
    }

    const data = JSON.parse(jsonTag.textContent);



    // ================= CARGAR REGISTROS =================
    try {
        const script = document.getElementById("registros-json");
        registros = JSON.parse(script.textContent);
    } catch (e) {
        console.error("❌ Error al parsear registros:", e);
    }



    const casillasEstado = Array.from(document.querySelectorAll('#filtroEstados input[name="estado"]'));
    const casillaTodos = document.getElementById("estadoTodos");

    function estadosSeleccionados() {
        return casillasEstado.filter(casilla => casilla.checked).map(casilla => casilla.value);
    }

    // Las fechas son opcionales: vacías = todos los casos. Solo se valida el orden.
    function fechasValidas() {
        const inicio = document.getElementById("fecha_inicio").value;
        const fin = document.getElementById("fecha_fin").value;
        if (inicio && fin && inicio > fin) {
            alert("La fecha de inicio no puede ser posterior a la fecha de fin.");
            return false;
        }
        return true;
    }

    // Filtros comunes del listado y del Excel: fechas (si hay), UF y estados.
    function parametrosFiltro() {
        const params = new URLSearchParams();
        const inicio = document.getElementById("fecha_inicio").value;
        const fin = document.getElementById("fecha_fin").value;
        if (inicio) params.set("fecha_inicio", inicio);
        if (fin) params.set("fecha_fin", fin);
        params.set("filtro_uf", document.getElementById("filtroUF").value);
        estadosSeleccionados().forEach(estado => params.append("estado", estado));
        return params;
    }

    document.getElementById('btnFiltrar').addEventListener('click', () => {
        if (!fechasValidas()) return;
        aplicarFiltrosDesdeFormulario();
    });

    document.getElementById("btnExportar").addEventListener("click", function() {
        if (!fechasValidas()) return;
        const params = parametrosFiltro();
        // El Excel nunca incluye casos eliminados.
        params.delete("estado");
        const estadosExcel = estadosSeleccionados().filter(estado => estado !== "eliminados");
        if (estadosExcel.length === 0) {
            alert("Los casos eliminados no se incluyen en el Excel. Seleccione Abiertos o Cerrados.");
            return;
        }
        estadosExcel.forEach(estado => params.append("estado", estado));
        window.location.href = `/Historico_danos/exportar_excel?${params.toString()}`;
    });


    const paginacion = JSON.parse(document.getElementById("paginacion-json").textContent);

    function aplicarFiltrosDesdeFormulario(pagina = 1) {
        const params = parametrosFiltro();
        document.querySelectorAll("thead th input[data-filtro]").forEach(input => {
            if (input.value.trim()) params.set(input.dataset.filtro, input.value.trim());
        });
        params.set("pagina", pagina);
        window.location.href = `/Historico_danos/?${params.toString()}`;
    }

    function configurarFiltrosYPaginacion() {
        document.getElementById("filtroUF").addEventListener("change", () => aplicarFiltrosDesdeFormulario());
        casillaTodos.addEventListener("change", () => {
            if (!casillaTodos.checked) {
                // Siempre debe quedar al menos un estado marcado.
                casillaTodos.checked = true;
                return;
            }
            casillasEstado.forEach(casilla => { casilla.checked = true; });
            aplicarFiltrosDesdeFormulario();
        });
        casillasEstado.forEach(casilla => {
            casilla.addEventListener("change", () => {
                if (estadosSeleccionados().length === 0) {
                    casilla.checked = true;
                    return;
                }
                casillaTodos.checked = casillasEstado.every(c => c.checked);
                aplicarFiltrosDesdeFormulario();
            });
        });
        document.querySelectorAll("thead th input[data-filtro]").forEach(input => {
            input.addEventListener("change", () => aplicarFiltrosDesdeFormulario());
            input.addEventListener("keydown", event => {
                if (event.key === "Enter") aplicarFiltrosDesdeFormulario();
            });
        });

        const inicio = paginacion.total_registros ? ((paginacion.pagina - 1) * paginacion.por_pagina) + 1 : 0;
        const fin = Math.min(paginacion.pagina * paginacion.por_pagina, paginacion.total_registros);
        document.getElementById("paginacionInfo").textContent = `${inicio}–${fin} de ${paginacion.total_registros}`;
        document.getElementById("btnPaginaAnterior").disabled = paginacion.pagina <= 1;
        document.getElementById("btnPaginaSiguiente").disabled = fin >= paginacion.total_registros;
        document.getElementById("btnPaginaAnterior").addEventListener("click", () => aplicarFiltrosDesdeFormulario(paginacion.pagina - 1));
        document.getElementById("btnPaginaSiguiente").addEventListener("click", () => aplicarFiltrosDesdeFormulario(paginacion.pagina + 1));
    }

    // ================= TABLA =================
    function renderTabla(lista) {
        const tbody = document.getElementById("tablaRegistros");
        tbody.innerHTML = "";



        lista.forEach(registro => {

            console.log("FECHA PARA FORMATEAR:", registro.fecha);

            const fechaFormateada =
                    window.formatearFechaRegistro(registro.fecha);

            const { duracion, duracionEvento, t } =
                    window.calcularDuracionesRegistro(registro);

            function iconoCheck(tiene) {
                return tiene
                    ? '<span style="color:green;font-weight:bold;">✔</span>'
                    : '<span style="color:red;font-weight:bold;">✖</span>';
            }


            const estadoCaso = registro.eliminado
                ? { texto: "Eliminado", clase: "estado-eliminado" }
                : registro.estado_caso
                    ? { texto: "Cerrado", clase: "estado-cerrado" }
                    : { texto: "Abierto", clase: "estado-abierto" };

            const tr = document.createElement("tr");
            tr.classList.add(t && t.dias >= 2 ? "row-danger" : "row-ok");
            tr.dataset.uf = registro.UF

            tr.innerHTML = `
                <td>${escaparHtml(registro.Id)}</td>
                <td>${escaparHtml(fechaFormateada)}</td>
                <td>${escaparHtml(registro.Movil)}</td>
                <td>${escaparHtml(registro.Codigo)}</td>
                <td>${escaparHtml(registro.Nombre)}</td>
                <td>${escaparHtml(duracion)}</td>
                <td>${escaparHtml(duracionEvento)}</td>
                <td>${iconoCheck(registro.tiene_oper)}</td>   <!-- Operaciones -->
                <td>${iconoCheck(registro.tiene_mtto)}</td>   <!-- Mantenimiento -->
                <td>${iconoCheck(registro.tiene_svial)}</td>  <!-- Seguridad vial -->
                <td>
                    ${
                        registro.archivos_count > 0
                        ? `
                            <button class="btn" data-accion="mostrar-adjuntos" data-id="${escaparHtml(registro.Id)}">
                                Ver archivos (${escaparHtml(registro.archivos_count)})
                            </button>
                        `
                        : `<span style="color:#777;">Sin archivos</span>`
                    }
                </td>
                <td class="estado-caso ${estadoCaso.clase}">${escaparHtml(estadoCaso.texto)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    configurarFiltrosYPaginacion();
    renderTabla(registros);

    document.getElementById("tablaRegistros").addEventListener("click", event => {
        const boton = event.target.closest('[data-accion="mostrar-adjuntos"]');
        if (boton) window.mostrarAdjuntos(boton.dataset.id);
    });


    // Modal del detalle y de adjuntos (window.mostrarAdjuntos / cerrarModalAdjuntos): ver detalle.js.
    registrarDetalleHistorico();

})
