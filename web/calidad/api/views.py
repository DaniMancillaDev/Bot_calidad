import logging
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import status
from calidad.models import PerfilUsuario

logger = logging.getLogger(__name__)

class BotUser:
    is_authenticated = True
    is_active = True

class StaticApiKeyAuthentication(BaseAuthentication):
    """Autenticación simple para uso interno (Bot -> Web) vía BOT_API_KEY"""
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Token '):
            return None
        
        token = auth_header.split(' ')[1]
        expected_token = os.getenv('BOT_API_KEY', 'default-internal-secret-key-123')
        
        if token == expected_token:
            return (BotUser(), None)
        
        raise AuthenticationFailed('Invalid API Key')

class AuthTieneAccesoView(APIView):
    """
    Verifica si un telegram_user_id tiene acceso y devuelve su info básica.
    Usado por el bot en cada mensaje.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip()
            
            return Response({
                'tiene_acceso': True,
                'usuario': {
                    'telegram_user_id': p.telegram_user_id,
                    'turno': p.turno,
                    'departamento': p.departamento,
                    'rol': p.rol,
                    'username': p.usuario.username,
                    'nombre': nombre_completo or p.usuario.username,
                }
            })
        except PerfilUsuario.DoesNotExist:
            return Response({'tiene_acceso': False}, status=status.HTTP_404_NOT_FOUND)

class RegistrosReporteView(APIView):
    """
    GET /workflows/usuario/reporte/?telegram_id=XXX
    Devuelve la lista de registros del usuario (o del grupo si es admin)
    formateada para el bot.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from calidad.models import RegistroDefecto
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip() or p.usuario.username

            from django.utils import timezone
            from datetime import timedelta
            limite = timezone.now() - timedelta(hours=72)

            if p.rol == 'admin':
                qs = RegistroDefecto.objects.filter(turno=p.turno, departamento=p.departamento, fecha_registro__gte=limite)
            else:
                qs = RegistroDefecto.objects.filter(user_id=telegram_id, fecha_registro__gte=limite)

            qs = qs.order_by('-fecha_registro')

            # 1. Extraer listas de fotos por registro
            registros_con_fotos = []
            for r in qs:
                try:
                    raw_fotos = r.fotos
                    if isinstance(raw_fotos, str):
                        f_list = [int(x.strip()) for x in raw_fotos.split(',') if x.strip()]
                    elif isinstance(raw_fotos, list):
                        f_list = raw_fotos
                    else:
                        f_list = []
                except Exception:
                    f_list = []
                registros_con_fotos.append((r, f_list))

            # 2. Construir orden global (ascendente por fecha) para asignar IDs secuenciales
            fotos_globales = []
            for r, f_list in registros_con_fotos:
                for num in f_list:
                    fotos_globales.append((r.fecha_registro, r.id, num))
            
            from datetime import datetime
            fotos_globales.sort(key=lambda x: (x[0] if x[0] else datetime.min, x[2]))
            
            mapping = {}
            for i, item in enumerate(fotos_globales, 1):
                mapping[(item[1], item[2])] = i

            def formatear_rango_mapeado(r_id, fotos_list):
                if not fotos_list: return ""
                mapped_nums = sorted([mapping[(r_id, n)] for n in fotos_list if (r_id, n) in mapping])
                if not mapped_nums: return ""
                rangos = []
                inicio = fin = mapped_nums[0]
                for n in mapped_nums[1:]:
                    if n == fin + 1:
                        fin = n
                    else:
                        rangos.append(f"({inicio:02d}-{fin:02d})" if inicio != fin else f"({inicio:02d})")
                        inicio = fin = n
                rangos.append(f"({inicio:02d}-{fin:02d})" if inicio != fin else f"({inicio:02d})")
                return "".join(rangos)

            # 3. Construir respuesta
            registros = []
            for r, f_list in registros_con_fotos:

                registros.append({
                    'id': r.id,
                    'fotos': formatear_rango_mapeado(r.id, f_list), 
                    'modelo': (r.modelo or "").upper(),
                    'linea': (r.linea or "").upper(),
                    'cantidad': r.cantidad,
                    'responsable': (r.responsable or "").upper(),
                    'descripcion': (r.descripcion or "").upper(),
                    'fecha_hora': r.fecha_registro.strftime('%Y-%m-%d') if r.fecha_registro else '',
                    'turno': r.turno,
                    'departamento': r.departamento,
                })

            return Response({
                'usuario': nombre_completo,
                'turno': p.turno,
                'departamento': p.departamento,
                'rol': p.rol,
                'registros': registros,
            })
        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error en RegistrosReporteView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReporteTurnoView(APIView):
    """
    GET /workflows/usuario/reporte-turno/?telegram_id=XXX&turno=A&operador_id=YYY
    Admin-only. Genera reporte de un turno dado, filtrando por operador si se indica.
    operador_id puede ser 'todos' o un telegram_user_id.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        turno = request.query_params.get('turno')
        operador_id = request.query_params.get('operador_id')  # 'todos' o telegram_user_id

        if not telegram_id or not turno:
            return Response({'error': 'telegram_id and turno required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calidad.models import RegistroDefecto
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)

            if p.rol != 'admin':
                return Response({'error': 'Acceso restringido a administradores.'}, status=status.HTTP_403_FORBIDDEN)

            from django.utils import timezone
            from datetime import timedelta
            limite = timezone.now() - timedelta(hours=72)

            qs = RegistroDefecto.objects.filter(turno=turno, departamento=p.departamento, fecha_registro__gte=limite)
            if operador_id and operador_id != 'todos':
                qs = qs.filter(user_id=operador_id)
            qs = qs.order_by('fecha_registro')

            # 1. Extraer listas de fotos por registro
            registros_con_fotos = []
            for r in qs:
                try:
                    raw_fotos = r.fotos
                    if isinstance(raw_fotos, str):
                        f_list = [int(x.strip()) for x in raw_fotos.split(',') if x.strip()]
                    elif isinstance(raw_fotos, list):
                        f_list = raw_fotos
                    else:
                        f_list = []
                except Exception:
                    f_list = []
                registros_con_fotos.append((r, f_list))

            # 2. Construir orden global (ascendente por fecha)
            fotos_globales = []
            for r, f_list in registros_con_fotos:
                for num in f_list:
                    fotos_globales.append((r.fecha_registro, r.id, num))
            
            from datetime import datetime
            fotos_globales.sort(key=lambda x: (x[0] if x[0] else datetime.min, x[2]))
            
            mapping = {}
            for i, item in enumerate(fotos_globales, 1):
                mapping[(item[1], item[2])] = i

            def formatear_rango_mapeado(r_id, fotos_list):
                if not fotos_list: return ""
                mapped_nums = sorted([mapping[(r_id, n)] for n in fotos_list if (r_id, n) in mapping])
                if not mapped_nums: return ""
                rangos = []
                inicio = fin = mapped_nums[0]
                for n in mapped_nums[1:]:
                    if n == fin + 1:
                        fin = n
                    else:
                        rangos.append(f"({inicio:02d}-{fin:02d})" if inicio != fin else f"({inicio:02d})")
                        inicio = fin = n
                rangos.append(f"({inicio:02d}-{fin:02d})" if inicio != fin else f"({inicio:02d})")
                return "".join(rangos)

            # 3. Construir respuesta
            registros = []
            for r, f_list in registros_con_fotos:

                registros.append({
                    'id': r.id,
                    'fotos': formatear_rango_mapeado(r.id, f_list),
                    'modelo': (r.modelo or "").upper(),
                    'linea': (r.linea or "").upper(),
                    'cantidad': r.cantidad,
                    'responsable': (r.responsable or "").upper(),
                    'descripcion': (r.descripcion or "").upper(),
                    'fecha_hora': r.fecha_registro.strftime('%Y-%m-%d %H:%M') if r.fecha_registro else '',
                    'user_id': r.user_id,
                    'turno': r.turno,
                    'departamento': r.departamento,
                })

            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip() or p.usuario.username
            return Response({
                'usuario': nombre_completo,
                'turno': turno,
                'departamento': p.departamento,
                'operador_id': operador_id or 'todos',
                'registros': registros,
            })

        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error en ReporteTurnoView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# ──────────────────────────────────────────────────────────────────────────────
# WORKFLOW: USUARIO
# ──────────────────────────────────────────────────────────────────────────────

class UsuarioPerfilView(APIView):
    """GET perfil completo de un usuario dado su telegram_id."""
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip()
            return Response({
                'telegram_user_id': p.telegram_user_id,
                'turno': p.turno,
                'departamento': p.departamento,
                'rol': p.rol,
                'username': p.usuario.username,
                'nombre': nombre_completo or p.usuario.username,
            })
        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)


class UsuarioEstadisticasView(APIView):
    """
    GET /workflows/usuario/estadisticas/
    Devuelve las estadísticas del usuario, turno y departamento actual.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from calidad.models import PerfilUsuario, RegistroDefecto, GlobalCounter
            from django.db.models import Sum, Count
            from django.utils import timezone
            from datetime import timedelta
            
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
            
            hoy = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
            manana = hoy + timedelta(days=1)
            
            # Estadísticas de registros
            agg = RegistroDefecto.objects.filter(
                user_id=telegram_id,
                fecha_registro__gte=hoy,
                fecha_registro__lt=manana
            ).aggregate(
                total=Count('id'), cantidad_total=Sum('cantidad')
            )
            
            # Contador actual
            try:
                contador = GlobalCounter.objects.get(nombre='fotos').valor_actual
            except GlobalCounter.DoesNotExist:
                contador = 1
                
            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip()

            return Response({
                'nombre': nombre_completo or p.usuario.username,
                'turno': p.turno,
                'departamento': p.departamento,
                'total_registros': agg['total'] or 0,
                'cantidad_total': agg['cantidad_total'] or 0,
                'siguiente_foto': contador
            })
            
        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error en UsuarioEstadisticasView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ──────────────────────────────────────────────────────────────────────────────
