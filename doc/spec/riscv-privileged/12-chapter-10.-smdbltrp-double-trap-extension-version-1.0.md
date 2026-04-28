## <span id="page-105-0"></span>Chapter 10. "Smdbltrp" Double Trap Extension, Version 1.0

The Smdbltrp extension addresses a double trap (See [Section 3.1.6.2\)](#page-40-0) in M-mode. When the Smrnmi extension [\(Chapter 8](#page-99-0)) is implemented, it enables invocation of the RNMI handler on a double trap in Mmode to handle the critical error. If the Smrnmi extension is not implemented or if a double trap occurs during the RNMI handler's execution, this extension helps transition the hart to a critical error state and enables signaling the critical error to the platform.

To improve error diagnosis and resolution, this extension supports debugging harts in a critical error state. The extension introduces a mechanism to enter Debug Mode instead of asserting a critical-error signal to the platform when the hart is in a critical error state. See (*[The RISC-V Debug Specification](#page-220-1)*[, n.d.\)](#page-220-1) for details.

See [Section 3.1.6.2](#page-40-0) for the operational details.
