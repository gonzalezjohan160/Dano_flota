// Módulo unificado — Campos del formulario: valor conciliado, estado del caso (RRLL), revisión y daño adicional.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// RADIO BUTTONS
//======================================================

const textareaObs = document.getElementById("observaciones");
const motivoCierre = document.getElementById("motivo_cierre");
const valorConciliado = document.getElementById("valor_conciliado"); // input oculto: valor numérico limpio
const valorConciliadoDisplay = document.getElementById("valor_conciliado_display"); // input visible: con formato de miles

//======================================================
// MULTISELECT DE CASILLAS: "CASO PENDIENTE POR EL PROCESO"
// (Mantenimiento / S.Vial / Operaciones / Completo)
//======================================================

const estadoCasoToggle = document.getElementById("estado_caso_toggle");
const estadoCasoOpciones = document.getElementById("estado_caso_opciones");
const estadoCasoLabel = document.getElementById("estado_caso_label");
const estadoCasoHidden = document.getElementById("estado_caso");

function sincronizarEstadoCaso() {
    if (!estadoCasoOpciones) return;

    const completo = estadoCasoOpciones.querySelector("input[value='COMPLETO']");
    const procesosIndividuales = Array.from(
        estadoCasoOpciones.querySelectorAll("input[type='checkbox']:not([value='COMPLETO'])")
    );

    if (completo?.checked) {
        procesosIndividuales.forEach(cb => {
            cb.checked = false;
            cb.disabled = true;
        });
    } else {
        procesosIndividuales.forEach(cb => {
            cb.disabled = false;
        });
    }

    const marcados = Array.from(
        estadoCasoOpciones.querySelectorAll("input[type='checkbox']:checked")
    ).map(cb => cb.value);

    estadoCasoHidden.value = marcados.join(", ");
    estadoCasoLabel.textContent = marcados.length
        ? marcados.join(", ")
        : "Seleccione estados";
}

//======================================================
// TOGGLE "¿EXISTE ALGÚN DAÑO MÁS ASOCIADO AL EVENTO?"
// (solo Mantenimiento).
//======================================================

function actualizarObservacionesPorDanoAdicional() {
    const radioSeleccionado = document.querySelector("input[name='DanoAdicional']:checked");
    const hayDanoAdicional = radioSeleccionado ? radioSeleccionado.value === "SI" : false;

    const lblObservaciones = document.querySelector("#bloqueObservaciones label[for='observaciones']");
    const textareaObservaciones = document.getElementById("observaciones");

    lblObservaciones.textContent = hayDanoAdicional
        ? "DESCRIBA EL DAÑO ADICIONAL:"
        : "OBSERVACIONES:";

    textareaObservaciones.required = hayDanoAdicional;
}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarFormularioCampos() {
    //======================================================
    // FORMATO DE MILES PARA VALOR CONCILIADO
    //======================================================

    if (valorConciliadoDisplay && valorConciliado) {

        valorConciliadoDisplay.addEventListener("input", () => {
            const soloDigitos = valorConciliadoDisplay.value.replace(/\D/g, "");

            valorConciliadoDisplay.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";

            valorConciliado.value = soloDigitos;
        });
    }

    if (estadoCasoToggle && estadoCasoOpciones) {

        estadoCasoToggle.addEventListener("click", e => {
            e.stopPropagation();
            estadoCasoOpciones.classList.toggle("abierto");
        });

        estadoCasoOpciones.addEventListener("change", sincronizarEstadoCaso);

        // Cierra el desplegable al hacer click fuera de él
        document.addEventListener("click", e => {
            if (!document.getElementById("estado_caso_multiselect").contains(e.target)) {
                estadoCasoOpciones.classList.remove("abierto");
            }
        });
    }

    document.querySelectorAll("input[name='Revinf']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            if (CFG.propia === "laboral") {
                // Motivo del cierre y valor conciliado solo aplican
                // cuando SÍ se genera el cierre del caso.
                const seCierra = radio.value === "SI";

                motivoCierre.disabled = !seCierra;
                motivoCierre.required = seCierra;
                valorConciliadoDisplay.disabled = !seCierra;
                valorConciliadoDisplay.required = seCierra;

                if (!seCierra) {
                    motivoCierre.value = "";
                    valorConciliadoDisplay.value = "";
                    valorConciliado.value = "";
                }
                return;
            }

            if (radio.value === "NO") {
                textareaObs.disabled = false;
                textareaObs.required = true;
            } else if (radio.value === "SI") {
                textareaObs.disabled = true;
                textareaObs.required = false;
                textareaObs.value = "";
            }
        });
    });

    document.querySelectorAll("input[name='DanoAdicional']").forEach(radio => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;
            actualizarObservacionesPorDanoAdicional();
        });
    });
}
