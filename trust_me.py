from aiohttp import web, ClientSession

from telegram.send_log import send_dev_telegram_log


async def trust_me(request: web.Request):
    # await send_dev_telegram_log('[TRUSTME]', 'DEV')
    DEV_TUNNEL = 'https://561fbda6-1f19-463c-9975-4f35065b2d4c.tunnel4.com'
    body = await request.read()
    target = f"{DEV_TUNNEL}{request.path_qs}"

    headers = dict(request.headers)
    headers.pop("Host", None)
    headers.pop("Content-Length", None)

    async with ClientSession() as s:
        async with s.request(
                request.method, target, data=body, headers=headers,
                ssl=False, allow_redirects=False
        ) as r:
            ...
            # return web.Response(
            #     status=r.status,
            #     body=await r.read(),
            #     headers=r.headers
            # )
    return web.Response(status=200, text=f"Йоу йоу йоу йоу, мой друг под кислотой, йоу йоу")
