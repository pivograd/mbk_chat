import contextlib
import os
import tempfile

import aiohttp


async def download_to_temp(session: aiohttp.ClientSession, url: str, suggested_name: str) -> str:
    """
    Скачивает бинарник по URL в temp-файл, возвращает локальный путь.
    Расширение берём из suggested_name (если есть).
    """
    suffix = ""
    base, ext = os.path.splitext(suggested_name)
    if ext:
        suffix = ext

    fd, tmp_path = tempfile.mkstemp(prefix="voice_", suffix=suffix)
    os.close(fd)

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    if chunk:
                        f.write(chunk)
        return tmp_path
    except Exception:
        with contextlib.suppress(Exception):
            os.remove(tmp_path)
        raise
