# 検証環境の動作原理 (= 初心者向け徹底解説)

## まず全体像を一言で

**「参考書 (= libiommu C モデル) と自分の答案 (= RTL) を、 同じ問題で別々に解かせて、 答えを比較する」**

```
[1] 問題作成: C プログラムが libiommu に問題を解かせて、 答えと一緒に JSON に書き出す
[2] 試験実施: cocotb (Python) が JSON を読んで、 同じ問題を RTL に解かせる
[3] 採点:     diff スクリプトが 2 つの答え (JSON) を 1 件ずつ比較する
```

ここで難しい点は **「同じ問題」 を保証する仕組み**。 単に IOVA や PTE フラグを揃えるだけでは足りなくて、 **メモリ配置 (= DDT や PT を物理 RAM のどこに置いたか)** まで完全一致させないと、 IOMMU の挙動が変わってしまう。 その鍵が **`alloc` フィールド** です。

---

## なぜ「メモリ配置を揃える」 必要があるか

IOMMU の翻訳は次のようなチェーンを辿ります:

```
device_id → DDT entry  → DC (= Device Context)
                 ↓ DC が持つポインタで:
       PDT entry    → PC (= Process Context)
                 ↓ PC が持つポインタで:
       PT (S1)        → PTE
                 ↓ PTE.PPN が SPA に
```

このチェーンの各段の「ポインタ」 は **物理メモリのアドレス (= PPN)** です。 つまり libiommu と RTL の両方が、 **同じ物理アドレスを参照すれば同じ結果になる**。

例えば libiommu が「 DDT を 0x100、 PDT root を 0x102 に置きました」 と言ったら、 RTL 側も同じく 0x100 に DDT、 0x102 に PDT root を置く必要がある。 デフォルト値で適当に決めると、 libiommu と RTL でズレて、 違う page table を引いて違う結果が出てしまう。

そこで **「 C side が決めたメモリ配置を JSON に記録し、 Python side が読み込んで再現する」** という Option B の仕組みが入っています。

---

## 全体フロー (= 2 段で説明)

### 第 1 段: 問題作成 (= C プログラム)

```
┌──────────────────────────────────────────────────────────────────┐
│  ホスト側 (= ビルド時に動く C プログラム)                        │
│                                                                  │
│   gen_access_matrix_nested.c  ← 問題のパターンを定義する         │
│   gen_phase1_pte_flags.c                                          │
│   gen_nested.c                ... (= カテゴリごとに 1 ファイル)  │
│         │                                                        │
│         │ test_case_t struct (= 1 問題の仕様)                    │
│         ▼                                                        │
│   run_case(&tc, out)  ← gen_common.c が提供する共通ルーチン      │
│         │                                                        │
│         │ ① 物理 RAM の役割を決める (= どの PPN に何を置くか)    │
│         │    例: DDT=0x100, PDT_root=0x102, S1_root=0x103        │
│         │                                                        │
│         │ ② その PPN に DDT / PC / PT entries を書き込む          │
│         │    (libiommu 専用の memory[] 配列に対して)              │
│         │                                                        │
│         │ ③ libiommu に翻訳を依頼                                │
│         │    libiommu_translate(device_id, iova, access)          │
│         │                                                        │
│         │ ④ 答え (= status, PPN, fault) を捕捉                   │
│         │                                                        │
│         │ ⑤ JSON 1 行で出力 (= input + alloc + 答え 全部含む)    │
│         ▼                                                        │
│   golden_access_matrix_nested.jsonl                              │
│   {"case_id":0, "name":"...", "stage_mode":"nested_full",        │
│    "iova":"0x2345", "level":0, "flags":195, "pte_raw":"0x...",   │
│    "alloc": {"ddt":"0x100", "pdt_root":"0x102", ...},   ← ここ!  │
│    "status":1, "PPN":"0x0", "fault":{...}}                       │
└──────────────────────────────────────────────────────────────────┘
```