# WORKFLOW: SESION (cancelar / limpiar / limpiar-fotos)
# ──────────────────────────────────────────────────────────────────────────────

class SesionCancelarView(APIView):
    """
    POST /workflows/sesion/cancelar/
    Payload: { telegram_id }
    Lógica: Solo cierra FSM en Redis. No toca registros, fotos, ni contador.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calidad.application.workflows.defecto_workflow import DefectoWorkflow
            DefectoWorkflow()._state_repo.finalizar(telegram_id)

            logger.info("FSM Cancelado para usuario %s", telegram_id)
            return Response({'status': 'cancelled'})
        except Exception as e:
            logger.error("Error en SesionCancelarView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SesionLimpiarView(APIView):
    """
    POST /workflows/sesion/limpiar/
    Payload: { telegram_id }
    Lógica: borra registros BD del usuario.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calidad.models import RegistroDefecto, ContadorUsuario, PerfilUsuario
            from django.db import transaction

            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)

            # FASE 0/1: SIMULACIÓN/NEUTRALIZACIÓN
            # NO ejecutamos .delete() sobre RegistroDefecto
            registros_afectados = RegistroDefecto.objects.filter(
                user_id=telegram_id,
                turno=p.turno,
                departamento=p.departamento
            ).count()
            
            logger.info("AUDITORÍA /limpiar | Usuario: %s | Registros evitados de borrado: %s", telegram_id, registros_afectados)
            
            # NO reiniciamos contador de usuario por seguridad de trazabilidad.

            from calidad.application.workflows.defecto_workflow import DefectoWorkflow
            DefectoWorkflow()._state_repo.finalizar(telegram_id)

            # NO ejecutamos .delete() sobre EvidenciaFotografica
            from calidad.models import EvidenciaFotografica
            fotos_afectadas = EvidenciaFotografica.objects.filter(
                ruta_archivo__startswith=f"fotos/{telegram_id}/"
            ).count()
            
            logger.info("AUDITORÍA /limpiar | Usuario: %s | Fotos evitadas de borrado: %s", telegram_id, fotos_afectadas)

            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip() or p.usuario.username
            return Response({
                'status': 'cleaned',
                'nombre': nombre_completo,
                'turno': p.turno,
                'departamento': p.departamento,
            })

        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error en SesionLimpiarView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SesionLimpiarFotosView(APIView):
    """
    POST /workflows/sesion/limpiar-fotos/
    Payload: { telegram_id }
    Lógica: El borrado físico lo hace el bot. No reinicia contador.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            import os
            from django.conf import settings
            from calidad.models import ContadorUsuario, PerfilUsuario, EvidenciaFotografica
            
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
            
            # FASE 0/1: NO borrar nada, solo calcular métricas reales comparando FS y BD
            en_uso = EvidenciaFotografica.objects.filter(
                ruta_archivo__startswith=f"fotos/{telegram_id}/"
            ).count()
            
            huerfanas = 0
            fotos_dir = settings.MEDIA_ROOT / "fotos" / str(telegram_id)
            if fotos_dir.exists():
                archivos_fisicos = [f.name for f in fotos_dir.iterdir() if f.is_file() and not f.name.startswith("tmp_")]
                # Si total en disco > en BD, asumimos que la diferencia son huérfanas
                huerfanas = max(0, len(archivos_fisicos) - en_uso)
            
            logger.info("AUDITORÍA /limpiar_fotos | Usuario: %s | En uso (BD): %s | Huérfanas detectadas: %s", telegram_id, en_uso, huerfanas)

            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip() or p.usuario.username
            return Response({
                'status': 'analysis',
                'nombre': nombre_completo,
                'fotos_en_uso': en_uso,
                'fotos_huerfanas': huerfanas
            })

        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error en SesionLimpiarFotosView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SesionCancelarView(APIView):
    """
    POST /workflows/sesion/cancelar/
    Payload: { telegram_id }
    Lógica: Solo cierra FSM en Redis. No toca registros, fotos, ni contador.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calidad.application.workflows.defecto_workflow import DefectoWorkflow
            DefectoWorkflow()._state_repo.finalizar(telegram_id)

            logger.info("FSM Cancelado para usuario %s", telegram_id)
            return Response({'status': 'cancelled'})
        except Exception as e:
            logger.error("Error en SesionCancelarView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ──────────────────────────────────────────────────────────────────────────────
# WORKFLOW: DEFECTO FSM
# ──────────────────────────────────────────────────────────────────────────────

from calidad.application.workflows.defecto_workflow import DefectoWorkflow

class DefectoIniciarView(APIView):
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        workflow = DefectoWorkflow()
        result = workflow.iniciar(telegram_id)
        return Response({
            'exito': result.exito,
            'mensaje': result.mensaje,
            'estado': result.nuevo_estado.value if result.nuevo_estado else None
        })

class DefectoAdjuntarEvidenciaView(APIView):
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        fotos_ids = request.data.get('fotos_ids', [])
        
        if not telegram_id or not isinstance(fotos_ids, list):
            return Response({'error': 'telegram_id and fotos_ids (list) required'}, status=status.HTTP_400_BAD_REQUEST)
            
        workflow = DefectoWorkflow()
        result = workflow.adjuntar_fotos(telegram_id, fotos_ids)
        return Response({
            'exito': result.exito,
            'mensaje': result.mensaje,
            'estado': result.nuevo_estado.value if result.nuevo_estado else None
        })

class DefectoResponderView(APIView):
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        texto = request.data.get('texto')
        
        if not telegram_id or not texto:
            return Response({'error': 'telegram_id and texto required'}, status=status.HTTP_400_BAD_REQUEST)
            
        workflow = DefectoWorkflow()
        result = workflow.responder(telegram_id, texto)
        
        response_data = {
            'exito': result.exito,
            'mensaje': result.mensaje,
            'estado': result.nuevo_estado.value if result.nuevo_estado else None,
            'finalizado': result.finalizado
        }
        
        # Inyectar datos de contexto si es necesario para sugerencias UI (sin romper abstracción)
        if result.nuevo_estado and result.nuevo_estado.value == "ESPERANDO_RESPONSABLE":
            from calidad.models import Responsable
            if 'context_data' not in response_data:
                response_data['context_data'] = {}
            response_data['context_data']['responsables_validos'] = Responsable.values
        elif result.nuevo_estado and result.nuevo_estado.value == "ESPERANDO_MODELO":
            from calidad.models import RegistroDefecto
            # Extraemos los últimos 20 para garantizar encontrar 3 únicos recientes
            historial = list(RegistroDefecto.objects.filter(
                user_id=telegram_id
            ).exclude(modelo='').order_by('-id').values_list('modelo', flat=True)[:20])
            
            unicos = []
            for m in historial:
                if m not in unicos:
                    unicos.append(m)
                if len(unicos) == 3:
                    break
                    
            if 'context_data' not in response_data:
                response_data['context_data'] = {}
            response_data['context_data']['historial_modelos'] = unicos
        elif result.nuevo_estado and result.nuevo_estado.value == "ESPERANDO_LINEA":
            from calidad.models import Linea
            if 'context_data' not in response_data:
                response_data['context_data'] = {}
            response_data['context_data']['lineas_validas'] = Linea.values
            
        return Response(response_data)


# ──────────────────────────────────────────────────────────────────────────────
# WORKFLOW: EXPORTACIONES (ZIP)
# ──────────────────────────────────────────────────────────────────────────────

from django.http import FileResponse
from shared.application.services.export_service import ExportService
from django.core.exceptions import PermissionDenied

class ExportTurnosView(APIView):
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service = ExportService()
            turnos = service.obtener_turnos(int(telegram_id))
            return Response(turnos)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error ExportTurnosView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ExportOperadoresView(APIView):
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        turno = request.query_params.get('turno')
        
        if not telegram_id or not turno:
            return Response({'error': 'telegram_id and turno required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service = ExportService()
            operadores = service.obtener_operadores(turno, int(telegram_id))
            return Response(operadores)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error ExportOperadoresView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ExportEvidenciaInfoView(APIView):
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service = ExportService()
            info = service.get_evidence_info(int(telegram_id))
            return Response(info)
        except Exception as e:
            logger.error(f"Error ExportEvidenciaInfoView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class _SelfDeletingFile:
    """File wrapper that deletes the underlying path when closed.

    Django's FileResponse calls .close() on the file object after the
    response has been fully streamed.  By hooking into close() we
    guarantee the temp ZIP is removed without cutting the download and
    without relying on OS /tmp cleanup or external cron jobs.
    """

    def __init__(self, path: str):
        self._path = path
        self._file = open(path, 'rb')

    # Proxy every attribute to the wrapped file so FileResponse
    # sees a normal file-like object (read, seek, tell, etc.).
    def __getattr__(self, name):
        return getattr(self._file, name)

    def close(self):
        try:
            self._file.close()
        finally:
            try:
                os.unlink(self._path)
            except OSError:
                pass  # already gone — harmless

    # Context-manager support (not required by FileResponse, but good hygiene)
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExportEvidenciaView(APIView):
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')
        turno = request.query_params.get('turno')
        operador_id = request.query_params.get('operador')
        inicio = request.query_params.get('inicio')
        fin = request.query_params.get('fin')

        if inicio: inicio = int(inicio)
        if fin: fin = int(fin)

        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            service = ExportService()
            zip_path, count = service.generate_evidence_zip(
                requester_id=int(telegram_id),
                turno=turno,
                operador_id=operador_id,
                inicio=inicio,
                fin=fin
            )

            # _SelfDeletingFile wraps the raw file handle and calls
            # os.unlink(zip_path) when FileResponse closes it after
            # the download finishes — no temp file leak.
            response = FileResponse(
                _SelfDeletingFile(zip_path),
                as_attachment=True,
                filename='evidencia.zip',
            )
            response['X-Image-Count'] = count
            return response

        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error ExportEvidenciaView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

