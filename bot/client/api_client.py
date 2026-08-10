import asyncio
import logging
import time

import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)


class ApiException(Exception):
    pass


# Caché técnica en memoria para perfiles (evita ráfagas de logs)
_CACHE_PERFIL: dict = {}
_CACHE_LOCKS: dict[int, asyncio.Lock] = {}  # ponytail: per-user locks; global lock serializa todos los usuarios
TTL_PERFIL = 300  # 5 minutos

# Política de retry compartida
_retry_policy = retry(
    wait=wait_exponential(multiplier=1, min=0.5, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
    reraise=True,
)

class BotApiClient:
    """
    Cliente HTTP asíncrono para comunicarse con la API de Workflows.
    Implementa retries exponenciales para resiliencia de red.
    """
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip('/')
        # Configuramos httpx con un connection pool y timeouts
        headers = {}
        if api_key:
            headers["Authorization"] = f"Token {api_key}"
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(10.0, connect=3.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
        )

    async def close(self):
        await self.client.aclose()

    @_retry_policy
    async def _get(self, endpoint: str, params: dict = None) -> dict:
        try:
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error {e.response.status_code} at {endpoint}: {e.response.text}")
            raise ApiException(f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Network Error at {endpoint}: {str(e)}")
            raise

    @_retry_policy
    async def _post(self, endpoint: str, json: dict = None, data: dict = None, files: dict = None) -> dict:
        try:
            response = await self.client.post(endpoint, json=json, data=data, files=files)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error {e.response.status_code} at {endpoint}: {e.response.text}")
            raise ApiException(f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Network Error at {endpoint}: {str(e)}")
            raise

    # ==========================
    # WORKFLOW: AUTH
    # ==========================
    async def tiene_acceso(self, telegram_id: int) -> dict:
        """Verifica el acceso de un usuario. Lanza ApiException si falla la red."""
        try:
            # Capturamos el 404 específicamente como acceso denegado, no como error de red
            response = await self.client.get("/api/v1/workflows/auth/tiene-acceso/", params={'telegram_id': telegram_id})
            if response.status_code == 404:
                return {"tiene_acceso": False}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error comprobando acceso para {telegram_id}: {str(e)}")
            # En caso de duda por error de red, denegamos y forzamos a intentar después
            raise ApiException("Servicio de validación temporalmente inactivo.")

    # ==========================
    # WORKFLOW: DEFECTOS
    # ==========================
    async def iniciar_defecto(self, telegram_id: int) -> dict:
        return await self._post("/api/v1/workflows/defecto/iniciar/", json={"telegram_id": telegram_id})

    async def adjuntar_evidencia_lote(self, telegram_id: int, fotos_ids: list[int]) -> dict:
        """Avanza la máquina de estados con las fotos agrupadas y descargadas."""
        return await self._post(
            "/api/v1/workflows/defecto/adjuntar-evidencia/",
            json={"telegram_id": telegram_id, "fotos_ids": fotos_ids}
        )

    async def responder_defecto(self, telegram_id: int, texto: str) -> dict:
        """Envía texto para avanzar la FSM."""
        return await self._post(
            "/api/v1/workflows/defecto/responder/",
            json={"telegram_id": telegram_id, "texto": texto}
        )

    # ==========================
    # WORKFLOW: USUARIO
    # ==========================
    async def obtener_perfil(self, telegram_id: int) -> dict:
        """Retorna perfil del usuario (turno, depto, rol, nombre). 404 → None. Caché con lock por usuario."""
        ahora = time.time()

        # Check sin lock — race benigno: lo peor es una llamada extra al API
        cached = _CACHE_PERFIL.get(telegram_id)
        if cached and ahora - cached[0] < TTL_PERFIL:
            return cached[1]

        lock = _CACHE_LOCKS.setdefault(telegram_id, asyncio.Lock())
        async with lock:
            # Re-check dentro del lock
            cached = _CACHE_PERFIL.get(telegram_id)
            if cached and ahora - cached[0] < TTL_PERFIL:
                return cached[1]

            try:
                response = await self.client.get(
                    "/api/v1/workflows/usuario/perfil/",
                    params={'telegram_id': telegram_id}
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()

                perfil = response.json()
                _CACHE_PERFIL[telegram_id] = (ahora, perfil)
                return perfil
            except Exception as e:
                logger.error(f"Error obteniendo perfil para {telegram_id}: {str(e)}")
                raise ApiException("No se pudo obtener perfil del usuario.")

    async def obtener_estadisticas(self, telegram_id: int) -> dict:
        """Obtiene las estadísticas de registros y estado actual del usuario."""
        return await self._get(
            "/api/v1/workflows/usuario/estadisticas/",
            params={'telegram_id': telegram_id}
        )

    # ==========================
    # WORKFLOW: SESION
    # ==========================
    async def cancelar_sesion(self, telegram_id: int) -> dict:
        """Rollback contador + limpieza backend. Borrado físico de fotos lo hace el bot."""
        return await self._post(
            "/api/v1/workflows/sesion/cancelar/",
            json={"telegram_id": telegram_id}
        )
