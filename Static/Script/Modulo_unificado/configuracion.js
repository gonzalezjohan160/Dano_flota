// Módulo unificado — Configuración del módulo (enviada por el backend), variables globales y restricciones por módulo.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// VARIABLES GLOBALES
//======================================================

let inputAdjuntos = null;
let listaAdjuntos = null;
let adjuntosSeleccionados = [];

let registros = [];
let movilSeleccionado = "";

// Paginación de la tabla principal (30 filas por página).
const FILAS_POR_PAGINA = 30;
let paginaActual = 1;
let listaTablaActual = []; // lista que se está paginando
const escaparHtml = window.escaparHtml;


//======================================================
// CONFIGURACIÓN DE TABLAS DEL MODAL (detalle cruzado)
//======================================================

const DETAIL_CONFIG = {

    general: [
        { key: "fecha", label: "FECHA EVENTO" },
        { key: "Movil", label: "MÓVIL" },
        { key: "Codigo", label: "CÓDIGO" },
        { key: "Nombre", label: "NOMBRE" },
        { key: "Area", label: "ÁREA" },
        { key: "Ruta", label: "RUTA" },
        { key: "Version_libre", label: "VERSIÓN LIBRE" },
        { key: "Zona_dano", label: "ZONA DEL DAÑO" },
        { key: "Parte_afectada", label: "PARTE AFECTADA" },
        { key: "Dano_ocasionado", label: "DAÑO OCASIONADO POR" },
        { key: "Centro_operaciones", label: "CENTRO OPERACIONAL" },
        { key: "Registrador", label: "RESPONSABLE DILIGENCIAMIENTO" },
        { key: "fecha_r", label: "FECHA REGISTRO" },
        { key: "Direccion", label: "DIRECCIÓN" }
    ],

    oper: [
        { key: "Observaciones_operaciones", label: "OBSERVACIONES OPERACIONALES" },
        { key: "rev_error", label: "INFO. CORRECTA" },
        { key: "Observaciones_correctivos", label: "OBSERVACIONES ADICIONALES" },
        { key: "responsabilidad_operador", label: "ACEPTA LA RESPONSABILIDAD EL OPERADOR" },
        { key: "conciliacion", label: "CONCILIACIÓN" },
        { key: "CostoDelDanoOper", label: "COSTO DEL DAÑO", formato: "moneda" },
        { key: "ValorConciliadoOper", label: "VALOR CONCILIADO", formato: "moneda" }
    ],

    // Vista reducida de Operaciones: la usa Mantenimiento en "Ver
    // archivos", donde los controles propios del flujo de Operaciones
    // (responsabilidad, conciliación, costo, valor conciliado) no
    // aplican -- Mantenimiento solo ve casos del camino > $2.000.000.
    oper_basico: [
        { key: "Observaciones_operaciones", label: "OBSERVACIONES OPERACIONALES" },
        { key: "rev_error", label: "INFO. CORRECTA" },
        { key: "Observaciones_correctivos", label: "OBSERVACIONES ADICIONALES" }
    ],

    mtto: [
        { key: "Costo", label: "COSTO", formato: "moneda" },
        { key: "dano_adicional", label: "DAÑO ADICIONAL" },
        { key: "observaciones", label: "OBSERVACIONES" }
    ],

    svial: [
        { key: "Observaciones_svial", label: "OBSERVACIONES" }
    ],

    laboral_estado: [
        { key: "Tipo_cerrado", label: "TIPO DE CIERRE" },
        { key: "Valor_conciliado", label: "VALOR CONCILIADO", formato: "moneda" }
    ]

};


//======================================================
// CONFIGURACIÓN DE FORMULARIOS
//======================================================

const FORM_CONFIG = {

    oper: {
        endpoint: "agregar_oper",
        campos: [
            { id: "campo_principal", nombre: "observaciones_1" }
        ]
    },

    mtto: {
        endpoint: "agregar_mtto",
        campos: [
            { id: "campo_principal", nombre: "Costo" },
            { id: "observaciones", nombre: "observaciones" }
        ]
    },

    svial: {
        endpoint: "agregar_svial",
        campos: [
            { id: "campo_principal", nombre: "Observaciones_svial" },
            { id: "conciliado_a_favor", nombre: "conciliado_a_favor" },
            { id: "valor_conciliado_terceros", nombre: "valor_conciliado_terceros" }
        ]
    },

    laboral: {
        endpoint: "agregar_rl",
        campos: [
            { id: "campo_principal", nombre: "observaciones_1" },
            { id: "fecha_presentacion", nombre: "Fecha_presentacion_input" },
            { id: "estado_caso", nombre: "Estado_caso" },
            { id: "valor_conciliado", nombre: "Costo" }
        ]
    }

};

