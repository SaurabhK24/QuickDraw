FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
COPY . .
RUN go mod tidy && CGO_ENABLED=0 go build -o /quickdraw-api ./cmd/quickdraw-api

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=builder /quickdraw-api /usr/local/bin/quickdraw-api
EXPOSE 8080
ENTRYPOINT ["quickdraw-api"]
