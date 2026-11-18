for (const boton of document.querySelectorAll('[data-visibilidad]')) {
    const campo = document.getElementById(boton.dataset.visibilidad);
    boton.addEventListener('click', () => {
        const oculto = campo.classList.toggle('perfil-oculto');
        boton.setAttribute('aria-pressed', String(!oculto));
    });
}

const guardarPerfil = document.getElementById('solicitar-guardar');
if (guardarPerfil) {
    const dialogo = document.getElementById('confirmar-cambios');
    const clave = dialogo.querySelector('[name="actual"]');
    guardarPerfil.addEventListener('click', () => {
        if (!guardarPerfil.form.reportValidity()) return;
        clave.disabled = false;
        dialogo.showModal();
        clave.focus();
    });
    document.getElementById('cancelar-cambios').addEventListener('click', () => dialogo.close());
    dialogo.addEventListener('close', () => { clave.value = ''; clave.disabled = true; });
}
