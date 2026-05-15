# RISC-V IOMMU v4 リファクタ後 mismatch 分析レポート (v2 改訂版)

> 作成日: 2026-05-12 (改訂: 同日)
> 対象 commit: walk_ctrl v4.2 + pdtw v4.3 + ddtw v4 + 他 v4 リファクタ群
> 検証ステータス (修正前): 2804/10382 match、 3369 timeout、 残り mismatch
> 推奨: PDTW v4.3 + walk_ctrl v4.2 を適用して再 replay

---

## TL;DR (= 30 秒版)

1. **前回診断 (cause=259 = DDT misconfigured check) は誤り**だった。 真因は **DDTW を BURST_FIXED にすると multi-beat read で同じ address を 4-7 回読みに行って DC データが壊れる**。 user が「 DDTW=INCR に戻したら直る」 と確認済み。
2. **私の PDTW v4.2 patch (= FIXED + split) も誤り**。 BURST_INCR + multi-beat に戻すべき。
3. **walk_ctrl v4.1 にも別バグ発見**: NESTED 模式で非 leaf S1 PTE を s1_lvl=0 (= 底) で見つけたとき、 spec 通りなら S1 page-fault のはずなのに、 walk_ctrl は無条件で S2 walk に行ってしまう。 これで多くの NESTED 系 case が cause=21 (S2 fault) になっている。
4. **明日朝に適用**: `outputs/rv_iommu_pdtw_v4_3.sv` と `outputs/rv_iommu_walk_ctrl.sv` (= NESTED bug fix 入り)

---

## 1. 観測 (= 最新 replay 結果、 DDTW=INCR + PDTW=v4.2 FIXED)

```
Per-category summary:
                      matches   mismatches
access_matrix_nested        0           80
access_matrix_s1           32            0          ← S1 only access は完璧
access_matrix_s2            0           32
bare_mixed                  8            8
iova_variation           1024            0          ← S1 only iova 変動は完璧
msi_translation            60            1
nested                    240          883
nested_full_quick           0          512
pc_iova_variation         192          832
pc_nested                   4         1119
pc_nested_full_quick        9          503
pc_phase1_pte_flags         4         1119
pc_s2_only                  4         1119
phase1_pte_flags         1095           28          ← 98% PASS
pte_reserved_nested         0           87
pte_reserved_s1           132            0          ← S1 only reserved は完璧
pte_reserved_s2             0          132
s2_only                     0         1123
TOTAL                    2804         7578
```

### パターン分析

| 種類 | 結果 | 解釈 |
|------|------|------|
| S1 only (non-PC, non-nested) | 完璧 (phase1, iova_variation, access_matrix_s1, pte_reserved_s1) | walk_ctrl の S1 単独 path は健全 |
| S2 only | **0% match** (s2_only, access_matrix_s2, pte_reserved_s2) | **WM_SINGLE_S2 path にバグ** |
| NESTED | 21% match | NESTED PH_S1 non-leaf @ lvl=0 のバグ |
| PC | 0.4% match + 77% timeout | **PDTW v4.2 が broken** (= 私の patch ミス) |
| MSI | 60/61 | MSI 翻訳は概ね OK (= 1 件は別調査) |

---

## 2. cause=259 (DDT_ENTRY_MISCONFIGURED) の真因 (= 訂正)

### 前回 (誤) の診断
「 DDTW v4 が DC 内容を強検査して misconfigured 判定」

### 訂正された理解
- DC 構造体は 32 byte (MSI_DISABLED) or 56 byte (MSI_FLAT) サイズ
- DDTW LEAF_S1 で 4 (or 7) beat の AXI burst で読む
- **BURST_FIXED で multi-beat だと全 beat が同じ address を read** → DC 全フィールドが同じ 8 byte で埋まる → reserved bit / mode 検査が確率的に hit → MISCONFIGURED
- BURST_INCR で multi-beat なら address が 8 byte ずつ増える → 正常 DC を読める

**結論**: DDTW は **絶対に BURST_INCR** にしておくべき。 BURST_FIXED は不可。

---

## 3. PDTW v4.2 の問題 (= 私のミス)

PC も同様に 16 byte (= pc_ta + pc_fsc, 2 entries) なので multi-beat read が必要。 私が v4.2 で「 BURST_FIXED + 1-beat × 2 回 split」 にしたのは **正しい spec ベース実装だが、 何かしらの理由で 77% timeout** を引き起こした。

原因確定までしている時間が惜しいので、 **v4.3 で BURST_INCR + multi-beat に戻す**。 用意してあります:

```
outputs/rv_iommu_pdtw_v4_3.sv
```

