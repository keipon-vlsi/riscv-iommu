# Chapter 12. Supervisor-Level ISA, Version 1.13

This chapter describes the RISC-V supervisor-level architecture, which contains a common core that is used with various supervisor-level address translation and protection schemes.

> **Note**: Supervisor mode is deliberately restricted in terms of interactions with underlying physical hardware, such as physical memory and device interrupts, to support clean virtualization. In this spirit, certain supervisor-level facilities, including requests for timer and interprocessor interrupts, are provided by implementation-specific mechanisms. In some systems, a supervisor execution environment (SEE) provides these facilities in a manner specified by a supervisor binary interface (SBI). Other systems supply these facilities directly, through some other implementation-defined mechanism.

---

## 12.1. Supervisor CSRs

### 12.1.1. Supervisor Status (`sstatus`) Register

`sstatus` is an SXLEN-bit read/write register. It is a **subset of `mstatus`**: in a straightforward implementation, reading or writing any field in `sstatus` is equivalent to reading or writing the homonymous field in `mstatus`.

#### Figure 49. `sstatus` when SXLEN=32

| Bits      | Field    |
| :-------- | :------- |
| **31**    | SD       |
| **30:25** | WPRI     |
| **24**    | SDT      |
| **23**    | SPELP    |
| **22:20** | WPRI     |
| **19**    | MXR      |
| **18**    | SUM      |
| **17**    | WPRI     |
| **16:15** | XS[1:0]  |
| **14:13** | FS[1:0]  |
| **12:10** | WPRI     |
| **9:8**   | VS[1:0]  |
| **8**     | SPP      |
| **7:6**   | WPRI     |
| **6**     | UBE      |
| **5**     | SPIE     |
| **4:2**   | WPRI     |
| **1**     | SIE      |
| **0**     | WPRI     |

(Layout note: Figure 49 in the spec packs these in two 16-bit halves; this table flattens them to bit-position order. SPP is at bit 8 and is a single bit. Some adjacent WPRI fields overlap notations in the spec figure; consult the prose below for definitive semantics.)

#### Figure 50. `sstatus` when SXLEN=64

Identical to Figure 49 for bits `31:0`, plus:

| Bits      | Field    |
| :-------- | :------- |
| **63**    | SD       |
| **62:34** | WPRI     |
| **33:32** | UXL[1:0] |

#### Field meanings (relevant to S-mode and supervisor address translation)

- **SPP** (bit 8): Supervisor Previous Privilege. Set by the hardware when a trap is taken into S-mode: 0 if the trap originated from user mode, 1 otherwise. On `SRET`, the privilege level is set to user (SPP=0) or supervisor (SPP=1), and SPP is then cleared to 0.
- **SIE** (bit 1): Supervisor Interrupt Enable. When clear, S-mode interrupts are masked. Ignored in U-mode (S-level interrupts are always enabled in U-mode).
- **SPIE** (bit 5): Supervisor Previous Interrupt Enable. When a trap is taken into S-mode, `SPIE := SIE` and `SIE := 0`. When `SRET` is executed, `SIE := SPIE` and `SPIE := 1`.
- **MXR** (bit 19): Make eXecutable Readable. Modifies how loads access virtual memory.
  - `MXR == 0`: only loads from pages with `R=1` succeed.
  - `MXR == 1`: loads from pages with `R=1 OR X=1` succeed.
  - No effect when paged virtual memory is not in effect.
- **SUM** (bit 18): permit Supervisor User Memory access. Modifies the privilege of S-mode loads/stores.
  - `SUM == 0`: S-mode access to a page with `U=1` faults.
  - `SUM == 1`: such accesses are permitted.
  - SUM has no effect when paged VM is not in effect, nor for U-mode execution. **S-mode can never execute instructions from user pages, regardless of SUM.**
  - SUM is read-only 0 if `satp.MODE` is read-only 0.
- **UBE** (bit 6, WARL): U-mode endianness for explicit accesses (0 = LE, 1 = BE). No effect on instruction fetches (always LE). No effect on implicit S-level page-table accesses (S-mode endianness applies).
- **UXL** (bits 33:32, WARL, only when SXLEN=64): controls XLEN for U-mode. Encoding same as `misa.MXL`.
- **SDT** (bit 24, WARL): S-mode-disable-trap (Ssdbltrp extension). When set to 1 by an explicit CSR write, `SIE` is cleared to 0. When a trap is taken into S-mode and `SDT` is already 1, a double-trap is delivered to M-mode. `SRET` sets `SDT` to 0.
- **SPELP** (bit 23): Previous Expected Landing Pad state (Zicfilp extension). Accesses `mstatus.SPELP` when V=0, `vsstatus.SPELP` when V=1.
- **FS, VS, XS** (2-bit fields): floating-point / vector / additional context status. SD = OR of FS, VS, XS dirty.

