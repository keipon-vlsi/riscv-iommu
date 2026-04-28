---
module: rv_iommu_ptw_sv39x4_pc
source: rtl/translation_logic/ptw/rv_iommu_ptw_sv39x4_pc.sv
module_card: doc/modules/rv_iommu_ptw_sv39x4_pc.md
must_test: doc/test-plan/_must_rv_iommu_ptw_sv39x4_pc.md
tb_dir: tb_coco/test/translation_logic/ptw/
reviewed: true
reviewed_by: null
reviewed_date: null
last_modified_by_claude: 2026-04-27
last_status_update: null
generated: 2026-04-27
---

> ⚠️ **レビュー状態: ⏳ レビュー待ち (reviewed: false)**
>
> このテストプランは Claude が生成/更新した直後の状態です。
> 内容を確認したら frontmatter の `reviewed: true` に変更してください。
> Claude は `reviewed: true` の状態でないと TB 生成に進みません。

# テスト計画: `rv_iommu_ptw_sv39x4_pc`

> モジュールカード: `doc/modules/rv_iommu_ptw_sv39x4_pc.md`
> TB 場所: `tb_coco/test/translation_logic/ptw/`
> 最終更新: 2026-04-27

---

## ウォーク階層の定義

| 記号 | 意味 | Sv39 VPN フィールド |
|---|---|---|
| LVL1 | 最上位 (root) | VPN[2] — 最も浅い |
| LVL2 | 中間 | VPN[1] |
| LVL3 | 最下位 (leaf) | VPN[0] — 最も深い |

4K ページウォークでは LVL1 → LVL2 → LVL3 の順に深くなる。LVL3 が leaf PTE。

---

## RTL 制約事項 (必読)

以下は RTL 解析で確認した現実装の制約。テスト期待値の設定に影響する。

### 1. アクセスタイプ識別
- `is_rx_i` はコメントアウト (`rv_iommu_ptw_sv39x4_pc.sv:50`)
- PTW は **STORE / 非STORE** のみ区別する
- INSTR_PAGE_FAULT (12) / INSTR_GUEST_PAGE_FAULT (20) は PTW では **生成されない**
- `is_store_i=0` → LOAD_PAGE_FAULT(13) / LOAD_GUEST_PAGE_FAULT(21)
- `is_store_i=1` → STORE_PAGE_FAULT(15) / STORE_GUEST_PAGE_FAULT(23)

### 2. AXI エラー cause code
- AXI error (r.resp≠OKAY) → **PT_DATA_CORRUPTION (274) 固定**
- must_test 記載の 1 (INSTR_ACCESS_FAULT) / 5 (LD_ACCESS_FAULT) / 7 (ST_ACCESS_FAULT) は誤り
- 正しい期待値: 常に 274

### 3. 葉 PTE 権限チェックのスコープ外
PTW は以下の葉 PTE チェックを **行わない**（Wrapper/IOTLB 層で実施）:
- A-bit (accessed) が 0
- D-bit (dirty) が 0 の STORE アクセス
- W-bit が 0 の STORE アクセス
- R-bit が 0 の LOAD アクセス (ただし R=0,W=1 は BR09 で検出)
- X-bit が 0 の INSTR アクセス

これらのシナリオでは PTW は **update_o=1 を返す** (フォルトなし)。
対応するテスト (T17-T20, T38-T40, T60-T62) は must_test 由来で記録するが、
期待値は「PTW 成功 (update_o=1)」であることに注意。

---

## 1. テスト目標

- `doc/test-plan/_must_rv_iommu_ptw_sv39x4_pc.md` の全シナリオを T-ID として網羅
- モジュールカード §6 の **BR01–BR33** を可能な限り網羅 (30/33 BR — BR13/BR32/BR33 は MSITrans!=DISABLED が必要)
- 正常系: S1-only / S2-only / nested の 4K ページウォークが完走し `update_o` がアサートされること
- フォルト系 (PTW 検出): invalid PTE, reserved bits, AXI error, 非リーフ A/D/U, LVL3 非リーフ, S2 leaf U=0, S1 GPPN 上位, スーパーページミスアライン
- フォルト系 (Wrapper scope): 葉 A/D/W/R/X チェック — PTW は update_o=1; テストは「スコープ外」として記録
- エッジケース: G ビット伝播、CDW 暗黙的変換、back-to-back、リセット中断、バックプレッシャ
- ランダム: 100 ケース × 3 関数で IOVA/GPA 空間を探索
- **スコープ外**: MSI 変換 (MSITrans=DISABLED)、Wrapper 層のパーミッション検査

