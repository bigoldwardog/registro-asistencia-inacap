"""Documentos imprimibles basados en los formatos físicos facilitados por el cliente."""
import io
import math
from pathlib import Path
from xml.sax.saxutils import escape
from datetime import datetime
from django.conf import settings
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.worksheet.pagebreak import Break
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Image, Spacer, PageBreak
from reportlab.lib.pagesizes import A4
from .domain import fecha_chile, json_guardado, EPP, PANOL, ErrorFormulario
from .models import Asistencias, Firmas

FORMATOS = Path(settings.BASE_DIR) / 'database/formatos'
ANCHO = A4[0] - 72


def seguro(valor):
    import re
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(valor or ''))


def fecha(valor, solo_hora=False):
    if not valor:
        return '' if not solo_hora else 'Pendiente de cierre'
    try:
        v = datetime.fromisoformat(fecha_chile(valor))
        return v.strftime('%H:%M' if solo_hora else '%d/%m/%Y')
    except (ValueError, TypeError):
        return seguro(valor)


def construir_documento(sesion):
    """Un mismo contenido estructurado alimenta PDF y Excel, sin interpretar nombres."""
    nombre = sesion.plantilla.nombre
    if nombre in (EPP, PANOL):
        raise ErrorFormulario('La adaptación de documentos de pañol y EPP está pendiente. Exporta las demás actividades por separado.', 409)
    valores = json_guardado(sesion.campos_valores_json, dict)
    contexto = getattr(sesion, 'contexto', None)
    sede = contexto.sede.nombre if contexto else valores.get('sede', '')
    area = contexto.area.nombre if contexto else valores.get('area_o_tematica', '')
    asistentes = list(Asistencias.objects.filter(sesion=sesion).order_by('fecha_registro', 'id'))
    firmas = {f.asistencia_id: bytes(f.imagen) for f in Firmas.objects.filter(asistencia__sesion=sesion)}
    programacion = getattr(sesion, 'programacion', None)
    if programacion and programacion.fecha_firma:
        from types import SimpleNamespace
        datos = json_guardado(programacion.datos_anfitrion_json, dict)
        anfitrion_firmante = SimpleNamespace(id=-sesion.pk, nombre_registrado=datos.get('nombre',''),
            rut_registrado=datos.get('rut',''), cargo_registrado='Anfitrión', correo_registrado=datos.get('correo',''),
            telefono_registrado=datos.get('telefono',''), campos_participante_json='{}', estado='FIRMADO')
        asistentes.insert(0, anfitrion_firmante)
        firmas[anfitrion_firmante.id] = bytes(programacion.firma_anfitrion)
    bloques = []
    def titulo(texto): bloques.append({'tipo': 'titulo', 'texto': texto})
    def tabla(filas, anchos=None, cabecera=False, firma=False):
        bloques.append({'tipo': 'tabla', 'filas': filas, 'anchos': anchos, 'cabecera': cabecera, 'firmas': firma})
    def campos(filas): tabla([[k, v] for k, v in filas], [0.30, 0.70])
    def parrafo(texto): bloques.append({'tipo': 'parrafo', 'texto': texto})
    def seccion(etiqueta, valor): titulo(etiqueta); tabla([[valor or '']], [1])
    def participantes(estilo='acta'):
        if estilo == 'visita':
            encabezado = ['N°', 'RUT', 'Nombre', 'Firma asistencia']; anchos = [.06, .20, .44, .30]
        elif estilo == 'actividad':
            encabezado = ['N°', 'Nombre participante', 'RUT participante', 'Cargo', 'Firma asistencia']; anchos = [.06,.30,.20,.18,.26]
        elif estilo == 'registro':
            encabezado = ['N°', 'Nombre', 'RUT', 'Teléfono', 'Firma']; anchos = [.06,.30,.18,.20,.26]
        else:
            encabezado = ['Nombre', 'Cargo / Carrera', 'Firma']; anchos = [.43,.27,.30]
        filas = [encabezado]
        for indice, a in enumerate(asistentes, 1):
            firma = {'imagen': firmas[a.id]} if a.id in firmas else ('Pendiente de firma' if a.estado != 'FIRMADO' else 'Firma no disponible')
            if estilo == 'visita': fila = [indice, a.rut_registrado, a.nombre_registrado, firma]
            elif estilo == 'actividad': fila = [indice, a.nombre_registrado, a.rut_registrado, a.cargo_registrado, firma]
            elif estilo == 'registro': fila = [indice, a.nombre_registrado, a.rut_registrado, a.telefono_registrado, firma]
            else: fila = [a.nombre_registrado, a.cargo_registrado, firma]
            filas.append(fila)
        if not asistentes: filas.append(['Sin asistentes registrados'] + [''] * (len(encabezado)-1))
        tabla(filas, anchos, cabecera=True, firma=True)
    titulo_documento = {
        'Registro de asistencia': 'REGISTRO DE ASISTENCIA',
        'Registro de participación en actividades': 'REGISTRO DE PARTICIPACIÓN EN ACTIVIDADES',
        'Nómina de estudiantes para visita': 'NÓMINA DE ESTUDIANTES',
        'Seguro escolar en terreno': 'SEGURO ESCOLAR EN ACTIVIDADES EN TERRENO',
        'Entrevista con estudiante': 'ACTA DE ENTREVISTA CON ESTUDIANTE',
        'Acta de reunión': 'ACTA DE REUNIÓN',
        'Acta de reunión detallada': 'ACTA REUNIÓN',
        'Solicitud de seguro para proyecto de título': 'SOLICITUD DE SEGURO PARA PROYECTO DE TÍTULO',
    }.get(nombre)
    if not titulo_documento:
        raise ErrorFormulario('Esta plantilla aún no tiene un formato de documento configurado.', 409)
    horario = fecha(sesion.fecha_inicio, True) + ' - ' + fecha(sesion.fecha_cierre, True)
    if nombre == 'Registro de asistencia':
        campos([('NOMBRE ACTIVIDAD', sesion.nombre), ('TEMA', valores.get('tema', '')), ('FECHA', fecha(sesion.fecha_inicio)), ('HORARIO', horario), ('LUGAR', valores.get('lugar', ''))]); participantes('registro')
    elif nombre == 'Registro de participación en actividades':
        parrafo('ÁREA ' + area)
        campos([('Institución', valores.get('institucion', '')), ('Sede/unidad de Casa Central', sede), ('Actividad', sesion.nombre), ('Fecha', fecha(sesion.fecha_inicio))])
        titulo('PARTICIPANTES'); participantes('actividad')
        seccion('Temas tratados en actividad', valores.get('temas_tratados', ''))
        seccion('Observaciones y/o acuerdos', valores.get('observaciones_y_acuerdos', ''))
    elif nombre in ('Nómina de estudiantes para visita', 'Seguro escolar en terreno'):
        if nombre == 'Seguro escolar en terreno':
            parrafo(f'{sede}, {fecha(sesion.fecha_inicio)}')
            parrafo('Señor(a): ' + valores.get('contacto_de_empresa', ''))
            parrafo(valores.get('cargo_del_contacto', ''))
            parrafo('Presente')
            parrafo('Mat.: Seguro Escolar en actividades en terreno')
            parrafo(f"Junto con saludar cordialmente, agradezco a usted permitir a nuestros estudiantes de la carrera {valores.get('carrera', '')}, de la asignatura {valores.get('asignatura', '')}, acceder a sus instalaciones para complementar sus clases y observación en terreno, como parte de sus actividades académicas del semestre {valores.get('semestre', '')}.")
            parrafo('Junto con ello, informo a usted que dichas actividades son consideradas clases y, por lo tanto, cada estudiante del listado adjunto, en caso de accidentes en actividad académica se encuentra protegido por la Ley N° 16.744, artículo 3, Decreto N° 313/72 del Ministerio del Trabajo y Prevención Social: Subsecretaría de Previsión Social.')
            parrafo('Sin otro particular se despide atentamente,')
            parrafo('Firma de autoridad institucional: __________________________')
            bloques.append({'tipo': 'pagina'})
            titulo('NÓMINA DE ESTUDIANTES')
        parrafo('ÁREA ' + area); parrafo('INACAP - ' + sede)
        campos([('Lugar', valores.get('lugar', '')), ('Docente', valores.get('docente') or (sesion.anfitrion.nombre if sesion.anfitrion else '')), ('Fecha', fecha(sesion.fecha_inicio)), ('Horario', horario), ('Empresa', valores.get('empresa', ''))])
        participantes('visita')
    elif nombre == 'Solicitud de seguro para proyecto de título':
        titulo('DATOS DE LA EMPRESA'); campos([('Nombre o Razón Social', valores.get('razon_social', '')), ('R.U.T.', valores.get('rut_empresa', '')), ('Dirección', valores.get('direccion_empresa', '')), ('Giro', valores.get('giro', ''))])
        for indice, a in enumerate(asistentes, 1):
            titulo(f'DATOS ESTUDIANTE N° {indice}')
            datos = json_guardado(a.campos_participante_json, dict)
            campos([('Nombre', a.nombre_registrado), ('R.U.N.', a.rut_registrado), ('Correo', a.correo_registrado), ('Teléfono', a.telefono_registrado), ('Carrera', datos.get('carrera') or a.cargo_registrado)])
        titulo('PROYECTO DE TÍTULO'); campos([('Nombre', valores.get('nombre_del_proyecto', '')), ('Descripción y/o Problemática', valores.get('descripcion_y_problematica', ''))])
        titulo('DATOS ENCARGADO DE LA EMPRESA'); campos([('Nombre', valores.get('encargado_de_empresa', '')), ('Correo', valores.get('correo_encargado', '')), ('Teléfono', valores.get('telefono_encargado', '')), ('Cargo', valores.get('cargo_encargado', ''))])
        titulo('PERÍODO'); tabla([['Fecha inicio', 'Fecha término'], [valores.get('fecha_inicio_proyecto', ''), valores.get('fecha_termino_proyecto', '')]], [.5,.5], True)
        titulo('DATOS PROFESOR GUÍA'); campos([('Nombre', valores.get('profesor_guia', '')), ('Cargo', valores.get('cargo_profesor_guia', '')), ('Correo', valores.get('correo_profesor_guia', ''))])
        titulo('FIRMAS DE ASISTENCIA'); participantes()
    else:
        if nombre == 'Acta de reunión detallada':
            campos([('N° Acta', valores.get('numero_de_acta', '')), ('Fecha', fecha(sesion.fecha_inicio)), ('Lugar de reunión', valores.get('lugar', '')), ('Responsable del Acta', valores.get('responsable_del_acta', '')), ('Sede', sede)])
        else:
            campos([('Sede', sede), ('Tema/Asunto', valores.get('tema_o_asunto') or sesion.nombre), ('Asistentes', '\n'.join(a.nombre_registrado + (': ' + a.cargo_registrado if a.cargo_registrado else '') for a in asistentes)), ('Lugar de reunión', valores.get('lugar', ''))])
        tabla([['Fecha de reunión', fecha(sesion.fecha_inicio), 'Hora inicio', fecha(sesion.fecha_inicio, True), 'Hora término', fecha(sesion.fecha_cierre, True)]], [.18,.18,.15,.15,.15,.19])
        if nombre == 'Entrevista con estudiante':
            seccion('DESARROLLO DE LA ENTREVISTA', valores.get('desarrollo_de_la_entrevista', ''))
        elif nombre == 'Acta de reunión':
            tabla([['N°', 'ÁREA / TEMÁTICA', 'TEMAS TRATADOS / ACUERDOS', 'Responsable / Fecha límite'], [1, valores.get('area_o_tematica', ''), '\n\n'.join(etiqueta + '\n' + valores.get(campo, '') for etiqueta, campo in [('Objetivo de la reunión','objetivo_de_la_reunion'), ('Temas tratados','temas_tratados'), ('Acuerdos y compromisos','acuerdos_y_compromisos')]), valores.get('responsables_y_fechas_limite', '')]], [.06,.20,.49,.25], True)
            campos([('Fecha próxima reunión', valores.get('fecha_proxima_reunion', '')), ('Minuta realizada por', valores.get('minuta_realizada_por', ''))])
        titulo('PARTICIPANTES'); participantes()
        if nombre == 'Acta de reunión detallada':
            seccion('MINUTA REUNIÓN', valores.get('minuta_de_reunion', ''))
            seccion('OBJETIVO DEL CONVERSATORIO', valores.get('objetivo_del_conversatorio', ''))
            seccion('METODOLOGÍA DEL CONVERSATORIO', valores.get('metodologia_del_conversatorio', ''))
    return {'titulo': titulo_documento, 'bloques': bloques, 'sesion': sesion, 'asistentes': asistentes,
            'firmas': firmas, 'logo': 'logo-visita.png' if nombre in ('Seguro escolar en terreno','Nómina de estudiantes para visita','Registro de participación en actividades') else 'logo-acta.png'}


