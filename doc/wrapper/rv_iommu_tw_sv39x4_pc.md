# `rv_iommu_tw_sv39x4_pc` 解析結果

## 1. ポート一覧

| ポート名 | 方向 | ビット幅 | 生成元 / 宛先 | 用途 |
|---|---|---|---|---|
| `clk_i` | In | 1 | 外部 | クロック |
| `rst_ni` | In | 1 | 外部 | 非同期リセット（Low 有効） |
| `req_trans_i` | In | 1 | 上位ラッパー | 通常変換トリガ。変換完了まで High 保持が必要（`tw:25`） |
| `req_dbg_i` | In | 1 | 上位ラッパー | デバッグ変換トリガ。MSI 変換を抑制（`tw:564`） |
| `did_i` | In | 24 | 上位ラッパー | device_id。DDTC / CDW の検索キー |
| `pv_i` | In | 1 | 上位ラッパー | process_id 有効フラグ |
| `pid_i` | In | 20 | 上位ラッパー | process_id。PDTC / CDW の検索キー |
| `iova_i` | In | 64 (`riscv::VLEN`) | 上位ラッパー | 変換対象 IOVA |
| `gscid_o` | Out | 16 | → 上位ラッパー | GSCID（現在の変換で使用中。`dc_base.iohgatp.gscid` から） |
| `pscid_o` | Out | 20 | → 上位ラッパー | PSCID（`dc_base.ta.pscid` or `pdtc_lu_content.ta.pscid` から） |
| `trans_type_i` | In | 6 (`TTYP_LEN`) | 上位ラッパー | トランザクション種別。bit[2]=翻訳済み, bits[1:0]=R/W/RX, bit[3]=PCIe |
| `priv_lvl_i` | In | 1 | 上位ラッパー | 特権レベル（0=U-mode, 1=S-mode） |
| `cdw_axi_resp_i` / `cdw_axi_req_o` | In / Out | struct | AXI Bus ↔ CDW | CDW のメモリアクセスポート（DDT/PDT 読み出し） |
| `ptw_axi_resp_i` / `ptw_axi_req_o` | In / Out | struct | AXI Bus ↔ PTW | PTW のメモリアクセスポート（ページテーブル読み出し） |
| `msiptw_axi_resp_i` / `msiptw_axi_req_o` | In / Out | struct | AXI Bus ↔ MSI-PTW | MSI PTW のメモリアクセスポート（`MSITrans` 有効時のみ） |
| `mrif_handler_axi_resp_i` / `mrif_handler_axi_req_o` | In / Out | struct | AXI Bus ↔ MRIF | MRIF ハンドラのメモリアクセスポート（`MSI_FLAT_MRIF` 時のみ） |
| `capabilities_i` | In | struct | Regmap | IOMMU ケーパビリティレジスタ（CDW の DC config check 用） |
| `fctl_i` | In | struct | Regmap | `fctl.gxl`, `fctl.be`（CDW の DC config check 用） |
| `ddtp_i` | In | struct | Regmap | DDT ポインタ。`iommu_mode[3:0]` + `ppn[43:0]` |
| `trans_valid_o` | Out | 1 | → 上位ラッパー | 変換成功完了 |
| `spaddr_o` | Out | 56 (`riscv::PLEN`) | → 上位ラッパー | 変換済み物理アドレス |
| `is_superpage_o` | Out | 1 | → 上位ラッパー | スーパーページフラグ（IOTLB ルックアップ結果から） |
| `trans_error_o` | Out | 1 | → 上位ラッパー | 変換エラー発生（全エラーソースの OR） |
| `report_fault_o` | Out | 1 | → FQ Handler | FQ へのフォルト報告が必要か（DTF ビット考慮済み） |
| `cause_code_o` | Out | 12 (`CAUSE_LEN`) | → FQ Handler | フォルトコード（優先 priority case で選択） |
| `is_guest_pf_o` | Out | 1 | → FQ Handler | ゲストページフォルト（PTW の第 2 ステージエラー） |
| `is_implicit_o` | Out | 1 | → FQ Handler | S1 変換中の暗黙的 S2 アクセスによるゲスト PF |
| `bad_gpaddr_o` | Out | 41 (`riscv::SVX`) | → FQ Handler | ゲスト PF 時の不正 GPA（bits[63:2] 報告用） |
| `msi_write_error_i` | In | 1 | 上位ラッパー | IOMMU が生成した MSI の書き込みエラー |
| `iotlb_miss_o` | Out | 1 | → HPM | IOTLB ミスイベント |
| `ddt_walk_o` | Out | 1 | → HPM | DDT ウォーク発生（`cdw_active & is_ddt_walk`） |
| `pdt_walk_o` | Out | 1 | → HPM | PDT ウォーク発生（`cdw_active & ~is_ddt_walk`） |
| `s1_ptw_o` | Out | 1 | → HPM | S1 PTW ウォーク（`ptw_active & ptw_en_1S`） |
| `s2_ptw_o` | Out | 1 | → HPM | S2 PTW ウォーク（`ptw_active & ptw_en_2S`） |
| `flush_ddtc_i`, `flush_dv_i`, `flush_did_i` | In | 1, 1, 24 | CQ Handler | DDTC 無効化（`IODIR.INVAL_DDT`） |
| `flush_pdtc_i`, `flush_pv_i`, `flush_pid_i` | In | 1, 1, 20 | CQ Handler | PDTC 無効化（`IODIR.INVAL_PDT`） |
| `flush_vma_i`, `flush_gvma_i`, `flush_av_i`, `flush_gv_i`, `flush_pscv_i` | In | 各 1 | CQ Handler | IOTLB 無効化コマンドフラグ（`IOTINVAL.VMA` / `IOTINVAL.GVMA`） |
| `flush_vpn_i`, `flush_gscid_i`, `flush_pscid_i` | In | 29, 16, 20 | CQ Handler | IOTLB 無効化のアドレス / ID タグ |
| `ignore_request_o` | Out | 1 | → 上位ラッパー | リクエストを無視（MRIF 処理中、フォルトなし） |
| `msi_data_valid_i` | In | 1 | 上位ラッパー | MSI データ（DMA が送信した write data）が有効 |
| `msi_data_i` | In | 32 | 上位ラッパー | MSI data（割り込み ID） |

