__all__ = [
    "Service",
    "SERVICE_LINKS",
    "SONG_LINK_REGEX",
]

import re
from enum import Enum


class Service(Enum):
    # Adding new services is as simple as adding a new value to this enum.
    # The key of the enum member is the name of the service as it appears in the SongLink API.
    # The value of the enum member is the name of the service as it appears to you in Telegram.
    # Links in the message are sorted as they appear here.
    spotify = "Spotify"
    youtubeMusic = "YouTube Music"
    yandex = "Yandex"
    soundcloud = "SoundCloud"


# Don't forget to add the new service to this regex.
SERVICE_LINKS = {
    Service.spotify: re.compile(r"^https?://open\.spotify\.com/track/(\w+)"),
    Service.youtubeMusic: re.compile(
        r"^https?://(?:(?:music\.|www\.)?youtube\.com/watch\?v=|youtu\.be/)(\w+)"
    ),
    Service.yandex: re.compile(r"^https?://music\.yandex\.ru/(?:album/\d+/)?track/(\d+)"),
    Service.soundcloud: re.compile(r"^https?://soundcloud\.com/[^/]+/[^/]+"),
}

SONG_LINK_REGEX = re.compile(r"^https?://song\.link/(\w+)/([^/]+)$")
