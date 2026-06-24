
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

    window.activarFiltros = function () {
        document.querySelectorAll("thead th input").forEach(input => {
            if (!input.disabled) {
                input.addEventListener("input", filtrarTabla);
                input.addEventListener("change", filtrarTabla);
            }
        });

        const filtroUF = document.getElementById("filtroUF");
        if (filtroUF) {
            filtroUF.addEventListener("change", filtrarTabla);
        }
    };

    // ================= TABLA =================
    function renderTabla(lista) {
        const tbody = document.getElementById("tablaRegistros");
        tbody.innerHTML = "";
        activarFiltros();



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
                <td>
                    <button class="btn btn-success" onclick="abrirModal('${registro.Id}')">Añadir info</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    renderTabla(registros);


    // ================= MODAL ADJUNTOS =================
    window.mostrarAdjuntos = (id) => {
        const registro = registros.find(r => r.Id == id);
        if (!registro) return;

        document.getElementById("modalAdjuntos").style.display = "block";
        document.getElementById("modal_laboral1").textContent = id;
        movilSeleccionado = id;

        
        // ================= FORMULARIO ADJUNTOS =================
        fetch(`/laboral/detalle/${id}`)
            .then(res => res.json())
            .then(data => {


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
                        <tr><td>FECHA REGISTRO OPERACIONES</td><td>${oper?.Fecha_registro ? formatoFechaHora(oper.Fecha_registro) : '-'}</td></tr>
                    `;

                    infomtto.innerHTML = `
                        <tr><td>COSTO</td><td>${mtto ? formatoCOP(mtto.Costo) : "-"}</td></tr>
                        <tr><td>DAÑO ADICIONAL</td><td>${mtto?.dano_adicional || "-"}</td></tr>
                        <tr><td>OBSERVACIONES</td><td>${mtto?.observaciones || "-"}</td></tr>
                        <tr><td>FECHA REGISTRO MANTENIMIENTO</td><td>${mtto?.Fecha_registro ? formatoFechaHora(mtto.Fecha_registro) :"-"}</td></tr>
                    `;

                    infosvial.innerHTML = `
                        <tr><td>OBSERVACIONES</td><td>${svial?.Observaciones_svial || "-"}</td></tr>
                        <tr><td>FECHA REGISTRO S. VIAL</td><td>${svial?.Fecha_registro ? formatoFechaHora(svial.Fecha_registro) : "-"}</td></tr>
                    `;

                    // Galería de archivos
                    galeria.innerHTML = '';
                    const archivos = [
                        ...(data.archivos || []),
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
                            const url = "/laboral/ver_archivo?path=" + encodeURIComponent(file.FilePath);

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

    // ================= MODAL RELACIONES LABORALES =================

    
    // Abrir/cerrar modal
    window.abrirModal = (id) => {
        const modal = document.getElementById("miModal");
        modal.style.display = "block";

        movilSeleccionado = id;
        document.getElementById('modal_laboral').textContent = id;

        inputAdjuntos = document.getElementById("evidencia");
        listaAdjuntos = document.getElementById("lista_adjuntos");

        if (!inputAdjuntos || !listaAdjuntos) {
            console.error("❌ Adjuntos no encontrados");
            return;
        }

        inputAdjuntos.onchange = () => {
            const nuevos = Array.from(inputAdjuntos.files);
            nuevos.forEach(f => adjuntosSeleccionados.push(f));
            inputAdjuntos.value = "";
            actualizarListaAdjuntos();
        };
    };
  
    
        const select_cierre = document.getElementById("Cerrado_input");
        const input_costo = document.getElementById("Costo_id");
        const radiosDaño = document.querySelectorAll('input[name="Revinf"]');
        const form = document.getElementById('miFormulario');
        const details = document.getElementById('estado_details');
        const hidden = document.getElementById('Estado_caso_input');





        // Activar/desactivar textarea según Revinf
        radiosDaño.forEach(radio => {
            radio.addEventListener("change", () => {

                if (radio.value === "NO" && radio.checked) {
                    select_cierre.disabled = true;
                    select_cierre.required = false;
                    select_cierre.value = "";
                    input_costo.disabled = true;
                    input_costo.required = false;
                    input_costo.value = "";
                }

                if (radio.value === "SI" && radio.checked) {
                    select_cierre.disabled = false;
                    select_cierre.required = true;
                    input_costo.disabled = false;
                    input_costo.required = true;
                }
            });
        });

        radiosDaño[0].dispatchEvent(new Event("change"));

        function actualizarEstados() {
                const valores = [...details.querySelectorAll('input[type="checkbox"]:checked')]
                    .map(cb => cb.value);

                hidden.value = valores.join(',');
        }

        // Envío de Formulario

        document.getElementById("formModal").addEventListener("submit", async (event) => {
            event.preventDefault();

            if (!movilSeleccionado) {
                alert("No se ha seleccionado un registro.");
                return;
            }

            const estadosSeleccionados = document.querySelectorAll(
                "#estado_details input[type='checkbox']:checked"
            );

            const valoresSeleccionados = Array.from(estadosSeleccionados)
                .map(cb => cb.value)
                .join(", ");
            document.getElementById("Estado_caso_input").value = valoresSeleccionados;    
            const formData = new FormData();
            formData.append("Id_damage_to_fleet", movilSeleccionado);
            formData.append("Usuario_registro_oper", document.body.dataset.usuario);
            formData.append("observaciones_1", document.getElementById("observaciones_1").value);
            formData.append("Fecha_presentacion_input", document.getElementById("Fecha_presentacion_input").value);
            formData.append("Estado_caso", valoresSeleccionados);
            formData.append("Costo", document.getElementById("Costo_real").value);
            formData.append("Cerrado_input", document.getElementById("Cerrado_input").value);

            
            // Mantener hidden actualizado cuando cambian los checkboxes
            const checkboxes = details.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => cb.addEventListener('change', actualizarEstados));

            // 🔹 Validación de checkboxes
            actualizarEstados(); // actualizar hidden con selección actual
            if (!hidden.value) {
                alert("Debe seleccionar al menos un estado");
                details.open = true;
                details.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }           
                
            
            const Revinf = document.querySelector('input[name="Revinf"]:checked').value;
            formData.append("Revinf", Revinf);

            if (Revinf === "SI") {
                if (!select_cierre.value.trim()) {
                    alert("DEBE INGRESAR EL MOTIVO DE CIERRE.");
                    return;
                }
                formData.append("Costo_id", input_costo.value);
            }

            adjuntosSeleccionados.forEach(file => formData.append("archivos", file));

            try {
                const response = await fetch("/laboral/agregar_laboral", { method: "POST", body: formData });
                const result = await response.json();

                if (result.status === "success") {
                    alert(result.message);
                    // Eliminar fila del DOM
                    document.querySelectorAll("#tablaRegistros tr").forEach(fila => {
                        if (fila.querySelector("td")?.textContent == movilSeleccionado) fila.remove();
                    });
                    // Limpiar modal
                    movilSeleccionado = "";
                    adjuntosSeleccionados = [];
                    actualizarListaAdjuntos();
                    select_cierre.value = "";
                    input_costo.value = "";
                    radiosDaño.forEach(r => r.checked = r.value === "NO");
                    document.getElementById("observaciones_1").value = "";
                    document.getElementById("Fecha_presentacion_input").value = "";
                    // Limpiar checkboxes
                    document.querySelectorAll("#estado_details input[type='checkbox']")
                        .forEach(checkbox => checkbox.checked = false);

                    // Cerrar el desplegable
                    document.getElementById("estado_details").removeAttribute("open");

                    // Limpiar input hidden
                    document.getElementById("Estado_caso_input").value = "";
                    cerrarModal();
                } else {
                    alert("Error: " + result.message);
                }
            } catch (err) {
                console.error(err);
                alert("Ocurrió un error al enviar los datos.");
            }
        });
    });
        

    window.cerrarModal = () => {
        document.getElementById("miModal").style.display = "none";
        movilSeleccionado = "";
        adjuntosSeleccionados = [];
        actualizarListaAdjuntos();
    };