---

## 2. サブモジュールの役割・内部配線・接続関係

### 2.1 DDTC (`rv_iommu_ddtc`, `tw:362–384`)

- **役割**: Device Context (DC) のフルアソシアティブキャッシュ。PLRU 置き換え。
- **ルックアップキー**: `did_i[23:0]`
- **ヒット判定**: `tags_q[i].valid && tags_q[i].device_id == lu_did_i`（`ddtc:76`）
- **接続**:
    - `lookup_i = ddtc_access`（`tw:378`）— translation ブロックで `req_trans_i` 時に有効化
    - `lu_content_o` → `ddtc_lu_content` → `dc_base`（`tw:183–184` `assign dc_base = rv_iommu::dc_base_t'(ddtc_lu_content)`）
    - `update_i = ddtc_update`, `up_content_i = ddtc_up_content` は CDW から供給（`tw:375–376`）
    - フラッシュ: `flush_i=flush_ddtc_i`, `flush_dv_i`, `flush_did_i` を直接受信

### 2.2 PDTC (`rv_iommu_pdtc`, `tw:386–412`)

- **役割**: Process Context (PC) のフルアソシアティブキャッシュ。PLRU 置き換え。
- **ルックアップキー**: `did_i[23:0]` + `process_id[19:0]`（`process_id` は DPE ビット処理後の値、`tw:270–271`）
- **接続**:
    - `lookup_i = pdtc_access`（`tw:408`）— DDTC ヒット後、`DC.tc.pdtv=1` かつ `pv_i=1` の場合のみ有効
    - `lu_content_o` → `pdtc_lu_content`。S1_en の計算（`tw:221–222`）および IOTLB ルックアップの pscid / iosatp_ppn 供給に使用
    - `up_did_i = ddtc_up_did`（`tw:402`）— DDTC と同じ device_id で更新（両方 CDW が管理）
    - フラッシュ: `flush_pdtc_i`, `flush_dv_i`, `flush_pv_i`, `flush_did_i`, `flush_pid_i`

### 2.3 IOTLB (`rv_iommu_iotlb_sv39x4`, `tw:415–461`)

- **役割**: S1 / S2 PTE ペアをキャッシュするアドレス変換 TLB。MSI エントリも格納可能。
- **ルックアップキー**: `iova_i[40:12]` (VPN[2:0]) + pscid + gscid + en_1S + en_2S
- **ヒット判定** (`iotlb:159–173`):
    - valid, PSCID 一致（or global bit）, GSCID 一致, ステージ一致, VPN[2] 一致
    - さらに 1G / 2M / 4K レベルに応じた VPN[1] / VPN[0] 比較
- **接続**:
    - `lookup_i = iotlb_access`（`tw:447`）— DDTC / PDTC ヒット後にアサート
    - `lu_pscid_i = pscid`, `lu_gscid_i = gscid`（`tw:448–449`）— translation ブロックで決定
    - 更新: `update_i = iotlb_update = ptw_update | msi_update`（`tw:314`）
    - MSI 更新優先の MUX（`tw:315–324`）— MSI 更新時は 2S スーパーページフラグは 0
    - `lu_1S_content_o` → `iotlb_lu_1S_content`（S1 PTE, GPA PPN）, `lu_2S_content_o` → `iotlb_lu_2S_content`（S2 PTE, SPA PPN）
    - フラッシュ: `IOTINVAL.VMA` / `GVMA` コマンドを直接受信

### 2.4 PTW (`rv_iommu_ptw_sv39x4_pc`, `tw:463–531`)