### 12.1.2. Supervisor Trap Vector Base Address (`stvec`) Register

`stvec` is an SXLEN-bit read/write register holding trap vector configuration.

#### Figure 51. `stvec` register

| Bits           | Field             |
| :------------- | :---------------- |
| **SXLEN-1:2**  | BASE[SXLEN-1:2]   |
| **1:0**        | MODE              |

`BASE` must be 4-byte aligned (the low two bits are not stored — implicit zeros). Vectored mode may impose stricter alignment.

**Table 36. `stvec` MODE field encoding**

| Value | Name      | Description                                                  |
| :---: | :-------- | :----------------------------------------------------------- |
| 0     | Direct    | All exceptions set `pc = BASE`.                              |
| 1     | Vectored  | Synchronous exceptions: `pc = BASE`. Asynchronous interrupts: `pc = BASE + 4 × cause`. |
| ≥ 2   | —         | Reserved.                                                    |

### 12.1.3. Supervisor Interrupt Registers (`sip`, `sie`)

`sip` and `sie` are SXLEN-bit RW registers. Each interrupt cause `i` corresponds to bit `i` in both registers. Bits `[15:0]` are allocated to standard interrupt causes; bits `[16+]` are platform-specific.

An interrupt `i` traps into S-mode iff:
- (current mode is S **AND** `sstatus.SIE == 1`) **OR** (current mode < S);  **AND**
- `sip[i] == 1` **AND** `sie[i] == 1`.

#### Figure 54. Standard portion (bits 15:0) of `sip`

| Bits     | Field    |
| :------- | :------- |
| **15:14**| 0        |
| **13**   | LCOFIP   |
| **12:10**| 0        |
| **9**    | SEIP     |
| **8:6**  | 0        |
| **5**    | STIP     |
| **4:2**  | 0        |
| **1**    | SSIP     |
| **0**    | 0        |

#### Figure 55. Standard portion (bits 15:0) of `sie`

| Bits     | Field    |
| :------- | :------- |
| **15:14**| 0        |
| **13**   | LCOFIE   |
| **12:10**| 0        |
| **9**    | SEIE     |
| **8:6**  | 0        |
| **5**    | STIE     |
| **4:2**  | 0        |
| **1**    | SSIE     |
| **0**    | 0        |

Standard interrupt-cause-to-bit mapping (used as bit index `i`):

| Cause | Name                              | Pending bit | Enable bit |
| :---: | :-------------------------------- | :---------- | :--------- |
| 1     | Supervisor software interrupt     | `SSIP`      | `SSIE`     |
| 5     | Supervisor timer interrupt        | `STIP`      | `STIE`     |
| 9     | Supervisor external interrupt     | `SEIP`      | `SEIE`     |
| 13    | Counter-overflow interrupt (Sscofpmf) | `LCOFIP` | `LCOFIE`   |

**Priority** (when multiple S-mode interrupts pend simultaneously): SEI > SSI > STI > LCOFI.

### 12.1.4. Supervisor Timers and Performance Counters

Supervisor software uses `time`, `cycle`, `instret` CSRs (same as user-mode HPM facility). Timer interrupts are scheduled via writes to the real-time `time` counter (or via `stimecmp` if Sstc is implemented; see §12.1.12).

### 12.1.5. Counter-Enable (`scounteren`) Register

#### Figure 56. `scounteren`

| Bits     | Field    |
| :------- | :------- |
| **31**   | HPM31    |
| **30**   | HPM30    |
| **29**   | HPM29    |
| **28:6** | HPM28..HPM5 |
| **5**    | HPM5     |
| **4**    | HPM4     |
| **3**    | HPM3     |
| **2**    | IR       |
| **1**    | TM       |
| **0**    | CY       |

When a bit is clear, U-mode access to the corresponding counter raises an illegal-instruction exception. U-mode access requires the bit to be set in **both** `scounteren` AND `mcounteren`.

### 12.1.6. Supervisor Scratch (`sscratch`) Register

SXLEN-bit RW. Holds a hart-local supervisor-context pointer; typically swapped with an integer register at trap-handler entry via `CSRRW` to obtain a working register.

### 12.1.7. Supervisor Exception PC (`sepc`) Register

SXLEN-bit WARL. Bit 0 is always 0; bit 1 is also 0 when only IALIGN=32 is supported. Written with the virtual address of the instruction that was interrupted or excepted when a trap is taken into S-mode.

### 12.1.8. Supervisor Cause (`scause`) Register

#### Figure 59. `scause`

| Bits           | Field         |
| :------------- | :------------ |
| **SXLEN-1**    | Interrupt     |
| **SXLEN-2:0**  | Exception Code (WLRL) |