---

## 2. テスト設定

| 項目 | 値 |
|---|---|
| **シミュレータ** | Verilator (cocotb) |
| **TB ディレクトリ** | `tb_coco/test/translation_logic/ptw/` |
| **トップモジュール** | `tb_rv_iommu_ptw_sv39x4_pc_wrapper` |
| **実行コマンド** | `cd tb_coco/test/translation_logic/ptw && make` |
| **ログ保存** | `cd tb_coco/test/translation_logic/ptw && make sim-log` |
| **Status 更新** | `/update-test-status rv_iommu_ptw_sv39x4_pc` |
| **ゴールデンモデル** | `tb_coco/common/helpers.py::translate_sv39_golden` |

---

## 3. BR カバレッジ計画

| BR-ID | 概要 | カバー方法 | T-ID |
|---|---|---|---|
| BR01 | `!edge_trigger_q && init_ptw_i` (立ち上がり検出) | init_ptw_i エッジ生成 | T03 |
| BR02 | `edge_trigger_q && !init_ptw_i` (立ち下がり検出) | init_ptw_i 保持後の解除 | T03 |
| BR03 | ウォーク開始条件 (`init_ptw_i || cdw_implicit`) | T03 (init), T04 (CDW) | T03, T04 |
| BR04 | `{en_1S, en_2S}` 4-way 分岐 | S1/S2/Nested の各モード | T10, T30, T50 |
| BR05 | CDW 暗黙的か否か (S2-only 開始時) | cdw_implicit_access_i 有無 | T30, T71 |
| BR06 | `ar_ready` で PROC_PTE 遷移 | 正常ウォーク全般 | T10 |
| BR07 | `r_valid` で PTE 処理開始 | 正常ウォーク全般 | T10 |
| BR08 | `pte.g && STAGE_1` → global_mapping 伝播 | 中間 PTE に G=1 設定 | T70 |
| BR09 | `!pte.v \|\| (!pte.r && pte.w)` → PAGE_FAULT | v=0 / R=0,W=1 の各 LVL | T11, T31, T52 |
| BR10 | `pte.r \|\| pte.x` → leaf/non-leaf 分岐 | 正常系(leaf)とフォルト系(non-leaf) | T10, T14 |
| BR11 | `case(ptw_stage_q)` in leaf_pte | STAGE_1/INTERMED/FINAL の遷移 | T50, T51 |
| BR12 | `en_2S_i` (S1 leaf 後の S2-FINAL 継続) | en_2S=1 での S1 完了後 | T50, T51 |
| BR13 | `gpaddr_is_msi` 検出 | **UNTESTABLE** (MSITrans=DISABLED) | — |
| BR14 | IOTLB update / cdw_done アサート条件 | 正常系ウォーク完了 | T10, T30, T51 |
| BR15 | `!cdw_implicit_access_q` → update_o vs cdw_done_o | CDW 暗黙的有無 | T71 |
| BR16 | 1G ミスアライン: `LVL1 && \|pte.ppn[17:0]` | S1/S2 LVL1 leaf の ppn[17:0]≠0 | T16, T36, T58 |
| BR17 | 2M ミスアライン: `LVL2 && \|pte.ppn[8:0]` | S1/S2 LVL2 leaf の ppn[8:0]≠0 | T16, T36, T58 |
| BR18 | `ptw_stage != STAGE_1 && !pte.u` (S2 leaf) | S2-FINAL leaf で u=0 | T37, T59 |
| BR19 | `main_lvl == LVL1` → LVL2 進行 (非リーフ) | 3-level walk の LVL1 非リーフ | T10, T50 |
| BR20 | `en_2S_i` (S1/LVL1 非リーフ) → S2-INTERMED | en_2S=1 で S1-LVL1 非リーフ通過 | T51 |
| BR21 | `main_lvl == LVL2` → LVL3 進行 (非リーフ) | 3-level walk の LVL2 非リーフ | T10, T50 |
| BR22 | `en_2S_i` (S1/LVL2 非リーフ) → S2-INTERMED | en_2S=1 で S1-LVL2 非リーフ通過 | T51 |
| BR23 | 非リーフ PTE に `pte.a \|\| pte.d \|\| pte.u` | LVL1,2 の非リーフ PTE に A/D/U セット | T14, T34, T55 |
| BR24 | `main_lvl == LVL3` かつ非リーフ (深さ超過) | LVL3 で r=x=0 の PTE | T15, T35, T56 |
| BR25 | `\|pte.reserved != 0` (PTE bits[63:54]) | 予約ビットに 1 をセット | T12, T32, T53 |
| BR26 | S1 leaf の `pte.ppn[43:29]` 非ゼロ (en_2S=1) | 2 ステージ時の S1 leaf GPPN 上位 | T57 |
| BR27 | `r.resp != OKAY` → PT_DATA_CORRUPTION | SLVERR 応答を MockMem から返す | T13, T33, T54 |
| BR28 | `pt_data_corrupt_q` (ERROR 状態) → cause=274 | AXI error 後の ERROR 状態遷移 | T13, T33, T54 |
| BR29 | `ptw_stage != STAGE_1` → ptw_error_2S_o=1 | S2 ステージでフォルト発生 | T31, T37, T52, T57 |
| BR30 | `ptw_stage == STAGE_2_INTERMED` → ptw_error_2S_int_o=1 | INTERMED walk 中のフォルト | T57, T55 |
| BR31 | `cdw_implicit_access_q` (ERROR) → flush_cdw_o=1 | CDW 暗黙的変換中にエラー | T72 |
| BR32 | `MSITrans != DISABLED` (generate) | **UNTESTABLE** | — |
| BR33 | MSI アドレス一致検出 | **UNTESTABLE** | — |

