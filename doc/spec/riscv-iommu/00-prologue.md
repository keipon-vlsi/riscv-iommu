![](_page_0_Picture_0.jpeg)

# RISC-V IOMMU Architecture Specification

Version v1.0.1, 2025-08-28: Ratified

# **Table of Contents**

| Preamble                                                                  | 1  |
|---------------------------------------------------------------------------|----|
| Copyright and license information                                         | 2  |
| Contributors                                                              | 3  |
| 1. Preface                                                                | 4  |
| 2. Introduction                                                           | 6  |
| 2.1. Glossary                                                             | 8  |
| 2.2. Usage models                                                         | 10 |
| 2.2.1. Non-virtualized OS                                                 | 10 |
| 2.2.2. Hypervisor                                                         | 11 |
| 2.2.3. Guest OS                                                           | 12 |
| 2.3. Placement and data flow                                              | 13 |
| 2.4. IOMMU features                                                       | 17 |
| 3. Data Structures                                                        | 18 |
| 3.1. Device-Directory-Table (DDT)                                         | 19 |
| 3.1.1. Non-leaf DDT entry                                                 | 20 |
| 3.1.2. Leaf DDT entry                                                     | 21 |
| 3.1.3. Device-context fields                                              |    |
| 3.1.3.1. Translation control (tc)                                         | 22 |
| 3.1.3.2. IO hypervisor guest address translation and protection (iohgatp) | 24 |
| 3.1.3.3. Translation attributes (ta)                                      | 25 |
| 3.1.3.4. First-Stage context (fsc)                                        | 25 |
| 3.1.3.5. MSI page table pointer (msiptp)                                  | 27 |
| 3.1.3.6. MSI address mask (msi_addr_mask) and pattern (msi_addr_pattern)  | 28 |
| 3.1.4. Device-context configuration checks                                | 28 |
| 3.2. Process-Directory-Table (PDT)                                        | 30 |
| 3.2.1. Non-leaf PDT entry                                                 | 30 |
| 3.2.2. Leaf PDT entry                                                     | 30 |
| 3.2.3. Process-context fields                                             | 31 |
| 3.2.3.1. Translation attributes (ta)                                      | 31 |
| 3.2.3.2. First-Stage context (fsc)                                        | 31 |
| 3.2.4. Process-context configuration checks                               | 32 |
| 3.3. Process to translate an IOVA                                         |    |
| 3.3.1. Process to locate the Device-context                               | 35 |
| 3.3.2. Process to locate the Process-context                              | 35 |
| 3.3.3. Process to translate addresses of MSIs                             | 36 |
| 3.4. IOMMU updating of PTE accessed (A) and dirty (D) updates             | 38 |
| 3.5. Faults from virtual address translation process                      | 39 |
| 3.6. PCIe ATS translation request handling                                | 39 |
| 3.7. PCIe ATS Page Request handling                                       |    |
| 3.8. Caching in-memory data structures                                    |    |
| 3.9. Updating in-memory data structure entries                            |    |
| 3.10. Endianness of in-memory data structures                             |    |
| 4. In-memory queue interface                                              | 45 |

