const sidebar = document.querySelector(".sidebar");
const user = document.getElementById("userToggle");
const dropdown = document.getElementById("userDropdown");
const submenuButtons = document.querySelectorAll(".has-submenu");

// --- Función para cerrar todo (Limpieza) ---
function cerrarTodo() {
    // Cerramos submenús de navegación
    submenuButtons.forEach((btn) => btn.classList.remove("active"));
    
    // Cerramos dropdown de usuario
    if (dropdown) dropdown.classList.remove("show");
    if (user) user.classList.remove("active");
    
    // Quitamos la clase de expansión forzada
    sidebar.classList.remove("has-active-submenu");
}

// --- Evento: Cuando el mouse SALE de la sidebar ---
sidebar.addEventListener("mouseleave", () => {
    cerrarTodo();
});

// --- Lógica del Menú de Usuario ---
user.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("show");
    user.classList.toggle("active");
    
    // Solo expande si el click fue manual y queremos asegurar el ancho
    if (user.classList.contains("active")) {
        sidebar.classList.add("has-active-submenu");
    }
});

// --- Lógica de los Submenús de Navegación ---
submenuButtons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Cerramos otros submenús para que no se amontonen
        submenuButtons.forEach(otroBtn => {
            if (otroBtn !== btn) otroBtn.classList.remove("active");
        });

        btn.classList.toggle("active");

        // Si se activó, aseguramos que la sidebar sepa que hay contenido expandido
        if (btn.classList.contains("active")) {
            sidebar.classList.add("has-active-submenu");
        } else {
            // Si no hay ningún otro activo, podríamos quitar la clase
            const algunActivo = Array.from(submenuButtons).some(b => b.classList.contains("active"));
            if (!algunActivo) sidebar.classList.remove("has-active-submenu");
        }
    });
});

// --- Click fuera (por seguridad) ---
document.addEventListener("click", (e) => {
    if (!sidebar.contains(e.target)) {
        cerrarTodo();
    }
});