`Interrupt` bit is 1 if the trap was caused by an interrupt. Exception Code identifies the cause. Bits 4:0 must be implemented (must hold values 0–31).

**Table 37 (Interrupts, `Interrupt = 1`). Supervisor cause values**

| Exception Code | Description                       |
| -------------: | :-------------------------------- |
| 0              | Reserved                          |
| 1              | Supervisor software interrupt     |
| 2-4            | Reserved                          |
| 5              | Supervisor timer interrupt        |
| 6-8            | Reserved                          |
| 9              | Supervisor external interrupt     |
| 10-12          | Reserved                          |
| 13             | Counter-overflow interrupt        |
| 14-15          | Reserved                          |
| ≥ 16           | Designated for platform use       |

**Table 37 (Exceptions, `Interrupt = 0`). Supervisor cause values**

| Exception Code | Description                       |
| -------------: | :-------------------------------- |
| 0              | Instruction address misaligned    |
| 1              | Instruction access fault          |
| 2              | Illegal instruction               |
| 3              | Breakpoint                        |
| 4              | Load address misaligned           |
| **5**          | **Load access fault**             |
| 6              | Store/AMO address misaligned      |
| **7**          | **Store/AMO access fault**        |
| 8              | Environment call from U-mode      |
| 9              | Environment call from S-mode      |
| 10-11          | Reserved                          |
| **12**         | **Instruction page fault**        |
| **13**         | **Load page fault**               |
| 14             | Reserved                          |
| **15**         | **Store/AMO page fault**          |
| 16-17          | Reserved                          |
| 18             | Software check                    |
| 19             | Hardware error                    |
| 20-23          | Reserved                          |
| 24-31          | Designated for custom use         |
| 32-47          | Reserved                          |
| 48-63          | Designated for custom use         |
| ≥ 64           | Reserved                          |

(Bold codes are the same exception causes used by the IOMMU fault queue, see riscv-iommu spec §4.2 Table 13.)

### 12.1.9. Supervisor Trap Value (`stval`) Register

SXLEN-bit RW. On a trap into S-mode, written with exception-specific information per the rules below.

#### Figure 60. `stval`

| Bits          | Field   |
| :------------ | :------ |
| **SXLEN-1:0** | stval   |

Setting rules:

| Exception                                                  | `stval` value |
| :--------------------------------------------------------- | :------------ |
| Breakpoint (non-zero), addr-misaligned, access-fault, page-fault, hardware-error on instruction fetch / load / store | Faulting virtual address |
| Misaligned load/store causing access/page/HW fault        | VA of the portion that caused the fault |
| Variable-length instr access fault, page fault, HW error  | VA of the portion that caused the fault; `sepc` points to the start of the instruction |
| Illegal-instruction (optional)                            | Faulting instruction bits, right-justified, upper bits zero. Length = min(actual, ILEN, SXLEN) |
| Software-check exception                                  | 0 = no info, 2 = Landing Pad Fault (Zicfilp), 3 = Shadow Stack Fault (Zicfiss) |
| Other traps                                               | 0 (may be redefined by future standards) |
| EBREAK / C.EBREAK                                         | 0 OR VA of the instruction (implementation-defined) |

### 12.1.10. Supervisor Environment Configuration (`senvcfg`) Register

#### Figure 61. `senvcfg` for RV64

| Bits      | Field    |
| :-------- | :------- |
| **63:34** | WPRI     |
| **33:32** | PMM      |
| **31:8**  | WPRI     |
| **7**     | CBZE     |
| **6**     | CBCFE    |
| **5:4**   | CBIE     |
| **3**     | SSE      |
| **2**     | LPE      |
| **1**     | WPRI     |
| **0**     | FIOM     |

#### Figure 62. `senvcfg` for RV32

| Bits      | Field    |
| :-------- | :------- |
| **31:8**  | WPRI     |
| **7**     | CBZE     |
| **6**     | CBCFE    |
| **5:4**   | CBIE     |
| **3**     | SSE      |
| **2**     | LPE      |
| **1**     | WPRI     |
| **0**     | FIOM     |

- **FIOM** (bit 0): Fence of I/O implies Memory. When 1, U-mode FENCE / atomic with `aq`/`rl` accessing device I/O also orders main memory.
- **CBZE / CBCFE / CBIE**: Zicboz / Zicbom enables for U-mode cache-block instructions.
- **PMM** (bits 33:32, RV64 + Ssnpm): Pointer masking enable for U/VU (see Table 39).
- **LPE / SSE**: Zicfilp / Zicfiss enables for U/VU.

**Table 38. FENCE PI/PO/SI/SO when FIOM=1 (U-mode)**

