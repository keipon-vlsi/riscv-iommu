![](_page_0_Picture_0.jpeg)

# The RISC-V Instruction Set Manual, Volume II

Privileged Architecture

Version 20260120: Official Release

## **Table of Contents**

| Preamble                                                                 |    |
|--------------------------------------------------------------------------|----|
| Preface                                                                  | 2  |
| 1. Introduction                                                          | 10 |
| 1.1. RISC-V Privileged Software Stack Terminology                        | 10 |
| 1.2. Privilege Levels                                                    | 11 |
| 1.3. Debug Mode                                                          | 12 |
| 2. Control and Status Registers (CSRs)                                   | 13 |
| 2.1. CSR Address Mapping Conventions                                     | 13 |
| 2.2. CSR Listing                                                         | 16 |
| 2.2.1. Currently allocated RISC-V unprivileged CSR addresses             | 16 |
| 2.2.2. Currently allocated RISC-V supervisor-level CSR addresses         | 17 |
| 2.2.3. Currently allocated RISC-V hypervisor and VS CSR addresses        | 19 |
| 2.2.4. Currently allocated RISC-V machine-level CSR addresses            | 21 |
| 2.2.5. Currently allocated RISC-V indirect CSR (Smcsrind) mappings       | 24 |
| 2.3. CSR Field Specifications                                            | 25 |
| 2.3.1. Reserved Writes Preserve Values, Reads Ignore Values (WPRI)       | 25 |
| 2.3.2. Write/Read Only Legal Values (WLRL)                               | 26 |
| 2.3.3. Write Any Values, Reads Legal Values (WARL)                       | 26 |
| 2.4. CSR Field Modulation                                                | 26 |
| 2.5. Implicit Reads of CSRs                                              | 27 |
| 2.6. CSR Width Modulation                                                | 27 |
| 2.7. Explicit Accesses to CSRs Wider than XLEN                           | 27 |
| 3. Machine-Level ISA, Version 1.13                                       | 28 |
| 3.1. Machine-Level CSRs                                                  | 28 |
| 3.1.1. Machine ISA (misa) Register                                       | 28 |
| 3.1.2. Machine Vendor ID (mvendorid) Register                            | 31 |
| 3.1.3. Machine Architecture ID (marchid) Register                        | 32 |
| 3.1.4. Machine Implementation ID (mimpid) Register                       | 32 |
| 3.1.5. Hart ID (mhartid) Register                                        | 32 |
| 3.1.6. Machine Status (mstatus and mstatush) Registers                   | 33 |
| 3.1.6.1. Privilege and Global Interrupt-Enable Stack in mstatus register |    |
| 3.1.6.2. Double Trap Control in mstatus Register                         |    |
| 3.1.6.3. Base ISA Control in mstatus Register                            |    |
| 3.1.6.4. Memory Privilege in mstatus Register                            |    |
| 3.1.6.5. Endianness Control in mstatus and mstatush Registers            | 37 |
| 3.1.6.6. Virtualization Support in mstatus Register                      |    |
| 3.1.6.7. Extension Context Status in mstatus Register                    |    |
| 3.1.6.8. Previous Expected Landing Pad (ELP) State in mstatus Register   |    |
| 3.1.7. Machine Trap-Vector Base-Address (mtvec) Register                 |    |
| 3.1.8. Machine Trap Delegation (medeleg and mideleg) Registers           |    |
| 3.1.9. Machine Interrupt (mip and mie) Registers                         |    |
| 3.1.10. Hardware Performance Monitor                                     |    |
| 3.1.11. Machine Counter-Enable (mcounteren) Register                     | 48 |