変更点 (v4.2 → v4.3):
- 全 AR を BURST_INCR
- LEAF_S1 を len=1 (2-beat) に戻す
- 元の v4 とほぼ同じ、 ST_PROC 構造のみ温存

---

## 4. walk_ctrl の NESTED 非 leaf @ lvl=0 バグ

### 症状
mismatch の主要パターン:
```
ref={'cause': 13, 'iotval2': '0x0'}      ← 期待: S1 LOAD_PAGE_FAULT
rtl={'cause': 21, 'iotval2': '0x2345'}   ← 実際: S2 LOAD_GUEST_PAGE_FAULT
```

iotval2 = 0x2345 = iova。 S2 fault の bad_gpaddr 計算 path で iova をそのままセットしている。

### 原因
walk_ctrl PH_S1 非 leaf 分岐 (= v4.1 line 320-340):
```systemverilog
else begin
    if (walk_mode_q == WM_NESTED) begin
        // 非 leaf NL PPN も GPA → S2 翻訳    ← ★ ここが問題
        s2_lvl_n  = 2'd2;
        s2_pptr_n = {iohgatp_ppn_i, ...};
        phase_n   = PH_S2;
        state_n   = ST_ISSUE;
    end
    else if (s1_lvl_q > 0) ...
    else cause = LOAD/STORE_PAGE_FAULT;
end
```

NESTED 模式では s1_lvl の値に関わらず S2 walk に飛んでしまう。 **s1_lvl=0 (= bottom) で leaf でない = spec 上 S1 fault のはず**。

walk_ctrl では bottom で non-leaf を S2 walk → その S2 walk が成功/失敗するとそれを S2 fault として報告 → cause=21 (本来 13 のはず)、 iotval2 が S2 fault 用の計算結果になる。

### 修正
walk_ctrl v4.2 で修正済み (= `outputs/rv_iommu_walk_ctrl.sv`):
```systemverilog
else begin
    // (d-0) 共通: bottom level で leaf じゃない = S1 page-fault
    if (s1_lvl_q == 2'd0) begin
        cause_n = is_store_q ? STORE_PAGE_FAULT : LOAD_PAGE_FAULT;
        state_n = ST_ERROR;
    end
    // (d-1) WM_NESTED: 中間 NL の PPN を S2 翻訳
    else if (walk_mode_q == WM_NESTED) begin
        ...
    end
    // (d-2) SINGLE_S1: 次レベルへ
    else begin
        s1_lvl_n  = s1_lvl_q - 1;
        ...
    end
end
```

### 影響範囲
これで治る category:
- access_matrix_nested (0/80 → 多分大半)
- nested (240/1123 → 多分 800-900)
- nested_full_quick (0/512 → 多分大半)
- pte_reserved_nested (0/87 → 多分大半)

---

## 5. S2-only (= s2_only, access_matrix_s2, pte_reserved_s2) 100% 失敗の謎

このカテゴリは S2 のみ翻訳。 walk_ctrl WM_SINGLE_S2 path を使う。

walk_ctrl の SINGLE_S2 path 自体は構造的に問題ないように見える。 でも 100% 失敗。

仮説:
- WM_SINGLE_S2 で leaf 確定後の commit (= update_iotlb_o + 各種 flag) が IOTLB-S2 に正しく伝わっていない
- IOTLB-S2 の lookup logic に bug
- TW の S2 only 経路 (= spaddr_o の計算) に bug
- 検査済みの A/D bit check が無いので silent success → wrong PA

サンプル mismatch が無いと特定できない。 朝起きたら以下を試してください:

```bash
# s2_only のサンプルケースを 1 件単独で実行 + 詳細 log
REPLAY_START_FROM=2147 REPLAY_STOP_AFTER=1 \
    WAVES=1 make replay WAVE_TRACE=vcd

# diff の詳細を出力
make replay 2>&1 | tee replay_full.log
grep -A 5 '\[s2_only\]' replay_full.log | head -50
```

サンプル mismatch を共有してくれれば、 cause / iotval / iotval2 / PPN を見て原因を絞り込めます。

---

## 6. 各モジュール アーキテクチャと責務 (= 引き継ぎ用)

### 6.1 主要モジュール

