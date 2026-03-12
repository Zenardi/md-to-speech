# =============================================================================
# Stage 1 — builder
# Install system build tools, create a virtual environment, and install all
# Python dependencies. This stage is discarded after the build.
# =============================================================================
FROM cgr.dev/chainguard/wolfi-base AS builder

RUN apk add --no-cache \
    python-3.11 \
    python-3.11-dev \
    py3.11-pip \
    build-base \
    libffi-dev

WORKDIR /build

# Create an isolated virtual environment at a stable path.
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install pinned dependencies first (better layer caching).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the app itself without reinstalling dependencies.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps -e .

# =============================================================================
# Stage 2 — runtime
# Minimal image containing only what is needed to run the app.
# No build tools, no Python headers, no pip.
# espeak-ng is NOT needed as a system package — the `espeakng-loader` Python
# package bundles the shared library for Linux ARM64 and x86_64.
# =============================================================================
FROM cgr.dev/chainguard/wolfi-base AS runtime

RUN apk add --no-cache \
    python-3.11

WORKDIR /app

# Copy the virtual environment and the app source from the builder.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/src /app/src

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Tell HuggingFace Hub where to store (and look for) cached model weights.
# Mount a host directory here to persist the model across container runs
# and to enable --offline mode without re-downloading every time.
ENV HF_HOME="/cache"

# /data  — mount your input Markdown files and receive output audio here.
# /cache — mount a persistent directory so the model (~327 MB) is only
#          downloaded once. Pass --offline on every run after the first.
VOLUME ["/data", "/cache"]

# Drop to a non-root user (Chainguard nonroot uid/gid = 65532).
USER 65532:65532

WORKDIR /data

ENTRYPOINT ["md-to-speech"]
CMD ["--help"]