- **役割**: AXI 経由でページテーブルをウォーク。S1 のみ・S2 のみ・ネスト（S1+S2）に対応。
- **FSM 状態** (`ptw:98–103`): `IDLE` → `MEM_ACCESS` → `PROC_PTE` → `ERROR`
- **ステージ状態** (`ptw:111–115`): `STAGE_1`, `STAGE_2_INTERMED`, `STAGE_2_FINAL`
- **トリガ**: `init_ptw_i = iotlb_lu_miss & (S1_en | (S2_en & ~iova_is_msi))`（`tw:339–341`）
    - エッジトリガ制御あり（`ptw:162–174`）— IDLE 復帰中に再トリガしない
- **PTW 開始時の pptr 計算** (`ptw:367–431`):
    - S2 のみ: `{iohgatp_ppn[43:2], GPA[40:30], 3'b0}`
    - S1 のみ: `{iosatp_ppn, VA[38:30], 3'b0}`
    - S1+S2（ネスト）: 最初に `iosatp_ppn` の GPA を S2 でウォーク → `ptw_stage = STAGE_2_INTERMED`
- **CDW 暗黙的アクセス** (`ptw:361`): `cdw_implicit_access_i=1` のとき、`pdt_gppn_i` を GPA として S2 のみウォーク
- **IOTLB 更新**: `update_o=1`（CDW 暗黙的アクセス時は `cdw_done_o=1`）（`ptw:548–550`）
- **MSI バス**: GPA が MSI アドレスと判定された場合（`ptw:187–189`）、`gpaddr_is_msi_o=1` で MSI PTW に制御を渡す
- **接続キー**:
    - `ptw_iohgatp_ppn = (is_ddt_walk & cdw_implicit_access) ? iohgatp_ppn_fw : iohgatp_ppn`（`tw:171`）— CDW が `pdtp.PPN` を変換する際に `iohgatp.ppn` をフォワード
    - `ptw_en_1S = cdw_implicit_access ? 0 : S1_en`（`tw:227`）— 暗黙的アクセスは常に S2 のみ

### 2.5 MSI PTW (`rv_iommu_msiptw`, `tw:550–612`、`MSITrans≠DISABLED` 時)

- **役割**: MSI ページテーブルをウォークし、MSI PTE (FLAT or MRIF) を取得
- **トリガ**: `init_msi_trans_i = init_msi_trans & ~req_dbg_i`（`tw:564`）
    - デバッグ変換は MSI 禁止
- **IOTLB 更新**: `msi_update=1`（FLAT PTE の場合）
- **MRIFC 更新**: `mrifc_update=1`（MRIF PTE の場合）
- **無効化**: `ignore_o=msiptw_ignore` でリクエストを吸収（フォルトなし）

### 2.6 MRIF Handler (`rv_iommu_mrif_handler`, `tw:654–681`、`MSI_FLAT_MRIF` 時のみ)

- **役割**: MRIFC ヒット後、メモリ上の MRIF に割り込みペンディングビットを書き込む
- **トリガ**: `init_mrif_i = mrifc_lu_hit & msi_data_valid_i`（`tw:666`）
- **入力データ**: `msi_data_i[31:0]`（割り込み ID）, `mrifc_lu_msi_content.addr`, `.nid`, `.nppn`
- **無効化**: `ignore_o=mrif_handler_ignore` — 処理完了後、上流に無視を指示

### 2.7 MRIFC (`rv_iommu_mrifc`, `tw:683–720`、`MSI_FLAT_MRIF` 時のみ)

- **役割**: MRIF エントリ（addr / nppn / nid）のフルアソシアティブキャッシュ
- **IOTLB と同期ルックアップ**: `lookup_i = iotlb_access`（`tw:711`）— IOTLB と同一サイクルで並行検索
- **更新**: MSI PTW の `mrifc_update` と `mrifc_up_msi_content` で更新
- **IOTLB miss 条件への参加**: `init_msi_trans` の `mrifc_lu_miss` 条件（`tw:349`）

### 2.8 CDW (`rv_iommu_cdw_pc`, `tw:741–819`)

- **役割**: DDT / PDT をウォークして DC・PC を取得・検証し、DDTC / PDTC を更新
- **FSM 状態** (`cdw:144–151`): `IDLE` → `MEM_ACCESS` → `NON_LEAF` / `LEAF` / `GUEST_TR` → `ERROR`
- **DDT ウォーク開始**: `init_cdw_i = ddtc_access && ~ddtc_lu_hit`（`tw:797`）
- **PDT ウォーク開始**: `pdtc_access_i = pdtc_access`, `pdtc_hit_i = pdtc_lu_hit`（`tw:799–800`）
- **DDT AXI burst 長** (`cdw:264`): 非リーフは 1 beat; リーフ DC は 4 beat（MSI 無効）or 7 beat（MSI 有効）; リーフ PC は 2 beat
- **暗黙的 S2 変換（CDW 側）**:
    - `GUEST_TR` 状態で `cdw_implicit_access_o=1` をアサート → PTW を S2 のみで起動（`cdw:673–685`）
    - DDT ウォーク: `DC.fsc.ppn`（`pdtp.ppn`）を変換（`cdw:683–686`）
    - PDT ウォーク: 非リーフ PDT エントリの `ppn` を変換（`cdw:672–675`）
    - `iohgatp_ppn_fw_o = dc_iohgatp_q.ppn`（`cdw:684`）を PTW にフォワード
