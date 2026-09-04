FROM python:3.12 AS builder

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
      build-essential cmake ninja-build git

WORKDIR /app

COPY pyproject.toml setup.py CMakeLists.txt MANIFEST.in README.md COPYING ./
COPY licenses/ ./licenses/
COPY src/piper/ ./src/piper/
COPY script/setup script/dev_build script/package ./script/
RUN script/setup --dev
RUN script/dev_build
RUN script/package

# -----------------------------------------------------------------------------

FROM python:3.12-slim

ENV PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /app
COPY --from=builder /app/dist/piper_tts-*.whl /tmp/
# The default image stays small enough for HTTP serving. Build with
# PIPER_EXTRAS=http,ja,zh,nlp for the optional Docker-only NLP profile.
ARG PIPER_EXTRAS="http,ja,zh"
RUN wheel="$(find /tmp -maxdepth 1 -name 'piper_tts-*.whl' -print -quit)" && \
    pip3 install --no-cache-dir "piper-tts[${PIPER_EXTRAS}] @ file://${wheel}" && \
    rm -f "${wheel}"

COPY docker/entrypoint.sh /

EXPOSE 5000
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