| 3.1.12. Machine Counter-Inhibit (mcountinhibit) Register                                 | 49 |
|------------------------------------------------------------------------------------------|----|
| 3.1.13. Machine Scratch (mscratch) Register                                              | 50 |
| 3.1.14. Machine Exception Program Counter (mepc) Register                                | 50 |
| 3.1.15. Machine Cause (mcause) Register                                                  | 51 |
| 3.1.16. Machine Trap Value (mtval) Register                                              | 54 |
| 3.1.17. Machine Configuration Pointer (mconfigptr) Register                              | 55 |
| 3.1.18. Machine Environment Configuration (menvcfg) Register                             | 56 |
| 3.1.19. Machine Security Configuration (mseccfg) Register                                | 59 |
| 3.2. Machine-Level Memory-Mapped Registers                                               | 61 |
| 3.2.1. Machine Timer (mtime and mtimecmp) Registers                                      | 61 |
| 3.3. Machine-Mode Privileged Instructions                                                | 63 |
| 3.3.1. Environment Call and Breakpoint                                                   | 63 |
| 3.3.2. Trap-Return Instructions                                                          | 63 |
| 3.3.3. Wait for Interrupt                                                                | 64 |
| 3.3.4. Custom SYSTEM Instructions                                                        | 65 |
| 3.4. Reset                                                                               | 65 |
| 3.5. Non-Maskable Interrupts                                                             | 66 |
| 3.6. Physical Memory Attributes                                                          | 66 |
| 3.6.1. Main Memory versus I/O Regions                                                    | 67 |
| 3.6.2. Supported Access Type PMAs                                                        | 67 |
| 3.6.3. Atomicity PMAs                                                                    | 68 |
| 3.6.3.1. AMO PMA                                                                         | 68 |
| 3.6.3.2. Reservability PMA                                                               | 69 |
| 3.6.4. Misaligned Atomicity Granule PMA                                                  |    |
| 3.6.5. Memory-Ordering PMAs                                                              | 69 |
| 3.6.6. Coherence and Cacheability PMAs                                                   | 70 |
| 3.6.7. Idempotency PMAs                                                                  | 71 |
| 3.7. Physical Memory Protection                                                          | 72 |
| 3.7.1. Physical Memory Protection CSRs                                                   | 72 |
| 3.7.1.1. Address Matching                                                                | 74 |
| 3.7.1.2. Locking and Privilege Mode                                                      | 75 |
| 3.7.1.3. Priority and Matching Logic                                                     | 75 |
| 3.7.2. Physical Memory Protection and Paging                                             | 76 |
| 4. "Smstateen/Ssstateen" Extensions, Version 1.0                                         | 77 |
| 4.1. State Enable Extensions                                                             | 77 |
| 4.2. State Enable O Registers                                                            |    |
| 4.3. Usage                                                                               | 81 |
| 5. "Smcsrind/Sscsrind" Indirect CSR Access, Version 1.0                                  | 83 |
| 5.1. Introduction                                                                        | 83 |
| 5.2. Machine-level CSRs                                                                  | 83 |
| 5.3. Supervisor-level CSRs                                                               |    |
| 5.4. Virtual Supervisor-level CSRs                                                       | 85 |
| 5.5. Access control by the state-enable CSRs                                             | 86 |
| 6. "Smepmp" Extension for PMP Enhancements for memory access and execution prevention in |    |
| Machine mode, Version 1.0                                                                | 88 |

