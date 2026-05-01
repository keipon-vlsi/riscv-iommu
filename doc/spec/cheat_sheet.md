# RISC-V IOMMU Cheat Sheet — Bit Field Reference

**Sources:**
- `doc/spec/riscv-iommu/06-chapter-3.-data-structures.md`
- `doc/spec/riscv-iommu/09-chapter-6.-memory-mapped-register-interface.md`
- `doc/spec/riscv-privileged/14-chapter-12.-supervisor-level-isa-version-1.13.md`

---

## 1. device_id (24-bit) — DDT Index Partitioning

`capabilities.MSI_FLAT` によって分割方法が異なる。

### 1a. Base-format (MSI_FLAT = 0, DC size = 32 B)

```
 23       16 15        7  6          0
 +----------+----------+------------+
 |  DDI[2]  |  DDI[1]  |   DDI[0]   |
 |  (8 bit) |  (9 bit) |   (7 bit)  |
 +----------+----------+------------+
```

| フィールド | ビット範囲 | 幅    | 用途                                    |
| :--------- | :--------- | :---: | :--------------------------------------- |
| DDI[0]     | [6:0]      | 7 bit | L1 DDT インデックス (末端ページ内オフセット) |
| DDI[1]     | [15:7]     | 9 bit | L2 DDT インデックス                        |
| DDI[2]     | [23:16]    | 8 bit | L3 DDT インデックス                        |

### 1b. Extended-format (MSI_FLAT = 1, DC size = 64 B)

```
 23       15 14        6  5          0
 +----------+----------+------------+
 |  DDI[2]  |  DDI[1]  |   DDI[0]   |
 |  (9 bit) |  (9 bit) |   (6 bit)  |
 +----------+----------+------------+
```

| フィールド | ビット範囲 | 幅    | 用途                                         |
| :--------- | :--------- | :---: | :------------------------------------------- |
| DDI[0]     | [5:0]      | 6 bit | L1 DDT インデックス (64B DC、ページあたり 64 エントリ) |
| DDI[1]     | [14:6]     | 9 bit | L2 DDT インデックス                             |
| DDI[2]     | [23:15]    | 9 bit | L3 DDT インデックス                             |

---

## 2. Non-leaf DDT Entry (DDTE, 64-bit)

```
 63       54 53                    10  9        1  0
 +----------+----------------------+------------+--+
 | reserved |         PPN          |  reserved  | V|
 | (10 bit) |       (44 bit)       |  (9 bit)   |1b|
 +----------+----------------------+------------+--+
```

| フィールド | ビット  | 意味                                                   |
| :--------- | :------ | :----------------------------------------------------- |
| V          | [0]     | Valid。0 のとき "DDT entry not valid" (cause=258)       |
| reserved   | [9:1]   | 0 でなければ "DDT entry misconfigured" (cause=259)     |
| PPN        | [53:10] | 次レベル DDT ページの PPN (44 bit, 4 KiB アライン)      |
| reserved   | [63:54] | 0 でなければ "DDT entry misconfigured" (cause=259)     |

---

## 3. Device Context (DC) — Base-format 32 B / Extended 64 B

DC は DDT の末端エントリ。4 フィールド (+ MSI_FLAT=1 時 3 フィールド追加)。

### 3.1 DC.tc — Translation Control (64-bit, offset +0)

```
 63       32 31       24 23       12 11 10  9  8  7  6  5  4  3  2  1  0
 +----------+----------+----------+--+--+--+--+--+--+--+--+--+--+--+--+
 | reserved |  custom  | reserved |SX|SB|DP|SA|GA|PR|PD|DT|T2|EP|AT| V|
 +----------+----------+----------+--+--+--+--+--+--+--+--+--+--+--+--+
```
*(SX=SXL, SB=SBE, DP=DPE, SA=SADE, GA=GADE, PR=PRPR, PD=PDTV, DT=DTF, T2=T2GPA, EP=EN_PRI, AT=EN_ATS)*

