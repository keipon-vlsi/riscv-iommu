# <span id="page-61-0"></span>Chapter 5. Debug support

To support software debug, the IOMMU may provide an optional register interface that may be used by software to request IOMMU to perform an address translation. The IOMMU supports this capability when capabilities.DBG is 1. The interface consists of two set of registers; translation-request registers that are used by software to program an IOVA and other inputs needed by the process to translate an IOVA [\(Section](#page-36-0) [3.3](#page-36-0)) as an Untranslated Request. The result of the translation, if the process completes successfully, is reported through the translation-response registers. If the process stops due to faults then the faults are reported normally in the fault-queue and the translation-response registers updated with a failure indicator. If the IOVA is determined to be that of a virtual interrupt file ([Section 3.1.3.6](#page-31-0)) and the corresponding MSI PTE is in MRIF mode, then the process stops and reports a "Transaction type disallowed" (cause = 260) fault.

When the process to translate an IOVA is invoked for this purpose, the IOMMU may or may not cache first-stage PTEs, second-stage PTEs, DDT entries, PDT entries, or MSI PTEs accessed for the translation process in the IOATC. The IOMMU is allowed to use any PTEs or directory structure entries that may already be cached in the IOATC. The IOMMU may update the Accessed (A) and/or Dirty (D) bits in the PTEs used for the translation process if supported by the IOMMU. When the IOMMU implements a HPM, the HPM counters may be updated normally by the IOMMU. For the purpose of counting in the HPM, these requests are treated as Untranslated Requests.

The translation-request interface consists of the following 64-bit WARL registers:

- ⚫ tr\_req\_iova ([Section 6.24\)](#page-83-0)
- ⚫ tr\_req\_ctl [\(Section 6.25\)](#page-83-1)

The translation-response interface consists of a single 64-bit RO register tr\_response [\(Section 6.26](#page-84-0))

To request a translation, the tr\_req\_iova register is written first with the desired IOVA and the tr\_req\_ctl register is written next. The 'Go/Busy` bit is set in tr\_req\_ctl to indicate a valid request in the registers. The Go/Busy bit is a read-write-sticky (RWS) bit that once set cannot be cleared by writing the register. The Go/Busy bit will be cleared to 0 by the IOMMU when the process completes (successfully or due to encountering a fault). When the Go/Busy bit goes from 1 to 0, a response is valid in the tr\_response register.

When the Go/Busy bit is 1, the IOMMU behavior is UNSPECIFIED if:

- ⚫ The tr\_req\_iova or tr\_req\_ctl are modified.
- ⚫ IOMMU configurations, such as ddtp.iommu\_mode, are modified.

The time to complete a translation request through this debug interface is UNSPECIFIED but is required to be finite. If the IOMMU is serving translation requests from the IO bridge when a request is made through this register interface then the time to complete the request may be longer than when the IOMMU is otherwise idle.

![](_page_61_Picture_13.jpeg)

*The debug interface is optional but recommended to be implemented to aid software debug and to implement architectural compliance tests.*
