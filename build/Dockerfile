FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    build-essential libpcre3-dev zlib1g-dev libssl-dev wget patch checkinstall

WORKDIR /build

RUN wget https://nginx.org/download/nginx-1.25.2.tar.gz && \
    tar -zxvf nginx-1.25.2.tar.gz

COPY patches/CVE-2023-44487.patch /build/
RUN cd nginx-1.25.2 && patch -p1 < ../CVE-2023-44487.patch

RUN cd nginx-1.25.2 && \
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
       --pkgversion=1.25.2 \
       --pkgrelease=1 \
       --maintainer="raz@example.com" \
       make install