| 4.1. Command-Queue (CQ)                                           | 46 |
|-------------------------------------------------------------------|----|
| 4.1.1. IOMMU Page-Table cache invalidation commands               | 47 |
| 4.1.2. IOMMU Command-queue Fence commands                         | 49 |
| 4.1.3. IOMMU directory cache invalidation commands                | 50 |
| 4.1.4. IOMMU PCIe ATS commands                                    | 51 |
| 4.2. Fault/Event-Queue (FQ)                                       | 53 |
| 4.3. Page-Request-Queue (PQ)                                      | 56 |
| 5. Debug support                                                  | 58 |
| 6. Memory-mapped register interface                               | 59 |
| 6.1. Register layout                                              | 59 |
| 6.2. Reset behavior                                               | 60 |
| 6.3. IOMMU capabilities (capabilities)                            | 60 |
| 6.4. Features-control register (fctl)                             | 63 |
| 6.5. Device-directory-table pointer (ddtp)                        | 64 |
| 6.6. Command-queue base (cqb)                                     | 65 |
| 6.7. Command-queue head (cqh)                                     |    |
| 6.8. Command-queue tail (cqt)                                     | 66 |
| 6.9. Fault queue base (fqb)                                       | 66 |
| 6.10. Fault queue head (fqh)                                      |    |
| 6.11. Fault queue tail (fqt)                                      | 67 |
| 6.12. Page-request-queue base (pqb)                               | 68 |
| 6.13. Page-request-queue head (pqh)                               | 68 |
| 6.14. Page-request-queue tail (pqt)                               | 69 |
| 6.15. Command-queue CSR (cqcsr)                                   | 70 |
| 6.16. Fault queue CSR (fqcsr)                                     | 72 |
| 6.17. Page-request-queue CSR (pqcsr)                              | 73 |
| 6.18. Interrupt pending status register (ipsr)                    | 74 |
| 6.19. Performance-monitoring counter overflow status (iocountovf) | 76 |
| 6.20. Performance-monitoring counter inhibits (iocountinh)        | 76 |
| 6.21. Performance-monitoring cycles counter (iohpmcycles)         |    |
| 6.22. Performance-monitoring event counters (iohpmctr1-31)        | 77 |
| 6.23. Performance-monitoring event selectors (iohpmevt1-31)       |    |
| 6.24. Translation-request IOVA (tr_req_iova)                      | 80 |
| 6.25. Translation-request control (tr_req_ctl)                    |    |
| 6.26. Translation-response (tr_response)                          |    |
| 6.27. IOMMU QoS ID (iommu_qosid)                                  |    |
| 6.28. Interrupt-cause-to-vector register (icvec)                  |    |
| 6.29. MSI configuration table (msi_cfg_tbl)                       |    |
| 7. Software guidelines                                            |    |
| 7.1. Reading and writing IOMMU registers                          |    |
| 7.2. Guidelines for initialization                                |    |
| 7.3. Guidelines for invalidations                                 |    |
| 7.3.1. Changing device directory table entry                      |    |
| 7.3.2. Changing process directory table entry                     |    |
| 7.3.3. Changing MSI page table entry                              |    |
|                                                                   |    |

| 7.3.4. Changing second-stage page table entry                    | 89  |
|------------------------------------------------------------------|-----|
| 7.3.5. Changing first-stage page table entry                     | 90  |
| 7.3.6. Accessed (A)/Dirty (D) bit updates and page promotions    | 91  |
| 7.3.7. Device Address Translation Cache invalidations            | 91  |
| 7.3.8. Caching invalid entries                                   | 92  |
| 7.3.9. Guidelines for emulating an IOMMU                         | 92  |
| 7.4. Reconfiguring PMAs                                          | 92  |
| 7.5. Guidelines for handling interrupts from IOMMU               | 92  |
| 7.6. Guidelines for enabling and disabling ATS and/or PRI        | 93  |
| 8. Hardware guidelines                                           | 95  |
| 8.1. Integrating an IOMMU as a PCIe device                       | 95  |
| 8.2. Faults from PMA and PMP                                     | 95  |
| 8.3. Aborting transactions                                       | 95  |
| 8.4. Reliability, Availability, and Serviceability (RAS)         | 95  |
| 9. IOMMU Extensions                                              | 97  |
| 9.1. Quality-of-Service (QoS) Identifiers Extension, Version 1.0 | 97  |
| 9.1.1. Reset Behavior                                            | 97  |
| 9.1.2. Sizing QoS Identifiers                                    | 98  |
| 9.1.3. IOMMU ATC Capacity Allocation and Monitoring              | 98  |
| 9.2. Non-leaf PTE Invalidation Extension, Version 1.0            | 99  |
| 9.2.1. Non-leaf PTE Invalidation by IOTINVAL.VMA                 | 99  |
| 9.2.2. Non-leaf PTE Invalidation by IOTINVAL.GVMA                | 99  |
| 9.3. Address Range Invalidation Extension, Version 1.0           | 101 |
| 9.4. PTE Reserved-for-Software Bits 60-59, Version 1.0           |     |
| Bibliography                                                     | 103 |
