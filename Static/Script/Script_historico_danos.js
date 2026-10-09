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

            function iconoCheck(lista) {
                return (lista && lista.length > 0)
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
                <td>${iconoCheck(registro.oper)}</td>   <!-- Archivos adjuntos -->
                <td>${iconoCheck(registro.mtto)}</td>        <!-- Mantenimiento -->
                <td>${iconoCheck(registro.svial)}</td>       <!-- Seguridad vial -->
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


    // ================= MODAL ADJUNTOS =================
    window.mostrarAdjuntos = (id) => {
        const registro = registros.find(r => r.Id == id);
        if (!registro) return;



        document.getElementById("modalAdjuntos").style.display = "block";
        document.getElementById("modal_laboral1").textContent = id;
        movilSeleccionado = id;


        
        // ================= FORMULARIO ADJUNTOS =================
        fetch(`/Historico_danos/detalle/${id}`)
            .then(res => res.json())
            .then(data => {

                    const galeria = document.getElementById("galeriaAdjuntos");
                    const infoBody = document.getElementById("infoEventoBody");
                    const infomtto = document.getElementById("infoEventomtto");
                    const infosvial = document.getElementById("infoEventosvial");
                    const infosoper = document.getElementById("infoEventooper");
                    const infolaboral = document.getElementById("infoEventolaboral");
                    const infocorrecciones = document.getElementById("infoEventocorrecciones");

                    const registroDetalle = data.registro || {};
                    const mtto = data.mtto || null;
                    const svial = data.svial || null;
                    const oper = data.oper || null;
                    const laboral = data.laboral || null;
                    const laboralm = data.laboralm || [];
                    const correcciones = data.correcciones || [];

                    
                    const observacionesHTML = laboralm.length > 0
                        ? laboralm.map(item => `
                            <div>
                                <strong>FECHA REGISTRO:</strong> ${escaparHtml(formatoFechaHora(item.Fecha_registro))}<br>
                                <strong>FECHA PRESENTACIÓN:</strong> ${escaparHtml(formatoFecha(item.Fecha_presentacion) || "-")}<br>
                                <strong>PENDIENTE POR EL PROCESO:</strong> ${escaparHtml(item.Pendiente_proceso || "-")}<br>
                                <strong>OBSERVACIÓN:</strong> ${escaparHtml(item.Observaciones_rrll || "-")}<br>
                                <strong>USUARIO:</strong> ${escaparHtml(item.Usuario_registro_laboral || "-")}
                                <hr>
                            </div>
                        `).join("")
                        : "-";

                    const correccionesHTML = correcciones.length > 0
                        ? correcciones.map(item => `
                            <div>
                                <strong>FECHA REGISTRO:</strong> ${escaparHtml(formatoFechaHora(item.Fecha_Modificacion))}<br>
                                <strong>TABLA AFECTADA:</strong> ${escaparHtml(item.Tabla_afectada || "-")}<br>
                                <strong>CAMPO MODIFICADO:</strong> ${escaparHtml(item.Campo_Modificado || "-")}<br>
                                <strong>VALOR ANTERIOR:</strong> ${escaparHtml(item.Valor_Anterior || "-")}<br>
                                <strong>VALOR NUEVO:</strong> ${escaparHtml(item.Valor_Nuevo || "-")}<br>
                                <strong>USUARIO:</strong> ${escaparHtml(item.Usuario_Modifica || "-")}
                                <hr>
                            </div>
                        `).join("")
                        : "-";
                    

                    // Obtener coordenadas desde la dirección
                    const coords = obtenerCoordsDesdeDireccion(registroDetalle.Direccion);



                    // ================= CARGA DE MAPA =================      
                    if (coords && window.initMapaModal && window.actualizarMapaModal) {
                        window.initMapaModal();
                        window.actualizarMapaModal(coords);
                    }


                    const fechaFormateadasvial = formatoFechaHora(svial?.Fecha_registro);
                    const fechaFormateadalaboral = formatoFechaHora(laboral?.Fecha_registro);
                    const formatoCOP = v =>
                        v ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", minimumFractionDigits: 0 }).format(v) : "-";

                    console.log("FECHA registro:", registro.fecha);
                    console.log("FECHA registroDetalle:", registroDetalle.Fecha_evento);

                    infoBody.innerHTML = `
                        <tr><td>FECHA EVENTO</td><td>${escaparHtml(formatoFechaHora(registroDetalle.Fecha_evento) || "-")}</td></tr>
                        <tr><td>MÓVIL</td><td>${escaparHtml(registroDetalle.Movil || "-")}</td></tr>
                        <tr><td>CÓDIGO</td><td>${escaparHtml(registroDetalle.Codigo || "-")}</td></tr>
                        <tr><td>NOMBRE</td><td>${escaparHtml(registroDetalle.Nombre || "-")}</td></tr>
                        <tr><td>ÁREA</td><td>${escaparHtml(registroDetalle.Area || "-")}</td></tr>
                        <tr><td>RUTA</td><td>${escaparHtml(registroDetalle.Ruta || "-")}</td></tr>
                        <tr><td>VERSIÓN LIBRE</td><td>${escaparHtml(registroDetalle.Version_libre || "-")}</td></tr>
                        <tr><td>ZONA DEL DAÑO</td><td>${escaparHtml(registroDetalle.Zona_dano || "-")}</td></tr>
                        <tr><td>PARTE AFECTADA</td><td>${escaparHtml(registroDetalle.Parte_afectada || "-")}</td></tr>
                        <tr><td>DAÑO OCASIONADO POR</td><td>${escaparHtml(registroDetalle.Dano_ocasionado || "-")}</td></tr>
                        <tr><td>CENTRO OPERACIONAL</td><td>${escaparHtml(registroDetalle.Centro_operaciones || "-")}</td></tr>
                        <tr><td>RESPONSABLE DILIGENCIAMIENTO</td><td>${escaparHtml(registroDetalle.Registrador || "-")}</td></tr>
                        <tr><td>FECHA REGISTRO</td><td>${escaparHtml(registro.fecha_r || "-")}</td></tr>
                        <tr><td>DIRECCIÓN</td><td>${escaparHtml(registroDetalle.Direccion || "-")}</td></tr>
                    `;

                    infosoper.innerHTML = `
                        <tr><td>OBSERVACIÓNES TECNICAS CONTROL OPERACIONAL</td><td>${escaparHtml(oper ? oper.Observaciones_operaciones : '-')}</td></tr>
                        <tr><td>LA INFORMACIÓN CARGADA ES CORRECTA?</td><td>${escaparHtml(oper ? oper.rev_error : '-')}</td></tr>
                        <tr><td>OBSERVACIÓNES DE DILIGENCIAMIENTO ERRONEO</td><td>${escaparHtml(oper ? oper.Observaciones_correctivos : '-')}</td></tr>
                        <tr><td>RESPONSABILIDAD DEL OPERADOR</td><td>${escaparHtml(oper?.responsabilidad_operador || '-')}</td></tr>
                        <tr><td>CONCILIACIÓN</td><td>${escaparHtml(oper?.conciliacion || '-')}</td></tr>
                        <tr><td>COSTO DEL DAÑO</td><td>${escaparHtml(formatoCOP(oper?.costo_oper))}</td></tr>
                        <tr><td>FECHA REGISTRO OPERACIONES</td><td>${escaparHtml(oper?.Fecha_registro ? formatoFechaHora(oper.Fecha_registro) : '-')}</td></tr>
                        <tr><td>USUARIO</td><td>${escaparHtml(oper ? oper.Usuario_registro_oper : '-')}</td></tr>
                    `;

                    infomtto.innerHTML = `
                        <tr><td>COSTO</td><td>${escaparHtml(mtto ? formatoCOP(mtto.Costo) : "-")}</td></tr>
                        <tr><td>DAÑO ADICIONAL</td><td>${escaparHtml(mtto?.dano_adicional || "-")}</td></tr>
                        <tr><td>OBSERVACIONES</td><td>${escaparHtml(mtto?.observaciones || "-")}</td></tr>
                        <tr><td>FECHA REGISTRO COSTO</td><td>${escaparHtml(mtto?.Fecha_registro ? formatoFechaHora(mtto.Fecha_registro) : "-")}</td></tr>
                        <tr><td>USUARIO</td><td>${escaparHtml(mtto?.Usuario_registro_mtto || "-")}</td></tr>
                    `;

                    infosvial.innerHTML = `
                        <tr><td>OBSERVACIONES</td><td>${escaparHtml(svial?.Observaciones_svial || "-")}</td></tr>
                        <tr><td>CONCILIADO A FAVOR DE</td><td>${escaparHtml(svial?.conciliado_a_favor || "-")}</td></tr>
                        <tr><td>VALOR CONCILIADO</td><td>${escaparHtml(formatoCOP(svial?.valor_conciliado_terceros))}</td></tr>
                        <tr><td>FECHA REGISTRO S. VIAL</td><td>${escaparHtml(svial?.Fecha_registro ? formatoFechaHora(svial.Fecha_registro) : "-")}</td></tr>
                        <tr><td>USUARIO</td><td>${escaparHtml(svial?.Usuario_registro_svial || "-")}</td></tr>
                    `;

                    infolaboral.innerHTML = `
                        <tr><td>VALOR CONCILIADO</td><td>${escaparHtml(formatoCOP(laboral?.Valor_conciliado) || "-")}</td></tr>
                        <tr><td>TIPO DE CIERRE:</td><td>${escaparHtml(laboral?.Tipo_cerrado || "-")}</td></tr>
                        <tr><td>FECHA REGISTRO DEBIDO PROCESO</td><td>${escaparHtml(laboral?.Fecha_registro ? formatoFechaHora(laboral.Fecha_registro) : "-")}</td></tr>
                        <tr><td>USUARIO</td><td>${escaparHtml(laboral?.Usuario_registro_labora || "-")}</td></tr>
                        <tr><td>PROCESO</td><td>${observacionesHTML}</td></tr>
                    `;

                    infocorrecciones.innerHTML = `
                        <tr><td>HISTORIAL DE CORRECCIONES</td><td>${correccionesHTML}</td></tr>
                    `;

                    // Galería de archivos
                    galeria.innerHTML = '';
                    const archivos = [
                        ...(data.archivos || []),
                        ...(data.archivos_laboral || []),
                        ...(data.archivos_mtto || []),
                        ...(data.archivos_svial || [])
                    ];

                    if (archivos.length === 0) {
                        galeria.innerHTML = '<p style="text-align:center; color:#777;">Sin archivos adjuntos</p>';
                    } else {
                        archivos.forEach(file => {
                            const div = document.createElement('div');
                            div.classList.add('adjunto-item');

                            const nombreArchivo = String(file.FileName || "Adjunto");
                            const ext = nombreArchivo.includes(".")
                                ? nombreArchivo.split(".").pop().toLowerCase()
                                : "";
                            const url = "/archivo/" + encodeURIComponent(file.Id) + "?tipo=" + encodeURIComponent(file.TipoArchivo);

                            if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
                                const img = document.createElement('img');
                                img.src = url;
                                img.onclick = () => abrirLightbox(url);
                                div.appendChild(img);

                            } else if (['mp4','webm'].includes(ext)) {
                                const video = document.createElement('video');
                                video.src = url;
                                video.controls = true;
                                div.appendChild(video);

                            } else if (['mp3','ogg','wav'].includes(ext)) {
                                const audio = document.createElement('audio');
                                audio.src = url;
                                audio.controls = true;
                                div.appendChild(audio);

                            } else {
                                const link = document.createElement('a');
                                link.href = url;
                                link.download = nombreArchivo;
                                link.rel = 'noopener noreferrer';
                                link.textContent = nombreArchivo;
                                div.appendChild(link);
                            }

                            galeria.appendChild(div);
                        });
                    }

                })
                    .catch(err => {
                    console.error("Error cargando adjuntos:", err);
                    alert("Error cargando la información del evento");
                                    });

    };


    window.cerrarModalAdjuntos = () => {
        document.getElementById("modalAdjuntos").style.display = "none";
    };

})




