"""Campos del anfitrión basados en las plantillas físicas del cliente.
Los datos y firmas de participantes siguen perteneciendo a cada asistencia.
"""
import unicodedata
from django.db import transaction
from .models import PlantillasSesion, CamposPlantilla

# etiqueta, tipo, obligatorio. Los campos narrativos se muestran como áreas de texto.
COMUNES = [("Sede", "texto", 0), ("Lugar", "texto", 1), ("Fecha de actividad", "fecha", 1), ("Hora inicio", "hora", 1), ("Hora término", "hora", 0)]
CATALOGO = [
 ("Registro de asistencia", "Formato compartido por Acta de Asistencia.xlsx y Registro de Asistencia.xlsx.", [("Tema", "texto", 1)] + COMUNES[1:]),
 ("Registro de participación en actividades", "Registro Asistencia Actividad.docx. Cada participante registra sus datos y firma por separado.", [("Institución", "texto", 1)] + COMUNES[:1] + [("Fecha de actividad", "fecha", 1), ("Temas tratados", "texto", 0), ("Observaciones y acuerdos", "texto", 0)]),
 ("Nómina de estudiantes para visita", "03 Nomina de estudiantes Visita.docx.", COMUNES[1:] + [("Empresa", "texto", 1), ("Docente", "texto", 1)]),
 ("Seguro escolar en terreno", "01 Carta Seguro Escolar en Terreno.docx, con nómina de asistencia asociada.", COMUNES[1:] + [("Empresa", "texto", 1), ("Contacto de empresa", "texto", 1), ("Cargo del contacto", "texto", 0), ("Carrera", "texto", 1), ("Asignatura", "texto", 1), ("Semestre", "texto", 1), ("Docente", "texto", 1)]),
 ("Entrevista con estudiante", "Acta de Entrevista Estudiante.docx.", [("Tema o asunto", "texto", 1)] + COMUNES + [("Desarrollo de la entrevista", "texto", 0)]),
 ("Acta de reunión", "Acta de Reunión.docx.", [("Tema o asunto", "texto", 1)] + COMUNES + [("Área o temática", "texto", 0), ("Objetivo de la reunión", "texto", 0), ("Temas tratados", "texto", 0), ("Acuerdos y compromisos", "texto", 0), ("Responsables y fechas límite", "texto", 0), ("Fecha próxima reunión", "fecha", 0), ("Minuta realizada por", "texto", 0)]),
 ("Acta de reunión detallada", "Acta de Reunión - Detallada.docx.", [("Número de acta", "texto", 1)] + COMUNES + [("Responsable del acta", "texto", 1), ("Minuta de reunión", "texto", 0), ("Objetivo del conversatorio", "texto", 0), ("Metodología del conversatorio", "texto", 0)]),
 ("Solicitud de seguro para proyecto de título", "00 Solciitud Seguro Proyecto Titulo.docx. Los datos de estudiantes corresponden a los participantes asociados.", [("Razón social", "texto", 1), ("RUT empresa", "texto", 1), ("Dirección empresa", "texto", 1), ("Giro", "texto", 0), ("Nombre del proyecto", "texto", 1), ("Descripción y problemática", "texto", 0), ("Encargado de empresa", "texto", 1), ("Correo encargado", "email", 0), ("Teléfono encargado", "texto", 0), ("Cargo encargado", "texto", 0), ("Fecha inicio proyecto", "fecha", 1), ("Fecha término proyecto", "fecha", 1), ("Profesor guía", "texto", 1), ("Cargo profesor guía", "texto", 0), ("Correo profesor guía", "email", 0)]),
 ("Entrega de elementos de protección personal", "02 Ficha entrega EPP Alumno.docx. Registra la recepción y devolución de los elementos con firmas independientes.", [("Lugar", "texto", 1), ("Empresa", "texto", 1), ("Fecha de ingreso", "fecha", 1), ("Hora de ingreso", "hora", 0), ("Elementos proporcionados", "texto", 1), ("Fecha de entrega", "fecha", 1), ("Fecha de devolución", "fecha", 0)]),
 ("Solicitud de materiales y equipo a Pañol", "04 Solicitud de Materiales - Pañol.xlsx. Indica materiales y cantidades. El alumno y el docente firman por separado.", [("Jornada", "texto", 1), ("Carrera", "texto", 1), ("Sección", "texto", 1), ("Docente", "texto", 1), ("Asignatura", "texto", 1), ("Lugar de uso", "texto", 1), ("Fecha de actividad", "fecha", 1), ("Materiales y cantidades", "texto", 1), ("Devolución y observaciones", "texto", 0)]),
]

def clave(etiqueta):
    return ''.join(c for c in unicodedata.normalize('NFKD', etiqueta) if not unicodedata.combining(c)).lower().replace(' ', '_')

AUTOMATICOS = {"fecha_de_actividad", "hora_inicio", "hora_termino",
               "fecha_de_ingreso", "hora_de_ingreso", "fecha_de_entrega"}
POSTERIORES = {"desarrollo_de_la_entrevista", "temas_tratados", "observaciones_y_acuerdos",
    "acuerdos_y_compromisos", "responsables_y_fechas_limite", "fecha_proxima_reunion",
    "minuta_realizada_por", "minuta_de_reunion", "devolucion_y_observaciones", "fecha_de_devolucion"}

def campos_por_etapa(campos):
    return [{**c, "etapa": "desarrollo" if c["nombre"] in POSTERIORES else "apertura"}
            for c in campos if c["nombre"] not in AUTOMATICOS]

@transaction.atomic
def cargar_catalogo():
    for nombre, descripcion, campos in CATALOGO:
        plantilla, _ = PlantillasSesion.objects.update_or_create(nombre=nombre, defaults={"descripcion": descripcion, "activa": 1})
        CamposPlantilla.objects.filter(plantilla=plantilla, nombre__in=AUTOMATICOS).delete()
        for orden, (etiqueta, tipo, obligatorio) in enumerate(campos):
            if clave(etiqueta) in AUTOMATICOS:
                continue
            CamposPlantilla.objects.update_or_create(plantilla=plantilla, nombre=clave(etiqueta), defaults={"etiqueta": etiqueta, "tipo": tipo, "obligatorio": obligatorio, "orden": orden})
    panol = PlantillasSesion.objects.get(nombre='Solicitud de materiales y equipo a Pañol')
    CamposPlantilla.objects.filter(plantilla=panol, nombre__in=['jornada', 'carrera', 'seccion']).delete()
    PlantillasSesion.objects.filter(nombre='Seminario de Informatica').update(activa=0)
    return len(CATALOGO)
