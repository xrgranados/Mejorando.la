# -*- coding: utf-8 -*-

from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils import simplejson
from django.template import TemplateDoesNotExist
from django.template.defaultfilters import slugify
from akismet import Akismet
import image
from models import Setting, Video, VideoComentario, VideoComentarioForm, Curso, RegistroCurso, Conferencia
import datetime
import time
import requests
from utils import get_pais, get_ip, get_pais_by_ip


# La vista del home muestra el ultimo video destacado
# y 4 videos mas, + el horario localizado
def home(solicitud):
    # si no existe el valor aun en la base de datos
    try:
        es_vivo = Setting.objects.get(key='en_vivo').value
    except Setting.DoesNotExist:
        es_vivo = False

    # checar si estamos transmitiendo en vivo
    # regresar la vista de "vivo" de ser asi
    if ('live' in solicitud.GET and solicitud.GET['live'] == '1') or es_vivo:
        return render_to_response('live.html')

    # si no hay videos aun
    try:
        ultimo_video = Video.objects.all().filter(activado=True).latest('fecha')
    except Video.DoesNotExist:
        ultimo_video = None

    ultimos_4_videos = Video.objects.all().order_by('-fecha').filter(activado=True)[1:5]
    # plantilla
    return render_to_response('home.html', {
        'ultimo_video': ultimo_video,  # El ultimo video
        'videos': ultimos_4_videos,  # ultimos 4 videos
        'pais': get_pais(solicitud.META),  # el horario del programa localizado
        'timestamp': get_timestamp(),  # Obtiene el timestamp del sig. program.
        'cursos': Curso.objects.all().order_by('fecha').filter(activado=True, fecha__gte=datetime.datetime.now()),
        'cursos_geo': Curso.objects.all().order_by('fecha').filter(activado=True, fecha__gte=datetime.datetime.now(), pais=get_pais(solicitud.META))
    })


def siguiente_jueves_4pm(now):
    _4PM = datetime.time(hour=15)
    _JUE = 3  # Monday=0 for weekday()
    old_now = now
    now += datetime.timedelta((_JUE - now.weekday()) % 7)
    now = now.combine(now.date(), _4PM)
    if old_now >= now:
        now += datetime.timedelta(days=7)
    return now


def get_timestamp():
    now = datetime.datetime.now()
    sig_jueves = siguiente_jueves_4pm(now)
    return int(time.mktime(sig_jueves.timetuple()) * 1000)


# el archivo muestra todos los videos
# organizados por mes-año
def videos(solicitud):
    return render_to_response('videos.html', {
        'meses': [{
            'fecha': fecha,
            'videos': Video.objects.filter(fecha__year=fecha.year,
                                        fecha__month=fecha.month, activado=True).order_by('-fecha')
        } for fecha in Video.objects.filter(activado=True).dates('fecha', 'month', order='DESC')]
    })


def conferencias(solicitud):
    return render_to_response('conferencias.html', {
        'meses': [{
            'fecha': fecha,
            'confes': Conferencia.objects.filter(fecha__year=fecha.year, fecha__month=fecha.month, activado=True).order_by('-fecha')
        } for fecha in Conferencia.objects.filter(activado=True).dates('fecha', 'month', order='DESC')]
    })


# la entrada de video muestra el video
# del capitulo + comentarios + formulario de comentarios
# tambien procesa +1 comentario
def video(solicitud, video_slug):
    # video por slug (nombre)
    video = get_object_or_404(Video, slug=video_slug)

    # si son datos del formulario de comentarios
    if solicitud.method == 'POST':
        form = VideoComentarioForm(solicitud.POST)

        # validar los datos
        if(form.is_valid()):
            ip = get_ip(solicitud.META)

            # asignar el video
            comentario = form.save(commit=False)
            comentario.ip = ip
            comentario.video = video

            # detectar spam
            api = Akismet(key=settings.AKISMET_API_KEY,
                        blog_url=settings.AKISMET_URL,
                        agent=settings.AKISMET_AGENT)
            if api.verify_key():
                # por si el usuario esta detras de un proxy

                if not api.comment_check(comment=comentario.content.encode('utf-8'), data={
                        'user_ip': ip,
                        'user_agent': solicitud.META['HTTP_USER_AGENT']
                    }):

                    # guardar el video
                    comentario.save()
    else:
        form = VideoComentarioForm()

    comentarios = VideoComentario.objects.filter(video_id=video.id, activado=True).\
                                            order_by('-fecha', '-id')
    return render_to_response('video.html', {
        'video': video,  # datos del video particular
        'form': form,  # formulario de comentarios
        'comentarios': comentarios  # comentarios al video
    })


# plantilla de transmision en vivo
def live(solicitud):
    return render_to_response('live.html')


# volver a generar las imagenes de video
# en todos sus sizes
@login_required()
def regenerate(solicitud):
    for video in Video.objects.all():
        image.resize(image.THUMB, video.imagen)
        image.resize(image.SINGLE, video.imagen)
        image.resize(image.HOME, video.imagen)

    for curso in Curso.objects.all():
        image.resize(image.THUMB, curso.imagen)

    return redirect('/')


def locateme(solicitud):
    ip = solicitud.GET.get('ip')

    if ip:
        return HttpResponse(get_pais_by_ip(ip))

    return HttpResponse(get_pais(solicitud.META))


def hola(solicitud):

    if solicitud.method == 'POST' and solicitud.POST.get('email') and solicitud.POST.get('nombre'):
        pais = get_pais(solicitud.META)
        email = solicitud.POST['email']
        nombre = solicitud.POST['nombre']

        payload = {
            'email_address': email,
            'apikey': settings.MAILCHIMP_APIKEY,
            'merge_vars': {
                'FNAME': nombre,
                'OPTINIP': get_ip(solicitud.META),
                'OPTIN_TIME': time.time(),
                'PAIS': pais
            },
            'id': settings.MAILCHIMP_LISTID,
            'email_type': 'html'
        }

        r = requests.post('http://us4.api.mailchimp.com/1.3/?method=listSubscribe', simplejson.dumps(payload))

        return HttpResponse(r.text)

    return render_to_response('hola.html', {})


def conferencia(solicitud, template):
    if template:
        try:
            return render_to_response('%s.html' % template)
        except TemplateDoesNotExist:
            return render_to_response('default.html')

    try:
        return render_to_response('%s.html' % slugify(get_pais(solicitud.META)))
    except TemplateDoesNotExist:
        return render_to_response('default.html')


def track(solicitud, registro_id):
    registro = get_object_or_404(RegistroCurso, id=registro_id)

    return render_to_response('track.html', {'registro': registro})


def podcast(solicitud):
    return render_to_response('podcast.html', {
        'podcast_list': Video.objects.filter(podcast=True, activado=True).order_by('-fecha')
     })


def all(req, path):
    try:
        return render_to_response('%s.html' % path)
    except TemplateDoesNotExist:
        raise Http404