ここで重要なのは:
- **問題の input** (stage_mode, level, flags, iova 等)
- **メモリ配置** (alloc field)
- **期待される答え** (status, PPN, fault)

の 3 つを 1 行に詰め込んでいること。 だから JSON 1 行 = 1 個の完結した問題セット。

### 第 2 段: 試験実施 (= cocotb / Python / RTL)

```
┌──────────────────────────────────────────────────────────────────┐
│  Docker の中 (= Verilator + cocotb で動く)                       │
│                                                                  │
│   test_replay_golden.py:                                         │
│   for entry in JSON 全行:                                        │
│       │                                                          │
│       │ ① reset_for_replay(env)                                  │
│       │    DUT をリセット (= キャッシュ全クリア + FQ 再初期化)   │
│       │                                                          │
│       │ ② setup_dc_for_entry(env, entry)                         │
│       │    ├─ _apply_alloc_override で entry["alloc"] を         │
│       │    │   env の属性に注入 (= env.ddt_base_ppn = 0x100 等)  │
│       │    └─ env.install_dc_*() で AxiRam に DC を書き込む       │
│       │       ★ ここで libiommu が選んだ PPN と同じ位置に書く!   │
│       │                                                          │
│       │ ③ setup_for_entry(env, entry)                            │
│       │    pte_raw を AxiRam の指定 level の位置に書き込む       │
│       │                                                          │
│       │ ④ drive_one(env, entry)                                  │
│       │    ├─ dev_tr_read/write で翻訳要求発行                   │
│       │    ├─ FQ tail を poll で監視                             │
│       │    └─ 応答 or fault を JSON 形式で捕捉                   │
│       │                                                          │
│       ▼                                                          │
│   rtl_log.jsonl  (= 同じ schema で 1 行ずつ追記)                 │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼ diff_logs.py が突き合わせ
                          │
              ┌────────── 比較するフィールド ──────────┐
              │ status, PPN, S, fault.cause,              │
              │ fault.iotval, fault.iotval2,              │
              │ fault.ttyp, fault.did                     │
              └───────────────────────────────────────────┘
```

---

## 「同じメモリ配置」 を実現する 2 つのメモリの正体

**ここが一番分かりにくい所**。 物理的には別物だが、 「中身が同じ」 という状態を作るのが env の仕事。

| メモリ | 物理的に存在する所 | アクセスする主体 |
|--------|------------------|----------------|
| **libiommu のメモリ** | ホスト C の `g_memory` 配列 (= gen_common.c の関数で malloc) | libiommu の関数群 (= ホスト C で動く) |
| **AxiRam** | cocotbext-axi の Python 側オブジェクト | RTL (= verilator で動く) が AXI 経由で読む / cocotb が Python API で読み書き |

libiommu のメモリは、 C プログラムが終了した瞬間に消える (= 生成は build 時、 検証時にはもう無い)。 検証時には JSON だけが残っている。

RTL 側 (= AxiRam) は **検証実行時に Python から動的に書き込む**:

```python
# 例: env.install_dc_sv39_s1() の中身 (env.py:265)
addr = install_dc_1lvl(self.ds_ram,
                        ddt_base_ppn=self.ddt_base_ppn,  # ← alloc から来た値
                        did=did, dc_bytes=dc)
```

`install_dc_1lvl()` は内部で `ds_ram.write(addr, dc_bytes)` をするので、 **Python 側のメモリオブジェクトに DC のバイト列を書き込む**。 これが RTL から見たら「 ds_ram の 0x100xxx に DC が書かれている」 状態。

つまり:
- C 側: g_memory[0x100xxx] に DC を書く → libiommu が翻訳時に読みに行く
- Python 側: ds_ram[0x100xxx] に DC を書く → RTL が AXI 経由で読みに行く

**書き込むバイト列の中身も同じ、 書き込むアドレスも同じ** → 両者が同じ翻訳を実行する保証。

