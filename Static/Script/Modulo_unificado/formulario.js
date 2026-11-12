// Módulo unificado — Modal de gestión: modo de cierre, precarga, apertura, cierre y limpieza del formulario.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// MODAL FORMULARIO ("Añadir info" de la sección propia)
//======================================================

// Para Operaciones, si el registro llega a la bandeja con tiene_oper
// ya en true, solo puede ser porque el caso termina en Operaciones
// (conciliación = 'SI' o responsabilidad = 'NO APLICA') y todavía no
// se ha cerrado -- el backend solo devuelve esos casos en la bandeja
// de Operaciones (ver FILTRO_PENDIENTE_MODULO). En ese escenario el
// formulario se precarga con lo ya guardado, para que el usuario
// pueda seguir usando "Guardar información" o pasar a "Cerrar caso".
function esModoCierreOperaciones(id) {
    if (CFG.propia !== "oper") return false;
    const registro = registros.find(r => r.Id == id);
    return !!(registro && registro.tiene_oper);
}

// Recuerda si el caso ya estaba guardado al abrir el modal (reabierto
// únicamente para poder cerrarse), para que "Cerrar caso" solo envíe
// la orden de cierre en vez de repetir el guardado.
let modoCierreActivo = false;
let envioOperacionesEnCurso = false;
let reincidenciaBloqueada = false;
let modoCorreccionGestion = false;

function configurarModoOperaciones(modoCierre) {
    if (CFG.propia !== "oper") return;
    modoCierreActivo = modoCierre;
}

// Precarga en el formulario la información que Operaciones ya había
// guardado, sin ocultar ni bloquear nada -- el usuario puede seguir
// editando y usando "Guardar información" o "Cerrar caso" con
// normalidad.
async function precargarFormularioOperaciones(id) {
    try {
        const resp = await fetch(`/${CFG.modulo}/detalle/${id}`);
        const data = await resp.json();

        const oper = data.oper ?? {};
        const mtto = data.mtto ?? {};
        const laboral = data.laboral?.estado ?? {};

        document.getElementById("campo_principal").value = oper.Observaciones_operaciones ?? "";
        document.getElementById("observaciones").value = oper.Observaciones_correctivos ?? "";

        document.querySelectorAll("input[name='Revinf']").forEach(r => {
            r.checked = r.value === (oper.rev_error ?? "SI");
        });

        // Se conserva la respuesta ya guardada. Un costo vacío en
        // table_info_oper representa el camino que supera el límite,
        // porque solo se almacena costo_oper cuando no lo supera.
        const noSupera = oper.CostoDelDanoOper != null;
        document.querySelectorAll("input[name='CostoSupera2M']").forEach(r => {
            r.checked = r.value === (noSupera ? "NO" : "SI");
        });
        bloqueCostoDano.style.display = noSupera ? "block" : "none";
        bloqueResponsabilidad.style.display = noSupera ? "block" : "none";

        if (noSupera) {
            costoDanoDisplay.value = new Intl.NumberFormat("es-CO").format(Number(oper.CostoDelDanoOper));
            costoDanoHidden.value = oper.CostoDelDanoOper;
            document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => {
                r.checked = r.value === oper.responsabilidad_operador;
            });
        } else {
            document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => {
                r.checked = false;
            });
            document.querySelectorAll("input[name='Conciliacion']").forEach(r => {
                r.checked = false;
            });
        }

        if (noSupera && oper.responsabilidad_operador === "NO APLICA") {
            bloqueValorConciliadoOper.style.display = "block";
            document.getElementById("lblValorConciliadoOper").textContent =
                "VALOR CONCILIADO CON TERCEROS";
            bloqueMotivoCierreOper.style.display = "block";
            motivoCierreOper.required = true;
            motivoCierreOper.value = laboral.Tipo_cerrado ?? "";

            if (laboral.Valor_conciliado != null) {
                valorConciliadoOperDisplay.value =
                    new Intl.NumberFormat("es-CO").format(Number(laboral.Valor_conciliado));
                valorConciliadoOperHidden.value = laboral.Valor_conciliado;
            }
        }

        if (noSupera && oper.responsabilidad_operador === "SI" && oper.conciliacion === "SI") {
            bloqueConciliacion.style.display = "block";

            document.querySelectorAll("input[name='Conciliacion']").forEach(r => {
                r.checked = r.value === "SI";
            });

            bloqueValorConciliadoOper.style.display = "block";

            if (laboral.Valor_conciliado != null) {
                valorConciliadoOperDisplay.value =
                    new Intl.NumberFormat("es-CO").format(Number(laboral.Valor_conciliado));
                valorConciliadoOperHidden.value = laboral.Valor_conciliado;
            }
        }

        actualizarVisibilidadCerrarCaso();
    } catch (error) {
        console.error("No se pudo precargar la información previa del caso:", error);
    }
}

async function precargarFormularioGestion(id) {
    if (CFG.propia === "oper") return precargarFormularioOperaciones(id);
    try {
        const resp = await fetch(`/${CFG.modulo}/detalle/${id}`);
        const data = await resp.json();
        if (CFG.propia === "mtto") {
            const mtto = data.mtto ?? {};
            const costo = mtto.Costo ?? "";
            document.getElementById("campo_principal").value = costo;
            document.getElementById("campo_principal_costo_display").value = costo
                ? new Intl.NumberFormat("es-CO").format(Number(costo)) : "";
            document.getElementById("observaciones").value = mtto.observaciones ?? "";
            document.querySelectorAll("input[name='DanoAdicional']").forEach(r => {
                r.checked = r.value === (mtto.dano_adicional ?? "NO");
            });
        }
        if (CFG.propia === "svial") {
            const svial = data.svial ?? {};
            document.getElementById("campo_principal").value = svial.Observaciones_svial ?? "";
        }
        if (CFG.propia === "laboral") {
            const laboral = data.laboral?.estado ?? {};
            document.getElementById("campo_principal").value = laboral.Observaciones_rrll ?? "";
        }
    } catch (error) {
        console.error("No se pudo precargar la gestión:", error);
    }
}

