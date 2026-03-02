FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /opt

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config ca-certificates curl \
    libssl-dev zlib1g-dev libjsoncpp-dev uuid-dev \
    libsqlite3-dev libpq-dev libhiredis-dev libc-ares-dev \
    libbrotli-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth=1 --branch v1.9.7 https://github.com/drogonframework/drogon.git /opt/drogon \
    && cd /opt/drogon \
    && git submodule update --init --recursive \
    && mkdir build \
    && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=OFF -DBUILD_CTL=OFF .. \
    && cmake --build . -j"$(nproc)" \
    && cmake --install . \
    && ldconfig

WORKDIR /app
COPY CMakeLists.txt /app/CMakeLists.txt
COPY src /app/src

RUN cmake -S /app -B /app/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /app/build -j"$(nproc)"

EXPOSE 8080
CMD ["/app/build/rag_gateway"]
