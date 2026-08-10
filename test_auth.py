import asyncio
from shared.config.dependencies import build_container
async def test():
    c = build_container()
    res = await c["api_client"].tiene_acceso(7287026906)
    print("tiene_acceso result:", res)
if __name__ == "__main__":
    asyncio.run(test())