| 6.1. Threat model                                                               | 88  |
|---------------------------------------------------------------------------------|-----|
| 6.2. Smepmp Physical Memory Protection Rules                                    |     |
| 6.3. Smepmp software discovery                                                  |     |
| 7. "Smcntrpmf" Cycle and Instret Privilege Mode Filtering, Version 1.0          |     |
| 7.1. Introduction                                                               |     |
| 7.2. CSRs                                                                       | 91  |
| 7.2.1. Machine Counter Configuration (mcyclecfg, minstretcfg) Registers         | 91  |
| 7.3. Counter Behavior                                                           |     |
| 8. "Smrnmi" Extension for Resumable Non-Maskable Interrupts, Version 1.0        | 93  |
| 8.1. RNMI Interrupt Signals                                                     | 93  |
| 8.2. RNMI Handler Addresses                                                     | 93  |
| 8.3. RNMI CSRs                                                                  | 93  |
| 8.4. MNRET Instruction                                                          | 95  |
| 8.5. RNMI Operation                                                             | 95  |
| 9. "Smcdeleg/Ssccfg" Counter Delegation Extensions, Version 1.0                 | 96  |
| 9.1. Counter Delegation                                                         |     |
| 9.2. Supervisor Counter Inhibit (scountinhibit) Register                        | 97  |
| 9.3. Virtualizing scountovf                                                     |     |
| 9.4. Virtualizing Local-Counter-Overflow Interrupts                             | 98  |
| 10. "Smdbltrp" Double Trap Extension, Version 1.0                               | 99  |
| 11. "Smctr" Control Transfer Records Extension, Version 1.0                     | 100 |
| 11.1. CSRs                                                                      | 100 |
| 11.1.1. Machine Control Transfer Records Control Register (mctrctl)             | 100 |
| 11.1.2. Supervisor Control Transfer Records Control Register (sctrctl)          | 102 |
| 11.1.3. Virtual Supervisor Control Transfer Records Control Register (vsctrctl) | 102 |
| 11.1.4. Supervisor Control Transfer Records Depth Register (sctrdepth)          | 103 |
| 11.1.5. Supervisor Control Transfer Records Status Register (sctrstatus)        | 103 |
| 11.2. Entry Registers                                                           | 105 |
| 11.2.1. Control Transfer Record Source Register (ctrsource)                     | 105 |
| 11.2.2. Control Transfer Record Target Register (ctrtarget)                     |     |
| 11.2.3. Control Transfer Record Metadata Register (ctrdata)                     | 106 |
| 11.3. Instructions                                                              | 106 |
| 11.3.1. Supervisor CTR Clear Instruction                                        | 106 |
| 11.4. State Enable Access Control                                               | 106 |
| 11.5. Behavior                                                                  | 107 |
| 11.5.1. Privilege Mode Transitions                                              | 108 |
| 11.5.1.1. Virtualization Mode Transitions                                       | 108 |
| 11.5.1.2. External Traps                                                        | 109 |
| 11.5.2. Transfer Type Filtering                                                 | 110 |
| 11.5.3. Cycle Counting                                                          | 111 |
| 11.5.4. RAS (Return Address Stack) Emulation Mode                               | 112 |
| 11.5.5. Freeze                                                                  |     |
| 11.6. Custom Extensions                                                         | 114 |
| 12. Supervisor-Level ISA, Version 1.13                                          | 115 |
| 12.1. Supervisor CSRs                                                           | 115 |

