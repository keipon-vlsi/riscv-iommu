## <span id="page-155-0"></span>Chapter 16. "Svadu" Extension for Hardware Updating of A/D Bits, Version 1.0

The Svadu extension adds support and CSR controls for hardware updating of PTE A/D bits.

If the Svadu extension is implemented, the menvcfg.ADUE field is writable. If the hypervisor extension is additionally implemented, the henvcfg.ADUE field is also writable. See [Section 3.1.18](#page-62-0) and [Section 22.2.5](#page-171-0) for the definitions of those fields.

[Section 12.3.1](#page-139-1) defines the semantics of hardware updating of A/D bits. When hardware updating of A/D bits is disabled, the Svade extension, which mandates exceptions when A/D bits need be set, instead takes effect. The Svade extension is also defined in [Section 12.3.1.](#page-139-1)
