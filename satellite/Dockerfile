FROM golang:1.24-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o satellite main.go

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/satellite .

# Install libc compatibility if needed, though pure go usually fine.
# But fsnotify might need something? Alpine is usually fine for static Go binaries.
# We need to ensure the watch directory exists or is mounted
VOLUME /downlink_buffer

CMD ["./satellite"]
