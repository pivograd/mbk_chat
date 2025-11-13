import aiohttp


async def download_bytes(url: str, timeout: float = 60.0) -> bytes:
    """

    """
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as sess:
        async with sess.get(url, allow_redirects=True) as r:
            r.raise_for_status()
            return await r.read()
