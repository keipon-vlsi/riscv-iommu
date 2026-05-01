# <span id="page-100-0"></span>Chapter 9. IOMMU Extensions

This chapter specifies the following standard extensions to the IOMMU Base Architecture:

| Specification                                  | Version | Status   |
|------------------------------------------------|---------|----------|
| Quality-of-Service (QoS) Identifiers Extension | 1.0     | Ratified |
| Non-leaf PTE Invalidation Extension            | 1.0     | Ratified |
| Address Range Invalidation Extension           | 1.0     | Ratified |
| PTE Reserved-for-Software Bits 60-59           | 1.0     | Ratified |

# <span id="page-100-1"></span>9.1. Quality-of-Service (QoS) Identifiers Extension, Version 1.0

Quality of Service (QoS) is defined as the minimal end-to-end performance guaranteed in advance by a service level agreement (SLA) to a workload. Performance metrics might include measures such as instructions per cycle (IPC), latency of service, etc.

When multiple workloads execute concurrently on modern processors — equipped with large core counts, multiple cache hierarchies, and multiple memory controllers — the performance of any given workload becomes less deterministic, or even non-deterministic, due to shared resource contention [[9](#page-106-9)].

To manage performance variability, system software needs resource allocation and monitoring capabilities. These capabilities allow for the reservation of resources like cache and bandwidth, thus meeting individual performance targets while minimizing interference [[10](#page-106-10)]. For resource management, hardware should provide monitoring features that allow system software to profile workload resource consumption and allocate resources accordingly.

To facilitate this, the QoS Identifiers ISA extension (Ssqosid) [[11](#page-106-11)] introduces the srmcfg register, which configures a hart with two identifiers: a Resource Control ID (RCID) and a Monitoring Counter ID (MCID). These identifiers accompany each request issued by the hart to shared resource controllers.

These identifiers are crucial for the RISC-V Capacity and Bandwidth Controller QoS Register Interface [[12\]](#page-106-12), which provides methods for setting resource usage limits and monitoring resource consumption. The RCID controls resource allocations, while the MCID is used for tracking resource usage.

The IOMMU QoS ID extension provides a method to associate QoS IDs with requests to access resources by the IOMMU, as well as with devices governed by it. This complements the Ssqosid extension that provides a method to associate QoS IDs with requests originated by the RISC-V harts. Assocating QoS IDs with device and IOMMU originated requests is required for effective monitoring and allocation of shared resources.

The IOMMU capabilities register ([Section 6.3](#page-63-1)) is extended with a QOSID field which enumerates support for associating QoS IDs with requests made through the IOMMU. When capabilities.QOSID is 1, the memory-mapped register layout is extended to add a register named iommu\_qosid ([Section 6.27\)](#page-85-0). This register is used to configure the Quality of Service (QoS) IDs associated with IOMMU-originated requests. The ta field of the device context [\(Section 3.1.3.3](#page-28-0)) is extended with two fields, RCID and MCID, to configure the QoS IDs to associate with requests originated by the devices.

# <span id="page-100-2"></span>9.1.1. Reset Behavior

If the reset value for ddtp.iommu\_mode field is Bare, then the iommu\_qosid.RCID field must have a reset value of 0.

![](_page_101_Picture_1.jpeg)

*At reset, it is required that the* RCID *field of* iommu\_qosid *is set to 0 if the IOMMU is in* Bare *mode, as typically the resource controllers in the SoC default to a reset behavior of associating all capacity or bandwidth to the* RCID *value of 0. When the reset value of the* ddtp.iommu\_mode *is not* Bare*, the* iommu\_qosid *register should be initialized by software before changing the mode to allow DMA.*

### <span id="page-101-0"></span>9.1.2. Sizing QoS Identifiers

The size (or width) of RCID and MCID, as fields in registers or in data structures, supported by the IOMMU must be at least as large as that supported by any RISC-V application processor hart in the system.

### <span id="page-101-1"></span>9.1.3. IOMMU ATC Capacity Allocation and Monitoring

Some IOMMUs might support capacity allocation and usage monitoring in the IOMMU address translation cache (IOATC) by implementing the capacity controller register interface.

Additionally, some IOMMUs might support multiple IOATCs, each potentially having different capacities. In scenarios where multiple IOATCs are implemented, such as an IOATC for each supported page size, the IOMMU can implement a capacity controller register interface for each IOATC to facilitate individual capacity allocation.

### <span id="page-102-0"></span>9.2. Non-leaf PTE Invalidation Extension, Version 1.0

The RISC-V IOMMU Version 1.0 specification provides commands to invalidate leaf page table entries from address translation caches when performing an address-specific invalidation operation. The non-leaf PTE invalidation extension provides commands to optionally also invalidate non-leaf PTE entries from the address translation caches when performing an address-specific invalidation operation.

The non-leaf PTE invalidation extension is implemented if the capabilities.NL (bit 42) is 1. When the capabilities.NL bit is 1, a non-leaf (NL) field is defined at bit 34 in the IOTINVAL.VMA and IOTINVAL.GVMA commands by this extension. When the capabilities.NL bit is 0, bit 34 remains reserved.

![](_page_102_Picture_4.jpeg)

*The non-leaf PTE invalidation extension enables optimizations in shared virtual addressing use cases by providing the ability to invalidate non-leaf PTEs corresponding to the IOVA being invalidated from the IOMMU address translation caches.*

If the address range invalidation extension is also implemented, the NL operand applies to the address range determined by the ADDR and S operands.

### <span id="page-102-1"></span>9.2.1. Non-leaf PTE Invalidation by **IOTINVAL.VMA**

- ⚫ When the AV operand is 0, the NL operand is ignored and the IOTINVAL.VMA command operations are as specified in RISC-V IOMMU Version 1.0 specification.
- ⚫ When the AV operand is 1 and the NL operand is 0, the IOTINVAL.VMA command operations are as specified in RISC-V IOMMU Version 1.0 specification.
- ⚫ When both the AV and NL operands are 1, the IOTINVAL.VMA command performs the following operations:
  - ⚫ When GV=0 and PSCV=0: Invalidates information cached from all levels of first-stage page table entries corresponding to the IOVA in the ADDR operand for all host address spaces, including entries containing global mappings.
  - ⚫ When GV=0 and PSCV=1: Invalidates information cached from all levels of first-stage page table entries corresponding to the IOVA in the ADDR operand and the host address space identified by the PSCID operand, except for entries containing global mappings.
  - ⚫ When GV=1 and PSCV=0: Invalidates information cached from all levels of first-stage page table entries corresponding to the IOVA in the ADDR operand for all VM address spaces associated with the GSCID operand, including entries that contain global mappings.
  - ⚫ When GV=1 and PSCV=1: Invalidates information cached from all levels of first-stage page table entries corresponding to the IOVA in the ADDR operand and the VM address space identified by the PSCID and GSCID operands, except for entries containing global mappings.

### <span id="page-102-2"></span>9.2.2. Non-leaf PTE Invalidation by **IOTINVAL.GVMA**

- ⚫ When the GV operand is 0, both the AV and NL operands are ignored and the IOTINVAL.GVMA command operations are as specified in RISC-V IOMMU Version 1.0 specification.
- ⚫ When the GV operand is 1 and the AV operand is 0, the NL operand is ignored and the IOTINVAL.GVMA command operations are as specified in RISC-V IOMMU Version 1.0 specification.
- ⚫ When the GV and AV operands are 1 and the NL operand is 0, the IOTINVAL.GVMA command operations are as specified in RISC-V IOMMU Version 1.0 specification.
- ⚫ When GV, AV, and NL are all 1, the IOTINVAL.GVMA command performs the following operations:
  - ⚫ Invalidates information cached from all levels of second-stage page table entries corresponding to

| the guest-physical address in the ADDR operand and the VM address spaces identified by the GSCID<br>operand. |
|--------------------------------------------------------------------------------------------------------------|
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |
|                                                                                                              |

### <span id="page-104-0"></span>9.3. Address Range Invalidation Extension, Version 1.0

The address range invalidation extension enables specifying a range of addresses in an IOMMU ATC invalidation command, reducing the number of commands queued to the IOMMU. This facility is especially useful when superpages are employed in page tables.

The address range invalidation extension is implemented if capabilities.S (bit 43) is 1. When capabilities.S is 1, a range-size (S) operand is defined at bit 73 in the IOTINVAL.VMA and IOTINVAL.GVMA commands by this extension. When the capabilities.S bit is 0, bit 73 remains reserved.

When the GV operand is 0, both the AV and S operands are ignored by the IOTINVAL.GVMA command. When the AV operand is 0, the S operand is ignored in both the IOTINVAL.VMA and IOTINVAL.GVMA commands. When the S operand is ignored or set to 0, the operations of the IOTINVAL.VMA and IOTINVAL.GVMA commands are as specified in the RISC-V IOMMU Version 1.0 specification.

When the S operand is not ignored and is 1, the ADDR operand represents a NAPOT range encoded in the operand itself. Starting from bit position 0 of the ADDR operand, if the first 0 bit is at position X, the range size is 2 (X+1) \* 4 KiB. When X is 0, the size of the range is 8 KiB.

If the S operand is not ignored and is 1 and all bits of the ADDR operand are 1, the behavior is UNSPECIFIED.

If the S operand is not ignored and is 1 and the most significant bit of the ADDR operand is 0 while all other bits are 1, the specified address range covers the entire address space.

![](_page_104_Picture_8.jpeg)

*The NAPOT range encoding used by this extension follows the convention used by PCIe ATS Invalidation Requests to denote address ranges. This convention is also used to encode the translation range size in* tr\_response *([Section 6.26\)](#page-84-0) register.*

*Simpler implementations may invalidate all address-translation cache entries when the* S *bit is set to 1.*

# <span id="page-105-0"></span>9.4. PTE Reserved-for-Software Bits 60-59, Version 1.0

| The Svrsw60t59b extension is implemented if capabilities.Svrsw60t59b (bit 14) is set to 1. |
|--------------------------------------------------------------------------------------------|
                                                                           

# <span id="page-106-0"></span>Bibliography

- <span id="page-106-1"></span>[1] "Clarification updates to IOMMU v06252025." [Online]. Available: [github.com/riscv-non-isa/riscv](https://github.com/riscv-non-isa/riscv-iommu/pull/569/commits)[iommu/pull/569/commits](https://github.com/riscv-non-isa/riscv-iommu/pull/569/commits).
- <span id="page-106-2"></span>[2] "Clarification updates to IOMMU v1.0.1." [Online]. Available: [github.com/riscv-non-isa/riscv-iommu/](https://github.com/riscv-non-isa/riscv-iommu/pull/441/commits) [pull/441/commits.](https://github.com/riscv-non-isa/riscv-iommu/pull/441/commits)
- <span id="page-106-3"></span>[3] "Clarification updates to IOMMU v1.0.0." [Online]. Available: [github.com/riscv-non-isa/riscv-iommu/](https://github.com/riscv-non-isa/riscv-iommu/pull/243/commits) [pull/243/commits](https://github.com/riscv-non-isa/riscv-iommu/pull/243/commits).
- <span id="page-106-4"></span>[4] "PCI Express® Base Specification Revision 6.0." [Online]. Available: [pcisig.com/pci-express-6.0](https://pcisig.com/pci-express-6.0-specification) [specification.](https://pcisig.com/pci-express-6.0-specification)
- <span id="page-106-5"></span>[5] "RISC-V Advanced Interrupt Architecture." [Online]. Available: [github.com/riscv/riscv-aia.](https://github.com/riscv/riscv-aia)
- <span id="page-106-6"></span>[6] "RISC-V Instruction Set Manual, Volume II: Privileged Architecture." [Online]. Available: [github.com/](https://github.com/riscv/riscv-isa-manual) [riscv/riscv-isa-manual](https://github.com/riscv/riscv-isa-manual).
- <span id="page-106-7"></span>[7] "RISC-V Shadow Stacks and Landing Pads." [Online]. Available: [github.com/riscv/riscv-cfi.](https://github.com/riscv/riscv-cfi)
- <span id="page-106-8"></span>[8] "PCI Code and ID Assignment Specification Revision 1.1." [Online]. Available: [pcisig.com/sites/default/](https://pcisig.com/sites/default/files/files/PCI_Code-ID_r_1_11__v24_Jan_2019.pdf) [files/files/PCI\\_Code-ID\\_r\\_1\\_11\\_\\_v24\\_Jan\\_2019.pdf.](https://pcisig.com/sites/default/files/files/PCI_Code-ID_r_1_11__v24_Jan_2019.pdf)
- <span id="page-106-9"></span>[9] K. Du Bois, S. Eyerman, and L. Eeckhout, "Per-Thread Cycle Accounting in Multicore Processors," *ACM Trans. Archit. Code Optim.*, vol. 9, no. 4, Jan. 2013, doi: 10.1145/2400682.2400688.
- <span id="page-106-10"></span>[10] D. Lo, L. Cheng, R. Govindaraju, P. Ranganathan, and C. Kozyrakis, "Heracles: Improving Resource Efficiency at Scale," in *Proceedings of the 42nd Annual International Symposium on Computer Architecture*, New York, NY, USA, 2015, pp. 450–462, doi: 10.1145/2749469.2749475.
- <span id="page-106-11"></span>[11] "RISC-V Quality-of-Service (QoS) Identifiers." [Online]. Available: [github.com/riscv/riscv-ssqosid](https://github.com/riscv/riscv-ssqosid).
- <span id="page-106-12"></span>[12] "RISC-V Capacity and Bandwidth QoS Register Interface." [Online]. Available: [github.com/riscv-non](https://github.com/riscv-non-isa/riscv-cbqri)[isa/riscv-cbqri.](https://github.com/riscv-non-isa/riscv-cbqri)