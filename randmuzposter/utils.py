__all__ = [
    "AudioProcessingError",
    "generate_audio_caption",
    "process_audio",
    "SongLinkClient",
    "suggested_track_text",
]

import re
from types import TracebackType
from typing import Any, Literal, Type, TypeVar, overload

import httpx
from aiogram.types import MessageEntity

from .constants import SERVICE_LINKS, SONG_LINK_REGEX, Service

_ET = TypeVar("_ET", bound=BaseException)


class SongLinkClient:
    def __init__(self, user_country: str | None = None) -> None:
        self._client = httpx.AsyncClient(base_url="https://api.song.link/v1-alpha.1/")
        if user_country is not None:
            self._client.params = {"userCountry": user_country}

    async def __aenter__(self):
        return self

    @overload
    async def __aexit__(self, exc_type: None, exc_val: None, exc_tb: None) -> None:
        ...

    @overload
    async def __aexit__(self, exc_type: Type[_ET], exc_val: _ET, exc_tb: TracebackType) -> None:
        ...

    async def __aexit__(
        self,
        exc_type: Type[_ET] | None,
        exc_val: _ET | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def _request(self, **params: str) -> dict[str, Any]:
        resp = await self._client.get("/links", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_platform_links_by_url(
        self,
        url: str,
    ) -> dict[Service | Literal["self"], str] | None:
        data = await self._request(url=url)
        res = {
            service: link
            for service in Service
            if (link := data["linksByPlatform"].get(service.name, {}).get("url")) is not None
        }
        res["self"] = data["pageUrl"]
        return res

    async def get_platform_links_by_song(
        self,
        platform: Service,
        song_id: str,
    ) -> dict[Service | Literal["self"], str] | None:
        data = await self._request(platform=platform.name, type="song", id=song_id)
        res = {
            service: link
            for service in Service
            if (link := data["linksByPlatform"].get(service.name, {}).get("url")) is not None
        }
        res["self"] = data["pageUrl"]
        return res


def generate_audio_caption(links: dict[Service | str, str]) -> str:
    text = ""
    for service in Service:
        if links.get(service.name) is not None:
            link = links[service.name]
        elif links.get(service) is not None:
            link = links[service]
        else:
            continue
        text += f'<a href="{link}">{service.value}</a>\n'
    text += f"<a href='{links['self']}'>Other</a>\n"
    return text


def suggested_track_text(bot_username: str) -> str:
    self_link = f"https://t.me/{bot_username}"
    return (
        f"_______\n"
        f"Трек из <a href='{self_link}'>предложки</a>\n"
        f"<a href='{self_link}'>Suggested</a> track"
    )


class AudioProcessingError(ValueError):
    pass


def detect_audio_link(
    entity: MessageEntity,
    caption: str | None,
) -> tuple[Service | None, re.Match[str]] | None:
    if entity.type != "text_link":
        if entity.type != "url" or caption is None:
            return None
        url = entity.extract_from(caption)
    else:
        url = entity.url
    if match := SONG_LINK_REGEX.search(url):
        return None, match
    for service, link_re in SERVICE_LINKS.items():
        if match := link_re.match(url):
            return service, match
    return None


async def process_audio(
    caption: str | None,
    caption_entities: list[MessageEntity] | None,
    client: SongLinkClient,
) -> dict[Service, str]:
    for entity in caption_entities or ():
        res = detect_audio_link(entity, caption)
        if res is not None:
            link = res[1][0]
            break
    else:
        raise AudioProcessingError("No valid link found")

    try:
        links = await client.get_platform_links_by_url(link)
    except httpx.HTTPError as e:
        raise AudioProcessingError("Upstream returned an error. See logs for details.") from e

    return links
