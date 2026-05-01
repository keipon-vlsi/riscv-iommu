# Chapter 6. Memory-mapped register interface

The IOMMU provides a memory-mapped programming interface. The memory-mapped registers of each IOMMU are located within a naturally aligned 4-KiB region (a page) of physical address space.

The IOMMU behavior for register accesses where the address is not aligned to the size of the access, or if the access spans multiple registers, or if the size of the access is not 4 bytes or 8 bytes, is `UNSPECIFIED`. A 4-byte access to an IOMMU register must be single-copy atomic. Whether an 8-byte access to an IOMMU register is single-copy atomic is `UNSPECIFIED`, and such an access may appear, internally to the IOMMU, as if two separate 4-byte accesses — first to the high half and second to the low half — were performed.

> **Note**: The 8-byte IOMMU registers are defined in such a way that software can perform two individual 4-byte accesses, or hardware can perform two independent 4-byte transactions resulting from an 8-byte access, to the high and low halves of the register, in that order, as long as the register semantics, with regard to side-effects, are respected between the two software accesses, or two hardware transactions, respectively.

The IOMMU registers have **little-endian** byte order, even for systems where all harts are big-endian-only.

> **Note**: Big-endian-configured harts that make use of an IOMMU are expected to implement the `REV8` byte-reversal instruction defined by the Zbb extension. If `REV8` is not implemented, then endianness conversion may be implemented using a sequence of instructions.

If a register is optional, as determined by the corresponding `capabilities` register bit being 0, then a read from the memory-mapped register offset of the register returns 0 and writes to that offset are ignored.

---

## 6.1. Register layout

**Table 15. IOMMU Memory-mapped register layout**

| Offset | Name           | Size | Description                       | Is Optional?                  |
| -----: | :------------- | ---: | :-------------------------------- | :---------------------------- |
|      0 | `capabilities` |    8 | Capabilities of the IOMMU         | No                            |
|      8 | `fctl`         |    4 | Features control                  | No                            |
|     12 | custom         |    4 | Designated For custom use         |                               |
|     16 | `ddtp`         |    8 | Device directory table pointer    | No                            |
|     24 | `cqb`          |    8 | Command-queue base                | No                            |
|     32 | `cqh`          |    4 | Command-queue head                | No                            |
|     36 | `cqt`          |    4 | Command-queue tail                | No                            |
|     40 | `fqb`          |    8 | Fault-queue base                  | No                            |
|     48 | `fqh`          |    4 | Fault-queue head                  | No                            |
|     52 | `fqt`          |    4 | Fault-queue tail                  | No                            |
|     56 | `pqb`          |    8 | Page-request-queue base           | if `capabilities.ATS==0`      |
|     64 | `pqh`          |    4 | Page-request-queue head           | if `capabilities.ATS==0`      |
|     68 | `pqt`          |    4 | Page-request-queue tail           | if `capabilities.ATS==0`      |
|     72 | `cqcsr`        |    4 | Command-queue CSR                 | No                            |
|     76 | `fqcsr`        |    4 | Fault-queue CSR                   | No                            |
|     80 | `pqcsr`        |    4 | Page-request-queue CSR            | if `capabilities.ATS==0`      |
|     84 | `ipsr`         |    4 | Interrupt pending status register | No                            |
|     88 | `iocountovf`   |    4 | HPM counter overflows             | if `capabilities.HPM==0`      |
|     92 | `iocountinh`   |    4 | HPM counter inhibits              | if `capabilities.HPM==0`      |
|     96 | `iohpmcycles`  |    8 | HPM cycles counter                | if `capabilities.HPM==0`      |
|    104 | `iohpmctr1-31` |  248 | HPM event counters                | if `capabilities.HPM==0`      |
|    352 | `iohpmevt1-31` |  248 | HPM event selector                | if `capabilities.HPM==0`      |
|    600 | `tr_req_iova`  |    8 | Translation-request IOVA          | if `capabilities.DBG==0`      |
|    608 | `tr_req_ctl`   |    8 | Translation-request control       | if `capabilities.DBG==0`      |
|    616 | `tr_response`  |    8 | Translation-request response      | if `capabilities.DBG==0`      |
|    624 | `iommu_qosid`  |    4 | IOMMU QoS ID                      | if `capabilities.QOSID==0`    |
|    628 | Reserved       |   60 | Reserved for future use (`WPRI`)  |                               |
|    688 | custom         |   72 | Designated for custom use (`WARL`)|                               |
|    760 | `icvec`        |    8 | Interrupt cause to vector register| No                            |
|    768 | `msi_cfg_tbl`  |  256 | MSI Configuration Table           | if `capabilities.IGS==WSI`    |
|   1024 | Reserved       | 3072 | Reserved for standard use         |                               |

---

## 6.2. Reset behavior

The reset value is 0 for the following registers fields.

- `cqcsr` - `cqen`, `cqie`, `cqon`, and `busy`
- `fqcsr` - `fqen`, `fqie`, `fqon`, and `busy`
- `pqcsr` - `pqen`, `pqie`, `pqon`, and `busy`
- `tr_req_ctl.Go/Busy`
- `ddtp.busy`

The reset value is 0 for the following registers.

- `ipsr`

Reset value for `ddtp.iommu_mode` field must be either `Off` or `Bare`.

After a reset the caches (Section 3.8) must have no valid entries.

> **Note**: The reset value for the `iommu_mode` is recommended to be `Off`.

The reset value is `UNSPECIFIED` for all other registers and/or fields.

---

## 6.3. IOMMU capabilities (`capabilities`)

The `capabilities` register is a read-only register reporting features supported by the IOMMU. Each field if not clear indicates the presence of that feature in the IOMMU. At reset, the register shall contain the IOMMU supported features.

**Figure 35. IOMMU capabilities register fields**

| Bits      | Field      |
| :-------- | :--------- |
| **63:56** | custom     |
| **55:48** | reserved   |
| **47:44** | reserved   |
| **43**    | S          |
| **42**    | NL         |
| **41**    | QOSID      |
| **40**    | PD20       |
| **39**    | PD17       |
| **38**    | PD8        |
| **37:32** | PAS        |
| **31**    | DBG        |
| **30**    | HPM        |
| **29:28** | IGS        |
| **27**    | END        |
| **26**    | T2GPA      |
| **25**    | ATS        |
| **24**    | AMO_HWAD   |
| **23**    | MSI_MRIF   |
| **22**    | MSI_FLAT   |
| **21**    | AMO_MRIF   |
| **20**    | reserved   |
| **19**    | Sv57x4     |
| **18**    | Sv48x4     |
| **17**    | Sv39x4     |
| **16**    | Sv32x4     |
| **15**    | Svpbmt     |
| **14**    | Svrsw60t59b|
| **13:12** | reserved   |
| **11**    | Sv57       |
| **10**    | Sv48       |
| **9**     | Sv39       |
| **8**     | Sv32       |
| **7:0**   | version    |

