from django.urls import path
from . import views
from . import views_importacion
from . import views_pending

urlpatterns = [
    path('',                    views.dashboard,           name='dashboard'),
    path('reportes/',           views.reportes,            name='reportes'),
    path('fotos/',              views.galeria_fotos,       name='galeria_fotos'),
    path('fotos/<int:numero>/', views.ver_foto,            name='ver_foto'),
    path('evidencias-pendientes/', views_pending.pending_evidence, name='pending_evidence'),
    path('evidencias-pendientes/grupos/nuevo/', views_pending.create_pending_group_draft, name='create_pending_group_draft'),
    path('evidencias-pendientes/grupos/<uuid:group_id>/actualizar/', views_pending.update_pending_group_view, name='update_pending_group'),
    path('evidencias-pendientes/excluidas/recuperar/', views_pending.restore_pending_evidence_view, name='restore_pending_evidence'),
    path('evidencias-pendientes/excluir/', views_pending.exclude_pending_evidence_view, name='exclude_pending_evidence'),
    path(
        'evidencias-pendientes/contactos/<int:contact_id>/',
        views_pending.rename_pending_contact,
        name='rename_pending_contact',
    ),
    path(
        'evidencias-pendientes/<uuid:evidence_id>/imagen/',
        views_pending.pending_evidence_image,
        name='pending_evidence_image',
    ),
    path('revisar/',            views.revisar_orientacion, name='revisar_orientacion'),
    path('revisar/box-condition/', views.revisar_box_condition, name='revisar_box_condition'),
    path('api/detectar/',       views.api_detectar_orientacion, name='api_detectar_orientacion'),
    path('generar-excel/',      views.generar_excel,       name='generar_excel'),
    path('generar-excel-box-condition/', views.generar_excel_box_condition, name='generar_excel_box_condition'),
    path('api/lotes-importacion/', views.api_lotes_importacion, name='api_lotes_importacion'),
    path('api/excel_status/<str:task_id>/', views.api_excel_status, name='api_excel_status'),
    path('api/download_excel/<str:task_id>/', views.api_download_excel, name='api_download_excel'),
    
    # Importación V1
    path('importacion/',                views_importacion.importacion_iniciar,   name='importacion_iniciar'),
    path('importacion/workspace/',      views_importacion.importacion_workspace, name='importacion_workspace'),
    path('importacion/api/action/',     views_importacion.importacion_update_ajax, name='importacion_update_ajax'),
    path('importacion/api/confirmar/',  views_importacion.importacion_confirmar, name='importacion_confirmar'),
    path('importacion/cancelar/',       views_importacion.importacion_cancelar, name='importacion_cancelar'),
    
    # Nuevas rutas operativas
    path('operacion/',          views.panel_operativo,     name='panel_operativo'),
    path('api/check_updates/',  views.api_check_updates,   name='api_check_updates'),
    path('api/get_nuevos/',     views.api_get_nuevos,      name='api_get_nuevos'),
    path('api/registro/<int:registro_id>/delete/', views.api_delete_registro, name='api_delete_registro'),
    path('api/registro/<int:registro_id>/edit/', views.api_edit_registro, name='api_edit_registro'),
    
    # Diccionario AI
    path('diccionario/', views.gestionar_diccionario, name='gestionar_diccionario'),
    path('api/diccionario/guardar/', views.api_guardar_diccionario, name='api_guardar_diccionario'),

    # Descargas directas
    path('descargar/txt/',  views.descargar_txt, name='descargar_txt'),
    path('descargar/zip/',  views.descargar_zip, name='descargar_zip'),
    
    # ==========================================================
    # API V2 (Centro de Revisión de Evidencias - SPA)
    # ==========================================================
    path('api/v2/lotes/', 
         __import__('calidad.api.endpoints_v2').api.endpoints_v2.api_get_lotes, 
         name='api_v2_lotes'),
    path('api/v2/lotes/<str:lote_id>/registros/', 
         __import__('calidad.api.endpoints_v2').api.endpoints_v2.api_get_registros_por_lote, 
         name='api_v2_registros_lote'),
    path('api/v2/registros/<int:registro_id>/', 
         __import__('calidad.api.endpoints_v2').api.endpoints_v2.api_registro_detail, 
         name='api_v2_patch_registro'),
    path('api/v2/evidencias/<int:evidencia_id>/rotar/', 
         __import__('calidad.api.endpoints_v2').api.endpoints_v2.api_rotar_evidencia, 
         name='api_v2_rotar_evidencia'),
    path('api/v2/evidencias/<int:evidencia_id>/', 
         __import__('calidad.api.endpoints_v2').api.endpoints_v2.api_evidencia_detail, 
         name='api_v2_evidencia_detail'),
    path('api/v2/evidencias/<int:evidencia_id>/restaurar/', 
         __import__('calidad.api.endpoints_v2').api.endpoints_v2.api_restore_evidencia, 
         name='api_v2_restore_evidencia'),
]
