const menuCuenta = document.getElementById('menu-perfil');
const dialogoSalida = document.getElementById('confirmar-salida');
document.addEventListener('click', event => {
    if (!menuCuenta.contains(event.target)) menuCuenta.open = false;
});
document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menuCuenta.open) {
        menuCuenta.open = false;
        menuCuenta.querySelector('summary').focus();
    }
});
document.getElementById('solicitar-salida').addEventListener('click', event => {
    if (typeof dialogoSalida.showModal !== 'function') return;
    event.preventDefault();
    menuCuenta.open = false;
    dialogoSalida.showModal();
});
document.getElementById('cancelar-salida').addEventListener('click', () => dialogoSalida.close());