---

## 1 件の case を具体的に追ってみる

例: `access_matrix_nested case 0 's1vary_u0_r0_w0_x0_accr'` (= R=0/W=0/X=0/U=0 で read access)

### (1) C 側 (gen_access_matrix_nested.c:38-54)

```c
uint8_t s1f = make_flags(0, 0, 0, 0);   // V=1, A=1, D=1 だけ、 R/W/X/U は全部 0
// → s1f = 0xC1 = 11000001 (V=1, A=1, D=1)

test_case_t tc = {0};
tc.case_id = 0;
tc.name = "s1vary_u0_r0_w0_x0_accr";
tc.category = "access_matrix_nested";
tc.stage_mode = STAGE_NESTED_FULL;
tc.level = 0;
tc.flags = 0xC1;
tc.s2_level = 0;
tc.s2_flags = 0xDF;       // S2 PTE は全フラグ立ち (= 制約なし)
tc.access = ACC_READ;
run_case(&tc, out);       // ← ここで全部やる
```

### (2) run_case() の中身 (= gen_common.c、 推測ベース)

run_case の中で典型的に行われること:
1. `g_memory` を確保 (= libiommu 用の仮想メモリ)
2. PPN の役割を決定: ddt=0x100, fq=0x101, pdt_*=0x102/0x104/0x105, iohgatp_root=0x..., s1_root=0x103, etc.
3. その PPN 位置に DC, PC, PT entries を組み立てて書き込む
4. `tc.flags` に基づいて test 対象 PTE を S1 leaf (= level 0) の位置に書く
5. `tc.s2_flags` に基づいて S2 leaf を G-stage の対応位置に書く
6. libiommu API 呼び出し:
   ```c
   libiommu_translate(device_id=0, iova=0x2345, access=ACC_READ, ...)
   ```
7. libiommu は内部で:
   - g_memory[0x100xxx] から DC を読む
   - g_memory[0x102xxx] から PDT 中間 NL を読む (... 3 段)
   - g_memory[0x105xxx + offset] から PC を読む
   - g_memory[0x103000] から S1 root PTE を読む
   - g_memory[<g_root>...] から S2 PTE をたどる
   - leaf 到達 → 検査 (R=0 で read 不可) → fault
8. 戻り値: `{status=1, cause=13, iotval=0x2345, iotval2=0x0}`
9. JSON に出力:
   ```json
   {"case_id":0, "name":"s1vary_u0_r0_w0_x0_accr", "category":"access_matrix_nested",
    "stage_mode":"nested_full", "iova":"0x2345", "level":0, "flags":193,
    "s2_level":0, "s2_flags":223, "access":"read",
    "pte_raw":"0x000000000300c1", "s2_pte_raw":"0x...",
    "alloc":{"ddt":"0x100","fq":"0x101","pdt_root":"0x102", ...},
    "status":1, "PPN":"0x0", "S":0,
    "fault":{"cause":13, "iotval":"0x2345", "iotval2":"0x0", "ttyp":2, "did":0}}
   ```

これでこの case の JSON 1 行ができる。 同様にして 10,382 件分が生成される。

### (3) Python 側 (test_replay_golden.py + replay.py)

```python
# test_replay_golden.py の主ループ抜粋:
for i in range(start_idx, end_idx):
    entry = all_entries[i]      # ← 上で作った JSON 1 行
    
    await reset_for_replay(env) # DUT リセット
    await setup_dc_for_entry(env, entry)  # ① DC を AxiRam に書き込む
    setup_for_entry(env, entry)           # ② PT を AxiRam に書き込む
    rtl_resp = await drive_one(env, entry)  # ③ 翻訳駆動 → 応答捕捉
    
    logf.write(json.dumps(rtl_resp) + "\n")
```

詳細を追うと:

