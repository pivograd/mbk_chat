from aiohttp import web


def trust_me():
    return web.Response(status=200, text=f"Йоу йоу йоу йоу, мой друг под кислотой, йоу йоу")