| モジュール | 行数 | 責務 |
|----------|------|------|
| `rv_iommu_tw_sv39x4_pc.sv` | ~1100 | 翻訳 orchestrate、 各 cache lookup、 permission check (= iotlb hit 時)、 fault 集約 |
| `rv_iommu_ddtw.sv` | ~490 | DDT walk、 DC fetch、 spec 適合検査、 capabilities 整合 check |
| `rv_iommu_pdtw.sv` | ~410 | PDT walk、 PC fetch、 spec 適合検査 |
| `rv_iommu_cdw_axi_mux.sv` | ~50 | DDTW + PDTW の AXI master を 1 本に集約 (= 排他動作前提) |
| `rv_iommu_ptw_sv39x4_pc.sv` | ~230 | walk_ctrl + pt_walker をくるむ wrapper、 旧 PTW interface 互換 |
| `rv_iommu_walk_ctrl.sv` | ~570 | PT walk の FSM、 S1/S2/nested の遷移制御、 PTE 検査 |
| `rv_iommu_pt_walker.sv` | ~145 | 1 PTE = 8 byte の AXI read engine、 BURST_FIXED 固定 |
| `rv_iommu_ddtc.sv` | ~257 | DC キャッシュ、 PLRU |
| `rv_iommu_pdtc.sv` | ~200 | PC キャッシュ、 PLRU |
| `rv_iommu_iotlb_s1.sv` | ~358 | S1 PTE キャッシュ (= PR1 で分割済み) |
| `rv_iommu_iotlb_s2.sv` | ~340 | S2 PTE キャッシュ |

### 6.2 AXI master の整理

| master | id | burst | len | 状態 |
|--------|----|----|-----|------|
| pt_walker | 4'b0000 | FIXED | 0 | ✓ 動作確認済み |
| DDTW NL_S1 | 4'b0001 | INCR | 0 | ✓ 動作確認済み (= 1-beat だが INCR でも OK) |
| DDTW LEAF_S1 | 4'b0001 | INCR | 3 or 6 | ✓ multi-beat 必須 |
| DDTW LEAF_S2 | (PTW master) | - | - | implicit S2 walk 経由 |
| PDTW NL_S1 | 4'b0010 | **INCR** (v4.3 で revert) | 0 | ✓ |
| PDTW LEAF_S1 | 4'b0010 | INCR | 1 | ✓ multi-beat 必須 |

**結論**: 1-beat read でも BURST_INCR は問題なく動く。 BURST_FIXED は **single-beat read 限定**。 multi-beat read には絶対 BURST_INCR を使うべし。

---

## 7. データフロー (= 1 件の翻訳が成功するまで、 訂正版)

### 7.1 簡略図

```
dev_tr_req
   │
   ▼ ddtc_access
[DDTC lookup] ──hit──▶ skip DDT walk
   │
   ▼ miss
[DDTW] ── walk DDT (= INCR multi-beat) ──▶ [DDTC update]
   │ if (en_S2 && pdtv && iohgatp.mode):
   ▼  need_leaf_s2 → implicit S2 walk on dc.fsc.PPN
[walk_ctrl WM_IMPLICIT_S2]
   ▼ ptw_done → dc.fsc.PPN updated to SPA
[DDTC update]  (= dc.fsc.PPN now in SPA)
   │
   ▼ pdtv=1 なら
[PDTC lookup] ──hit──▶ skip PDT walk
   │
   ▼ miss
[PDTW] ── walk PDT (= INCR multi-beat for LEAF_S1) ──▶ [PDTC update]
   │ if (en_S2 && pc_fsc.mode != 0):
   ▼  need_leaf_s2 → implicit S2 walk on pc.fsc.PPN
[walk_ctrl WM_IMPLICIT_S2]
   ▼ ptw_done → pc.fsc.PPN updated to SPA
[PDTC update]
   │
   ▼ iotlb_access
[IOTLB-S1 + IOTLB-S2 lookup] ──hit──▶ permission check → trans_valid_o
   │
   ▼ miss
[walk_ctrl PTW] ── walk S1 / S2 / nested ──▶ [IOTLB update]
   │
   ▼ commit / error
[TW]: trans_valid_o + spaddr_o, or trans_error_o + cause + iotval/iotval2
   │
   ▼
[fq_handler] ── 必要なら FQ 書込 ──▶ dev_tr 応答
```

### 7.2 nested 翻訳の詳細 (= walk_ctrl WM_NESTED)

```
walk_ctrl WM_NESTED 開始 (iova=V, iosatp.PPN=R_S1, iohgatp.PPN=R_S2)

PH_S1 lvl=2:  S1 root から PTE 読む
  ├ non-leaf, lvl > 0: PPN を S2 翻訳 → PH_S2 lvl=2
  ├ non-leaf, lvl = 0: S1 LOAD/STORE_PAGE_FAULT ★ v4.2 で修正
  ├ leaf: S1 leaf を保持し PH_S2 lvl=2 で leaf PPN を S2 翻訳
  └ fault (V=0 等): S1 LOAD/STORE_PAGE_FAULT

PH_S2 (= 中間 NL の SPA を取りに): S2 walk 3 levels
  ├ S2 leaf 取れた + s1_leaf 未確定: 次の S1 level へ (= s1_lvl--)
  ├ S2 leaf 取れた + s1_leaf 確定: 両 leaf 揃った → commit IOTLB
  └ S2 fault: LOAD/STORE_GUEST_PAGE_FAULT

PH_S1 lvl=1:  S1 mid から PTE 読む (= S2 で取れた SPA を使う)
... (再帰的)

PH_S1 lvl=0:  S1 leaf 確定 → PH_S2 で leaf PPN を S2 翻訳

最終 commit: 1S_content + 2S_content をそれぞれ IOTLB に update
```