- **DC 格納レジスタ**: `dc_tc_q`, `dc_iohgatp_q`, `dc_ta_q`, `dc_fsc_q`（MSI 有効時は追加 3 フィールド）
- **更新出力**: `update_dc_o` → `ddtc_update`, `update_pc_o` → `pdtc_update`

---

## 3. 例外 / フォルト検出ポイント

### 3.1 ラッパーレベル (`wrap_error`, translation ブロック `tw:822–1068`)

| #   | 検出条件 | 使用信号 | Cause Code | `report_always` |
|-----|---|---|---|---|
| W1  | `ddtp.iommu_mode == 4'b0000` (Off) | `ddtp_i.iommu_mode.q` | 256 `ALL_INB_TRANSACTIONS_DISALLOWED` | 1 |
| W2  | `ddtp.mode == Bare` && (`is_translated` OR `is_pcie_tr_req`) | `is_translated`, `is_pcie_tr_req` | 260 `TRANS_TYPE_DISALLOWED` | 1 |
| W3  | `ddtp.mode==3LVL(4)` && `did[23:15]!=0`、OR `ddtp.mode==2LVL(3)` && `did[23:6]!=0` | `ddtp_i.iommu_mode.q`, `did_i` | 260 `TRANS_TYPE_DISALLOWED` | 1 |
| W4  | DDTC ヒット後: (`is_translated` OR `is_pcie_tr_req`) && `!dc.tc.en_ats` | `ddtc_lu_hit`, `dc_base.tc.en_ats` | 260 | 0 |
| W5  | DDTC ヒット後: `pv_i && !dc.tc.pdtv` | `pv_i`, `dc_base.tc.pdtv` | 260 | 0 |
| W6  | DDTC ヒット後: `pv_i && dc.tc.pdtv && pid_wider_than_supported` | `pid_wider_than_supported` (`tw:275–276`) | 260 | 0 |
| W7  | PDTC ヒット後: `priv_lvl_i && !pc.ta.ens` | `priv_lvl_i`, `pdtc_lu_content.ta.ens` | 260 | 0 |
| W8  | IOTLB ヒット後: `is_store && !1S_pte.w && S1_en` | `iotlb_lu_1S_content.w`, `is_store`, `S1_en` | 15 `STORE_PAGE_FAULT` | 0 |
| W9  | IOTLB ヒット後: `is_rx && !1S_pte.x && S1_en` | `iotlb_lu_1S_content.x`, `is_rx`, `S1_en` | 13 `LOAD_PAGE_FAULT` | 0 |
| W10 | IOTLB ヒット後: `!priv_lvl_i && !1S_pte.u && S1_en`（U-mode, U=0 の PTE） | `priv_lvl_i`, `iotlb_lu_1S_content.u` | 13 / 15 | 0 |
| W11 | IOTLB ヒット後: `priv_lvl_i && 1S_pte.u && (!pc.ta.sum OR 1S_pte.x) && S1_en`（S-mode, U=1） | `pdtc_lu_content.ta.sum`, `iotlb_lu_1S_content.u/x` | 13 / 15 | 0 |
| W12 | IOTLB ヒット後: `is_store && !2S_pte.w && S2_en` | `iotlb_lu_2S_content.w`, `S2_en` | 23 `STORE_GUEST_PAGE_FAULT` | 0 |
| W13 | IOTLB ヒット後: `is_rx && !2S_pte.x && S2_en` | `iotlb_lu_2S_content.x` | 21 `LOAD_GUEST_PAGE_FAULT` | 0 |
| W14 | デバッグリクエストで MSI 変換が発生 (`init_msi_trans & req_dbg_i`) | `init_msi_trans`, `req_dbg_i` | 260 | 0 |

### 3.2 PTW レベル (`ptw_error`, `ptw:727–751`)

