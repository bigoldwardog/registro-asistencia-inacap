
const form = document.getElementById("attendance-form");
const title = document.getElementById("attendance-title");
const eventDate = document.getElementById("event-date");
const message = document.getElementById("form-message");
const submitButton = document.getElementById("submit-button");

const params = new URLSearchParams(window.location.search);
const token = params.get("token");

let sessionIsOpen = false;

async function loadSession() {
    if (!token) {
        title.textContent = "No se especificó un evento";
        message.textContent = "Accede mediante el código QR de la sesión.";
        form.hidden = true;
        return;
    }

    try {
        const response = await fetch(
            `/api/sesiones/${encodeURIComponent(token)}/`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "No se pudo cargar el evento.");
        }

        title.textContent = data.nombre;
        eventDate.textContent = data.fecha_inicio
            ? `Fecha: ${data.fecha_inicio}`
            : "";

        
        sessionIsOpen = data.estado === "ABIERTA";

        if (!sessionIsOpen) {
            form.hidden = true;
            message.textContent = "Esta sesión está cerrada y no admite registros.";
            return;
        }

        const rutGuardado = localStorage.getItem(
            `asistencia_rut_${token}`
        );

        if (rutGuardado) {
            try {
                const response = await fetch(
                    `/api/sesiones/${encodeURIComponent(token)}/asistencias/consultar/?rut=${encodeURIComponent(rutGuardado)}`
                );

                const resultado = await response.json();

                if (response.ok && resultado.registrada) {
                    form.hidden = true;
                    message.textContent =
                        "Tu asistencia ya está registrada. No necesitas completar el formulario nuevamente.";
                    return;
                }
            } catch (error) {
                console.error(
                    "No se pudo comprobar la asistencia existente:",
                    error
                );
            }
        }

    } catch (error) {
        title.textContent = "No se pudo cargar el evento";
        message.textContent = error.message;
        form.hidden = true;
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!token || !sessionIsOpen) {
        message.textContent = "No hay una sesión abierta para registrar.";
        return;
    }

    const datos = {
        nombre: form.elements.nombre.value.trim(),
        rut: form.elements.rut.value.trim(),
        telefono: form.elements.telefono.value.trim(),
        correo: form.elements.correo.value.trim()
    };

    submitButton.disabled = true;
    message.textContent = "Registrando asistencia...";

    try {
        const response = await fetch(
            `/api/sesiones/${encodeURIComponent(token)}/asistencias/`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(datos)
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "No se pudo registrar la asistencia.");
        }
        
        localStorage.setItem(
            `asistencia_rut_${token}`,
            datos.rut
        );
        
        message.textContent =
            "Asistencia registrada. Dirígete a la tablet del encargado para firmar.";

        form.reset();
        form.hidden = true;
    } catch (error) {
        message.textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
});

loadSession();
