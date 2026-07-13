"""Proxy web per pannelli JANIS — bypass X-Frame-Options per siti esterni."""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse, urljoin

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter()

_MAX_BYTES = 2_000_000
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


def _validate_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL vuoto")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Solo http/https")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        raise HTTPException(status_code=403, detail="Host non consentito")
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise HTTPException(status_code=403, detail="IP privato non consentito")
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Host non risolvibile")
    return url


def _inject_base(html: bytes, base_url: str) -> bytes:
    text = html.decode("utf-8", errors="replace")
    base_tag = f'<base href="{base_url}">'
    if re.search(r"<head[^>]*>", text, re.I):
        return re.sub(r"(<head[^>]*>)", r"\1" + base_tag, text, count=1, flags=re.I).encode("utf-8")
    if re.search(r"<html[^>]*>", text, re.I):
        return re.sub(r"(<html[^>]*>)", r"\1<head>" + base_tag + "</head>", text, count=1, flags=re.I).encode("utf-8")
    return (base_tag + text).encode("utf-8")


@router.get("/api/web/proxy")
async def web_proxy(url: str = Query(..., min_length=4)):
    target = _validate_url(url)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            headers={"User-Agent": "JANIS/2.0 WebPanel (+local proxy)"},
        ) as client:
            r = await client.get(target)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Sito non raggiungibile: {e}") from e

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=f"Sito risponde {r.status_code}")

    content = r.content[:_MAX_BYTES]
    ctype = r.headers.get("content-type", "text/html").split(";")[0].strip().lower()

    if "html" in ctype or content.lstrip()[:15].lower().startswith(b"<!doctype") or b"<html" in content[:500].lower():
        content = _inject_base(content, target)
        ctype = "text/html; charset=utf-8"

    return Response(
        content=content,
        media_type=ctype,
        headers={
            "Cache-Control": "no-store",
            "X-JANIS-Proxy-Target": target,
        },
    )


@router.get("/api/web/check")
async def web_check(url: str = Query(..., min_length=4)):
    """Verifica se un URL e raggiungibile."""
    target = _validate_url(url)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            r = await client.head(target)
            if r.status_code >= 400:
                r = await client.get(target)
        return {
            "url": target,
            "ok": r.status_code < 400,
            "status": r.status_code,
            "x_frame_options": r.headers.get("x-frame-options", ""),
            "needs_proxy": bool(r.headers.get("x-frame-options")),
        }
    except httpx.HTTPError as e:
        return {"url": target, "ok": False, "error": str(e)}
