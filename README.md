# randmuzposter

A simple bot to help with posting music to my channel.

## Dependencies
- Python 3.10
- aiogram 3.0.0b1
- PyYAML
- httpx

## Setup
1. (Optional) Create and activate venv: `python3.10 -m venv .venv && source .venv/bin/activate`
2. Copy `config.example.yaml` to `config.yaml` and edit the latter.
3. Install requirements with `pip install -r requirements.txt`

Run the bot with `python main.py`

## Usage
Send a music file with Spotify link attached to it in caption (e.g. with [@nowplaybot][nowplay]).
The bot will parse it and make a request to [song.link API][songlink] to get links to more streaming
services. Then you can edit some links if they're not accurate, e.g. to use audio-only for YT Music,
or even replace an audio, and post it to your channel.

[nowplay]: https://t.me/nowplaybot
[songlink]: https://odesli.co/