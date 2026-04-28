# <span id="page-7-0"></span>Chapter 1. Preface

# *Preface to Version 20250828*

This document describes the RISC-V IOMMU architecture. This release, version 20250828, includes the following versions of the RISC-V IOMMU Base Architecture specification and standard extensions:

| Specification                                  | Version | Status   |
|------------------------------------------------|---------|----------|
| RISC-V IOMMU Base Architecture Specification   | 1.0     | Ratified |
| Quality-of-Service (QoS) Identifiers Extension | 1.0     | Ratified |
| Non-leaf PTE Invalidation Extension            | 1.0     | Ratified |
| Address Range Invalidation Extension           | 1.0     | Ratified |
| PTE Reserved-for-Software Bits 60-59           | 1.0     | Ratified |

The following backward-compatible changes—comprising a set of clarifications and corrections—have been made since version 20250620:

- ⚫ Corrected typographic errors and made editorial updates.
- ⚫ Clarified the types of faults that may be caused by G-stage due to implicit PDT accesses.
- ⚫ Updated the software guideline indicating that wired-signaled interrupts are supported when IGS is either WSI or BOTH.
- ⚫ Clarified that ATS Translation responses with U=1 include the granted permissions.
- ⚫ Clarified that MSI PTEs do not include A/D bits, but these bits may be assumed to be 1.
- ⚫ Included definitions for TLB and Walk in the Glossary.

The following change has been made which, while not strictly backwards compatible, is not expected to cause software portability issues in practice:

⚫ While the MSI address mask and pattern fields are 52 bits wide, any bits beyond the maximum GPA width supported by the IOMMU are reserved for future standard use.

These changes were made through PR#569, [[1\]](#page-106-1).

# *Preface to Version 20250620*

This document describes the RISC-V IOMMU architecture. This release, version 20250620, includes the following versions of the RISC-V IOMMU Base Architecture specification and standard extensions:

| Specification                                  | Version | Status   |
|------------------------------------------------|---------|----------|
| RISC-V IOMMU Base Architecture Specification   | 1.0     | Ratified |
| Quality-of-Service (QoS) Identifiers Extension | 1.0     | Ratified |
| Non-leaf PTE Invalidation Extension            | 1.0     | Ratified |
| Address Range Invalidation Extension           | 1.0     | Ratified |

The following backward-compatible changes—comprising a set of clarifications and corrections—have been made since version 20240901:

- ⚫ Typographic errors have been corrected, and editorial updates have been made.
- ⚫ Clarified that the translation size is implementation-defined when both stages are bare.
- ⚫ Clarified that the size of a queue is one less than the number of its entries.

These changes were made through PR#441, [[2\]](#page-106-2).

# *Preface to Version 20240901*

Chapters 2 through 8 of this document form the RISC-V IOMMU Base Architecture Specification. Chapter 9 includes the standard extensions to the base architecture. This release, version 20240901, contains the following versions of the RISC-V IOMMU Base Architecture specification and standard extensions:

| Specification                                  | Version | Status   |
|------------------------------------------------|---------|----------|
| RISC-V IOMMU Base Architecture specification   | 1.0     | Ratified |
| Quality-of-Service (QoS) Identifiers Extension | 1.0     | Ratified |

The following backward-compatible changes, comprising a set of clarifications and corrections, have been made since version 1.0.0:

- ⚫ A set of typographic errors and editorial updates were made.
- ⚫ Translations cached, if any, in Bare mode do not require invalidation.
- ⚫ Clarified that memory faults encountered by commands also set the cqmf flag.
- ⚫ Values tested by algorithms in SW Guidelines are before modifications made by the algorithms.
- ⚫ Included SW guidelines for modifying non-leaf PDT entries.
- ⚫ Clarified the behavior for in-flight transactions observed at the time of ddtp write operations.
- ⚫ Clarified the behavior when IOTINVAL is invoked with an invalid address.
- ⚫ Stated that faults leading to UR/CA ATS responses are reported in the Fault Queue.
- ⚫ Added a detailed description of the capabilities.PAS field.
- ⚫ SW guidelines for changing IOMMU modes and programming tr\_req\_ctl and HPM counters.
- ⚫ PCIe ATS Translation Resp. grants execute permission only if requested.
- ⚫ Clarified the handling of hardware implementations that internally split 8-byte transactions.
- ⚫ Shadow stack encodings introduced by Zicfiss are reserved for IOMMU use.
- ⚫ Listed the fault codes reported for faults detected by Page Request.
- ⚫ Updated Fig 31 to remove the unused Destination ID field for ATS.PRGR
- ⚫ Included a software guideline for IOMMU emulation.

These changes were made through PR#243 [[3\]](#page-106-3).

# *Preface to Version 1.0.0*

⚫ Ratified version of the RISC-V IOMMU Architecture Specification.
