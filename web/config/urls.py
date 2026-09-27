from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from calidad.views import serve_protected_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='calidad/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('calidad.urls')),
    path('workspace/', include('workspace.urls')),
    path('api/v1/', include('calidad.api.urls')),
    # Proxy autenticado para /media/fotos/, /media/thumbs/, /media/proxies/
    re_path(r'^media-protegida/(?P<subpath>.+)$', serve_protected_media, name='media_protegida'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