| Bits  | Field         | Attribute | Description                                                                                                                                                                                            |
| :---- | :------------ | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 7:0   | `version`     | RO        | The `version` field holds the version of the specification implemented by the IOMMU. The low nibble is used to hold the minor version of the specification and the upper nibble is used to hold the major version of the specification. For example, an implementation that supports version 1.0 of the specification reports `0x10`. |
| 8     | `Sv32`        | RO        | Page-based 32-bit virtual addressing is supported.                                                                                                                                                     |
| 9     | `Sv39`        | RO        | Page-based 39-bit virtual addressing is supported.                                                                                                                                                     |
| 10    | `Sv48`        | RO        | Page-based 48-bit virtual addressing is supported. When `Sv48` is set, `Sv39` must be set.                                                                                                              |
| 11    | `Sv57`        | RO        | Page-based 57-bit virtual addressing is supported. When `Sv57` is set, `Sv48` must be set.                                                                                                              |
| 13:12 | reserved      | RO        | Reserved for standard use.                                                                                                                                                                             |
| 14    | `Svrsw60t59b` | RO        | PTE Reserved-for-Software Bits 60-59.                                                                                                                                                                  |
| 15    | `Svpbmt`      | RO        | Page-based memory types.                                                                                                                                                                               |
| 16    | `Sv32x4`      | RO        | Page-based 34-bit virtual addressing for second-stage address translation is supported.                                                                                                                |
| 17    | `Sv39x4`      | RO        | Page-based 41-bit virtual addressing for second-stage address translation is supported.                                                                                                                |
| 18    | `Sv48x4`      | RO        | Page-based 50-bit virtual addressing for second-stage address translation is supported.                                                                                                                |
| 19    | `Sv57x4`      | RO        | Page-based 59-bit virtual addressing for second-stage address translation is supported.                                                                                                                |
| 20    | reserved      | RO        | Reserved for standard use.                                                                                                                                                                             |
| 21    | `AMO_MRIF`    | RO        | Atomic updates to MRIF is supported.                                                                                                                                                                   |
| 22    | `MSI_FLAT`    | RO        | MSI address translation using Pass-through mode MSI PTE is supported.                                                                                                                                  |
| 23    | `MSI_MRIF`    | RO        | MSI address translation using MRIF mode MSI PTE is supported.                                                                                                                                          |
| 24    | `AMO_HWAD`    | RO        | Atomic updates to PTE accessed (A) and dirty (D) bit is supported.                                                                                                                                     |
| 25    | `ATS`         | RO        | PCIe Address Translation Services (ATS) and page-request interface (PRI) is supported.                                                                                                                 |
| 26    | `T2GPA`       | RO        | Returning guest-physical-address in ATS translation completions is supported.                                                                                                                          |
| 27    | `END`         | RO        | When 0, IOMMU supports one endianness (either little or big). When 1, IOMMU supports both endianness. The endianness is defined in the `fctl` register.                                                |
| 29:28 | `IGS`         | RO        | IOMMU interrupt generation support. (See `IGS` value table below.)                                                                                                                                     |
| 30    | `HPM`         | RO        | IOMMU implements a hardware performance monitor.                                                                                                                                                       |
| 31    | `DBG`         | RO        | IOMMU supports the translation-request interface.                                                                                                                                                      |
| 37:32 | `PAS`         | RO        | Physical Address Size supported by the IOMMU.                                                                                                                                                          |
| 38    | `PD8`         | RO        | One level PDT with 8-bit `process_id` supported.                                                                                                                                                       |
| 39    | `PD17`        | RO        | Two level PDT with 17-bit `process_id` supported.                                                                                                                                                      |
| 40    | `PD20`        | RO        | Three level PDT with 20-bit `process_id` supported.                                                                                                                                                    |
| 41    | `QOSID`       | RO        | Associating QoS IDs with requests is supported.                                                                                                                                                        |
| 42    | `NL`          | RO        | Non-leaf PTE invalidation extension is supported.                                                                                                                                                      |
| 43    | `S`           | RO        | Address range invalidation extension is supported.                                                                                                                                                     |
| 55:44 | reserved      | RO        | Reserved for standard use.                                                                                                                                                                             |
| 63:56 | custom        | RO        | Designated for custom use.                                                                                                                                                                             |

**`IGS` field encoding:**

| Value | Name | Description                                                                                                                            |
| :---: | :--- | :------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | MSI  | IOMMU supports only message-signaled-interrupt generation.                                                                             |
| 1     | WSI  | IOMMU supports only wire-signaled-interrupt generation.                                                                                |
| 2     | BOTH | IOMMU supports both MSI and WSI generation. The interrupt generation method must be defined in the `fctl` register.                    |
| 3     | —    | Reserved for standard use.                                                                                                             |

When `HPM` is 1, the `iohpmcycles` and the `iohpmctr1` registers must be present and be at least 32-bits wide.

At least one method, `MSI` or `WSI`, of generating interrupts from the IOMMU must be supported.

IOMMU implementations must support the Svnapot standard extension for NAPOT Translation Contiguity.

The physical address space addressable by the IOMMU ranges from 0 to 2^(`capabilities.PAS`) − 1.

> **Notes:**
> - Hypervisor may provide an SW emulated IOMMU to allow the guest to manage the first-stage page tables for fine grained control on memory accessed by guest controlled devices.
> - A hypervisor that provides such an emulated IOMMU to the guest may retain control of the second-stage address translation and clear the `SvNx4` fields of the emulated `capabilities` register.
> - A hypervisor that provides such an emulated IOMMU to the guest may retain control of the MSI page tables used to direct MSIs to guest interrupt files in an IMSIC or to a memory-resident-interrupt-file and clear the `MSI_FLAT` and `MSI_MRIF` fields of the emulated `capabilities` register.
> - The `AMO_HWAD/AMO_MRIF` bits do not indicate support for device-initiated atomic memory operations. Support for device-initiated atomic memory operations must be discovered through other means.
> - The IOMMU is designed to provide a highly modular and extensible set of capabilities allowing implementations to include only the exact set of capabilities required for an application. In addition, implementations may add their own custom extensions to the IOMMU.
> - The IOMMU must support all the virtual memory extensions that are supported by any of the harts in the system.
> - RISC-V platform specifications may mandate a set of IOMMU capabilities that must be provided by an implementation to be compliant to those specifications.

---

## 6.4. Features-control register (`fctl`)

This register must be readable in any implementation. An implementation may allow one or more fields in the register to be writable to support enabling or disabling the feature controlled by that field.

If software enables or disables a feature when the IOMMU is not OFF (i.e. when `ddtp.iommu_mode != Off`) then the IOMMU behavior is `UNSPECIFIED`.

If software enables or disables a feature when the IOMMU in-memory queues are enabled (i.e. `cqcsr.cqon/cqen == 1`, `fqcsr.fqon/cqen == 1`, or `pqcsr.pqon/pqen == 1`) then the IOMMU behavior is `UNSPECIFIED`.

**Figure 36. Feature-control register fields**

| Bits      | Field    |
| :-------- | :------- |
| **31:16** | custom   |
| **15:3**  | reserved |
| **2**     | GXL      |
| **1**     | WSI      |
| **0**     | BE       |

| Bits  | Field      | Attribute | Description                                                                                                                                                                       |
| :---- | :--------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | `BE`       | WARL      | When 0, IOMMU accesses to memory resident data structures, as specified in Table 9, and accesses to in-memory queues are performed as little-endian accesses and when 1 as big-endian accesses. |
| 1     | `WSI`      | WARL      | When 1, IOMMU interrupts are signaled as wire-signaled-interrupts else they are signaled as message-signaled-interrupts.                                                          |
| 2     | `GXL`      | WARL      | Controls the address-translation schemes that may be used for guest physical addresses as defined in Table 2 and Table 3.                                                         |
| 15:3  | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                        |
| 31:16 | custom     | WPRI      | Designated for custom use.                                                                                                                                                        |

---

## 6.5. Device-directory-table pointer (`ddtp`)

**Figure 37. Device-directory-table pointer register fields**

| Bits      | Field        |
| :-------- | :----------- |
| **63:54** | reserved     |
| **53:10** | PPN          |
| **9:5**   | reserved     |
| **4**     | busy         |
| **3:0**   | iommu_mode   |

| Bits  | Field        | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| :---- | :----------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3:0   | `iommu_mode` | WARL      | The IOMMU may be configured to be in the following modes (see table below).                                                                                                                                                                                                                                                                                                                                                                                       |
| 4     | `busy`       | RO        | A write to `ddtp.iommu_mode` may require the IOMMU to perform many operations that may not occur synchronously to the write. When a write is observed by the `ddtp.iommu_mode`, the `busy` bit is set to 1. When the `busy` bit is 1, behavior of additional writes to the `ddtp` is `UNSPECIFIED`. Some implementations may ignore the second write and others may perform the actions determined by the second write. Software must verify that the `busy` bit is 0 before writing to the `ddtp`. If the `busy` bit reads 0 then the IOMMU has completed the operations associated with the previous write to `ddtp.iommu_mode`. An IOMMU that can complete these operations synchronously may hard-wire this bit to 0. |
| 9:5   | reserved     | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 53:10 | `PPN`        | WARL      | Holds the `PPN` of the root page of the device-directory-table.                                                                                                                                                                                                                                                                                                                                                                                                   |
| 63:54 | reserved     | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |

**`iommu_mode` value encoding:**

