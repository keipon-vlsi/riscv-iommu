# Microsoftが提供するPython開発用の公式コンテナを利用（これでvenvなどの面倒な設定が不要になります）
FROM mcr.microsoft.com/devcontainers/python:3.12

# ハードウェア検証に必要なツール（Verilator等）を追加インストール
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    build-essential \
    verilator \
    gtkwave
