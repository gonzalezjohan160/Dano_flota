// Historicos comun — festivos de Colombia, adjuntos y textos en mayúscula.
// Antes formaba parte de Mult_formularios.js; se carga en orden desde frontend/Front_historico_danos.html y frontend/Front_historico_movil.html.

    /***********************
     * FESTIVOS COLOMBIA 🇨🇴
     ***********************/

    // Cache por año (mejor rendimiento)
    const festivosPorAnio = {};

    // Pascua
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

    // Mover festivos al lunes (Ley Emiliani)
    function moverALunes(fecha) {
        const d = fecha.getDay();
        if (d === 1) return fecha;
        const f = new Date(fecha);
        f.setDate(fecha.getDate() + ((8 - d) % 7));
        return f;
    }

    // Generar festivos Colombia
    function generarFestivosColombia(year) {
        const festivos = [];

        // Fijos
        festivos.push(new Date(year, 0, 1));    // Año Nuevo
        festivos.push(new Date(year, 4, 1));    // Día del Trabajo
        festivos.push(new Date(year, 6, 20));   // Independencia
        festivos.push(new Date(year, 7, 7));    // Boyacá
        festivos.push(new Date(year, 11, 8));   // Inmaculada
        festivos.push(new Date(year, 11, 25));  // Navidad

        // Emiliani
        festivos.push(moverALunes(new Date(year, 0, 6)));   // Reyes
        festivos.push(moverALunes(new Date(year, 2, 19)));  // San José
        festivos.push(moverALunes(new Date(year, 5, 29)));  // San Pedro y San Pablo
        festivos.push(moverALunes(new Date(year, 7, 15)));  // Asunción
        festivos.push(moverALunes(new Date(year, 9, 12)));  // Raza
        festivos.push(moverALunes(new Date(year, 10, 1)));  // Todos los Santos
        festivos.push(moverALunes(new Date(year, 10, 11))); // Cartagena

        // Pascua
        const pascua = calcularPascua(year);
        festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 3)); // Jueves Santo
        festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 2)); // Viernes Santo
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 43))); // Ascensión
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 64))); // Corpus
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 71))); // Sagrado

        return festivos.map(f => f.toISOString().split("T")[0]);
    }

    // Obtener festivos por año
    function obtenerFestivosColombia(year) {
        if (!festivosPorAnio[year]) {
            festivosPorAnio[year] = generarFestivosColombia(year);
        }
        return festivosPorAnio[year];
    }

    /***********************
     * DÍAS HÁBILES
     ***********************/
    function esDiaHabil(fecha) {
        const dia = fecha.getDay();
        if (dia === 0 || dia === 6) return false; // domingo o sábado

        const iso = fecha.toISOString().split("T")[0];
        const festivos = obtenerFestivosColombia(fecha.getFullYear());

        return !festivos.includes(iso);
    }

    /***********************
     * DURACIÓN HÁBIL
     ***********************/
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

    // Eliminar adjunto específico
    function eliminarAdjunto(i) {
        adjuntosSeleccionados.splice(i, 1);
        actualizarListaAdjuntos();
    }

    // Redibuja la lista
    function actualizarListaAdjuntos() {
        listaAdjuntos.innerHTML = "";

        adjuntosSeleccionados.forEach((file, index) => {
            const item = document.createElement("div");
            item.className = "adjunto_item";

            const nombre = document.createElement("span");
            nombre.className = "adjunto_nombre";
            nombre.textContent = file.name;

            const btnDel = document.createElement("button");
            btnDel.className = "btnAdjuntoDelete";
            btnDel.textContent = "❌";
            btnDel.onclick = () => {
                eliminarAdjunto(index);
            };

            item.appendChild(nombre);
            item.appendChild(btnDel);
            listaAdjuntos.appendChild(item);
        });
    }

        // Selecciona todos los textarea
    const textareas = document.querySelectorAll('textarea');

    // Convierte a mayúsculas mientras se escribe
    textareas.forEach(textarea => {
        textarea.addEventListener('input', () => {
            textarea.value = textarea.value.toUpperCase();
        });
    });
