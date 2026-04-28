## <span id="page-217-0"></span>Chapter 27. History

## <span id="page-217-1"></span>27.1. Research Funding at UC Berkeley

Development of the RISC-V architecture and implementations has been partially funded by the following sponsors.

- ⚫ Par Lab: Research supported by Microsoft (Award #024263) and Intel (Award #024894) funding and by matching funding by U.C. Discovery (Award #DIG07-10227). Additional support came from Par Lab affiliates Nokia, NVIDIA, Oracle, and Samsung.
- ⚫ Project Isis: DoE Award DE-SC0003624.
- ⚫ ASPIRE Lab: DARPA PERFECT program, Award HR0011-12-2-0016. DARPA POEM program Award HR0011-11-C-0100. The Center for Future Architectures Research (C-FAR), a STARnet center funded by the Semiconductor Research Corporation. Additional support from ASPIRE industrial sponsor, Intel, and ASPIRE affiliates, Google, Huawei, Nokia, NVIDIA, Oracle, and Samsung.

The content of this paper does not necessarily reflect the position or the policy of the US government and no official endorsement should be inferred.

## <span id="page-218-0"></span>Appendix A: Historical Rationale for Extensions

This appendix contains the rationale for RISC-V ISA extensions at the time they were ratified. Unlike the ISA specification, this appendix is ordered chronologically, so as to convey the motivation and architectural reasoning underpinning each extension at the time of ratification. For extensions ratified prior to the conception of this appendix (ca. 2025), the rationale will be added over time. In cases where the rationale was not recorded, the authors and editors will synthesize it from the historical record.

## <span id="page-218-1"></span>A.1. "Smepmp" Extension for PMP Enhancements for memory access and execution prevention in Machine mode

- 1. Since a CSR for security and / or global PMP behavior settings is not available with the current spec, we needed to define a new mseccfg CSR. This new CSR will allow us to add further security configuration options in the future and also allow developers to verify the existence of the new mechanisms defined on this extension.
- 2. There are use cases where developers want to enforce PMP rules in M-mode during the boot process, that are also able to modify, merge, and / or remove later on. Since a rule that is enforced in M-mode also needs to be locked (or else badly written or malicious M-mode software can remove it at any time), the only way for developers to approach this is to keep adding PMP rules to the chain and rely on rule priority. This is a waste of PMP rules and since it's only needed during boot, mseccfg.RLB is a simple workaround that can be used temporarily and then disabled and locked down.

Also when mseccfg.MML is set, according to 4b it's not possible to add a *Shared-Region* rule with executable privileges. So RLB can be set temporarily during the boot process to register such regions. Note that it's still possible to register executable *Shared-Region* rules using initial register settings (that may include mseccfg.MML being set and the rule being set on PMP registers) on PMP reset, without using RLB.

![](_page_218_Picture_7.jpeg)

Be aware that RLB introduces a security vulnerability if left set after the boot process is over and in general it should be used with caution, even when used temporarily. *Having editable PMP rules in M-mode gives a false sense of security since it only takes a few malicious instructions to lift any PMP restrictions this way. It doesn't make sense to have a security control in place and leave it unprotected. Rule Locking Bypass is only meant as a way to optimize the allocation of PMP rules, catch errors during debugging, and allow the bootrom/firmware to register executable Shared-Region rules. If developers / vendors have no use for such functionality, they should never set* mseccfg.RLB *and if possible hard-wire it to 0. In any case* RLB should be disabled and locked as soon as possible*.*

![](_page_218_Picture_9.jpeg)

*If* mseccfg.RLB *is not used and left unset, it will be locked as soon as a PMP rule/entry with the* pmpcfg.L *bit set is configured.*

![](_page_218_Picture_11.jpeg)

*Since PMP rules with a higher priority override rules with a lower priority, locked rules must precede non-locked rules.*

- 3. With the current spec M-mode can access any memory region unless restricted by a PMP rule with the pmpcfg.L bit set. There are cases where this approach is overly permissive, and although it's possible to restrict M-mode by adding PMP rules during the boot process, this can also be seen as a waste of PMP rules. Having the option to block anything by default, and use PMP as an allowlist for M-mode is considered a safer approach. This functionality may be used during the boot process or upon PMP reset, using initial register settings.
- 4. The current dual meaning of the pmpcfg.L bit that marks a rule as Locked and enforced on all modes is

neither flexible nor clean. With the introduction of *Machine Mode Lock-down* the pmpcfg.L bit distinguishes between rules that are enforced only in M-mode (*M-mode-only*) or only in S/U-modes (*S/U-mode-only*). The rule locking becomes part of the definition of an *M-mode-only* rule, since when a rule is added in M mode, if not locked, can be modified or removed in a few instructions. On the other hand, S/U modes can't modify PMP rules anyway so locking them doesn't make sense.

a. This separation between *M-mode-only* and *S/U-mode-only* rules also allows us to distinguish which regions are to be used by processes in Machine mode (pmpcfg.L == 1) and which by Supervisor or User mode processes (pmpcfg.L == 0), in the same way the U bit on the Virtual Memory's PTEs marks which Virtual Memory pages are to be used by User mode applications (U=1) and which by the Supervisor / OS (U=0). With this distinction in place we are able to implement memory access and execution prevention in M-mode for any physical memory region that is not *M-mode-only*.

An attacker that manages to tamper with a memory region used by S/U mode, even after successfully tricking a process running in M-mode to use or execute that region, will fail to perform a successful attack since that region will be *S/U-mode-only* hence any access when in M-mode will trigger an access exception.

![](_page_219_Picture_4.jpeg)

*In order to support zero-copy transfers between M-mode and S/U-mode we need to either allow shared memory regions, or introduce a mechanism similar to the* sstatus.SUM *bit to temporary allow the high-privileged mode (in this case M-mode) to be able to perform loads and stores on the region of a less-privileged process (in this case S/U-mode). In our case after discussion within the group it seemed a better idea to follow the first approach and have this functionality encoded on a per-rule basis to avoid the risk of leaving a temporary, global bypass active when exiting Mmode, hence rendering memory access prevention useless.*

![](_page_219_Picture_6.jpeg)

*Although it's possible to use* mstatus.MPRV *in M-mode to read/write data on an S/Umode-only region using general purpose registers for copying, this will happen with S/U-mode permissions, honoring any MMU restrictions put in place by S-mode. Of course it's still possible for M-mode to tamper with the page tables and / or add S/Umode-only rules and bypass the protections put in place by S-mode but if an attacker has managed to compromise M-mode to such extent, no security guarantees are possible in any way.* Also note that the threat model we present here assumes buggy software in M-mode, not compromised software*. We considered disabling* mstatus.MPRV *but it seemed too much and out of scope.*

*Shared-region* rules can be used both for zero-copy data transfers and for sharing code segments. The latter may be used for example to allow S/U-mode to execute code by the vendor, that makes use of some vendor-specific ISA extension, without having to go through the firmware with an ecall. This is similar to the vDSO approach followed on Linux, that allows user space code to execute kernel code without having to perform a system call.

To make sure that shared data regions can't be executed and shared code regions can't be modified, the encoding changes the meaning of the pmpcfg.X bit. In case of shared data regions, with the exception of the pmpcfg.LRWX=1111 encoding, the pmpcfg.X bit marks the capability of S/U-mode to write to that region, so it's not possible to encode an executable shared data region. In case of shared code regions, the pmpcfg.X bit marks the capability of M-mode to read from that region, and since pmpcfg.RW=01 is used for encoding the shared region, it's not possible to encode a shared writable code region.

![](_page_219_Picture_10.jpeg)

*For adding Shared-region rules with executable privileges to share code segments between M-mode and S/U-mode,* mseccfg.RLB *needs to be implemented, or else such rules can only be added together with* mseccfg.MML *being set on* PMP Reset*. That's because the reserved encoding* pmpcfg.RW=01 *being used for Shared-region rules is* *only defined when* mseccfg.MML *is set, and 4b prevents the addition of rules with executable privileges on M-mode after* mseccfg.MML *is set unless* mseccfg.RLB *is also set.*

*Using the* pmpcfg.LRWX=1111 *encoding for a locked shared read-only data region was decided later on, its initial meaning was an M-mode-only read/write/execute region. The reason for that change was that the already defined shared data regions were not locked, so r/w access to M-mode couldn't be restricted. In the same way we have execute-only shared code regions for both modes, it was decided to also be able to allow a least-privileged shared data region for both modes. This approach allows for example to share the .text section of an ELF with a shared code region and the .rodata section with a locked shared data region, without allowing M-mode to modify .rodata. We also decided that having a locked read/write/execute region in M-mode doesn't make much sense and could be dangerous, since M-mode won't be able to add further restrictions there (as in the case of S/U-mode where S-mode can further limit access to an* pmpcfg.LWRX=0111 *region through the MMU), leaving the possibility of modifying an executable region in M-mode open.*

![](_page_220_Picture_3.jpeg)

*For encoding Shared-region rules initially we used one of the two reserved bits on pmpcfg (bit 5) but in order to avoid allocating an extra bit, since those bits are a very limited resource, it was decided to use the reserved R=0,W=1 combination.*

- b. The idea with this restriction is that after the Firmware or the OS running in M-mode is initialized and mseccfg.MML is set, no new code regions are expected to be added since nothing else is expected to run in M-mode (everything else will run in S/U mode). Since we want to limit the attack surface of the system as much as possible, it makes sense to disallow any new code regions which may include malicious code, to be added/executed in M-mode.
- c. In case mseccfg.MMWP is not set, M-mode can still access and execute any region not covered by a PMP rule. Since we try to prevent M-mode from executing malicious code and since an attacker may manage to place code on some region not covered by PMP (e.g. a directly-addressable flash memory), we need to ensure that M-mode can only execute the code segments initialized during firmware / OS initialization.
- d. We are only using the encoding pmpcfg.RW=01 together with mseccfg.MML, if mseccfg.MML is not set the encoding remains usable for future use. == Bibliography

<span id="page-220-1"></span>*The RISC-V Debug Specification*. [github.com/riscv/riscv-debug-spec](https://github.com/riscv/riscv-debug-spec)

<span id="page-220-0"></span>Goldberg, R. P. (1974). Survey of virtual machine research. *Computer*, *7*(6), 34–45.

<span id="page-220-2"></span>Navarro, J., Iyer, S., Druschel, P., & Cox, A. (2002). Practical, Transparent Operating System Support for Superpages. *SIGOPS Oper. Syst. Rev.*, *36*(SI), 89–104. [doi.org/10.1145/844128.844138](https://doi.org/10.1145/844128.844138)

<span id="page-220-3"></span>Serebryany, K., Stepanov, E., Shlyapnikov, A., Tsyrklevich, V., & Vyukov, D. (2018). Memory Tagging and how it improves C/C++ memory safety. *CoRR*, *abs/1802.09517*. [arxiv.org/abs/1802.09517](http://arxiv.org/abs/1802.09517)