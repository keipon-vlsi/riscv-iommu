#!/usr/bin/env bash
# =============================================================================
# Entrypoint for the riscv-iommu cocotb dev container.
#
# - venv の activate
# - submodule のチェック (まだ checkout されていなければ警告)
# - 渡された引数を実行 (デフォルトは bash)
# =============================================================================
set -e

# (1) venv を有効化
export PATH="/opt/venv/bin:${PATH}"
export VIRTUAL_ENV="/opt/venv"

# (2) submodule の初期化を促す
if [ -d "/workspace/third_party/iommu-reference" ] && \
   [ ! -f "/workspace/third_party/iommu-reference/Makefile" ] && \
   [ ! -f "/workspace/third_party/iommu-reference/libiommu/Makefile" ]; then
    echo ""
    echo "  ⚠  third_party/iommu-reference は空のようです。"
    echo "     ホスト側で次のコマンドを実行してから再度コンテナを立ち上げてください:"
    echo ""
    echo "         git submodule update --init --recursive"
    echo ""
fi

# (3) cocotb の自動キャッシュ場所をワークスペース内に固定
#     ホストにキャッシュが残らない方が cleanup が楽。
export COCOTB_BUILD_DIR="${COCOTB_BUILD_DIR:-/workspace/.cocotb_build}"

# (4) 引数を実行
if [ "$#" -eq 0 ]; then
    exec bash
else
    exec "$@"
fi