---

## 4. テストマトリクス

### 4.1 リセット・制御系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T01 | 初期リセット | rst_ni=0 → 1 | state_q=IDLE, 全レジスタ初期値 | `scenario/test_directed.py::test_t01_initial_reset` | — | - | ⏱ PENDING |
| T02 | ウォーク中リセット | LVL2 walk 中に rst_ni=0 | state_q=IDLE, ptw_active_o=0 | `scenario/test_directed.py::test_t02_reset_during_walk` | — | - | ⏱ PENDING |
| T03 | キャッシュミストリガ | init_ptw_i=1 pulse, cdw_implicit_access_i=0 | ウォーク開始 (ptw_active_o=1) | `scenario/test_directed.py::test_t03_cache_miss_trigger` | BR01, BR02, BR03 | - | ⏱ PENDING |
| T04 | CDW 暗黙的トリガ | init_ptw_i=0, cdw_implicit_access_i=1 | ウォーク開始, cdw_done_o=1 (成功時) | `scenario/test_directed.py::test_t04_cdw_trigger` | BR03, BR05 | - | ⏱ PENDING |
| T05 | MSI 無効化確認 | msi_en_i=0, S1 walk 完了 | gpaddr_is_msi_o=0 固定 | `scenario/test_directed.py::test_t05_msi_disabled` | BR32 (False path) | - | ⏱ PENDING |

### 4.2 S1-only 正常系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T10 | S1 LVL1,2,3 正常ウォーク | en_1S=1, en_2S=0, iova[63:39]=canonical, 各 VPN (max/min/random), PTE: v=1, a=1, d=1(leaf STORE), u=0(非leaf), r/x=0(非leaf), r/x≠0(leaf), reserved=0, RESP_OKAY | update_o=1, ptw_error_o=0 | `scenario/test_directed.py::test_t10_s1_normal_walk` | BR04, BR06, BR07, BR10, BR14, BR19, BR21 | - | ⏱ PENDING |

