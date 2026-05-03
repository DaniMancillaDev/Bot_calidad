"""
Admin personalizado — Panel de administración del sistema de calidad.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import RegistroDefecto, PerfilUsuario


# ============================================================
# ADMIN: Registros de Defectos
# ============================================================

@admin.register(RegistroDefecto)
class RegistroDefectoAdmin(admin.ModelAdmin):
    list_display   = ['id', 'fotos', 'modelo', 'linea', 'responsable', 'cantidad', 'turno', 'departamento', 'fecha_registro']
    list_filter    = ['turno', 'departamento', 'linea', 'fecha_registro']
    search_fields  = ['modelo', 'responsable', 'descripcion', 'fotos']
    date_hierarchy = 'fecha_registro'
    ordering       = ['-fecha_registro']
    readonly_fields = ['id', 'fotos', 'modelo', 'linea', 'cantidad',
                       'responsable', 'descripcion', 'turno', 'departamento',
                       'fecha_registro', 'user_id']

    def has_add_permission(self, request):
        return False  # Los registros solo los crea el bot

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Solo el admin puede borrar





# ============================================================
# ADMIN: Usuarios con Perfil de Turno
# ============================================================

class PerfilInline(admin.StackedInline):
    model  = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil y Turno'
    fields = ['turno', 'departamento', 'telegram_user_id']


class UserAdmin(BaseUserAdmin):
    inlines = [PerfilInline]
    list_display = ['username', 'first_name', 'last_name', 'email', 'get_turno', 'is_staff', 'is_active']
    list_filter  = ['is_staff', 'is_active', 'perfil__turno']

    def get_turno(self, obj):
        try:
            return f'Turno {obj.perfil.turno}'
        except PerfilUsuario.DoesNotExist:
            return '—'
    get_turno.short_description = 'Turno'


# Reemplazar el UserAdmin por defecto con el personalizado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# ============================================================
# Personalización del Admin
# ============================================================
admin.site.site_header = '🏭 Panel de Calidad'
admin.site.site_title  = 'Calidad Admin'
admin.site.index_title = 'Gestión del Sistema de Calidad'