**setup_dc_for_entry (replay.py:143)** の冒頭:
```python
async def setup_dc_for_entry(env, entry):
    _apply_alloc_override(env, entry)   # ★ ここで alloc を env に注入
    mode = entry.get("stage_mode", "s1_only")
    if mode in ("nested", "nested_full"):
        await env.install_dc_2stage(did=GOLDEN_DID)
    ...
```

`_apply_alloc_override` (replay.py:94):
```python
def _apply_alloc_override(env, entry):
    alloc = entry.get("alloc")
    if not alloc:
        return
    mapping = (
        ("ddt",     "ddt_base_ppn"),
        ("fq",      "fq_base_ppn"),
        ("pdt_root","pdt_root_ppn"),
        ...
    )
    for jsonl_key, env_attr in mapping:
        if jsonl_key in alloc:
            ppn = _parse_ppn(alloc[jsonl_key])
            setattr(env, env_attr, ppn)   # ← env.ddt_base_ppn = 0x100 とか
```

つまり JSON の "alloc" を読んで env の属性を **C 側と同じ値に書き換える**。 これで以降の install_dc_* が AxiRam の同じ場所にデータを書く。

**env.install_dc_2stage()** (env.py:294):
```python
async def install_dc_2stage(self, *, did=0, ...):
    dc = build_dc_sv39_2stage(s1_root_ppn, g_root_ppn, gscid=gscid)
    addr = install_dc_1lvl(self.ds_ram,
                            ddt_base_ppn=self.ddt_base_ppn,  # ← 0x100
                            did=did, dc_bytes=dc)
    await configure_ddt_mode(self.prog_master, self.dut,
                              mode=DDTP_MODE_1LVL,
                              ddt_base_ppn=self.ddt_base_ppn)
```

- `build_dc_sv39_2stage()` で DC のバイト列を組み立て (= libiommu が作ったのと同じ構造)
- `install_dc_1lvl()` で AxiRam (= ds_ram) の `ddt_base_ppn` 位置に書き込む
- `configure_ddt_mode()` で DDTP レジスタを programming AXI 経由で設定

**setup_for_entry (replay.py:179)**:
mode に応じて分岐。 例えば nested の場合:
```python
elif mode == "nested":
    leaf_ppn_from_pte = (pte_raw >> 10) & 0x0FFF_FFFF_FFFF
    setup_sv39x4_identity_4k_for_ppns(...)  # ← S2 を 4K identity で透過化
    setup_sv39_custom_at_level(            # ← test 対象 S1 leaf PTE を配置
        env.ds_ram,
        root_ppn=env.s1_root_ppn, ...
        pte_bytes=pte_bytes,
    )
```

これも C 側と同じ位置に PTE を書き込む。

**drive_one (replay.py:396)**:
```python
async def drive_one(env, entry, *, settle_cycles=300, post_cycles=30):
    access = entry["access"]
    iova = _entry_iova(entry)
    
    rd_done = Event()
    rd_data_holder = [None]
    
    async def _fire():        # 翻訳要求発行 (background)
        if access == "read":
            op = await env.dev_tr_read(iova, length=8, ...)
            rd_data_holder[0] = int.from_bytes(op.data, "little")
        else:
            await env.dev_tr_write(iova, b"\x00"*8, ...)
        rd_done.set()
    
    cocotb.start_soon(_fire())
    
    # FQ tail を poll で監視 + rd_done を待つ
    for _ in range(settle_cycles):
        tail = await env.fq.read_tail()
        if tail != env.fq.head_local:        # FQ に新しい fault entry が!
            records = await env.fq.drain()
            found_fault = records[0]
            break
        if rd_done.is_set():                  # AXI 応答が返ってきた
            break
        await RisingEdge(env.dut.clk_i)
    
    if found_fault is not None:
        return _format_fault(entry, found_fault)
    return _format_success(entry, rd_data_holder[0])
```

