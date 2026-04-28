## <span id="page-207-0"></span>Chapter 24. "Ssdbltrp" Double Trap Extension, Version 1.0

The Ssdbltrp extension addresses a double trap (See [Section 3.1.6.2](#page-40-0)) privilege modes lower than M. It enables HS-mode to invoke a critical error handler in a virtual machine on a double trap in VS-mode. It also allows M-mode to invoke a critical error handler in the OS/Hypervisor on a double trap in S/HSmode.

The Ssdbltrp extension adds the menvcfg.DTE (See [Section 3.1.18](#page-62-0)) and the sstatus.SDT fields (See [Section](#page-121-2) [12.1.1\)](#page-121-2). If the hypervisor extension is additionally implemented, then the extension adds the henvcfg.DTE (See [Section 22.2.5](#page-171-0)) and the vsstatus.SDT fields (See [Section 22.2.11](#page-176-0)).

See [Section 12.1.1.5](#page-123-2) for the operational details.
