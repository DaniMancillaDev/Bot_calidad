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
    
    # Nuevas rutas operativas
    path('operacion/',          views.panel_operativo,     name='panel_operativo'),
    path('api/check_updates/',  views.api_check_updates,   name='api_check_updates'),
    path('api/get_nuevos/',     views.api_get_nuevos,      name='api_get_nuevos'),
    path('api/registro/<int:registro_id>/delete/', views.api_delete_registro, name='api_delete_registro'),
    path('api/registro/<int:registro_id>/edit/', views.api_edit_registro, name='api_edit_registro'),
]
