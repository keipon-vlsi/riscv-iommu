# riscv-privileged.md — 章別インデックス

- 全 30 章 (分割 Level 2, パターン `^(Chapter\s+\d+|Preamble|Preface)`)

---

## 01. [prologue](./00-prologue.md)

_(要約抽出不可、本文を参照)_

## 02. [Preamble](./01-preamble.md)

*Contributors to all versions of the spec in alphabetical order (please contact editors to suggest corrections): Krste Asanović, Peter Ashenden, Rimas Avižienis, Jacob Bachmeyer, Allen J. Baum, Jonathan Behrens, Paolo Bonzini, Ruslan Bukin, Christoph…

## 03. [Preface](./02-preface.md)

This document describes the RISC-V privileged architecture. It contains the following versions of the RISC-V ISA modules, all of which have been ratified:

## 04. [Chapter 1. Introduction](./03-chapter-1.-introduction.md)

This document describes the RISC-V privileged architecture, which covers all aspects of RISC-V systems beyond the unprivileged ISA, including privileged instructions as well as additional functionality required for running operating systems and attac…

## 05. [Chapter 2. Control and Status Registers (CSRs)](./04-chapter-2.-control-and-status-registers-csrs.md)

The SYSTEM major opcode is used to encode all privileged instructions in the RISC-V ISA. These can be divided into two main classes: those that atomically read-modify-write control and status registers (CSRs), which are defined in the Zicsr extension…

## 06. [Chapter 3. Machine-Level ISA, Version 1.13](./05-chapter-3.-machine-level-isa-version-1.13.md)

This chapter describes the machine-level operations available in machine-mode (M-mode), which is the highest privilege mode in a RISC-V hart. M-mode is used for low-level access to a hardware platform and is the first mode entered at reset. M-mode ca…

## 07. [Chapter 4. "Smstateen/Ssstateen" Extensions, Version 1.0](./06-chapter-4.-smstateenssstateen-extensions-version-1.0.md)

The implementation of optional RISC-V extensions has the potential to open covert channels between separate user threads, or between separate guest OSes running under a hypervisor. The problem occurs when an extension adds processor state — usually e…

## 08. [Chapter 5. "Smcsrind/Sscsrind" Indirect CSR Access, Version 1.0](./07-chapter-5.-smcsrindsscsrind-indirect-csr-access-version-1.0.md)