def pdf_documentos(documentos):
    salida = io.BytesIO()
    estilo = ParagraphStyle('texto', fontName='Helvetica', fontSize=9, leading=12, spaceAfter=6, wordWrap='CJK')
    titulo = ParagraphStyle('titulo', parent=estilo, fontName='Helvetica-Bold', fontSize=11, leading=14, alignment=1, spaceBefore=10, spaceAfter=9, keepWithNext=True)
    contenido = []
    def texto(v): return Paragraph(escape(seguro(v)).replace('\n', '<br/>'), estilo)
    def imagen(datos):
        try:
            reader = ImageReader(io.BytesIO(datos)); w,h = reader.getSize(); factor = min(110/w, 42/h)
            return Image(io.BytesIO(datos), width=w*factor, height=h*factor)
        except Exception:
            return texto('Firma no legible')
    for indice, documento in enumerate(documentos):
        if indice: contenido.append(PageBreak())
        logo = FORMATOS / documento['logo']
        if logo.exists():
            reader=ImageReader(str(logo)); w,h=reader.getSize(); contenido.append(Image(str(logo), width=90, height=90*h/w, hAlign='LEFT'))
        contenido.append(Paragraph(escape(documento['titulo']), titulo))
        for bloque in documento['bloques']:
            if bloque['tipo'] == 'pagina': contenido.append(PageBreak()); continue
            if bloque['tipo'] == 'titulo': contenido.append(Paragraph(escape(bloque['texto']), titulo)); continue
            if bloque['tipo'] == 'parrafo': contenido.append(texto(bloque['texto'])); continue
            filas = [[imagen(v['imagen']) if isinstance(v,dict) else texto(v) for v in fila] for fila in bloque['filas']]
            anchos = [ANCHO*f for f in bloque['anchos']] if bloque['anchos'] else None
            tabla = Table(filas, colWidths=anchos, repeatRows=1 if bloque['cabecera'] else 0, hAlign='LEFT', splitByRow=1, splitInRow=1)
            comandos=[('GRID',(0,0),(-1,-1),.5,colors.HexColor('#777777')), ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6), ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]
            if bloque['cabecera']: comandos += [('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')), ('VALIGN',(0,0),(-1,-1),'MIDDLE')]
            tabla.setStyle(TableStyle(comandos)); contenido += [tabla, Spacer(1,8)]
    def pie(canvas, doc):
        canvas.saveState(); canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#666666')); canvas.drawRightString(A4[0]-36,22,f'Página {doc.page}'); canvas.restoreState()
    doc = SimpleDocTemplate(salida,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=32,bottomMargin=36,title='Registros de asistencia',author='INACAP')
    doc.build(contenido, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()


def xlsx_documentos(documentos):
    """Hojas imprimibles con valores de texto y firmas incrustadas, sin fórmulas de usuario."""
    libro=Workbook(); libro.remove(libro.active)
    borde=Border(*( [Side(style='thin', color='777777')]*4 ))
    for indice,d in enumerate(documentos,1):
        s=d['sesion']
        if s.plantilla.nombre == 'Registro de asistencia':
            # Mantener bordes, combinación de celdas y dimensiones de la plantilla real.
            original=load_workbook(FORMATOS/'Registro de Asistencia.xlsx').active
            hoja=libro.create_sheet(f'{indice} Registro')
            from copy import copy
            for fila in original:
                for celda in fila:
                    destino=hoja.cell(celda.row,celda.column,celda.value)
                    destino.font=copy(celda.font); destino.fill=copy(celda.fill); destino.border=copy(celda.border)
                    destino.alignment=copy(celda.alignment); destino.number_format=celda.number_format; destino.protection=copy(celda.protection)
                    if celda.value is not None: destino.data_type='s' if isinstance(celda.value,str) else 'n'
            for rango in original.merged_cells.ranges: hoja.merge_cells(str(rango))
            for k,v in original.column_dimensions.items(): hoja.column_dimensions[k]=copy(v)
            for k,v in original.row_dimensions.items(): hoja.row_dimensions[k]=copy(v)
            valores=json_guardado(s.campos_valores_json,dict)
            for celda,valor in {'A1':'REGISTRO DE ASISTENCIA','C2':s.nombre,'C3':valores.get('tema',''),'C4':fecha(s.fecha_inicio),'C5':fecha(s.fecha_inicio,True)+' - '+fecha(s.fecha_cierre,True),'C6':valores.get('lugar','')}.items():
                hoja[celda]=seguro(valor); hoja[celda].data_type='s'; hoja[celda].alignment=Alignment(wrap_text=True, vertical='center')
            for n,a in enumerate(d['asistentes'],9):
                for col,valor in enumerate([n-8,a.nombre_registrado,a.rut_registrado,a.telefono_registrado],1):
                    celda=hoja.cell(n,col,seguro(valor)); celda.data_type='s'; celda.number_format='@'; celda.border=borde; celda.alignment=Alignment(wrap_text=True,vertical='center')
                hoja.cell(n,5).border=borde; hoja.row_dimensions[n].height=42
                if a.id in d['firmas']: agregar_firma_excel(hoja,d['firmas'][a.id],n,5,150,46)
            hoja.print_title_rows='1:8'; hoja.print_area=f'A1:E{max(27,8+len(d["asistentes"]))}'
        else:
            hoja=libro.create_sheet(f'{indice} Documento')
            for col in range(1,25): hoja.column_dimensions[__import__('openpyxl').utils.get_column_letter(col)].width=3
            logo=ExcelImage(FORMATOS/d['logo']); factor=90/logo.width
            logo.width=90; logo.height*=factor; hoja.add_image(logo,'A1')
            hoja.row_dimensions[1].height=max(30,logo.height*.75+6)
            fila=3
            def escribir(valores, proporciones=None, cabecera=False, firmas=False, dividir=True):
                nonlocal fila
                proporciones=proporciones or [1/len(valores)]*len(valores)
                if dividir:
                    import textwrap
                    trozos=[]
                    for valor, proporcion in zip(valores, proporciones):
                        if isinstance(valor,dict): trozos.append([valor]); continue
                        ancho=max(8,int(round(proporcion*24)*3.5))
                        lineas=[parte for linea in seguro(valor).split('\n') for parte in (textwrap.wrap(linea,width=ancho) or [''])]
                        trozos.append(['\n'.join(lineas[i:i+18]) for i in range(0,len(lineas),18)])
                    if max(map(len,trozos), default=1)>1:
                        for i in range(max(map(len,trozos))):
                            escribir([partes[i] if i<len(partes) else '' for partes in trozos],proporciones,cabecera,firmas,False)
                        return
                inicio=1; alto=22
                for i,valor in enumerate(valores):
                    fin=24 if i==len(valores)-1 else min(24,inicio+max(1,round(proporciones[i]*24))-1)
                    if fin>inicio: hoja.merge_cells(start_row=fila,start_column=inicio,end_row=fila,end_column=fin)
                    celda=hoja.cell(fila,inicio)
                    for col in range(inicio,fin+1): hoja.cell(fila,col).border=borde
                    if isinstance(valor,dict):
                        agregar_firma_excel(hoja,valor['imagen'],fila,inicio,max(45,(fin-inicio+1)*19),42); alto=max(alto,42)
                    else:
                        celda.value=seguro(valor); celda.data_type='s'; celda.number_format='@'
                        lineas=sum(max(1,math.ceil(len(line)/max(8,(fin-inicio+1)*3.5))) for line in celda.value.split('\n'))
                        alto=max(alto,16*lineas+12)
                    celda.font=Font(name='Arial',size=10,bold=cabecera)
                    celda.alignment=Alignment(wrap_text=True,vertical='center')
                    if cabecera: celda.fill=PatternFill('solid',fgColor='EEEEEE')
                    inicio=fin+1
                hoja.row_dimensions[fila].height=min(409,alto)
                fila+=1
            escribir([d['titulo']], [1],True)
            for bloque in d['bloques']:
                if bloque['tipo']=='pagina': hoja.row_breaks.append(Break(id=fila-1)); continue
                if bloque['tipo']=='titulo': escribir([bloque['texto']],[1],True)
                elif bloque['tipo']=='parrafo': escribir([bloque['texto']],[1])
                else:
                    inicio_tabla=fila
                    for numero,valores in enumerate(bloque['filas']): escribir(valores,bloque['anchos'],bloque['cabecera'] and numero==0,bloque['firmas'])
                    if bloque['firmas'] and not hoja.print_title_rows: hoja.print_title_rows=f'{inicio_tabla}:{inicio_tabla}'
                fila+=1
            hoja.print_area=f'A1:X{fila-1}'
        hoja.sheet_view.showGridLines=False
        hoja.sheet_properties.pageSetUpPr.fitToPage=True
        hoja.page_setup.paperSize=hoja.PAPERSIZE_A4; hoja.page_setup.orientation='portrait'; hoja.page_setup.fitToWidth=1; hoja.page_setup.fitToHeight=0
        hoja.page_margins.left=.35; hoja.page_margins.right=.35; hoja.page_margins.top=.4; hoja.page_margins.bottom=.4
        hoja.print_options.horizontalCentered=True
        hoja.oddFooter.right.text='Página &P de &N'
    salida=io.BytesIO(); libro.save(salida); return salida.getvalue()


def agregar_firma_excel(hoja,datos,fila,columna,ancho,alto):
    try:
        imagen=ExcelImage(io.BytesIO(datos)); factor=min(ancho/imagen.width,alto/imagen.height)
        imagen.width*=factor; imagen.height*=factor
        hoja.add_image(imagen,f'{__import__("openpyxl").utils.get_column_letter(columna)}{fila}')
    except (OSError,ValueError,SyntaxError):
        hoja.cell(fila,columna,'Firma no legible')