| Value | Name     | Description                                                          |
| :---: | :------- | :------------------------------------------------------------------- |
| 0     | `Off`    | No inbound memory transactions are allowed by the IOMMU.             |
| 1     | `Bare`   | No translation or protection. All inbound memory accesses are passed through. |
| 2     | `1LVL`   | One-level device-directory-table                                     |
| 3     | `2LVL`   | Two-level device-directory-table                                     |
| 4     | `3LVL`   | Three-level device-directory-table                                   |
| 5-13  | reserved | Reserved for standard use.                                           |
| 14-15 | custom   | Designated for custom use.                                           |

The device-context is 64-bytes in size if `capabilities.MSI_FLAT` is 1 else it is 32-bytes.

When the `iommu_mode` is `Bare` or `Off`, the `PPN` field is don't-care. When in `Bare` mode only Untranslated requests are allowed. Translated requests, Translation request, and PCIe message transactions are unsupported.

All IOMMUs must support `Off` and `Bare` mode. An IOMMU is allowed to support a subset of directory-table levels and device-context widths. At a minimum one of the modes must be supported.

When the `iommu_mode` field value is changed to `Off` the IOMMU guarantees that in-flight transactions, observed at the time of the write to this field, from devices connected to the IOMMU will either be processed with the configurations applicable to the old value of the `iommu_mode` field or be aborted (Section 8.3). It also ensures that all transactions and previous requests from devices that have already been processed by the IOMMU are committed to a global ordering point such that they can be observed by all RISC-V harts, devices, and IOMMUs in the platform. Software must not change the `PPN` field value when transitioning the `iommu_mode` to `Off`.

The IOMMU behavior of writing `iommu_mode` to `1LVL`, `2LVL`, or `3LVL`, when the previous value of the `iommu_mode` is not `Off` or `Bare` is `UNSPECIFIED`. To change DDT levels, the IOMMU must first be transitioned to `Bare` or `Off` state. The behavior resulting from changing the `iommu_mode` to `Bare` when the previous value of the `iommu_mode` was not `Off` is `UNSPECIFIED`.

When an IOMMU is transitioned to `Bare` or `Off` state, the IOMMU may retain information cached from in-memory data structures such as page tables, DDT, PDT, etc. Software must use suitable invalidation commands to invalidate cached entries.

> **Note**: In RV32, only the low order 32-bits of the register (22-bit `PPN` and 4-bit `iommu_mode`) need to be written.

---

## 6.6. Command-queue base (`cqb`)

This 64-bit register (RW) holds the PPN of the root page of the command-queue and number of entries in the queue. Each command is 16 bytes.

The IOMMU behavior on writing `cqb` when `cqcsr.busy` or `cqon` bits are 1 is `UNSPECIFIED`. The software recommended sequence to change `cqb` is to first disable the command-queue by clearing `cqen` and wait for both `cqcsr.busy` and `cqon` to be 0 before changing the `cqb`. The status of bits `31:cqb.LOG2SZ` in `cqt` following a write to `cqb` is 0 and the bits `cqb.LOG2SZ-1:0` in `cqt` assume a valid but otherwise `UNSPECIFIED` value.

**Figure 38. Command-queue base register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:54** | reserved |
| **53:10** | PPN      |
| **9:5**   | reserved |
| **4:0**   | LOG2SZ-1 |

| Bits  | Field      | Attribute | Description                                                                                                                                                                                                                                                                                                              |
| :---- | :--------- | :-------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4:0   | `LOG2SZ-1` | WARL      | The `LOG2SZ-1` field holds the number of entries in command-queue as a log to base 2 minus 1. A value of 0 indicates a queue of 2 entries. Each IOMMU command is 16-bytes. If the command-queue has 256 or fewer entries then the base address of the queue is always aligned to 4-KiB. If the command-queue has more than 256 entries then the command-queue base address must be naturally aligned to 2^LOG2SZ × 16. |
| 9:5   | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                              |
| 53:10 | `PPN`      | WARL      | Holds the `PPN` of the root page of the in-memory command-queue used by software to queue commands to the IOMMU. If the base address as determined by `PPN` is not aligned as required, all entries in the queue appear to an IOMMU as `UNSPECIFIED` and any address an IOMMU may compute and use for accessing an entry in the queue is also `UNSPECIFIED`. |
| 63:54 | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                              |

> **Note**: In RV32, only the low order 32-bits of the register (22-bit `PPN` and 5-bit `LOG2SZ-1`) need to be written.

---

## 6.7. Command-queue head (`cqh`)

This 32-bit register (RO) holds the index into the command-queue where the IOMMU will fetch the next command.

**Figure 39. Command-queue head register fields**

| Bits      | Field |
| :-------- | :---- |
| **31:0**  | index |

| Bits | Field   | Attribute | Description                                                                          |
| :--- | :------ | :-------- | :----------------------------------------------------------------------------------- |
| 31:0 | `index` | RO        | Holds the `index` into the command-queue from where the next command will be fetched by the IOMMU. |

---

## 6.8. Command-queue tail (`cqt`)

This 32-bit register (RW) holds the index into the command-queue where the software queues the next command for the IOMMU.

**Figure 40. Command-queue tail register fields**

| Bits      | Field |
| :-------- | :---- |
| **31:0**  | index |

| Bits | Field   | Attribute | Description                                                                                                              |
| :--- | :------ | :-------- | :----------------------------------------------------------------------------------------------------------------------- |
| 31:0 | `index` | WARL      | Holds the `index` into the command-queue where software queues the next command for IOMMU. Only `LOG2SZ-1:0` bits are writable. |

---

## 6.9. Fault queue base (`fqb`)

This 64-bit register (RW) holds the PPN of the root page of the fault-queue and number of entries in the queue. Each fault record is 32 bytes.

The IOMMU behavior on writing `fqb` when `fqcsr.busy` or `fqon` bits are 1 is `UNSPECIFIED`. The software recommended sequence to change `fqb` is to first disable the fault-queue by clearing `fqen` and wait for both `fqcsr.busy` and `fqon` to be 0 before changing the `fqb`. The status of bits `31:fqb.LOG2SZ` in `fqh` following a write to `fqb` is 0 and the bits `fqb.LOG2SZ-1:0` in `fqh` assume a valid but otherwise `UNSPECIFIED` value.

**Figure 41. Fault queue base register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:54** | reserved |
| **53:10** | PPN      |
| **9:5**   | reserved |
| **4:0**   | LOG2SZ-1 |

| Bits  | Field      | Attribute | Description                                                                                                                                                                                                                                                                                                          |
| :---- | :--------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4:0   | `LOG2SZ-1` | WARL      | The `LOG2SZ-1` field holds the number of entries in the fault-queue as a log-to-base-2 minus 1. A value of 0 indicates a queue of 2 entries. Each fault record is 32-bytes. If the fault-queue has 128 or fewer entries then the base address of the queue is always aligned to 4-KiB. If the fault-queue has more than 128 entries then the fault-queue base address must be naturally aligned to 2^LOG2SZ × 32. |
| 9:5   | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                          |
| 53:10 | `PPN`      | WARL      | Holds the `PPN` of the root page of the in-memory fault-queue used by IOMMU to queue fault record. If the base address as determined by `PPN` is not aligned as required, all entries in the queue appear to an IOMMU as `UNSPECIFIED` and any address an IOMMU may compute and use for accessing an entry in the queue is also `UNSPECIFIED`. |
| 63:54 | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                          |

> **Note**: In RV32, only the low order 32-bits of the register (22-bit `PPN` and 5-bit `LOG2SZ-1`) need to be written.

---

## 6.10. Fault queue head (`fqh`)

This 32-bit register (RW) holds the index into the fault-queue where the software will fetch the next fault record.

**Figure 42. Fault queue head register fields**

| Bits      | Field |
| :-------- | :---- |
| **31:0**  | index |

| Bits | Field   | Attribute | Description                                                                                                  |
| :--- | :------ | :-------- | :----------------------------------------------------------------------------------------------------------- |
| 31:0 | `index` | WARL      | Holds the `index` into the fault-queue from which software reads the next fault record. Only `LOG2SZ-1:0` bits are writable. |

---

## 6.11. Fault queue tail (`fqt`)

