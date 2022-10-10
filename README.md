# randmuzposter

A simple bot to help with posting music to my channel.

## Dependencies
- Python 3.10
- aiogram 3.0.0b5
- httpx

## Setup
1. (Optional) Create and activate venv: `python3.10 -m venv .venv && source .venv/bin/activate`
2. Copy `.env.example` to `.env` and edit the latter.
3. Install requirements with `pip install -r requirements.txt`

## Run
1. Source venv if you created one: `source .venv/bin/activate`
2. Export environment variables (it's safe, trust me): `eval "$(sed '/^#/d;s/^/export /' <.env)"`
3. Run the bot with `python -m randmuzposter`

## Usage
Send a music file with Spotify link attached to it in caption (e.g. with [@nowplaybot][nowplay]).
The bot will parse it and make a request to [song.link API][songlink] to get links to more streaming
services. Then you can edit some links if they're not accurate, e.g. to use audio-only for YT Music,
or even replace an audio, and post it to your channel.

[nowplay]: https://t.me/nowplaybot
[songlink]: https://odesli.co/
