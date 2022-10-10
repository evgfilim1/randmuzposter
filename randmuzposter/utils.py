__all__ = [
    "AudioProcessingError",
    "generate_audio_caption",
    "process_audio",
    "SongLinkClient",
]

from types import TracebackType
from typing import Type, TypeVar, overload

import httpx
from aiogram.types import MessageEntity

from .constants import Service

_ET = TypeVar("_ET", bound=BaseException)


class SongLinkClient:
    def __init__(self):
        self._client = httpx.AsyncClient(base_url="https://api.song.link/v1-alpha.1/")

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

    async def get_platform_links_by_song(
        self,
        platform: Service,
        song_id: str,
    ) -> dict[Service, str] | None:
        resp = await self._client.get(
            "/links",
            params=dict(platform=platform.name, type="song", id=song_id),
        )
        resp.raise_for_status()
        return {
            service: link
            for service in Service
            if (link := resp.json()["linksByPlatform"].get(service.name, {}).get("url")) is not None
        }


def generate_audio_caption(kwargs: dict[Service | str, str]) -> str:
    text = ""
    for service in Service:
        if kwargs.get(service.name) is not None:
            link = kwargs[service.name]
        elif kwargs.get(service) is not None:
            link = kwargs[service]
        else:
            continue
        text += f'<a href="{link}">{service.value}</a>\n'
    return text


class AudioProcessingError(ValueError):
    pass


async def process_audio(
    caption_entities: list[MessageEntity] | None,
    client: SongLinkClient,
) -> dict[Service, str]:
    for entity in caption_entities or ():
        if entity.type == "text_link" and entity.url.startswith(""):
            spotify_id = entity.url.rsplit("/", maxsplit=1)[1]
            break
    else:
        raise AudioProcessingError("No valid Spotify link found")

    try:
        links = await client.get_platform_links_by_song(Service.spotify, spotify_id)
    except httpx.HTTPError as e:
        raise AudioProcessingError("Upstream returned an error. See logs for details.") from e

    return links
