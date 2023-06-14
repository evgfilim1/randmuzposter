FROM python:3.11-slim

WORKDIR /app
RUN useradd -Ud /app randmuzposter

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY randmuzposter ./randmuzposter

USER randmuzposter:randmuzposter
ENTRYPOINT ["/usr/bin/env", "python3.11", "-m", "randmuzposter"]
