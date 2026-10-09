(() => {
    const playerDialog = document.getElementById("reproductorTutorial");
    const player = document.getElementById("videoTutorial");
    const playerTitle = document.getElementById("tituloReproductor");

    document.querySelectorAll(".tutoriales-watch").forEach((button) => {
        button.addEventListener("click", () => {
            playerTitle.textContent = button.dataset.title || "Tutorial";
            player.src = button.dataset.videoUrl;
            playerDialog.showModal();
        });
    });

    const closePlayer = () => {
        player.pause();
        player.removeAttribute("src");
        player.load();
        playerDialog.close();
    };

    document.getElementById("cerrarReproductor").addEventListener("click", closePlayer);

    playerDialog.addEventListener("click", (event) => {
        if (event.target === playerDialog) closePlayer();
    });

    document.querySelectorAll(".form-eliminar-tutorial").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const confirmado = window.confirm("¿Está seguro de eliminar este video? Esta acción eliminará el archivo y no se puede deshacer.");
            if (!confirmado) event.preventDefault();
        });
    });

    const uploadDialog = document.getElementById("dialogoSubida");

    if (uploadDialog) {
        document.getElementById("abrirSubida").addEventListener("click", () => uploadDialog.showModal());

        document.getElementById("cancelarSubida").addEventListener("click", () => uploadDialog.close());

        document.getElementById("cerrarSubida").addEventListener("click", () => uploadDialog.close());

        const fileInput = document.getElementById("archivoVideo");
        const titleInput = document.getElementById("tituloTutorial");
        const submitButton = document.querySelector(".tutoriales-submit");
        const mensajePesoVideo = document.getElementById("mensajePesoVideo");

        const MAX_SIZE = 20 * 1024 * 1024; // 20 MB

        titleInput.addEventListener("input", () => {
            titleInput.value = titleInput.value.slice(0, 200);
            titleInput.setCustomValidity(
                titleInput.value.trim() ? "" : "Escribe el título del tutorial."
            );
        });

        fileInput.addEventListener("change", () => {
            const archivo = fileInput.files[0];

            if (!archivo) {
                mensajePesoVideo.style.display = "none";
                submitButton.disabled = false;
                return;
            }

            if (archivo.size > MAX_SIZE) {
                mensajePesoVideo.style.display = "block";
                submitButton.disabled = true;
                fileInput.setCustomValidity(
                    "El video supera el límite máximo permitido de 20 MB."
                );
            } else {
                mensajePesoVideo.style.display = "none";
                submitButton.disabled = false;
                fileInput.setCustomValidity("");
            }
        });

        document.querySelector(".tutorial-upload-form").addEventListener("submit", (event) => {
            titleInput.value = titleInput.value.trim();

            if (!titleInput.value) {
                event.preventDefault();
                titleInput.setCustomValidity("Escribe el título del tutorial.");
                titleInput.reportValidity();
                return;
            }

            const archivo = fileInput.files[0];

            if (archivo && archivo.size > MAX_SIZE) {
                event.preventDefault();
                mensajePesoVideo.style.display = "block";
                submitButton.disabled = true;
                fileInput.setCustomValidity(
                    "El video supera el límite máximo permitido de 20 MB."
                );
                fileInput.reportValidity();
            }
        });
    }

    document.querySelectorAll(".tutoriales-watch").forEach((button) => {
        const probe = document.createElement("video");
        probe.preload = "metadata";

        probe.onloadedmetadata = () => {
            const seconds = Math.round(probe.duration);

            if (Number.isFinite(seconds) && seconds > 0) {
                const minutes = Math.floor(seconds / 60);

                button.closest(".tutorial-card").querySelector(".tutorial-duration").textContent =
                    `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
            }

            probe.removeAttribute("src");
            probe.load();
        };

        probe.src = button.dataset.videoUrl;
    });
})();
