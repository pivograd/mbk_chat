import asyncio
from imageio_ffmpeg import get_ffmpeg_exe

async def convert_to_wav_via_imageio_ffmpeg(src: str, dst: str):
    ffmpeg = get_ffmpeg_exe()
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, '-y', '-i', src, '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', dst,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(err.decode(errors='ignore') or 'ffmpeg failed')
    return dst
