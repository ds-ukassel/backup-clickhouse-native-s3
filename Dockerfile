FROM debian:bookworm-slim

# https://clickhouse.com/docs/install#setup-the-debian-repository
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    gzip \
    tar \
    ca-certificates \
    apt-transport-https \
    gnupg \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL 'https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml.key'  \
    | gpg --dearmor -o /usr/share/keyrings/clickhouse-keyring.gpg

ARG ARCH
RUN ARCH=$(dpkg --print-architecture) \
    && echo "deb [signed-by=/usr/share/keyrings/clickhouse-keyring.gpg arch=${ARCH}] https://packages.clickhouse.com/deb stable main"  \
    | tee /etc/apt/sources.list.d/clickhouse.list

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends clickhouse-client \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L "https://dl.min.io/client/mc/release/linux-amd64/mc" -o /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc

COPY scripts/backup-clickhouse.sh /usr/local/bin/backup-clickhouse.sh
RUN chmod +x /usr/local/bin/backup-clickhouse.sh

COPY scripts/query_generator.py /usr/local/bin/query_generator.py

ENV MINIO_COMMAND="mc"
ENTRYPOINT ["/usr/local/bin/backup-clickhouse.sh"]