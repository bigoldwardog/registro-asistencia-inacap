const confirmacionSalida = document.getElementById('confirmar-salida');
document.getElementById('solicitar-salida').addEventListener('click', event => {
    if (typeof confirmacionSalida.showModal !== 'function') return;
    event.preventDefault();
    confirmacionSalida.showModal();
});
document.getElementById('cancelar-salida').addEventListener('click', () => {
    confirmacionSalida.close();
});
