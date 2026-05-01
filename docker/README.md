# docker/ — 検証環境の容器

このディレクトリ単体で完結する Docker 設定。
ユーザ視点での使い方は repo root の `README.md` を参照。

---

## ファイル構成

| ファイル | 役割 |
| :--- | :--- |
| `Dockerfile` | Ubuntu 22.04 に Verilator/cocotb/gcc/lcov を仕込む手順 |
| `docker-compose.yml` | bind-mount + uid/gid 合わせ + ワンライナー実行 |
| `entrypoint.sh` | venv の activate / submodule 状態のチェック |
| `requirements.txt` | Python パッケージのバージョン固定 |

---

## 設計メモ

### なぜ Ubuntu 22.04 ベースか
- glibc 2.35 — cocotb / Verilator の prebuilt と相性が良い
- `python3.10` が apt で素直に入る (PEP 668 対応も `python3-venv` で OK)
- LTS で 2027 まで security fix が来る

### なぜ Verilator をソースビルドするのか
- apt の `verilator` は古い (Ubuntu 22.04 だと 4.038)。
  本プロジェクトは 5.x の `--coverage`/`--trace-structs` 改善を使う前提。
- バージョンを完全に固定したい (CI とローカルの差異を消したい) ので、
  tag (`v5.046`) を pin。

### なぜ venv を使うのか
- システムの Python に直 pip すると Ubuntu 22.04 では PEP 668 で弾かれる。
- `--break-system-packages` で押し切るより venv の方が clean。
- `entrypoint.sh` で activate しているので、ユーザは意識しなくていい。

### なぜ非 root ユーザ + uid/gid 合わせなのか
- bind-mount したファイルを root が編集すると、ホスト側で `chmod` が必要になる。
- `compose.yml` の `args.USER_UID/USER_GID` でホスト uid/gid を渡すと、
  コンテナ内の `dev` ユーザがそのままホストファイルを所有できる。

### なぜ named volume `cocotb-build` を分けるのか
- `sim_build/` を bind-mount 側に書くと、macOS だと I/O が遅い。
- named volume なら Linux ext4 上で動くので速い。
- `.cocotb_build/` 配下なので、消したいときは `docker volume rm` 一発。

---

## トラブルシュート

### `verilator: command not found`
Dockerfile の `RUN make install` が成功していない可能性。
ローカルで `docker compose build --no-cache` でリトライ。

### Python パッケージのバージョンを変えたい
`requirements.txt` を編集して、`docker compose build` を再実行。

### ビルドが遅い
- Verilator のソースビルドが一番重い (5〜10 分)。
- 一度成功すればキャッシュされるので、`Dockerfile` の Verilator より上の行を
  変えなければ再ビルド時間は短い。

### macOS で `--platform` 警告が出る
Apple Silicon Mac だと `linux/amd64` イメージに警告が出る。
パフォーマンス重視なら `Dockerfile` の `FROM` を `FROM --platform=linux/arm64 ubuntu:22.04`
に書き換えてもよい (ただし Verilator の挙動は arm64 の方が枯れていない)。