### 4.3 S1-only フォルト系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T11 | S1 LVL1,2,3 無効 PTE | en_1S=1, en_2S=0; 各 LVL で以下 3 パターン: (1) v=0,w=0,r=0, (2) v=1,w=1,r=0, (3) v=0,w=1,r=0 | ptw_error_o=1, ptw_error_2S_o=0; is_store=0→13, is_store=1→15 | `scenario/test_fault.py::test_t11_s1_invalid_pte` | BR09, BR29(False) | - | ⏱ PENDING |
| T12 | S1 LVL1,2,3 reserved bits 非ゼロ | en_1S=1, en_2S=0; 各 LVL で pte[63:54]≠0: 1ビットずつ + ランダム10パターン | ptw_error_o=1, ptw_error_2S_o=0; is_store=0→13, is_store=1→15 | `scenario/test_fault.py::test_t12_s1_reserved_bits` | BR25, BR29(False) | - | ⏱ PENDING |
| T13 | S1 LVL1,2,3 AXI エラー | en_1S=1, en_2S=0; 各 LVL で SLVERR 応答 | ptw_error_o=1, cause_code_o=274 (PT_DATA_CORRUPTION) | `scenario/test_fault.py::test_t13_s1_axi_error` | BR27, BR28 | - | ⏱ PENDING |
| T14 | S1 非リーフ (LVL1,2) A/D/U ビットセット | en_1S=1, en_2S=0; LVL1,2 の非リーフ PTE に a=1/d=1/u=1 (7パターン/LVL) | ptw_error_o=1, ptw_error_2S_o=0; is_store=0→13, is_store=1→15 | `scenario/test_fault.py::test_t14_s1_nonleaf_adu` | BR23, BR29(False) | - | ⏱ PENDING |
| T15 | S1 LVL3 非リーフ (深さ超過) | en_1S=1, en_2S=0; LVL3 で r=0,x=0 の PTE (non-leaf) | ptw_error_o=1, ptw_error_2S_o=0; is_store=0→13, is_store=1→15 | `scenario/test_fault.py::test_t15_s1_lvl3_nonleaf` | BR24, BR29(False) | - | ⏱ PENDING |
| T16 | S1 スーパーページ ミスアライン | en_1S=1, en_2S=0; LVL1(1G) leaf ppn[17:0]≠0, LVL2(2M) leaf ppn[8:0]≠0 | ptw_error_o=1, ptw_error_2S_o=0; is_store=0→13, is_store=1→15 | `scenario/test_fault.py::test_t16_s1_superpage_misalign` | BR16, BR17 | - | ⏱ PENDING |
| T17 | S1 リーフ A-bit クリア | en_1S=1, en_2S=0; LVL3 leaf pte.a=0 (他は正常) | **PTW scope 外**: update_o=1 (PTW 成功); フォルトは Wrapper 層 | `scenario/test_fault.py::test_t17_s1_leaf_a_cleared` | — | - | ⏱ PENDING |
| T18 | S1 リーフ R-bit クリア (execute-only) | en_1S=1, en_2S=0; LVL3 leaf r=0, x=1, w=0/1 | **PTW scope 外**: update_o=1 (R=0,W=0,X=1 は BR09 非トリガ); ただし R=0,W=1 は T11 で担当 | `scenario/test_fault.py::test_t18_s1_leaf_r_cleared` | — | - | ⏱ PENDING |
| T19 | S1 STORE D-bit クリア | en_1S=1, en_2S=0, is_store=1; LVL3 leaf pte.d=0 | **PTW scope 外**: update_o=1 | `scenario/test_fault.py::test_t19_s1_store_d_cleared` | — | - | ⏱ PENDING |
| T20 | S1 STORE W-bit クリア | en_1S=1, en_2S=0, is_store=1; LVL3 leaf pte.w=0, r=1 | **PTW scope 外**: update_o=1 | `scenario/test_fault.py::test_t20_s1_store_w_cleared` | — | - | ⏱ PENDING |
| T21 | S1 フォルト優先順位 (AXI > PAGE) | en_1S=1, en_2S=0; 同じ LVL で SLVERR + invalid PTE 同時 | ptw_error_o=1, cause_code_o=274 (PT_DATA_CORRUPTION > PAGE_FAULT) | `scenario/test_fault.py::test_t21_s1_fault_priority` | BR27, BR28, BR09 | - | ⏱ PENDING |
| T22 | S1 フォルト分類 | en_1S=1, en_2S=0; 各フォルト種別を個別に発生 | 各 cause_code: 274/15/13 が正しく出力されること | `scenario/test_fault.py::test_t22_s1_fault_classification` | BR28, BR29 | - | ⏱ PENDING |