| Instruction bit | Meaning when set                                              |
| :-------------- | :------------------------------------------------------------ |
| PI              | Predecessor device input AND memory reads (PR implied)        |
| PO              | Predecessor device output AND memory writes (PW implied)      |
| SI              | Successor device input AND memory reads (SR implied)          |
| SO              | Successor device output AND memory writes (SW implied)        |

**Table 39. Legal values of `PMM`**

| Value | Description                                       |
| :---: | :------------------------------------------------ |
| 00    | Pointer masking disabled (PMLEN = 0)              |
| 01    | Reserved                                          |
| 10    | PMLEN = XLEN − 57 (PMLEN = 7 on RV64)             |
| 11    | PMLEN = XLEN − 48 (PMLEN = 16 on RV64)            |

### 12.1.11. Supervisor Address Translation and Protection (`satp`) Register

`satp` controls supervisor-mode address translation. It holds the **PPN of the root page table** (= root SPA / 4 KiB), an **ASID**, and the **MODE**.

#### Figure 63. `satp` when SXLEN=32

| Bits      | Field    |
| :-------- | :------- |
| **31**    | MODE     |
| **30:22** | ASID (9 bit) |
| **21:0**  | PPN (22 bit) |

#### Figure 64. `satp` when SXLEN=64 (MODE values Bare, Sv39, Sv48, Sv57)

| Bits      | Field    |
| :-------- | :------- |
| **63:60** | MODE (4 bit) |
| **59:44** | ASID (16 bit) |
| **43:0**  | PPN (44 bit) |

**Table 40. Encoding of `satp.MODE`**

When SXLEN=32:

| Value | Name | Description                              |
| :---: | :--- | :--------------------------------------- |
| 0     | Bare | No translation or protection.            |
| 1     | Sv32 | Page-based 32-bit virtual addressing (§12.3). |

When SXLEN=64:

| Value | Name | Description                              |
| :---: | :--- | :--------------------------------------- |
| 0     | Bare | No translation or protection.            |
| 1-7   | —    | Reserved for standard use.               |
| **8** | **Sv39** | **Page-based 39-bit virtual addressing (§12.4).** |
| 9     | Sv48 | Page-based 48-bit virtual addressing (§12.5). |
| 10    | Sv57 | Page-based 57-bit virtual addressing (§12.6). |
| 11    | Sv64 | Reserved for page-based 64-bit virtual addressing. |
| 12-13 | —    | Reserved for standard use.               |
| 14-15 | —    | Designated for custom use.               |

