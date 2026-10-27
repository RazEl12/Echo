FROM nginx-builder AS builder-stage

FROM debian:bookworm-slim

COPY --from=builder-stage /build/nginx-1.25.5/nginx_1.25.5-1_*.deb /tmp/

ARG LIBSSL3_MIN_VERSION=3.0.18-1~deb12u2

RUN apt-get update && apt-get install -y \
    curl \
    libpcre3 \
    zlib1g \
    libssl3 \
    gettext-base \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libssl3)" ge "${LIBSSL3_MIN_VERSION}" \
    && dpkg -i /tmp/nginx_*.deb \
    && rm /tmp/nginx_*.deb \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 101 nginx \
    && useradd --system --gid nginx --no-create-home --home /nonexistent --comment "nginx user" --shell /bin/false --uid 101 nginx \
    && mkdir -p /var/log/nginx \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && mkdir -p /var/run /var/cache/nginx \
    && mkdir -p /etc/nginx/conf.d /usr/share/nginx \
    && mv /etc/nginx/html /usr/share/nginx/html \
    && chown -R nginx:nginx /etc/nginx /var/log/nginx /var/cache/nginx /var/run

COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY docker-entrypoint.d/ /docker-entrypoint.d/
RUN chmod +x /docker-entrypoint.sh /docker-entrypoint.d/*

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 80
STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]