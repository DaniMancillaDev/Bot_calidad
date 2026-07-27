from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='calidad/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('calidad.urls')),
    path('workspace/', include('workspace.urls')),
    path('api/v1/', include('calidad.api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
