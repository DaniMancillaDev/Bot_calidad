from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('workflows/auth/tiene-acceso/', views.AuthTieneAccesoView.as_view(), name='workflow_auth_acceso'),

    # Usuario
    path('workflows/usuario/perfil/', views.UsuarioPerfilView.as_view(), name='workflow_usuario_perfil'),
    path('workflows/usuario/estadisticas/', views.UsuarioEstadisticasView.as_view(), name='workflow_usuario_estadisticas'),
    path('workflows/usuario/reporte/', views.RegistrosReporteView.as_view(), name='workflow_usuario_reporte'),
    path('workflows/usuario/reporte-turno/', views.ReporteTurnoView.as_view(), name='workflow_usuario_reporte_turno'),

    # Sesion
    path('workflows/sesion/cancelar/', views.SesionCancelarView.as_view(), name='workflow_sesion_cancelar'),
    path('workflows/sesion/limpiar/', views.SesionLimpiarView.as_view(), name='workflow_sesion_limpiar'),
    path('workflows/sesion/limpiar-fotos/', views.SesionLimpiarFotosView.as_view(), name='workflow_sesion_limpiar_fotos'),

    # Defecto Workflow Endpoints
    path('workflows/defecto/iniciar/', views.DefectoIniciarView.as_view(), name='workflow_defecto_iniciar'),
    path('workflows/defecto/adjuntar-evidencia/', views.DefectoAdjuntarEvidenciaView.as_view(), name='workflow_defecto_adjuntar'),
    path('workflows/defecto/responder/', views.DefectoResponderView.as_view(), name='workflow_defecto_responder'),

    # Exportaciones (ZIP)
    path('export/turnos/', views.ExportTurnosView.as_view(), name='export_turnos'),
    path('export/operadores/', views.ExportOperadoresView.as_view(), name='export_operadores'),
    path('export/evidencia/info/', views.ExportEvidenciaInfoView.as_view(), name='export_evidencia_info'),
    path('export/evidencia/', views.ExportEvidenciaView.as_view(), name='export_evidencia'),
]