### 4.4 S2-only 正常系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T30 | S2 LVL1,2,3 正常ウォーク | en_1S=0, en_2S=1, iova[63:41]=0, 各 VPN (max/min/random), PTE: v=1, a=1, d=1(leaf STORE), u=1(leaf), u=0(非leaf), r/x=0(非leaf), r/x≠0(leaf), reserved=0, RESP_OKAY | update_o=1, ptw_error_o=0 | `scenario/test_directed.py::test_t30_s2_normal_walk` | BR04, BR06, BR07, BR10, BR14, BR19, BR21 | - | ⏱ PENDING |

### 4.5 S2-only フォルト系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T31 | S2 LVL1,2,3 無効 PTE | en_1S=0, en_2S=1; 各 LVL で 3 パターン (v=0,w=0,r=0 / v=1,w=1,r=0 / v=0,w=1,r=0) | ptw_error_o=1, **ptw_error_2S_o=1**; is_store=0→21, is_store=1→23 | `scenario/test_fault.py::test_t31_s2_invalid_pte` | BR09, BR29(True) | - | ⏱ PENDING |
| T32 | S2 LVL1,2,3 reserved bits 非ゼロ | en_1S=0, en_2S=1; 各 LVL で pte[63:54]≠0 (ランダム10パターン含む) | ptw_error_o=1, ptw_error_2S_o=1; is_store=0→21, is_store=1→23 | `scenario/test_fault.py::test_t32_s2_reserved_bits` | BR25, BR29(True) | - | ⏱ PENDING |
| T33 | S2 LVL1,2,3 AXI エラー | en_1S=0, en_2S=1; 各 LVL で SLVERR 応答 | ptw_error_o=1, cause_code_o=274 | `scenario/test_fault.py::test_t33_s2_axi_error` | BR27, BR28 | - | ⏱ PENDING |
| T34 | S2 非リーフ (LVL1,2) A/D/U ビットセット | en_1S=0, en_2S=1; LVL1,2 の非リーフ PTE に a=1/d=1/u=1 (7パターン/LVL) | ptw_error_o=1, ptw_error_2S_o=1; is_store=0→21, is_store=1→23 | `scenario/test_fault.py::test_t34_s2_nonleaf_adu` | BR23, BR29(True) | - | ⏱ PENDING |
| T35 | S2 LVL3 非リーフ (深さ超過) | en_1S=0, en_2S=1; LVL3 で r=0,x=0 の PTE | ptw_error_o=1, ptw_error_2S_o=1; is_store=0→21, is_store=1→23 | `scenario/test_fault.py::test_t35_s2_lvl3_nonleaf` | BR24, BR29(True) | - | ⏱ PENDING |
| T36 | S2 スーパーページ ミスアライン | en_1S=0, en_2S=1; LVL1 leaf ppn[17:0]≠0, LVL2 leaf ppn[8:0]≠0 | ptw_error_o=1, ptw_error_2S_o=1; is_store=0→21, is_store=1→23 | `scenario/test_fault.py::test_t36_s2_superpage_misalign` | BR16, BR17, BR29(True) | - | ⏱ PENDING |
| T37 | S2 リーフ U-bit クリア | en_1S=0, en_2S=1; LVL3 leaf pte.u=0 | ptw_error_o=1, ptw_error_2S_o=1; is_store=0→21, is_store=1→23 | `scenario/test_fault.py::test_t37_s2_leaf_u_cleared` | BR18, BR29(True) | - | ⏱ PENDING |
| T38 | S2 リーフ A-bit クリア | en_1S=0, en_2S=1; LVL3 leaf pte.a=0 | **PTW scope 外**: update_o=1 | `scenario/test_fault.py::test_t38_s2_leaf_a_cleared` | — | - | ⏱ PENDING |
| T39 | S2 リーフ R-bit クリア | en_1S=0, en_2S=1; LVL3 leaf r=0, x=1 | **PTW scope 外**: update_o=1 (R=0,W=0,X=1 は有効) | `scenario/test_fault.py::test_t39_s2_leaf_r_cleared` | — | - | ⏱ PENDING |
| T40 | S2 STORE D-bit クリア | en_1S=0, en_2S=1, is_store=1; LVL3 leaf pte.d=0 | **PTW scope 外**: update_o=1 | `scenario/test_fault.py::test_t40_s2_store_d_cleared` | — | - | ⏱ PENDING |
| T41 | S2 フォルト優先順位 | en_1S=0, en_2S=1; SLVERR + invalid PTE 同時 | ptw_error_o=1, cause_code_o=274 | `scenario/test_fault.py::test_t41_s2_fault_priority` | BR27, BR28 | - | ⏱ PENDING |