| ビット   | フィールド | 意味                                                                   |
| :------- | :--------- | :--------------------------------------------------------------------- |
| [0]      | V          | Valid。0 なら "DDT entry not valid" (cause=258)                         |
| [1]      | EN_ATS     | PCIe ATS/PRI 有効化 (`capabilities.ATS=1` 必須)                        |
| [2]      | EN_PRI     | PCIe PRI (Page Request Interface) 有効化                               |
| [3]      | T2GPA      | ATS 応答で GPA を返す (`capabilities.T2GPA` 必須、`EN_ATS=1` 必須)     |
| [4]      | DTF        | DMA Translation Fault — fault reporting を無効化                       |
| [5]      | PDTV       | PDT Valid。1 のとき `fsc` フィールドが `pdtp` として使用される          |
| [6]      | PRPR       | PCIe PASID 付き PRI 要求時にレスポンス必須                              |
| [7]      | GADE       | G-stage A/D bit ハードウェア更新有効 (`capabilities.AMO_HWAD` 必須)    |
| [8]      | SADE       | S-stage A/D bit ハードウェア更新有効 (`capabilities.AMO_HWAD` 必須)    |
| [9]      | DPE        | Default Process Enable。`process_id` 無しの要求に `process_id=0` を適用 |
| [10]     | SBE        | Structure Big-Endian。1 = DC 内フィールドがビッグエンディアン           |
| [11]     | SXL        | S-stage Extra Level。1 = RV32 ページング (Sv32) 使用                   |
| [23:12]  | reserved   | —                                                                      |
| [31:24]  | custom     | カスタム拡張用                                                          |
| [63:32]  | reserved   | —                                                                      |

### 3.2 DC.iohgatp — G-stage Page Table Pointer (64-bit, offset +8)

```
 63       60 59             44 43                             0
 +----------+--------------+----------------------------------+
 |   MODE   |    GSCID     |              PPN                 |
 |  (4 bit) |   (16 bit)   |            (44 bit)              |
 +----------+--------------+----------------------------------+
```

