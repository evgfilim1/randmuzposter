# randmuzposter

[![black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[![Lint code](https://github.com/evgfilim1/randmuzposter/actions/workflows/lint.yaml/badge.svg)](https://github.com/evgfilim1/randmuzposter/actions/workflows/lint.yaml)
[![Build and push Docker image](https://github.com/evgfilim1/randmuzposter/actions/workflows/build.yaml/badge.svg)](https://github.com/evgfilim1/randmuzposter/actions/workflows/build.yaml)
[![Deploy a Docker container](https://github.com/evgfilim1/randmuzposter/actions/workflows/deploy.yaml/badge.svg)](https://github.com/evgfilim1/randmuzposter/actions/workflows/deploy.yaml)

A simple bot to help with posting music to my channel.

## Dependencies
- Python 3.10
- aiogram 3.0.0b5
- httpx

## Setup

Copy `.env.example` to `.env` and edit the latter. Then follow the instructions below depending
on your setup.

### Docker

**Note**: This requires [Docker Engine][docker-engine] and [Docker Compose][docker-compose]
to be installed.

```bash
docker compose build
```

### Manual
1. (Optional) Create and activate venv
    ```bash
    python3.10 -m venv .venv && source .venv/bin/activate
    ```
2. Install requirements
    ```bash
    pip install -r requirements.txt
    ```

## Run

### Docker

```bash
docker compose up -d
```

### Manual

1. Source venv if you created one
    ```bash
    source .venv/bin/activate
    ```
2. Export environment variables (it's safe, trust me)
    ```bash
    eval "$(sed '/^#/d;s/^/export /' <.env)"
    ```
3. Run the bot
    ```bash
    python -m randmuzposter
    ```

## Usage
Send a music file with any [supported link][supported] attached to it in caption (e.g. with
[@nowplaybot][nowplay] or [@LyBot][lybot]). The bot will parse it and make a request to
[song.link API][songlink] to get links to more streaming services. Then you can edit some links
if they're not accurate, e.g. to use audio-only for YT Music, or even replace an audio, and post it
to your channel.

[docker-engine]: https://docs.docker.com/engine/install/
[docker-compose]: https://docs.docker.com/compose/install/
[supported]: randmuzposter/constants.py
[nowplay]: https://t.me/nowplaybot
[lybot]: https://t.me/LyBot
[songlink]: https://odesli.co/