### 4.6 Two-stage 正常系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T50 | Two-stage S2 walk (S2-INTERMED LVL1,2,3) | en_1S=1, en_2S=1; S2 側 LVL1,2,3 にそれぞれ正常 PTE 配置。S2-INTERMED は S1 テーブルのアドレス解決に使用 | ウォーク継続 (S2-INTERMED 後 S1 walk へ進む) | `scenario/test_directed.py::test_t50_twostage_s2_walk` | BR04, BR11, BR12, BR19, BR20, BR21, BR22 | - | ⏱ PENDING |
| T51 | Two-stage 完全ウォーク (S1 LVL1,2,3 + S2-FINAL) | en_1S=1, en_2S=1; S1 LVL1,2,3 + S2-INTERMED ×3 + S2-FINAL LVL1,2,3 | update_o=1, up_1S_content_o valid, up_2S_content_o valid | `scenario/test_directed.py::test_t51_twostage_full_walk` | BR04, BR11, BR12, BR14, BR19-BR22 | - | ⏱ PENDING |

### 4.7 Two-stage フォルト系

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T52 | Two-stage S1,2 LVL1,2,3 無効 PTE | en_1S=1, en_2S=1; S1 側各 LVL / S2-INTERMED 各 LVL / S2-FINAL 各 LVL でそれぞれ invalid PTE | S1 フォルト: ptw_error_2S_o=0; S2 フォルト: ptw_error_2S_o=1; S2-INTERMED: さらに ptw_error_2S_int_o=1 | `scenario/test_fault.py::test_t52_twostage_invalid_pte` | BR09, BR29, BR30 | - | ⏱ PENDING |
| T53 | Two-stage S1,2 LVL1,2,3 reserved bits 非ゼロ | en_1S=1, en_2S=1; 各ステージ × 各 LVL でランダム reserved bits | 各ステージの ptw_error_2S_o / ptw_error_2S_int_o が正しく出力 | `scenario/test_fault.py::test_t53_twostage_reserved_bits` | BR25, BR29, BR30 | - | ⏱ PENDING |
| T54 | Two-stage S1,2 LVL1,2,3 AXI エラー | en_1S=1, en_2S=1; 各ステージ × 各 LVL で SLVERR | ptw_error_o=1, cause_code_o=274 | `scenario/test_fault.py::test_t54_twostage_axi_error` | BR27, BR28 | - | ⏱ PENDING |
| T55 | Two-stage 非リーフ S1,2 LVL1,2 A/D/U ビットセット | en_1S=1, en_2S=1; S1 LVL1,2 / S2-INTERMED LVL1,2 の非リーフ PTE に A/D/U セット | 各ステージの error 信号が正しく出力; S2-INTERMED フォルトは ptw_error_2S_int_o=1 | `scenario/test_fault.py::test_t55_twostage_nonleaf_adu` | BR23, BR29, BR30 | - | ⏱ PENDING |
| T56 | Two-stage S1,2 LVL3 非リーフ | en_1S=1, en_2S=1; S1/S2-INTERMED/S2-FINAL の LVL3 で r=x=0 | 各ステージの error 信号; S2-INTERMED は ptw_error_2S_int_o=1 | `scenario/test_fault.py::test_t56_twostage_lvl3_nonleaf` | BR24, BR29, BR30 | - | ⏱ PENDING |
| T57 | Two-stage S1 leaf PPN[44:29] 非ゼロ (BR26) | en_1S=1, en_2S=1; S1 leaf PTE の pte.ppn[43:29]≠0 | ptw_error_o=1, ptw_error_2S_o=1, ptw_error_2S_int_o=1; LOAD/STORE_GUEST_PAGE_FAULT | `scenario/test_fault.py::test_t57_s1_leaf_gppn_upper` | BR26, BR29, BR30 | - | ⏱ PENDING |
| T58 | Two-stage スーパーページ ミスアライン | en_1S=1, en_2S=1; S1/S2-INTERMED/S2-FINAL の LVL1(1G)/LVL2(2M) leaf でミスアライン ppn | 各ステージの error 信号 | `scenario/test_fault.py::test_t58_twostage_superpage_misalign` | BR16, BR17, BR29 | - | ⏱ PENDING |
| T59 | Two-stage S2 リーフ U-bit クリア | en_1S=1, en_2S=1; S2-FINAL LVL3 leaf pte.u=0 | ptw_error_o=1, ptw_error_2S_o=1, ptw_error_2S_int_o=0; LOAD/STORE_GUEST_PAGE_FAULT | `scenario/test_fault.py::test_t59_twostage_s2_leaf_u_cleared` | BR18, BR29(True) | - | ⏱ PENDING |
| T60 | Two-stage リーフ A-bit クリア | en_1S=1, en_2S=1; S1/S2 LVL3 leaf pte.a=0 | **PTW scope 外**: update_o=1 (S1); S2 は T38 と同様 | `scenario/test_fault.py::test_t60_twostage_leaf_a_cleared` | — | - | ⏱ PENDING |
| T61 | Two-stage リーフ R-bit クリア | en_1S=1, en_2S=1; S1/S2 LVL3 leaf r=0, x=1 | **PTW scope 外**: update_o=1 | `scenario/test_fault.py::test_t61_twostage_leaf_r_cleared` | — | - | ⏱ PENDING |
| T62 | Two-stage STORE D-bit クリア | en_1S=1, en_2S=1, is_store=1; S1/S2 LVL3 leaf pte.d=0 | **PTW scope 外**: update_o=1 | `scenario/test_fault.py::test_t62_twostage_store_d_cleared` | — | - | ⏱ PENDING |
| T63 | Two-stage フォルト優先順位 | en_1S=1, en_2S=1; SLVERR + invalid PTE 同時 | ptw_error_o=1, cause_code_o=274 | `scenario/test_fault.py::test_t63_twostage_fault_priority` | BR27, BR28 | - | ⏱ PENDING |

