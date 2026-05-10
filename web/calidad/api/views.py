import logging
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import status
from django.shortcuts import get_object_or_404
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

            if p.rol == 'admin':
                qs = RegistroDefecto.objects.filter(turno=p.turno, departamento=p.departamento)
            else:
                qs = RegistroDefecto.objects.filter(user_id=telegram_id)

            qs = qs.order_by('-fecha_registro')

            def formatear_rango(fotos_list):
                if not fotos_list: return ""
                nums = sorted(list(set(fotos_list)))
                rangos = []
                if not nums: return ""
                
                inicio = fin = nums[0]
                for n in nums[1:]:
                    if n == fin + 1:
                        fin = n
                    else:
                        rangos.append(f"({inicio:03d}-{fin:03d})" if inicio != fin else f"({inicio:03d})")
                        inicio = fin = n
                rangos.append(f"({inicio:03d}-{fin:03d})" if inicio != fin else f"({inicio:03d})")
                return "".join(rangos)

            registros = []
            for r in qs:
                # r.fotos es un TextField que guarda "1, 2, 3"
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

                registros.append({
                    'id': r.id,
                    'fotos': formatear_rango(f_list), 
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
            from calidad.models import PerfilUsuario, RegistroDefecto, ContadorGrupo
            from django.db.models import Sum, Count
            
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
            
            # Estadísticas de registros
            agg = RegistroDefecto.objects.filter(user_id=telegram_id).aggregate(
                total=Count('id'), cantidad_total=Sum('cantidad')
            )
            
            # Contador actual
            try:
                contador = ContadorGrupo.objects.get(turno=p.turno, departamento=p.departamento).contador_actual
            except ContadorGrupo.DoesNotExist:
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
    Payload: { telegram_id, fotos: [int,...] }
    Lógica: rollback contador (a min(fotos)), limpia estado Redis.
    El borrado físico de fotos lo hace el bot (tiene acceso al volumen).
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        fotos = request.data.get('fotos', [])

        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calidad.models import ContadorGrupo, PerfilUsuario
            from django.db import transaction

            p = PerfilUsuario.objects.get(telegram_user_id=telegram_id)

            # Rollback contador al mínimo de la sesión cancelada
            contador_revertido = None
            if fotos:
                valor_anterior = max(1, min(fotos))
                with transaction.atomic():
                    contador = ContadorGrupo.objects.select_for_update().get(
                        turno=p.turno, departamento=p.departamento
                    )
                    contador.contador_actual = valor_anterior
                    contador.save(update_fields=['contador_actual'])
                contador_revertido = valor_anterior

            from calidad.application.workflows.defecto_workflow import DefectoWorkflow
            DefectoWorkflow()._state_repo.finalizar(telegram_id)

            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip() or p.usuario.username
            return Response({
                'status': 'cancelled',
                'contador_revertido': contador_revertido,
                'nombre': nombre_completo,
            })

        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except ContadorGrupo.DoesNotExist:
            # No hay contador que revertir, igual respondemos OK
            return Response({'status': 'cancelled', 'contador_revertido': None})
        except Exception as e:
            logger.error("Error en SesionCancelarView: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SesionLimpiarView(APIView):
    """
    POST /workflows/sesion/limpiar/
    Payload: { telegram_id }
    Lógica: borra registros BD del usuario + reinicia contador a 1.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calidad.models import RegistroDefecto, ContadorGrupo, PerfilUsuario
            from django.db import transaction

            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)

            with transaction.atomic():
                RegistroDefecto.objects.filter(user_id=telegram_id).delete()
                ContadorGrupo.objects.filter(
                    turno=p.turno, departamento=p.departamento
                ).update(contador_actual=1)

            from calidad.application.workflows.defecto_workflow import DefectoWorkflow
            DefectoWorkflow()._state_repo.finalizar(telegram_id)

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
    Lógica: reinicia contador a 1. El borrado físico lo hace el bot.
    """
    authentication_classes = [StaticApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calidad.models import ContadorGrupo, PerfilUsuario

            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
            ContadorGrupo.objects.filter(turno=p.turno, departamento=p.departamento).update(contador_actual=1)

            from calidad.application.workflows.defecto_workflow import DefectoWorkflow
            DefectoWorkflow()._state_repo.finalizar(telegram_id)

            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip() or p.usuario.username
            return Response({
                'status': 'photos_cleaned',
                'nombre': nombre_completo,
            })

        except PerfilUsuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error en SesionLimpiarFotosView: %s", e)
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
        return Response({
            'exito': result.exito,
            'mensaje': result.mensaje,
            'estado': result.nuevo_estado.value if result.nuevo_estado else None,
            'finalizado': result.finalizado
        })