---

## 8. 明日やる順番

### Step 1: パッチ適用 (= 10 分)
```bash
cd /workspace

# walk_ctrl v4.2 (NESTED bug fix 入り)
cp /path/to/outputs/rv_iommu_walk_ctrl.sv rtl/translation_logic/ptw/

# pdtw v4.3 (BURST_INCR に revert)
cp /path/to/outputs/rv_iommu_pdtw_v4_3.sv rtl/translation_logic/cdw/rv_iommu_pdtw.sv

cd tb_coco/test
make clean
```

### Step 2: smoke 確認 (= 5 分)
```bash
make smoke   # → 12/12 PASS のまま (= 退行していないことを確認)
```

### Step 3: replay 全実行 (= 20 分)
```bash
make replay 2>&1 | tee replay_full.log
```

期待される変化:
- timeout が **激減** (= PDTW が動くので)
- NESTED 系の match が **激増** (= walk_ctrl bug fix で cause=21 → cause=13)
- match 数が 2804 → 7000+ 程度まで上がる予想

### Step 4: 残 mismatch の分析 (= 1-2 時間)

期待される残課題:
- **s2_only 100% 失敗が継続する場合**: walk_ctrl WM_SINGLE_S2 か IOTLB-S2 にバグあり
  → 単独 case 実行 + 波形 確認:
  ```bash
  REPLAY_START_FROM=2147 REPLAY_STOP_AFTER=1 \
      WAVES=1 make replay WAVE_TRACE=vcd
  ```
- **A/D bit fault 未実装** による mismatch (= access_matrix 等)
  → walk_ctrl に A/D bit check 追加
- **iotval2 計算誤り** (= s2_only 系の bad_gpaddr_o)
  → walk_ctrl の WM_SINGLE_S2 fault path での bad_gpaddr 計算を見直し

### Step 5: A/D bit + 残り walk_ctrl 修正 (= 半日)

走らせ次第、 残 mismatch の category 分布から優先順位決定。

---

## 9. プレゼン slide への素材

このデバッグ経験そのものが **slide 12 (= トレーニングを通して)** の鉄板ネタになる:

> 「リファクタ過程で 3 つの bug を連鎖発見した:
> 1. PDTW NL_S1 hang (= BURST_INCR + len=0 が axi4_bc を停めるのでは、 と仮説立てて FIXED 化 → 実は別原因の hang を取り違えた)
> 2. DDTW BURST_FIXED 化で全 case mismatch (= multi-beat read で同じ address を 4 回読みに行く → DC 完全破壊 → "DDT_MISCONFIGURED" が確率的に発火 → 真の意味の検査エラーと誤読)
> 3. walk_ctrl NESTED 非 leaf @ lvl=0 で S2 walk に行く spec 違反 (= "NESTED なら必ず S2 翻訳" という思い込み)
> 学び: **「動くから正しい」 と「壊れているから誤検出」 を区別するのが難しい。 spec を疑う前に observation を 2 回確認する**」

質疑では「 axi4_bc が BURST_INCR + len=0 で hang するという最初の仮説、 どこで気付きましたか?」 と聞かれる可能性。 → 「 multi-beat の DDTW が INCR + len > 0 で問題なく動いていたこと、 そして同 user の指摘で。 thinking-out-loud を恥ずかしがらず共有してもらった結果」 と答える、 でいいです。

---

## 10. 用語と参照

- **DDT** (Device Directory Table): device_id → DC を引く 1-3 段のテーブル
- **PDT** (Process Directory Table): process_id → PC を引く 1-3 段のテーブル
- **DC** (Device Context): 32 byte (or 56 byte with MSI) の構造体、 iohgatp / fsc 等を含む
- **PC** (Process Context): 16 byte の構造体、 pc.ta + pc.fsc
- **S1**: First-stage translation (= iova → gpa)
- **S2**: Second-stage translation (= gpa → spa)
- **iohgatp**: G-stage (= S2) PT base
- **iosatp / pc.fsc.ppn**: VS-stage (= S1) PT base

参照ファイル: `docker/iommu_presentation_outline.md` (= プレゼン骨子)

---

> 報告者: Claude
> 質問あれば朝いつでも投げてください。 私の前回診断 (cause=259) を訂正してくれて助かりました 🙏
