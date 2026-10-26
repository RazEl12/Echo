FROM debian:bookworm-slim

ARG NGINX_VERSION=1.25.5

RUN apt-get update && apt-get install -y \
    build-essential libpcre3-dev zlib1g-dev libssl-dev wget patch checkinstall

WORKDIR /build

RUN wget https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz && \
    tar -zxvf nginx-${NGINX_VERSION}.tar.gz

COPY patches/CVE-2026-97629.patch /build/
RUN cd nginx-${NGINX_VERSION} && patch -p1 < ../CVE-2026-97629.patch

RUN cd nginx-${NGINX_VERSION} && \
    ./configure \
    --prefix=/etc/nginx \
    --sbin-path=/usr/sbin/nginx \
    --conf-path=/etc/nginx/nginx.conf \
    --error-log-path=/var/log/nginx/error.log \
    --http-log-path=/var/log/nginx/access.log \
    --pid-path=/var/run/nginx.pid \
    --lock-path=/var/run/nginx.lock \
    --with-http_ssl_module \
    --with-http_v2_module \
    && make \
    && checkinstall -D -y \
       --install=no \
       --fstrans=no \
       --pkgname=custom-nginx \
       --pkgversion=${NGINX_VERSION} \
       --pkgrelease=1 \
       --maintainer="raz@example.com" \
       make install