| フィールド | ビット  | 意味                                                                       |
| :--------- | :------ | :------------------------------------------------------------------------- |
| PPN        | [43:0]  | G-stage ページテーブルルートの PPN (Bare 時は don't care)                   |
| GSCID      | [59:44] | Guest Soft-Context ID (VMID 相当)。TLB タグに使用 (16 bit)                 |
| MODE       | [63:60] | ページングモード: `0`=Bare, `8`=Sv39x4, `9`=Sv48x4, `10`=Sv57x4           |

> `iohgatp.MODE=Bare` のとき第 2 ステージ変換なし (IOVA = GPA = SPA)
> `fctl.GXL=1` のとき `8`=Sv32x4 のみ有効

### 3.3 DC.ta — Translation Attributes (64-bit, offset +16)

```
 63       52 51       40 39       32 31               12 11           0
 +----------+----------+----------+-------------------+--------------+
 |   MCID   |   RCID   | reserved |       PSCID        |   reserved   |
 | (12 bit) | (12 bit) |  (8 bit) |      (20 bit)      |   (12 bit)   |
 +----------+----------+----------+-------------------+--------------+
```

| フィールド | ビット  | 意味                                                         |
| :--------- | :------ | :----------------------------------------------------------- |
| reserved   | [11:0]  | —                                                            |
| PSCID      | [31:12] | Process Soft-Context ID (ASID 相当)。`PDTV=0` 時に TLB タグとして使用 (20 bit) |
| reserved   | [39:32] | —                                                            |
| RCID       | [51:40] | Resource Configuration ID (QoS 識別子、12 bit)               |
| MCID       | [63:52] | Monitoring Counter ID (QoS モニタリング用、12 bit)            |

### 3.4a DC.fsc / iosatp — First-Stage Context (64-bit, offset +24, PDTV=0)

```
 63       60 59             44 43                             0
 +----------+--------------+----------------------------------+
 |   MODE   |   reserved   |              PPN                 |
 |  (4 bit) |   (16 bit)   |            (44 bit)              |
 +----------+--------------+----------------------------------+
```

| MODE 値 | 名前   | 条件 (SXL=0) / (SXL=1) |
| :-----: | :----- | :---------------------- |
| 0       | Bare   | 第 1 ステージ変換なし      |
| 8       | Sv39 / Sv32 | SXL=0: Sv39 / SXL=1: Sv32 |
| 9       | Sv48   | SXL=0 のみ              |
| 10      | Sv57   | SXL=0 のみ              |

### 3.4b DC.fsc / pdtp — Process-Directory Table Pointer (64-bit, offset +24, PDTV=1)

```
 63       60 59             44 43                             0
 +----------+--------------+----------------------------------+
 |   MODE   |   reserved   |              PPN                 |
 |  (4 bit) |   (16 bit)   |            (44 bit)              |
 +----------+--------------+----------------------------------+
```

| MODE 値 | 名前  | 意味                                   |
| :-----: | :---- | :------------------------------------- |
| 0       | Bare  | 第 1 ステージ変換なし                    |
| 1       | PD8   | 1-level PDT、8-bit `process_id`         |
| 2       | PD17  | 2-level PDT、17-bit `process_id`        |
| 3       | PD20  | 3-level PDT、20-bit `process_id`        |

---

## 4. process_id (20-bit) — PDT Index Partitioning

```
 19     17 16              8 7               0
 +--------+-----------------+----------------+
 | PDI[2] |     PDI[1]      |    PDI[0]      |
 | (3 bit)|    (9 bit)      |    (8 bit)     |
 +--------+-----------------+----------------+
```

| フィールド | ビット範囲 | 幅    | 用途                                              |
| :--------- | :--------- | :---: | :------------------------------------------------ |
| PDI[0]     | [7:0]      | 8 bit | 末端 PDT ページ内インデックス (16B PC エントリ)    |
| PDI[1]     | [16:8]     | 9 bit | 中間 PDT ページインデックス                        |
| PDI[2]     | [19:17]    | 3 bit | ルート PDT インデックス (PD20 のみ使用、8 エントリ) |

モードと有効ビット: `PD8` → [19:8]=0 必須 / `PD17` → [19:17]=0 必須 / `PD20` → 全 20 bit 有効

---

## 5. Non-leaf PDT Entry (PDTE, 64-bit)

Non-leaf DDTE と同一レイアウト。

```
 63       54 53                    10  9        1  0
 +----------+----------------------+------------+--+
 | reserved |         PPN          |  reserved  | V|
 | (10 bit) |       (44 bit)       |  (9 bit)   |1b|
 +----------+----------------------+------------+--+
```

| フィールド | ビット  | 意味                                                       |
| :--------- | :------ | :--------------------------------------------------------- |
| V          | [0]     | Valid                                                      |
| reserved   | [9:1]   | 0 でなければ "PDT entry misconfigured" (cause=267)         |
| PPN        | [53:10] | 次レベル PDT ページ PPN (44 bit)                            |
| reserved   | [63:54] | 0 でなければ "PDT entry misconfigured" (cause=267)         |

---

## 6. Process Context (PC, 16 B = 2 × 64-bit doublewords)

```
 byte offset  0          8         15
              +----------+----------+
              |   ta      |   fsc    |
              | (64 bit)  | (64 bit) |
              +----------+----------+
```

バイトオーダーは `DC.tc.SBE` で決まる (LE or BE)。

### 6.1 PC.ta — Translation Attributes (64-bit, byte offset 0)

```
 63       32 31               12 11        3   2    1    0
 +----------+-------------------+----------+----+----+---+
 | reserved |       PSCID       | reserved | SUM|ENS | V |
 | (32 bit) |     (20 bit)      |  (9 bit) |    |    |   |
 +----------+-------------------+----------+----+----+---+
```

| フィールド | ビット  | 意味                                                                 |
| :--------- | :------ | :------------------------------------------------------------------- |
| V          | [0]     | Valid。0 なら "PDT entry not valid" (cause=266)                       |
| ENS        | [1]     | Enable Supervisor。supervisor 権限トランザクションを許可               |
| SUM        | [2]     | Supervisor User Memory access。`ENS=1` 時有効。0 = U-page アクセス禁止 |
| reserved   | [11:3]  | —                                                                    |
| PSCID      | [31:12] | Process Soft-Context ID。第 1 ステージ TLB タグとして使用 (20 bit)    |
| reserved   | [63:32] | —                                                                    |

### 6.2 PC.fsc — First-Stage Context (64-bit, byte offset 8)

`DC.fsc/iosatp` と同一レイアウト (§3.4a 参照)。

```
 63       60 59             44 43                             0
 +----------+--------------+----------------------------------+
 |   MODE   |   reserved   |              PPN                 |
 |  (4 bit) |   (16 bit)   |            (44 bit)              |
 +----------+--------------+----------------------------------+
```

---

## 7. Sv39 Virtual Address (VA, 64-bit)

```
 63              39 38         30 29         21 20         12 11             0
 +-----------------+------------+------------+------------+----------------+
 | sign-ext(bit38) |   VPN[2]   |   VPN[1]   |   VPN[0]   |   page offset  |
 |    (25 bit)     |   (9 bit)  |   (9 bit)  |   (9 bit)  |    (12 bit)    |
 +-----------------+------------+------------+------------+----------------+
```

| フィールド      | ビット  | 意味                                   |
| :-------------- | :------ | :------------------------------------- |
| page offset     | [11:0]  | ページ内オフセット (12 bit = 4 KiB)     |
| VPN[0]          | [20:12] | L1 ページテーブルインデックス (9 bit)   |
| VPN[1]          | [29:21] | L2 ページテーブルインデックス (9 bit)   |
| VPN[2]          | [38:30] | L3 ページテーブルインデックス (9 bit)   |
| sign-ext(bit38) | [63:39] | bit[38] の符号拡張。異なる値なら page-fault |

**スーパーページ:**
- 1 GiB: leaf PTE が VPN[2] レベル → VPN[1]+VPN[0] がオフセット扱い
- 2 MiB: leaf PTE が VPN[1] レベル → VPN[0] がオフセット扱い

---

## 8. Sv39 Physical Address (PA, 56-bit)

```
 55                  30 29         21 20         12 11             0
 +--------------------+------------+------------+----------------+
 |       PPN[2]       |   PPN[1]   |   PPN[0]   |   page offset  |
 |      (26 bit)      |   (9 bit)  |   (9 bit)  |    (12 bit)    |
 +--------------------+------------+------------+----------------+
```

| フィールド  | ビット  | 意味                              |
| :---------- | :------ | :-------------------------------- |
| page offset | [11:0]  | ページ内オフセット (12 bit)         |
| PPN[0]      | [20:12] | 物理ページ番号 [0] (9 bit)          |
| PPN[1]      | [29:21] | 物理ページ番号 [1] (9 bit)          |
| PPN[2]      | [55:30] | 物理ページ番号 [2] (26 bit)         |

最大物理アドレス空間: 2^56 = 64 PiB。`capabilities.PAS` で実装サポート幅を示す。

---

## 9. Sv39 PTE (Page Table Entry, 64-bit)

```
 63  62 61 60       54 53         28 27        19 18         10  9  8  7  6  5  4  3  2  1  0
 +--+----+----------+-------------+------------+------------+----+--+--+--+--+--+--+--+--+--+
 | N|PBMT| reserved |   PPN[2]    |   PPN[1]   |   PPN[0]   |RSW| D| A| G| U| X| W| R| V|
 |1b| 2b | (7 bit)  |  (26 bit)   |   (9 bit)  |   (9 bit)  | 2b|  |  |  |  |  |  |  |  |
 +--+----+----------+-------------+------------+------------+----+--+--+--+--+--+--+--+--+
```

| ビット   | フィールド | 意味                                                          |
| :------- | :--------- | :------------------------------------------------------------ |
| [0]      | V          | Valid。0 なら "instruction/load/store page fault"              |
| [1]      | R          | Read 許可                                                     |
| [2]      | W          | Write 許可 (R=0 かつ W=1 は reserved)                         |
| [3]      | X          | Execute 許可                                                  |
| [4]      | U          | User-mode アクセス許可                                         |
| [5]      | G          | Global マッピング (全 ASID に適用)                             |
| [6]      | A          | Accessed (ソフトウェア or ハードウェアが更新)                   |
| [7]      | D          | Dirty (書き込み時にハードウェアが更新)                          |
| [9:8]    | RSW        | Reserved for Software (OS が自由に使用可)                      |
| [18:10]  | PPN[0]     | 物理ページ番号 [0] (9 bit)                                     |
| [27:19]  | PPN[1]     | 物理ページ番号 [1] (9 bit)                                     |
| [53:28]  | PPN[2]     | 物理ページ番号 [2] (26 bit)                                    |
| [60:54]  | reserved   | 0 でなければ page-fault (`Svrsw60t59b` 有効時は SW 使用可)     |
| [62:61]  | PBMT       | Page-Based Memory Types (Svpbmt 拡張)                         |
| [63]     | N          | NAPOT 変換連続性 (Svnapot 拡張)                                |

**leaf / non-leaf 判定:** R=0, W=0, X=0 → non-leaf (PPN は次レベルポインタ)

**主要な権限組み合わせ:**

| R | W | X | 用途                       |
|:-:|:-:|:-:| :------------------------- |
| 0 | 0 | 0 | non-leaf (次レベルへのポインタ) |
| 1 | 0 | 0 | read-only data             |
| 1 | 1 | 0 | read-write data            |
| 0 | 0 | 1 | execute-only               |
| 1 | 0 | 1 | read + execute             |
| 1 | 1 | 1 | read + write + execute     |

---

## 10. capabilities Register (64-bit, RO)

### 10a. Lower Half [31:0]

```
 31  30 29:28  27  26  25  24  23     22      21  20  19   18   17   16  15     14    13:12  11  10  9   8   7:0
 +--+--+----+--+--+--+--+-------+-------+---+--+----+----+----+----+------+-------+-----+--+--+--+--+--------+
 |DB|HP| IGS|EN|T2|AT|AH|MSI_MRF|MSI_FLT|AOM|rs|S57x|S48x|S39x|S32x|Svpbmt|Svrsw60|     |S5|S4|S3|S3| version|
 |G |M |2bit|D |G |S |WD|       |       |RF |  | 4  | 4  | 4  | 4  |      |t59b   | rs  | 7| 8| 9| 2|  8 bit |
 +--+--+----+--+--+--+--+-------+-------+---+--+----+----+----+----+------+-------+-----+--+--+--+--+--------+
```

| ビット   | フィールド   | 意味                                                                     |
| :------- | :----------- | :----------------------------------------------------------------------- |
| [7:0]    | version      | 仕様バージョン (`0x10` = v1.0; 上位 4bit=major, 下位 4bit=minor)          |
| [8]      | Sv32         | S-stage Sv32 サポート                                                    |
| [9]      | Sv39         | S-stage Sv39 サポート                                                    |
| [10]     | Sv48         | S-stage Sv48 サポート (Sv39 も必須)                                       |
| [11]     | Sv57         | S-stage Sv57 サポート (Sv48 も必須)                                       |
| [13:12]  | reserved     | —                                                                        |
| [14]     | Svrsw60t59b  | PTE bits[60:59] を SW 用予約ビットとして使用可能                          |
| [15]     | Svpbmt       | Page-Based Memory Types (Svpbmt 拡張) サポート                           |
| [16]     | Sv32x4       | G-stage Sv32x4 サポート                                                  |
| [17]     | Sv39x4       | G-stage Sv39x4 サポート                                                  |
| [18]     | Sv48x4       | G-stage Sv48x4 サポート                                                  |
| [19]     | Sv57x4       | G-stage Sv57x4 サポート                                                  |
| [20]     | reserved     | —                                                                        |
| [21]     | AMO_MRIF     | MRIF へのアトミック更新サポート                                           |
| [22]     | MSI_FLAT     | MSI フラット変換サポート (DC が 64B 拡張形式に)                           |
| [23]     | MSI_MRIF     | MSI MRIF 変換サポート                                                    |
| [24]     | AMO_HWAD     | PTE A/D ビットのハードウェア自動更新サポート                               |
| [25]     | ATS          | PCIe ATS / PRI サポート                                                  |
| [26]     | T2GPA        | ATS 応答で GPA を返す (T2GPA) サポート                                    |
| [27]     | END          | 両エンディアンサポート (0 = 片方のみ)                                     |
| [29:28]  | IGS          | 割り込み生成方式: `0`=MSI only, `1`=WSI only, `2`=BOTH                   |
| [30]     | HPM          | Hardware Performance Monitor サポート                                    |
| [31]     | DBG          | デバッグ変換インターフェース (`tr_req`/`tr_response`) サポート             |

### 10b. Upper Half [63:32]

```
 63       56 55       44 43   42    41    40    39    38  37       32
 +----------+----------+--+------+-----+-----+-----+-----+----------+
 |  custom  | reserved | S|  NL  |QOSID| PD20| PD17|  PD8|   PAS    |
 |  (8 bit) | (12 bit) |  |      |     |     |     |     |  (6 bit) |
 +----------+----------+--+------+-----+-----+-----+-----+----------+
```

| ビット   | フィールド | 意味                                                              |
| :------- | :--------- | :---------------------------------------------------------------- |
| [37:32]  | PAS        | Physical Address Size。実装がサポートする物理アドレス幅 (bit 数)   |
| [38]     | PD8        | 1-level PDT、8-bit `process_id` サポート                          |
| [39]     | PD17       | 2-level PDT、17-bit `process_id` サポート                         |
| [40]     | PD20       | 3-level PDT、20-bit `process_id` サポート                         |
| [41]     | QOSID      | QoS ID (RCID/MCID) アソシエーションサポート                        |
| [42]     | NL         | Non-leaf PTE 無効化拡張サポート                                    |
| [43]     | S          | アドレス範囲無効化拡張サポート                                     |
| [55:44]  | reserved   | —                                                                 |
| [63:56]  | custom     | カスタム拡張用                                                     |

---

## 11. fctl — Features Control Register (32-bit)

```
 31              16 15          3   2    1    0
 +-----------------+------------+----+----+----+
 |     custom      |  reserved  | GXL| WSI| BE |
 |    (16 bit)     |  (13 bit)  |    |    |    |
 +-----------------+------------+----+----+----+
```

| ビット   | フィールド | Attr | 意味                                                                       |
| :------- | :--------- | :--- | :------------------------------------------------------------------------- |
| [0]      | BE         | WARL | Big-Endian。1 = データ構造アクセスをビッグエンディアンで行う                |
| [1]      | WSI        | WARL | Wire-Signaled Interrupt。1 = ワイヤ割り込み、0 = MSI (`IGS=BOTH` 時のみ切替可) |
| [2]      | GXL        | WARL | G-stage Extra Level。G-stage ページングモードの選択範囲を制御               |
| [15:3]   | reserved   | WPRI | —                                                                          |
| [31:16]  | custom     | WPRI | カスタム拡張用                                                              |

**WSI 書き込み可能条件:**
- `IGS=WSI` → WSI=1 のみ設定可 (WSI=0 は NG)
- `IGS=MSI` → WSI=0 のみ設定可 (WSI=1 は NG)
- `IGS=BOTH` → 0/1 どちらも設定可

**注:** `fctl.BE` は本実装で 0 固定 (RTL: `capabilities.END=0` のため)。`fctl` への書き込みは IOMMU が Off の時のみ安全。

---

## 12. ddtp — Device Directory Table Pointer (64-bit)

```
 63       54 53                    10  9        5   4   3        0
 +----------+----------------------+------------+---+--+-----------+
 | reserved |         PPN          |  reserved  |rs |By| iommu_mode|
 | (10 bit) |       (44 bit)       |  (5 bit)   |   |1b|  (4 bit)  |
 +----------+----------------------+------------+---+--+-----------+
```
*(By = busy)*

| フィールド  | ビット  | Attr | 意味                                                                              |
| :---------- | :------ | :--- | :-------------------------------------------------------------------------------- |
| iommu_mode  | [3:0]   | WARL | 動作モード (下表参照)                                                              |
| busy        | [4]     | RO   | `iommu_mode` 変更後の完了待ちフラグ。1 の間は再書き込み結果 UNSPECIFIED            |
| reserved    | [9:5]   | WPRI | —                                                                                 |
| PPN         | [53:10] | WARL | DDT ルートページの PPN (44 bit)。`Bare`/`Off` 時は don't care                     |
| reserved    | [63:54] | WPRI | —                                                                                 |

**`iommu_mode` エンコーディング:**

| 値   | 名前   | 意味                                         |
| :--: | :----- | :------------------------------------------- |
| 0    | Off    | 全インバウンドトランザクション拒否             |
| 1    | Bare   | 変換・保護なし。Untranslated request のみ通過 |
| 2    | 1LVL   | 1-level DDT                                  |
| 3    | 2LVL   | 2-level DDT                                  |
| 4    | 3LVL   | 3-level DDT                                  |
| 5-13 | —      | reserved                                     |
| 14-15| —      | custom                                        |

**注意事項:**
- `iommu_mode > 4` への書き込みはサイレントドロップ (RTL: `rv_iommu_regmap.sv` BR08)。
- 64-bit レジスタへの 2 回の 32-bit アクセスは **Low(offset 0x10) → High(offset 0x014)** の順で両方書き込まれるまで commit されない (2-half ステージングプロトコル)。
- `busy=1` の間は `in_flight_i=1` が保持され commit が遅延する。
- `iommu_mode` を `1LVL`/`2LVL`/`3LVL` に変更する場合、事前に `Bare` か `Off` に遷移させてから変更する必要がある。