### 4.8 エッジケース

| T-ID | シナリオ | 入力条件 | 期待出力 | TB 場所 | BR-ID | Last Run | Status |
|---|---|---|---|---|---|---|---|
| T70 | G-bit (グローバルマッピング) 伝播 | S1 walk 中の非リーフ PTE に pte.g=1 | up_1S_content_o.g=1 でウォーク完了 | `scenario/test_directed.py::test_t70_global_bit` | BR08 | - | ⏱ PENDING |
| T71 | CDW 暗黙的変換 成功 | cdw_implicit_access_i=1, pdt_gppn_i 指定, en_2S=1 | cdw_done_o=1, update_o=0 | `scenario/test_directed.py::test_t71_cdw_implicit_success` | BR03, BR05, BR15 | - | ⏱ PENDING |
| T72 | CDW 暗黙的変換 エラー | cdw_implicit_access_i=1, en_2S=1; S2 walk で invalid PTE | ptw_error_o=1, flush_cdw_o=1 | `scenario/test_fault.py::test_t72_cdw_implicit_error` | BR03, BR31 | - | ⏱ PENDING |
| T73 | Back-to-back ウォーク | 1 回目成功後、即座に 2 回目 init_ptw_i エッジ | 2 回連続で update_o=1 | `scenario/test_directed.py::test_t73_back_to_back` | BR01, BR02 | - | ⏱ PENDING |
| T74 | バックプレッシャ (ar_ready 遅延) | ar_ready=0 を 10/50 サイクル維持後に 1 | 遅延後正常に update_o=1 | `scenario/test_directed.py::test_t74_backpressure` | BR06 | - | ⏱ PENDING |

