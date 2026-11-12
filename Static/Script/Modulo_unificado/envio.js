// Módulo unificado — Envío de la gestión, cierre del caso y lista de adjuntos seleccionados.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// ACTUALIZAR ESTADO LOCAL TRAS GUARDAR
//======================================================

function actualizarEstadoLocal(id, resultado = {}) {

    const registro = registros.find(r => r.Id == id);
    if (!registro) return;

    let debeOcultarse = false;

    if (["oper", "mtto", "svial"].includes(CFG.propia)) {
        registro["tiene_" + CFG.propia] = true;
        registro.estado_modulo = true;
        if (CFG.propia === "mtto" && typeof resultado.estado_mtto === "boolean") {
            registro.estado_mtto = resultado.estado_mtto ? 1 : 0;
            registro.estado_modulo = resultado.estado_mtto;
            registro.pendiente_ot = Boolean(resultado.pendiente_ot);
        }
        filtrarTabla();
        return;
    }


    if (CFG.propia === "laboral") {
        const revision = document.querySelector("input[name='Revinf']:checked")?.value;
        const pendienteProceso = document.getElementById("estado_caso")?.value?.trim() || "";

        registro.pendiente_proceso_actual = pendienteProceso;
        registro.en_comite = esCasoComite(registro);
        registro.tiene_laboral = true;

        const procesosPendientes = pendienteProceso
          .split(",")
          .map(proceso => proceso.trim().toUpperCase())
          .filter(Boolean);

        if (procesosPendientes.includes("MANTENIMIENTO")) {
            registro.estado_mtto = false;
        }
        if (procesosPendientes.includes("OPERACIONES")) {
            registro.estado_oper = false;
        }
        if (procesosPendientes.includes("SEGURIDAD VIAL")) {
            registro.estado_svial = false;
        }

        if (revision === "SI") {
            registro.caso_cerrado = true;
            registro.en_comite = false;



            // El filtro "Cerrados" debe mostrar inmediatamente el caso
            // que RRLL acaba de cerrar.
            filtrarTabla();
            return;
        }
        filtrarTabla();
        return;
    } else {
        registro["tiene_" + CFG.propia] = true;
        debeOcultarse = true;
    }

    // Ya diligenció su parte
    if (debeOcultarse) {
        registros = registros.filter(r => r.Id != id);
    }

    renderTabla(registros);
}

//======================================================
// SUBMIT GENERAL
//======================================================

async function enviarFormulario() {

    if (CFG.propia === "oper" && envioOperacionesEnCurso) return;

    if (!validarFormulario()) return;

    const formulario = FORM_CONFIG[CFG.propia];
    const endpoint = `/${CFG.modulo}/${formulario.endpoint}`;
    const idGuardado = movilSeleccionado;

    if (CFG.propia === "oper") {
        envioOperacionesEnCurso = true;
        document.getElementById("btnGuardar").disabled = true;
    }

    try {
        const response = await csrfFetch(endpoint, {
            method: "POST",
            body: construirFormData()
        });

        const result = await response.json();

        if (result.status === "success") {
            if (CFG.propia === "oper" && result.bloqueado_reincidencia) {
                reincidenciaBloqueada = true;
                bloqueConciliacion.style.display = "none";
                document.getElementById("btnCerrarCaso")?.style && (document.getElementById("btnCerrarCaso").style.display = "none");
            }
            alert(result.message);
            actualizarEstadoLocal(idGuardado, result);
            cerrarModal();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error(error);
        alert("Error enviando formulario.");
    } finally {
        if (CFG.propia === "oper") {
            envioOperacionesEnCurso = false;
            document.getElementById("btnGuardar").disabled = false;
        }
    }
}

//======================================================
// CERRAR CASO (solo Operaciones, cuando hubo conciliación)
//======================================================

// Envía únicamente la orden de cierre (Id + usuario). Se usa tanto en
// "modo cierre" (la info ya se guardó antes) como al final del flujo
// de guardar+cerrar del formulario nuevo.
async function enviarCierreCaso(idGuardado) {
    const formData = new FormData();
    formData.append("Id_damage_to_fleet", idGuardado);
    formData.append("Usuario_registro_oper", document.body.dataset.usuario);

    const response = await csrfFetch(`/${CFG.modulo}/cerrar_caso_oper`, {
        method: "POST",
        body: formData
    });

    return response.json();
}

//======================================================
// UTILIDADES ADJUNTOS
//======================================================

function actualizarListaAdjuntos() {

    if (!listaAdjuntos) return;
    listaAdjuntos.innerHTML = "";

    adjuntosSeleccionados.forEach((archivo, index) => {

        const div = document.createElement("div");
        div.className = "archivo-item";
        const nombre = document.createElement("span");
        nombre.textContent = archivo.name;
        const botonEliminar = document.createElement("button");
        botonEliminar.type = "button";
        botonEliminar.className = "btn btn-danger btn-sm";
        botonEliminar.textContent = "✕";

        botonEliminar.addEventListener("click", () => {
            adjuntosSeleccionados.splice(index, 1);
            actualizarListaAdjuntos();
        });

        div.append(nombre, botonEliminar);

        listaAdjuntos.appendChild(div);
    });
}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarEnvio() {
    //======================================================
    // EVENTO SUBMIT
    //======================================================

    document.getElementById("formModal").addEventListener("submit", e => {
        e.preventDefault();
        enviarFormulario();
    });

    document.getElementById("btnCerrarCaso")?.addEventListener("click", async () => {

        if (!movilSeleccionado) {
            alert("Seleccione un registro.");
            return;
        }

        const idGuardado = movilSeleccionado;

        // Modo cierre: el caso ya fue guardado antes (reapareció en la
        // bandeja únicamente para cerrarse). Solo se envía la orden de
        // cierre, exactamente como ya funcionaba.
        if (modoCierreActivo) {

            if (!confirm("¿Confirma que desea cerrar este caso? Esta acción no se puede deshacer.")) {
                return;
            }

            try {
                const result = await enviarCierreCaso(idGuardado);

                if (result.status === "success") {
                    alert(result.message);
                    registros = registros.filter(r => r.Id != idGuardado);
                    renderTabla(registros);
                    cerrarModal();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error(error);
                alert("Error cerrando el caso.");
            }
            return;
        }

        // Formulario nuevo: el caso termina en Operaciones (responsabilidad
        // SI + conciliación SI). "Cerrar caso" primero guarda toda la
        // información (igual que "Guardar información", reutilizando el
        // mismo endpoint) y, si el guardado es exitoso, envía la orden de
        // cierre reutilizando la misma lógica del modo cierre.
        if (!validarFormulario()) return;

        if (!confirm("¿Confirma que desea cerrar este caso? Esta acción no se puede deshacer.")) {
            return;
        }

        try {
            const responseGuardar = await csrfFetch(`/${CFG.modulo}/${FORM_CONFIG[CFG.propia].endpoint}`, {
                method: "POST",
                body: construirFormData()
            });

            const resultGuardar = await responseGuardar.json();

            if (resultGuardar.status !== "success") {
                alert(resultGuardar.message);
                return;
            }

            actualizarEstadoLocal(idGuardado, resultGuardar);

            const resultCierre = await enviarCierreCaso(idGuardado);

            if (resultCierre.status === "success") {
                alert(resultCierre.message);
                registros = registros.filter(r => r.Id != idGuardado);
                renderTabla(registros);
            } else {
                alert(resultCierre.message);
            }

            cerrarModal();
        } catch (error) {
            console.error(error);
            alert("Error cerrando el caso.");
        }
    });
}
