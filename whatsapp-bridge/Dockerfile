# The bridge holds the WhatsApp session and owns the SQLite store.
#
# CGO_ENABLED=1 is not optional: github.com/mattn/go-sqlite3 is a cgo wrapper
# around the SQLite C library. With CGO_ENABLED=0 the build still *succeeds* —
# the package swaps in a stub (static_mock.go) whose every call returns
# "Binary was compiled with 'CGO_ENABLED=0', go-sqlite3 requires cgo to work".
# You would get a clean image that fails the moment it opens the database.

FROM golang:1.25-alpine AS build

# gcc and musl-dev provide the C toolchain cgo needs.
RUN apk add --no-cache gcc musl-dev

WORKDIR /src

# Copy the manifests first so dependency download is cached independently of
# source edits.
COPY go.mod go.sum ./
RUN go mod download

COPY . .

ENV CGO_ENABLED=1
RUN go build -trimpath -ldflags='-s -w' -o /out/whatsapp-bridge .


FROM alpine:3.22

# ca-certificates: the bridge speaks TLS to WhatsApp's servers and to the media
# CDN, and alpine ships no root store of its own.
RUN apk add --no-cache ca-certificates tzdata

# The store path is relative to the working directory (main.go calls
# os.MkdirAll("store")), so WORKDIR determines where the session and message
# databases land. /data is the documented mount point.
WORKDIR /data

COPY --from=build /out/whatsapp-bridge /usr/local/bin/whatsapp-bridge

# Inside the container the API must listen on all interfaces, or nothing else in
# the compose network could reach it. Host exposure is controlled separately, by
# publishing the port to 127.0.0.1 only — see docker-compose.yml.
ENV BIND_ADDR=0.0.0.0

EXPOSE 8080

ENTRYPOINT ["whatsapp-bridge"]