| #   | 検出条件 | `pf_excep_n` | `pt_data_corrupt` | Cause Code |
|-----|---|---|---|---|
| P1  | `!pte.v` OR (`!pte.r && pte.w`) (無効 PTE) (`ptw:459–461`) | 1 | — | `STAGE_1`: 13/15 PF, `STAGE_2_x`: 21/23 GPF |
| P2  | 非リーフ PTE に A/D/U ビットがセット (`ptw:671–675`) | 1 | — | 同上（ステージ依存） |
| P3  | LVL3 で非リーフ PTE（ページレベル超過）(`ptw:679–684`) | 1 | — | 同上 |
| P4  | ミスアライメントスーパーページ: LVL1 かつ `pte.ppn[17:0]!=0`、OR LVL2 かつ `pte.ppn[8:0]!=0` (`ptw:555–563`) | 1 | — | 同上 |
| P5  | `pte.reserved != 0`（予約ビット使用）(`ptw:690–696`) | 1 | — | 同上 |
| P6  | `S2_en && STAGE_1 && pte.ppn[PPNW-1:GPPNW] != 0`（GPA が 41 bit 超）(`ptw:700–706`) | 1 | — | 21/23 `LOAD/STORE_GUEST_PAGE_FAULT`（stage=`STAGE_2_INTERMED` を強制セット） |
| P7  | AXI R チャネルエラー (`r.resp != RESP_OKAY`) (`ptw:717–723`) | — | 1 | 274 `PT_DATA_CORRUPTION` |

- `ptw_error_2S_int_o = (ptw_stage_q == STAGE_2_INTERMED)`（`ptw:749`）— S1 変換のための暗黙 S2 アクセス中のエラー
- `flush_cdw_o = cdw_implicit_access_q`（`ptw:750`）— CDW 暗黙アクセス中にエラーが発生したら CDW に通知

### 3.3 CDW レベル (`cdw_error`, `cdw:408–720`)

| #   | 検出条件 | Cause Code |
|-----|---|---|
| C1  | 非リーフ DDT/PDT エントリ: `nl.v == 0` (`cdw:408–411`) | 258 `DDT_ENTRY_INVALID` / 266 `PDT_ENTRY_INVALID` |
| C2  | 非リーフ DDT/PDT エントリ: `nl.reserved_1` or `nl.reserved_2 != 0` (`cdw:415–419`) | 259 `DDT_ENTRY_MISCONFIGURED` / 267 `PDT_ENTRY_MISCONFIGURED` |
| C3  | リーフ DC: `dc_tc.v == 0` (`cdw:535–539`) | 258 `DDT_ENTRY_INVALID` |
| C4  | リーフ DC: `dc_tc` 設定チェック失敗（ATS, T2GPA, DPE, AMO-HWAD, BE, SXL など）(`cdw:542–553`) | 259 `DDT_ENTRY_MISCONFIGURED` |
| C5  | リーフ DC: `dc_iohgatp` 設定チェック失敗（mode 値, T2GPA 必須, PPN[1:0]!=0 など）(`cdw:561–568`) | 259 |
| C6  | リーフ DC: `dc_ta` 予約ビット (`cdw:579–582`) | 259 |
| C7  | リーフ DC: `dc_fsc` 設定チェック失敗（PDT mode 範囲, iosatp mode 範囲）(`cdw:591–608`) | 259 |
| C8  | リーフ DC (MSI 有効): `msiptp.mode` 不正, `msi_addr_mask` 予約ビット, `msi_addr_pattern` 予約ビット (`cdw:785–815`) | 259 |
| C9  | リーフ PC: `pc_ta.v == 0` (`cdw:498–502`) | 266 `PDT_ENTRY_INVALID` |
| C10 | リーフ PC: `pc_ta.reserved != 0` (`cdw:505–509`) | 267 `PDT_ENTRY_MISCONFIGURED` |
| C11 | リーフ PC: `pc_fsc` 設定チェック失敗（mode 値, supported VA mode）(`cdw:517–525`) | 267 |
| C12 | AXI R チャネルエラー（DDT アクセス）(`cdw:710–719`) | 268 `DDT_DATA_CORRUPTION` |
| C13 | AXI R チャネルエラー（PDT アクセス）(`cdw:710–719`) | 269 `PDT_DATA_CORRUPTION` |

### 3.4 `report_fault_o` の論理 (`tw:280–281`)

```text
report_fault_o = (((ddtc_lu_hit & !dc_base.tc.dtf) |
                   report_always | msi_write_error_i | (cdw_error & is_ddt_walk))
                 & trans_error_o)
```

- `report_always=1` → DDTC ルックアップ前のエラー（W1, W2, W3）は **常に報告**
- `DC.tc.DTF=1` → DDTC ヒット後のエラーは **報告抑制**（フォルト報告無効化）
- CDW の DDT ウォーク中のエラー (`cdw_error & is_ddt_walk`) は DTF に関わらず報告
- `msi_write_error_i` も常に報告

---

## 4. 変換リクエスト到来からの完了シーケンス（場合分け）

### Case A: 完全キャッシュヒット（DDTC ヒット + PDTC ヒット + IOTLB ヒット）