### 4.9 ランダム

| R-ID | シナリオ | ケース数 | Seed | TB 場所 | Last Run | Status |
|---|---|---|---|---|---|---|
| R01 | S1-only ランダム (valid iova, valid PTE flags) | 100 | 42 | `scenario/test_random.py::test_r01_s1_random` | - | ⏱ PENDING |
| R02 | S2-only ランダム (valid gpa[40:0], valid PTE flags) | 100 | 43 | `scenario/test_random.py::test_r02_s2_random` | - | ⏱ PENDING |
| R03 | Two-stage ランダム (S1+S2 同時) | 100 | 44 | `scenario/test_random.py::test_r03_twostage_random` | - | ⏱ PENDING |

### 4.10 カバレッジサマリ

| カテゴリ | 計 | PASS | FAIL | SKIP | PENDING |
|---|---|---|---|---|---|
| リセット・制御系 | 5 | 0 | 0 | 0 | 5 |
| S1-only 正常系 | 1 | 0 | 0 | 0 | 1 |
| S1-only フォルト系 | 12 | 0 | 0 | 0 | 12 |
| S2-only 正常系 | 1 | 0 | 0 | 0 | 1 |
| S2-only フォルト系 | 11 | 0 | 0 | 0 | 11 |
| Two-stage 正常系 | 2 | 0 | 0 | 0 | 2 |
| Two-stage フォルト系 | 12 | 0 | 0 | 0 | 12 |
| エッジケース | 5 | 0 | 0 | 0 | 5 |
| ランダム | 3 | 0 | 0 | 0 | 3 |
| **合計** | **52** | **0** | **0** | **0** | **52** |

---

## 5. 未カバー BR と今後の追加計画

| 優先 | BR-ID | 追加すべきテスト | T-ID 候補 | 理由 |
|---|---|---|---|---|
| 高 | BR13 | MSI アドレス一致 (gpaddr_is_msi_o=1) | T05b | MSITrans=DISABLED のため現 TB 構成では不可。MSITrans パラメータ変更が必要 |
| 高 | BR32 | MSITrans generate ブロック有効化 | T05b | 同上 |
| 高 | BR33 | MSI アドレスパターンマッチ検証 | T05b | 同上 |
| 低 | — | INSTR_PAGE_FAULT (12), INSTR_GUEST_PAGE_FAULT (20) | — | is_rx_i がコメントアウトのため現実装で生成不可。is_rx_i の再有効化後に対応 |

---

## 6. ゴールデンモデルの制限

| 制限 | 詳細 | 対策 |
|---|---|---|
| Two-stage 同時対応なし | `translate_sv39_golden` は en_1S=1 かつ en_2S=1 の場合 UNSUPPORTED を返す | R03 (Two-stage random) は期待値を手動設定するか、golden model を拡張する |
| INSTR_PAGE_FAULT 生成不可 | `is_rx_i` がコメントアウト (line:50) — LOAD/STORE のみ区別可能 | テスト期待値は 12 でなく 13 (LOAD) を使用 |
| AXI error cause code の誤解 | must_test 記載の 1/5/7 は誤り。正しくは常に 274 (PT_DATA_CORRUPTION) | T13, T33, T54 の期待値は 274 に設定すること |
| Wrapper scope の権限チェック | 葉 PTE の A/D/R/W/X チェックは PTW 内では実施しない | T17-T20, T38-T40, T60-T62 の期待値は update_o=1 (PTW 成功) |

---

## 7. 変更履歴

| 日付 | 変更者 | 内容 | reviewed 遷移 |
|---|---|---|---|
| 2026-04-27 | Claude | 初版作成 — must_test 全シナリオを T-ID に展開、RTL 制約 (is_rx_i, AXI cause code, scope外) を明記 | (新規) false |
