// Módulo unificado — Utilidades: formato de moneda y estado, fechas, festivos de Colombia y duraciones hábiles.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// UTILIDADES
//======================================================

function formatoCOP(valor) {
    if (!valor) return "-";
    return new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        minimumFractionDigits: 0
    }).format(valor);
}

// Histórico de eventos del detalle de Relaciones Laborales.
const TEXTO_ESTADO_CASO = {
    "MANTENIMIENTO": "pendiente por mantenimiento",
    "OPERACIONES": "pendiente por operaciones",
    "SEGURIDAD VIAL": "pendiente por seguridad vial",
    "COMPLETO": "completo",
    "COMITE": "Comite"
};

function esCasoComite(registro) {
    return !registro.caso_cerrado && String(registro.pendiente_proceso_actual ?? "")
        .split(",").some(proceso => proceso.trim().toUpperCase() === "COMITE");
}

function formatearEstadoCaso(valorCrudo) {
    if (!valorCrudo) return "-";

    const partes = String(valorCrudo)
        .split(",")
        .map(p => p.trim().toUpperCase())
        .filter(Boolean);

    if (partes.includes("COMPLETO")) return "completo";

    return partes.map(p => TEXTO_ESTADO_CASO[p] || p).join(", ");
}

function construirAvisosPendienteLaboral(eventos) {
    if (!eventos?.length) return "";

    return eventos.map(ev => `
        <tr>
            <td colspan="2"><strong>Relaciones Laborales — caso ${escaparHtml(formatearEstadoCaso(ev.Pendiente_proceso))}</strong></td>
        </tr>
        <tr>
            <td>Fecha presentación</td>
            <td>${escaparHtml(ev.Fecha_presentacion ?? "-")}</td>
        </tr>
        <tr>
            <td>Observaciones de Relaciones Laborales</td>
            <td>${escaparHtml(ev.Observaciones_rrll ?? "-")}</td>
        </tr>
    `).join("<tr><td colspan='2'><hr></td></tr>");
}

function construirTabla(datos, campos) {
    return campos.map(campo => {
        let valor = datos?.[campo.key];

        if (campo.key === "fecha" && valor) {
            const d = new Date(valor);

            if (!isNaN(d.getTime())) {
                valor =
                `${String(d.getDate()).padStart(2, "0")}/` +
                `${String(d.getMonth() + 1).padStart(2, "0")}/` +
                `${d.getFullYear()} ` +
                `${String(d.getHours()).padStart(2, "0")}:` +
                `${String(d.getMinutes()).padStart(2, "0")}:` +
                `${String(d.getSeconds()).padStart(2, "0")}`;
            }
        }

        if (campo.formato === "moneda") {
            valor = formatoCOP(valor);
        }
        if (valor === undefined || valor === null || valor === "") {
            valor = "-";
        }
        return `<tr><td>${campo.label}</td><td>${escaparHtml(valor)}</td></tr>`;
    }).join("");
}

// fecha de evento llega como "YYYY-MM-DD" y fecha registro
// como "DD/MM/YYYY HH:MM:SS".
function parseFechaBackend(valor) {
    if (!valor) return null;

    const str = String(valor).trim();
    let m = str.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/);
    if (m) {
        return new Date(
        +m[1],
        +m[2] - 1,
        +m[3],
        +m[4],
        +m[5],
        +(m[6] || 0)
        );
    }

    m = str.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/);
    if (m) {
        return new Date(
            +m[1],
            +m[2] - 1,
            +m[3],
            +m[4],
            +m[5],
            +(m[6] || 0)
        );
    }

    m = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) {
    return new Date(
        +m[1],
        +m[2] - 1,
        +m[3]
        );
    }

    m = str.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
    if (m) {
        return new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0));
    }

     return null;
}

function formatearFechaRegistro(fecha) {
    const d = parseFechaBackend(fecha);
    if (!d) return "-";

    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();

    return `${dd}/${mm}/${yyyy}`;
}

//======================================================
// FESTIVOS COLOMBIA
//======================================================

const festivosPorAnio = {};

function calcularPascua(year) {
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const month = Math.floor((h + l - 7 * m + 114) / 31);
    const day = ((h + l - 7 * m + 114) % 31) + 1;
    return new Date(year, month - 1, day);
}

function moverALunes(fecha) {
    const d = fecha.getDay();
    if (d === 1) return fecha;
    const f = new Date(fecha);
    f.setDate(fecha.getDate() + ((8 - d) % 7));
    return f;
}

