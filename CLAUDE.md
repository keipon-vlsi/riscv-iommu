# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SystemVerilog RTL implementation of a RISC-V IOMMU (Input/Output Memory Management Unit) compliant with [RISC-V IOMMU Specification v1.0](https://github.com/riscv-non-isa/riscv-iommu). The IOMMU performs DMA permission checks, address translation (virtual→physical), and interrupt remapping for I/O devices.

**Goal of this project**: Create testbenches for each module and fix bugs discovered during verification.

---

## Working Rules (Read Before Answering)

Claude **must** follow these rules for every RTL-related question:

1. **Never guess about RTL behavior.** Always read the actual source file (`rtl/**/*.sv`) and cite `file:line` for claims.
2. **Prefer existing doc over spec.** Check `doc/modules/<module>.md` first; fall back to RTL and then to specs.
3. **Cite spec sections.** When referring to protocol behavior, cite the specific chapter file under `doc/spec/`. Use the "Specification navigation" table below to find the right file.
4. **Flag discrepancies.** If the RTL contradicts the spec, explicitly say so (don't silently pick one side).
5. **Mark uncertainty.** Use `**推測:**` or `**要検証:**` prefix when inference is unavoidable.
6. **Record design decisions.** When non-trivial choices are made (bug fixes, design tweaks), append to `doc/design-log.md`.
7. **Preserve TB conventions.** New testbench code must reuse `ptw_helpers.py`, `tb_zdl_ptw.py`, and the Force-based wrapper pattern (see TB section below).
8. **Test plan の Status 列のみの自動更新** は内容変更とみなさない:
   - frontmatter の `reviewed` はそのまま
   - `last_modified_by_claude` は変更しない
   - `last_status_update` のみ更新

---

## Documentation Index

Read these first when onboarding into a task:

| ドキュメント | 内容 | 優先度 |
|---|---|---|
| `CLAUDE.md` (this file) | プロジェクト全体のナビと作業ルール | 必読 |
| `doc/ARCHITECTURE.md` | モジュール階層・信号接続の全体像 | 高 |
| `doc/modules/<module>.md` | 各モジュールの 1-pager (I/O, FSM, 接続先) | モジュール作業時に必読 |
| `doc/tb-infrastructure.md` | 既存 TB 基盤 (MockMem, PteFactory 等) の使い方 | TB 作業時に必読 |
| `doc/test-plan.md` | モジュール別テスト計画 (網羅状況) | TB 作業時 |
| `doc/design-log.md` | 自プロジェクトの設計判断・バグ修正履歴 | 変更時に追記 |
| `doc/connectivity/` | 信号接続マップ (上位・下位・横接続) | 必要時 |

**作成状況**: `doc/` 配下のファイルは段階的に追加する方針。まだ未作成のファイルは、必要になった時に該当モジュールの RTL を読んで生成してよい (生成前にユーザに確認)。

---

## Specification Navigation

仕様書は `doc/spec/` 以下に **章ごとに Markdown 分割済み**。質問に答える際、以下の対応表から該当ファイルを必ず参照すること。**章ファイル名は実ファイルに一致する正式名称で記載**。

---

### RISC-V IOMMU Specification (`doc/spec/riscv-iommu/`)

索引: `doc/spec/riscv-iommu/README.md` (全 13 章)

| トピック | 参照ファイル |
|---|---|
| 全体アーキテクチャ / IOMMU の位置づけ | `05-chapter-2.-introduction.md` |
| **DC / PC / DDT / PDT のレイアウト** | `06-chapter-3.-data-structures.md` |
| **2 段アドレス変換 (IOVA → GPA → SPA)** | 同上 (§3.3 付近) |
| PTE の A/D ビット更新仕様 | 同上 (§3.4) |
| **ATS / Translated Request / T2GPA** | 同上 (§3.6) |
| **MSI 変換 / MRIF** | 同上 (§3.1.3.5 msiptp, §3.1.3.6 msi_addr_mask 付近) |
| Memory-mapped データ構造のキャッシュ | 同上 (§3.8) |
| **Command Queue / Fault Queue / Page-Request Queue** | `07-chapter-4.-in-memory-queue-interface.md` |
| Cause code 一覧 | 同上 (Fault Queue エントリ定義内) |
| デバッグ変換 (req_dbg_i 関連) | `08-chapter-5.-debug-support.md` |
| **レジスタ定義 (capabilities / fctl / ddtp / cqcsr / fqcsr 等)** | `09-chapter-6.-memory-mapped-register-interface.md` |
| **ソフトウェア側の使い方 (無効化コマンド順序など)** | `10-chapter-7.-software-guidelines.md` |
| ハードウェア実装ガイドライン | `11-chapter-8.-hardware-guidelines.md` |
| IOMMU 拡張 | `12-chapter-9.-iommu-extensions.md` |

---

### RISC-V Privileged ISA (`doc/spec/riscv-privileged/`)

索引: `doc/spec/riscv-privileged/README.md` (全 30 章)

| トピック | 参照ファイル |
|---|---|
| 特権レベル (M/S/U/VS) 総論 | `03-chapter-1.-introduction.md` |
| CSR アクセス機構一般 | `04-chapter-2.-control-and-status-registers-csrs.md` |
| **Machine-Level ISA、PMA / PMP** | `05-chapter-3.-machine-level-isa-version-1.13.md` |
| PMP 拡張 (Smepmp) | `08-chapter-6.-smepmp-extension-for-pmp-enhancements-for-memory.md` |
| **Supervisor-Level ISA (Sv39 PTE, R/W/X/U/A/D, SUM/MXR)** | `14-chapter-12.-supervisor-level-isa-version-1.13.md` |
| NAPOT ページ (Svnapot) | `15-chapter-13.-svnapot-extension-for-napot-translation-contigui.md` |
| Page-Based Memory Types (Svpbmt) | `16-chapter-14.-svpbmt-extension-for-page-based-memory-types-ver.md` |
| **SFENCE.VMA / HFENCE 系の無効化 (Svinval)** | `17-chapter-15.-svinval-extension-for-fine-grained-address-trans.md` |
| **ハードウェア A/D ビット更新 (Svadu)** | `18-chapter-16.-svadu-extension-for-hardware-updating-of-ad-bits.md` |
| PTE Valid ビット変更後のフェンス省略 (Svvptc) | `19-chapter-17.-svvptc-extension-for-obviating-memory-management.md` |
| **Hypervisor Extension、VS-mode、G-stage (Sv39x4)** | `24-chapter-22.-h-extension-for-hypervisor-support-version-1.0.md` |
| 全命令一覧 | `28-chapter-26.-risc-v-privileged-instruction-set-listings.md` |

**太字** のトピックは IOMMU 実装でよく参照するので優先。特に `14-chapter-12` (Sv39 PTE 仕様) と `24-chapter-22` (H 拡張・G-stage) は必読。

---

### AMBA AXI Protocol (`doc/spec/IHI0022L_amba_axi_protocol_spec/`)

索引: `doc/spec/IHI0022L_amba_axi_protocol_spec/README.md` (全 19 章、Part A/B)

| トピック | 参照ファイル |
|---|---|
| AXI アーキテクチャ概要 | `01-chapter-a1-introduction.md` |
| **Valid-Ready ハンドシェイク (AR/R/AW/W/B)** | `02-chapter-a2-axi-transport.md` |
| **Burst 転送 (INCR/WRAP/FIXED)、AxLEN/AxSIZE** | `03-chapter-a3-axi-transactions.md` |
| **RRESP / BRESP (OKAY/EXOKAY/SLVERR/DECERR)** | 同上 (§A3.3 Transaction response) |
| Narrow / Unaligned 転送 | 同上 (§A3.2) |
| Memory attributes (Cache, Device/Normal) | `04-chapter-a4.md` |
| QoS signaling | 同上 (§A4.8) |
| **Transaction ID / 順序保証** | `05-chapter-a5.md` |
| **Atomic access / Exclusive** | `06-chapter-a6-atomic-accesses.md` |
| Opcodes (AxSNOOP 等) | `07-chapter-a7-request-opcodes.md` |
| Caching / Coherency (ACE 系) | `08-chapter-a8.md` |
| Cache Maintenance Operations (CMO) | `09-chapter-a9.md` |
| NSAID / PBHA / ACT 等の追加属性 | `10-chapter-a10.md` |
| WriteZero / WriteDeferrable | `11-chapter-a11.md` |
| MPAM / MTE / Trace / User 信号 | `12-chapter-a12.md` |
| **Untranslated Transaction (SMMU/PCIe 連携)** | `13-chapter-a13.md` |
| Clock / Power gating | `14-chapter-a14-interface-clock-and-power-gating.md` |
| DVM messages (TLB invalidation 等) | `15-chapter-a15.md` |
| **全信号リファレンス (AR*, R*, AW*, W*, B*)** | `16-chapter-b1-signal-list.md` |
| Interface class (AXI5 / ACE5-Lite 等) | `17-chapter-b2.md` |
| Issue 間の差分 (H.c / J / K / L) | `18-chapter-b4-revisions.md` |

**太字** のトピックは IOMMU の実装で頻出するので、関連質問時は迷わず該当ファイルを参照すること。

---

## Commands

### Linting (from repo root)

```bash
make          # Run Verilator lint checks (default target)
make lint     # Explicit lint target
make lint2log # Lint with output to verilator.log
```

Requires Verilator 5.022.

### Running PTW Tests (from `tb_coco/translation_logic/ptw/`)

```bash
make          # Run all scenario/test_*.py tests via cocotb
make sim-log  # Run simulation and save output to sim.log
make clean    # Remove build artifacts, dump.vcd, sim.log
```

Test scenarios are auto-discovered from `scenario/test_*.py`. Waveforms go to `dump.vcd`.

---

## Architecture

### Top-Level Module

`rtl/riscv_iommu.sv` — IOMMU top module with four AXI ports:

1. **Translation Request (Slave)** — DMA device requests (uses `MMUSID`/`MMUSSID` for device/process ID)
2. **Translation Completion (Master)** — Translated requests forwarded to interconnect
3. **Data Structures (Master)** — Implicit memory accesses for PTW, CDW, FQ, CQ
4. **Programming (Slave)** — AXI4-Lite register interface

### Three Functional Groups

**Translation Logic** (`rtl/translation_logic/`):
- **PTW** (`ptw/`): Walks page tables in memory for address translation
  - `rv_iommu_ptw_sv39x4.sv` — Sv39/Sv39x4 first-stage translation
  - `rv_iommu_ptw_sv39x4_pc.sv` — Adds Process Context support
- **CDW** (`cdw/`): Fetches Device Contexts (`rv_iommu_cdw.sv`) and Process Contexts (`rv_iommu_cdw_pc.sv`) from memory
- **Caches** (`cache/`): Fully-associative — IOTLB, DDTC, PDTC, MRIFC
- **MSI Translation** (`msi/`): MSI Page Table Walker and MRIF handler
- **Wrapper** (`wrapper/rv_iommu_translation_wrapper.sv`): Orchestrates all translation components

**Software Interface** (`rtl/software_interface/`):
- `regmap/rv_iommu_regmap.sv` — Memory-mapped configuration registers
- `rv_iommu_cq_handler.sv` / `rv_iommu_fq_handler.sv` — Command/Fault queue handlers
- `rv_iommu_wsi_ig.sv` / `rv_iommu_msi_ig.sv` — Interrupt generation (Wire Signal / Message Signaled)
- `rv_iommu_hpm.sv` — Hardware Performance Monitor (up to 31 event counters)

**External Interfaces** (`rtl/ext_interfaces/`):
- `rv_iommu_prog_if.sv` — AXI4-Lite slave for register access
- `rv_iommu_ds_if.sv` — AXI4 master for data structure memory accesses
- `rv_iommu_axi4_bc.sv` — 4-KiB AXI boundary checker
- `rv_iommu_ign_slv.sv` — AXI error slave for failed translations

### Package Files

- `packages/rv_iommu/rv_iommu_pkg.sv` — IOMMU-specific types, enums, structs
- `packages/rv_iommu/rv_iommu_reg_pkg.sv` — Register field type definitions
- `packages/dependencies/` — RISC-V (`riscv_pkg.sv`), AXI (`axi_pkg.sv`), and CVA6 config packages

### Key Parameters

| Parameter | Purpose |
|-----------|---------|
| `InclPC` | Enable Process Context support |
| `MSITrans` | MSI translation: `MSI_DISABLED`, `MSI_FLAT_ONLY`, `MSI_FLAT_MRIF` |
| `IGS` | Interrupt generation: `WSI_ONLY`, `MSI_ONLY`, `BOTH` |
| `InclBC` | Enable AXI 4-KiB boundary check |
| `InclDBG` | Enable debug register interface |
| `N_IOHPMCTR` | Number of HPM event counters (0–31) |
| `*_ENTRIES` | Cache sizes for IOTLB, DDTC, PDTC, MRIFC |

Lint configuration uses `lint_checks.sv` in the repo root and instantiates the top module with representative parameters.

---

## Two-Stage Address Translation

The IOMMU supports nested (hypervisor) virtualization:

- **Stage 1**: Guest Virtual Address → Guest Physical Address (using guest OS page tables)
- **Stage 2**: Guest Physical Address → Supervisor Physical Address (using hypervisor page tables)

Both stages use Sv39x4 (39-bit VA extended to 4× for guest physical space). Superpages (1 GiB, 2 MiB) are supported.

---

## Testbench (Cocotb)

`tb_coco/translation_logic/ptw/` is the active testbench. The older `tb/` directory has been deprecated.

### Current Files (PTW single-module)

- `test_ptw.py` — Main cocotb test entry, discovers and runs all scenarios
- `ptw_helpers.py` — `PteFactory` (build PTEs), `PTWTester` (drive/check DUT signals)
- `tb_zdl_ptw.py` — Physical memory manager (`PhysicalMemoryManager`) and address helpers
- `scenario/test_*.py` — Individual test scenarios (auto-discovered)
- `tb_ptw_wrapper.sv` — SystemVerilog wrapper around the PTW DUT for cocotb

When adding test scenarios, place new files in `scenario/test_*.py` — they are auto-discovered.

### Extended Test Strategy (tw_sv39x4_pc 単位)

Permission checks (W/X/U/SUM の組合せ) are implemented at the IOTLB-hit path in the wrapper, so PTW-alone tests are insufficient. Use the **Force-based test wrapper** approach:

- `rv_iommu_ptw_test_wrapper.sv` instantiates `rv_iommu_tw_sv39x4_pc` and exposes `force_*` inputs that drive the PTW submodule's `init_ptw_i` / `iosatp_ppn_i` / `iohgatp_ppn_i` / `en_1S_i` / `en_2S_i` via `force/release`.
- DDTC/PDTC/CDW stay idle (they are skipped, not verified by these tests).
- Goal: exercise PTW walk, IOTLB update, and the wrapper's permission-check path without needing to populate DDT/PDT in memory.

Dependencies: PTW-standalone tests remain valid for walk mechanics. CDW/DDTC/PDTC will need their own unit tests.

### Guidelines for New Tests

- Reuse `MockMem` / `PhysicalMemoryManager` / `PteFactory` (do not reinvent).
- Follow the faulty-walk injection pattern in `scenario/test_nested_*.py` when targeting fault detection.
- Permission-check coverage requires driving both `trans_type_i` (R/W/RX) and the cached PTE bits.
- When modifying the DUT wrapper, update `doc/modules/<module>.md` and `doc/test-plan.md`.

---

## Using Claude Code Effectively

### Recommended commands and flows

- **Exploring an unknown module**:
  > `rtl/<path>/<module>.sv` を読んで `doc/_template/module_card.md` の形式で `doc/modules/<module>.md` を作成して。推測禁止、file:line 引用必須。

- **Spec lookup**:
  > `doc/spec/riscv-iommu/` の該当章を引いて、`<topic>` の挙動を説明して。引用時はファイル名 + セクション番号を明記。

- **Creating a testbench**:
  > `/create-tb <module>` (see `.claude/commands/create-tb.md`)

- **Investigating a bug**:
  > `rtl/<file>.sv` の `<signal>` 駆動箇所を grep で全部洗い出し、それぞれを仕様と突き合わせて評価して。矛盾があれば file:line で指摘。

### Context Management

- モジュール 1 個に集中するセッションでは、他モジュールの doc は読み込まなくてよい
- セッションが長くなったら `/clear` して CLAUDE.md + 必要 doc だけ再ロード
- 重要な発見は `doc/design-log.md` に即座に追記 (session が切れても失われない)

---

## Known Project State / Caveats

- Permission checks for leaf PTE have been moved from PTW to IOTLB/wrapper path. Verify against `rtl/translation_logic/wrapper/` when investigating related bugs.
- `req_trans_i` must be held High until translation completes (`trans_valid_o` or `trans_error_o`). Lowering it mid-walk will clear IOTLB hit signals.
- `t2gpa=1` (ATS completion returns GPA) may not be fully implemented — verify before relying on it.
- Check `doc/design-log.md` for ongoing modifications made by this project.