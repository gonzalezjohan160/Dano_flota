// Módulo unificado — Datos que se envían (FormData) y validación del formulario.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// CONSTRUIR FORMDATA
//======================================================

function construirFormData() {

    const formData = new FormData();

    formData.append("Id_damage_to_fleet", movilSeleccionado);
    formData.append("Usuario_registro_oper", document.body.dataset.usuario);
    if (modoCorreccionGestion) {
        formData.append("Motivo_modificacion", document.getElementById("motivo_gestion").value.trim());
    }

    const formulario = FORM_CONFIG[CFG.propia];

    formulario.campos.forEach(campo => {
        const control = document.getElementById(campo.id);
        if (control) {
            formData.append(campo.nombre, control.value);
        }
    });

    if (CFG.mostrarRevision) {
        const revision = document.querySelector("input[name='Revinf']:checked").value;
        formData.append("Revinf", revision);

        if (CFG.propia === "laboral") {
            formData.append(
                "Tipo_cerrado_input",
                revision === "SI" ? document.getElementById("motivo_cierre").value : ""
            );
        }
    }

    // Mantenimiento: "¿Existe algún daño más asociado al evento?"
    if (CFG.propia === "mtto") {
        const danoAdicional = document.querySelector("input[name='DanoAdicional']:checked");
        formData.append("dano_adicional", danoAdicional ? danoAdicional.value : "NO");
    }

    if (CFG.propia === "svial" && conciliadoAFavor.value) {
        formData.append("conciliado_a_favor", conciliadoAFavor.value);
        formData.append(
            "valor_conciliado_terceros",
            valorConciliadoTercerosSvial.value.replace(/\D/g, "")
        );
    }

    // Operaciones: nuevo flujo (costo del daño / responsabilidad / conciliación)
    if (CFG.propia === "oper") {
        const costoSupera = document.querySelector("input[name='CostoSupera2M']:checked");
        formData.append("costo_supera_2m", costoSupera ? costoSupera.value : "");

        if (costoSupera && costoSupera.value === "NO") {
            formData.append("costo_valor", document.getElementById("costo_dano").value);

            const responsabilidad = document.querySelector("input[name='ResponsabilidadOperador']:checked");
            formData.append("responsabilidad_operador", responsabilidad ? responsabilidad.value : "");

            if (responsabilidad && responsabilidad.value === "NO APLICA") {
                formData.append("conciliacion", "");
                formData.append("motivo_cierre_oper", motivoCierreOper.value);

                formData.append(
                    "valor_conciliado_oper",
                    document.getElementById("valor_conciliado_oper").value
                );

            } else if (
                responsabilidad &&
                responsabilidad.value === "SI" &&
                document.getElementById("bloqueConciliacion").style.display !== "none"
            ) {

                const conciliacion = document.querySelector("input[name='Conciliacion']:checked");
                formData.append("conciliacion", conciliacion ? conciliacion.value : "");

                if (conciliacion && conciliacion.value === "SI") {
                    formData.append("valor_conciliado_oper", document.getElementById("valor_conciliado_oper").value);
                }
            }
        }
    }

    adjuntosSeleccionados.forEach(file => {
        formData.append("archivos", file);
    });

    return formData;
}

//======================================================
// VALIDAR FORMULARIO
//======================================================

function validarFormulario() {

    if (!movilSeleccionado) {
        alert("Seleccione un registro.");
        return false;
    }
    if (modoCorreccionGestion && CFG.propia !== "laboral") {
        const motivoCambio = document.getElementById("motivo_gestion");

        if (!motivoCambio.reportValidity()) return false;
    }

    if (CFG.mostrarRevision) {
        const revision = document.querySelector("input[name='Revinf']:checked").value;

        if (CFG.mostrarObservaciones && revision === "NO" && !textareaObs.value.trim()) {
            alert("Debe ingresar observaciones.");
            return false;
        }

        if (CFG.propia === "laboral" && revision === "SI") {
            if (!motivoCierre.value) {
                alert("Seleccione el motivo del cierre.");
                return false;
            }
            if (!valorConciliado.value) {
                alert("Ingrese el valor conciliado.");
                return false;
            }
        }
    }

    if (CFG.propia === "mtto") {
        const danoAdicional = document.querySelector("input[name='DanoAdicional']:checked");
        if (danoAdicional && danoAdicional.value === "SI" &&
            !document.getElementById("observaciones").value.trim()) {
            alert("Describa el daño adicional.");
            return false;
        }
    }

    if (CFG.propia === "oper") {
        const costoSupera = document.querySelector("input[name='CostoSupera2M']:checked");
        if (!costoSupera) {
            alert("Responda si el costo del daño supera $2.000.000.");
            return false;
        }

        if (costoSupera.value === "NO") {
            if (!document.getElementById("costo_dano").value) {
                alert("Ingrese el costo del daño.");
                return false;
            }

            // Mientras el mensaje de "supera el monto máximo" esté
            // visible, no se permite guardar la información.
            if (Number(document.getElementById("costo_dano").value || 0) > LIMITE_COSTO_DANO) {
                return false;
            }

            const responsabilidad = document.querySelector("input[name='ResponsabilidadOperador']:checked");
            if (!responsabilidad) {
                alert("Responda si el operador acepta la responsabilidad.");
                return false;
            }

            if (responsabilidad.value === "NO APLICA" && !motivoCierreOper.reportValidity()) {
                return false;
            }

            if (responsabilidad.value === "SI" &&
                document.getElementById("bloqueConciliacion").style.display !== "none") {
                const conciliacion = document.querySelector("input[name='Conciliacion']:checked");
                if (!conciliacion) {
                    alert("Responda si se llega a conciliación.");
                    return false;
                }

                if (conciliacion.value === "SI" && !document.getElementById("valor_conciliado_oper").value) {
                    alert("Ingrese el valor conciliado.");
                    return false;
                }
            }
        }
    }

    return true;
}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarValidacion() {
    // Esta parte no tiene acciones de arranque.
}
