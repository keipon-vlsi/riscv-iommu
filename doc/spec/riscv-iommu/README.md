# riscv-iommu.md — 章別インデックス

- 全 13 章 (分割 Level 1, パターン `^(Chapter\s+\d+|Preamble|Copyright|Contributors)`)

---

## 01. [prologue](./00-prologue.md)

_(要約抽出不可、本文を参照)_

## 02. [Preamble](./01-preamble.md)

*This document is [Ratified](http://riscv.org/spec-state).*

## 03. [Copyright and license information](./02-copyright-and-license-information.md)

This specification is licensed under the Creative Commons Attribution 4.0 International License (CC-BY 4.0). The full license text is available at [creativecommons.org/licenses/by/4.0/.](https://creativecommons.org/licenses/by/4.0/)

## 04. [Contributors](./03-contributors.md)

This RISC-V specification has been contributed to directly or indirectly by (in alphabetical order):

## 05. [Chapter 1. Preface](./04-chapter-1.-preface.md)

This document describes the RISC-V IOMMU architecture. This release, version 20250828, includes the following versions of the RISC-V IOMMU Base Architecture specification and standard extensions:

## 06. [Chapter 2. Introduction](./05-chapter-2.-introduction.md)

The Input-Output Memory Management Unit (IOMMU), sometimes referred to as a System MMU (SMMU), is a system-level Memory Management Unit (MMU) that connects direct-memory-access-capable Input/Output (I/O) devices to system memory.

## 07. [Chapter 3. Data Structures](./06-chapter-3.-data-structures.md)

A data structure called device-context (DC) is used by the IOMMU to associate a device with an address space and to hold other per-device parameters used by the IOMMU to perform address translations. A radix-tree data structure called device director…

## 08. [Chapter 4. In-memory queue interface](./07-chapter-4.-in-memory-queue-interface.md)

Software and IOMMU interact using 3 in-memory queue data structures.

## 09. [Chapter 5. Debug support](./08-chapter-5.-debug-support.md)

To support software debug, the IOMMU may provide an optional register interface that may be used by software to request IOMMU to perform an address translation. The IOMMU supports this capability when capabilities.DBG is 1. The interface consists of…

## 10. [Chapter 6. Memory-mapped register interface](./09-chapter-6.-memory-mapped-register-interface.md)

The IOMMU provides a memory-mapped programming interface. The memory-mapped registers of each IOMMU are located within a naturally aligned 4-KiB region (a page) of physical address space.

## 11. [Chapter 7. Software guidelines](./10-chapter-7.-software-guidelines.md)

This section provides guidelines to software developers on the correct and expected sequence of using the IOMMU interfaces. The behavior of the IOMMU if these guidelines are not followed is implementation defined.

## 12. [Chapter 8. Hardware guidelines](./11-chapter-8.-hardware-guidelines.md)

This section provides guidelines to the system/hardware integrator of the IOMMU in the platform.

## 13. [Chapter 9. IOMMU Extensions](./12-chapter-9.-iommu-extensions.md)

This chapter specifies the following standard extensions to the IOMMU Base Architecture:
