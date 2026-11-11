# Official MinIO public images are no longer anonymously pullable. Source-build fallback.
FROM golang:1.24.7-alpine3.22@sha256:fc2cff6625f3c1c92e6c85938ac5bd09034ad0d4bc2dfb08278020b68540dbb5 AS build
WORKDIR /src
ADD --checksum=sha256:c9598dcce3440977e79f787f2ba0e7e4d92c8d556bd51e7cef3785bafd6635f3 https://codeload.github.com/minio/minio/tar.gz/refs/tags/RELEASE.2025-09-07T16-13-09Z /source.tar.gz
RUN tar -xzf /source.tar.gz --strip-components=1 && CGO_ENABLED=0 go build -trimpath -o /minio .
FROM alpine:3.22.1@sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1
RUN addgroup -g 1000 minio && adduser -D -u 1000 -G minio minio && mkdir /data && chown 1000:1000 /data
COPY --from=build /minio /usr/local/bin/minio
USER 1000:1000
VOLUME /data
ENTRYPOINT ["/usr/local/bin/minio"]
