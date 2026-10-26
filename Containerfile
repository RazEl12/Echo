FROM nginx-builder AS builder-stage

FROM debian:bookworm-slim

COPY --from=builder-stage /build/nginx-1.25.2/custom-nginx_1.25.2-1_amd64.deb /tmp/nginx.deb

RUN apt-get update && apt-get install -y \
    curl \
    libpcre3 \
    zlib1g \
    libssl3 \
    && dpkg -i /tmp/nginx.deb \
    && rm /tmp/nginx.deb \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 101 nginx \
    && useradd --system --gid nginx --no-create-home --home /nonexistent --comment "nginx user" --shell /bin/false --uid 101 nginx \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && mkdir -p /var/run /var/cache/nginx \
    && chown -R nginx:nginx /etc/nginx /var/log/nginx /var/cache/nginx /var/run

EXPOSE 80
STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]