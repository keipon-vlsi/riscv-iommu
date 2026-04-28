# RISC-V IOMMU ビットフィールド チートシート

ソース:
- `doc/spec/riscv-iommu/06-chapter-3.-data-structures.md`
- `doc/spec/riscv-iommu/09-chapter-6.-memory-mapped-register-interface.md`
- `doc/spec/riscv-privileged/14-chapter-12.-supervisor-level-isa-version-1.13.md`

---

## 目次

1. [device_id](#device_id)
2. [Non-leaf DDTE](#non-leaf-ddte)
3. [DC (Device Context)](#dc-device-context)
4. [process_id](#process_id)
5. [Non-leaf PDTE](#non-leaf-pdte)
6. [PC (Process Context)](#pc-process-context)
7. [Sv39 VA](#sv39-va)
8. [Sv39 PA](#sv39-pa)
9. [Sv39 PTE](#sv39-pte)
10. [capabilities](#capabilities)
11. [fctl](#fctl)
12. [ddtp](#ddtp)

---

## device_id

24 ビット。DDT ラジックスツリー探索に使用する 3 段インデックス。
フォーマットは `capabilities.MSI_FLAT` に依存する。

### Base DDT フォーマット (capabilities.MSI_FLAT = 0, DC = 32 バイト)

| ビット | フィールド | 幅 | 説明 |
|--------|-----------|-----|------|
| [23:16] | DDI[2] | 8 | 第 1 段 DDT インデックス |
| [15:7]  | DDI[1] | 9 | 第 2 段 DDT インデックス |
| [6:0]   | DDI[0] | 7 | 第 3 段 DDT インデックス (DC へのオフセット) |

### Extended DDT フォーマット (capabilities.MSI_FLAT = 1, DC = 64 バイト)

| ビット | フィールド | 幅 | 説明 |
|--------|-----------|-----|------|
| [23:15] | DDI[2] | 9 | 第 1 段 DDT インデックス |
| [14:6]  | DDI[1] | 9 | 第 2 段 DDT インデックス |
| [5:0]   | DDI[0] | 6 | 第 3 段 DDT インデックス (DC へのオフセット) |

> DDT 段数は `ddtp.iommu_mode`: 1LVL=DDI[0]のみ, 2LVL=DDI[1:0], 3LVL=DDI[2:0]

---

## Non-leaf DDTE

Device Directory Table エントリ (非リーフ)。8 バイト。

| ビット | フィールド | 属性 | 説明 |
|--------|-----------|------|------|
| [53:10] | PPN | — | 次段 DDT ページの PPN |
| [63:54],[9:1]   | reserved | WPRI | 予約 |
| [0]     | V | — | Valid ビット。0=エントリ無効 (Fault) |

---

## DC (Device Context)

デバイスごとの変換設定。`capabilities.MSI_FLAT=0` なら 32 バイト、`=1` なら 64 バイト。

### DC.tc — Translation Control (offset 0, 64 bit)

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [0]    | V | Valid。0=DC 無効 |
| [1]    | EN_ATS | PCIe ATS 変換リクエストを有効化 |
| [2]    | EN_PRI | PCIe Page-Request Interface (PRI) を有効化 |
| [3]    | T2GPA | ATS 変換完了で GPA を返す (capabilities.T2GPA=1 が必要) |
| [4]    | DTF | Disable Translation Faults。フォルトを抑制しゼロページを返す |
| [5]    | PDTV | 1=PDT 有効 (fsc は pdtp として解釈)、0=PDT 無効 (fsc は iosatp) |
| [6]    | PRPR | Page-Request PRivileged-Request |
| [7]    | GADE | Guest (2段目) A/D ビットのハードウェア更新を有効化 |
| [8]    | SADE | Supervisor (1段目) A/D ビットのハードウェア更新を有効化 |
| [9]    | DPE | Disable Page faults for Execute access |
| [10]   | SBE | Supervisor Big-page Enable |
| [11]| SXL | Supervisor XLEN (00=XLEN設定に従う) |
| [23:12]| reserved | 予約 |
| [31:24]| custom | カスタム使用 |
| [63:32]| reserved | 予約 |

### DC.iohgatp — G-stage page table pointer (offset 8, 64 bit)

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [43:0]  | PPN | G-stage ページテーブルrootページの PPN (44 ビット) |
| [59:44] | GSCID | Guest Soft-Context ID (16 ビット) |
| [63:60] | MODE | 0=Bare (2段無効), 8=Sv39x4, 9=Sv48x4, 10=Sv57x4 |

### DC.ta — Translation Attributes (offset 16, 64 bit)

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [19:0]  | PSCID | Process Soft-Context ID (20 ビット)。PDTV=0 のとき使用 |
| [31:20] | reserved | 予約 |
| [43:32] | RCID | Resource Controller ID (12 ビット、QOSID 用) |
| [55:44] | MCID | Monitoring Counter ID (12 ビット、QOSID 用) |
| [63:56] | reserved | 予約 |

### DC.fsc — First-Stage Context (offset 24, 64 bit)

**PDTV=0 の場合 (iosatp — 1段目ページテーブルポインタ)**

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [43:0]  | PPN | 1段目ページテーブル根ページの PPN |
| [59:44] | ASID | Address Space ID (16 ビット) |
| [63:60] | MODE | 0=Bare, 8=Sv39, 9=Sv48, 10=Sv57 |

**PDTV=1 の場合 (pdtp — PDT ポインタ)**

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [43:0]  | PPN | PDT 根ページの PPN |
| [63:60] | MODE | 0=Bare, 1=PD8 (1段/8bit), 2=PD17 (2段/17bit), 3=PD20 (3段/20bit) |

### DC.msiptp / msi_addr_mask / msi_addr_pattern (offset 32-56, MSI_FLAT=1 のみ)

| オフセット | フィールド | 説明 |
|-----------|-----------|------|
| 32 | msiptp | MSI ページテーブルポインタ。[3:0]=MODE(0=Off,1=Flat), [43:0]=PPN |
| 40 | msi_addr_mask | MSI 判定マスク (52 ビット有効) |
| 48 | msi_addr_pattern | MSI 判定パターン (52 ビット有効) |

---

## process_id

20 ビット。PDT ラジックスツリー探索に使用する 3 段インデックス。

| ビット | フィールド | 幅 | 説明 |
|--------|-----------|-----|------|
| [19:17] | PDI[2] | 3 | 第 1 段 PDT インデックス (PD20 のみ) |
| [16:8]  | PDI[1] | 9 | 第 2 段 PDT インデックス (PD17/PD20) |
| [7:0]   | PDI[0] | 8 | 第 3 段 PDT インデックス (全モード) |

> PDT 段数は `DC.fsc.MODE`: PD8=PDI[0]のみ, PD17=PDI[1:0], PD20=PDI[2:0]

---

## Non-leaf PDTE

Process Directory Table エントリ (非リーフ)。8 バイト。Non-leaf DDTE と同じフォーマット。

| ビット | フィールド | 属性 | 説明 |
|--------|-----------|------|------|
| [63:10] | PPN | — | 次段 PDT ページの PPN |
| [9:1]   | reserved | WPRI | 予約 |
| [0]     | V | — | Valid ビット。0=エントリ無効 (Fault) |

---

## PC (Process Context)

プロセスごとの変換設定。16 バイト。

### PC.ta — Translation Attributes (offset 0, 64 bit)

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [0]    | V | Valid。0=PC 無効 |
| [1]    | ENS | Enable Supervisor mode (1段目を有効化) |
| [2]    | SUM | Supervisor User-page access. 1=S-mode から U-page へのロード/ストアを許可 |
| [19:3] | reserved | 予約 |
| [39:20]| PSCID | Process Soft-Context ID (20 ビット) |
| [63:40]| reserved | 予約 |

### PC.fsc — First-Stage Context (offset 8, 64 bit)

DC.fsc (PDTV=0) と同フォーマット。

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [43:0]  | PPN | 1段目ページテーブル根ページの PPN |
| [59:44] | ASID | Address Space ID (16 ビット) |
| [63:60] | MODE | 0=Bare, 8=Sv39, 9=Sv48, 10=Sv57 |

---

## Sv39 VA

仮想アドレス。64 ビット符号拡張 (有効幅 39 ビット)。

```
63        39 38      30 29      21 20      12 11         0
+-----------+----------+----------+----------+------------+
| sign-ext  |  VPN[2]  |  VPN[1]  |  VPN[0]  | page offset|
| (bit[38]) |  (9 bit) |  (9 bit) |  (9 bit) |  (12 bit)  |
+-----------+----------+----------+----------+------------+
```

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [63:39] | sign-ext | ビット[38]の符号拡張。[63:39]が[38]と一致しない場合は無効アドレス |
| [38:30] | VPN[2] | ページテーブル第1段インデックス (9 ビット) |
| [29:21] | VPN[1] | ページテーブル第2段インデックス (9 ビット) |
| [20:12] | VPN[0] | ページテーブル第3段インデックス (9 ビット) |
| [11:0]  | offset | ページ内オフセット (12 ビット) |

**スーパーページ**:
- 1 GiB: リーフ PTE が第1段 (VPN[2])。PA オフセットは VPN[1:0]+offset = 30 ビット
- 2 MiB: リーフ PTE が第2段 (VPN[1])。PA オフセットは VPN[0]+offset = 21 ビット

---

## Sv39 PA

物理アドレス。最大 56 ビット。

```
55      30 29      21 20      12 11         0
+----------+----------+----------+------------+
|  PPN[2]  |  PPN[1]  |  PPN[0]  | page offset|
| (26 bit) |  (9 bit) |  (9 bit) |  (12 bit)  |
+----------+----------+----------+------------+
```

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [55:30] | PPN[2] | 物理ページ番号第2段 (26 ビット) |
| [29:21] | PPN[1] | 物理ページ番号第1段 (9 ビット) |
| [20:12] | PPN[0] | 物理ページ番号第0段 (9 ビット) |
| [11:0]  | offset | ページ内オフセット (12 ビット) |

---

## Sv39 PTE

ページテーブルエントリ。8 バイト。

```
63 62 61 60  54 53    28 27   19 18   10 9 8 7 6 5 4 3 2 1 0
+--+-----+----+----------+-------+-------+---+-+-+-+-+-+-+-+-+
|N |PBMT |rsv |  PPN[2]  | PPN[1]| PPN[0]|RSW|D|A|G|U|X|W|R|V|
+--+-----+----+----------+-------+-------+---+-+-+-+-+-+-+-+-+
```

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [0]    | V | Valid。0=PTE 無効 |
| [1]    | R | Read 許可 |
| [2]    | W | Write 許可 |
| [3]    | X | eXecute 許可 |
| [4]    | U | User-mode アクセス許可。S-mode は SUM=0 のとき U=1 ページへのアクセスを禁止 |
| [5]    | G | Global マッピング (全 ASID に有効) |
| [6]    | A | Accessed。ハードウェアがアクセス時にセット (Svadu) |
| [7]    | D | Dirty。ハードウェアが書き込み時にセット (Svadu) |
| [9:8]  | RSW | Reserved for Software 使用 |
| [18:10]| PPN[0] | 物理ページ番号第0段 (9 ビット) |
| [27:19]| PPN[1] | 物理ページ番号第1段 (9 ビット) |
| [53:28]| PPN[2] | 物理ページ番号第2段 (26 ビット) |
| [60:54]| reserved | 予約 (Svnapot の場合は [59:54] を別途参照) |
| [62:61]| PBMT | Page-Based Memory Types (Svpbmt)。0=PMA, 1=NC, 2=IO, 3=rsvd |
| [63]   | N | NAPOT (Svnapot)。連続ページ最適化 |

**リーフ判定**: R=1 または X=1 → リーフ PTE。R=0 かつ X=0 → 非リーフ (次段 PPN を参照)

**無効ケース**:
- V=0: 無効
- W=1 かつ R=0: 予約 (ページフォルト)
- スーパーページの場合、対応する PPN 下位ビットが 0 でなければ不整合 (ページフォルト)

---

## capabilities

IOMMU 機能通知レジスタ。8 バイト、読み出し専用 (RO)。オフセット 0x000。

| ビット | フィールド | 説明 |
|--------|-----------|------|
| [7:0]   | version | 仕様バージョン。上位ニブル=メジャー、下位ニブル=マイナー (例: 0x10 = v1.0) |
| [8]     | Sv32 | 32 ビット VA ページング対応 |
| [9]     | Sv39 | 39 ビット VA ページング対応 |
| [10]    | Sv48 | 48 ビット VA 対応 (Sv39 が必要) |
| [11]    | Sv57 | 57 ビット VA 対応 (Sv48 が必要) |
| [13:12] | reserved | — |
| [14]    | Svrsw60t59b | PTE ビット[60:59] をソフトウェア使用として予約 |
| [15]    | Svpbmt | ページベースメモリタイプ (Svpbmt) 対応 |
| [16]    | Sv32x4 | G-stage 34 ビット VA 対応 |
| [17]    | Sv39x4 | G-stage 41 ビット VA 対応 |
| [18]    | Sv48x4 | G-stage 50 ビット VA 対応 |
| [19]    | Sv57x4 | G-stage 59 ビット VA 対応 |
| [20]    | reserved | — |
| [21]    | AMO_MRIF | MRIF へのアトミック更新対応 |
| [22]    | MSI_FLAT | MSI パススルーモード (Flat) 対応 |
| [23]    | MSI_MRIF | MSI MRIF モード対応 |
| [24]    | AMO_HWAD | PTE A/D ビットのハードウェア更新対応 |
| [25]    | ATS | PCIe ATS / PRI 対応 |
| [26]    | T2GPA | ATS 変換完了で GPA を返す機能対応 |
| [27]    | END | 0=単一エンディアン、1=両エンディアン対応 |
| [29:28] | IGS | 割り込み生成方式: 0=MSI only, 1=WSI only, 2=BOTH, 3=reserved |
| [30]    | HPM | ハードウェアパフォーマンスモニタ実装 |
| [31]    | DBG | 変換リクエストデバッグインタフェース対応 |
| [37:32] | PAS | 物理アドレスサイズ (ビット幅) |
| [38]    | PD8 | 1段 PDT (8 ビット process_id) 対応 |
| [39]    | PD17 | 2段 PDT (17 ビット process_id) 対応 |
| [40]    | PD20 | 3段 PDT (20 ビット process_id) 対応 |
| [41]    | QOSID | QoS ID 付与対応 |
| [42]    | NL | 非リーフ PTE 無効化拡張対応 |
| [43]    | S | アドレス範囲無効化拡張対応 |
| [55:44] | reserved | — |
| [63:56] | custom | カスタム使用 |

---

## fctl

フィーチャー制御レジスタ。4 バイト。オフセット 0x008。

| ビット | フィールド | 属性 | 説明 |
|--------|-----------|------|------|
| [0]    | BE | WARL | 0=リトルエンディアン、1=ビッグエンディアンでメモリアクセス |
| [1]    | WSI | WARL | 0=MSI 割り込み、1=WSI (Wire) 割り込み。`capabilities.IGS=BOTH` のときのみ有効 |
| [2]    | GXL | WARL | G-stage アドレス変換スキームを制御 (Table 2/3 参照) |
| [15:3] | reserved | WPRI | — |
| [31:16]| custom | WPRI | カスタム使用 |

> `ddtp.iommu_mode != Off` のとき、または in-memory キューが有効なときに変更した場合の動作は UNSPECIFIED。

---

## ddtp

Device Directory Table ポインタレジスタ。8 バイト。オフセット 0x010。

| ビット | フィールド | 属性 | 説明 |
|--------|-----------|------|------|
| [3:0]  | iommu_mode | WARL | IOMMU 動作モード (下表参照) |
| [4]    | busy | RO | 書き込み処理中フラグ。1 のとき ddtp への追加書き込みは UNSPECIFIED |
| [9:5]  | reserved | WPRI | — |
| [53:10]| PPN | WARL | DDT 根ページの PPN (44 ビット) |
| [63:54]| reserved | WPRI | — |

**iommu_mode 値**:

| 値 | 名前 | 説明 |
|----|------|------|
| 0 | Off | インバウンドトランザクション全拒否 |
| 1 | Bare | 変換・保護なし。全トランザクションをパススルー |
| 2 | 1LVL | 1段 DDT (DDI[0] のみ) |
| 3 | 2LVL | 2段 DDT (DDI[1:0]) |
| 4 | 3LVL | 3段 DDT (DDI[2:0]) |
| 5–13 | reserved | — |
| 14–15 | custom | カスタム使用 |

> `busy=1` の状態で ddtp を書き換えると動作 UNSPECIFIED。必ず `busy=0` を確認してから書き込む。
> モード変更後はキャッシュの無効化コマンドが必要 (IOTLB / DDTC / PDTC)。
