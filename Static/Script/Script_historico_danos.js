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



    // ================= CARGAR REGISTROS =================
    try {
        const script = document.getElementById("registros-json");
        registros = JSON.parse(script.textContent);
    } catch (e) {
        console.error("❌ Error al parsear registros:", e);
    }



    document.getElementById('btnFiltrar').addEventListener('click', () => {
        const fecha_inicio = document.getElementById('fecha_inicio').value;
        const fecha_fin = document.getElementById('fecha_fin').value;

        if(!fecha_inicio || !fecha_fin){
            alert("Por favor seleccione ambas fechas.");
            return;
        }

        const start = new Date(fecha_inicio);
        const end = new Date(fecha_fin);
        const diffMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
        if(diffMonths > 2 || diffMonths < 0){
            alert("El rango de fechas no puede superar 2 meses.");
            return;
        }

        aplicarFiltrosDesdeFormulario();
    });

    document.getElementById("btnExportar").addEventListener("click", function() {
        const fechaInicio = document.getElementById("fecha_inicio").value;
        const fechaFin = document.getElementById("fecha_fin").value;

        if(!fechaInicio || !fechaFin){
            alert("Por favor seleccione ambas fechas.");
            return;
        }

        const start = new Date(fechaInicio);
        const end = new Date(fechaFin);
        const diffMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
        if(diffMonths > 2 || diffMonths < 0){
            alert("El rango de fechas no puede superar 2 meses.");
            return;
        }

        const filtroEstado = document.getElementById("filtroEstado").value;
        window.location.href = `/Historico_danos/exportar_excel?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}&filtro_estado=${encodeURIComponent(filtroEstado)}`;
    });


    const paginacion = JSON.parse(document.getElementById("paginacion-json").textContent);

    function aplicarFiltrosDesdeFormulario(pagina = 1) {
        const params = new URLSearchParams();
        params.set("fecha_inicio", document.getElementById("fecha_inicio").value);
        params.set("fecha_fin", document.getElementById("fecha_fin").value);
        params.set("filtro_uf", document.getElementById("filtroUF").value);
        params.set("filtro_estado", document.getElementById("filtroEstado").value);
        document.querySelectorAll("thead th input[data-filtro]").forEach(input => {
            if (input.value.trim()) params.set(input.dataset.filtro, input.value.trim());
        });
        params.set("pagina", pagina);
        window.location.href = `/Historico_danos/?${params.toString()}`;
    }

    function configurarFiltrosYPaginacion() {
        document.getElementById("filtroUF").addEventListener("change", () => aplicarFiltrosDesdeFormulario());
        document.getElementById("filtroEstado").addEventListener("change", () => aplicarFiltrosDesdeFormulario());
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

            const fechaFormateada =
                    window.formatearFechaRegistro(registro.fecha);

            const { duracion, duracionEvento, t } =
                    window.calcularDuracionesRegistro(registro);

            function iconoCheck(lista) {
                return (lista && lista.length > 0)
                    ? '<span style="color:green;font-weight:bold;">✔</span>'
                    : '<span style="color:red;font-weight:bold;">✖</span>';
            }


            const tr = document.createElement("tr");
            tr.classList.add(t && t.dias >= 2 ? "row-danger" : "row-ok");
            tr.dataset.uf = registro.UF

            tr.innerHTML = `
                <td>${registro.Id}</td>
                <td>${fechaFormateada}</td>
                <td>${registro.Movil}</td>
                <td>${registro.Codigo}</td>
                <td>${registro.Nombre}</td>
                <td>${duracion}</td>
                <td>${duracionEvento}</td>
                <td>${iconoCheck(registro.oper)}</td>   <!-- Archivos adjuntos -->
                <td>${iconoCheck(registro.mtto)}</td>        <!-- Mantenimiento -->
                <td>${iconoCheck(registro.svial)}</td>       <!-- Seguridad vial -->
                <td>
                    ${
                        registro.archivos_count > 0
                        ? `
                            <button class="btn" onclick="mostrarAdjuntos('${registro.Id}')">
                                Ver archivos (${registro.archivos_count})
                            </button>
                        `
                        : `<span style="color:#777;">Sin archivos</span>`
                    }
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    configurarFiltrosYPaginacion();
    renderTabla(registros);


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
                                <strong>FECHA REGISTRO:</strong> ${formatoFechaHora(item.Fecha_registro)}<br>
                                <strong>FECHA PRESENTACIÓN:</strong> ${formatoFecha(item.Fecha_presentacion) || "-"}<br>
                                <strong>PENDIENTE POR EL PROCESO:</strong> ${item.Pendiente_proceso || "-"}<br>                                
                                <strong>OBSERVACIÓN:</strong> ${item.Observaciones_rrll || "-"}<br>
                                <strong>USUARIO:</strong> ${item.Usuario_registro_laboral || "-"}
                                <hr>
                            </div>
                        `).join("")
                        : "-";

                    const correccionesHTML = correcciones.length > 0
                        ? correcciones.map(item => `
                            <div>
                                <strong>FECHA REGISTRO:</strong> ${formatoFechaHora(item.Fecha_Modificacion)}<br>
                                <strong>TABLA AFECTADA:</strong> ${item.Tabla_afectada || "-"}<br>
                                <strong>CAMPO MODIFICADO:</strong> ${item.Campo_Modificado || "-"}<br>
                                <strong>VALOR ANTERIOR:</strong> ${item.Valor_Anterior || "-"}<br>
                                <strong>VALOR NUEVO:</strong> ${item.Valor_Nuevo || "-"}<br>
                                <strong>USUARIO:</strong> ${item.Usuario_Modifica || "-"}
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

                    infoBody.innerHTML = `
                        <tr><td>FECHA EVENTO</td><td>${registro.fecha || "-"}</td></tr>
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
                        <tr><td>FECHA REGISTRO</td><td>${registro.fecha_r || "-"}</td></tr>
                        <tr><td>DIRECCIÓN</td><td>${registroDetalle.Direccion || "-"}</td></tr>
                    `;

                    infosoper.innerHTML = `
                        <tr><td>OBSERVACIÓNES TECNICAS CONTROL OPERACIONAL</td><td>${oper ? oper.Observaciones_operaciones : '-'}</td></tr>
                        <tr><td>LA INFORMACIÓN CARGADA ES CORRECTA?</td><td>${oper ? oper.rev_error : '-'}</td></tr>
                        <tr><td>OBSERVACIÓNES DE DILIGENCIAMIENTO ERRONEO</td><td>${oper ? oper.Observaciones_correctivos : '-'}</td></tr>
                        <tr><td>RESPONSABILIDAD DEL OPERADOR</td><td>${oper?.responsabilidad_operador || '-'}</td></tr>
                        <tr><td>CONCILIACIÓN</td><td>${oper?.conciliacion || '-'}</td></tr>
                        <tr><td>COSTO DEL DAÑO</td><td>${formatoCOP(oper?.costo_oper)}</td></tr>
                        <tr><td>FECHA REGISTRO OPERACIONES</td><td>${ oper?.Fecha_registro ? formatoFechaHora(oper.Fecha_registro) : '-'}</td></tr>
                        <tr><td>USUARIO</td><td>${ oper ? oper.Usuario_registro_oper : '-'}</td></tr>
                    `;

                    infomtto.innerHTML = `
                        <tr><td>COSTO</td><td>${mtto ? formatoCOP(mtto.Costo) : "-"}</td></tr>
                        <tr><td>DAÑO ADICIONAL</td><td>${mtto?.dano_adicional || "-"}</td></tr>
                        <tr><td>OBSERVACIONES</td><td>${mtto?.observaciones || "-"}</td></tr>
                        <tr><td>FECHA REGISTRO COSTO</td><td>${ mtto?.Fecha_registro ? formatoFechaHora(mtto.Fecha_registro) : "-"}</td></tr>
                        <tr><td>USUARIO</td><td>${mtto?.Usuario_registro_mtto || "-"}</td></tr>
                    `;

                    infosvial.innerHTML = `
                        <tr><td>OBSERVACIONES</td><td>${svial?.Observaciones_svial || "-"}</td></tr>
                        <tr><td>CONCILIADO A FAVOR DE</td><td>${svial?.conciliado_a_favor || "-"}</td></tr>
                        <tr><td>VALOR CONCILIADO</td><td>${formatoCOP(svial?.valor_conciliado_terceros)}</td></tr>
                        <tr><td>FECHA REGISTRO S. VIAL</td><td>${svial?.Fecha_registro ? formatoFechaHora(svial.Fecha_registro) : "-"}</td></tr>
                        <tr><td>USUARIO</td><td>${svial?.Usuario_registro_svial || "-"}</td></tr>
                    `;

                    infolaboral.innerHTML = `
                        <tr><td>VALOR CONCILIADO</td><td>${formatoCOP(laboral?.Valor_conciliado) || "-"}</td></tr>
                        <tr><td>TIPO DE CIERRE:</td><td>${laboral?.Tipo_cerrado || "-"}</td></tr>
                        <tr><td>FECHA REGISTRO DEBIDO PROCESO</td><td>${ laboral?.Fecha_registro ? formatoFechaHora(laboral.Fecha_registro) : "-"}</td></tr>
                        <tr><td>USUARIO</td><td>${laboral?.Usuario_registro_labora || "-"}</td></tr>
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

                            const ext = file.FileName.split('.').pop().toLowerCase();
                            const url = "/Historico_danos/ver_archivo?path=" + encodeURIComponent(file.FilePath);

                            if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
                                const img = document.createElement('img');
                                img.src = url;
                                img.onclick = () => abrirLightbox(url);
                                div.appendChild(img);

                            } else if (['mp4','mov','avi','webm'].includes(ext)) {
                                const video = document.createElement('video');
                                video.src = url;
                                video.controls = true;
                                div.appendChild(video);

                            } else {
                                const link = document.createElement('a');
                                link.href = url;
                                link.target = '_blank';
                                link.textContent = file.FileName;
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