This 32-bit register (RO) holds the index into the fault-queue where the IOMMU queues the next fault record.

**Figure 43. Fault queue tail register fields**

| Bits      | Field |
| :-------- | :---- |
| **31:0**  | index |

| Bits | Field   | Attribute | Description                                                                          |
| :--- | :------ | :-------- | :----------------------------------------------------------------------------------- |
| 31:0 | `index` | RO        | Holds the `index` into the fault-queue where IOMMU writes the next fault record.     |

---

## 6.12. Page-request-queue base (`pqb`)

This 64-bit register (WARL) holds the PPN of the root page of the page-request-queue and number of entries in the queue. Each "Page Request" message is 16 bytes.

The IOMMU behavior on writing `pqb` when `pqcsr.busy` or `pqon` bits are 1 is `UNSPECIFIED`. The software recommended sequence to change `pqb` is to first disable the page-request-queue by clearing `pqen` and wait for both `pqcsr.busy` and `pqon` to be 0 before changing the `pqb`. The status of bits `31:pqb.LOG2SZ` in `pqh` following a write to `pqb` is 0 and the bits `pqb.LOG2SZ-1:0` in `pqh` assume a valid but otherwise `UNSPECIFIED` value.

**Figure 44. Page-Request-queue base register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:54** | reserved |
| **53:10** | PPN      |
| **9:5**   | reserved |
| **4:0**   | LOG2SZ-1 |

| Bits  | Field      | Attribute | Description                                                                                                                                                                                                                                                                                                                              |
| :---- | :--------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4:0   | `LOG2SZ-1` | WARL      | The `LOG2SZ-1` field holds the number of entries in the page-request-queue as a log-to-base-2 minus 1. A value of 0 indicates a queue of 2 entries. Each page-request is 16-bytes. If the page-request-queue has 256 or fewer entries then the base address of the queue is always aligned to 4-KiB. If the page-request-queue has more than 256 entries then the page-request-queue base address must be naturally aligned to 2^LOG2SZ × 16. |
| 9:5   | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                              |
| 53:10 | `PPN`      | WARL      | Holds the `PPN` of the root page of the in-memory page-request-queue used by IOMMU to queue "Page Request" messages. If the base address as determined by `PPN` is not aligned as required, all entries in the queue appear to an IOMMU as `UNSPECIFIED` and any address an IOMMU may compute and use for accessing an entry in the queue is also `UNSPECIFIED`. |
| 63:54 | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                              |

> **Note**: In RV32, only the low order 32-bits of the register (22-bit `PPN` and 5-bit `LOG2SZ-1`) need to be written.

---

## 6.13. Page-request-queue head (`pqh`)

This 32-bit register (RW) holds the index into the page-request-queue where software will fetch the next page-request.

**Figure 45. Page-request-queue head register fields**

| Bits      | Field |
| :-------- | :---- |
| **31:0**  | index |

| Bits | Field   | Attribute | Description                                                                                                          |
| :--- | :------ | :-------- | :------------------------------------------------------------------------------------------------------------------- |
| 31:0 | `index` | WARL      | Holds the `index` into the page-request-queue from which software reads the next "Page Request" message. Only `LOG2SZ-1:0` bits are writable. |

---

## 6.14. Page-request-queue tail (`pqt`)

This 32-bit register (RO) holds the index into the page-request-queue where the IOMMU writes the next page-request.

**Figure 46. Page-request-queue tail register fields**

| Bits      | Field |
| :-------- | :---- |
| **31:0**  | index |

| Bits | Field   | Attribute | Description                                                                                                |
| :--- | :------ | :-------- | :--------------------------------------------------------------------------------------------------------- |
| 31:0 | `index` | RO        | Holds the `index` into the page-request-queue where IOMMU writes the next "Page Request" message.         |

---

## 6.15. Command-queue CSR (`cqcsr`)

This 32-bit register (RW) is used to control the operations and report the status of the command-queue.

**Figure 47. Command-queue CSR register fields**

| Bits      | Field        |
| :-------- | :----------- |
| **31:28** | custom       |
| **27:18** | reserved     |
| **17**    | busy         |
| **16**    | cqon         |
| **15:12** | reserved     |
| **11**    | fence_w_ip   |
| **10**    | cmd_ill      |
| **9**     | cmd_to       |
| **8**     | cqmf         |
| **7:2**   | reserved     |
| **1**     | cie          |
| **0**     | cqen         |

| Bits  | Field        | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| :---- | :----------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | `cqen`       | RW        | The command-queue-enable bit enables the command-queue when set to 1. Changing `cqen` from 0 to 1 sets the `cqh` register and the `cqcsr` bits `cmd_ill`, `cmd_to`, `cqmf`, `fence_w_ip` to 0. The command-queue may take some time to be active following setting the `cqen` to 1. During this delay the `busy` bit is 1. When the command queue is active, the `cqon` bit reads 1. When `cqen` is changed from 1 to 0, the command queue may stay active (with `busy` asserted) until the commands already fetched from the command-queue are being processed and/or there are outstanding implicit loads from the command-queue. When the command-queue turns off the `cqon` bit reads 0. When the `cqon` bit reads 0, the IOMMU guarantees that no implicit memory accesses to the command queue are in-flight and the command-queue will not generate new implicit loads to the queue memory. |
| 1     | `cie`        | RW        | Command-queue-interrupt-enable bit enables generation of interrupts from command-queue when set to 1.                                                                                                                                                                                                                                                                                                                                                            |
| 7:2   | reserved     | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 8     | `cqmf`       | RW1C      | If command-queue access to fetch a command or a memory access made by a command leads to a memory fault, then the command-queue-memory-fault bit is set to 1, and the command-queue stalls until this bit is cleared. To re-enable command processing, software should clear this bit by writing 1.                                                                                                                                                              |
| 9     | `cmd_to`     | RW1C      | If the execution of a command leads to a timeout (e.g. a command to invalidate device ATC may timeout waiting for a completion), then the command-queue sets the `cmd_to` bit and stops processing from the command-queue. To re-enable command processing, software should clear this bit by writing 1.                                                                                                                                                         |
| 10    | `cmd_ill`    | RW1C      | If an illegal or unsupported command is fetched and decoded by the command-queue then the command-queue sets the `cmd_ill` bit and stops processing from the command-queue. To re-enable command processing software should clear this bit by writing 1.                                                                                                                                                                                                        |
| 11    | `fence_w_ip` | RW1C      | An IOMMU that supports wire-signaled-interrupts sets the `fence_w_ip` bit to indicate completion of an `IOFENCE.C` command. To re-enable interrupts on `IOFENCE.C` completion, software should clear this bit by writing 1. This bit is reserved if the IOMMU does not support wire-signaled-interrupts or wire-signaled-interrupts are not enabled (i.e., `fctl.WSI == 0`).                                                                                       |
| 15:12 | reserved     | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 16    | `cqon`       | RO        | The command-queue is active if `cqon` is 1.                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 17    | `busy`       | RO        | A write to `cqcsr` may require the IOMMU to perform many operations that may not occur synchronously to the write. When a write is observed by the `cqcsr`, the `busy` bit is set to 1. When the `busy` bit is 1, behavior of additional writes to the `cqcsr` is `UNSPECIFIED`. Some implementations may ignore the second write and others may perform the actions determined by the second write. Software must verify that the busy bit is 0 before writing to the `cqcsr`. An IOMMU that can complete these operations synchronously may hard-wire this bit to 0. |
| 27:18 | reserved     | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 31:28 | custom       | WPRI      | Designated for custom use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |

When `cmd_ill` or `cqmf` is 1 in `cqcsr`, the `cqh` references the command in the CQ that caused the error. Previous commands may have completed, timed out, or their execution aborted by the IOMMU.

> **Note**: If software makes the CQ operational again after a `cmd_ill` or `cqmf` error, then software should resubmit the commands submitted since the last `IOFENCE.C` that successfully completed.

The `cmd_to` bit is set when a `IOFENCE.C` command detects that one or more previous commands that are specified to have timeouts have timed out but all other commands previous to the `IOFENCE.C` have completed. When `cmd_to` is 1, `cqh` references the `IOFENCE.C` command that detected the timeout.

