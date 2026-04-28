# <span id="page-62-0"></span>Chapter 6. Memory-mapped register interface

The IOMMU provides a memory-mapped programming interface. The memory-mapped registers of each IOMMU are located within a naturally aligned 4-KiB region (a page) of physical address space.

The IOMMU behavior for register accesses where the address is not aligned to the size of the access, or if the access spans multiple registers, or if the size of the access is not 4 bytes or 8 bytes, is UNSPECIFIED. A 4 byte access to an IOMMU register must be single-copy atomic. Whether an 8 byte access to an IOMMU register is single-copy atomic is UNSPECIFIED, and such an access may appear, internally to the IOMMU, as if two separate 4 byte accesses — first to the high half and second to the low half — were performed.

![](_page_62_Picture_4.jpeg)

*The 8-byte IOMMU registers are defined in such a way that software can perform two individual 4-byte accesses, or hardware can perform two independent 4-byte transactions resulting from an 8-byte access, to the high and low halves of the register, in that order, as long as the register semantics, with regard to side-effects, are respected between the two software accesses, or two hardware transactions, respectively.*

The IOMMU registers have little-endian byte order, even for systems where all harts are big-endian-only.

![](_page_62_Picture_7.jpeg)

*Big-endian-configured harts that make use of an IOMMU are expected to implement the* REV8 *byte-reversal instruction defined by the Zbb extension. If* REV8 *is not implemented, then endianness conversion may be implemented using a sequence of instructions.*

If a register is optional, as determined by the corresponding capabilities register bit being 0, then a read from the memory-mapped register offset of the register returns 0 and writes to that offset are ignored.

# <span id="page-62-1"></span>6.1. Register layout

*Table 15. IOMMU Memory-mapped register layout*

| Offset | Name         | Size | Description                    | Is Optional?           |
|--------|--------------|------|--------------------------------|------------------------|
| 0      | capabilities | 8    | Capabilities of the IOMMU      | No                     |
| 8      | fctl         | 4    | Features control               | No                     |
| 12     | custom       | 4    | Designated For custom use      |                        |
| 16     | ddtp         | 8    | Device directory table pointer | No                     |
| 24     | cqb          | 8    | Command-queue base             | No                     |
| 32     | cqh          | 4    | Command-queue head             | No                     |
| 36     | cqt          | 4    | Command-queue tail             | No                     |
| 40     | fqb          | 8    | Fault-queue base               | No                     |
| 48     | fqh          | 4    | Fault-queue head               | No                     |
| 52     | fqt          | 4    | Fault-queue tail               | No                     |
| 56     | pqb          | 8    | Page-request-queue base        | if capabilities.ATS==0 |
| 64     | pqh          | 4    | Page-request-queue head        | if capabilities.ATS==0 |
| 68     | pqt          | 4    | Page-request-queue tail        | if capabilities.ATS==0 |
| 72     | cqcsr        | 4    | Command-queue CSR              | No                     |
| 76     | fqcsr        | 4    | Fault-queue CSR                | No                     |
| 80     | pqcsr        | 4    | Page-request-queue CSR         | if capabilities.ATS==0 |

| Offset | Name         | Size | Description                        | Is Optional?             |
|--------|--------------|------|------------------------------------|--------------------------|
| 84     | ipsr         | 4    | Interrupt pending status register  | No                       |
| 88     | iocountovf   | 4    | HPM counter overflows              | if capabilities.HPM==0   |
| 92     | iocountinh   | 4    | HPM counter inhibits               | if capabilities.HPM==0   |
| 96     | iohpmcycles  | 8    | HPM cycles counter                 | if capabilities.HPM==0   |
| 104    | iohpmctr1-31 | 248  | HPM event counters                 | if capabilities.HPM==0   |
| 352    | iohpmevt1-31 | 248  | HPM event selector                 | if capabilities.HPM==0   |
| 600    | tr_req_iova  | 8    | Translation-request IOVA           | if capabilities.DBG==0   |
| 608    | tr_req_ctl   | 8    | Translation-request control        | if capabilities.DBG==0   |
| 616    | tr_response  | 8    | Translation-request response       | if capabilities.DBG==0   |
| 624    | iommu_qosid  | 4    | IOMMU QoS ID                       | if capabilities.QOSID==0 |
| 628    | Reserved     | 60   | Reserved for future use (WPRI)     |                          |
| 688    | custom       | 72   | Designated for custom use (WARL)   |                          |
| 760    | icvec        | 8    | Interrupt cause to vector register | No                       |
| 768    | msi_cfg_tbl  | 256  | MSI Configuration Table            | if capabilities.IGS==WSI |
| 1024   | Reserved     | 3072 | Reserved for standard use          |                          |

### <span id="page-63-0"></span>6.2. Reset behavior

The reset value is 0 for the following registers fields.

- ⚫ cqcsr cqen, cqie, cqon, and busy
- ⚫ fqcsr fqen, fqie, fqon, and busy
- ⚫ pqcsr pqen, pqie, pqon, and busy
- ⚫ tr\_req\_ctl.Go/Busy
- ⚫ ddtp.busy

The reset value is 0 for the following registers.

⚫ ipsr

Reset value for ddtp.iommu\_mode field must be either Off or Bare.

