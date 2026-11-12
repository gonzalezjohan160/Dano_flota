// Módulo unificado — Flujo de Operaciones: costo del daño, responsabilidad, reincidencia y conciliación.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// NUEVO FLUJO DE OPERACIONES
// (¿costo > $2.000.000? / responsabilidad / reincidencia / conciliación)
//======================================================

const costoDanoDisplay = document.getElementById("costo_dano_display");
const costoDanoHidden = document.getElementById("costo_dano");
const bloqueCostoDano = document.getElementById("bloqueCostoDano");
const bloqueResponsabilidad = document.getElementById("bloqueResponsabilidad");
const mensajeReincidencia = document.getElementById("mensajeReincidencia");
const bloqueConciliacion = document.getElementById("bloqueConciliacion");
const msgCostoDano = document.getElementById("msgCostoDano");
const bloqueValorConciliadoOper = document.getElementById("bloqueValorConciliadoOper");
const valorConciliadoOperDisplay = document.getElementById("valor_conciliado_oper_display");
const valorConciliadoOperHidden = document.getElementById("valor_conciliado_oper");
const bloqueMotivoCierreOper = document.getElementById("bloqueMotivoCierreOper");
const motivoCierreOper = document.getElementById("motivo_cierre_oper");
const bloqueConciliacionTercerosSvial = document.getElementById("bloqueConciliadoFavor");
const conciliadoAFavor = document.getElementById("conciliado_a_favor");
const valorConciliadoTercerosSvial = document.getElementById("valor_conciliado_terceros");

// Límite máximo permitido para "Costo del daño"
const LIMITE_COSTO_DANO = 2000000;

function resetConciliacionTercerosSvial() {
    if (!bloqueConciliacionTercerosSvial) return;
    bloqueConciliacionTercerosSvial.style.display = CFG.propia === "svial" ? "block" : "none";
    conciliadoAFavor.value = "";
    valorConciliadoTercerosSvial.value = "";
    valorConciliadoTercerosSvial.disabled = true;
}

function actualizarValorConciliadoTercerosSvial() {
    const haySeleccion = !!conciliadoAFavor.value;
    valorConciliadoTercerosSvial.disabled = !haySeleccion;
    if (!haySeleccion) valorConciliadoTercerosSvial.value = "";
}

async function configurarConciliacionTercerosSvial(id) {
    resetConciliacionTercerosSvial();
}

function resetResponsabilidadYConciliacion() {
    reincidenciaBloqueada = false;
    document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(r => r.checked = false);
    document.querySelectorAll("input[name='Conciliacion']").forEach(r => r.checked = false);
    mensajeReincidencia.style.display = "none";
    mensajeReincidencia.textContent = "";
    bloqueConciliacion.style.display = "none";
    bloqueValorConciliadoOper.style.display = "none";
    bloqueMotivoCierreOper.style.display = "none";
    valorConciliadoOperDisplay.value = "";
    valorConciliadoOperHidden.value = "";
    motivoCierreOper.value = "";
    motivoCierreOper.required = false;
    actualizarVisibilidadCerrarCaso();
}