ここで RTL が:
- 翻訳成功 → `tr_master.read()` が AXI 応答を返す → `rd_done.set()`
- 翻訳失敗 → `fq_handler` が FQ に fault entry を書き込む → tail 変化を検出

両者の結果を JSON 形式 (= ref と同じ schema) で記録する。 これが `rtl_log.jsonl` に追記される。

### (4) 比較 (diff_logs.py)

`rtl_log.jsonl` と `golden_*.jsonl` を `(category, case_id)` キーで突き合わせる。 7 つのフィールド (= status, PPN, S, fault.cause, fault.iotval, fault.iotval2, fault.ttyp, fault.did) を 1 件ずつ比較。

例えば case 0 で:
- ref: `{cause: 13, iotval: 0x2345, iotval2: 0x0}`
- rtl: `{cause: 21, iotval: 0x2345, iotval2: 0x2345}`

→ cause が違う、 iotval2 が違う → 不一致と報告。

---

## なぜこの設計が良いか

**1. 検証信頼度が極めて高い**
- libiommu は spec の official reference (= 仕様書を書いた人達が作ったもの)
- それと bit 一致を要求するので、 spec 違反は物理的に検出される

**2. RTL 内部実装の自由度が高い**
- 比較するのは **外部 interface** だけ (= AXI 応答 + FQ entry)
- 内部 module 分割、 pipeline 構造、 cache 戦略は何でも OK
- ⇒ OoO walks / multi-master arbitration / 新しい cache policy 等の実装変更がやりやすい

**3. 「同じ問題」 の保証が alloc 経由で自動化されている**
- メモリ配置を手動で揃えるのは大変だしバグ源 (= 1 つズレるだけで全 case 落ちる)
- alloc field で **C 側のメモリ配置を Python 側に翻訳** する仕組みで自動化

**4. JSON 1 行 = 1 完結問題 という設計**
- どの case で何が起きたか、 入力 / 期待 / 実際の差分が即座に分かる
- shift match (= 順序ずれ許容) や category 単位の集計が簡単

---

## あなたが書き換えたら良さそうな所 (= プレゼン slide 12 の「学び」 ネタ)

検証環境のうち、 次の 2 つは特に「初心者の盲点」 になる場所:

### 盲点 1: alloc field の存在

「ただの便利機能」 と思いがち。 実は **これが無いと libiommu と RTL のメモリ配置が違って何も動かない**。 引き継ぎ doc に書いてあった「 Option B」 はこれ。

### 盲点 2: drive_one() の polling 戦略

「待ち時間」 のロジックがシンプルすぎる。 settle_cycles だけだと、 応答が遅れる case を timeout に誤検出する。 watchdog (= 私が追加した部分) は debug 用の補強。

---

## まとめ (= 30 秒版)

| 段階 | やること | 出力 |
|------|--------|------|
| C generator | libiommu で問題を解く + メモリ配置記録 | golden_*.jsonl |
| Python cocotb | JSON を読んで RTL に同じ問題を解かせる | rtl_log.jsonl |
| diff | 2 つの JSON を field 単位で比較 | per-category 一致表 |

**鍵となる仕組みは "alloc" field**: C side が決めたメモリ配置 (= どの PPN に何を置いたか) を JSON に保存し、 Python side がそれを読んで AxiRam に再現する。 これにより libiommu と RTL が **同じバイトを同じアドレスから読む** ことが保証される。

---

## プレゼンで触れる時の流れ (= slide 8 の 90 秒)

> 「(1) C リファレンス libiommu に同じ問題を解かせて、 入力と答えと **使用したメモリ配置** を JSON に記録。 (2) cocotb 側がそれを読んで、 alloc field を頼りに AxiRam を同じ配置に再現。 RTL に同じ問題を流して、 同じ schema で応答記録。 (3) 7 フィールドで bit-exact 比較。 18 カテゴリ × 10,382 件で網羅検証。 ポイントは alloc field — これが C と RTL のメモリを揃えるブリッジ」
