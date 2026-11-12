// Módulo unificado — Edición de la información del evento (Operaciones), eliminación y reapertura.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// EDICIÓN DE INFORMACIÓN DEL EVENTO (solo gestionados)
//======================================================

let eventoEdicionActual = null;
let archivosEdicionSeleccionados = [];
let edicionImagenesActiva = false;
let imagenesEdicionEliminar = new Set();
let archivosGaleriaActuales = [];
let guardandoEdicionEvento = false;
// Listas de los catálogos de la base (las arma el servidor en <script id="catalogos-json">).
const CATALOGOS_EVENTO = JSON.parse(document.getElementById("catalogos-json")?.textContent || "{}");
const RUTAS_POR_UF = CATALOGOS_EVENTO.rutas_por_uf || {};
const ZONAS_DANO = CATALOGOS_EVENTO.zonas_dano || [];
const DANOS_OCASIONADOS = CATALOGOS_EVENTO.tipos_dano || [];
const PREFIJOS_MOVIL = CATALOGOS_EVENTO.prefijos_movil || {};

function opcionesSelect(valores, seleccionado) {
    return valores.map(valor => `<option value="${escaparHtml(valor)}" ${String(valor) === String(seleccionado ?? "") ? "selected" : ""}>${escaparHtml(valor)}</option>`).join("");
}

const AREAS_ESPECIALES = CATALOGOS_EVENTO.areas_por_codigo || {};
const AREA_POR_DEFECTO = CATALOGOS_EVENTO.area_por_defecto || "";
const CENTROS_OPERACIONES = CATALOGOS_EVENTO.centros_operacion || [];

function mostrarAccionesEdicion(editando) {
    edicionUbicacionMapaActiva = editando && CFG.propia === "oper";

    const mensajeMapaEdicion = document.getElementById("mensajeMapaEdicion");
    if (mensajeMapaEdicion) {
        mensajeMapaEdicion.style.display = edicionUbicacionMapaActiva ? "block" : "none";
    }
    document.getElementById("seccionMotivoModificacion").style.display = editando ? "block" : "none";

    const casoCerrado = Boolean(eventoEdicionActual?.registro?.caso_cerrado);
    edicionImagenesActiva = Boolean(editando && CFG.propia === "oper" && !casoCerrado);
    if (!edicionImagenesActiva) imagenesEdicionEliminar.clear();
    renderGaleria(archivosGaleriaActuales);

    const botonEditar = document.getElementById("btn_editar_informacion");
    if (botonEditar) {
        botonEditar.style.display = !editando && !casoCerrado ? "inline-block" : "none";
    }

    const botonEliminarEvento = document.getElementById("btn_eliminar_evento");
    if (botonEliminarEvento) {
        botonEliminarEvento.style.display = editando || (!botonEditar && !casoCerrado) ? "inline-block" : "none";
    }

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
    archivosGaleriaActuales = [];
    imagenesEdicionEliminar.clear();
    mostrarAccionesEdicion(false);
}

function actualizarMovilYTipologia() {
    const uf = document.getElementById("evento_uf").value;
    const movil = document.getElementById("evento_movil");
    const prefijo = PREFIJOS_MOVIL[uf] || "";
    const digitos = movil.value.replace(/^[A-Z]\d{2}-/i, "").replace(/\D/g, "").slice(0, 4);
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
    area.value = AREA_POR_DEFECTO;
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
        <tr><td>FECHA EVENTO</td><td><input type="datetime-local" id="evento_fecha" value="${escaparHtml(registro.fecha)}"></td></tr>
        <tr><td>UF</td><td><select id="evento_uf">${opcionesSelect(Object.keys(PREFIJOS_MOVIL), detalle.UF)}</select></td></tr>
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

window.reabrirCaso = async function (id) {
    const motivo = (prompt("Motivo obligatorio de reapertura:") || "").trim();
    if (!motivo) {
        alert("El motivo de reapertura es obligatorio.");
        return;
    }
    if (!confirm("¿Confirma que desea reabrir este caso?")) return;
    const response = await csrfFetch(`/${CFG.modulo}/reabrir_evento/${id}`, {
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


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarEdicionEvento() {
    document.getElementById("btn_guardar_modificacion")?.addEventListener("click", async () => {
        if (!eventoEdicionActual || guardandoEdicionEvento) return;
        const edicionGuardada = eventoEdicionActual;
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
        formData.append("archivos_eliminar", JSON.stringify(Array.from(imagenesEdicionEliminar)));
        const cantidadNuevos = archivosEdicionSeleccionados.length;
        archivosEdicionSeleccionados.forEach(archivo => {
            formData.append("archivos", archivo);
        });
        const botonGuardar = document.getElementById("btn_guardar_modificacion");
        botonGuardar.disabled = true;
        guardandoEdicionEvento = true;
        try {
            const response = await csrfFetch(`/${CFG.modulo}/actualizar_evento/${edicionGuardada.registro.Id}`, {
                method: "POST",
                body: formData
            });
            const resultado = await response.json();
            alert(resultado.message);
            if (resultado.status === "success"){
                const registro = edicionGuardada.registro;
                registro.archivos_count = Math.max(0, Number(registro.archivos_count || 0)
                    + cantidadNuevos - Number(resultado.archivos_eliminados || 0));
                if (eventoEdicionActual !== edicionGuardada) { filtrarTabla(); return; }
                archivosEdicionSeleccionados = [];
                document.getElementById("archivos_edicion").value = "";
                actualizarListaArchivosEdicion();
                mostrarAccionesEdicion(false);
                filtrarTabla();
                cerrarModalAdjuntos();
            }
        } catch (error) {
            console.error("No se pudo guardar la edición del evento.", error);
            alert("No fue posible guardar la información. Inténtelo nuevamente.");
        } finally {
            guardandoEdicionEvento = false;
            botonGuardar.disabled = false;
        }
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
        const motivo = document.getElementById("btn_editar_informacion")
            ? campoMotivo.value.trim()
            : (prompt("Motivo obligatorio de eliminación:") || "").trim();
        if (!motivo) {
            alert("Indique el motivo de la eliminación.");
            return;
        }
        if (!confirm("¿Confirma que desea eliminar este caso? Esta acción no se puede deshacer.")) return;
        const response = await csrfFetch(`/Operaciones/eliminar_evento/${eventoEdicionActual.registro.Id}`, {
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

    document.getElementById("btn_reabrir_evento")?.addEventListener("click", async () => {
        if (!eventoEdicionActual) return;
        const motivo = (prompt("Motivo obligatorio de reapertura:") || "").trim();
        if (!motivo) {
            alert("El motivo de reapertura es obligatorio.");
            return;
        }
        if (!confirm("¿Confirma que desea reabrir este caso?")) return;
        const response = await csrfFetch(`/${CFG.modulo}/reabrir_evento/${eventoEdicionActual.registro.Id}`, {
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
}
