__all__ = [
    "Service",
]

from enum import Enum


class Service(Enum):
    # Adding new services is as simple as adding a new value to this enum.
    # The key of the enum member is the name of the service as it appears in the SongLink API.
    # The value of the enum member is the name of the service as it appears to you in Telegram.
    spotify = "Spotify"
    youtubeMusic = "YouTube Music"
    yandex = "Yandex"
    soundcloud = "SoundCloud"