1. `req_trans_i=1` → translation ブロック起動
2. 入力チェック（`ddtp.mode`, DID 幅）— 通過
3. `ddtc_access=1` → DDTC 組合せ論理が即時評価 → `ddtc_lu_hit=1`（同サイクル）
4. DDTC ヒット処理: トランザクションタイプ・ATS チェック通過
5. `pdtc_access=1`（`DC.tc.pdtv=1` かつ `pv_i=1` の場合のみ）→ PDTC 即時ヒット
6. GSCID / PSCID / iohgatp_ppn / iosatp_ppn を確定 → `iotlb_access=1`
7. IOTLB 組合せ論理評価 → `iotlb_lu_hit=1`（同サイクル）
8. パーミッションチェック（W, X, U ビット）— 通過
9. `spaddr_o` を PPN + IOVA[11:0] + スーパーページ補正で計算（`tw:999–1033`）
10. `trans_valid_o=1` — 同一サイクルで完了（組合せ論理のみ）

### Case B: DDTC ミス → CDW DDT ウォーク（S2 無効、pdtv=0）

1. `req_trans_i=1` → `ddtc_access=1` → DDTC ミス
2. `init_cdw_i = ddtc_access && ~ddtc_lu_hit = 1` → CDW FSM: `IDLE→MEM_ACCESS`
3. CDW が `ddtp.ppn` を起点に DDT をウォーク（AXI AR チャンネルで 1〜7 DW 読み出し）
4. 非リーフエントリを経由してリーフ DC に到達 → `LEAF` 状態で 4 DW 読み込み（MSI 無効時）
5. DC config チェック通過 → `update_dc_o=1` → DDTC 更新
6. CDW: IDLE 復帰 → 次サイクルで `ddtc_lu_hit=1`
7. `iotlb_access=1` → IOTLB ミス → `init_ptw=1`
8. PTW: S1 のみまたは S1+S2 でウォーク（後述）
9. PTW 完了 → `ptw_update=1` → IOTLB 更新
10. 次サイクル: IOTLB ヒット → `trans_valid_o=1`

### Case C: S1+S2 ネスト変換（IOTLB ミス時の PTW）

1. PTW IDLE: `{en_1S=1, en_2S=1}` → `ptw_stage=STAGE_2_INTERMED`
2. `GPA_1 = {iosatp_ppn[GPPNW-1:0], VA[38:30], 3'b0}` を計算
3. 第 1 S2 ウォーク開始: `ptw_pptr = {iohgatp_ppn[43:2], GPA_1[40:30], 3'b0}`
4. S2 L1 → L2 → L3 まで `MEM_ACCESS` → `PROC_PTE` を繰り返し、S1 L1 アドレスの SPA を取得
5. `ptw_stage=STAGE_1`、S1 L1 アクセス → S1 非リーフなら `GPA_2` を計算して再び `STAGE_2_INTERMED` に
6. S1 が 3 レベル全て走る場合、途中の各 S1 PTE アドレスに対して S2 ウォークが発生（最悪 3 回）
7. S1 リーフ PTE 発見 → `leaf_1Spte_n` に保存 → `ptw_stage=STAGE_2_FINAL`
8. 最終 GPA を S2 ウォーク → SPA（S2 リーフ PTE の ppn）取得
9. `update_o=1` → IOTLB に S1+S2 両 PTE を格納

### Case D: `DC.tc.pdtv=1`、S2 有効 → CDW による `pdtp.PPN` の暗黙変換

1. CDW `LEAF`: `DC.fsc.ppn`（`pdtp.ppn`）は GPA → `translate_pdtp=1` → `GUEST_TR` 状態へ
2. CDW `GUEST_TR`: `cdw_implicit_access_o=1`、`pdt_gppn_o = dc_fsc_q.ppn[GPPNW-1:0]`、`iohgatp_ppn_fw_o = dc_iohgatp_q.ppn` をアサート
3. PTW（暗黙的モード）: `ptw_en_1S=0, ptw_en_2S=1`、S2 のみで `pdtp.ppn` の GPA → SPA を変換
4. PTW 完了 → `cdw_done_o=1`
5. CDW `LEAF`: `dc_fsc_n.ppn = pdt_ppn_i`（`iotlb_up_2S_content.ppn` から）で `DC.fsc.ppn` を SPA に上書き（`cdw:469`）
6. `update_dc_o=1` → DDTC 更新

### Case E: MSI 変換（S1 有効、IOVA が MSI GPA にマップ）

1. PTW の S1 ウォークで GPA 確定 → `gpaddr_is_msi=1`（MSI アドレスマスク一致）
2. PTW: `gpaddr_is_msi_o=1` をアサートして IDLE へ（S2 ウォーク不実施）
3. `init_msi_trans = gpaddr_is_msi = 1` → MSI PTW 起動
4. MSI PTW: `DC.msiptp.ppn` 起点で MSI PT をウォーク
5. FLAT PTE: `msi_update=1` → IOTLB に S1 PTE + MSI flat PTE を格納
6. MRIF PTE: `mrifc_update=1` → MRIFC に MRIF エントリ格納 → `ignore_request_o=1`
7. MRIF PTE の場合: `msi_data_valid_i=1` 到来時に `init_mrif_i=1` → MRIF Handler 起動
8. MRIF Handler がメモリ上の MRIF にペンディングビットを書き込み → `ignore_request_o=1`

