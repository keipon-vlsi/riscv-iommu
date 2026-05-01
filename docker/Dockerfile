# =============================================================================
# riscv-iommu-kawano  cocotb verification environment
# =============================================================================
# Base : Ubuntu 22.04 (LTS, glibc 2.35 — matches what Verilator wheels expect)
# Ships:
#   - Verilator 5.046 (built from source, pinned by tag)
#   - Python 3.10  + cocotb 2.0.x  + cocotbext-axi 0.1.28
#   - gcc/g++ 11   + gcov + lcov   (for libiommu / libtables coverage)
#   - GTKWave (波形を Linux 上で見たい人向け; X11 forward すれば動く)
#
# Build:    docker build -t riscv-iommu-tb -f docker/Dockerfile .
# Compose:  docker compose -f docker/docker-compose.yml run --rm cocotb make smoke
# =============================================================================

FROM ubuntu:22.04

ARG VERILATOR_TAG=v5.046
ARG DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# (1) OS パッケージ
#     - build-essential / autoconf / flex / bison : Verilator ビルド用
#     - help2man / libfl-dev / zlib1g-dev         : 同上
#     - python3.10 / python3-venv / python3-pip   : cocotb 用
#     - gcc / g++ / make / git / lcov             : libiommu/libtables カバレッジ用
#     - gtkwave                                    : 波形ビューア (任意)
#     - sudo / less / vim                          : コンテナ内デバッグ用
# ---------------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        wget \
        curl \
        build-essential \
        autoconf \
        automake \
        flex \
        bison \
        help2man \
        libfl-dev \
        libfl2 \
        zlib1g-dev \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        gcc \
        g++ \
        make \
        lcov \
        gtkwave \
        sudo \
        less \
        vim-tiny \
        && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# (2) Verilator をソースからビルド (バージョンを完全に固定)
# ---------------------------------------------------------------------------
RUN git clone --depth 1 --branch ${VERILATOR_TAG} \
        https://github.com/verilator/verilator.git /opt/verilator-src && \
    cd /opt/verilator-src && \
    autoconf && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    rm -rf /opt/verilator-src

RUN verilator --version

# ---------------------------------------------------------------------------
# (3) Python 仮想環境 + cocotb
#     venv にしておくと PEP 668 に怒られないし、
#     ホストの pip と干渉しない。
# ---------------------------------------------------------------------------
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ---------------------------------------------------------------------------
# (4) 非 root ユーザ
#     ホストの bind-mount で書き込むファイルが root 所有にならないように、
#     ホストと同じ uid/gid を使う (compose 側で UID/GID を渡す前提)。
#
#     ⚠ macOS のデフォルト gid=20 (staff) は Ubuntu の dialout と衝突するため、
#       groupadd は既に存在する GID なら skip する。
#     ⚠ macOS のデフォルト uid=501 は Ubuntu に既存ユーザは無いはず。
# ---------------------------------------------------------------------------
ARG USER_NAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

RUN set -eux; \
    # GID が既に使われていればその既存グループを使い回す。
    if ! getent group ${USER_GID} > /dev/null; then \
        groupadd -g ${USER_GID} ${USER_NAME}; \
    fi; \
    # UID が既に使われている場合 (まれ) は失敗するので、その時はホストの uid を変更。
    useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash ${USER_NAME}; \
    echo "${USER_NAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER ${USER_NAME}

WORKDIR /workspace

# ---------------------------------------------------------------------------
# (5) Entrypoint
#     - PYTHONPATH などを毎回 export しなくていいように、
#       /etc/profile に注入しておく。
#     - 何も指定されなければ bash を起動 (interactive 用)。
# ---------------------------------------------------------------------------
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]