from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.dashboard,           name='dashboard'),
    path('reportes/',           views.reportes,            name='reportes'),
    path('fotos/',              views.galeria_fotos,       name='galeria_fotos'),
    path('fotos/<int:numero>/', views.ver_foto,            name='ver_foto'),
    path('revisar/',            views.revisar_orientacion, name='revisar_orientacion'),
    path('api/detectar/',       views.api_detectar_orientacion, name='api_detectar_orientacion'),
    path('generar-excel/',      views.generar_excel,       name='generar_excel'),
]