### Case F: Bare 変換（S1=0, S2=0, MSI でない）

1. DDTC ヒット（および pdtv=1 なら PDTC ヒット）
2. `bare_translation = ~S1_en & ~S2_en & ~iova_is_msi = 1`（`tw:354–356`）
3. 条件チェック（`tw:1055–1060`）: `ddtc_lu_hit && (pdtc_lu_hit || !dc.tc.pdtv || ...) && bare_translation`
4. `trans_valid_o=1`、`spaddr_o = iova_i[PLEN-1:0]` — IOVA をそのまま PA として出力

---

## 5. 各条件分岐の判定方法

| 条件 | 判定式 | 根拠 |
|---|---|---|
| `is_translated` | `!trans_type_i[3] && trans_type_i[2]` | `tw:155` — bit[2]=1, bit[3]=0 が Translated |
| `is_pcie_tr_req` | `trans_type_i == 6'b00_1_0_00` | `tw:159` |
| `is_store` | `(&trans_type_i[1:0]) && !trans_type_i[3]` | `tw:163` — bits[1:0]=11 が Write |
| `is_rx` | `!trans_type_i[3] && !trans_type_i[1] && trans_type_i[0]` | `tw:167` — bits[3,1]=0, bit[0]=1 が RX |
| `S1_en` | `(dc.tc.pdtv && pdtc.fsc.mode!=0)` OR `(!dc.tc.pdtv && dc.fsc.mode!=0)` | `tw:221–222` — iosatp/pdtp の mode が 0 でなければ有効 |
| `S2_en` | `dc.iohgatp.mode != 4'b0000` | `tw:223` |
| `iova_is_msi` | `msi_enabled && is_store && (iova[GPLEN-1:12] & ~mask) == (pattern & ~mask)` | `tw:546–548`（MSI 有効時のみ） |
| `init_ptw` | `iotlb_lu_miss & (S1_en | (S2_en & ~iova_is_msi))` | `tw:339–341` — IOTLB ミスかつ変換有効 |
| `init_msi_trans` | `gpaddr_is_msi | (iotlb_lu_miss & mrifc_lu_miss & ~S1_en & iova_is_msi)` | `tw:348–350` |
| `bare_translation` | `~S1_en & ~S2_en & ~iova_is_msi` | `tw:354–356` |
| `process_id` | `(!pv_i && dc.tc.dpe) ? '0 : pid_i` | `tw:271` — DPE=1 かつ pv=0 のとき PID=0 |
| `pid_wider_than_supported` | `(fsc.mode==PD8 && pid[19:8]!=0)` OR `(fsc.mode==PD17 && pid[19:17]!=0)` | `tw:275–276` |
| `ptw_iohgatp_ppn` | `(is_ddt_walk & cdw_implicit_access) ? iohgatp_ppn_fw : iohgatp_ppn` | `tw:171` — CDW 暗黙アクセス中は CDW がフォワード |
| `ptw_en_1S`（暗黙的） | `cdw_implicit_access ? 0 : S1_en` | `tw:227` |
| `ptw_en_2S`（暗黙的） | `cdw_implicit_access ? 1 : S2_en` | `tw:228` |
| `is_implicit_o` | `ptw_error_2S_int | (flush_cdw & ~is_ddt_walk)` | `tw:251` — S1 変換の暗黙 S2 アクセスエラー |
| エラー cause 選択 | `priority case (1'b1)` | `tw:1080–1088` — `wrap → cdw → ptw → msiptw → mrif → msi_write` |

---

## 6. その他の重要ポイント

1. **`req_trans_i` の保持必須** (`tw:25–27`)
    ウォーク中に `req_trans_i` がクリアされると IOTLB ヒット信号もクリアされる。現状実装の制約。

2. **エッジトリガ制御**（PTW `ptw:162–174`、CDW `cdw:209–222`）
    `init_ptw_i` / `init_cdw_i` の立ち上がりエッジのみで FSM を起動する `edge_trigger_q` レジスタ。これにより Walker が IDLE に戻った後も init 信号がまだ High の場合の誤再起動を防止。

3. **DDTC と PDTC の同時アクセス**（`tw:879`, `tw:943` の comb ブロック）
    DDTC ルックアップ結果が組合せ論理で確定した同サイクルに PDTC にもアクセスが始まる。FSM はなく全て組合せ論理での多段連鎖評価。

4. **スーパーページの物理アドレス合成**（`tw:999–1033`）
    S1 / S2 両ステージがスーパーページの場合 6 パターンをケース文で合成。`spaddr_o = {2S_ppn, iova[11:0]}` をベースに VPN の各セグメントをページオフセット相当部分として上書き。

5. **IOTLB 更新の仲裁**（`tw:314–324`）
    `msi_update`（MSI PTW）が PTW の `ptw_update` より優先（MSI 更新時は 2S スーパーページフラグを強制 0 にする設計）。両方同時は原則発生しない（`init_ptw` と `init_msi_trans` の排他関係）。