const NOMBRE_SECCION = {
    oper: "OPERACIONAL",
    mtto: "MANTENIMIENTO",
    svial: "SEGURIDAD VIAL",
    laboral: "RELACIONES LABORALES"
};


//======================================================
// CONFIG DEL MÓDULO (enviada por el backend)
//======================================================

let CFG = null;

try {
    const scriptCfg = document.getElementById("modulo-config-json");
    CFG = JSON.parse(scriptCfg.textContent);
} catch (error) {
    console.error("No se pudo leer la configuración del módulo:", error);
}

// Antes los definía un <script> en línea de la plantilla; salen de la misma config.
const MODULO = CFG ? CFG.modulo : null;
const TITULO = CFG ? CFG.titulo : null;

// Set de secciones visibles para consultas rápidas
const SECCIONES_VISIBLES = new Set((CFG && CFG.seccionesVisibles) || []);

// FECHA R. LABORALES
const MOSTRAR_COLUMNA_FECHA_LABORAL = Boolean(CFG) && CFG.propia === "laboral";

//======================================================
// CONFIGURAR MÓDULO (aplica las restricciones)
//======================================================

function configurarModulo() {

    document.getElementById("lblCampoPrincipal").textContent =
        CFG.campoPrincipalLabel;

    const esLaboral = CFG.propia === "laboral";
    const esMtto = CFG.propia === "mtto";
    const esOper = CFG.propia === "oper";
    const esSvial = CFG.propia === "svial";

    // Nuevo flujo de Operaciones (valor del daño / responsabilidad / conciliación)
    document.getElementById("cardFlujoOper").style.display = esOper ? "block" : "none";
    document.getElementById("bloqueConciliadoFavor").style.display = esSvial ? "block" : "none";

    // Activa el nuevo look (tarjetas, toggle NO/SÍ, campos de cierre)
    // solo para RRLL.
    document.getElementById("formModal").classList.toggle("form-laboral", esLaboral);

    document.getElementById("cardCierre").style.display =
        CFG.mostrarRevision ? "block" : "none";

    document.getElementById("lblRevision").textContent = esLaboral
        ? "¿SE GENERA CIERRE DEL CASO?"
        : "¿LA INFORMACIÓN CARGADA ES CORRECTA?";


    const textareaObsInicial = document.getElementById("observaciones");
    document.getElementById("bloqueObservaciones").style.display =
        (CFG.mostrarObservaciones || esMtto) ? "block" : "none";

    if (esMtto) {
        textareaObsInicial.disabled = false;
    }

    document.getElementById("bloqueCamposLaboral").style.display =
        esLaboral ? "block" : "none";

    document.getElementById("bloqueLaboralCierre").style.display =
        esLaboral ? "block" : "none";

    // En RRLL el caso arranca como "no cerrado".
    if (esLaboral) {
        document.querySelector("input[name='Revinf'][value='NO']").checked = true;
        document.getElementById("motivo_cierre").disabled = true;
        document.getElementById("valor_conciliado_display").disabled = true;
    }

    // Mantenimiento: "Costo del daño" es un valor monetario, así que
    // se usa el input con formato de miles
    const campoPrincipalTextarea = document.getElementById("campo_principal");
    const campoPrincipalCosto = document.getElementById("campo_principal_costo_display");

    campoPrincipalTextarea.style.display = esMtto ? "none" : "";
    campoPrincipalCosto.style.display = esMtto ? "" : "none";
    campoPrincipalTextarea.required = !esMtto;
    campoPrincipalCosto.required = esMtto;

    // Mantenimiento: pregunta "¿Existe algún daño más asociado
    // al evento?" (toggle NO/SÍ), justo debajo del costo del daño.
    document.getElementById("bloqueDanoAdicional").style.display =
        esMtto ? "block" : "none";

    if (esMtto) {
        actualizarObservacionesPorDanoAdicional();
    }

    // Mostrar/ocultar secciones del modal de detalle según permisos
    document.querySelectorAll("[data-seccion]").forEach(el => {
        const seccion = el.dataset.seccion;
        const visible = SECCIONES_VISIBLES.has(seccion);
        el.style.display = visible ? "" : "none";
    });

}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarConfiguracion() {
    configurarModulo();

    if (CFG.propia === "mtto") {
        const campoPrincipalCosto = document.getElementById("campo_principal_costo_display");
        const campoPrincipalTextarea = document.getElementById("campo_principal");

        campoPrincipalCosto.addEventListener("input", () => {
            const soloDigitos = campoPrincipalCosto.value.replace(/\D/g, "");

            campoPrincipalCosto.value = soloDigitos
                ? new Intl.NumberFormat("es-CO").format(Number(soloDigitos))
                : "";

            campoPrincipalTextarea.value = soloDigitos;
        });
    }
}
