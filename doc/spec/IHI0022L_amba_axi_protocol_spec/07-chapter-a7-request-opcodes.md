# <span id="page-122-0"></span>Chapter A7 **Request Opcodes**

The request Opcode indicates the function of a request and how it must be processed by a Subordinate.

This chapter summarizes all Opcodes that are available with links in the tables to detailed descriptions of how they work.

It contains the following sections:

- [A7.1](#page-123-0) *[Opcode signaling](#page-123-0)*
- [A7.2](#page-125-0) *[AWSNOOP encodings](#page-125-0)*
- [A7.3](#page-128-0) *[ARSNOOP encodings](#page-128-0)*

# <span id="page-123-0"></span>**A7.1 Opcode signaling**

The request Opcode is communicated using the AWSNOOP and ARSNOOP signals.

**Table A7.1: AxSNOOP signals**

<span id="page-123-2"></span>

| Name    | Width         | Default                                                                                  | Description                                   |
|---------|---------------|------------------------------------------------------------------------------------------|-----------------------------------------------|
| AWSNOOP | AWSNOOP_WIDTH | 0x00<br>(WriteNoSnoop /<br>WriteUniquePtl /<br>Atomic /<br>WriteExclusive /<br>WriteACT) | Opcode for requests using the write channels. |
| ARSNOOP | ARSNOOP_WIDTH | 0x0 (ReadNoSnoop<br>/ ReadOnce /<br>ReadExclusive /<br>ReadACT)                          | Opcode for requests using the read channels.  |

<span id="page-123-3"></span>WriteNoSnoop, WriteUniquePtl, ReadNoSnoop and ReadOnce are default Opcodes and are used for generic requests.

<span id="page-123-1"></span>The AxSNOOP width properties are defined in [Table](#page-123-1) [A7.2.](#page-123-1)

**Table A7.2: AxSNOOP width properties**

| Name          | Values  | Default | Description               |
|---------------|---------|---------|---------------------------|
| AWSNOOP_WIDTH | 0, 4, 5 | 4       | Width of AWSNOOP in bits. |
| ARSNOOP_WIDTH | 0, 4    | 4       | Width of ARSNOOP in bits. |

If any of the following properties are not False, AWSNOOP\_WIDTH must be 5:

- WriteDeferrable\_Transaction
- UnstashTranslation\_Transaction
- InvalidateHint\_Transaction

If any of the following properties are not False, AWSNOOP\_WIDTH must be 4 or 5:

- Shareable\_Cache\_Support
- WriteNoSnoopFull\_Transaction
- CMO\_On\_Write
- WriteZero\_Transaction
- Cache\_Stash\_Transactions
- Untranslated\_Transactions
- Prefetch\_Transaction

If any of the following properties are not False, ARSNOOP\_WIDTH must be 4:

- Shareable\_Cache\_Support
- DeAllocation\_Transactions

#### *Chapter A7. Request Opcodes A7.1. Opcode signaling*

- CMO\_On\_Read
- DVM\_Message\_Support

Any AxSNOOP bits not driven by an interface are assumed to be LOW.

A Manager that only uses Opcodes where AWSNOOP is LOW can set AWSNOOP\_WIDTH to 0 which omits the AWSNOOP output from its interface. An attached Subordinate must have its AWSNOOP input tied LOW.

A Manager that only uses Opcodes where ARSNOOP is LOW can set ARSNOOP\_WIDTH to 0 which omits the ARSNOOP output from its interface. An attached Subordinate must have its ARSNOOP input tied LOW.

# <span id="page-125-0"></span>**A7.2 AWSNOOP encodings**

The encodings for AWSNOOP are shown in [Table](#page-125-1) [A7.3.](#page-125-1) Some Opcodes depend on the Domain of the request. The Enable column lists the property expression that determines whether a Manager interface is permitted to use the Opcode and a Subordinate interface supports it.

Unlisted combinations of AWSNOOP and AWDOMAIN are illegal.

**Table A7.3: AWSNOOP encodings**

<span id="page-125-1"></span>

| AWSNOOP | AWDOMAIN1    | Opcode           | Enable                                                     | Description                                                                                                                                                                                   |
|---------|--------------|------------------|------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0b00000 | NSH, SYS     | WriteNoSnoop     | -                                                          | Write to a Non-shareable or<br>System location.                                                                                                                                               |
|         | SH           | WriteUniquePtl   | Shareable_Transactions                                     | Write to a Shareable location.                                                                                                                                                                |
|         | NSH, SH, SYS | Atomic           | Atomic_Transactions                                        | Atomic transaction, indicated by<br>nonzero AWATOP signal.                                                                                                                                    |
|         | NSH, SYS     | WriteExclusive   | Exclusive_Accesses                                         | Exclusive write access, indicated<br>by AWLOCK asserted.                                                                                                                                      |
|         | SYS          | WriteACT         | ACT_Support                                                | ACT write access, indicated by<br>AWACTV asserted.                                                                                                                                            |
| 0b00001 | NSH, SYS     | WriteNoSnoopFull | WriteNoSnoopFull_Transaction<br>or Shareable_Cache_Support | Cache line sized and Regular write<br>to a Non-shareable location.                                                                                                                            |
|         | SH           | WriteUniqueFull  | Shareable_Transactions                                     | Cache line sized and Regular write<br>to a Shareable location.                                                                                                                                |
| 0b00010 | -            | RESERVED         | -                                                          |                                                                                                                                                                                               |
| 0b00011 | SH           | WriteBackFull    | Shareable_Transactions and<br>Shareable_Cache_Support      | Cache line sized and Regular write<br>to a Shareable location. The line<br>was held in a coherent cache and<br>is Dirty.                                                                      |
| 0b00100 | -            | RESERVED         | -                                                          |                                                                                                                                                                                               |
| 0b00101 | SH           | WriteEvictFull   | Shareable_Transactions and<br>Shareable_Cache_Support      | Cache line sized and Regular write<br>to a Shareable location. The line<br>was held in a coherent cache and<br>is Clean.                                                                      |
| 0b00110 | NSH, SH      | CMO              | CMO_On_Write                                               | A data-less request which<br>indicates that a cache maintenance<br>operation must be performed. The<br>specific operation is encoded on<br>the AWCMO signal. Cache line<br>sized and Regular. |
| 0b00111 | NSH, SH, SYS | WriteZero        | WriteZero_Transaction                                      | Cache line sized and Regular<br>write, where the value of every<br>byte is zero.                                                                                                              |

Table A7.3 – *Continued from previous page*

| AWSNOOP | AWDOMAIN1    | Opcode               | Enable                                                    | Description                                                                                                                                                                                     |
|---------|--------------|----------------------|-----------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0b01000 | SH           | WriteUniquePtlStash  | Shareable_Transactions and<br>Cache_Stash_Transactions    | Write to a Shareable location with<br>an indication that the data should<br>be allocated into a cache. Cache<br>line sized or smaller.                                                          |
| 0b01001 | SH           | WriteUniqueFullStash | Shareable_Transactions and<br>Cache_Stash_Transactions    | Cache line sized and Regular write<br>to a Shareable location with an<br>indication that the data should be<br>allocated into a cache.                                                          |
| 0b01010 | NSH, SH      | WritePtlCMO          | Write_Plus_CMO                                            | Write where any cached copies of<br>the line must be cleaned and/or<br>invalidated according to the<br>AWCMO signal. Cache line sized<br>or smaller.                                            |
| 0b01011 | NSH, SH      | WriteFullCMO         | Write_Plus_CMO                                            | Cache line sized and Regular write<br>where any cached copies of the<br>line must be cleaned and/or<br>invalidated according to the<br>AWCMO signal.                                            |
| 0b01100 | NSH, SH      | StashOnceShared      | Cache_Stash_Transactions                                  | A data-less request which<br>indicates that a cache line should<br>be fetched into a cache. Other<br>copies of the line are not required<br>to be invalidated. Cache line sized<br>and Regular. |
| 0b01101 | NSH, SH      | StashOnceUnique      | Cache_Stash_Transactions                                  | A data-less request which<br>indicates that a cache line should<br>be fetched into a cache. It is<br>recommended that all other copies<br>are invalidated. Cache line sized<br>and Regular.     |
| 0b01110 | NSH, SH, SYS | StashTranslation     | Untranslated_Transactions and<br>Cache_Stash_Transactions | A data-less request which<br>indicates that a translation should<br>be cached in an MMU.                                                                                                        |
| 0b01111 | NSH, SH      | Prefetch             | Prefetch_Transaction                                      | A data-less request which<br>indicates that a Manager might<br>read the addressed cache line at a<br>later time. Cache line sized and<br>Regular.                                               |
| 0b10000 | SYS          | WriteDeferrable      | WriteDeferrable_Transaction                               | A 64-byte atomic write where the<br>Subordinate can give a DEFER or<br>UNSUPPORTED response.                                                                                                    |
| 0b10001 | NSH, SH, SYS | UnstashTranslation   | UnstashTranslation_Transaction                            | A data-less request which is a hint<br>that a translation is not likely to be<br>used again.                                                                                                    |

Table A7.3 – *Continued from previous page*

| AWSNOOP               | AWDOMAIN1 | Opcode         | Enable                     | Description                                                                                                                                                                                  |
|-----------------------|-----------|----------------|----------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0b10010               | NSH, SH   | InvalidateHint | InvalidateHint_Transaction | A data-less request which<br>indicates that a cache line is no<br>longer required and can be<br>invalidated. A write-back is<br>permitted but not required. Cache<br>line sized and Regular. |
| 0b10011 to<br>0b11111 | -         | RESERVED       | -                          | -                                                                                                                                                                                            |

<sup>1</sup> NSH is Non-shareable (0b00), SH is Shareable (0b01 or 0b10), SYS is System (0b11).

# <span id="page-128-0"></span>**A7.3 ARSNOOP encodings**

The encodings for ARSNOOP are shown in [Table](#page-128-1) [A7.4.](#page-128-1) Some Opcodes depend on the Domain of the request. The Enable column lists the property expression that determines whether a Manager interface is permitted to use the Opcode and a Subordinate interface supports it.

Unlisted combinations of ARSNOOP and ARDOMAIN are illegal.

**Table A7.4: ARSNOOP encodings**

<span id="page-128-1"></span>

| ARSNOOP | ARDOMAIN1 | Opcode               | Enable                                                  | Description                                                                                                                                                                        |
|---------|-----------|----------------------|---------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0b0000  | NSH, SYS  | ReadNoSnoop          | -                                                       | Read from a Non-shareable or<br>System location.                                                                                                                                   |
|         | SH        | ReadOnce             | Shareable_Transactions                                  | Read from a Shareable location<br>which the Manager will not<br>cache.                                                                                                             |
|         | NSH, SYS  | ReadExclusive        | Exclusive_Accesses                                      | Exclusive read access, indicated<br>by ARLOCK asserted.                                                                                                                            |
|         | SYS       | ReadACT              | ACT_Support                                             | ACT read access, indicated by<br>ARACTV asserted.                                                                                                                                  |
| 0b0001  | SH        | ReadShared           | Shareable_Transactions and<br>Shareable_Cache_Support   | Cache line sized and Regular<br>read from a Shareable location<br>which the Manager might cache.<br>Data can be Dirty.                                                             |
| 0b0010  | SH        | ReadClean            | Shareable_Transactions and<br>Shareable_Cache_Support   | Cache line sized and Regular<br>read from Shareable location<br>which the Manager might cache.<br>Data must not be Dirty.                                                          |
| 0b0011  | -         | RESERVED             | -                                                       | -                                                                                                                                                                                  |
| 0b0100  | SH        | ReadOnceCleanInvalid | Shareable_Transactions and<br>DeAllocation_Transactions | Read from a Shareable location<br>which the Manager will not<br>cache. Cached copies are<br>recommended to be cleaned and<br>invalidated. Cache line sized or<br>smaller.          |
| 0b0101  | SH        | ReadOnceMakeInvalid  | Shareable_Transactions and<br>DeAllocation_Transactions | Read from a Shareable location<br>which the Manager will not<br>cache. Cached copies are<br>recommended to be invalidated<br>without a write-back. Cache line<br>sized or smaller. |
| 0b0110  | -         | RESERVED             | -                                                       | -                                                                                                                                                                                  |
| 0b0111  | -         | RESERVED             | -                                                       | -                                                                                                                                                                                  |
| 0b1000  | NSH, SH   | CleanShared          | CMO_On_Read                                             | A request to clean all copies of a<br>cache line. Cache line sized and<br>Regular.                                                                                                 |

Table A7.4 – *Continued from previous page*

| ARSNOOP | ARDOMAIN1 | Opcode             | Enable                         | Description                                                                                                                                                            |
|---------|-----------|--------------------|--------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0b1001  | NSH, SH   | CleanInvalid       | CMO_On_Read                    | A request to clean and invalidate<br>all copies of a cache line. Cache<br>line sized and Regular.                                                                      |
| 0b1010  | NSH, SH   | CleanSharedPersist | CMO_On_Read and<br>Persist_CMO | A request to clean all copies of a<br>cache line. Cleaned data must<br>pass the Point of Persistence or<br>Point of Deep Persistence.<br>Cache line sized and Regular. |
| 0b1011  | -         | RESERVED           | -                              | -                                                                                                                                                                      |
| 0b1100  | -         | RESERVED           | -                              | -                                                                                                                                                                      |
| 0b1101  | NSH, SH   | MakeInvalid        | CMO_On_Read                    | A request to clean and invalidate<br>all copies of a cache line. Dirty<br>data is not required to be written<br>to memory. Cache line sized<br>and Regular.            |
| 0b1110  | SH        | DVM Complete       | DVM_Message_Support            | Indicates completion of a DVM<br>synchronization message.                                                                                                              |
| 0b1111  | -         | RESERVED           | -                              | -                                                                                                                                                                      |

<sup>1</sup> NSH is Non-shareable (0b00), SH is Shareable (0b01 or 0b10), SYS is System (0b11).