| 12.1.1. Supervisor Status (sstatus) Register115                                                 |  |
|-------------------------------------------------------------------------------------------------|--|
| 12.1.1.1. Base ISA Control in sstatus Register116                                               |  |
| 12.1.1.2. Memory Privilege in sstatus Register116                                               |  |
| 12.1.1.3. Endianness Control in sstatus Register117                                             |  |
| 12.1.1.4. Previous Expected Landing Pad (ELP) State in sstatus Register117                      |  |
| 12.1.1.5. Double Trap Control in sstatus Register117                                            |  |
| 12.1.2. Supervisor Trap Vector Base Address (stvec) Register118                                 |  |
| 12.1.3. Supervisor Interrupt (sip and sie) Registers119                                         |  |
| 12.1.4. Supervisor Timers and Performance Counters120                                           |  |
| 12.1.5. Counter-Enable (scounteren) Register121                                                 |  |
| 12.1.6. Supervisor Scratch (sscratch) Register121                                               |  |
| 12.1.7. Supervisor Exception Program Counter (sepc) Register121                                 |  |
| 12.1.8. Supervisor Cause (scause) Register122                                                   |  |
| 12.1.9. Supervisor Trap Value (stval) Register123                                               |  |
| 12.1.10. Supervisor Environment Configuration (senvcfg) Register124                             |  |
| 12.1.11. Supervisor Address Translation and Protection (satp) Register126                       |  |
| 12.1.12. Supervisor Timer (stimecmp) Register129                                                |  |
| 12.2. Supervisor Instructions130                                                                |  |
| 12.2.1. Supervisor Memory-Management Fence Instruction130                                       |  |
| 12.3. Sv32: Page-Based 32-bit Virtual-Memory Systems133                                         |  |
| 12.3.1. Addressing and Memory Protection133                                                     |  |
| 12.3.2. Virtual Address Translation Process137                                                  |  |
| 12.4. Sv39: Page-Based 39-bit Virtual-Memory System139                                          |  |
| 12.4.1. Addressing and Memory Protection139                                                     |  |
| 12.5. Sv48: Page-Based 48-bit Virtual-Memory System140                                          |  |
| 12.5.1. Addressing and Memory Protection140                                                     |  |
| 12.6. Sv57: Page-Based 57-bit Virtual-Memory System141                                          |  |
| 12.6.1. Addressing and Memory Protection141                                                     |  |
| 13. "Svnapot" Extension for NAPOT Translation Contiguity, Version 1.0143                        |  |
| 14. "Svpbmt" Extension for Page-Based Memory Types, Version 1.0145                              |  |
| 15. "Svinval" Extension for Fine-Grained Address-Translation Cache Invalidation, Version 1.0147 |  |
| 16. "Svadu" Extension for Hardware Updating of A/D Bits, Version 1.0149                         |  |
| 17. "Svvptc" Extension for Obviating Memory-Management Instructions after Marking PTEs Valid,   |  |
| Version 1.0150                                                                                  |  |
| 18. "Svrsw60t59b" Extension for PTE Reserved-for-Software Bits 60-59, Version 1.0151            |  |
| 19. "Ssqosid" Extension for Quality-of-Service (QoS) Identifiers, Version 1.0152                |  |
| 19.1. Supervisor Resource Management Configuration (srmcfg) register152                         |  |
| 20. "Sstc" Extension for Supervisor-mode Timer Interrupts, Version 1.0154                       |  |
| 21. "Sscofpmf" Extension for Count Overflow and Mode-Based Filtering, Version 1.0155            |  |
| 21.1. Count Overflow Control155                                                                 |  |
| 21.2. Supervisor Count Overflow (scountovf) Register156                                         |  |
| 22. "H" Extension for Hypervisor Support, Version 1.0157                                        |  |
| 22.1. Privilege Modes157                                                                        |  |
| 22.2. Hypervisor and Virtual Supervisor CSRs158                                                 |  |
| 22.2.1. Hypervisor Status (hstatus) Register159                                                 |  |
|                                                                                                 |  |

