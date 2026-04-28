## <span id="page-102-0"></span>Chapter 9. "Smcdeleg/Ssccfg" Counter Delegation Extensions, Version 1.0

In modern "Rich OS" environments, hardware performance monitoring resources are managed by the kernel, kernel driver, and/or hypervisor. Counters may be configured with differing scopes, in some cases counting events system-wide, while in others counting events on behalf of a single virtual machine or application. In such environments, the latency of counter writes has a direct impact on overall profiling overhead as a result of frequent counter writes during:

- 1. Sample collection, to clear overflow indication, and reload overflowed counter(s)
- 2. Context switch, between processes, threads, containers, or virtual machines

These extensions provide a means for M-mode to allow writing select counters and event selectors from S/HS-mode. The purpose is to avert transitions to and from M-mode that add latency to these performance critical supervisor/hypervisor code sections. These extensions also defines one new CSR, scountinhibit.

For a Machine-level environment, extension Smcdeleg ('Sm' for Privileged architecture and Machine-level extension, 'cdeleg' for Counter Delegation) encompasses all added CSRs and all behavior modifications for a hart, over all privilege levels. For a Supervisor-level environment, extension Ssccfg ('Ss' for Privileged architecture and Supervisor-level extension, 'ccfg' for Counter Configuration) provides access to delegated counters, and to new supervisor-level state.For a RISC-V hardware platform, Smcdeleg and Ssccfg must always be implemented in tandem.

## <span id="page-102-1"></span>9.1. Counter Delegation

The mcounteren register allows M-mode to provide the next-lower privilege mode with read access to select counters.When the Smcdeleg/Ssccfg extensions are enabled (menvcfg.CDE=1), it further allows M-mode to delegate select counters to S-mode.

The siselect (and vsiselect) index range 0x40-0x5F is reserved for delegated counter access. When a counter *i* is delegated (mcounteren[*i*]=1 and menvcfg.CDE=1), the register state associated with counter *i* can be read or written via sireg\*, while siselect holds 0x40+*i*. The counter state accessible via alias CSRs is shown in the table below.

<span id="page-102-2"></span>

| siselect value | sireg         | sireg4         |              | sireg5        |  |
|----------------|---------------|----------------|--------------|---------------|--|
| 0x40           | cycle1        | cycleh1        | cyclecfg14   | cyclecfgh14   |  |
| 0x41           |               |                | See below    |               |  |
| 0x42           | instret1      | instreth1      | instretcfg14 | instretcfgh14 |  |
| 0x43           | hpmcounter32  | hpmcounter3h2  | hpmevent32   | hpmevent3h23  |  |
| …              | …             | …              | …            | …             |  |
| 0x5F           | hpmcounter312 | hpmcounter31h2 | hpmevent312  | hpmevent31h23 |  |

*Table 25. Indirect HPM State Mappings*

hpmevent*i* may represent a subset of the state accessed by the mhpmevent*i* register. Specifically, if Sscofpmf is implemented, event selector bit 62 (MINH) is read-only 0 when accessed through sireg\*.

Depends on Zicntr support

Depends on Zihpm support

<sup>3</sup> Depends on Sscofpmf support

<sup>4</sup> Depends on Smcntrpmf support

Likewise, cyclecfg and instretcfg may represent a subset of the state accessed by the mcyclecfg and minstretcfg registers, respectively. If Smcntrpmf is implemented, counter configuration register bit 62 (MINH) is read-only 0 when accessed through sireg\*.

If extension Smstateen is implemented, refer to extensions Smcsrind/Sscsrind [\(Chapter 5\)](#page-89-0) for how setting bit 60 of CSR mstateen0 to zero prevents access to registers siselect, sireg\*, vsiselect, and vsireg\* from privileged modes less privileged than M-mode, and likewise how setting bit 60 of hstateen0 to zero prevents access to siselect and sireg\* (really vsiselect and vsireg\*) from VS-mode.

The remaining rules of this section apply only when access to a CSR is not blocked by mstateen0[60] = 0 or hstateen0[60] = 0.

While the privilege mode is M or S and siselect holds a value in the range 0x40-0x5F, illegal-instruction exceptions are raised for the following cases:

\* attempts to access any sireg\* when menvcfg.CDE = 0; \* attempts to access sireg3 or sireg6; \* attempts to access sireg4 or sireg5 when XLEN = 64; \* attempts to access sireg\* when siselect = 0x41, or when the counter selected by siselect is not delegated to S-mode (the corresponding bit in mcounteren = 0).

![](_page_103_Picture_6.jpeg)

*The memory-mapped mtime register is not a performance monitoring counter to be managed by supervisor software, hence the special treatment of siselect value 0x41 described above.*

For each siselect and sireg\* combination defined in [Table 25,](#page-102-2) the table further indicates the extensions upon which the underlying counter state depends.If any extension upon which the underlying state depends is not implemented, an attempt from M or S mode to access the given state through sireg\* raises an illegal-instruction exception.

If the hypervisor (H) extension is also implemented, then as specified by extensions Smcsrind/Sscsrind, a virtual-instruction exception is raised for attempts from VS-mode or VU-mode to directly access vsiselect or vsireg\*, or attempts from VU-mode to access siselect or sireg\*. Furthermore, while vsiselect holds a value in the range 0x40-0x5F:

\* An attempt to access any vsireg\* from M or S mode raises an illegal-instruction exception. \* An attempt from VS-mode to access any sireg\* (really vsireg\*) raises an illegal-instruction exception if menvcfg.CDE = 0, or a virtual-instruction exception if menvcfg.CDE = 1.

## <span id="page-103-0"></span>9.2. Supervisor Counter Inhibit (**scountinhibit**) Register

Smcdeleg/Ssccfg defines a new scountinhibit register, a masked alias of mcountinhibit. For counters delegated to S-mode, the associated mcountinhibit bits can be accessed via scountinhibit.For counters not delegated to S-mode, the associated bits in scountinhibit are read-only zero.

When menvcfg.CDE=0, attempts to access scountinhibit raise an illegal-instruction exception. When Supervisor Counter Delegation is enabled, attempts to access scountinhibit from VS-mode or VU-mode raise a virtual-instruction exception.

## <span id="page-103-1"></span>9.3. Virtualizing **scountovf**

For implementations that support Smcdeleg/Ssccfg, Sscofpmf, and the H extension, when menvcfg.CDE=1, attempts to read scountovf from VS-mode or VU-mode raise a virtual-instruction exception.

## <span id="page-104-0"></span>9.4. Virtualizing Local-Counter-Overflow Interrupts

For implementations that support Smcdeleg, Sscofpmf, and Smaia, the local-counter-overflow interrupt (LCOFI) bit (bit 13) in each of CSRs mvip and mvien is implemented and writable.

For implementations that support Smcdeleg/Ssccfg, Sscofpmf, Smaia/Ssaia, and the H extension, the LCOFI bit (bit 13) in each of hvip and hvien is implemented and writable.

> *The hvip register is defined by the hypervisor (H) extension, while the mvip, mvien and hvien registers are defined by the Smaia/Ssaia extensions.*

![](_page_104_Picture_5.jpeg)

*By virtue of implementing hvip.LCOFI, it is implicit that the LCOFI bit (bit 13) in each of vsie and vsip is also implemented.*

*Requiring support for the LCOFI bits listed above ensures that virtual LCOFIs can be delivered to an OS running in S-mode, and to a guest OS running in VS-mode. It is optional whether the LCOFI bit (bit 13) in each of mideleg and hideleg, which allows all LCOFIs to be delegated to S-mode and VS-mode, respectively, is implemented and writable.*