> **Note**: Command-queue being empty does not imply that all commands fetched from the command-queue have been completed. When the command-queue is requested to be disabled, an implementation may either complete the already fetched commands or abort execution of those commands. Software must use an `IOFENCE.C` command to wait for all previous commands to be committed, if so desired, before turning off the command-queue.

---

## 6.16. Fault queue CSR (`fqcsr`)

This 32-bit register (RW) is used to control the operations and report the status of the fault-queue.

**Figure 48. Fault queue CSR register fields**

| Bits      | Field    |
| :-------- | :------- |
| **31:28** | custom   |
| **27:18** | reserved |
| **17**    | busy     |
| **16**    | fqon     |
| **15:10** | reserved |
| **9**     | fqof     |
| **8**     | fqmf     |
| **7:2**   | reserved |
| **1**     | fie      |
| **0**     | fqen     |

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| :---- | :------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | `fqen`   | RW        | The fault-queue enable bit enables the fault-queue when set to 1. Changing `fqen` from 0 to 1 sets the `fqt` register and the `fqcsr` bits `fqof` and `fqmf` to 0. The fault-queue may take some time to be active following setting the `fqen` to 1. During this delay the `busy` bit is 1. When the fault queue is active, the `fqon` bit reads 1. When `fqen` is changed from 1 to 0, the fault-queue may stay active (with `busy` asserted) until in-flight fault-recording is completed. When the fault-queue is off the `fqon` bit reads 0. When `fqon` reads 0, the IOMMU guarantees that there are no in-flight implicit writes to the fault-queue in progress and that no new fault records will be written to the fault-queue. |
| 1     | `fie`    | RW        | Fault queue interrupt enable bit enables generation of interrupts from fault-queue when set to 1.                                                                                                                                                                                                                                                                                                                                                                |
| 7:2   | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 8     | `fqmf`   | RW1C      | The `fqmf` bit is set to 1 if the IOMMU encounters an access fault when storing a fault record to the fault queue. The fault-record that was attempted to be written is discarded and no more fault records are generated until software clears the `fqmf` bit by writing 1 to the bit.                                                                                                                                                                          |
| 9     | `fqof`   | RW1C      | The fault-queue-overflow bit is set to 1 if the IOMMU needs to queue a fault record but the fault-queue is full (i.e., `fqt == fqh - 1`). The fault-record is discarded and no more fault records are generated until software clears `fqof` by writing 1 to the bit.                                                                                                                                                                                            |
| 15:10 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 16    | `fqon`   | RO        | The fault-queue is active if `fqon` reads 1.                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 17    | `busy`   | RO        | Write to `fqcsr` may require the IOMMU to perform many operations that may not occur synchronously to the write. When a write is observed by the fqcsr, the `busy` bit is set to 1. When the `busy` bit is 1, behavior of additional writes to the `fqcsr` are `UNSPECIFIED`. Some implementations may ignore the second write and others may perform the actions determined by the second write. Software should ensure that the `busy` bit is 0 before writing to the `fqcsr`. An IOMMU that can complete controls synchronously may hard-wire this bit to 0. |
| 27:18 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 31:28 | custom   | WPRI      | Designated for custom use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |

---

## 6.17. Page-request-queue CSR (`pqcsr`)

This 32-bit register (RW) is used to control the operations and report the status of the page-request-queue.

**Figure 49. Page-request-queue CSR register fields**

| Bits      | Field      |
| :-------- | :--------- |
| **31:28** | Custom use |
| **27:18** | reserved   |
| **17**    | busy       |
| **16**    | pqon       |
| **15:10** | reserved   |
| **9**     | pqof       |
| **8**     | pqmf       |
| **7:2**   | reserved   |
| **1**     | pie        |
| **0**     | pqen       |

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| :---- | :------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | `pqen`   | RW        | The page-request-enable bit enables the page-request-queue when set to 1. Changing `pqen` from 0 to 1, sets the `pqt` register and the `pqcsr` bits `pqmf` and `pqof` to 0. The page-request-queue may take some time to be active following setting the `pqen` to 1. During this delay the `busy` bit is 1. When the page-request-queue is active, the `pqon` bit reads 1. When `pqen` is changed from 1 to 0, the page-request-queue may stay active (with `busy` asserted) until in-flight page-request writes are completed. When the page-request-queue turns off, the `pqon` bit reads 0. When `pqon` reads 0, the IOMMU guarantees that there are no older in-flight implicit writes to the queue memory and no further implicit writes will be generated to the queue memory. The IOMMU may respond to "Page Request" messages received when page-request-queue is off or in the process of being turned off, as specified in Section 3.7. |
| 1     | `pie`    | RW        | The page-request-queue-interrupt-enable bit when set to 1, enables generation of interrupts from page-request-queue.                                                                                                                                                                                                                                                                                                                                              |
| 7:2   | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 8     | `pqmf`   | RW1C      | The `pqmf` bit is set to 1 if the IOMMU encounters an access fault when storing a "Page Request" message to the page-request-queue. The "Page Request" message that caused the `pqmf` or `pqof` error and all subsequent "Page Request" messages are discarded until software clears the `pqof` and/or `pqmf` bits by writing 1 to it. The IOMMU may respond to "Page Request" messages that caused the `pqof` or `pqmf` bit to be set and all subsequent "Page Request" messages received while these bits are 1 as specified in Section 3.7. |
| 9     | `pqof`   | RW1C      | The page-request-queue-overflow bit is set to 1 if the page-request queue overflows i.e. IOMMU needs to queue a "Page Request" message but the page-request queue is full (i.e., `pqt == pqh - 1`). The "Page Request" message that caused the `pqmf` or `pqof` error and all subsequent "Page Request" messages are discarded until software clears the `pqof` and/or `pqmf` bits by writing 1 to it. The IOMMU may respond to "Page Request" messages that caused the `pqof` or `pqmf` bit to be set and all subsequent "Page Request" messages received while these bits are 1 as specified in Section 3.7. |
| 15:10 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 16    | `pqon`   | RO        | The page-request is active when `pqon` reads 1.                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 17    | `busy`   | RO        | A write to `pqcsr` may require the IOMMU to perform many operations that may not occur synchronously to the write. When a write is observed by the `pqcsr`, the `busy` bit is set to 1. When the `busy` bit is 1, behavior of additional writes to the `pqcsr` are `UNSPECIFIED`. Some implementations may ignore the second write and others may perform the actions determined by the second write. Software should ensure that the `busy` bit is 0 before writing to the `pqcsr`. An IOMMU that can complete controls synchronously may hard-wire this bit to 0. |
| 27:18 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 31:28 | custom   | WPRI      | Designated for custom use.                                                                                                                                                                                                                                                                                                                                                                                                                                       |

---

## 6.18. Interrupt pending status register (`ipsr`)

This 32-bit register (RW1C) reports the pending interrupts which require software service. Each interrupt-pending bit in the register corresponds to a interrupt source in the IOMMU. The interrupt-pending bit in the register once set to 1 stays 1 till software clears that interrupt-pending bit by writing 1 to clear it.

When `fctl.WSI` is 1, the interrupt-pending bit drives the wire selected by the corresponding `icvec` field to signal an interrupt.

When `fctl.WSI` is 0, the IOMMU signals interrupts using messages. MSI have edge semantics and an interrupt message is generated when an interrupt-pending bit transitions from 0 to 1. The address and data for the message are obtained from the `msi_cfg_tbl` entry selected by the `icvec` field corresponding to the interrupt-pending bit.

**Figure 50. Interrupt pending status register fields**

| Bits      | Field    |
| :-------- | :------- |
| **31:16** | reserved |
| **15:8**  | custom   |
| **7:4**   | reserved |
| **3**     | pip      |
| **2**     | pmip     |
| **1**     | fip      |
| **0**     | cip      |

