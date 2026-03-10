FROM debian:13-slim

ARG CLICKHOUSE_VERSION=26.2.4.23
ARG CLICKHOUSE_CLIENT_CHECKSUM=sha256:db62837caaa34041049f5b23e12f30370e6501270eed7f22b3851a528fe6aed4
ARG CLICKHOUSE_COMMON_CHECKSUM=sha256:437c272fea4297b38fce9840b020bca954c8f6a9bd5758a9558e24b1162cb070
ADD --checksum=$CLICKHOUSE_COMMON_CHECKSUM \
    "https://github.com/ClickHouse/ClickHouse/releases/download/v${CLICKHOUSE_VERSION}-stable/clickhouse-common-static_${CLICKHOUSE_VERSION}_amd64.deb" \
    /tmp/clickhouse-common.deb
ADD --checksum=$CLICKHOUSE_CLIENT_CHECKSUM \
    "https://github.com/ClickHouse/ClickHouse/releases/download/v${CLICKHOUSE_VERSION}-stable/clickhouse-client_${CLICKHOUSE_VERSION}_amd64.deb" \
    /tmp/clickhouse-client.deb
RUN dpkg -i /tmp/clickhouse-common.deb /tmp/clickhouse-client.deb && rm /tmp/clickhouse-*.deb

ARG MINIO_RELEASE=RELEASE.2025-08-13T08-35-41Z
ARG MINIO_CHECKSUM=sha256:01f866e9c5f9b87c2b09116fa5d7c06695b106242d829a8bb32990c00312e891
ADD --chmod=+x --checksum=${MINIO_CHECKSUM} "https://dl.min.io/client/mc/release/linux-amd64/mc.${MINIO_RELEASE}" /usr/local/bin/mc

COPY --chmod=+x scripts/backup-clickhouse.sh /usr/local/bin/backup-clickhouse.sh
COPY --chmod=+x scripts/query_generator.py /usr/local/bin/query_generator.py

ENV MINIO_COMMAND="mc"
ENV CLICKHOUSE_COMMAND="clickhouse-client"
WORKDIR /usr/local/bin
CMD ["backup-clickhouse.sh"]
