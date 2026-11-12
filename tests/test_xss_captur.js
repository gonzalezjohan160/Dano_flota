const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

class Element {
    constructor(tagName) {
        this.tagName = tagName;
        this.children = [];
        this.listeners = {};
        this.style = {};
        this.removed = false;
        this._textContent = "";
    }

    set textContent(value) {
        this._textContent = String(value);
        this.children = [];
    }

    get textContent() {
        return this._textContent + this.children.map(child => child.textContent).join("");
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    append(...children) {
        this.children.push(...children);
    }

    addEventListener(name, callback) {
        this.listeners[name] = callback;
    }

    remove() {
        this.removed = true;
    }
}

const source = fs.readFileSync("Static/Script/Capturador/adjuntos_envio.js", "utf8");
const start = source.indexOf("function mostrarModalDuplicado(");
const end = source.indexOf("// 5. Función de Compresión", start);
assert(start >= 0 && end > start, "Debe existir la función del modal de duplicados");

let modal;
let formSent = false;
const document = {
    getElementById(id) {
        return id === "modalDuplicado" ? null : null;
    },
    createElement(tagName) {
        return new Element(tagName);
    },
    body: {
        appendChild(element) {
            modal = element;
        }
    }
};

const mostrarModalDuplicado = vm.runInNewContext(
    `${source.slice(start, end)}; mostrarModalDuplicado;`,
    { document, enviarFormulario() { formSent = true; } }
);
mostrarModalDuplicado("fecha", "<img src=x onerror=alert(1)>", "codigo", "<svg onload=alert(1)>");

assert(modal, "El modal debe agregarse al documento");
assert.strictEqual(modal.children[0].children[1].children[1].textContent, "<img src=x onerror=alert(1)>");
assert.strictEqual(modal.children[0].children[1].children[3].textContent, "<svg onload=alert(1)>");
assert.strictEqual(modal.children[0].children[1].children[1].tagName, "b");
assert.strictEqual(modal.children[0].children[1].children[3].tagName, "b");

const actions = modal.children[0].children[2].children;
actions[0].listeners.click();
assert.strictEqual(modal.removed, true, "Cancelar debe cerrar el modal");

mostrarModalDuplicado("fecha", "móvil", "codigo", "zona");
modal.children[0].children[2].children[1].listeners.click();
assert.strictEqual(formSent, true, "Enviar de todos modos debe conservar el envío existente");
assert.strictEqual(modal.removed, true, "Enviar de todos modos debe cerrar el modal");

console.log("XSS capturador tests passed: untrusted fields render as text and modal actions remain functional.");