**Table 16. Interrupt pending status register fields**

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                          |
| :---- | :------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | `cip`    | RW1C      | The command-queue-interrupt-pending bit is set to 1 if `cqcsr.cie` is 1 and any of the following are true: `cqcsr.fence_w_ip` is 1, `cqcsr.cmd_ill` is 1, `cqcsr.cmd_to` is 1, `cqcsr.cqmf` is 1.                                                                     |
| 1     | `fip`    | RW1C      | The fault-queue-interrupt-pending bit is set to 1 if `fqcsr.fie` is 1 and any of the following are true: `fqcsr.fqof` is 1, `fqcsr.fqmf` is 1, A new record is produced in the FQ.                                                                                    |
| 2     | `pmip`   | RW1C      | The performance-monitoring-interrupt-pending is set to 1 when `OF` bit in `iohpmcycles` or in any of the `iohpmctr1-31` registers transitions from 0 to 1.                                                                                                            |
| 3     | `pip`    | RW1C      | The page-request-queue-interrupt-pending bit is set to 1 if `pqcsr.pie` is 1 and any of the following are true: `pqcsr.pqof` is 1, `pqcsr.pqmf` is 1, A new message is produced in the PQ.                                                                            |
| 7:4   | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                           |
| 15:8  | custom   | WPRI      | Designated for custom use.                                                                                                                                                                                                                                           |
| 31:16 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                           |

If a bit in `ipsr` is 1 then a write of 1 to the bit transitions the bit from 1→0. If the conditions to set that bit are still present (See Table 16) or if they occur after the bit is cleared then that bit transitions again from 0→1.

---

## 6.19. Performance-monitoring counter overflow status (`iocountovf`)

The performance-monitoring counter overflow status is a 32-bit read-only register that contains shadow copies of the OF bits in the `iohpmevt1-31` registers — where `iocountovf` bit X corresponds to `iohpmevtX` and bit 0 corresponds to the `OF` bit of `iohpmcycles`.

This register enables overflow interrupt handler software to quickly and easily determine which counter(s) have overflowed.

**Figure 51. Performance-monitoring counter overflow status register fields**

| Bits     | Field |
| :------- | :---- |
| **31:1** | HPM   |
| **0**    | CY    |

| Bits | Field | Attribute | Description                       |
| :--- | :---- | :-------- | :-------------------------------- |
| 0    | `CY`  | RO        | Shadow of `iohpmcycles.OF`.       |
| 31:1 | `HPM` | RO        | Shadow of `iohpmevt[1-31].OF`.    |

---

## 6.20. Performance-monitoring counter inhibits (`iocountinh`)

The performance-monitoring counter inhibits is a 32-bit WARL register that contains bits to inhibit the corresponding counters from counting. Bit X when set inhibits counting in `iohpmctrX` and bit 0 inhibits counting in `iohpmcycles`.

**Figure 52. Performance-monitoring counter inhibits register fields**

| Bits     | Field |
| :------- | :---- |
| **31:1** | HPM   |
| **0**    | CY    |

| Bits | Field | Attribute | Description                                                                          |
| :--- | :---- | :-------- | :----------------------------------------------------------------------------------- |
| 0    | `CY`  | RW        | When set, `iohpmcycles` counter is inhibited from counting.                          |
| 31:1 | `HPM` | WARL      | When bit X is set, then counting of events in `iohpmctrX` is inhibited.              |

> **Note**: When the `iohpmcycles` counter is not needed, it is desirable to conditionally inhibit it to reduce energy consumption. Providing a single register to inhibit all counters allows a) one or more counters to be atomically programmed with events to count b) one or more counters to be sampled atomically.
>
> To initialize an event counter or the cycles counter to a desired value, it should be first inhibited if it is enabled to count. This measure ensures that it does not count during the update process. The inhibition should be removed after the register has been programmed with the desired value.

---

## 6.21. Performance-monitoring cycles counter (`iohpmcycles`)

This 64-bit register is a free running clock cycle counter. There is no associated `iohpmevt0`.

**Figure 53. Performance-monitoring cycles counter register fields**

| Bits      | Field   |
| :-------- | :------ |
| **63**    | OF      |
| **62:0**  | counter |

| Bits | Field     | Attribute | Description           |
| :--- | :-------- | :-------- | :-------------------- |
| 62:0 | `counter` | WARL      | Cycles counter value. |
| 63   | `OF`      | RW        | Overflow.             |

The `OF` bit is set when the `iohpmcycles` counter overflows, and remains set until cleared by software. Since `iohpmcycles` value is an unsigned value, overflow is defined as unsigned overflow. Note that there is no loss of information after an overflow since the counter wraps around and keeps counting while the sticky `OF` bit remains set.

If the `iohpmcycles` counter overflows when the `OF` bit is zero, then a HPM Counter Overflow interrupt is generated by setting `ipsr.pmip` bit to 1. If the `OF` bit is already one, then no interrupt request is generated. Consequently the `OF` bit also functions as a count overflow interrupt disable for the `iohpmcycles`.

---

## 6.22. Performance-monitoring event counters (`iohpmctr1-31`)

These registers are 64-bit WARL counter registers.

**Figure 54. Performance-monitoring event counters register fields**

| Bits     | Field   |
| :------- | :------ |
| **63:0** | counter |

| Bits | Field     | Attribute | Description          |
| :--- | :-------- | :-------- | :------------------- |
| 63:0 | `counter` | WARL      | Event counter value. |

---

## 6.23. Performance-monitoring event selectors (`iohpmevt1-31`)

These performance-monitoring event registers are 64-bit RW registers. When a transaction processed by the IOMMU causes an event that is programmed to count in a counter then the counter is incremented. In addition to matching events, the event selector may be programmed with additional filters based on `device_id`, `process_id`, `GSCID`, and `PSCID` such that the counter is incremented conditionally based on the transaction matching these additional filters. When such `device_id` based filtering is used, the match may be configured to be a precise match or a partial match. A partial match allows transactions with a range of IDs to be counted by the counter.

**Figure 55. Performance-monitoring event selector register fields**

| Bits      | Field     |
| :-------- | :-------- |
| **63**    | OF        |
| **62**    | IDT       |
| **61**    | DV_GSCV   |
| **60**    | PV_PSCV   |
| **59:36** | DID_GSCID |
| **35:16** | PID_PSCID |
| **15**    | DMASK     |
| **14:0**  | eventID   |

| Bits  | Field       | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| :---- | :---------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 14:0  | `eventID`   | WARL      | Indicates the event to count. A value of 0 indicates no events are counted. Encodings 1 to 16383 are reserved for standard events defined in Table 19. Encodings 16384 to 32767 are for designated for custom use. When `eventID` is changed, including to 0, the counter retains its value.                                                                                                                                                                     |
| 15    | `DMASK`     | RW        | When set to 1, partial matching of the `DID_GSCID` is performed for the transaction. The lower bits of the `DID_GSCID` all the way to the first low order 0 bit (including the 0 bit position itself) are masked.                                                                                                                                                                                                                                                |
| 35:16 | `PID_PSCID` | RW        | `process_id` if `IDT` is 0, `PSCID` if `IDT` is 1.                                                                                                                                                                                                                                                                                                                                                                                                               |
| 59:36 | `DID_GSCID` | RW        | `device_id` if `IDT` is 0, `GSCID` if `IDT` is 1.                                                                                                                                                                                                                                                                                                                                                                                                                |
| 60    | `PV_PSCV`   | RW        | If set, only transactions with matching `process_id` or `PSCID` (based on the Filter ID Type) are counted.                                                                                                                                                                                                                                                                                                                                                       |
| 61    | `DV_GSCV`   | RW        | If set, only transactions with matching `device_id` or `GSCID` (based on the Filter ID Type) are counted.                                                                                                                                                                                                                                                                                                                                                        |
| 62    | `IDT`       | RW        | Filter ID Type: This field indicates the type of ID to filter on. When 0, the `DID_GSCID` field holds a `device_id` and the `PID_PSCID` field holds a `process_id`. When 1, the `DID_GSCID` field holds a `GSCID` and `PID_PSCID` field holds a `PSCID`.                                                                                                                                                                                                          |
| 63    | `OF`        | RW        | Overflow status or Interrupt disable.                                                                                                                                                                                                                                                                                                                                                                                                                            |

The table below summarizes the filtering option for events that support filtering by IDs.

**Table 17. filtering options**