(Note: The IOMMU's `iosatp.MODE` and `iohgatp.MODE` re-use these values; see riscv-iommu spec Tables 4-5.)

ASIDLEN: max 9 bits for Sv32, max 16 bits for Sv39/Sv48/Sv57. Implementations may have ASIDLEN < these maxima.

`satp` is **active** when the effective privilege mode is S or U. Translations using a stale `satp` value are not required to terminate when `satp` changes; software must use `SFENCE.VMA` for ordering.

> **Note**: Writing `satp` does not imply ordering between page-table updates and subsequent address translations, nor does it imply invalidation of address-translation caches.

### 12.1.12. Supervisor Timer (`stimecmp`) Register (Sstc extension)

64-bit register; on RV32, accessed as `stimecmp` (low 32) + `stimecmph` (high 32). A timer interrupt becomes pending (`mip.STIP`/`sip.STIP`) when `time >= stimecmp` (unsigned comparison).

---

## 12.2. Supervisor Instructions

### 12.2.1. Supervisor Memory-Management Fence Instruction (`SFENCE.VMA`)

#### Encoding

| Bits      | Field    | Value         |
| :-------- | :------- | :------------ |
| **31:25** | funct7   | `SFENCE.VMA` (= 0b0001001) |
| **24:20** | rs2      | asid (5-bit register specifier) |
| **19:15** | rs1      | vaddr (5-bit register specifier) |
| **14:12** | funct3   | 0 (PRIV)      |
| **11:7**  | rd       | 0             |
| **6:0**   | opcode   | SYSTEM (0b1110011) |

#### Operand semantics

| `rs1` | `rs2` | Operation                                                                                              |
| :---: | :---: | :----------------------------------------------------------------------------------------------------- |
| `x0`  | `x0`  | Order all reads/writes to any level of page tables, **for all address spaces**. Invalidate all TLB entries (including global). |
| `x0`  | ≠`x0` | Order page-table accesses for the address space identified by `rs2` (= ASID). Global mappings not ordered. Invalidate all matching ASID entries except global. |
| ≠`x0` | `x0`  | Order accesses only to leaf PTEs corresponding to the VA in `rs1`, **all address spaces**. Invalidate matching leaf entries (including global). |
| ≠`x0` | ≠`x0` | Order leaf-PTE accesses for VA in `rs1` and ASID in `rs2`. Invalidate matching leaf entries except global. |

If `rs1` does not hold a valid virtual address, `SFENCE.VMA` has no effect (no exception is raised).

When `rs2 != x0`: bits `SXLEN-1:ASIDMAX` of `rs2` are reserved for future standard use; bits `ASIDMAX-1:ASIDLEN` are ignored.

#### Memory ordering rules

`SFENCE.VMA` orders **prior explicit accesses** before subsequent **implicit page-table accesses**, and orders those implicit accesses before subsequent explicit accesses. It does **not** force prior explicit accesses to precede subsequent explicit accesses in the global memory order. (See spec prose for full detail.)

#### Common usage patterns (informative)

| Software action                          | Required SFENCE.VMA invocation                   |
| :--------------------------------------- | :----------------------------------------------- |
| Recycle an ASID                          | `SFENCE.VMA rs1=x0, rs2=<recycled ASID>`         |
| Implementation has no ASIDs              | `SFENCE.VMA rs1=x0` after every `satp` write     |
| Modify a non-leaf PTE                    | `SFENCE.VMA rs1=x0`; `rs2 = x0` if any G bit on path else ASID |
| Modify a leaf PTE                        | `SFENCE.VMA rs1=<vaddr in page>`; `rs2 = x0` if any G on path else ASID |
| Increase permission / invalid → valid leaf | May lazily SFENCE after a fault occurs         |

(Mapping to IOMMU: `IOTINVAL.VMA` is the device-side analog. See riscv-iommu spec §4.1.1 Table 11 for the GV/AV/PSCV variants.)

---

## 12.3. Sv32: Page-Based 32-bit Virtual-Memory System

### 12.3.1. Addressing and Memory Protection

Sv32: 32-bit VA → 34-bit PA via a **2-level** page table. 4 KiB pages, 4 MiB megapages.

#### Figure 65. Sv32 virtual address (32 bit)

| Bits      | Field        |
| :-------- | :----------- |
| **31:22** | VPN[1] (10 bit) |
| **21:12** | VPN[0] (10 bit) |
| **11:0**  | page offset (12 bit) |

#### Figure 66. Sv32 physical address (34 bit)

| Bits      | Field        |
| :-------- | :----------- |
| **33:22** | PPN[1] (12 bit) |
| **21:12** | PPN[0] (10 bit) |
| **11:0**  | page offset (12 bit) |

#### Figure 67. Sv32 PTE (4 byte)

| Bits      | Field    |
| :-------- | :------- |
| **31:20** | PPN[1] (12 bit) |
| **19:10** | PPN[0] (10 bit) |
| **9:8**   | RSW      |
| **7**     | D        |
| **6**     | A        |
| **5**     | G        |
| **4**     | U        |
| **3**     | X        |
| **2**     | W        |
| **1**     | R        |
| **0**     | V        |

**Table 41. PTE R/W/X encoding**

| X | W | R | Meaning                            |
| :---: | :---: | :---: | :------------------------------- |
| 0 | 0 | 0 | Pointer to next level of page table |
| 0 | 0 | 1 | Read-only page                    |
| 0 | 1 | 0 | *Reserved for future use.*        |
| 0 | 1 | 1 | Read-write page                   |
| 1 | 0 | 0 | Execute-only page                 |
| 1 | 0 | 1 | Read-execute page                 |
| 1 | 1 | 0 | *Reserved for future use.*        |
| 1 | 1 | 1 | Read-write-execute page           |

When `R=W=X=0`, the PTE is a **non-leaf pointer** to the next level. Otherwise, it is a leaf PTE. **Writable pages must also be marked readable**; the `W=1, R=0` combinations are reserved.

#### Bit field semantics

- **V** (bit 0): Valid. If 0, all other bits are don't-care; the PTE causes a page-fault on use.
- **R / W / X** (bits 1, 2, 3): permissions; see Table 41.
- **U** (bit 4): User-mode accessible. U-mode access requires `U=1`. S-mode access requires `U=0`, **unless** `sstatus.SUM=1` AND access is data (not fetch).
- **G** (bit 5): Global mapping (exists in all address spaces). For non-leaf PTEs, G=1 implies all subsequent levels are global.
- **A** (bit 6): Accessed. Set to 1 when the page is read/written/fetched (or a fault is raised if Svade is implemented).
- **D** (bit 7): Dirty. Set to 1 when the page is written (or a fault is raised if Svade).
- **RSW** (bits 9:8): Reserved for supervisor software; hardware ignores.

A and D bit management has two schemes (HW updates vs Svade fault-on-use). When two-stage translation is active, additional rules apply (see prose).

### 12.3.2. Virtual Address Translation Process — algorithmic reference

This is **the core PTW algorithm** that the IOMMU's PTW implements. The pseudocode below is faithful to spec §12.3.2 and parameterized by `LEVELS`, `PTESIZE`, `PAGESIZE` so the same algorithm covers Sv32 / Sv39 / Sv48 / Sv57.

#### PTW pseudocode (canonical)

```
# ===== INPUT =====
va             : virtual address (XLEN bit, but only N bit are meaningful;
                 upper bits sign-extended from bit N-1 — page-fault if not)
satp.PPN       : root PT page (44 bit on RV64, 22 bit on RV32)
satp.MODE      : selects scheme (Sv32 / Sv39 / Sv48 / Sv57)
access_type    : "fetch" | "load" | "store"
priv           : current privilege mode (S or U)
sstatus.SUM    : permit S-mode access to U pages
sstatus.MXR    : make X readable

# ===== PARAMETERS (from satp.MODE) =====
PAGESIZE = 4096   = 2^12                          # always 4 KiB
LEVELS, PTESIZE, VPN_BITS_PER_LEVEL =
    Sv32: (2, 4, 10)
    Sv39: (3, 8, 9)
    Sv48: (4, 8, 9)
    Sv57: (5, 8, 9)

# ===== STEP 1 =====
a = satp.PPN * PAGESIZE                           # base of root PT
i = LEVELS - 1                                    # level index, top → 0

while True:
    # ===== STEP 2 — read PTE =====
    pte_addr = a + va.vpn[i] * PTESIZE
    if PMA/PMP_violation(pte_addr):
        fault_access(access_type)                 # cause = 1/5/7
    pte = read_atomic(pte_addr, PTESIZE)

    # ===== STEP 3 — basic checks =====
    if pte.V == 0 or (pte.R == 0 and pte.W == 1) or (pte.reserved != 0):
        fault_page(access_type)                   # cause = 12/13/15

    # ===== STEP 4 — non-leaf? =====
    if pte.R == 0 and pte.X == 0:
        i = i - 1
        if i < 0:
            fault_page(access_type)
        a = pte.ppn * PAGESIZE
        continue                                  # back to step 2

    # ===== STEP 5 — leaf reached, check superpage alignment =====
    if i > 0 and any( pte.ppn[k] != 0 for k in 0..i-1 ):
        fault_page(access_type)                   # misaligned superpage

    # ===== STEP 6 — U-bit / SUM / MXR check =====
    if priv == U and pte.U == 0:
        fault_page(access_type)
    if priv == S and pte.U == 1 and (sstatus.SUM == 0 or access_type == "fetch"):
        fault_page(access_type)

    # ===== STEP 7 — Zicfiss shadow-stack check (omitted unless extension active) =====

    # ===== STEP 8 — R/W/X permission check =====
    if access_type == "fetch" and pte.X == 0:                         fault_page(access_type)
    if access_type == "load":
        readable = pte.R == 1 or (sstatus.MXR == 1 and pte.X == 1)
        if not readable:                                              fault_page(access_type)
    if access_type == "store" and pte.W == 0:                         fault_page(access_type)

    # ===== STEP 9 — A/D bit management =====
    if pte.A == 0 or (access_type == "store" and pte.D == 0):
        if Svade_extension_implemented:
            fault_page(access_type)
        else:
            # HW A/D update: atomic compare-and-set
            atomic:
                pte_in_mem = read_atomic(pte_addr, PTESIZE)
                if pte_in_mem == pte:
                    pte_in_mem.A = 1
                    if access_type == "store": pte_in_mem.D = 1
                    write_atomic(pte_addr, pte_in_mem)
                else:
                    goto step 2     # restart walk

    # ===== STEP 10 — compose physical address =====
    pa.pgoff = va.pgoff
    if i > 0:
        pa.ppn[i-1:0] = va.vpn[i-1:0]              # superpage: low bits from VA
    pa.ppn[LEVELS-1:i] = pte.ppn[LEVELS-1:i]
    return pa
```

#### Per-mode parameter table

| Mode | LEVELS | PTESIZE | VA bits used | VPN slices | PPN bits | Page sizes |
| :--- | :----: | :-----: | :----------: | :--------- | :------: | :--------- |
| Sv32 | 2      | 4       | 32           | VPN[1]=[31:22]/10 bit, VPN[0]=[21:12]/10 bit | 22 | 4 KiB, 4 MiB |
| **Sv39** | **3** | **8** | **39 (sign-ext to 64)** | **VPN[2]=[38:30]/9, VPN[1]=[29:21]/9, VPN[0]=[20:12]/9** | **44** | **4 KiB, 2 MiB, 1 GiB** |
| Sv48 | 4      | 8       | 48 (sign-ext to 64) | VPN[3]/9, VPN[2]/9, VPN[1]/9, VPN[0]/9 | 44 | 4 KiB, 2 MiB, 1 GiB, 512 GiB |
| Sv57 | 5      | 8       | 57 (sign-ext to 64) | VPN[4..0] each 9 bit                   | 44 | 4 KiB, 2 MiB, 1 GiB, 512 GiB, 256 TiB |

#### Worked example — Sv39 4 KiB walk (matches IOMMU testbench `test_10`)

Configuration: Sv39, IOVA `0x002_345`, S1 PT root PPN = 0x11, mid = 0x12, leaf = 0x13, target page PPN = 0x100, leaf permissions = `V|R|W|X|U|A|D`.

```
va         = 0x000_000_002_345                     # 39-bit IOVA
VPN[2]     = (va >> 30) & 0x1FF = 0
VPN[1]     = (va >> 21) & 0x1FF = 0
VPN[0]     = (va >> 12) & 0x1FF = 0x2
pgoff      = va & 0xFFF        = 0x345

# step 2 (level 2): read root PT entry
a          = 0x11 * 4096 = 0x11000
pte_addr   = 0x11000 + 0 * 8 = 0x11000
pte_root   = make_pte(ppn=0x12, flags=V) = (0x12 << 10) | 1 = 0x4801
                                                    # R=W=X=0 → non-leaf
# step 4 → continue, i=1, a = 0x12*4096 = 0x12000

# step 2 (level 1):
pte_addr   = 0x12000 + 0 * 8 = 0x12000
pte_mid    = make_pte(ppn=0x13, flags=V) = (0x13 << 10) | 1 = 0x4C01
                                                    # non-leaf
# step 4 → continue, i=0, a = 0x13*4096 = 0x13000

# step 2 (level 0):
pte_addr   = 0x13000 + 0x2 * 8 = 0x13010
pte_leaf   = make_pte(ppn=0x100, flags=V|R|W|X|U|A|D)
           = (0x100 << 10) | 0xDF
           = 0x400DF                                # R or X != 0 → leaf

# step 5 — i=0, no superpage alignment check needed

# step 6/8 — assume U-mode access matches U=1, R=1: pass

# step 10 — compose PA
pa.pgoff   = 0x345
i==0 so no superpage carry
pa.ppn     = pte_leaf.ppn = 0x100
pa         = (0x100 << 12) | 0x345 = 0x100_345
```

This matches the testbench's `expected_spa = 0x100345` exactly.

---

## 12.4. Sv39: Page-Based 39-bit Virtual-Memory System

39-bit VA, 56-bit PA, **3-level** page table, 4 KiB / 2 MiB / 1 GiB page sizes. Algorithm is identical to §12.3.2 with `LEVELS=3`, `PTESIZE=8`.

VA must have bits `63:39` all equal to bit 38 (sign-extension), else page-fault.

#### Figure 68. Sv39 virtual address

| Bits      | Field            |
| :-------- | :--------------- |
| **38:30** | VPN[2] (9 bit)   |
| **29:21** | VPN[1] (9 bit)   |
| **20:12** | VPN[0] (9 bit)   |
| **11:0**  | page offset (12 bit) |

#### Figure 69. Sv39 physical address (56 bit)

| Bits      | Field            |
| :-------- | :--------------- |
| **55:30** | PPN[2] (26 bit)  |
| **29:21** | PPN[1] (9 bit)   |
| **20:12** | PPN[0] (9 bit)   |
| **11:0**  | page offset      |

#### Figure 70. Sv39 PTE (8 byte)

| Bits      | Field    |
| :-------- | :------- |
| **63**    | N (Svnapot) |
| **62:61** | PBMT (Svpbmt) |
| **60:54** | Reserved |
| **53:28** | PPN[2] (26 bit) |
| **27:19** | PPN[1] (9 bit) |
| **18:10** | PPN[0] (9 bit) |
| **9:8**   | RSW      |
| **7**     | D        |
| **6**     | A        |
| **5**     | G        |
| **4**     | U        |
| **3**     | X        |
| **2**     | W        |
| **1**     | R        |
| **0**     | V        |

(Bits 9:0 have the same meaning as Sv32. Bits 63:54 must be 0 unless Svnapot/Svpbmt is implemented; otherwise page-fault. The IOMMU testbench's `make_pte()` builds exactly this layout.)

A megapage (2 MiB) leaf must have `pte.PPN[0] == 0`. A gigapage (1 GiB) leaf must have `pte.PPN[1:0] == 0`. Otherwise → "misaligned superpage" page-fault.

---

## 12.5. Sv48: Page-Based 48-bit Virtual-Memory System

48-bit VA, **4-level** PT. `LEVELS=4`, `PTESIZE=8`. Page sizes: 4 KiB, 2 MiB, 1 GiB, 512 GiB. Implementations supporting Sv48 must also support Sv39.

VA must have bits `63:48` all equal to bit 47.

#### Figure 71. Sv48 virtual address

| Bits      | Field            |
| :-------- | :--------------- |
| **47:39** | VPN[3] (9 bit)   |
| **38:30** | VPN[2] (9 bit)   |
| **29:21** | VPN[1] (9 bit)   |
| **20:12** | VPN[0] (9 bit)   |
| **11:0**  | page offset      |

#### Figure 72. Sv48 physical address

| Bits      | Field            |
| :-------- | :--------------- |
| **55:39** | PPN[3] (17 bit)  |
| **38:30** | PPN[2] (9 bit)   |
| **29:21** | PPN[1] (9 bit)   |
| **20:12** | PPN[0] (9 bit)   |
| **11:0**  | page offset      |

#### Figure 73. Sv48 PTE (8 byte)

| Bits      | Field    |
| :-------- | :------- |
| **63**    | N        |
| **62:61** | PBMT     |
| **60:54** | Reserved |
| **53:37** | PPN[3] (17 bit) |
| **36:28** | PPN[2] (9 bit) |
| **27:19** | PPN[1] (9 bit) |
| **18:10** | PPN[0] (9 bit) |
| **9:0**   | (same as Sv39) |

---

## 12.6. Sv57: Page-Based 57-bit Virtual-Memory System

57-bit VA, **5-level** PT. `LEVELS=5`, `PTESIZE=8`. Page sizes: 4 KiB, 2 MiB, 1 GiB, 512 GiB, 256 TiB. Implementations supporting Sv57 must also support Sv48.

VA must have bits `63:57` all equal to bit 56.

#### Figure 74. Sv57 virtual address

| Bits      | Field            |
| :-------- | :--------------- |
| **56:48** | VPN[4] (9 bit)   |
| **47:39** | VPN[3] (9 bit)   |
| **38:30** | VPN[2] (9 bit)   |
| **29:21** | VPN[1] (9 bit)   |
| **20:12** | VPN[0] (9 bit)   |
| **11:0**  | page offset      |

#### Figure 75. Sv57 physical address

| Bits      | Field            |
| :-------- | :--------------- |
| **55:48** | PPN[4] (8 bit)   |
| **47:39** | PPN[3] (9 bit)   |
| **38:30** | PPN[2] (9 bit)   |
| **29:21** | PPN[1] (9 bit)   |
| **20:12** | PPN[0] (9 bit)   |
| **11:0**  | page offset      |

#### Figure 76. Sv57 PTE (8 byte)

| Bits      | Field    |
| :-------- | :------- |
| **63**    | N        |
| **62:61** | PBMT     |
| **60:54** | Reserved |
| **53:46** | PPN[4] (8 bit) |
| **45:37** | PPN[3] (9 bit) |
| **36:28** | PPN[2] (9 bit) |
| **27:19** | PPN[1] (9 bit) |
| **18:10** | PPN[0] (9 bit) |
| **9:0**   | (same as Sv39) |

---

## Cross-reference summary (for IOMMU testbench)

| Privileged spec concept                  | IOMMU spec analog                                      |
| :--------------------------------------- | :----------------------------------------------------- |
| `satp` (root PT pointer)                 | `iosatp` (in `DC.fsc` when `DC.tc.PDTV=0`) — same MODE encoding (Sv39 = 8) |
| `satp.MODE` Bare/Sv39                    | `iosatp.MODE` Bare/Sv39 (riscv-iommu §3.1.3.4 Table 4) |
| Virtual address translation algorithm §12.3.2 | IOMMU PTW = same algorithm, with potentially nested second-stage walk via `iohgatp` |
| `SFENCE.VMA rs1, rs2`                    | `IOTINVAL.VMA` with operands GV/AV/PSCV (§4.1.1)       |
| Page-fault cause 12/13/15                | Same cause codes in IOMMU FQ (§4.2 Table 13)           |
| Access-fault cause 1/5/7                 | Same cause codes in IOMMU FQ (§4.2 Table 13)           |
| PTE format §12.3.1 / §12.4 (Sv39 PTE)    | Identical bit layout. Testbench `make_pte()` produces this 8-byte little-endian word |
| PTE.V=0, PTE.W=1∧R=0, reserved bits set  | Each maps to one IOMMU PTW fault test in Phase 2       |

This chapter defines the exact behavior the IOMMU's PTW must replicate per stream. When verifying the PTW, the **algorithmic reference (§12.3.2 pseudocode)** is the ground truth; everything in the IOMMU spec §3.3 step 17 (`Use the process specified in Section "Two-Stage Address Translation" of the RISC-V Privileged specification`) refers to this exact algorithm.