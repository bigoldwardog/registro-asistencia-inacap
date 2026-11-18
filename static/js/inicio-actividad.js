(() => {
    const panel = document.getElementById('inicio-actividad');
    const form = document.getElementById('inicio-actividad-form');
    const selector = document.getElementById('anfitrion-efectivo');
    const canvas = document.getElementById('firma-inicio');
    const ctx = canvas.getContext('2d');
    const feedback = document.getElementById('inicio-actividad-feedback');
    let sesion = null, anfitriones = [], tinta = false, dibujando = false;
    const limpiar = () => { ctx.clearRect(0,0,canvas.width,canvas.height); tinta = false; };
    const punto = event => { const r=canvas.getBoundingClientRect(); return [(event.clientX-r.left)*canvas.width/r.width,(event.clientY-r.top)*canvas.height/r.height]; };
    canvas.addEventListener('pointerdown', event => { event.preventDefault(); canvas.setPointerCapture(event.pointerId); dibujando=true; ctx.beginPath(); ctx.moveTo(...punto(event)); ctx.lineWidth=3; ctx.lineCap='round'; ctx.strokeStyle='#111'; });
    canvas.addEventListener('pointermove', event => { if(!dibujando)return; event.preventDefault(); ctx.lineTo(...punto(event)); ctx.stroke(); tinta=true; });
    for(const nombre of ['pointerup','pointercancel','lostpointercapture']) canvas.addEventListener(nombre,()=>{dibujando=false;});
    document.getElementById('limpiar-firma-inicio').addEventListener('click',limpiar);
    function datosAnfitrion() {
        const elegido=anfitriones.find(a=>String(a.id)===selector.value);
        document.getElementById('anfitrion-efectivo-datos').textContent=elegido ? `${elegido.nombre} · ${elegido.sede} · ${elegido.area}` : '';
    }
    selector.addEventListener('change',()=>{limpiar(); datosAnfitrion();});
    function opciones() {
        selector.replaceChildren(new Option('Selecciona el anfitrión presente',''));
        for(const a of anfitriones) selector.add(new Option(a.nombre,a.id));
        if(sesion?.anfitrion_previsto_id) selector.value=String(sesion.anfitrion_previsto_id);
        datosAnfitrion();
    }
    fetch('/api/configuracion-sesiones/').then(r=>r.json()).then(datos=>{anfitriones=datos.anfitriones||[]; opciones();}).catch(()=>{feedback.textContent='No se pudo cargar la lista de anfitriones. Recarga para reintentar.';});
    window.addEventListener('sesion-cargada',event=>{
        const nueva=event.detail;
        if(sesion?.id!==nueva.id) { limpiar(); form.reset(); feedback.textContent=''; sesion=nueva; opciones(); }
        else sesion=nueva;
        panel.hidden=nueva.estado!=='PROGRAMADA' || !nueva.permisos.crear;
        const texto=document.getElementById('programacion-detalle');
        texto.textContent=nueva.fecha_programada ? `Programada: ${new Date(nueva.fecha_programada).toLocaleString('es-CL',{timeZone:'America/Santiago',dateStyle:'short',timeStyle:'short'})} · Creada por: ${nueva.creador} · Anfitrión: ${nueva.anfitrion}` : '';
    });
    form.addEventListener('submit',async event=>{
        event.preventDefault();
        if(!sesion || sesion.estado!=='PROGRAMADA')return;
        if(!tinta){feedback.textContent='El anfitrión debe dibujar su firma antes de iniciar.';return;}
        const boton=document.getElementById('confirmar-inicio'); boton.disabled=true;
        const id=sesion.id;
        try {
            const respuesta=await fetch(`/api/sesiones/${id}/iniciar/`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':form.querySelector('[name="csrfmiddlewaretoken"]').value},body:JSON.stringify({anfitrion_id:selector.value,rut:document.getElementById('anfitrion-rut').value,firma:canvas.toDataURL('image/png')})});
            const datos=await respuesta.json(); if(!respuesta.ok)throw new Error(datos.error||'No se pudo iniciar.');
            limpiar(); panel.hidden=true; await loadSessions(id);
            const aviso=document.getElementById('dashboard-feedback'); aviso.hidden=false; aviso.textContent='Actividad iniciada. La firma del anfitrión quedó registrada primero y el QR ya admite asistentes.';
        } catch(error) {feedback.textContent=error.message;}
        finally {boton.disabled=false;}
    });
})();
