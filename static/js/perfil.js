const confirmacionSalida = document.getElementById('confirmar-salida');
document.getElementById('solicitar-salida').addEventListener('click', event => {
    if (typeof confirmacionSalida.showModal !== 'function') return;
    event.preventDefault();
    confirmacionSalida.showModal();
});
document.getElementById('cancelar-salida').addEventListener('click', () => {
    confirmacionSalida.close();
});

for (const boton of document.querySelectorAll('[data-visibilidad]')) {
    const campo = document.getElementById(boton.dataset.visibilidad);
    boton.addEventListener('click', () => {
        const oculto = campo.classList.toggle('perfil-oculto');
        boton.setAttribute('aria-pressed', String(!oculto));
    });
}
