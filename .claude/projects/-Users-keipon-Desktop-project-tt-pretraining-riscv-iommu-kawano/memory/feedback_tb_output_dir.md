---
name: create-tb output directory
description: /create-tb コマンドで生成する TB ファイルの出力先ディレクトリ
type: feedback
---

`/create-tb` で生成されるファイル（SV ラッパー、Makefile、test_*.py、scenario/）は **すべて `tb_coco/test/` に配置**する。RTL パスをミラーした `tb_coco/translation_logic/ptw/` のようなサブディレクトリ構造は使わない。

**Why:** ユーザが `tb_coco/test/` に一元管理したいという方針。

**How to apply:** 次回以降の `/create-tb` 実行時、出力先を `tb_coco/test/` に固定する。Makefile の REPO_ROOT は `$(MAKEFILE_DIR)../..`（2 階層上）で計算する。