| 22.2.2. Hypervisor Trap Delegation (hedeleg and hideleg) Registers              | 160 |
|---------------------------------------------------------------------------------|-----|
| 22.2.3. Hypervisor Interrupt (hvip, hip, and hie) Registers                     | 162 |
| 22.2.4. Hypervisor Guest External Interrupt Registers (hgeip and hgeie)         | 164 |
| 22.2.5. Hypervisor Environment Configuration Register (henvcfg)                 |     |
| 22.2.6. Hypervisor Counter-Enable (hcounteren) Register                         | 167 |
| 22.2.7. Hypervisor Time Delta (htimedelta) Register                             | 167 |
| 22.2.8. Hypervisor Trap Value (htval) Register                                  | 168 |
| 22.2.9. Hypervisor Trap Instruction (htinst) Register                           | 169 |
| 22.2.10. Hypervisor Guest Address Translation and Protection (hgatp) Register   |     |
| 22.2.11. Virtual Supervisor Status (vsstatus) Register                          | 170 |
| 22.2.12. Virtual Supervisor Interrupt (vsip and vsie) Registers                 | 172 |
| 22.2.13. Virtual Supervisor Trap Vector Base Address (vstvec) Register          |     |
| 22.2.14. Virtual Supervisor Scratch (vsscratch) Register                        |     |
| 22.2.15. Virtual Supervisor Exception Program Counter (vsepc) Register          | 173 |
| 22.2.16. Virtual Supervisor Cause (vscause) Register                            |     |
| 22.2.17. Virtual Supervisor Trap Value (vstval) Register                        |     |
| 22.2.18. Virtual Supervisor Address Translation and Protection (vsatp) Register |     |
| 22.2.19. Virtual Supervisor Timer (vstimecmp) Register                          |     |
| 22.3. Hypervisor Instructions                                                   |     |
| 22.3.1. Hypervisor Virtual-Machine Load and Store Instructions                  |     |
| 22.3.2. Hypervisor Memory-Management Fence Instructions                         |     |
| 22.4. Machine-Level CSRs                                                        | 177 |
| 22.4.1. Machine Status (mstatus and mstatush) Registers                         | 177 |
| 22.4.2. Machine Interrupt Delegation (mideleg) Register                         | 179 |
| 22.4.3. Machine Interrupt (mip and mie) Registers                               | 179 |
| 22.4.4. Machine Second Trap Value (mtval2) Register                             | 180 |
| 22.4.5. Machine Trap Instruction (mtinst) Register                              | 180 |
| 22.5. Two-Stage Address Translation                                             | 181 |
| 22.5.1. Guest Physical Address Translation                                      | 181 |
| 22.5.2. Guest-Page Faults                                                       |     |
| 22.5.3. Memory-Management Fences                                                |     |
| 22.5.4. Interaction with Pointer Masking                                        | 184 |
| 22.6. Traps                                                                     | 184 |
| 22.6.1. Trap Cause Codes                                                        |     |
| 22.6.2. Trap Entry                                                              |     |
| 22.6.3. Transformed Instruction or Pseudoinstruction for mtinst or htinst       |     |
| 22.6.4. Trap Return                                                             |     |
| 23. Control-flow Integrity (CFI)                                                |     |
| 23.1. Landing Pad (Zicfilp)                                                     |     |
| 23.1.1. Landing-Pad-Enabled (LPE) State                                         |     |
| 23.1.2. Preserving Expected Landing Pad State on Traps                          |     |
| 23.2. Shadow Stack (Zicfiss)                                                    |     |
| 23.2.1. Shadow Stack Pointer (ssp) CSR access control                           |     |
| 23.2.2. Shadow-Stack-Enabled (SSE) State                                        |     |
| 23.2.3. Shadow Stack Memory Protection                                          |     |
| •                                                                               |     |

| 24. "Ssdbltrp" Double Trap Extension, Version 1.0                                          | 201 |
|--------------------------------------------------------------------------------------------|-----|
| 25. Pointer Masking Extensions, Version 1.0.0                                              | 202 |
| 25.1. Introduction                                                                         | 202 |
| 25.2. Background                                                                           | 202 |
| 25.2.1. Definitions                                                                        | 202 |
| 25.2.2. The "Ignore" Transformation                                                        | 203 |
| 25.2.3. Example                                                                            |     |
| 25.2.4. Determining the Value of PMLEN                                                     | 204 |
| 25.2.5. Pointer Masking and Privilege Modes                                                | 205 |
| 25.2.6. Memory Accesses Subject to Pointer Masking                                         | 205 |
| 25.2.7. Pointer Masking Extensions                                                         | 207 |
| 25.2.8. Number of Masked Bits                                                              | 208 |
| 26. RISC-V Privileged Instruction Set Listings                                             | 209 |
| 27. History                                                                                | 211 |
| 27.1. Research Funding at UC Berkeley                                                      | 211 |
| Appendix A: Historical Rationale for Extensions                                            | 212 |
| A.1. "Smepmp" Extension for PMP Enhancements for memory access and execution prevention in |     |
| Machine mode                                                                               | 212 |