| IDT | DV_GSCV | PV_PSCV | Operation                                                                                                            |
| :-: | :-----: | :-----: | :------------------------------------------------------------------------------------------------------------------- |
| 0/1 |    0    |    0    | Counter increments. No ID based filtering.                                                                           |
| 0   |    0    |    1    | If the transaction has a valid `process_id`, counter increments if `process_id` matches `PID_PSCID`.                 |
| 0   |    1    |    0    | Counter increments if `device_id` matches `DID_GSCID`.                                                               |
| 0   |    1    |    1    | If the transaction has a valid `process_id`, counter increments if `device_id` matches `DID_GSCID` and `process_id` matches `PID_PSCID`. |
| 1   |    0    |    1    | If the transaction has a valid `PSCID`, counter increments if the `PSCID` of that process matches `PID_PSCID`.       |
| 1   |    1    |    0    | Counter increments if `GSCID` is valid and matches `DID_GSCID`.                                                      |
| 1   |    1    |    1    | Counter increments if `GSCID` is valid and matches `DID_GSCID` and if `PSCID` is valid and matches `PID_PSCID`.      |

When filtering by `device_id` or `GSCID` is selected and the event supports ID based filtering, the `DMASK` field can be used to configure a partial match. When `DMASK` is set to 1, partial matching of the `DID_GSCID` is performed for the transaction. The lower bits of the `DID_GSCID` all the way to the first low order 0 bit (including the 0 bit position itself) are masked.

The following example illustrates the use of `DMASK` and filtering by `device_id`.

**Table 18. `DMASK` with `IDT` set to `device_id` based filtering**

| DMASK | DID_GSCID                        | Comment                |
| :---: | :------------------------------- | :--------------------- |
| 0     | `yyyyyyyy yyyyyyyy yyyyyyyy`     | One specific seg:bus:dev:func |
| 1     | `yyyyyyyy yyyyyyyy yyyyy011`     | seg:bus:dev - any func |
| 1     | `yyyyyyyy yyyyyyyy 01111111`     | seg:bus - any dev:func |
| 1     | `yyyyyyyy 01111111 11111111`     | seg - any bus:dev:func |

The following table lists the standard events that can be counted:

**Table 19. Standard Events list**

| eventID  | Event counted               | IDT settings supported |
| :------: | :-------------------------- | :--------------------- |
| 0        | Do not count                |                        |
| 1        | Untranslated requests       | 0                      |
| 2        | Translated requests         | 0                      |
| 3        | ATS Translation requests    | 0                      |
| 4        | TLB miss                    | 0/1                    |
| 5        | Device Directory Walks      | 0                      |
| 6        | Process Directory Walks     | 0                      |
| 7        | First-stage Page Table Walks| 0/1                    |
| 8        | Second-stage Page Table Walks| 0/1                   |
| 9 - 16383| reserved for future standard| -                      |

When the programmed `IDT` setting is not supported for an event then the associated counter does not increment.

The `OF` bit is set when the corresponding `iohpmctr1-31` counter overflows, and remains set until cleared by software. Since `iohpmctr1-31` values are unsigned values, overflow is defined as unsigned overflow. Note that there is no loss of information after an overflow since the counter wraps around and keeps counting while the sticky `OF` bit remains set.

If a `iohpmctr1-31` counter overflows when the associated `OF` bit is zero, then a HPM Counter Overflow interrupt is generated by setting `ipsr.pmip` bit to 1. If the `OF` bit is already one, then no interrupt request is generated. Consequently the `OF` bit also functions as a count overflow interrupt disable for the associated `iohpmctr1-31`.

> **Notes:**
> - There are not separate overflow status and overflow interrupt enable bits. In practice, enabling overflow interrupt generation (by clearing the `OF` bit) is done in conjunction with initializing the counter to a starting value. Once a counter has overflowed, it and the `OF` bit must be reinitialized before another overflow interrupt can be generated.
> - In RV32, memory-mapped writes to `iohpmevt1-31` modify only one 32-bit part of the register. The following sequence may be used to update the register without counting events spuriously due to the intermediate value of the register:
>   - Write the low order 32-bits to set `eventID` to 0.
>   - Write the high order 32-bits with the new desired values.
>   - Write the low order 32-bits the new desired values, including that of the `eventID` field.
>
>   Alternatively, the counter may first be inhibited such that no events count during the update and the inhibit removed after the register has been programmed with the desired value.
> - If `capabilities.HPM` is 1 then a minimum of one programmable event counter besides the cycles counter is required to comply with this specification. One counter may be used in a time multiplexed manner to sample events but such analysis may take longer to complete. The IOMMU, unlike the CPU MMU, services multiple streams of IO and the HPM may be used by a performance analyst to analyze one or more of those streams concurrently. Typically, a performance analyst may require four programmable counters to count events for an IO stream. To support concurrent analysis of at least two streams of IO it is recommended to support seven programmable counters.

---

## 6.24. Translation-request IOVA (`tr_req_iova`)

The `tr_req_iova` is a 64-bit register used to implement a translation-request interface for debug. This register is present when `capabilities.DBG == 1`.

**Figure 56. Translation-request IOVA register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:12** | vpn      |
| **11:0**  | reserved |

| Bits  | Field      | Attribute | Description                       |
| :---- | :--------- | :-------- | :-------------------------------- |
| 11:0  | reserved   | WPRI      | Reserved for standard use.        |
| 63:12 | `vpn`      | WARL      | The IOVA virtual page number.     |

---

## 6.25. Translation-request control (`tr_req_ctl`)

The `tr_req_ctl` is a 64-bit WARL register used to implement a translation-request interface for debug. This register is present when `capabilities.DBG == 1`.

**Figure 57. Translation-request control register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:40** | DID      |
| **39:36** | custom   |
| **35:33** | reserved |
| **32**    | PV       |
| **31:12** | PID      |
| **11:4**  | reserved |
| **3**     | NW       |
| **2**     | Exe      |
| **1**     | Priv     |
| **0**     | Go/Busy  |

| Bits  | Field      | Attribute | Description                                                                                                                                                                                                                                                                                                                                                |
| :---- | :--------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | `Go/Busy`  | RW1S      | This bit is set to indicate a valid request has been setup in the `tr_req_iova/tr_req_ctl` registers for the IOMMU to translate. The IOMMU indicates completion of the requested translation by clearing this bit to 0. On completion, the results of the translation are in the `tr_response` register.                                                  |
| 1     | `Priv`     | WARL      | If set to 1, Privileged Mode access is requested else no Privileged Mode access is requested.                                                                                                                                                                                                                                                              |
| 2     | `Exe`      | WARL      | If set to 1, execute permission is requested else execute permission is not requested.                                                                                                                                                                                                                                                                     |
| 3     | `NW`       | WARL      | If set to 1, read permission is requested. If set to 0, both read and write permissions are requested.                                                                                                                                                                                                                                                     |
| 11:4  | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                 |
| 31:12 | `PID`      | WARL      | If `PV` is 1, this field provides the `process_id` input for this translation request. If `PV` is 0 then this field is not used.                                                                                                                                                                                                                           |
| 32    | `PV`       | WARL      | If set to 1, the `PID` field of the register is valid and provides the `process_id` for this translation request. If set to 0 then the `PID` field is not used and a `process_id` is not valid for this translation request.                                                                                                                              |
| 35:33 | reserved   | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                 |
| 39:36 | custom     | WPRI      | Designated for custom use.                                                                                                                                                                                                                                                                                                                                 |
| 63:40 | `DID`      | WARL      | This field provides the `device_id` for this translation request.                                                                                                                                                                                                                                                                                          |

> **Note**: In RV32, the high half of the register should be written first, followed by the low half, which includes the `Go/Busy` bit, to initiate a translation.

---

## 6.26. Translation-response (`tr_response`)

The `tr_response` is a 64-bit RO register used to hold the results of a translation requested using the translation-request interface. This register is present when `capabilities.DBG == 1`.

