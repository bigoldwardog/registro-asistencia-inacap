from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from datetime import datetime
from asistencia.domain import fecha_chile
from asistencia.models import (Usuarios, AccesoUsuario, Sesiones, Asistentes, Asistencias,
    ContextoSesion, ProgramacionSesion, Firmas, FirmasDevolucion, FirmasAdicionales)

class Command(BaseCommand):
    help = 'Revisión de solo lectura de relaciones y estados del registro de asistencia.'
    def handle(self, *args, **options):
        problemas = []
        if connection.vendor == 'sqlite':
            with connection.cursor() as c:
                if c.execute('PRAGMA quick_check').fetchall() != [('ok',)]: problemas.append('Integridad física SQLite')
                if c.execute('PRAGMA foreign_key_check').fetchall(): problemas.append('Claves foráneas SQLite')
        for modelo, campo, destino in [(AccesoUsuario,'usuario',Usuarios),(ContextoSesion,'sesion',Sesiones),
            (ProgramacionSesion,'sesion',Sesiones),(ProgramacionSesion,'creador',Usuarios),
            (ProgramacionSesion,'anfitrion_previsto',Usuarios),(ProgramacionSesion,'iniciada_por',Usuarios),
            (Asistencias,'sesion',Sesiones),(Asistencias,'asistente',Asistentes),
            (Firmas,'asistencia',Asistencias),(FirmasDevolucion,'asistencia',Asistencias),(FirmasAdicionales,'asistencia',Asistencias)]:
            cantidad = modelo.objects.exclude(**{campo+'_id__isnull':True}).exclude(**{campo+'_id__in':destino.objects.values('pk')}).count()
            if cantidad: problemas.append(f'{modelo._meta.db_table}.{campo}: {cantidad} referencias huérfanas')
        for s in Sesiones.objects.all():
            p = getattr(s,'programacion',None)
            for valor in (s.fecha_inicio, s.fecha_cierre):
                if valor and not fecha_chile(valor): problemas.append(f'Actividad {s.pk}: fecha inválida')
            if s.fecha_inicio and s.fecha_cierre and fecha_chile(s.fecha_inicio) and fecha_chile(s.fecha_cierre):
                if datetime.fromisoformat(fecha_chile(s.fecha_cierre)) < datetime.fromisoformat(fecha_chile(s.fecha_inicio)):
                    problemas.append(f'Actividad {s.pk}: cierre anterior al inicio')
            if s.estado == 'PROGRAMADA' and Asistencias.objects.filter(sesion=s).exists(): problemas.append(f'Actividad {s.pk}: registros antes del inicio')
            if s.estado == 'PROGRAMADA' and (s.fecha_inicio or s.fecha_cierre or s.anfitrion_id or not p): problemas.append(f'Actividad {s.pk}: programación inconsistente')
            if s.estado == 'ABIERTA' and (not s.fecha_inicio or not s.anfitrion_id or s.fecha_cierre): problemas.append(f'Actividad {s.pk}: inicio inconsistente')
            if s.estado == 'CERRADA' and (not s.fecha_inicio or not s.fecha_cierre): problemas.append(f'Actividad {s.pk}: cierre inconsistente')
            if p and s.estado != 'PROGRAMADA' and (not p.fecha_firma or not p.firma_anfitrion or not p.iniciada_por_id): problemas.append(f'Actividad {s.pk}: falta firma de inicio')
            if p and s.estado == 'PROGRAMADA' and p.fecha_firma: problemas.append(f'Actividad {s.pk}: firma de inicio prematura')
        for a in Asistencias.objects.all():
            firma = Firmas.objects.filter(asistencia=a).exists()
            if (a.estado == 'FIRMADO') != firma or (firma and not a.fecha_firma): problemas.append(f'Asistencia {a.pk}: estado y firma no coinciden')
        perfiles_faltantes = Usuarios.objects.filter(activo=1).exclude(pk__in=AccesoUsuario.objects.values('usuario_id')).count()
        if perfiles_faltantes: problemas.append(f'{perfiles_faltantes} cuentas activas sin perfil de acceso')
        if problemas:
            raise CommandError('\n'.join(problemas))
        self.stdout.write(self.style.SUCCESS('Integridad y estados correctos. No se modificaron datos.'))
