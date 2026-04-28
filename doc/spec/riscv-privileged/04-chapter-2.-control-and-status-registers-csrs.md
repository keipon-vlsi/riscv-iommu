## <span id="page-19-0"></span>Chapter 2. Control and Status Registers (CSRs)

The SYSTEM major opcode is used to encode all privileged instructions in the RISC-V ISA. These can be divided into two main classes: those that atomically read-modify-write control and status registers (CSRs), which are defined in the Zicsr extension, and all other privileged instructions. The privileged architecture requires the Zicsr extension; which other privileged instructions are required depends on the privilegedarchitecture feature set.

In addition to the unprivileged state described in Volume I of this manual, an implementation may contain additional CSRs, accessible by some subset of the privilege levels using the CSR instructions described in Volume I. In this chapter, we map out the CSR address space. The following chapters describe the function of each of the CSRs according to privilege level, as well as the other privileged instructions which are generally closely associated with a particular privilege level. Note that although CSRs and instructions are associated with one privilege level, they are also accessible at all higher privilege levels.

Standard CSRs do not have side effects on reads but may have side effects on writes.

## <span id="page-19-1"></span>2.1. CSR Address Mapping Conventions

The standard RISC-V ISA sets aside a 12-bit encoding space (csr[11:0]) for up to 4,096 CSRs. By convention, the upper 4 bits of the CSR address (csr[11:8]) are used to encode the read and write accessibility of the CSRs according to privilege level as shown in [Table 3.](#page-19-2) The top two bits (csr[11:10]) indicate whether the register is read/write (00,01, or 10) or read-only (11). The next two bits (csr[9:8]) encode the lowest privilege level that can access the CSR, with the pattern 10 representing hypervisor CSRs.

![](_page_19_Picture_7.jpeg)

*The CSR address convention uses the upper bits of the CSR address to encode default access privileges. This simplifies error checking in the hardware and provides a larger CSR space, but does constrain the mapping of CSRs into the address space.*

*Implementations might allow a more-privileged level to trap otherwise permitted CSR accesses by a less-privileged level to allow these accesses to be intercepted. This change should be transparent to the less-privileged software.*

Instructions that access a non-existent CSR are reserved. Attempts to access a CSR without appropriate privilege level raise illegal-instruction exceptions or, as described in [Section 22.6.1,](#page-190-2) virtual-instruction exceptions. Attempts to write a read-only register raise illegal-instruction exceptions. A read/write register might also contain some bits that are read-only, in which case writes to the read-only bits are ignored.

[Table 3](#page-19-2) also indicates the convention to allocate CSR addresses between standard and custom uses. The CSR addresses designated for custom uses will not be redefined by future standard extensions.

Machine-mode standard read-write CSRs 0x7A0-0x7BF are reserved for use by the debug system. Of these CSRs, 0x7A0-0x7AF are accessible to machine mode, whereas 0x7B0-0x7BF are only visible to debug mode. Implementations should raise illegal-instruction exceptions on machine-mode access to the latter set of registers.

<span id="page-19-2"></span>![](_page_19_Picture_13.jpeg)

*Effective virtualization requires that as many instructions run natively as possible inside a virtualized environment, while any privileged accesses trap to the virtual machine monitor. ([Goldberg, 1974\)](#page-220-0) CSRs that are read-only at some lower privilege level are shadowed into separate CSR addresses if they are made read-write at a higher privilege level. This avoids trapping permitted lower-privilege accesses while still causing traps on illegal accesses. Currently, the counters are the only shadowed CSRs.*

*Table 3. Allocation of RISC-V CSR address ranges.*

| CSR Address            |       | Hex   | Use and Accessibility            |                                |  |
|------------------------|-------|-------|----------------------------------|--------------------------------|--|
| [11:10]                | [9:8] | [7:4] |                                  |                                |  |
|                        |       |       | Unprivileged and User-Level CSRs |                                |  |
| 00                     | 00    | XXXX  | 0x000-0x0FF                      | Standard read/write            |  |
| 01                     | 00    | XXXX  | 0x400-0x4FF                      | Standard read/write            |  |
| 10                     | 00    | XXXX  | 0x800-0x8FF                      | Custom read/write              |  |
| 11                     | 00    | 0XXX  | 0xC00-0xC7F                      | Standard read-only             |  |
| 11                     | 00    | 10XX  | 0xC80-0xCBF                      | Standard read-only             |  |
| 11                     | 00    | 11XX  | 0xCC0-0xCFF                      | Custom read-only               |  |
|                        |       |       | Supervisor-Level CSRs            |                                |  |
| 00                     | 01    | XXXX  | 0x100-0x1FF                      | Standard read/write            |  |
| 01                     | 01    | 0XXX  | 0x500-0x57F                      | Standard read/write            |  |
| 01                     | 01    | 10XX  | 0x580-0x5BF                      | Standard read/write            |  |
| 01                     | 01    | 11XX  | 0x5C0-0x5FF                      | Custom read/write              |  |
| 10                     | 01    | 0XXX  | 0x900-0x97F                      | Standard read/write            |  |
| 10                     | 01    | 10XX  | 0x980-0x9BF                      | Standard read/write            |  |
| 10                     | 01    | 11XX  | 0x9C0-0x9FF                      | Custom read/write              |  |
| 11                     | 01    | 0XXX  | 0xD00-0xD7F                      | Standard read-only             |  |
| 11                     | 01    | 10XX  | 0xD80-0xDBF                      | Standard read-only             |  |
| 11                     | 01    | 11XX  | 0xDC0-0xDFF                      | Custom read-only               |  |
| Hypervisor and VS CSRs |       |       |                                  |                                |  |
| 00                     | 10    | XXXX  | 0x200-0x2FF                      | Standard read/write            |  |
| 01                     | 10    | 0XXX  | 0x600-0x67F                      | Standard read/write            |  |
| 01                     | 10    | 10XX  | 0x680-0x6BF                      | Standard read/write            |  |
| 01                     | 10    | 11XX  | 0x6C0-0x6FF                      | Custom read/write              |  |
| 10                     | 10    | 0XXX  | 0xA00-0xA7F                      | Standard read/write            |  |
| 10                     | 10    | 10XX  | 0xA80-0xABF                      | Standard read/write            |  |
| 10                     | 10    | 11XX  | 0xAC0-0xAFF                      | Custom read/write              |  |
| 11                     | 10    | 0XXX  | 0xE00-0xE7F                      | Standard read-only             |  |
| 11                     | 10    | 10XX  | 0xE80-0xEBF                      | Standard read-only             |  |
| 11                     | 10    | 11XX  | 0xEC0-0xEFF                      | Custom read-only               |  |
|                        |       |       | Machine-Level CSRs               |                                |  |
| 00                     | 11    | XXXX  | 0x300-0x3FF                      | Standard read/write            |  |
| 01                     | 11    | 0XXX  | 0x700-0x77F                      | Standard read/write            |  |
| 01                     | 11    | 100X  | 0x780-0x79F                      | Standard read/write            |  |
| 01                     | 11    | 1010  | 0x7A0-0x7AF                      | Standard read/write debug CSRs |  |
| 01                     | 11    | 1011  | 0x7B0-0x7BF                      | Debug-mode-only CSRs           |  |
| 01                     | 11    | 11XX  | 0x7C0-0x7FF                      | Custom read/write              |  |
| 10                     | 11    | 0XXX  | 0xB00-0xB7F                      | Standard read/write            |  |

| 10 | 11 | 10XX | 0xB80-0xBBF | Standard read/write |
|----|----|------|-------------|---------------------|
| 10 | 11 | 11XX | 0xBC0-0xBFF | Custom read/write   |
| 11 | 11 | 0XXX | 0xF00-0xF7F | Standard read-only  |
| 11 | 11 | 10XX | 0xF80-0xFBF | Standard read-only  |
| 11 | 11 | 11XX | 0xFC0-0xFFF | Custom read-only    |

## <span id="page-22-0"></span>2.2. CSR Listing

[Table 4-](#page-22-2)[Table 7](#page-27-1) list the CSRs that have currently been allocated CSR addresses. The timers, counters, and floating-point CSRs are standard unprivileged CSRs. The other registers are used by privileged code, as described in the following chapters. Note that not all registers are required on all implementations.

#### <span id="page-22-1"></span>2.2.1. Currently allocated RISC-V unprivileged CSR addresses

*Table 4. Currently allocated RISC-V unprivileged CSR addresses.*

<span id="page-22-2"></span>

| Number                  | Privilege         | Name                  | Description                                                                                                                              |
|-------------------------|-------------------|-----------------------|------------------------------------------------------------------------------------------------------------------------------------------|
|                         |                   |                       | Unprivileged Floating-Point CSRs                                                                                                         |
| 0x001<br>0x002<br>0x003 | URW<br>URW<br>URW | fflags<br>frm<br>fcsr | Floating-Point Accrued Exceptions.<br>Floating-Point Dynamic Rounding Mode.<br>Floating-Point Control and Status Register (frm +fflags). |
|                         |                   |                       | Unprivileged Vector CSRs                                                                                                                 |
| 0x008                   | URW               | vstart                | Vector start position.                                                                                                                   |
| 0x009                   | URW               | vxsat                 | Fixed-point accrued saturation flag.                                                                                                     |
| 0x00A                   | URW               | vxrm                  | Fixed-point rounding mode.                                                                                                               |
| 0x00F                   | URW               | vcsr                  | Vector control and status register.                                                                                                      |
| 0xC20                   | URO               | vl                    | Vector length.                                                                                                                           |
| 0xC21                   | URO               | vtype                 | Vector data type register.                                                                                                               |
| 0xC22                   | URO               | vlenb                 | Vector register length in bytes.                                                                                                         |
|                         |                   |                       | Unprivileged Zicfiss extension CSR                                                                                                       |
| 0x011                   | URW               | ssp                   | Shadow Stack Pointer.                                                                                                                    |
|                         |                   |                       | Unprivileged Entropy Source Extension CSR                                                                                                |
| 0x015                   | URW               | seed                  | Seed for cryptographic random bit generators.                                                                                            |
|                         |                   |                       | Unprivileged Zcmt Extension CSR                                                                                                          |
| 0x017                   | URW               | jvt                   | Table jump base vector and control register.                                                                                             |
|                         |                   |                       | Unprivileged Counter/Timers                                                                                                              |
| 0xC00                   | URO               | cycle                 | Cycle counter for RDCYCLE instruction.                                                                                                   |
| 0xC01                   | URO               | time                  | Timer for RDTIME instruction.                                                                                                            |
| 0xC02                   | URO               | instret               | Instructions-retired counter for RDINSTRET instruction.                                                                                  |
| 0xC03                   | URO               | hpmcounter3           | Performance-monitoring counter.                                                                                                          |
| 0xC04                   | URO               | hpmcounter4<br>⋮      | Performance-monitoring counter.                                                                                                          |
| 0xC1F                   | URO               | hpmcounter31          | Performance-monitoring counter.                                                                                                          |
| 0xC80                   | URO               | cycleh                | Upper 32 bits of cycle, RV32 only.                                                                                                       |
| 0xC81                   | URO               | timeh                 | Upper 32 bits of time, RV32 only.                                                                                                        |
| 0xC82                   | URO               | instreth              | Upper 32 bits of instret, RV32 only.                                                                                                     |
| 0xC83                   | URO               | hpmcounter3h          | Upper 32 bits of hpmcounter3, RV32 only.                                                                                                 |
| 0xC84                   | URO               | hpmcounter4h<br>⋮     | Upper 32 bits of hpmcounter4, RV32 only.                                                                                                 |
| 0xC9F                   | URO               | hpmcounter31h         | Upper 32 bits of hpmcounter31, RV32 only.                                                                                                |

### <span id="page-23-0"></span>2.2.2. Currently allocated RISC-V supervisor-level CSR addresses

*Table 5. Currently allocated RISC-V supervisor-level CSR addresses.*

| Number | Privilege | Name          | Description                                    |
|--------|-----------|---------------|------------------------------------------------|
|        |           |               | Supervisor Trap Setup                          |
| 0x100  | SRW       | sstatus       | Supervisor status register.                    |
| 0x104  | SRW       | sie           | Supervisor interrupt-enable register.          |
| 0x105  | SRW       | stvec         | Supervisor trap handler base address.          |
| 0x106  | SRW       | scounteren    | Supervisor counter enable.                     |
|        |           |               | Supervisor Configuration                       |
| 0x10A  | SRW       | senvcfg       | Supervisor environment configuration register. |
|        |           |               | Supervisor Counter Setup                       |
| 0x120  | SRW       | scountinhibit | Supervisor counter-inhibit register.           |
|        |           |               | Supervisor Trap Handling                       |
| 0x140  | SRW       | sscratch      | Supervisor scratch register.                   |
| 0x141  | SRW       | sepc          | Supervisor exception program counter.          |
| 0x142  | SRW       | scause        | Supervisor trap cause.                         |
| 0x143  | SRW       | stval         | Supervisor trap value.                         |
| 0x144  | SRW       | sip           | Supervisor interrupt pending.                  |
| 0xDA0  | SRO       | scountovf     | Supervisor count overflow.                     |
|        |           |               | Supervisor Indirect                            |
| 0x150  | SRW       | siselect      | Supervisor indirect register select.           |
| 0x151  | SRW       | sireg         | Supervisor indirect register alias.            |
| 0x152  | SRW       | sireg2        | Supervisor indirect register alias 2.          |
| 0x153  | SRW       | sireg3        | Supervisor indirect register alias 3.          |
| 0x155  | SRW       | sireg4        | Supervisor indirect register alias 4.          |
| 0x156  | SRW       | sireg5        | Supervisor indirect register alias 5.          |
| 0x157  | SRW       | sireg6        | Supervisor indirect register alias 6.          |
|        |           |               | Supervisor Protection and Translation          |
| 0x180  | SRW       | satp          | Supervisor address translation and protection. |
|        |           |               | Supervisor Timer Compare                       |
| 0x14D  | SRW       | stimecmp      | Supervisor timer compare.                      |
| 0x15D  | SRW       | stimecmph     | Upper 32 bits of stimecmp, RV32 only.          |
|        |           |               | Debug/Trace Registers                          |
| 0x5A8  | SRW       | scontext      | Supervisor-mode context register.              |
|        |           |               | Supervisor Resource Management Configuration   |
| 0x181  | SRW       | srmcfg        | Supervisor Resource Management Configuration.  |
|        |           |               | Supervisor State Enable Registers              |
| 0x10C  | SRW       | sstateen0     | Supervisor State Enable 0 Register.            |
| 0x10D  | SRW       | sstateen1     | Supervisor State Enable 1 Register.            |
| 0x10E  | SRW       | sstateen2     | Supervisor State Enable 2 Register.            |
|        |           |               |                                                |
| 0x10F  | SRW       | sstateen3     | Supervisor State Enable 3 Register.            |

| Number | Privilege | Name       | Description                                           |
|--------|-----------|------------|-------------------------------------------------------|
| 0x14E  | SRW       | sctrctl    | Supervisor Control Transfer Records Control Register. |
| 0x14F  | SRW       | sctrstatus | Supervisor Control Transfer Records Status Register.  |
| 0x15F  | SRW       | sctrdepth  | Supervisor Control Transfer Records Depth Register.   |

### <span id="page-25-0"></span>2.2.3. Currently allocated RISC-V hypervisor and VS CSR addresses

*Table 6. Currently allocated RISC-V hypervisor and VS CSR addresses.*

| Number | Privilege | Name        | Description                                                     |
|--------|-----------|-------------|-----------------------------------------------------------------|
|        |           |             | Hypervisor Trap Setup                                           |
| 0x600  | HRW       | hstatus     | Hypervisor status register.                                     |
| 0x602  | HRW       | hedeleg     | Hypervisor exception delegation register.                       |
| 0x603  | HRW       | hideleg     | Hypervisor interrupt delegation register.                       |
| 0x604  | HRW       | hie         | Hypervisor interrupt-enable register.                           |
| 0x606  | HRW       | hcounteren  | Hypervisor counter enable.                                      |
| 0x607  | HRW       | hgeie       | Hypervisor guest external interrupt-enable register.            |
| 0x612  | HRW       | hedelegh    | Upper 32 bits of hedeleg, RV32 only.                            |
|        |           |             | Hypervisor Trap Handling                                        |
| 0x643  | HRW       | htval       | Hypervisor trap value.                                          |
| 0x644  | HRW       | hip         | Hypervisor interrupt pending.                                   |
| 0x645  | HRW       | hvip        | Hypervisor virtual interrupt pending.                           |
| 0x64A  | HRW       | htinst      | Hypervisor trap instruction (transformed).                      |
| 0xE12  | HRO       | hgeip       | Hypervisor guest external interrupt pending.                    |
|        |           |             | Hypervisor Configuration                                        |
| 0x60A  | HRW       | henvcfg     | Hypervisor environment configuration register.                  |
| 0x61A  | HRW       | henvcfgh    | Upper 32 bits of henvcfg, RV32 only.                            |
|        |           |             | Hypervisor Protection and Translation                           |
| 0x680  | HRW       | hgatp       | Hypervisor guest address translation and protection.            |
|        |           |             | Debug/Trace Registers                                           |
| 0x6A8  | HRW       | hcontext    | Hypervisor-mode context register.                               |
|        |           |             | Hypervisor Counter/Timer Virtualization Registers               |
| 0x605  | HRW       | htimedelta  | Delta for VS/VU-mode timer.                                     |
| 0x615  | HRW       | htimedeltah | Upper 32 bits of htimedelta, RV32 only.                         |
|        |           |             | Hypervisor State Enable Registers                               |
| 0x60C  | HRW       | hstateen0   | Hypervisor State Enable 0 Register.                             |
| 0x60D  | HRW       | hstateen1   | Hypervisor State Enable 1 Register.                             |
| 0x60E  | HRW       | hstateen2   | Hypervisor State Enable 2 Register.                             |
| 0x60F  | HRW       | hstateen3   | Hypervisor State Enable 3 Register.                             |
| 0x61C  | HRW       | hstateen0h  | Upper 32 bits of Hypervisor State Enable 0 Register, RV32 only. |
| 0x61D  | HRW       | hstateen1h  | Upper 32 bits of Hypervisor State Enable 1 Register, RV32 only. |
|        | HRW       | hstateen2h  | Upper 32 bits of Hypervisor State Enable 2 Register, RV32 only. |
| 0x61E  |           |             |                                                                 |

| Number | Privilege                                                 | Name       | Description                                                   |  |
|--------|-----------------------------------------------------------|------------|---------------------------------------------------------------|--|
| 0x200  | HRW                                                       | vsstatus   | Virtual supervisor status register.                           |  |
| 0x204  | HRW                                                       | vsie       | Virtual supervisor interrupt-enable register.                 |  |
| 0x205  | HRW                                                       | vstvec     | Virtual supervisor trap handler base address.                 |  |
| 0x240  | HRW                                                       | vsscratch  | Virtual supervisor scratch register.                          |  |
| 0x241  | HRW                                                       | vsepc      | Virtual supervisor exception program counter.                 |  |
| 0x242  | HRW                                                       | vscause    | Virtual supervisor trap cause.                                |  |
| 0x243  | HRW                                                       | vstval     | Virtual supervisor trap value.                                |  |
| 0x244  | HRW                                                       | vsip       | Virtual supervisor interrupt pending.                         |  |
| 0x280  | HRW                                                       | vsatp      | Virtual supervisor address translation and protection.        |  |
|        | Virtual Supervisor Indirect                               |            |                                                               |  |
| 0x250  | HRW                                                       | vsiselect  | Virtual supervisor indirect register select.                  |  |
| 0x251  | HRW                                                       | vsireg     | Virtual supervisor indirect register alias.                   |  |
| 0x252  | HRW                                                       | vsireg2    | Virtual supervisor indirect register alias 2.                 |  |
| 0x253  | HRW                                                       | vsireg3    | Virtual supervisor indirect register alias 3.                 |  |
| 0x255  | HRW                                                       | vsireg4    | Virtual supervisor indirect register alias 4.                 |  |
| 0x256  | HRW                                                       | vsireg5    | Virtual supervisor indirect register alias 5.                 |  |
| 0x257  | HRW                                                       | vsireg6    | Virtual supervisor indirect register alias 6.                 |  |
|        | Virtual Supervisor Timer Compare                          |            |                                                               |  |
| 0x24D  | HRW                                                       | vstimecmp  | Virtual supervisor timer compare.                             |  |
| 0x25D  | HRW                                                       | vstimecmph | Upper 32 bits of vstimecmp, RV32 only.                        |  |
|        | Virtual Supervisor Control Transfer Records Configuration |            |                                                               |  |
| 0x24E  | HRW                                                       | vsctrctl   | Virtual Supervisor Control Transfer Records Control Register. |  |
|        |                                                           |            |                                                               |  |

#### <span id="page-27-1"></span><span id="page-27-0"></span>2.2.4. Currently allocated RISC-V machine-level CSR addresses

*Table 7. Currently allocated RISC-V machine-level CSR addresses.*

| Number             | Privilege             | Name       | Description                                    |  |  |
|--------------------|-----------------------|------------|------------------------------------------------|--|--|
|                    |                       |            | Machine Information Registers                  |  |  |
| 0xF11              | MRO                   | mvendorid  | Vendor ID.                                     |  |  |
| 0xF12              | MRO                   | marchid    | Architecture ID.                               |  |  |
| 0xF13              | MRO                   | mimpid     | Implementation ID.                             |  |  |
| 0xF14              | MRO                   | mhartid    | Hardware thread ID.                            |  |  |
| 0xF15              | MRO                   | mconfigptr | Pointer to configuration data structure.       |  |  |
| Machine Trap Setup |                       |            |                                                |  |  |
| 0x300              | MRW                   | mstatus    | Machine status register.                       |  |  |
| 0x301              | MRW                   | misa       | ISA and extensions                             |  |  |
| 0x302              | MRW                   | medeleg    | Machine exception delegation register.         |  |  |
| 0x303              | MRW                   | mideleg    | Machine interrupt delegation register.         |  |  |
| 0x304              | MRW                   | mie        | Machine interrupt-enable register.             |  |  |
| 0x305              | MRW                   | mtvec      | Machine trap-handler base address.             |  |  |
| 0x306              | MRW                   | mcounteren | Machine counter enable.                        |  |  |
| 0x310              | MRW                   | mstatush   | Additional machine status register, RV32 only. |  |  |
| 0x312              | MRW                   | medelegh   | Upper 32 bits of medeleg, RV32 only.           |  |  |
|                    |                       |            | Machine Trap Handling                          |  |  |
| 0x340              | MRW                   | mscratch   | Machine scratch register.                      |  |  |
| 0x341              | MRW                   | mepc       | Machine exception program counter.             |  |  |
| 0x342              | MRW                   | mcause     | Machine trap cause.                            |  |  |
| 0x343              | MRW                   | mtval      | Machine trap value.                            |  |  |
| 0x344              | MRW                   | mip        | Machine interrupt pending.                     |  |  |
| 0x34A              | MRW                   | mtinst     | Machine trap instruction (transformed).        |  |  |
| 0x34B              | MRW                   | mtval2     | Machine second trap value.                     |  |  |
|                    | Machine Indirect      |            |                                                |  |  |
| 0x350              | MRW                   | miselect   | Machine indirect register select.              |  |  |
| 0x351              | MRW                   | mireg      | Machine indirect register alias.               |  |  |
| 0x352              | MRW                   | mireg2     | Machine indirect register alias 2.             |  |  |
| 0x353              | MRW                   | mireg3     | Machine indirect register alias 3.             |  |  |
| 0x355              | MRW                   | mireg4     | Machine indirect register alias 4.             |  |  |
| 0x356              | MRW                   | mireg5     | Machine indirect register alias 5.             |  |  |
| 0x357              | MRW                   | mireg6     | Machine indirect register alias 6.             |  |  |
|                    | Machine Configuration |            |                                                |  |  |
| 0x30A              | MRW                   | menvcfg    | Machine environment configuration register.    |  |  |
| 0x31A              | MRW                   | menvcfgh   | Upper 32 bits of menvcfg, RV32 only.           |  |  |
| 0x747              | MRW                   | mseccfg    | Machine security configuration register.       |  |  |
| 0x757              | MRW                   | mseccfgh   | Upper 32 bits of mseccfg, RV32 only.           |  |  |
|                    |                       |            | Machine Memory Protection                      |  |  |

| Number | Privilege | Name           | Description                                                  |
|--------|-----------|----------------|--------------------------------------------------------------|
| 0x3A0  | MRW       | pmpcfg0        | Physical memory protection configuration.                    |
| 0x3A1  | MRW       | pmpcfg1        | Physical memory protection configuration, RV32 only.         |
| 0x3A2  | MRW       | pmpcfg2        | Physical memory protection configuration.                    |
| 0x3A3  | MRW       | pmpcfg3        | Physical memory protection configuration, RV32 only.         |
|        |           | ⋯              |                                                              |
| 0x3AE  | MRW       | pmpcfg14       | Physical memory protection configuration.                    |
| 0x3AF  | MRW       | pmpcfg15       | Physical memory protection configuration, RV32 only.         |
| 0x3B0  | MRW       | pmpaddr0       | Physical memory protection address register.                 |
| 0x3B1  | MRW       | pmpaddr1       | Physical memory protection address register.                 |
|        |           | ⋯              |                                                              |
| 0x3EF  | MRW       | pmpaddr63      | Physical memory protection address register.                 |
|        |           |                | Machine State Enable Registers                               |
| 0x30C  | MRW       | mstateen0      | Machine State Enable 0 Register.                             |
| 0x30D  | MRW       | mstateen1      | Machine State Enable 1 Register.                             |
| 0x30E  | MRW       | mstateen2      | Machine State Enable 2 Register.                             |
| 0x30F  | MRW       | mstateen3      | Machine State Enable 3 Register.                             |
| 0x31C  | MRW       | mstateen0h     | Upper 32 bits of Machine State Enable 0 Register, RV32 only. |
| 0x31D  | MRW       | mstateen1h     | Upper 32 bits of Machine State Enable 1 Register, RV32 only. |
| 0x31E  | MRW       | mstateen2h     | Upper 32 bits of Machine State Enable 2 Register, RV32 only. |
| 0x31F  | MRW       | mstateen3h     | Upper 32 bits of Machine State Enable 3 Register, RV32 only. |
|        |           |                | Machine Non-Maskable Interrupt Handling                      |
| 0x740  | MRW       | mnscratch      | Resumable NMI scratch register.                              |
| 0x741  | MRW       | mnepc          | Resumable NMI program counter.                               |
| 0x742  | MRW       | mncause        | Resumable NMI cause.                                         |
| 0x744  | MRW       | mnstatus       | Resumable NMI status.                                        |
|        |           |                | Machine Counter/Timers                                       |
| 0xB00  | MRW       | mcycle         | Machine cycle counter.                                       |
| 0xB02  | MRW       | minstret       | Machine instructions-retired counter.                        |
| 0xB03  | MRW       | mhpmcounter3   | Machine performance-monitoring counter.                      |
| 0xB04  | MRW       | mhpmcounter4   | Machine performance-monitoring counter.                      |
|        |           | ⋮              |                                                              |
| 0xB1F  | MRW       | mhpmcounter31  | Machine performance-monitoring counter.                      |
| 0xB80  | MRW       | mcycleh        | Upper 32 bits of mcycle, RV32 only.                          |
| 0xB82  | MRW       | minstreth      | Upper 32 bits of minstret, RV32 only.                        |
| 0xB83  | MRW       | mhpmcounter3h  | Upper 32 bits of mhpmcounter3, RV32 only.                    |
| 0xB84  | MRW       | mhpmcounter4h  | Upper 32 bits of mhpmcounter4, RV32 only.                    |
|        |           | ⋮              |                                                              |
| 0xB9F  | MRW       | mhpmcounter31h | Upper 32 bits of mhpmcounter31, RV32 only.                   |
|        |           |                | Machine Counter Setup                                        |

| Number | Privilege                                                            | Name          | Description                                     |  |
|--------|----------------------------------------------------------------------|---------------|-------------------------------------------------|--|
| 0x320  | MRW                                                                  | mcountinhibit | Machine counter-inhibit register.               |  |
| 0x321  | MRW                                                                  | mcyclecfg     | Machine cycle counter configuration register.   |  |
| 0x322  | MRW                                                                  | minstretcfg   | Machine instret counter configuration register. |  |
| 0x323  | MRW                                                                  | mhpmevent3    | Machine performance-monitoring event selector.  |  |
| 0x324  | MRW                                                                  | mhpmevent4    | Machine performance-monitoring event selector.  |  |
|        |                                                                      | ⋮             |                                                 |  |
| 0x33F  | MRW                                                                  | mhpmevent31   | Machine performance-monitoring event selector.  |  |
| 0x721  | MRW                                                                  | mcyclecfgh    | Upper 32 bits of mcyclecfg, RV32 only.          |  |
| 0x722  | MRW                                                                  | minstretcfgh  | Upper 32 bits of minstretcfg, RV32 only.        |  |
| 0x723  | MRW                                                                  | mhpmevent3h   | Upper 32 bits of mhpmevent3, RV32 only.         |  |
| 0x724  | MRW                                                                  | mhpmevent4h   | Upper 32 bits of mhpmevent4, RV32 only.         |  |
|        |                                                                      | ⋮             |                                                 |  |
| 0x73F  | MRW                                                                  | mhpmevent31h  | Upper 32 bits of mhpmevent31, RV32 only.        |  |
|        |                                                                      |               | Machine Control Transfer Records Configuration  |  |
| 0x34E  | MRW<br>Machine Control Transfer Records Control Register.<br>mctrctl |               |                                                 |  |
|        |                                                                      |               | Debug/Trace Registers (shared with Debug Mode)  |  |
| 0x7A0  | MRW                                                                  | tselect       | Debug/Trace trigger register select.            |  |
| 0x7A1  | MRW                                                                  | tdata1        | First Debug/Trace trigger data register.        |  |
| 0x7A2  | MRW                                                                  | tdata2        | Second Debug/Trace trigger data register.       |  |
| 0x7A3  | MRW                                                                  | tdata3        | Third Debug/Trace trigger data register.        |  |
| 0x7A8  | MRW                                                                  | mcontext      | Machine-mode context register.                  |  |
|        | Debug Mode Registers                                                 |               |                                                 |  |
| 0x7B0  | DRW                                                                  | dcsr          | Debug control and status register.              |  |
| 0x7B1  | DRW                                                                  | dpc           | Debug program counter.                          |  |
| 0x7B2  | DRW                                                                  | dscratch0     | Debug scratch register 0.                       |  |
| 0x7B3  | DRW                                                                  | dscratch1     | Debug scratch register 1.                       |  |

### <span id="page-30-0"></span>2.2.5. Currently allocated RISC-V indirect CSR (Smcsrind) mappings

*Table 8. Currently allocated RISC-V indirect CSR (Smcsrind) mappings - M-mode*

| miselect | mireg       | mireg2 | mireg3 | mireg4 | mireg5 | mireg6 |
|----------|-------------|--------|--------|--------|--------|--------|
| 0x30     | iprio0      | none   | none   | none   | none   | none   |
| …        | …           | …      | …      | …      | …      | …      |
| 0x3F     | iprio15     | none   | none   | none   | none   | none   |
| 0x70     | eidelivery  | none   | none   | none   | none   | none   |
| 0x71     | 0           | none   | none   | none   | none   | none   |
| 0x72     | eithreshold | none   | none   | none   | none   | none   |
| 0x73     | 0           | none   | none   | none   | none   | none   |
| …        | …           | …      | …      | …      | …      | …      |
| 0x7F     | 0           | none   | none   | none   | none   | none   |
| 0x80     | eip0        | none   | none   | none   | none   | none   |
| …        | …           | …      | …      | …      | …      | …      |
| 0xBF     | eip63       | none   | none   | none   | none   | none   |
| 0xC0     | eie0        | none   | none   | none   | none   | none   |
| …        | …           | …      | …      | …      | …      | …      |
| 0xFF     | eie63       | none   | none   | none   | none   | none   |

*Table 9. Currently allocated RISC-V indirect CSR (Smcsrind/Sscsrind) mappings - S-mode*

| siselect | sireg        | sireg2     | sireg3 | sireg4            | sireg5      | sireg6 |
|----------|--------------|------------|--------|-------------------|-------------|--------|
| 0x30     | iprio0       | none       | none   | none              | none        | none   |
| …        | …            | …          | …      | …                 | …           | …      |
| 0x3F     | iprio15      | none       | none   | none              | none        | none   |
| 0x40     | cycle        | cyclecfg   | none   | cycleh            | cyclecfgh   | none   |
| 0x41     | none         | none       | none   | none              | none        | none   |
| 0x42     | instret      | instretcfg | none   | instreth          | instretcfgh | none   |
| 0x43     | hpmcounter3  | hpmevent3  | none   | hpmcounter3h      | hpmevent3h  | none   |
| …        | …            | …          | …      | …                 | …           | …      |
| 0x5F     | hpmcounter31 | hpmevent31 | none   | hpmcounter31<br>h | hpmevent31h | none   |
| 0x70     | eidelivery   | none       | none   | none              | none        | none   |
| 0x71     | 0            | none       | none   | none              | none        | none   |
| 0x72     | eithreshold  | none       | none   | none              | none        | none   |
| 0x73     | 0            | none       | none   | none              | none        | none   |
| …        | …            | …          | …      | …                 | …           | …      |
| 0x7F     | 0            | none       | none   | none              | none        | none   |
| 0x80     | eip0         | none       | none   | none              | none        | none   |
| …        | …            | …          | …      | …                 | …           | …      |
| 0xBF     | eip63        | none       | none   | none              | none        | none   |

| siselect | sireg        | sireg2       | sireg3     | sireg4 | sireg5 | sireg6 |
|----------|--------------|--------------|------------|--------|--------|--------|
| OxC0     | eie0         | none         | none       | none   | none   | none   |
|          |              |              |            |        |        |        |
| OxFF     | eie63        | none         | none       | none   | none   | none   |
| 0x200    | ctrsource0   | ctrtarget0   | ctrdata0   | 0      | 0      | 0      |
|          |              |              |            |        |        |        |
| Ox2FF    | ctrsource255 | ctrtarget255 | ctrdata255 | 0      | 0      | 0      |

Table 10. Currently allocated RISC-V indirect CSR (Smcsrind/Sscsrind) mappings - VS-mode

| vsiselect | vsireg       | vsireg2      | vsireg3    | vsireg4 | vsireg5 | vsireg6 |
|-----------|--------------|--------------|------------|---------|---------|---------|
| 0x30      | iprio0       | none         | none       | none    | none    | none    |
|           |              |              |            |         |         |         |
| Ox3F      | iprio15      | none         | none       | none    | none    | none    |
| 0x70      | eidelivery   | none         | none       | none    | none    | none    |
| Ox71      | О            | none         | none       | none    | none    | none    |
| Ox72      | eithreshold  | none         | none       | none    | none    | none    |
| Ox73      | О            | none         | none       | none    | none    | none    |
|           |              |              |            |         |         |         |
| Ox7F      | О            | none         | none       | none    | none    | none    |
| 0x80      | eip0         | none         | none       | none    | none    | none    |
|           |              |              |            |         |         |         |
| OxBF      | eip63        | none         | none       | none    | none    | none    |
| OxCO      | eie0         | none         | none       | none    | none    | none    |
|           |              |              |            |         |         |         |
| OxFF      | eie63        | none         | none       | none    | none    | none    |
| 0x200     | ctrsource0   | ctrtarget0   | ctrdata0   | О       | О       | О       |
|           |              |              |            |         |         |         |
| Ox2FF     | ctrsource255 | ctrtarget255 | ctrdata255 | 0       | О       | 0       |

## <span id="page-31-0"></span>2.3. CSR Field Specifications

The following definitions and abbreviations are used in specifying the behavior of fields within the CSRs.

### <span id="page-31-1"></span>2.3.1. Reserved Writes Preserve Values, Reads Ignore Values (WPRI)

Some whole read/write fields are reserved for future use. Software should ignore the values read from these fields, and should preserve the values held in these fields when writing values to other fields of the same register. For forward compatibility, implementations that do not furnish these fields must make them read-only zero. These fields are labeled WPRI in the register descriptions.

![](_page_31_Picture_8.jpeg)

To simplify the software model, any backward-compatible future definition of previously reserved fields within a CSR must cope with the possibility that a non-atomic read/modify/write sequence is used to update other fields in the CSR. Alternatively, the

*original CSR definition must specify that subfields can only be updated atomically, which may require a two-instruction clear bit/set bit sequence in general that can be problematic if intermediate values are not legal.*

#### <span id="page-32-0"></span>2.3.2. Write/Read Only Legal Values (WLRL)

Some read/write CSR fields specify behavior for only a subset of possible bit encodings, with other bit encodings reserved. Software should not write anything other than legal values to such a field, and should not assume a read will return a legal value unless the last write was of a legal value, or the register has not been written since another operation (e.g., reset) set the register to a legal value. These fields are labeled WLRL in the register descriptions.

![](_page_32_Picture_4.jpeg)

*Hardware implementations need only implement enough state bits to differentiate between the supported values, but must always return the complete specified bit-encoding of any supported value when read.*

Implementations are permitted but not required to raise an illegal-instruction exception if an instruction attempts to write a non-supported value to a WLRL field. Implementations can return arbitrary bit patterns on the read of a WLRL field when the last write was of an illegal value, but the value returned should deterministically depend on the illegal written value and the value of the field prior to the write.

#### <span id="page-32-1"></span>2.3.3. Write Any Values, Reads Legal Values (WARL)

Some read/write CSR fields are only defined for a subset of bit encodings, but allow any value to be written while guaranteeing to return a legal value whenever read. Assuming that writing the CSR has no other side effects, the range of supported values can be determined by attempting to write a desired setting then reading to see if the value was retained. These fields are labeled WARL in the register descriptions.

Implementations will not raise an exception on writes of unsupported values to a WARL field. Implementations can return any legal value on the read of a WARL field when the last write was of an illegal value, but the legal value returned should deterministically depend on the illegal written value and the architectural state of the hart.

## <span id="page-32-2"></span>2.4. CSR Field Modulation

If a write to one CSR changes the set of legal values allowed for a field of a second CSR, then unless specified otherwise, the second CSR's field immediately gets an UNSPECIFIED value from among its new legal values. This is true even if the field's value before the write remains legal after the write; the value of the field may be changed in consequence of the write to the controlling CSR.

> *As a special case of this rule, the value written to one CSR may control whether a field of a second CSR is writable (with multiple legal values) or is read-only. When a write to the controlling CSR causes the second CSR's field to change from previously read-only to now writable, that field immediately gets an* UNSPECIFIED *but legal value, unless specified otherwise.*

![](_page_32_Picture_13.jpeg)

*Some CSR fields are, when writable, defined as aliases of other CSR fields. Let x be such a CSR field, and let y be the CSR field it aliases when writable. If a write to a controlling CSR causes field x to change from previously read-only to now writable, the new value of x is not* UNSPECIFIED *but instead immediately reflects the existing value of its alias y, as required.*

A change to the value of a CSR for this reason is not a write to the affected CSR and thus does not trigger any side effects specified for that CSR.

## <span id="page-33-0"></span>2.5. Implicit Reads of CSRs

Implementations sometimes perform *implicit* reads of CSRs. (For example, all S-mode instruction fetches implicitly read the satp CSR.) Unless otherwise specified, the value returned by an implicit read of a CSR is the same value that would have been returned by an explicit read of the CSR, using a CSR-access instruction in a sufficient privilege mode.

## <span id="page-33-1"></span>2.6. CSR Width Modulation

If the width of a CSR is changed (for example, by changing SXLEN or UXLEN, as described in [Section](#page-41-0) [3.1.6.3](#page-41-0)), the values of the *writable* fields and bits of the new-width CSR are, unless specified otherwise, determined from the previous-width CSR as though by this algorithm:

- 1. The value of the previous-width CSR is copied to a temporary register of the same width.
- 2. For the read-only bits of the previous-width CSR, the bits at the same positions in the temporary register are set to zeros.
- 3. The width of the temporary register is changed to the new width. If the new width *W* is narrower than the previous width, the least-significant *W* bits of the temporary register are retained and the moresignificant bits are discarded. If the new width is wider than the previous width, the temporary register is zero-extended to the wider width.
- 4. Each writable field of the new-width CSR takes the value of the bits at the same positions in the temporary register.

Changing the width of a CSR is not a read or write of the CSR and thus does not trigger any side effects.

## <span id="page-33-2"></span>2.7. Explicit Accesses to CSRs Wider than XLEN

If a standard CSR is wider than XLEN bits, then an explicit read of the CSR returns the register's leastsignificant XLEN bits, and an explicit write to the CSR modifies only the register's least-significant XLEN bits, leaving the upper bits unchanged.

Some standard CSRs, such as the counter CSRs of extension Zicntr, are always 64 bits, even when XLEN=32 (RV32). For each such 64-bit CSR (for example, counter time), a corresponding 32-bit *high-half CSR* is usually defined with the same name but with the letter 'h' appended at the end (timeh). The highhalf CSR aliases bits 63:32 of its namesake 64-bit CSR, thus providing a way for RV32 software to read and modify the otherwise-unreachable 32 bits.

Standard high-half CSRs are accessible only when the base RISC-V instruction set is RV32 (XLEN=32). For RV64 (when XLEN=64), the addresses of all standard high-half CSRs are reserved, so an attempt to access a high-half CSR typically raises an illegal-instruction exception.
