from django.urls import path
from . import views

app_name = 'workspace'

urlpatterns = [
    path('<uuid:session_uuid>/', views.workspace_ui, name='ui'),
    path('upload/', views.upload_workspace, name='upload'),
    path('status/<uuid:session_uuid>/', views.workspace_status, name='status'),
    path('api/drafts/', views.api_drafts, name='api_drafts'),
    path('api/draft/<int:draft_id>/', views.api_draft_detail, name='api_draft_detail'),
    path('api/validate/<uuid:session_uuid>/', views.api_validate_all, name='api_validate_all'),
    path('api/confirm/<uuid:session_uuid>/', views.api_confirm, name='api_confirm'),
]