**Figure 58. Translation-response register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:60** | custom   |
| **59:54** | reserved |
| **53:10** | PPN      |
| **9**     | S        |
| **8:7**   | PBMT     |
| **6:1**   | reserved |
| **0**     | fault    |

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                              |
| :---- | :------- | :-------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | `fault`  | RO        | If the process to translate the IOVA detects a fault then the `fault` field is set to 1. The detected fault may be reported through the fault-queue.                                                                                                                                                                                                                                                                     |
| 6:1   | reserved | RO        | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                               |
| 8:7   | `PBMT`   | RO        | Memory type determined for the translation using the PBMT fields in the first-stage and/or the second-stage page tables used for the translation. This value of this field is `UNSPECIFIED` if the `fault` field is 1.                                                                                                                                                                                                   |
| 9     | `S`      | RO        | Translation range size field, when set to 1 indicates that the translation applies to a range that is larger than 4 KiB and the size of the translation range is encoded in the `PPN` field. The value of this field is `UNSPECIFIED` if the `fault` field is 1.                                                                                                                                                         |
| 53:10 | `PPN`    | RO        | If the `fault` bit is 0, then this field provides the PPN determined as a result of translating the `vpn` in `tr_req_iova`. If the `fault` bit is 1, then the value of this field is `UNSPECIFIED`. If the `S` bit is 0, then the size of the translation is 4 KiB - a page. If the `S` bit is 1, then the translation resulted in a superpage, and the size of the superpage is encoded in the `PPN` itself. If scanning from bit position 0 to bit position 43, the first bit with a value of 0 at position X, then the superpage size is 2^(X+1) × 4 KiB. If `X` is not 0, then all bits at position 0 through `X-1` are each encoded with a value of 1. |
| 59:54 | reserved | RO        | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                               |
| 63:60 | custom   | RO        | Designated for custom use.                                                                                                                                                                                                                                                                                                                                                                                               |

**Table 20. Example of encoding of super page size in `PPN`**

| PPN                          | S | Size  |
| :--------------------------- | :-: | :---- |
| `yyyy....yyyy yyyy yyyy`     | 0 | 4 KiB |
| `yyyy....yyyy yyyy 0111`     | 1 | 64 KiB|
| `yyyy....yyy0 1111 1111`     | 1 | 2 MiB |
| `yyyy....yy01 1111 1111`     | 1 | 4 MiB |

> **Note**: An IOMMU implementation is not required to report a superpage translation or support reporting all possible superpage sizes. An implementation is allowed to report a 4 KiB translation corresponding to the requested `vpn` or report a translation size that is smaller than the superpage size configured in the page tables.

---

## 6.27. IOMMU QoS ID (`iommu_qosid`)

The `iommu_qosid` register fields are defined as follows:

**Figure 59. `iommu_qosid` register fields**

| Bits      | Field    |
| :-------- | :------- |
| **31:28** | WPRI     |
| **27:16** | MCID     |
| **15:12** | WPRI     |
| **11:0**  | RCID     |

| Bits  | Field   | Attribute | Description                              |
| :---- | :------ | :-------- | :--------------------------------------- |
| 11:0  | `RCID`  | WARL      | `RCID` for IOMMU-initiated requests.     |
| 15:12 | reserved| WPRI      | Reserved for standard use.               |
| 27:16 | `MCID`  | WARL      | `MCID` for IOMMU-initiated requests.     |
| 31:28 | reserved| WPRI      | Reserved for standard use.               |

IOMMU-initiated requests for accessing the following data structures use the value programmed in the `RCID` and `MCID` fields of the `iommu_qosid` register.

- Device directory table (DDT)
- Fault queue (FQ)
- Command queue (CQ)
- Page-request queue (PQ)
- IOMMU-initiated MSI (Message-signaled interrupts)

When `ddtp.iommu_mode == Bare`, all device-originated requests are associated with the QoS IDs configured in the `iommu_qosid` register.

---

## 6.28. Interrupt-cause-to-vector register (`icvec`)

Interrupt-cause-to-vector register maps a cause to a vector. All causes can be mapped to the same vector or a cause can be given a unique vector.

The vector is used:

1. By an IOMMU that generates interrupts as MSIs, to index into MSI configuration table (`msi_cfg_tbl`) to determine the MSI to generate. An IOMMU is capable of generating interrupts as a MSI if `capabilities.IGS==MSI` or if `capabilities.IGS==BOTH`. When `capabilities.IGS==BOTH` the IOMMU may be configured to generate interrupts as MSI by setting `fctl.WSI` to 0.
2. By an IOMMU that generates WSI, to determine the wire to signal the interrupt. An IOMMU is capable of generating wire-signaled-interrupts if `capabilities.IGS==WSI` or if `capabilities.IGS==BOTH`. When `capabilities.IGS==BOTH` the IOMMU may be configured to generate wire-signaled-interrupts by setting `fctl.WSI` to 1.

If an implementation only supports a single vector then all bits of this register may be hardwired to 0 (WARL). Likewise if only two vectors are supported then only bit 0 for each cause could be writable.

**Figure 60. Interrupt-cause-to-vector register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:32** | custom   |
| **31:16** | reserved |
| **15:12** | piv      |
| **11:8**  | pmiv     |
| **7:4**   | fiv      |
| **3:0**   | civ      |

| Bits  | Field    | Attribute | Description                                                                                            |
| :---- | :------- | :-------- | :----------------------------------------------------------------------------------------------------- |
| 3:0   | `civ`    | WARL      | The command-queue-interrupt-vector (`civ`) is the vector number assigned to the command-queue-interrupt. |
| 7:4   | `fiv`    | WARL      | The fault-queue-interrupt-vector (`fiv`) is the vector number assigned to the fault-queue-interrupt. |
| 11:8  | `pmiv`   | WARL      | The performance-monitoring-interrupt-vector (`pmiv`) is the vector number assigned to the performance-monitoring-interrupt. |
| 15:12 | `piv`    | WARL      | The page-request-queue-interrupt-vector (`piv`) is the vector number assigned to the page-request-queue-interrupt. |
| 31:16 | reserved | WPRI      | Reserved for standard use.                                                                             |
| 63:32 | custom   | WPRI      | Designated for custom use.                                                                             |

---

## 6.29. MSI configuration table (`msi_cfg_tbl`)

An IOMMU that supports generating IOMMU-originated interrupts (i.e., `capabilities.IGS == MSI` or `capabilities.IGS == BOTH`) as MSIs implements a MSI configuration table that is indexed by the vector from `icvec` to determine a MSI table entry. Each MSI table entry for interrupt vector `x` has three registers `msi_addr_x`, `msi_data_x`, and `msi_vec_ctl_x`. These registers are hardwired to 0 if `capabilities.IGS == WSI`.

If an access fault is detected on a MSI write using `msi_addr_x`, then the IOMMU reports a "IOMMU MSI write access fault" (cause 273) fault, with `TTYP` set to 0 and `iotval` set to the value of `msi_addr_x`.

**Table 21. MSI configuration table structure**

| bit 63                 |             bit 0 | Byte Offset |
| :--------------------- | ----------------: | :---------- |
| Entry 0: Message address                   || +000h       |
| Entry 0: Vector Control | Entry 0: Message Data | +008h    |
| Entry 1: Message address                   || +010h       |
| Entry 1: Vector Control | Entry 1: Message Data | +018h    |
| ...                                        || +020h       |

**Figure 61. Message address register fields**

| Bits      | Field    |
| :-------- | :------- |
| **63:56** | reserved |
| **55:2**  | ADDR     |
| **1:0**   | 0        |

| Bits  | Field    | Attribute | Description                                |
| :---- | :------- | :-------- | :----------------------------------------- |
| 1:0   | 0        | RO        | Fixed to 0.                                |
| 55:2  | `ADDR`   | WARL      | Holds the 4-byte aligned MSI address.      |
| 63:56 | reserved | WPRI      | Reserved for standard use.                 |

**Figure 62. Message data register fields**

| Bits     | Field |
| :------- | :---- |
| **31:0** | data  |

| Bits | Field   | Attribute | Description           |
| :--- | :------ | :-------- | :-------------------- |
| 31:0 | `data`  | WARL      | Holds the MSI data.   |

**Figure 63. Vector control register fields**

| Bits     | Field    |
| :------- | :------- |
| **31:1** | reserved |
| **0**    | M        |

| Bits | Field    | Attribute | Description                                                                                                                                                                                              |
| :--- | :------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0    | `M`      | RW        | When the mask bit `M` is 1, the corresponding interrupt vector is masked and the IOMMU is prohibited from sending the associated message. Pending messages for that vector are later generated if the corresponding mask bit is cleared to 0. |
| 31:1 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                              |