function generarFestivosColombia(year) {
    const festivos = [];

    festivos.push(new Date(year, 0, 1));    // Año Nuevo
    festivos.push(new Date(year, 4, 1));    // Día del Trabajo
    festivos.push(new Date(year, 6, 20));   // Independencia
    festivos.push(new Date(year, 7, 7));    // Boyacá
    festivos.push(new Date(year, 11, 8));   // Inmaculada
    festivos.push(new Date(year, 11, 25));  // Navidad

    festivos.push(moverALunes(new Date(year, 0, 6)));   // Reyes
    festivos.push(moverALunes(new Date(year, 2, 19)));  // San José
    festivos.push(moverALunes(new Date(year, 5, 29)));  // San Pedro y San Pablo
    festivos.push(moverALunes(new Date(year, 7, 15)));  // Asunción
    festivos.push(moverALunes(new Date(year, 9, 12)));  // Raza
    festivos.push(moverALunes(new Date(year, 10, 1)));  // Todos los Santos
    festivos.push(moverALunes(new Date(year, 10, 11))); // Cartagena

    const pascua = calcularPascua(year);
    festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 3)); // Jueves Santo
    festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 2)); // Viernes Santo
    festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 43))); // Ascensión
    festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 64))); // Corpus
    festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 71))); // Sagrado

    return festivos.map(f => f.toISOString().split("T")[0]);
}

function obtenerFestivosColombia(year) {
    if (!festivosPorAnio[year]) {
        festivosPorAnio[year] = generarFestivosColombia(year);
    }
    return festivosPorAnio[year];
}

function esDiaHabil(fecha) {
    const dia = fecha.getDay();
    if (dia === 0 || dia === 6) return false; // domingo o sábado

    const iso = fecha.toISOString().split("T")[0];
    const festivos = obtenerFestivosColombia(fecha.getFullYear());

    return !festivos.includes(iso);
}

// Diferencia entre inicio y fin contando solo tiempo dentro de días hábiles
function calcularDuracionHabil(inicio, fin) {
    let actual = new Date(inicio);
    let totalMs = 0;

    while (actual < fin) {
        if (esDiaHabil(actual)) {
            let finDia = new Date(actual);
            finDia.setHours(23, 59, 59, 999);
            if (finDia > fin) finDia = fin;
            totalMs += (finDia - actual);
        }
        actual.setDate(actual.getDate() + 1);
        actual.setHours(0, 0, 0, 0);
    }

    const dias = Math.floor(totalMs / 86400000);
    const horas = Math.floor((totalMs % 86400000) / 3600000);
    const minutos = Math.floor((totalMs % 3600000) / 60000);

    return { dias, horas, minutos };
}

function calcularDiferencia(fechaValor, fechaFin = null) {
    const inicio = parseFechaBackend(fechaValor);
    if (!inicio) return null;

    const fin = fechaFin
    ? parseFechaBackend(fechaFin)
    : new Date();

    if (!fin) return null;

    const fechaFinal = fin > inicio ? fin : inicio;

    const { dias, horas, minutos } =
    calcularDuracionHabil(inicio, fechaFinal);

    let texto;
    if (dias > 0) texto = `${dias} d ${horas} h`;
    else if (horas > 0) texto = `${horas} h ${minutos} min`;
    else texto = `${minutos} min`;

    return { dias, horas, minutos, texto };
}

// Duración desde que se registró el evento y desde que ocurrió el evento en si.
function calcularDuracionesRegistro(registro) { const tRegistro = calcularDiferencia(registro.fecha_r);
    let tEvento;
    if (Number(registro.estado_caso) === 1 && registro.fecha_cierre) {
        // Caso cerrado: el contador termina en la fecha real de cierre
        tEvento = calcularDiferencia(
            registro.fecha,
            registro.fecha_cierre
        );
    }else {
        // Caso abierto: el contador continúa hasta ahora
        tEvento = calcularDiferencia(registro.fecha);
    }
    return {
        duracion: tRegistro ? tRegistro.texto : "-",
        duracionEvento: tEvento ? tEvento.texto : "-",
        t: tEvento
    };
}


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarUtilidades() {
    window.formatearFechaRegistro = formatearFechaRegistro;

    window.calcularDuracionesRegistro = calcularDuracionesRegistro;
}
