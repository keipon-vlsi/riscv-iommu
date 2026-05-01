# riscv-iommu-kawano

自作 RISC-V IOMMU RTL の cocotb ベース検証環境。

> 配置: この README は repo root (`riscv-iommu-kawano/README.md`) に置く想定です。

---

## 0. 全体像

```
riscv-iommu-kawano/
├── rtl/                        # 自作 IOMMU RTL (DUT)
├── packages/  vendor/  include/
│
├── third_party/
│   └── iommu-reference/        # ved-rivos の仕様著者ゴールデンモデル (submodule)
│
├── docker/
│   ├── Dockerfile              # Ubuntu 22.04 + Verilator 5.046 + cocotb 2.0
│   ├── docker-compose.yml
│   ├── entrypoint.sh
│   └── requirements.txt
│
└── tb_coco/test/                 # cocotb のシナリオを動かす場所
    ├── Makefile                  # ← ここで `make smoke` などを叩く
    ├── tb_riscv_iommu_wrapper.sv
    ├── stub/                     # common_cells/assertions.svh など
    ├── helpers/                  # IommuEnv / regs / memory / faultq / cmdq
    ├── scenarios/                # test_smoke.py / test_ptw_*.py / test_iotlb.py
    ├── translation_logic/ptw/    # モジュール単位のテスト (PTW 単体)
    ├── reference/gen_vectors/    # 仕様著者モデルからゴールデンベクタを吐く
    │   ├── Makefile
    │   ├── gen_vectors.c
    │   └── README.md
    └── _example/iommu_smoke.archive/   # 旧配置 (歴史保存用)
```

検証戦略は二系統のカバレッジを併用する **dual coverage**:

- **(A) 自作 RTL のカバレッジ** — Verilator `--coverage` を有効にして、
  どの行 / トグルが叩かれたかを確認する。実装抜けを見つけるためのもの。
- **(B) リファレンスモデル (libiommu) のカバレッジ** — `gcov`/`lcov` で
  仕様書記述の何割を踏んだかを確認する。テストパターン抜けを見つけるためのもの。

A だけだと「自作 RTL に実装されていない仕様分岐は永遠にカバレッジに現れない」ので、
B でテストの網羅性そのものを担保する。

---

## 1. 必要なもの (ホスト側)

- **Docker Desktop / Docker Engine** （バージョン 24+ 推奨）
- **Docker Compose v2** （`docker compose ...` サブコマンド）
- **git** （submodule を引くだけ）
- それ以外は **何も要らない**。Verilator も cocotb も gcc も全部コンテナの中。

> macOS / Linux / WSL2 のいずれでも動く。GTKWave で波形を見たい人だけ
> X11 forwarding の設定を `docker/docker-compose.yml` のコメントを参考に
> 有効化する。

---

## 2. クローンから最初の smoke テストまで

```bash
# (1) repo を submodule ごと取得
git clone --recurse-submodules git@github.com:<you>/riscv-iommu-kawano.git
cd riscv-iommu-kawano

# クローン済みで submodule を引き忘れていた場合:
git submodule update --init --recursive

# (2) コンテナをビルド (初回のみ・5〜15 分)
docker compose -f docker/docker-compose.yml build

# (3) 対話シェルに入る
docker compose -f docker/docker-compose.yml run --rm cocotb
# → /workspace で repo が見える状態のシェルに入る

# (3a) いきなり smoke だけ走らせたいなら ↓
docker compose -f docker/docker-compose.yml run --rm cocotb \
  bash -c "cd tb_coco/test && make smoke"
```

`make smoke` が完走すれば、Verilator + cocotb + IommuEnv の動作確認は完了。

---

## 3. ゴールデンベクタを生成する (仕様著者モデル → JSONL)

```bash
# 対話シェルの中で:
cd /workspace/third_party/iommu-reference
make -C libiommu       # libiommu.a
make -C libtables      # libtables.a

cd /workspace/tb_coco/test/reference/gen_vectors
make run               # ./gen_vectors > golden_vectors.jsonl
# 期待: 1124 行
```

`golden_vectors.jsonl` は `(B)` コードカバレッジ計測でも使うし、
Python 側 `helpers/predict.py` の入力にもなる。

---

## 4. テストの実行コマンド一覧

`tb_coco/test/` に `cd` した状態で:

| コマンド | 目的 |
| :--- | :--- |
| `make smoke` | 既存 12 ケースのリグレッション |
| `make ptw-normal` / `make ptw-fault` / `make ptw-access` | PTW 系テスト |
| `make iotlb` | IOTLB 系テスト |
| `make sim` | `MODULE` で指定された全ファイルをまとめて実行 |
| `make one MODULE=test_ptw_fault TEST=test_20_pte_invalid` | 1 ケースだけ |
| `make COVERAGE=1 sim && make coverage-report` | (A) RTL カバレッジ |

`(B)` リファレンスモデルカバレッジは:

```bash
# libiommu / libtables を --coverage 付きで rebuild してから
cd /workspace/third_party/iommu-reference
make -C libiommu   clean && make -C libiommu   CFLAGS+=--coverage LDFLAGS+=--coverage
make -C libtables  clean && make -C libtables  CFLAGS+=--coverage LDFLAGS+=--coverage

cd /workspace/tb_coco/test/reference/gen_vectors
make COVERAGE=1 clean && make COVERAGE=1 run
make coverage-report
# → libiommu_coverage_html/index.html を開く
```

---

## 5. ファイルを編集するときの所有者問題

`docker compose ... run` は `docker-compose.yml` の `args` で
`USER_UID=${UID:-1000}` / `USER_GID=${GID:-1000}` を渡すので、
ホストのユーザー uid/gid と一致したコンテナユーザでファイルを書く。

別の uid/gid のホストの場合はビルド時に明示する:

```bash
docker compose -f docker/docker-compose.yml build \
  --build-arg USER_UID=$(id -u) \
  --build-arg USER_GID=$(id -g)
```

---

## 6. CI に流すなら

GitHub Actions に乗せるなら、`docker/Dockerfile` をそのまま使って
`actions/checkout@v4` の後に submodule 込みで checkout、`docker compose build`
→ `docker compose run --rm cocotb make smoke` の 3 ステップで終わる。
ローカルと CI でビルド手順が完全に一致するので、`"私のマシンでは通る"` 問題が消える。

---

## 7. 既知の制限

- **Computer use 系の波形ビュー**: GTKWave をホストで動かしたい場合は
  `docker/docker-compose.yml` の X11 forwarding コメントを外す
  （Linux ホストのみ）。macOS の人は `*.fst` をホストに書き出して、
  ホストにインストールした GTKWave で開く。
- **Verilator バージョン**: Dockerfile で `v5.046` にピン留めしている。
  違うバージョンを試したい場合は `--build-arg VERILATOR_TAG=v5.xxx`。
- **iommu-reference のコミット固定**: submodule のポインタが repo に commit
  されているので、誰が clone しても同じ参照モデルでテストが走る。
  上流を更新したいときは `cd third_party/iommu-reference && git pull`、
  動作確認の上で `git add third_party/iommu-reference && git commit`。