// Muestra/oculta "Cerrar caso" en tiempo real, únicamente cuando el
// flujo actual del formulario termina en Operaciones: responsabilidad
// = SI y conciliación = SI, o responsabilidad = NO APLICA. En
// cualquier otro caso el botón permanece oculto y solo existe
// "Guardar información".
function actualizarVisibilidadCerrarCaso() {
    // Operaciones ya no tiene cierre manual: el cierre es automático
    // cuando finalizan las tres gestiones requeridas.
    return;

    if (reincidenciaBloqueada) {
        document.getElementById("btnCerrarCaso")?.style && (document.getElementById("btnCerrarCaso").style.display = "none");
        return;
    }

    const responsabilidad = document.querySelector("input[name='ResponsabilidadOperador']:checked");
    const conciliacion = document.querySelector("input[name='Conciliacion']:checked");

    const terminaEnOperaciones =
        (responsabilidad?.value === "SI" && conciliacion?.value === "SI") ||
        responsabilidad?.value === "NO APLICA";

    const btnCerrarCaso = document.getElementById("btnCerrarCaso");
    if (btnCerrarCaso) {
        btnCerrarCaso.style.display = terminaEnOperaciones ? "inline-block" : "none";
    }
}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarFlujoOperaciones() {
    // Formato de miles para "Costo del daño" + validación en tiempo real
    // (si supera el límite, se bloquea el guardado desde validarFormulario)
    if (costoDanoDisplay && costoDanoHidden) {
        costoDanoDisplay.addEventListener("input", () => {
            const soloDigitos = costoDanoDisplay.value.replace(/\D/g, "");
            costoDanoDisplay.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";
            costoDanoHidden.value = soloDigitos;

            const superaLimite = Number(soloDigitos || 0) > LIMITE_COSTO_DANO;
            if (msgCostoDano) {
                msgCostoDano.textContent = superaLimite
                    ? "Valor supera el monto máximo permitido de $2.000.000"
                    : "";
                msgCostoDano.style.display = superaLimite ? "block" : "none";
            }
        });
    }

    // Formato de miles para "Valor conciliado" (mismo patrón que "Costo del daño")
    if (valorConciliadoOperDisplay && valorConciliadoOperHidden) {
        valorConciliadoOperDisplay.addEventListener("input", () => {
            const soloDigitos = valorConciliadoOperDisplay.value.replace(/\D/g, "");
            valorConciliadoOperDisplay.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";
            valorConciliadoOperHidden.value = soloDigitos;
        });
    }

    if (conciliadoAFavor && valorConciliadoTercerosSvial) {
        conciliadoAFavor.addEventListener("change", actualizarValorConciliadoTercerosSvial);
        valorConciliadoTercerosSvial.addEventListener("input", () => {
            const soloDigitos = valorConciliadoTercerosSvial.value.replace(/\D/g, "");
            valorConciliadoTercerosSvial.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";
        });
    }

    // Pregunta 1: ¿el costo del daño supera $2.000.000?
    document.querySelectorAll("input[name='CostoSupera2M']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            const superaValor = radio.value === "SI";

            bloqueCostoDano.style.display = superaValor ? "none" : "block";
            bloqueResponsabilidad.style.display = superaValor ? "none" : "block";

            if (superaValor) {
                costoDanoDisplay.value = "";
                costoDanoHidden.value = "";
                if (msgCostoDano) {
                    msgCostoDano.style.display = "none";
                    msgCostoDano.textContent = "";
                }
            }

            resetResponsabilidadYConciliacion();
        });
    });

    // Pregunta: ¿operador acepta la responsabilidad?
    document.querySelectorAll("input[name='ResponsabilidadOperador']").forEach(radio => {
        radio.addEventListener("change", async () => {
            if (!radio.checked) return;

            reincidenciaBloqueada = false;
            mensajeReincidencia.style.display = "none";
            mensajeReincidencia.textContent = "";
            bloqueConciliacion.style.display = "none";
            bloqueValorConciliadoOper.style.display = "none";
            bloqueMotivoCierreOper.style.display = "none";
            valorConciliadoOperDisplay.value = "";
            valorConciliadoOperHidden.value = "";
            motivoCierreOper.value = "";
            motivoCierreOper.required = false;
            document.querySelectorAll("input[name='Conciliacion']").forEach(r => r.checked = false);
            actualizarVisibilidadCerrarCaso();

            document.getElementById("lblValorConciliadoOper").textContent =
                "VALOR CONCILIADO";

            if (radio.value === "NO APLICA") {
                document.getElementById("lblValorConciliadoOper").textContent =
                    "VALOR CONCILIADO CON TERCEROS";
                bloqueValorConciliadoOper.style.display = "block";
                bloqueMotivoCierreOper.style.display = "block";
                motivoCierreOper.required = true;
                return;
            }

            // La validación de reincidencia aplica tanto si el operador
            // acepta la responsabilidad (SI) como si no la acepta (NO):
            // ambas cuentan como responsabilidad del operador. "NO
            // APLICA" ya retornó arriba y nunca llega aquí.
            if (radio.value !== "SI" && radio.value !== "NO") return;

            if (!movilSeleccionado) return;

            try {
                const resp = await fetch(`/Operaciones/verificar_reincidencia/${movilSeleccionado}`);
                const data = await resp.json();

                // Si el usuario cambió de respuesta mientras se consultaba,
                // no se aplica una respuesta anterior.
                if (!radio.checked) return;

                if (data.bloqueado) {
                    reincidenciaBloqueada = true;
                    mensajeReincidencia.textContent =
                        "El operador ya registra 3 eventos con responsabilidad dentro de un período de 2 meses. " +
                        "El caso debe ser remitido a Relaciones Laborales.";
                    mensajeReincidencia.style.display = "block";
                    bloqueConciliacion.style.display = "none";
                    document.getElementById("btnCerrarCaso")?.style && (document.getElementById("btnCerrarCaso").style.display = "none");
                } else if (radio.value === "SI") {
                    // La pregunta de conciliación solo existe cuando la
                    // responsabilidad es SI; para NO el flujo continúa
                    // igual que hoy (sin este bloque).
                    bloqueConciliacion.style.display = "block";
                }
            } catch (error) {
                console.error("No se pudo verificar la reincidencia del operador:", error);
                alert("No se pudo verificar el historial del operador. Intente nuevamente.");
            }
        });
    });

    // Pregunta: ¿se llega a conciliación? Si es SI, aparece "Valor
    // conciliado" (mismo patrón que "Costo del daño") y puede aparecer
    // "Cerrar caso".
    document.querySelectorAll("input[name='Conciliacion']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            const esSi = radio.value === "SI";

            bloqueValorConciliadoOper.style.display = esSi ? "block" : "none";
            if (!esSi) {
                valorConciliadoOperDisplay.value = "";
                valorConciliadoOperHidden.value = "";
            }

            actualizarVisibilidadCerrarCaso();
        });
    });
}
