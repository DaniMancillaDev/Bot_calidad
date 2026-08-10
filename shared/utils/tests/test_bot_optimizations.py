import time
import pytest
from bot.client.api_client import BotApiClient, _CACHE_PERFIL, _CACHE_LOCKS

@pytest.mark.anyio
async def test_per_user_cache_locks():
    client = BotApiClient(base_url="http://mock-invalid-domain:9999")
    _CACHE_PERFIL.clear()
    _CACHE_LOCKS.clear()

    # Pre-populate cache for user 1 with current time.time()
    _CACHE_PERFIL[1] = (time.time(), {"nombre": "Juan", "turno": "A"})

    # Should hit cache without making network request
    perfil = await client.obtener_perfil(1)
    assert perfil["nombre"] == "Juan"
    await client.close()