6. **デバッグ変換のスーパーページエンコード**（`tw:1037–1040`）
    `req_dbg_i=1` の場合、IOTLB ヒット時の `spaddr_o` でスーパーページ対応ビットに実際の PPN ではなくマスク値（2M: `{1'b0, {8{1'b1}}}`, 1G: `{1'b0, {17{1'b1}}}`）を設定してサイズを示す。

7. **`pdtp.PPN` 変換後の `DC.fsc.ppn` 上書き**（`cdw:469`）
    CDW の `LEAF` 状態で `ptw_done_i=1` を受信した時点で `dc_fsc_n.ppn = pdt_ppn_i`（`iotlb_up_2S_content.ppn` の最新値）で `pdtp.ppn` を SPA に置き換えてから DDTC に格納。

8. **MSI アドレスチェックの S1 変換内での評価** (`ptw:187–189`)
    PTW は S1 リーフ PTE の `pte.ppn` を MSI マスク / パターンと照合して `gpaddr_is_msi` を評価。これは S2 変換前に行われ、S2 が有効でも MSI GPA 判定は S1 PTE の `ppn` に対して行う。

9. **MRIFC と IOTLB の並列ルックアップ**（`tw:711` `lookup_i = iotlb_access`）
    `iova_is_msi && ~S1_en` の経路では、MSI PTW 起動条件に `mrifc_lu_miss` が含まれる（`tw:349`）。MRIFC ヒット時は MRIF Handler へ直接進み、MSI PTW を再走不要にする。

10. **DC フォーマット（基本 vs 拡張）の動的選択**（`tw:539–540`）
    `MSITrans != MSI_DISABLED` のとき `dc_ext_t` にキャスト（7 DW = 56 bytes）; それ以外は `dc_base_t`（4 DW = 32 bytes）。CDW の `ar_len` パラメータで AXI バースト長を変更（`cdw:35–36`）。

---

## 7. このモジュールのテスト方針

### 7.1 現状のテストカバレッジ（`tb_coco/translation_logic/ptw/`）

現在のテストベンチは **PTW 単体に特化**しており、wrapper 全体をカバーしていない。以下の点が未テスト:

- DDTC / PDTC ルックアップ論理
- CDW（DDT / PDT ウォーク）
- IOTLB ヒット・パーミッションチェック（W / X / U ビット）
- MSI 変換フロー全体
- `report_fault_o` の DTF 制御
- 複数エラーソースの priority case 動作

### 7.2 wrapper 単体テストで必要なシナリオ分類

| カテゴリ | 必須テストケース |
|---|---|
| キャッシュ状態 | 全ミス（コールドスタート）→ CDW + PTW フル起動、部分ヒット（DDTC ヒット + IOTLB ミス）、全ヒット |
| 変換タイプ | Untranslated R/W/RX、Translated（T2GPA=0/1）、PCIe ATS |
| ステージ設定 | S1 のみ、S2 のみ、S1+S2 ネスト、Bare |
| プロセスコンテキスト | `pdtv=0`（DC のみ）、`pdtv=1 + pv=0 + dpe=0`、`pdtv=1 + pv=1` |
| スーパーページ | 1G / 2M / 4K 各ステージ、S1+S2 の全 6 組合せ |
| MSI 変換 | S1 経由 MSI GPA、S1 なし直接 MSI GPA、FLAT PTE、MRIF PTE（`MSI_FLAT_MRIF` 時） |
| CDW 暗黙変換 | `pdtp.PPN` の S2 変換、非リーフ PDT GPPN の S2 変換 |
| フォルト網羅 | W1–W14、P1–P7、C1–C13 の各フォルト条件 |
| DTF ビット | `DC.tc.DTF=1` でフォルト報告が抑制されることの確認 |
| DDT 深さ | 1LVL / 2LVL / 3LVL モード各々の DDT ウォーク |
| 無効化コマンド | `IODIR.INVAL_DDT`（DV=0/1）、`IODIR.INVAL_PDT`、`IOTINVAL.VMA`（全 8 組合せ）、`IOTINVAL.GVMA`（全 3 組合せ）、無効化後の再変換（ミス発生確認） |
| デバッグ変換 | `req_dbg_i` でスーパーページマスク値が正しく出力される確認 |
| エラー優先度 | 複数エラーが同時発生した場合の `cause_code_o` 優先順位（priority case） |

### 7.3 テスト実装上の留意点

- `req_trans_i` は変換完了（`trans_valid_o` または `trans_error_o`）まで **High 保持が必須**（`tw:25–27`）
- CDW / PTW それぞれの AXI メモリモデルを **別バスとして分離**して実装する必要あり
- CDW 暗黙変換テストでは PTW の AXI バスとの同時駆動シナリオが必要
- MRIFC テストでは `msi_data_valid_i` のタイミング（MSI PTW 完了後）を正確に制御