window.abrirModal = function (id) {

    reincidenciaBloqueada = false;
    movilSeleccionado = id;
    document.getElementById("modal_registro").textContent = id;
    document.getElementById("miModal").style.display = "block";

    const modoCierre = esModoCierreOperaciones(id);
    configurarModoOperaciones(modoCierre);

    const registro = registros.find(r => r.Id == id);
    modoCorreccionGestion = !!registro && !registro.caso_cerrado && (
        CFG.propia === "oper" ? registro.tiene_oper :
            CFG.propia === "laboral" ? registro.tiene_laboral
            : CFG.propia === "mtto"
            ? (registro.estado_modulo || registro.pendiente_ot)
            : registro.estado_modulo
    );
    document.getElementById("bloqueMotivoGestion").style.display = modoCorreccionGestion ? "block" : "none";
    const motivoGestion = document.getElementById("motivo_gestion");
    motivoGestion.value = "";
    motivoGestion.required = modoCorreccionGestion;

    if (modoCorreccionGestion) {
        precargarFormularioGestion(id);
    }

    if (CFG.propia === "svial") {
        configurarConciliacionTercerosSvial(id);
    }

    inputAdjuntos = document.getElementById("evidencia");
    listaAdjuntos = document.getElementById("lista_adjuntos");

    inputAdjuntos.value = "";
    adjuntosSeleccionados = [];
    actualizarListaAdjuntos();

    inputAdjuntos.onchange = () => {
        const nuevos = [...inputAdjuntos.files];
        nuevos.forEach(a => adjuntosSeleccionados.push(a));
        inputAdjuntos.value = "";
        actualizarListaAdjuntos();
    };
};

window.cerrarModal = function () {
    document.getElementById("miModal").style.display = "none";
    movilSeleccionado = "";
    adjuntosSeleccionados = [];
    actualizarListaAdjuntos();
    modoCorreccionGestion = false;
    document.getElementById("motivo_gestion").required = false;
    limpiarFormulario();
};

//======================================================
// LIMPIAR FORMULARIO
//======================================================

function limpiarFormulario() {
    document.getElementById("campo_principal").value = "";
    document.getElementById("campo_principal_costo_display").value = "";
    document.getElementById("observaciones").value = "";
    document.getElementById("observaciones").disabled = CFG.propia !== "mtto";
    document.getElementById("observaciones").required = false;

    document.querySelectorAll("input[name='DanoAdicional']").forEach(r => {
        r.checked = r.value === "NO";
    });

    if (CFG.propia === "mtto") {
        actualizarObservacionesPorDanoAdicional();
    }

    if (CFG.propia === "oper") {
        document.querySelectorAll("input[name='CostoSupera2M']").forEach(r => r.checked = false);
        document.getElementById("costo_dano_display").value = "";
        document.getElementById("costo_dano").value = "";
        document.getElementById("bloqueCostoDano").style.display = "none";
        document.getElementById("bloqueResponsabilidad").style.display = "none";
        document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => r.checked = false);
        document.querySelectorAll("input[name='Conciliacion']").forEach(r => r.checked = false);
        document.getElementById("mensajeReincidencia").style.display = "none";
        document.getElementById("mensajeReincidencia").textContent = "";
        document.getElementById("bloqueConciliacion").style.display = "none";
        document.getElementById("bloqueValorConciliadoOper").style.display = "none";
        document.getElementById("bloqueMotivoCierreOper").style.display = "none";
        document.getElementById("valor_conciliado_oper_display").value = "";
        document.getElementById("valor_conciliado_oper").value = "";
        document.getElementById("motivo_cierre_oper").value = "";
        document.getElementById("motivo_cierre_oper").required = false;
        const msgCosto = document.getElementById("msgCostoDano");
        if (msgCosto) { msgCosto.style.display = "none"; msgCosto.textContent = ""; }
    }

    const fp = document.getElementById("fecha_presentacion");
    if (fp) fp.value = "";

    if (estadoCasoOpciones) {
        estadoCasoOpciones.querySelectorAll("input[type='checkbox']").forEach(cb => {
            cb.checked = false;
        });
        estadoCasoOpciones.classList.remove("abierto");
        sincronizarEstadoCaso();
    }

    const mc = document.getElementById("motivo_cierre");
    const vc = document.getElementById("valor_conciliado");
    const vcDisplay = document.getElementById("valor_conciliado_display");
    if (mc) { mc.value = ""; mc.disabled = true; }
    if (vc) { vc.value = ""; }
    if (vcDisplay) { vcDisplay.value = ""; vcDisplay.disabled = true; }

    if (CFG.propia === "svial") {
        resetConciliacionTercerosSvial();
    }

    // RRLL arranca en "NO" (caso no cerrado)
    const defaultRevinf = CFG.propia === "laboral" ? "NO" : "SI";
    document.querySelectorAll("input[name='Revinf']").forEach(r => {
        r.checked = r.value === defaultRevinf;
    });
}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarFormulario() {
    // Esta parte no tiene acciones de arranque.
}