After a reset the caches [\(Section 3.8\)](#page-46-0) must have no valid entries.

![](_page_63_Picture_13.jpeg)

*The reset value for the* iommu\_mode *is recommended to be* Off*.*

The reset value is UNSPECIFIED for all other registers and/or fields.

# <span id="page-63-1"></span>6.3. IOMMU capabilities (**capabilities**)

The capabilities register is a read-only register reporting features supported by the IOMMU. Each field if not clear indicates the presence of that feature in the IOMMU. At reset, the register shall contain the IOMMU supported features.

| 63       | _           |          |          |        |        |        | 56       |
|----------|-------------|----------|----------|--------|--------|--------|----------|
|          |             |          | cus      | stom   |        |        |          |
| 55       |             |          |          |        |        |        | 48       |
|          |             |          | rese     | erved  |        |        |          |
| 47       |             |          | 44       | 43     | 42     | 41     | 40       |
|          | rese        | rved     |          | s      | NL     | QOSID  | PD20     |
| 39       | 38          | 37       |          |        |        |        | 32       |
| PD17     | PD8         |          |          | P      | AS     |        |          |
| 31       | 30          | 29       | 28       | 27     | 26     | 25     | 24       |
| DBG      | НРМ         | IC       | S        | END    | T2GPA  | ATS    | AMO_HWAD |
| 23       | 22          | 21       | 20       | 19     | 18     | 17     | 16       |
| MSI_MRIF | MSI_FLAT    | AMO_MRIF | reserved | Sv57x4 | Sv48x4 | Sv39x4 | Sv32x4   |
| 15       | 14          | 13       | 12       | 11     | 10     | 9      | 8        |
| Svpbmt   | Svrsw60t59b | rese     | rved     | Sv57   | Sv48   | Sv39   | Sv32     |
| 7        | 1           | 1        | •        | •      | 1      | •      | 0        |
|          | T           | 1        | ver      | rsion  | 1      | 1      |          |

*Figure 35. IOMMU capabilities register fields*

| Bits  | Field           | Attribut<br>e | Description                                                                                                                                                                                                                                                                                                                                |  |  |
|-------|-----------------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--|--|
| 7:0   | version         | RO            | The version field holds the version of the specification implemented by the IOMMU.<br>The low nibble is used to hold the minor version of the specification and the upper<br>nibble is used to hold the major version of the specification. For example, an<br>implementation that supports version 1.0 of the specification reports 0x10. |  |  |
| 8     | Sv32            | RO            | Page-based 32-bit virtual addressing is supported.                                                                                                                                                                                                                                                                                         |  |  |
| 9     | Sv39            | RO            | Page-based 39-bit virtual addressing is supported.                                                                                                                                                                                                                                                                                         |  |  |
| 10    | Sv48            | RO            | Page-based 48-bit virtual addressing is supported.<br>When Sv48 is set, Sv39 must be set.                                                                                                                                                                                                                                                  |  |  |
| 11    | Sv57            | RO            | Page-based 57-bit virtual addressing is supported<br>When Sv57 is set, Sv48 must be set.                                                                                                                                                                                                                                                   |  |  |
| 13:12 | reserved        | RO            | Reserved for standard use.                                                                                                                                                                                                                                                                                                                 |  |  |
| 14    | Svrsw60t<br>59b | RO            | PTE Reserved-for-Software Bits 60-59.                                                                                                                                                                                                                                                                                                      |  |  |
| 15    | Svpbmt          | RO            | Page-based memory types.                                                                                                                                                                                                                                                                                                                   |  |  |
| 16    | Sv32x4          | RO            | Page-based 34-bit virtual addressing for second-stage address translation is supported.                                                                                                                                                                                                                                                    |  |  |
| 17    | Sv39x4          | RO            | Page-based 41-bit virtual addressing for second-stage address translation is supported.                                                                                                                                                                                                                                                    |  |  |
| 18    | Sv48x4          | RO            | Page-based 50-bit virtual addressing for second-stage address translation is supported.                                                                                                                                                                                                                                                    |  |  |
| 19    | Sv57x4          | RO            | Page-based 59-bit virtual addressing for second-stage address translation is supported.                                                                                                                                                                                                                                                    |  |  |
| 20    | reserved        | RO            | Reserved for standard use.                                                                                                                                                                                                                                                                                                                 |  |  |
| 21    | AMO_MRIF        | RO            | Atomic updates to MRIF is supported.                                                                                                                                                                                                                                                                                                       |  |  |
| 22    | MSI_FLAT        | RO            | MSI address translation using Pass-through mode MSI PTE is supported.                                                                                                                                                                                                                                                                      |  |  |
| 23    | MSI_MRIF        | RO            | MSI address translation using MRIF mode MSI PTE is supported.                                                                                                                                                                                                                                                                              |  |  |
| 24    | AMO_HWAD        | RO            | Atomic updates to PTE accessed (A) and dirty (D) bit is supported.                                                                                                                                                                                                                                                                         |  |  |
| 25    | ATS             | RO            | PCIe Address Translation Services (ATS) and page-request interface (PRI) [4] is<br>supported.                                                                                                                                                                                                                                              |  |  |
| 26    | T2GPA           | RO            | Returning guest-physical-address in ATS translation completions is supported.                                                                                                                                                                                                                                                              |  |  |

| Bits      | Field          | Attribut<br>e | Description                                                                                                                                              |                                                   |                                                                                                                         |  |  |
|-----------|----------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|--|--|
| 27        | END            | RO            | When 0, IOMMU supports one endianness (either little or big). When 1, IOMMU<br>supports both endianness. The endianness is defined in the fctl register. |                                                   |                                                                                                                         |  |  |
| 29:2<br>8 | IGS            | RO            | IOMMU interrupt generation support.                                                                                                                      |                                                   |                                                                                                                         |  |  |
|           |                |               | Value                                                                                                                                                    | Name                                              | Description                                                                                                             |  |  |
|           |                |               | 0                                                                                                                                                        | MSI                                               | IOMMU supports only message- signaled-interrupt<br>generation.                                                          |  |  |
|           |                |               | 1                                                                                                                                                        | WSI                                               | IOMMU supports only wire- signaled-interrupt<br>generation.                                                             |  |  |
|           |                |               | 2                                                                                                                                                        | BOTH                                              | IOMMU supports both MSI and WSI generation.<br>The interrupt generation method must be defined<br>in the fctl register. |  |  |
|           |                |               | 3                                                                                                                                                        | 0                                                 | Reserved for standard use                                                                                               |  |  |
| 30        | HPM            | RO            | IOMMU implements a hardware performance monitor.                                                                                                         |                                                   |                                                                                                                         |  |  |
| 31        | DBG            | RO            | IOMMU supports the translation-request interface                                                                                                         |                                                   |                                                                                                                         |  |  |
| 37:32 PAS |                | RO            | Physical Address Size supported by the IOMMU.                                                                                                            |                                                   |                                                                                                                         |  |  |
| 38        | PD8            | RO            | One level PDT with 8-bit process_id supported.                                                                                                           |                                                   |                                                                                                                         |  |  |
| 39        | PD17           | RO            |                                                                                                                                                          | Two level PDT with 17-bit process_id supported.   |                                                                                                                         |  |  |
| 40        | PD20           | RO            |                                                                                                                                                          | Three level PDT with 20-bit process_id supported. |                                                                                                                         |  |  |
| 41        | QOSID          | RO            | Associating QoS IDs with requests is supported.                                                                                                          |                                                   |                                                                                                                         |  |  |
| 42        | NL             | RO            | Non-leaf PTE invalidation extension is supported.                                                                                                        |                                                   |                                                                                                                         |  |  |
| 43        | S              | RO            | Address range invalidation extension is supported.                                                                                                       |                                                   |                                                                                                                         |  |  |
|           | 55:44 reserved | RO            | Reserved for standard use.                                                                                                                               |                                                   |                                                                                                                         |  |  |
| 63:5<br>6 | custom         | RO            | Designated for custom use.                                                                                                                               |                                                   |                                                                                                                         |  |  |

When HPM is 1, the iohpmcycles and the iohpmctr1 registers must be present and be at least 32-bits wide.

At least one method, MSI or WSI, of generating interrupts from the IOMMU must be supported.

IOMMU implementations must support the Svnapot standard extension for NAPOT Translation Contiguity.

The physical address space addressable by the IOMMU ranges from 0 to .

*Hypervisor may provide an SW emulated IOMMU to allow the guest to manage the first-stage page tables for fine grained control on memory accessed by guest controlled devices.*

![](_page_66_Picture_5.jpeg)

*A hypervisor that provides such an emulated IOMMU to the guest may retain control of the second-stage address translation and clear the* SvNx4 *fields of the emulated* capabilities *register.*

*A hypervisor that provides such an emulated IOMMU to the guest may retain control of the MSI page tables used to direct MSIs to guest interrupt files in an IMSIC or to a memoryresident-interrupt-file and clear the* MSI\_FLAT *and* MSI\_MRIF *fields of the emulated* capabilities *register.*

![](_page_66_Picture_8.jpeg)

*The* AMO\_HWAD*/*AMO\_MRIF *bits do not indicate support for device-initiated atomic memory operations. Support for device-initiated atomic memory operations must be discovered through other means.*

*The IOMMU is designed to provide a highly modular and extensible set of capabilities allowing implementations to include only the exact set of capabilities required for an application. In addition, implementations may add their own custom extensions to the IOMMU.*

![](_page_66_Picture_11.jpeg)

*The IOMMU must support all the virtual memory extensions that are supported by any of the harts in the system.*

*RISC-V platform specifications may mandate a set of IOMMU capabilities that must be provided by an implementation to be compliant to those specifications.*

# <span id="page-66-0"></span>6.4. Features-control register (**fctl**)

This register must be readable in any implementation. An implementation may allow one or more fields in the register to be writable to support enabling or disabling the feature controlled by that field.

If software enables or disables a feature when the IOMMU is not OFF (i.e. when ddtp.iommu\_mode != Off) then the IOMMU behavior is UNSPECIFIED.

If software enables or disables a feature when the IOMMU in-memory queues are enabled (i.e. cqcsr.cqon/cqen == 1, fqcsr.fqon/cqen == 1, or pqcsr.pqon/pqen == 1) then the IOMMU behavior is UNSPECIFIED.

![](_page_66_Figure_18.jpeg)

*Figure 36. Feature-control register fields*

| Bits | Field | Attribute | Description                                                                                                                                                                                              |
|------|-------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0    | BE    | WARL      | When 0, IOMMU accesses to memory resident data structures,<br>as specified in Table 9, and accesses to in-memory queues are<br>performed as little-endian accesses and when 1 as big-endian<br>accesses. |

| Bits  | Field    | Attribute | Description                                                                                                                  |
|-------|----------|-----------|------------------------------------------------------------------------------------------------------------------------------|
| 1     | WSI      | WARL      | When 1, IOMMU interrupts are signaled as wire-signaled<br>interrupts else they are signaled as message-signaled-interrupts.  |
| 2     | GXL      | WARL      | Controls the address-translation schemes that may be used for<br>guest physical addresses as defined in Table 2 and Table 3. |
| 15:3  | reserved | WPRI      | Reserved for standard use.                                                                                                   |
| 31:16 | custom   | WPRI      | Designated for custom use.                                                                                                   |

# <span id="page-67-0"></span>6.5. Device-directory-table pointer (**ddtp**)

![](_page_67_Figure_3.jpeg)

*Figure 37. Device-directory-table pointer register fields*

| Bits | Field      | Attribute |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |          | Description                                                                         |
|------|------------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------|
| 3:0  | iommu_mode | WARL      | The IOMMU may be configured to be in the following modes:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |          |                                                                                     |
|      |            |           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Name     | Description                                                                         |
|      |            |           | 0                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Off      | No inbound memory transactions are<br>allowed by the IOMMU.                         |
|      |            |           | 1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Bare     | No translation or protection. All<br>inbound memory accesses are passed<br>through. |
|      |            |           | 2                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 1LVL     | One-level device-directory-table                                                    |
|      |            |           | 3                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 2LVL     | Two-level device-directory-table                                                    |
|      |            |           | 4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 3LVL     | Three-level device-directory-table                                                  |
|      |            |           | 5-13                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | reserved | Reserved for standard use.                                                          |
|      |            |           | 14-15                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | custom   | Designated for custom use.                                                          |
| 4    | busy       | RO        | A write to ddtp.iommu_mode may require the IOMMU to<br>perform many operations that may not occur synchronously to<br>the write. When a write is observed by the ddtp.iommu_mode,<br>the busy bit is set to 1. When the busy bit is 1, behavior of<br>additional writes to the ddtp is UNSPECIFIED. Some<br>implementations may ignore the second write and others may<br>perform the actions determined by the second write. Software<br>must verify that the busy bit is 0 before writing to the ddtp.<br>If the busy bit reads 0 then the IOMMU has completed the<br>operations associated with the previous write to<br>ddtp.iommu_mode.<br>An IOMMU that can complete these operations synchronously |          | may hard-wire this bit to 0.                                                        |

| Bits  | Field    | Attribute | Description                                                   |
|-------|----------|-----------|---------------------------------------------------------------|
| 9:5   | reserved | WPRI      | Reserved for standard use                                     |
| 53:10 | PPN      | WARL      | Holds the PPN of the root page of the device-directory-table. |
| 63:54 | reserved | WPRI      | Reserved for standard use                                     |

The device-context is 64-bytes in size if capabilities.MSI\_FLAT is 1 else it is 32-bytes.

When the iommu\_mode is Bare or Off, the PPN field is don't-care. When in Bare mode only Untranslated requests are allowed. Translated requests, Translation request, and PCIe message transactions are unsupported.

All IOMMUs must support Off and Bare mode. An IOMMU is allowed to support a subset of directory-table levels and device-context widths. At a minimum one of the modes must be supported.

When the iommu\_mode field value is changed to Off the IOMMU guarantees that in-flight transactions, observed at the time of the write to this field, from devices connected to the IOMMU will either be processed with the configurations applicable to the old value of the iommu\_mode field or be aborted [\(Section](#page-98-3) [8.3\)](#page-98-3). It also ensures that all transactions and previous requests from devices that have already been processed by the IOMMU are committed to a global ordering point such that they can be observed by all RISC-V harts, devices, and IOMMUs in the platform. Software must not change the PPN field value when transitioning the iommu\_mode to Off.

The IOMMU behavior of writing iommu\_mode to 1LVL, 2LVL, or 3LVL, when the previous value of the iommu\_mode is not Off or Bare is UNSPECIFIED. To change DDT levels, the IOMMU must first be transitioned to Bare or Off state. The behavior resulting from changing the iommu\_mode to Bare when the previous value of the iommu\_mode was not Off is UNSPECIFIED.

When an IOMMU is transitioned to Bare or Off state, the IOMMU may retain information cached from inmemory data structures such as page tables, DDT, PDT, etc. Software must use suitable invalidation commands to invalidate cached entries.

![](_page_68_Picture_8.jpeg)

*In RV32, only the low order 32-bits of the register (22-bit* PPN *and 4-bit* iommu\_mode*) need to be written.*

# <span id="page-68-0"></span>6.6. Command-queue base (**cqb**)

This 64-bit register (RW) holds the PPN of the root page of the command-queue and number of entries in the queue. Each command is 16 bytes.

The IOMMU behavior on writing cqb when cqcsr.busy or cqon bits are 1 is UNSPECIFIED. The software recommended sequence to change cqb is to first disable the command-queue by clearing cqen and wait for both cqcsr.busy and cqon to be 0 before changing the cqb. The status of bits 31:cqb.LOG2SZ in cqt following a write to cqb is 0 and the bits cqb.LOG2SZ-1:0 in cqt assume a valid but otherwise UNSPECIFIED value.

![](_page_68_Figure_13.jpeg)

*Figure 38. Command-queue base register fields*

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                            |
|-------|----------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 4:0   | LOG2SZ-1 | WARL      | The LOG2SZ-1 field holds the number of entries in command-queue as a log<br>to base 2 minus 1. A value of 0 indicates a queue of 2 entries. Each IOMMU<br>command is 16-bytes. If the command-queue has 256 or fewer entries then<br>the base address of the queue is always aligned to 4-KiB. If the command<br>queue has more than 256 entries then the command-queue base address<br>LOG2SZ x 16.<br>must be naturally aligned to 2 |
| 9:5   | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                              |
| 53:10 | PPN      | WARL      | Holds the PPN of the root page of the in-memory command-queue used by<br>software to queue commands to the IOMMU. If the base address as<br>determined by PPN is not aligned as required, all entries in the queue appear<br>to an IOMMU as UNSPECIFIED and any address an IOMMU may compute<br>and use for accessing an entry in the queue is also UNSPECIFIED.                                                                       |
| 63:54 | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                              |

![](_page_69_Picture_2.jpeg)

*In RV32, only the low order 32-bits of the register (22-bit* PPN *and 5-bit* LOG2SZ-1*) need to be written.*

# <span id="page-69-0"></span>6.7. Command-queue head (**cqh**)

This 32-bit register (RO) holds the index into the command-queue where the IOMMU will fetch the next command.

![](_page_69_Figure_6.jpeg)

*Figure 39. Command-queue head register fields*

| Bits | Field | Attribute | Description                                                                                         |
|------|-------|-----------|-----------------------------------------------------------------------------------------------------|
| 31:0 | index | RO        | Holds the index into the command-queue from where the next command<br>will be fetched by the IOMMU. |

# <span id="page-69-1"></span>6.8. Command-queue tail (**cqt**)

This 32-bit register (RW) holds the index into the command-queue where the software queues the next command for the IOMMU.

![](_page_69_Figure_11.jpeg)

*Figure 40. Command-queue tail register fields*

| Bits | Field | Attribute | Description                                                                                                                    |
|------|-------|-----------|--------------------------------------------------------------------------------------------------------------------------------|
| 31:0 | index | WARL      | Holds the index into the command-queue where software queues the next<br>command for IOMMU. Only LOG2SZ-1:0 bits are writable. |

### <span id="page-69-2"></span>6.9. Fault queue base (**fqb**)

This 64-bit register (RW) holds the PPN of the root page of the fault-queue and number of entries in the queue. Each fault record is 32 bytes.

The IOMMU behavior on writing fqb when fqcsr.busy or fqon bits are 1 is UNSPECIFIED. The software

recommended sequence to change fqb is to first disable the fault-queue by clearing fqen and wait for both fqcsr.busy and fqon to be 0 before changing the fqb. The status of bits 31:fqb.LOG2SZ in fqh following a write to fqb is 0 and the bits fqb.LOG2SZ-1:0 in fqh assume a valid but otherwise UNSPECIFIED value.

![](_page_70_Figure_2.jpeg)

*Figure 41. Fault queue base register fields*

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                       |
|-------|----------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 4:0   | LOG2SZ-1 | WARL      | The LOG2SZ-1 field holds the number of entries in the fault-queue as a log<br>to-base-2 minus 1. A value of 0 indicates a queue of 2 entries. Each fault<br>record is 32-bytes. If the fault-queue has 128 or fewer entries then the base<br>address of the queue is always aligned to 4-KiB. If the fault-queue has more<br>than 128 entries then the fault-queue base address must be naturally aligned<br>LOG2SZ x 32.<br>to 2 |
| 9:5   | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                         |
| 53:10 | PPN      | WARL      | Holds the PPN of the root page of the in-memory fault-queue used by IOMMU<br>to queue fault record. If the base address as determined by PPN is not aligned<br>as required, all entries in the queue appear to an IOMMU as UNSPECIFIED<br>and any address an IOMMU may compute and use for accessing an entry in<br>the queue is also UNSPECIFIED.                                                                                |
| 63:54 | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                         |

![](_page_70_Picture_5.jpeg)

*In RV32, only the low order 32-bits of the register (22-bit* PPN *and 5-bit* LOG2SZ-1*) need to be written.*

# <span id="page-70-0"></span>6.10. Fault queue head (**fqh**)

This 32-bit register (RW) holds the index into the fault-queue where the software will fetch the next fault record.

![](_page_70_Figure_9.jpeg)

*Figure 42. Fault queue head register fields*

| Bits | Field | Attribute | Description                                                                                                                 |
|------|-------|-----------|-----------------------------------------------------------------------------------------------------------------------------|
| 31:0 | index | WARL      | Holds the index into the fault-queue from which software reads the next<br>fault record. Only LOG2SZ-1:0 bits are writable. |

# <span id="page-70-1"></span>6.11. Fault queue tail (**fqt**)

This 32-bit register (RO) holds the index into the fault-queue where the IOMMU queues the next fault record.

![](_page_70_Figure_14.jpeg)

*Figure 43. Fault queue tail register fields*

| Bits | Field | Attribute | Description                                                                       |
|------|-------|-----------|-----------------------------------------------------------------------------------|
| 31:0 | index | RO        | Holds the index into the fault-queue where IOMMU writes the next fault<br>record. |

# <span id="page-71-0"></span>6.12. Page-request-queue base (**pqb**)

This 64-bit register (WARL) holds the PPN of the root page of the page-request-queue and number of entries in the queue. Each "Page Request" message is 16 bytes.

The IOMMU behavior on writing pqb when pqcsr.busy or pqon bits are 1 is UNSPECIFIED. The software recommended sequence to change pqb is to first disable the page-request-queue by clearing pqen and wait for both pqcsr.busy and pqon to be 0 before changing the pqb. The status of bits 31:pqb.LOG2SZ in pqh following a write to pqb is 0 and the bits pqb.LOG2SZ-1:0 in pqh assume a valid but otherwise UNSPECIFIED value.

![](_page_71_Figure_5.jpeg)

*Figure 44. Page-Request-queue base register fields*

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
|-------|----------|-----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 4:0   | LOG2SZ-1 | WARL      | The LOG2SZ-1 field holds the number of entries in the page-request-queue as<br>a log-to-base-2 minus 1. A value of 0 indicates a queue of 2 entries. Each page<br>request is 16-bytes. If the page-request-queue has 256 or fewer entries then<br>the base address of the queue is always aligned to 4-KiB. If the page-request<br>queue has more than 256 entries then the page-request-queue base address<br>LOG2SZ x 16.<br>must be naturally aligned to 2 |
| 9:5   | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 53:10 | PPN      | WARL      | Holds the PPN of the root page of the in-memory page-request-queue used by<br>IOMMU to queue "Page Request" messages. If the base address as determined<br>by PPN is not aligned as required, all entries in the queue appear to an<br>IOMMU as UNSPECIFIED and any address an IOMMU may compute and use<br>for accessing an entry in the queue is also UNSPECIFIED.                                                                                          |
| 63:54 | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                     |

![](_page_71_Picture_8.jpeg)

*In RV32, only the low order 32-bits of the register (22-bit* PPN *and 5-bit* LOG2SZ-1*) need to be written.*

# <span id="page-71-1"></span>6.13. Page-request-queue head (**pqh**)

This 32-bit register (RW) holds the index into the page-request-queue where software will fetch the next page-request.

![](_page_71_Figure_12.jpeg)

*Figure 45. Page-request-queue head register fields*

| Bits | Field | Attribute | Description                                                                                                                                  |
|------|-------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------|
| 31:0 | index | WARL      | Holds the index into the page-request-queue from which software reads the<br>next "Page Request" message. Only LOG2SZ-1:0 bits are writable. |

### <span id="page-72-0"></span>6.14. Page-request-queue tail (**pqt**)

This 32-bit register (RO) holds the index into the page-request-queue where the IOMMU writes the next page-request.

![](_page_72_Figure_3.jpeg)

*Figure 46. Page-request-queue tail register fields*

| Bits | Field | Attribute | Description                                                                                        |
|------|-------|-----------|----------------------------------------------------------------------------------------------------|
| 31:0 | index | RO        | Holds the index into the page-request-queue where IOMMU writes the next<br>"Page Request" message. |

### <span id="page-73-0"></span>6.15. Command-queue CSR (**cqcsr**)

This 32-bit register (RW) is used to control the operations and report the status of the command-queue.

| 31 |          |      | 28   | 27         |         |        | 24   |
|----|----------|------|------|------------|---------|--------|------|
|    | custom   |      |      |            | rese    | rved   |      |
| 23 |          |      |      |            | 18      | 17     | 16   |
|    |          | rese | rved |            |         | busy   | cqon |
| 15 |          |      | 12   | 11         | 10      | 9      | 8    |
|    | reserved |      |      | fence_w_ip | cmd_ill | cmd_to | cqmf |
| 7  |          |      |      |            | 2       | 1      | 0    |
|    | '        | rese | rved |            |         | cie    | cqen |

*Figure 47. Command-queue CSR register fields*

| Bits  | Field          | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
|-------|----------------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0     | cqen           | RW        | The command-queue-enable bit enables the command- queue when set to 1.                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
|       |                |           | Changing cqen from 0 to 1 sets the cqh register and the cqcsr bits cmd_ill<br>,cmd_to, cqmf, fence_w_ip to 0. The command-queue may take some time<br>to be active following setting the cqen to 1. During this delay the busy bit is 1.<br>When the command queue is active, the cqon bit reads 1.                                                                                                                                                                                                                        |
|       |                |           | When cqen is changed from 1 to 0, the command queue may stay active (with<br>busy asserted) until the commands already fetched from the command<br>queue are being processed and/or there are outstanding implicit loads from<br>the command-queue. When the command-queue turns off the cqon bit reads<br>0.<br>When the cqon bit reads 0, the IOMMU guarantees that no implicit memory<br>accesses to the command queue are in-flight and the command-queue will<br>not generate new implicit loads to the queue memory. |
| 1     | cie            | RW        | Command-queue-interrupt-enable bit enables generation of interrupts from<br>command-queue when set to 1.                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 7:2   | reserved       | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 8     | cqmf           | RW1C      | If command-queue access to fetch a command or a memory access made by a<br>command leads to a memory fault, then the command-queue-memory-fault<br>bit is set to 1, and the command-queue stalls until this bit is cleared. To re<br>enable command processing, software should clear this bit by writing 1.                                                                                                                                                                                                               |
| 9     | cmd_to         | RW1C      | If the execution of a command leads to a timeout (e.g. a command to<br>invalidate device ATC may timeout waiting for a completion), then the<br>command-queue sets the cmd_to bit and stops processing from the<br>command-queue. To re-enable command processing, software should clear<br>this bit by writing 1.                                                                                                                                                                                                         |
| 10    | cmd_ill        | RW1C      | If an illegal or unsupported command is fetched and decoded by the<br>command-queue then the command-queue sets the cmd_ill bit and stops<br>processing from the command-queue. To re-enable command processing<br>software should clear this bit by writing 1.                                                                                                                                                                                                                                                            |
| 11    | fence_w_i<br>p | RW1C      | An IOMMU that supports wire-signaled-interrupts sets the fence_w_ip bit to<br>indicate completion of an IOFENCE.C command. To re-enable interrupts on<br>IOFENCE.C completion, software should clear this bit by writing 1. This bit is<br>reserved if the IOMMU does not support wire-signaled-interrupts or wire<br>signaled-interrupts are not enabled (i.e., fctl.WSI == 0).                                                                                                                                           |
| 15:12 | reserved       | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 16    | cqon           | RO        | The command-queue is active if cqon is 1.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                  |
|-------|----------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 17    | busy     | RO        | A write to cqcsr may require the IOMMU to perform many operations that<br>may not occur synchronously to the write. When a write is observed by the<br>cqcsr, the busy bit is set to 1.                      |
|       |          |           | When the busy bit is 1, behavior of additional writes to the cqcsr is<br>UNSPECIFIED. Some implementations may ignore the second write and<br>others may perform the actions determined by the second write. |
|       |          |           | Software must verify that the busy bit is 0 before writing to the cqcsr.                                                                                                                                     |
|       |          |           | An IOMMU that can complete these operations synchronously may hard-wire<br>this bit to 0.                                                                                                                    |
| 27:18 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                   |
| 31:28 | custom   | WPRI      | Designated for custom use.                                                                                                                                                                                   |

When cmd\_ill or cqmf is 1 in cqcsr, the cqh references the command in the CQ that caused the error. Previous commands may have completed, timed out, or their execution aborted by the IOMMU.

![](_page_74_Picture_3.jpeg)

*If software makes the CQ operational again after a* cmd\_ill *or* cqmf *error, then software should resubmit the commands submitted since the last* IOFENCE.C *that successfully completed.*

The cmd\_to bit is set when a IOFENCE.C command detects that one or more previous commands that are specified to have timeouts have timed out but all other commands previous to the IOFENCE.C have completed. When cmd\_to is 1, cqh references the IOFENCE.C command that detected the timeout.

![](_page_74_Picture_6.jpeg)

*Command-queue being empty does not imply that all commands fetched from the commandqueue have been completed. When the command-queue is requested to be disabled, an implementation may either complete the already fetched commands or abort execution of those commands. Software must use an* IOFENCE.C *command to wait for all previous commands to be committed, if so desired, before turning off the command-queue.*

### <span id="page-75-0"></span>6.16. Fault queue CSR (**fqcsr**)

This 32-bit register (RW) is used to control the operations and report the status of the fault-queue.

| 31 | ,      | 28   | 27 |      |      | 24   |
|----|--------|------|----|------|------|------|
|    | custom |      |    | rese | rved |      |
| 23 |        |      |    | 18   | 17   | 16   |
|    | reser  | rved |    |      | busy | fqon |
| 15 |        |      |    | 10   | 9    | 8    |
|    | reser  | rved |    |      | fqof | fqmf |
| 7  |        |      |    | 2    | 1    | 0    |
|    | reser  | rved |    |      | fie  | fqen |

*Figure 48. Fault queue CSR register fields*

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|-------|----------|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0     | fqen     | RW        | The fault-queue enable bit enables the fault-queue when set to 1.<br>Changing fqen from 0 to 1 sets the fqt register and the fqcsr bits fqof and<br>fqmf to 0. The fault-queue may take some time to be active following setting<br>the fqen to 1. During this delay the busy bit is 1. When the fault queue is<br>active, the fqon bit reads 1.<br>When fqen is changed from 1 to 0, the fault-queue may stay active (with<br>busy asserted) until in-flight fault-recording is completed. When the fault<br>queue is off the fqon bit reads 0.<br>When fqon reads 0, the IOMMU guarantees that there are no in-flight<br>implicit writes to the fault-queue in progress and that no new fault records<br>will be written to the fault-queue. |
| 1     | fie      | RW        | Fault queue interrupt enable bit enables generation of interrupts from fault<br>queue when set to 1.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 7:2   | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 8     | fqmf     | RW1C      | The fqmf bit is set to 1 if the IOMMU encounters an access fault when storing<br>a fault record to the fault queue. The fault-record that was attempted to be<br>written is discarded and no more fault records are generated until software<br>clears the fqmf bit by writing 1 to the bit.                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 9     | fqof     | RW1C      | The fault-queue-overflow bit is set to 1 if the IOMMU needs to queue a fault<br>record but the fault-queue is full (i.e., fqt == fqh - 1).<br>The fault-record is discarded and no more fault records are generated until<br>software clears fqof by writing 1 to the bit.                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 15:10 | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 16    | fqon     | RO        | The fault-queue is active if fqon reads 1.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 17    | busy     | RO        | Write to fqcsr may require the IOMMU to perform many operations that<br>may not occur synchronously to the write. When a write is observed by the<br>fqcsr, the busy bit is set to 1. When the busy bit is 1, behavior of additional<br>writes to the fqcsr are UNSPECIFIED. Some implementations may ignore the<br>second write and others may perform the actions determined by the second<br>write.<br>Software should ensure that the busy bit is 0 before writing to the fqcsr.<br>An IOMMU that can complete controls synchronously may hard-wire this bit                                                                                                                                                                               |

| Bits  | Field    | Attribute | Description                |
|-------|----------|-----------|----------------------------|
| 27:18 | reserved | WPRI      | Reserved for standard use. |
| 31:28 | custom   | WPRI      | Designated for custom use. |

# <span id="page-76-0"></span>6.17. Page-request-queue CSR (**pqcsr**)

This 32-bit register (RW) is used to control the operations and report the status of the page-request-queue.

| 31 |            | 28   | 27 |      |      | 24   |
|----|------------|------|----|------|------|------|
|    | Custom use |      |    | rese | rved |      |
| 23 |            |      |    | 18   | 17   | 16   |
|    | rese       | rved |    |      | busy | pqon |
| 15 |            |      |    | 10   | 9    | 8    |
|    | rese       | rved |    |      | pqof | pqmf |
| 7  |            |      |    | 2    | 1    | 0    |
|    | reser      | rved |    | ,    | pie  | pqen |

*Figure 49. Page-request-queue CSR register fields*

| Bits | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
|------|----------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0    | pqen     | RW        | The page-request-enable bit enables the page-request-queue when set to 1.<br>Changing pqen from 0 to 1, sets the pqt register and the pqcsr bits pqmf and<br>pqof to 0. The page-request-queue may take some time to be active following<br>setting the pqen to 1. During this delay the busy bit is 1. When the page<br>request-queue is active, the pqon bit reads 1.<br>When pqen is changed from 1 to 0, the page-request-queue may stay active<br>(with busy asserted) until in-flight page-request writes are completed. When<br>the page-request-queue turns off, the pqon bit reads 0.<br>When pqon reads 0, the IOMMU guarantees that there are no older in-flight<br>implicit writes to the queue memory and no further implicit writes will be<br>generated to the queue memory.<br>The IOMMU may respond to "Page Request" messages received when page<br>request-queue is off or in the process of being turned off, as specified in<br>Section 3.7. |
| 1    | pie      | RW        | The page-request-queue-interrupt-enable bit when set to 1, enables generation<br>of interrupts from page-request-queue.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 7:2  | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 8    | pqmf     | RW1C      | The pqmf bit is set to 1 if the IOMMU encounters an access fault when storing<br>a "Page Request" message to the page-request-queue.<br>The "Page Request" message that caused the pqmf or pqof error and all<br>subsequent "Page Request" messages are discarded until software clears the<br>pqof and/or pqmf bits by writing 1 to it.<br>The IOMMU may respond to "Page Request" messages that caused the pqof<br>or pqmf bit to be set and all subsequent "Page Request" messages received<br>while these bits are 1 as specified in Section 3.7.                                                                                                                                                                                                                                                                                                                                                                                                             |

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|-------|----------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 9     | pqof     | RW1C      | The page-request-queue-overflow bit is set to 1 if the page-request queue<br>overflows i.e. IOMMU needs to queue a "Page Request" message but the page<br>request queue is full (i.e., pqt == pqh - 1).<br>The "Page Request" message that caused the pqmf or pqof error and all<br>subsequent "Page Request" messages are discarded until software clears the<br>pqof and/or pqmf bits by writing 1 to it.<br>The IOMMU may respond to "Page Request" messages that caused the pqof<br>or pqmf bit to be set and all subsequent "Page Request" messages received<br>while these bits are 1 as specified in Section 3.7. |
| 15:10 | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 16    | pqon     | RO        | The page-request is active when pqon reads 1.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 17    | busy     | RO        | A write to pqcsr may require the IOMMU to perform many operations that<br>may not occur synchronously to the write. When a write is observed by the<br>pqcsr, the busy bit is set to 1.<br>When the busy bit is 1, behavior of additional writes to the pqcsr are<br>UNSPECIFIED. Some implementations may ignore the second write and<br>others may perform the actions determined by the second write. Software<br>should ensure that the busy bit is 0 before writing to the pqcsr.<br>An IOMMU that can complete controls synchronously may hard-wire this bit<br>to 0                                               |
| 27:18 | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 31:28 | custom   | WPRI      | Designated for custom use.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |

# <span id="page-77-0"></span>6.18. Interrupt pending status register (**ipsr**)

This 32-bit register (RW1C) reports the pending interrupts which require software service. Each interruptpending bit in the register corresponds to a interrupt source in the IOMMU. The interrupt-pending bit in the register once set to 1 stays 1 till software clears that interrupt-pending bit by writing 1 to clear it.

When fctl.WSI is 1, the interrupt-pending bit drives the wire selected by the corresponding icvec field to signal an interrupt.

When fctl.WSI is 0, the IOMMU signals interrupts using messages. MSI have edge semantics and an interrupt message is generated when an interrupt-pending bit transitions from 0 to 1. The address and data for the message are obtained from the msi\_cfg\_tbl entry selected by the icvec field corresponding to the interrupt-pending bit.

<span id="page-77-1"></span>![](_page_77_Figure_6.jpeg)

*Figure 50. Interrupt pending status register fields*

*Table 16. Interrupt pending status register fields*

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                |
|-------|----------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0     | cip      | RW1C      | The command-queue-interrupt-pending bit is set to 1 if cqcsr.cie is 1 and<br>any of the following are true:<br>⚫<br>cqcsr.fence_w_ip is 1.<br>⚫<br>cqcsr.cmd_ill is 1.<br>⚫<br>cqcsr.cmd_to is 1.<br>⚫<br>cqcsr.cqmf is 1. |
| 1     | fip      | RW1C      | The fault-queue-interrupt-pending bit is set to 1 if fqcsr.fie is 1 and any of<br>the following are true:<br>⚫<br>fqcsr.fqof is 1.<br>⚫<br>fqcsr.fqmf is 1.<br>⚫<br>A new record is produced in the FQ.                    |
| 2     | pmip     | RW1C      | The performance-monitoring-interrupt-pending is set to 1 when OF bit in<br>iohpmcycles or in any of the iohpmctr1-31 registers transitions from 0 to<br>1.                                                                 |
| 3     | pip      | RW1C      | The page-request-queue-interrupt-pending is set to 1 if pqcsr.pie is 1 and<br>any of the following are true:<br>⚫<br>pqcsr.pqof is 1.<br>⚫<br>pqcsr.pqmf is 1.<br>⚫<br>A new message is produced in the PQ.                |
| 7:4   | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                 |
| 15:8  | custom   | WPRI      | Designated for custom use.                                                                                                                                                                                                 |
| 31:16 | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                  |

If a bit in ipsr is 1 then a write of 1 to the bit transitions the bit from 1→0. If the conditions to set that bit are still present (See [Table 16\)](#page-77-1) or if they occur after the bit is cleared then that bit transitions again from 0→1.

# <span id="page-79-0"></span>6.19. Performance-monitoring counter overflow status (**iocountovf**)

The performance-monitoring counter overflow status is a 32-bit read-only register that contains shadow copies of the OF bits in the iohpmevt1-31 registers - where iocountovf bit X corresponds to iohpmevtX and bit 0 corresponds to the OF bit of iohpmcycles.

This register enables overflow interrupt handler software to quickly and easily determine which counter(s) have overflowed.

![](_page_79_Figure_4.jpeg)

*Figure 51. Performance-monitoring counter overflow status register fields*

| Bits | Field | Attribute | Description                 |
|------|-------|-----------|-----------------------------|
| 0    | CY    | RO        | Shadow of iohpmcycles.OF    |
| 31:1 | HPM   | RO        | Shadow of iohpmevt[1-31].OF |

# <span id="page-79-1"></span>6.20. Performance-monitoring counter inhibits (**iocountinh**)

The performance-monitoring counter inhibits is a 32-bit WARL register that contains bits to inhibit the corresponding counters from counting. Bit X when set inhibits counting in iohpmctrX and bit 0 inhibits counting in iohpmcycles.

![](_page_79_Figure_9.jpeg)

*Figure 52. Performance-monitoring counter inhibits register fields*

| Bits | Field | Attribute | Description                                                           |
|------|-------|-----------|-----------------------------------------------------------------------|
| 0    | CY    | RW        | When set, iohpmcycles counter is inhibited from counting.             |
| 31:1 | HPM   | WARL      | When bit X is set, then counting of events in iohpmctrX is inhibited. |

*When the* iohpmcycles *counter is not needed, it is desirable to conditionally inhibit it to reduce energy consumption. Providing a single register to inhibit all counters allows a) one or more counters to be atomically programmed with events to count b) one or more counters to be sampled atomically.*

*To initialize an event counter or the cycles counter to a desired value, it should be first inhibited if it is enabled to count. This measure ensures that it does not count during the update process. The inhibition should be removed after the register has been programmed with the desired value.*

# <span id="page-80-0"></span>6.21. Performance-monitoring cycles counter (**iohpmcycles**)

This 64-bit register is a free running clock cycle counter. There is no associated iohpmevt0.

![](_page_80_Figure_3.jpeg)

*Figure 53. Performance-monitoring cycles counter register fields*

| Bits | Field   | Attribute | Description           |  |  |
|------|---------|-----------|-----------------------|--|--|
| 62:0 | counter | WARL      | Cycles counter value. |  |  |
| 63   | OF      | RW        | Overflow              |  |  |

The OF bit is set when the iohpmcycles counter overflows, and remains set until cleared by software. Since iohpmcycles value is an unsigned value, overflow is defined as unsigned overflow. Note that there is no loss of information after an overflow since the counter wraps around and keeps counting while the sticky OF bit remains set.

If the iohpmcycles counter overflows when the OF bit is zero, then a HPM Counter Overflow interrupt is generated by setting ipsr.pmip bit to 1. If the OF bit is already one, then no interrupt request is generated. Consequently the OF bit also functions as a count overflow interrupt disable for the iohpmcycles.

# <span id="page-80-1"></span>6.22. Performance-monitoring event counters (**iohpmctr1-31**)

These registers are 64-bit WARL counter registers.

![](_page_80_Figure_10.jpeg)

*Figure 54. Performance-monitoring event counters register fields*

| Bits | Field   | Attribute | Description          |
|------|---------|-----------|----------------------|
| 63:0 | counter | WARL      | Event counter value. |

# <span id="page-80-2"></span>6.23. Performance-monitoring event selectors (**iohpmevt1-31**)

These performance-monitoring event registers are 64-bit RW registers. When a transaction processed by the IOMMU causes an event that is programmed to count in a counter then the counter is incremented. In addition to matching events, the event selector may be programmed with additional filters based on device\_id, process\_id, GSCID, and PSCID such that the counter is incremented conditionally based on the transaction matching these additional filters. When such device\_id based filtering is used, the match may be configured to be a precise match or a partial match. A partial match allows transactions with a range of IDs to be counted by the counter.

| 63    | 62    | 61      | 60      | 59      |           | 56 |
|-------|-------|---------|---------|---------|-----------|----|
| OF    | IDT   | DV_GSCV | PV_PSCV |         | DID_GSCID |    |
| 55    |       |         |         |         |           | 48 |
| ·     |       |         | DID_C   | SCID    | <u>'</u>  |    |
| 47    |       |         |         |         | ,         | 40 |
|       |       |         | DID_C   | SCID    | ,         |    |
| 39    |       |         | 36      | 35      |           | 32 |
|       | DID_C | SCID    |         |         | PID_PSCID |    |
| 31    |       |         |         |         | ,         | 24 |
|       |       |         | PID_P   | SCID    |           |    |
| 23    |       |         |         | -       | ,         | 16 |
|       |       |         | PID_P   | SCID    | ,         |    |
| 15    | 14    |         |         |         |           | 8  |
| DMASK |       |         |         | eventID |           |    |
| 7     |       |         |         | ,       | ,         | 0  |
|       |       |         | eve     | ntID    | T         | ,  |

*Figure 55. Performance-monitoring event selector register fields*

| Bits  | Field     | Attribute | Description                                                                                                                                                                                                                                                                                                      |
|-------|-----------|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 14:0  | eventID   | WARL      | Indicates the event to count. A value of 0 indicates no events are<br>counted.<br>Encodings 1 to 16383 are reserved for standard events defined in<br>the Table 19.<br>Encodings 16384 to 32767 are for designated for custom use.<br>When eventID is changed, including to 0, the counter retains<br>its value. |
| 15    | DMASK     | RW        | When set to 1, partial matching of the DID_GSCID is performed<br>for the transaction. The lower bits of the DID_GSCID all the way<br>to the first low order 0 bit (including the 0 bit position itself) are<br>masked.                                                                                           |
| 35:16 | PID_PSCID | RW        | process_id if IDT is 0, PSCID if IDT is 1                                                                                                                                                                                                                                                                        |
| 59:36 | DID_GSCID | RW        | device_id if IDT is 0, GSCID if IDT is 1.                                                                                                                                                                                                                                                                        |
| 60    | PV_PSCV   | RW        | If set, only transactions with matching process_id or PSCID<br>(based on the Filter ID Type) are counted.                                                                                                                                                                                                        |
| 61    | DV_GSCV   | RW        | If set, only transactions with matching device_id or GSCID<br>(based on the Filter ID Type) are counted.                                                                                                                                                                                                         |
| 62    | IDT       | RW        | Filter ID Type: This field indicates the type of ID to filter on.<br>When 0, the DID_GSCID field holds a device_id and the<br>PID_PSCID field holds a process_id. When 1, the DID_GSCID<br>field holds a GSCID and PID_PSCID field holds a PSCID.                                                                |
| 63    | OF        | RW        | Overflow status or Interrupt disable                                                                                                                                                                                                                                                                             |

The table below summarizes the filtering option for events that support filtering by IDs.

*Table 17. filtering options*

| IDT | DV_GSCV | PV_PSCV | Operation                                                                                         |
|-----|---------|---------|---------------------------------------------------------------------------------------------------|
| 0/1 | 0       | 0       | Counter increments. No ID based filtering.                                                        |
| 0   | 0       | 1       | If the transaction has a valid process_id, counter increments if<br>process_id matches PID_PSCID. |
| 0   | 1       | 0       | Counter increments if device_id matches DID_GSCID.                                                |

| IDT | DV_GSCV | PV_PSCV | Operation                                                                                                                         |
|-----|---------|---------|-----------------------------------------------------------------------------------------------------------------------------------|
| 0   | 1       | 1       | If the transaction has a valid process_id, counter increments if<br>device_id matches DID_GSCID and process_id matches PID_PSCID. |
| 1   | 0       | 1       | If the transaction has a valid PSCID, counter increments if the PSCID of<br>that process matches PID_PSCID.                       |
| 1   | 1       | 0       | Counter increments if GSCID is valid and matches DID_GSCID.                                                                       |
| 1   | 1       | 1       | Counter increments if GSCID is valid and matches DID_GSCID and if<br>PSCID is valid and matches PID_PSCID.                        |

When filtering by device\_id or GSCID is selected and the event supports ID based filtering, the DMASK field can be used to configure a partial match. When DMASK is set to 1, partial matching of the DID\_GSCID is performed for the transaction. The lower bits of the DID\_GSCID all the way to the first low order 0 bit (including the 0 bit position itself) are masked.

The following example illustrates the use of DMASK and filtering by device\_id.

*Table 18.* DMASK *with* IDT *set to* device\_id *based filtering*

| DMASK | DID_GSCID                  | Comment                       |
|-------|----------------------------|-------------------------------|
| 0     | yyyyyyyy yyyyyyyy yyyyyyyy | One specific seg:bus:dev:func |
| 1     | yyyyyyyy yyyyyyyy yyyyy011 | seg:bus:dev - any func        |
| 1     | yyyyyyyy yyyyyyyy 01111111 | seg:bus - any dev:func        |
| 1     | yyyyyyyy 01111111 11111111 | seg - any bus:dev:func        |

The following table lists the standard events that can be counted:

*Table 19. Standard Events list*

<span id="page-82-0"></span>

| eventID   | Event counted                        | IDT settings supported |  |  |  |  |
|-----------|--------------------------------------|------------------------|--|--|--|--|
| 0         | Do not count                         |                        |  |  |  |  |
| 1         | Untranslated requests                | 0                      |  |  |  |  |
| 2         | Translated requests                  | 0                      |  |  |  |  |
| 3         | ATS Translation requests             | 0                      |  |  |  |  |
| 4         | TLB miss                             | 0/1                    |  |  |  |  |
| 5         | Device Directory Walks               | 0                      |  |  |  |  |
| 6         | Process Directory Walks              | 0                      |  |  |  |  |
| 7         | First-stage Page Table Walks         | 0/1                    |  |  |  |  |
| 8         | Second-stage Page Table Walks<br>0/1 |                        |  |  |  |  |
| 9 - 16383 | reserved for future standard         | -                      |  |  |  |  |

When the programmed IDT setting is not supported for an event then the associated counter does not increment.

The OF bit is set when the corresponding iohpmctr1-31 counter overflows, and remains set until cleared by software. Since iohpmctr1-31 values are unsigned values, overflow is defined as unsigned overflow. Note that there is no loss of information after an overflow since the counter wraps around and keeps counting while the sticky OF bit remains set.

If a iohpmctr1-31 counter overflows when the associated OF bit is zero, then a HPM Counter Overflow

interrupt is generated by setting ipsr.pmip bit to 1. If the OF bit is already one, then no interrupt request is generated. Consequently the OF bit also functions as a count overflow interrupt disable for the associated iohpmctr1-31.

![](_page_83_Picture_2.jpeg)

*There are not separate overflow status and overflow interrupt enable bits. In practice, enabling overflow interrupt generation (by clearing the* OF *bit) is done in conjunction with initializing the counter to a starting value. Once a counter has overflowed, it and the* OF *bit must be reinitialized before another overflow interrupt can be generated.*

*In RV32, memory-mapped writes to* iohpmevt1-31 *modify only one 32-bit part of the register. The following sequence may be used to update the register without counting events spuriously due to the intermediate value of the register:*

![](_page_83_Picture_5.jpeg)

- ⚫ *Write the low order 32-bits to set* eventID *to 0.*
- ⚫ *Write the high order 32-bits with the new desired values.*
- ⚫ *Write the low order 32-bits the new desired values, including that of the* eventID *field.*

*Alternatively, the counter may first be inhibited such that no events count during the update and the inhibit removed after the register has been programmed with the desired value.*

![](_page_83_Picture_10.jpeg)

*If* capabilities.HPM *is 1 then a minimum of one programmable event counter besides the cycles counter is required to comply with this specification. One counter may be used in a time multiplexed manner to sample events but such analysis may take longer to complete. The IOMMU, unlike the CPU MMU, services multiple streams of IO and the HPM may be used by a performance analyst to analyze one or more of those streams concurrently. Typically, a performance analyst may require four programmable counters to count events for an IO stream. To support concurrent analysis of at least two streams of IO it is recommended to support seven programmable counters.*

# <span id="page-83-0"></span>6.24. Translation-request IOVA (**tr\_req\_iova**)

The tr\_req\_iova is a 64-bit register used to implement a translation-request interface for debug. This register is present when capabilities.DBG == 1.

![](_page_83_Figure_14.jpeg)

*Figure 56. Translation-request IOVA register fields*

| Bits  | Field    | Attribute | Description                  |  |  |
|-------|----------|-----------|------------------------------|--|--|
| 11:0  | reserved | WPRI      | Reserved for standard use    |  |  |
| 63:12 | vpn      | WARL      | The IOVA virtual page number |  |  |

# <span id="page-83-1"></span>6.25. Translation-request control (**tr\_req\_ctl**)

The tr\_req\_ctl is a 64-bit WARL register used to implement a translation-request interface for debug. This register is present when capabilities.DBG == 1.

![](_page_84_Figure_1.jpeg)

*Figure 57. Translation-request control register fields*

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                      |  |
|-------|----------|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--|
| 0     | Go/Busy  | RW1S      | This bit is set to indicate a valid request has been setup in the<br>tr_req_iova/tr_req_ctl registers for the IOMMU to translate.<br>The IOMMU indicates completion of the requested translation by clearing<br>this bit to 0. On completion, the results of the translation are in the<br>tr_response register. |  |
| 1     | Priv     | WARL      | If set to 1, Privileged Mode access is requested else no Privileged Mode access<br>is not requested.                                                                                                                                                                                                             |  |
| 2     | Exe      | WARL      | If set to 1, execute permission is requested else execute permission is not<br>requested.                                                                                                                                                                                                                        |  |
| 3     | NW       | WARL      | If set to 1, read permission is requested. If set to 0, both read and write<br>permissions are requested.                                                                                                                                                                                                        |  |
| 11:4  | reserved | WPRI      | Reserved for standard use                                                                                                                                                                                                                                                                                        |  |
| 31:12 | PID      | WARL      | If PV is 1, this field provides the process_id input for this translation<br>request. If PV is 0 then this field is not used.                                                                                                                                                                                    |  |
| 32    | PV       | WARL      | If set to 1, the PID field of the register is valid and provides the process_id<br>for this translation request. If set to 0 then the PID field is not used and a<br>process_id is not valid for this translation request.                                                                                       |  |
| 35:33 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                                                                                       |  |
| 39:36 | custom   | WPRI      | Designated for custom use.                                                                                                                                                                                                                                                                                       |  |
| 63:40 | DID      | WARL      | This field provides the device_id for this translation request.                                                                                                                                                                                                                                                  |  |

![](_page_84_Picture_4.jpeg)

*In RV32, the high half of the register should be written first, followed by the low half, which includes the* Go/Busy *bit, to initiate a translation.*

# <span id="page-84-0"></span>6.26. Translation-response (**tr\_response**)

The tr\_response is a 64-bit RO register used to hold the results of a translation requested using the translation-request interface. This register is present when capabilities.DBG == 1.

![](_page_84_Figure_8.jpeg)

*Figure 58. Translation-response register fields*

| Bits  | Field    | Attribute | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |                                                         |  |         |  |
|-------|----------|-----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|--|---------|--|
| 0     | fault    | RO        | If the process to translate the IOVA detects a fault then the fault field is set<br>to 1. The detected fault may be reported through the fault-queue.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |                                                         |  |         |  |
| 6:1   | reserved | RO        | Reserved for standard use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |                                                         |  |         |  |
| 8:7   | PBMT     | RO        | Memory type determined for the translation using the PBMT fields in the<br>first-stage and/or the second-stage page tables used for the translation. This<br>value of this field is UNSPECIFIED if the fault field is 1.                                                                                                                                                                                                                                                                                                                                                                                                                                            |                                                         |  |         |  |
| 9     | S        | RO        | Translation range size field, when set to 1 indicates that the translation applies<br>to a range that is larger than 4 KiB and the size of the translation range is<br>encoded in the PPN field. The value of this field is UNSPECIFIED if the fault<br>field is 1.                                                                                                                                                                                                                                                                                                                                                                                                 |                                                         |  |         |  |
| 53:10 | PPN      | RO        | If the fault bit is 0, then this field provides the PPN determined as a result<br>of translating the vpn in tr_req_iova.<br>If the fault bit is 1, then the value of this field is UNSPECIFIED.<br>If the S bit is 0, then the size of the translation is 4 KiB - a page.<br>If the S bit is 1, then the translation resulted in a superpage, and the size of the<br>superpage is encoded in the PPN itself. If scanning from bit position 0 to bit<br>position 43, the first bit with a value of 0 at position X, then the superpage size<br>X+1 * 4 KiB.<br>is 2<br>If X is not 0, then all bits at position 0 through X-1 are each encoded with a<br>value of 1. |                                                         |  |         |  |
|       |          |           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Table 20. Example of encoding of super page size in PPN |  |         |  |
|       |          |           | Size<br>PPN<br>S                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |                                                         |  |         |  |
|       |          |           | 0 4 KiB<br>yyyyyyyy yyyy yyyy<br>1 64 KiB<br>yyyyyyyy yyyy 0111<br>1 2 MiB<br>yyyyyyy0 1111 1111                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |                                                         |  |         |  |
|       |          |           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |                                                         |  |         |  |
|       |          |           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |                                                         |  |         |  |
|       |          |           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | yyyyyy01 1111 1111                                      |  | 1 4 MiB |  |
| 59:54 | reserved | RO        | Reserved for standard use.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |                                                         |  |         |  |
| 63:60 | custom   | RO        | Designated for custom use.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |                                                         |  |         |  |

![](_page_85_Picture_2.jpeg)

*An IOMMU implementation is not required to report a superpage translation or support reporting all possible superpage sizes. An implementation is allowed to report a 4 KiB translation corresponding to the requested* vpn *or report a translation size that is smaller than the superpage size configured in the page tables.*

### <span id="page-85-0"></span>6.27. IOMMU QoS ID (**iommu\_qosid**)

The iommu\_qosid register fields are defined as follows:

![](_page_85_Figure_6.jpeg)

*Figure 59.* iommu\_qosid *register fields*

| Bits  | Field    | Attribute | Description                        |
|-------|----------|-----------|------------------------------------|
| 11:0  | RCID     | WARL      | RCID for IOMMU-initiated requests. |
| 15:12 | reserved | WPRI      | Reserved for standard use.         |
| 27:16 | MCID     | WARL      | MCID for IOMMU-initiated requests. |
| 31:28 | reserved | WPRI      | Reserved for standard use.         |

IOMMU-initiated requests for accessing the following data structures use the value programmed in the RCID and MCID fields of the iommu\_qosid register.

- ⚫ Device directory table (DDT)
- ⚫ Fault queue (FQ)
- ⚫ Command queue (CQ)
- ⚫ Page-request queue (PQ)
- ⚫ IOMMU-initiated MSI (Message-signaled interrupts)

When ddtp.iommu\_mode == Bare, all device-originated requests are associated with the QoS IDs configured in the iommu\_qosid register.

# <span id="page-86-0"></span>6.28. Interrupt-cause-to-vector register (**icvec**)

Interrupt-cause-to-vector register maps a cause to a vector. All causes can be mapped to the same vector or a cause can be given a unique vector.

The vector is used:

- 1. By an IOMMU that generates interrupts as MSIs, to index into MSI configuration table (msi\_cfg\_tbl) to determine the MSI to generate. An IOMMU is capable of generating interrupts as a MSI if capabilities.IGS==MSI or if capabilities.IGS==BOTH. When capabilities.IGS==BOTH the IOMMU may be configured to generate interrupts as MSI by setting fctl.WSI to 0.
- 2. By an IOMMU that generates WSI, to determine the wire to signal the interrupt. An IOMMU is capable of generating wire-signaled- interrupts if capabilities.IGS==WSI or if capabilities.IGS==BOTH. When capabilities.IGS==BOTH the IOMMU may be configured to generate wire-signaled- interrupts by setting fctl.WSI to 1.

If an implementation only supports a single vector then all bits of this register may be hardwired to 0 (WARL). Likewise if only two vectors are supported then only bit 0 for each cause could be writable.

![](_page_86_Figure_15.jpeg)

*Figure 60. Interrupt-cause-to-vector register fields*

| Bits | Field | Attribute | Description                                                                                               |
|------|-------|-----------|-----------------------------------------------------------------------------------------------------------|
| 3:0  | civ   | WARL      | The command-queue-interrupt-vector (civ) is the vector number assigned to<br>the command-queue-interrupt. |

| Bits  | Field    | Attribute | Description                                                                                                                  |
|-------|----------|-----------|------------------------------------------------------------------------------------------------------------------------------|
| 7:4   | fiv      | WARL      | The fault-queue-interrupt-vector (fiv) is the vector number assigned to the<br>fault-queue-interrupt.                        |
| 11:8  | pmiv     | WARL      | The performance-monitoring-interrupt-vector (pmiv) is the vector number<br>assigned to the performance-monitoring-interrupt. |
| 15:12 | piv      | WARL      | The page-request-queue-interrupt-vector (piv) is the vector number assigned<br>to the page-request-queue-interrupt.          |
| 31:16 | reserved | WPRI      | Reserved for standard use.                                                                                                   |
| 63:32 | custom   | WPRI      | Designated for custom use.                                                                                                   |

# <span id="page-87-0"></span>6.29. MSI configuration table (**msi\_cfg\_tbl**)

An IOMMU that supports generating IOMMU-originated interrupts (i.e., capabilities.IGS == MSI or capabilities.IGS == BOTH) as MSIs implements a MSI configuration table that is indexed by the vector from icvec to determine a MSI table entry. Each MSI table entry for interrupt vector x has three registers msi\_addr\_x, msi\_data\_x, and msi\_vec\_ctl\_x. These registers are hardwired to 0 if capabilities.IGS == WSI.

If an access fault is detected on a MSI write using msi\_addr\_x, then the IOMMU reports a "IOMMU MSI write access fault" (cause 273) fault, with TTYP set to 0 and iotval set to the value of msi\_addr\_x.

*Table 21. MSI configuration table structure*

| bit 63                   |                          | bit 0 Byte Offset |  |  |  |  |  |  |
|--------------------------|--------------------------|-------------------|--|--|--|--|--|--|
| Entry 0: Message address |                          |                   |  |  |  |  |  |  |
| Entry 0: Vector Control  | Entry 0: Message Data    | +008h             |  |  |  |  |  |  |
|                          | Entry 1: Message address |                   |  |  |  |  |  |  |
| Entry 1: Vector Control  | Entry 1: Message Data    | +018h             |  |  |  |  |  |  |
|                          | …                        | +020h             |  |  |  |  |  |  |

| 63 |          |    | 56 | 55 |  |   |   |    |     |   |   |     |   |  |   |   |  |   |   | 32 |
|----|----------|----|----|----|--|---|---|----|-----|---|---|-----|---|--|---|---|--|---|---|----|
|    | reserved | į. |    |    |  |   |   |    |     |   |   | ADD | R |  |   |   |  |   |   |    |
| 31 |          |    |    |    |  | • | • | •  |     | • | • |     |   |  | • | • |  | 2 | 1 | 0  |
|    |          |    |    |    |  |   |   | AI | DDR |   |   |     |   |  |   |   |  |   |   | 0  |

*Figure 61. Message address register fields*

| Bits  | Field    | Attribute | Description                           |
|-------|----------|-----------|---------------------------------------|
| 1:0   | 0        | RO        | Fixed to 0                            |
| 55:2  | ADDR     | WARL      | Holds the 4-byte aligned MSI address. |
| 63:56 | reserved | WPRI      | Reserved for standard use.            |

![](_page_87_Figure_10.jpeg)

*Figure 62. Message data register fields*

| Bits | Field | Attribute | Description        |
|------|-------|-----------|--------------------|
| 31:0 | data  | WARL      | Holds the MSI data |

| 31 |      |      |      |      |      |      |               |    |      |     |      |      |      |  |       |                   |      | 1 | 0 |        |
|----|------|------|------|------|------|------|---------------|----|------|-----|------|------|------|--|-------|-------------------|------|---|---|--------|
|    | <br> | <br> | <br> | <br> | <br> | <br> | $\overline{}$ |    | -    |     | <br> | <br> | <br> |  | <br>_ | <br>$\overline{}$ | <br> |   |   | $\neg$ |
|    |      |      |      |      |      |      |               | re | eser | ved |      |      |      |  |       |                   |      |   | М |        |
|    | <br> | <br> | <br> | <br> | <br> | <br> |               |    |      |     | <br> | <br> | <br> |  | <br>  | <br>              | <br> |   |   |        |

*Figure 63. Vector control register fields*

| Bits | Field    | Attribute | Description                                                                                                                                                                                                                                          |
|------|----------|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0    | M        | RW        | When the mask bit M is 1, the corresponding interrupt vector is masked and<br>the IOMMU is prohibited from sending the associated message. Pending<br>messages for that vector are later generated if the corresponding mask bit is<br>cleared to 0. |
| 31:1 | reserved | WPRI      | Reserved for standard use.                                                                                                                                                                                                                           |
