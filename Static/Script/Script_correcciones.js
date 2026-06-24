document.addEventListener("DOMContentLoaded", () => {
    // --- Utilidades de Formato ---
    const formatoCOP = v => v ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", minimumFractionDigits: 0 }).format(v) : "-";
    const formatoFechaHora = f => f ? new Date(f).toLocaleString("es-CO") : "-";

    const inputId = document.getElementById("inputIdRegistro");
    const btnCargar = document.getElementById("btnCargarRegistro");
    const formulario = document.getElementById("formularioRegistro");

    // Contenedores HTML
    const infolaboral = document.getElementById("infoEventolaboral");

    let adjuntosOper = [], adjuntosMtto = [], adjuntosSvial = [], adjuntosLaboral = [];

    // --- Gestión de Lista Visual de Archivos ---
    const actualizarListaVisual = (array, contenedorId, prefijoFuncion) => {
            const lista = document.getElementById(contenedorId);
            if (!lista) return;
            lista.innerHTML = "";
            array.forEach((file, index) => {
                const item = document.createElement("div");
                item.style.cssText = "display:flex; justify-content:space-between; background:#f4f4f4; padding:5px; margin-bottom:5px; border-radius:4px; font-size:0.85rem;";
                item.innerHTML = `
                    <span>📄 ${file.name}</span>
                    <button type="button" onclick="${prefijoFuncion}(${index})" style="color:red; border:none; background:none; cursor:pointer;">&times;</button>
                `;
                lista.appendChild(item);
            });
        };

// Funciones de eliminación accesibles globalmente
    window.elimOper = (i) => { adjuntosOper.splice(i, 1); actualizarListaVisual(adjuntosOper, "lista_adjuntos_oper", "elimOper"); };
    window.elimMtto = (i) => { adjuntosMtto.splice(i, 1); actualizarListaVisual(adjuntosMtto, "lista_adjuntos_mtto", "elimMtto"); };
    window.elimSvial = (i) => { adjuntosSvial.splice(i, 1); actualizarListaVisual(adjuntosSvial, "lista_adjuntos_svial", "elimSvial"); };
    window.elimLaboral = (i) => { adjuntosLaboral.splice(i, 1); actualizarListaVisual(adjuntosLaboral, "lista_adjuntos_laboral", "elimLaboral"); };


    
    adjuntosOper.forEach(f => formData.append("archivos_oper", f));   
    adjuntosMtto.forEach(f => formData.append("archivos_mtto", f));    
    adjuntosSvial.forEach(f => formData.append("archivos_svial", f));
    adjuntosLaboral.forEach(f => formData.append("archivos_laboral", f));


    // --- CARGAR REGISTRO ---
    btnCargar.addEventListener("click", () => {
        const id = inputId.value;
        if (!id) return alert("Ingrese un ID");

        fetch(`/Correcciones/detalle/${id}`)
            .then(res => res.json())
            .then(data => {
                if (!data.registro) return alert("No encontrado");

                const { registro, oper = {}, mtto = {}, svial = {}, laboral = {} } = data;
                formulario.style.display = "block";
                adjuntosSeleccionados = [];

                const seccionCompleta = document.getElementById("seccion_Completa");
                const seccionCompleta1 = document.getElementById("seccion_Completa1");
                const seccionCompleta2 = document.getElementById("seccion_Completa2");
                const seccionCompleta3 = document.getElementById("seccion_Completa3");
                const contenedorMtto = document.getElementById("infoEventomtto");
                const contenedorcaptur = document.getElementById("infoEventoBody");
                const contenedoroper = document.getElementById("infoEventooper");
                const contenedorsvial = document.getElementById("infoEventosvial");
                const contenedorlaboral = document.getElementById("infoEventolaboral");
                
                
                if (seccionCompleta) {
                        if (laboral.Cerrado === "SI") {
                            // Escondemos TODA la sección (título, recuadro, etc.)
                            seccionCompleta.style.setProperty("display", "none", "important");
                        } else {
                            // Si no está cerrado, nos aseguramos que sea visible y llenamos
                            seccionCompleta.style.display = "block";
                
                // 1. EVENTO (table_damage_to_fleet)
                contenedorcaptur.innerHTML = `
                    <tr><td>FECHA EVENTO</td><td>${formatoFechaHora(registro.Fecha_evento) || "-"}</td><td><input type="date" name="Fecha_evento" value="${registro.Fecha_evento || ""}"></td></tr>
                    <tr><td>MÓVIL</td><td>${registro.Movil || "-"}</td><td><input type="text" name="Movil" value="${registro.Movil || ""}" data-original="${registro.Movil || ""}"></td></tr>
                    <tr><td>CÓDIGO</td><td>${registro.Codigo || "-"}</td><td><input type="text" name="Codigo" value="${registro.Codigo || ""}" data-original="${registro.Codigo || ""}"></td></tr>
                    <tr><td>NOMBRE</td><td>${registro.Nombre || "-"}</td><td><input type="text" name="Nombre" value="${registro.Nombre || ""}" data-original="${registro.Nombre || ""}"></td></tr>
                    <tr><td>ÁREA</td><td>${registro.Area || "-"}</td><td><input type="text" name="Area" value="${registro.Area || ""}" data-original="${registro.Area || ""}"></td></tr>
                    <tr><td>RUTA</td><td>${registro.Ruta || "-"}</td><td><input type="text" name="Ruta" value="${registro.Ruta || ""}" data-original="${registro.Ruta || ""}"></td></tr>
                    <tr><td>VERSIÓN LIBRE</td><td>${registro.Version_libre || "-"}</td><td><textarea name="Version_libre" data-original="${registro.Version_libre || ""}">${registro.Version_libre || ""}</textarea></td></tr>
                    <tr><td>ZONA DAÑO</td><td>${registro.Zona_dano || "-"}</td><td><input type="text" name="Zona_dano" value="${registro.Zona_dano || ""}" data-original="${registro.Zona_dano || ""}"></td></tr>
                    <tr><td>PARTE AFECTADA</td><td>${registro.Parte_afectada || "-"}</td><td><input type="text" name="Parte_afectada" value="${registro.Parte_afectada || ""}" data-original="${registro.Parte_afectada || ""}"></td></tr>
                    <tr><td>DAÑO OCASIONADO</td><td>${registro.Dano_ocasionado || "-"}</td><td><input type="text" name="Dano_ocasionado" value="${registro.Dano_ocasionado || ""}" data-original="${registro.Dano_ocasionado || ""}"></td></tr>
                    <tr><td>CENTRO OPER.</td><td>${registro.Centro_operaciones || "-"}</td><td><input type="text" name="Centro_operaciones" value="${registro.Centro_operaciones || ""}" data-original="${registro.Centro_operaciones || ""}"></td></tr>
                    <tr><td>DIRECCIÓN</td><td>${registro.Direccion || "-"}</td><td><input type="text" name="Direccion" value="${registro.Direccion || ""}" data-original="${registro.Direccion || ""}"></td></tr>
                    <tr>
                        <td>MULTIMEDIA</td>
                        <td colspan="2">
                            <label for="evidenciaoper" style="background:#444; color:white; padding:5px 10px; border-radius:4px; cursor:pointer; font-size:12px;">+ AGREGAR ARCHIVOS</label>
                            <input type="file" id="evidenciaoper" accept="image/*,video/*" multiple style="display:none;">
                            <div id="lista_adjuntos_oper" style="margin-top:10px; border:1px dashed #ccc; padding:10px;"></div>
                        </td>
                    </tr>

                `;

                const inOper = document.getElementById("evidenciaoper");
                inOper.onchange = () => { 
                    Array.from(inOper.files).forEach(f => adjuntosOper.push(f)); 
                    inOper.value = ""; actualizarListaVisual(adjuntosOper, "lista_adjuntos_oper", "elimOper"); 
                };
                }}



                if (seccionCompleta1) {
                        if (laboral.Cerrado === "SI") {
                            // Escondemos TODA la sección (título, recuadro, etc.)
                            seccionCompleta1.style.setProperty("display", "none", "important");
                        } else {
                            // Si no está cerrado, nos aseguramos que sea visible y llenamos
                            seccionCompleta1.style.display = "block";
                // 2. OPERACIONES (table_info_oper)
                contenedoroper.innerHTML = `
                    <tr><td>OBS. TÉCNICAS</td><td>${oper.Observaciones_operaciones || "-"}</td><td><textarea name="Observaciones_operaciones" data-original="${oper.Observaciones_operaciones || ""}">${oper.Observaciones_operaciones || ""}</textarea></td></tr>
                    <tr><td>REV ERROR</td><td>${oper.rev_error || "-"}</td><td><input type="text" name="rev_error" value="${oper.rev_error || ""}" data-original="${oper.rev_error || ""}"></td></tr>
                    <tr><td>OBS. CORRECTIVOS</td><td>${oper.Observaciones_correctivos || "-"}</td><td><textarea name="Observaciones_correctivos" data-original="${oper.Observaciones_correctivos || ""}">${oper.Observaciones_correctivos || ""}</textarea></td></tr>
                `;
                }}

                if (seccionCompleta2) {
                        if (laboral.Cerrado === "SI") {
                            // Escondemos TODA la sección (título, recuadro, etc.)
                            seccionCompleta2.style.setProperty("display", "none", "important");
                        } else {
                            // Si no está cerrado, nos aseguramos que sea visible y llenamos
                            seccionCompleta2.style.display = "block";
                
                // 3. MANTENIMIENTO (table_info_mtto) + MULTIMEDIA
                contenedorMtto.innerHTML = `
                    <tr><td>COSTO</td><td>${formatoCOP(mtto.Costo)}</td><td><input type="number" name="Costo" value="${mtto.Costo || ""}" data-original="${mtto.Costo || ""}"></td></tr>
                    <tr><td>DAÑO ADICIONAL</td><td>${mtto.dano_adicional || "-"}</td><td><input type="text" name="dano_adicional" value="${mtto.dano_adicional || ""}" data-original="${mtto.dano_adicional || ""}"></td></tr>
                    <tr><td>OBSERVACIONES</td><td>${mtto.observaciones || "-"}</td><td><textarea name="Observaciones_mtto" data-original="${mtto.observaciones || ""}">${mtto.observaciones || ""}</textarea></td></tr>
                    <tr>
                        <td>MULTIMEDIA</td>
                        <td colspan="2">
                            <label for="evidenciaMtto" style="background:#444; color:white; padding:5px 10px; border-radius:4px; cursor:pointer; font-size:12px;">+ AGREGAR ARCHIVOS</label>
                            <input type="file" id="evidenciaMtto" accept="image/*,video/*" multiple style="display:none;">
                            <div id="lista_adjuntos_mtto" style="margin-top:10px; border:1px dashed #ccc; padding:10px;"></div>
                        </td>
                    </tr>
                `;

                // Listener para el input de archivos recién creado
                const inMtto = document.getElementById("evidenciaMtto");
                inMtto.onchange = () => { 
                    Array.from(inMtto.files).forEach(f => adjuntosMtto.push(f)); 
                    inMtto.value = ""; actualizarListaVisual(adjuntosMtto, "lista_adjuntos_mtto", "elimMtto"); 
                };
                }
                }


                if (seccionCompleta3) {
                        if (laboral.Cerrado === "SI") {
                            // Escondemos TODA la sección (título, recuadro, etc.)
                            seccionCompleta3.style.setProperty("display", "none", "important");
                        } else {
                            // Si no está cerrado, nos aseguramos que sea visible y llenamos
                            seccionCompleta3.style.display = "block";                
                // 4. SEGURIDAD VIAL (table_info_svial)
                contenedorsvial.innerHTML = `
                    <tr><td>OBS. SVIAL</td><td>${svial.Observaciones_svial || "-"}</td><td><textarea name="Observaciones_svial" data-original="${svial.Observaciones_svial || ""}">${svial.Observaciones_svial || ""}</textarea></td></tr>
                    <tr>
                        <td>MULTIMEDIA</td>
                        <td colspan="2">
                            <label for="evidenciasvial" style="background:#444; color:white; padding:5px 10px; border-radius:4px; cursor:pointer; font-size:12px;">+ AGREGAR ARCHIVOS</label>
                            <input type="file" id="evidenciasvial" accept="image/*,video/*" multiple style="display:none;">
                            <div id="lista_adjuntos_svial" style="margin-top:10px; border:1px dashed #ccc; padding:10px;"></div>
                        </td>
                    </tr>    
                `;

                const inSvial = document.getElementById("evidenciasvial");
                inSvial.onchange = () => { 
                    Array.from(inSvial.files).forEach(f => adjuntosSvial.push(f)); 
                    inSvial.value = ""; actualizarListaVisual(adjuntosSvial, "lista_adjuntos_svial", "elimSvial"); 
                };
                }}

                if (contenedorlaboral) {
                // 5. LABORAL (table_info_labora)
                infolaboral.innerHTML = `
                    <tr><td>VALOR CONCILIADO</td><td>${formatoCOP(laboral.Valor_conciliado)}</td><td><input type="number" name="Valor_conciliado" value="${laboral.Valor_conciliado || ""}" data-original="${laboral.Valor_conciliado || ""}"></td></tr>
                    <tr><td>CERRADO POR</td><td>${laboral.Tipo_cerrado || "-"}</td><td><input type="text" name="Tipo_cerrado" value="${laboral.Tipo_cerrado || ""}" data-original="${laboral.Tipo_cerrado || ""}"></td></tr>
                    <tr><td>CERRADO</td><td>${laboral.Cerrado || "-"}</td><td><input type="text" name="Cerrado" value="${laboral.Cerrado || ""}" data-original="${laboral.Cerrado || ""}"></td></tr>
                    <tr>
                        <td>MULTIMEDIA</td>
                        <td colspan="2">
                            <label for="evidencialaboral" style="background:#444; color:white; padding:5px 10px; border-radius:4px; cursor:pointer; font-size:12px;">+ AGREGAR ARCHIVOS</label>
                            <input type="file" id="evidencialaboral" accept="image/*,video/*" multiple style="display:none;">
                            <div id="lista_adjuntos_laboral" style="margin-top:10px; border:1px dashed #ccc; padding:10px;"></div>
                        </td>
                    </tr>
                `;

                // Listener Laboral
                const inLaboral = document.getElementById("evidencialaboral");
                inLaboral.onchange = () => { 
                    Array.from(inLaboral.files).forEach(f => adjuntosLaboral.push(f)); 
                    inLaboral.value = ""; actualizarListaVisual(adjuntosLaboral, "lista_adjuntos_laboral", "elimLaboral"); 
                };  
                }              

            });
    });

    // --- GUARDAR CAMBIOS ---
    document.getElementById("btnGuardarCambios").addEventListener("click", () => {
        const id = inputId.value;
        const formData = new FormData();
        let huboCambios = false;

        const campos = formulario.querySelectorAll("input, textarea, select");
        campos.forEach(i => {
            if (i.name && i.type !== "file") {
                const actual = i.value.trim();
                const original = i.getAttribute("data-original") || "";
                if (actual !== original) {
                    formData.append(i.name, actual);
                    huboCambios = true;
                }
            }
        });

        // CAPTURAR ARCHIVOS (Corregido: preguntamos por cada array)
        if (adjuntosOper.length > 0) { 
            adjuntosOper.forEach(f => formData.append("archivos_oper", f)); 
            huboCambios = true; 
        }
        if (adjuntosMtto.length > 0) { 
            adjuntosMtto.forEach(f => formData.append("archivos_mtto", f)); 
            huboCambios = true; 
        }
        if (adjuntosSvial.length > 0) { 
            adjuntosSvial.forEach(f => formData.append("archivos_svial", f)); 
            huboCambios = true; 
        }
        if (adjuntosLaboral.length > 0) { 
            adjuntosLaboral.forEach(f => formData.append("archivos_laboral", f)); 
            huboCambios = true; 
        }

        if (!huboCambios) return alert("No hay cambios para guardar.");

        formData.append("Usuario_registro_mtto", document.body.dataset.usuario);

        fetch(`/Correcciones/modificar/${id}`, { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("✅ Guardado");
                    location.reload();
                } else {
                    alert("❌ Error: " + data.message);
                }
            });
    });
});