Smcsrind/Sscsrind is an ISA extension that extends the indirect CSR access mechanism originally defined as part of the [Smaia/Ssaia extensions](https://github.com/riscv/riscv-aia), in order to make it available for use by other extensions without cre…

## 09. [Chapter 6. "Smepmp" Extension for PMP Enhancements for memory access and execution prevention in Machine mode, Version 1.0](./08-chapter-6.-smepmp-extension-for-pmp-enhancements-for-memory.md)

Being able to access the memory of a process running at a high privileged execution mode, such as the Supervisor or Machine mode, from a lower privileged mode such as the User mode, introduces an obvious attack vector since it allows for an attacker…

## 10. [Chapter 7. "Smcntrpmf" Cycle and Instret Privilege Mode Filtering, Version 1.0](./09-chapter-7.-smcntrpmf-cycle-and-instret-privilege-mode-filter.md)

The cycle and instret counters serve to support user mode self-profiling usages, wherein a user can read the counter(s) twice and compute the delta(s) to evaluate user software performance and behavior. By default, these counters are not filtered by…

## 11. [Chapter 8. "Smrnmi" Extension for Resumable Non-Maskable Interrupts, Version 1.0](./10-chapter-8.-smrnmi-extension-for-resumable-non-maskable-inter.md)

The base machine-level architecture supports only unresumable non-maskable interrupts (UNMIs), where the NMI jumps to a handler in machine mode, overwriting the current mepc and mcause register values. If the hart had been executing machine-mode code…

## 12. [Chapter 9. "Smcdeleg/Ssccfg" Counter Delegation Extensions, Version 1.0](./11-chapter-9.-smcdelegssccfg-counter-delegation-extensions-vers.md)

In modern "Rich OS" environments, hardware performance monitoring resources are managed by the kernel, kernel driver, and/or hypervisor. Counters may be configured with differing scopes, in some cases counting events system-wide, while in others coun…

## 13. [Chapter 10. "Smdbltrp" Double Trap Extension, Version 1.0](./12-chapter-10.-smdbltrp-double-trap-extension-version-1.0.md)

The Smdbltrp extension addresses a double trap (See [Section 3.1.6.2\)](#page-40-0) in M-mode. When the Smrnmi extension [\(Chapter 8](#page-99-0)) is implemented, it enables invocation of the RNMI handler on a double trap in Mmode to handle the crit…

## 14. [Chapter 11. "Smctr" Control Transfer Records Extension, Version 1.0](./13-chapter-11.-smctr-control-transfer-records-extension-version.md)

A method for recording control flow transfer history is valuable not only for performance profiling but also for debugging. Control flow transfers refer to jump instructions (including function calls and returns), taken branch instructions, traps, an…

## 15. [Chapter 12. Supervisor-Level ISA, Version 1.13](./14-chapter-12.-supervisor-level-isa-version-1.13.md)

This chapter describes the RISC-V supervisor-level architecture, which contains a common core that is used with various supervisor-level address translation and protection schemes.

## 16. [Chapter 13. "Svnapot" Extension for NAPOT Translation Contiguity, Version 1.0](./15-chapter-13.-svnapot-extension-for-napot-translation-contigui.md)

In Sv39, Sv48, and Sv57, when a PTE has N=1, the PTE represents a translation that is part of a range of contiguous virtual-to-physical translations with the same values for PTE bits 5–0. Such ranges must be of a naturally aligned power-of-2 (NAPOT)…

## 17. [Chapter 14. "Svpbmt" Extension for Page-Based Memory Types, Version 1.0](./16-chapter-14.-svpbmt-extension-for-page-based-memory-types-ver.md)

In Sv39, Sv48, and Sv57, bits 62-61 of a leaf page table entry indicate the use of page-based memory types that override the PMA(s) for the associated memory pages. The encoding for the PBMT bits is captured in [Table 43](#page-151-1).

## 18. [Chapter 15. "Svinval" Extension for Fine-Grained Address-Translation Cache Invalidation, Version 1.0](./17-chapter-15.-svinval-extension-for-fine-grained-address-trans.md)

The Svinval extension splits SFENCE.VMA, HFENCE.VVMA, and HFENCE.GVMA instructions into finergrained invalidation and ordering operations that can be more efficiently batched or pipelined on certain classes of high-performance implementation.

## 19. [Chapter 16. "Svadu" Extension for Hardware Updating of A/D Bits, Version 1.0](./18-chapter-16.-svadu-extension-for-hardware-updating-of-ad-bits.md)

The Svadu extension adds support and CSR controls for hardware updating of PTE A/D bits.

## 20. [Chapter 17. "Svvptc" Extension for Obviating Memory-Management Instructions after Marking PTEs Valid, Version 1.0](./19-chapter-17.-svvptc-extension-for-obviating-memory-management.md)

When the Svvptc extension is implemented, explicit stores by a hart that update the Valid bit of leaf and/or non-leaf PTEs from 0 to 1 and are visible to a hart will eventually become visible within a bounded timeframe to subsequent implicit accesses…

## 21. [Chapter 18. "Svrsw60t59b" Extension for PTE Reserved-for-Software Bits 60-59, Version 1.0](./20-chapter-18.-svrsw60t59b-extension-for-pte-reserved-for-softw.md)

If the Svrsw60t59b extension is implemented, then bits 60-59 of the page table entries (PTEs) are reserved for use by supervisor software and are ignored by the implementation.

## 22. [Chapter 19. "Ssqosid" Extension for Quality-of-Service (QoS) Identifiers, Version 1.0](./21-chapter-19.-ssqosid-extension-for-quality-of-service-qos-ide.md)

Quality of Service (QoS) is defined as the minimal end-to-end performance guaranteed in advance by a service level agreement (SLA) to a workload. Performance metrics might include measures such as instructions per cycle (IPC), latency of service, etc…

## 23. [Chapter 20. "Sstc" Extension for Supervisor-mode Timer Interrupts, Version 1.0](./22-chapter-20.-sstc-extension-for-supervisor-mode-timer-interru.md)

The current Privileged arch specification only defines a hardware mechanism for generating machinemode timer interrupts (based on the mtime and mtimecmp registers). With the resultant requirement that timer services for S-mode/HS-mode (and for VS-mod…

## 24. [Chapter 21. "Sscofpmf" Extension for Count Overflow and Mode-Based Filtering, Version 1.0](./23-chapter-21.-sscofpmf-extension-for-count-overflow-and-mode-b.md)

The current Privileged specification defines mhpmevent CSRs to select and control event counting by the associated hpmcounter CSRs, but provides no standardization of any fields within these CSRs. For at least Linux-class rich-OS systems it is desira…

## 25. [Chapter 22. "H" Extension for Hypervisor Support, Version 1.0](./24-chapter-22.-h-extension-for-hypervisor-support-version-1.0.md)

This chapter describes the RISC-V hypervisor extension, which virtualizes the supervisor-level architecture to support the efficient hosting of guest operating systems atop a type-1 or type-2 hypervisor. The hypervisor extension changes supervisor mo…

## 26. [Chapter 23. Control-flow Integrity (CFI)](./25-chapter-23.-control-flow-integrity-cfi.md)

Control-flow Integrity (CFI) capabilities help defend against Return-Oriented Programming (ROP) and Call/Jump-Oriented Programming (COP/JOP) style control-flow subversion attacks. The Zicfiss and Zicfilp extensions provide backward-edge and forward-e…

## 27. [Chapter 24. "Ssdbltrp" Double Trap Extension, Version 1.0](./26-chapter-24.-ssdbltrp-double-trap-extension-version-1.0.md)

The Ssdbltrp extension addresses a double trap (See [Section 3.1.6.2](#page-40-0)) privilege modes lower than M. It enables HS-mode to invoke a critical error handler in a virtual machine on a double trap in VS-mode. It also allows M-mode to invoke a…

## 28. [Chapter 25. Pointer Masking Extensions, Version 1.0.0](./27-chapter-25.-pointer-masking-extensions-version-1.0.0.md)

RISC-V Pointer Masking (PM) is a feature that, when enabled, causes the CPU to ignore the upper bits of the effective address (these terms will be defined more precisely in the Background section). This allows these bits to be used in whichever way t…

## 29. [Chapter 26. RISC-V Privileged Instruction Set Listings](./28-chapter-26.-risc-v-privileged-instruction-set-listings.md)

This chapter presents instruction-set listings for all instructions defined in the RISC-V Privileged Architecture.

## 30. [Chapter 27. History](./29-chapter-27.-history.md)

Development of the RISC-V architecture and implementations has been partially funded by the following sponsors.
