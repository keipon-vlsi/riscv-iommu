# <span id="page-305-0"></span>Chapter B4 **Revisions**

This appendix describes the technical changes between released issues of this specification.

It contains the following sections:

- [B4.1](#page-306-0) *[Differences between Issue H.c and Issue J](#page-306-0)*
- [B4.2](#page-308-0) *[Differences between Issue J and Issue K](#page-308-0)*
- [B4.3](#page-310-0) *[Differences between Issue K and Issue L](#page-310-0)*

# <span id="page-306-0"></span>**B4.1 Differences between Issue H.c and Issue J**

| Feature                                                                  | Change        | Detail                                                                                                                                                                                                                                                                         |  |
|--------------------------------------------------------------------------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--|
| AXI3, AXI4, AXI4-Lite<br>interfaces                                      | Removal       | AXI3, AXI4, and AXI4-Lite content is removed from the specification.<br>These interface types are not recommended for new designs and have<br>been superseded by the AXI5 interface. Removed content can be<br>accessed by downloading earlier versions of this specification. |  |
| ACE and ACE5<br>interfaces                                               | Removal       | ACE and ACE5 content is removed from the specification. AMBA CHI<br>is recommended for fully coherent agents and is actively supported.                                                                                                                                        |  |
| ACE5-Lite,<br>ACE5-LiteDVM,<br>ACE5-LiteACP, and<br>AXI5-Lite interfaces | Update        | ACE5-Lite, ACE5-LiteDVM, ACE5-LiteACP, and AXI5-Lite interfaces<br>are described through constraints on property values and signal<br>presence.                                                                                                                                |  |
| AXI5 interface                                                           | New feature   | All optional features in this specification are now applicable to AXI5<br>class interfaces. AXI5 is expected to be used for general-purpose<br>interfaces.                                                                                                                     |  |
| Caching shareable lines                                                  | New feature   | Support for storing shareable lines in a system cache.                                                                                                                                                                                                                         |  |
| Cache stashing                                                           | New feature   | There is an additional Basic option for cache stashing to support<br>interfaces which use only a sub-set of the cache stashing protocol.                                                                                                                                       |  |
| Invalidate hint                                                          | New feature   | InvalidateHint transaction, which can be used by an agent when it is<br>finished working with a data set and that data might be allocated in a<br>downstream cache.                                                                                                            |  |
| WriteDeferrable<br>transaction                                           | New feature   | A 64-byte atomic store operation that might not be accepted by the<br>Subordinate.                                                                                                                                                                                             |  |
| Realm Management<br>Extension (RME)                                      | New feature   | Enhanced memory protection.                                                                                                                                                                                                                                                    |  |
| DVM v9.2                                                                 | New feature   | New messages to support the Armv9.2 architecture.                                                                                                                                                                                                                              |  |
| Untranslated transactions                                                | New feature   | Version 3 adds support for mixing translated and untranslated<br>transactions.                                                                                                                                                                                                 |  |
|                                                                          | New feature   | UnstashTranslation transaction, used as a deallocation hint for an<br>address translation cache.                                                                                                                                                                               |  |
| Page-based Hardware<br>Attributes (PBHA)                                 | New feature   | 4-bit descriptors associated with a translation table entry that can be<br>annotated onto a transaction request.                                                                                                                                                               |  |
| Subsystem Identifier                                                     | New feature   | An additional identifier that can be added to transaction requests to<br>indicate from which subsystem they originate.                                                                                                                                                         |  |
| Subordinate busy                                                         | New feature   | Response signal that indicates the level of activity of a Subordinate.                                                                                                                                                                                                         |  |
| Unique ID indicator                                                      | Clarification | Added rules for the Unique ID Indicator and Atomic transactions that<br>include read and write responses.                                                                                                                                                                      |  |
|                                                                          | Correction    | BIDUNQ is not required to follow AWIDUNQ for non-Completion<br>write responses such as Persist and MTE Match.                                                                                                                                                                  |  |
| Memory Tagging<br>Extension (MTE)                                        | Clarification | A WritePtlCMO or WriteFullCMO with AWTAGOP Transfer must be<br>Non-shareable. This is because a WriteUnique with AWTAGOP of<br>Transfer is not permitted.                                                                                                                      |  |
|                                                                          |               |                                                                                                                                                                                                                                                                                |  |

Table B4.1 – *Continued from previous page*

| Feature              | Change                    | Detail                                                                                                                                                                                     |
|----------------------|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|                      | Clarification             | Transactions that carry MTE tags must not cross a cache line boundary.                                                                                                                     |
|                      | Additional<br>requirement | Read transactions with the MTE opcode of Fetch must be Regular.                                                                                                                            |
|                      | Enhancement               | The text describing MTE and Poison is enhanced with additional<br>guidance.                                                                                                                |
| Prefetch transaction | Clarification             | A Prefetch request must not be used to signal that a line can be fetched<br>into a managed or visible cache.                                                                               |
| Wakeup signals       | Clarification             | It is permitted for Wakeup signals to be driven from a glitch-free OR<br>tree if that implementation is safe for asynchronous sampling.                                                    |
| Multi-copy atomicity | Update                    | The requirements for multi-copy atomicity are updated for the Armv8<br>architecture.                                                                                                       |
| Exclusive accesses   | Update                    | New signals are added to the rules for an exclusive sequence.                                                                                                                              |
|                      | Clarification             | The requirements for AxCACHE in an exclusive access have been<br>redefined to be easier to understand.                                                                                     |
| Read response        | Clarification             | For read responses where data is not required to be valid, the Manager<br>might still sample the RDATA value so the Subordinate should not rely<br>on the response to hide sensitive data. |
| Interface parity     | Enhancement               | The description regarding how to handle missing signals in CHK groups<br>is enhanced to cover the case where either the input or output is missing.                                        |
| Signal matrix        | Correction                | The ARDOMAIN and AWDOMAIN entries in the signal matrix are<br>corrected to be dependent on the Shareable_Transactions property and<br>marked as Configurable rather than Mandatory.        |
| Cache stashing       | Correction                | "AWSTASHLPIDEN must be driven to all zeros when<br>AWSTASHLPIDEN is deasserted"<br>is corrected to:<br>"When AWSTASHLPIDEN is LOW, AWSTASHLPID is invalid and must<br>be zero"             |

# <span id="page-308-0"></span>**B4.2 Differences between Issue J and Issue K**

| Feature                                                | Change        | Detail                                                                                                                                                                                                                       |
|--------------------------------------------------------|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Memory Encryption<br>Contexts (MEC)                    | New feature   | The Memory Encryption Contexts (MEC) feature is added to the Realm<br>Management Extension (RME).                                                                                                                            |
| MPAM extension                                         | Enhancement   | A new configuration option is defined for MPAM to support a wider<br>PartID field.                                                                                                                                           |
| MTE extension                                          | Enhancement   | A new configuration option is defined for MTE to support components<br>which transport tags but do not support the Match operation.                                                                                          |
| Fixed_Burst_Disable                                    | Enhancement   | A new property is defined that allows components to not support a Burst<br>type of FIXED.                                                                                                                                    |
| Cache_Line_Size                                        | Enhancement   | A new property is defined to capture the cache line size of an interface.                                                                                                                                                    |
| WriteNoSnoopFull<br>Transaction                        | Enhancement   | A new WriteNoSnoopFull_Transaction property is defined to enable an<br>interface to support WriteNoSnoopFull without having to support all<br>transactions related to caching shareable lines.                               |
| Write channel<br>dependency                            | Clarification | It is clarified that a Subordinate must not block acceptance of data-less<br>write requests due to transactions with leading write data.                                                                                     |
| Length attribute                                       | Clarification | It is clarified that Size x Length defines that maximum number of bytes<br>in a transaction rather than the actual number in all cases.                                                                                      |
| Transaction equations                                  | Correction    | The Data_Bytes variable is corrected to be DATA_WIDTH/8.                                                                                                                                                                     |
| Transaction pseudocode                                 | Clarification | Variable names changed to align with earlier sections.                                                                                                                                                                       |
| Ordering between<br>Device and Normal<br>Non-cacheable | Enhancement   | A property Device_Normal_Independence is added to control whether<br>Device and Normal Non-cacheable requests are required to be ordered<br>against each other.                                                              |
| CACHE_Present                                          | Clarification | It is clarified that the CACHE_Present property determines whether<br>AxCACHE signals are present on an interface.                                                                                                           |
| Cache stash property                                   | Correction    | In the paragraph text and Table A8.19, the Cache_Stash_Transactions<br>property was incorrectly referred to as Stash_Transactions.                                                                                           |
| Max_Transaction_Bytes                                  | Clarification | Clarification on the meaning of the Max_Transaction_Bytes property.                                                                                                                                                          |
| Write data strobes                                     | Clarification | Clarification of the rules for WSTRB.                                                                                                                                                                                        |
| Read data interleaving                                 | Clarification | It is clarified that read data transfers in Atomic transactions can be<br>interleaved.                                                                                                                                       |
| Modifiable transactions                                | Clarification | It is clarified that AxNSE must not be modified, along with AxPROT.                                                                                                                                                          |
| Exclusive accesses                                     | Clarification | It is clarified that AWATOP must not be Match for exclusive writes.                                                                                                                                                          |
| PREFETCHED response                                    | Change        | The recommendation for PREFETCHED response is changed to be:<br>within a cache line, the PREFETCHED response is used for all data<br>transfers or no data transfers. This aligns better with the CHI<br>DataSource response. |
| Caching shareable lines                                | Clarification | It is clarified that clean evictions of Shareable lines must not be written<br>back to memory.                                                                                                                               |
|                                                        | Clarification | In Table A8.8, CacheStash* is replaced with StashOnce*.                                                                                                                                                                      |

Table B4.2 – *Continued from previous page*

| Feature                                     | Change        | Detail                                                                                                                                                                                                            |
|---------------------------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Memory Tagging                              | Clarification | A footnote is added to Table A12.13 to clarify that a WriteNoSnoop<br>with tag Match must not be Exclusive.                                                                                                       |
|                                             | Correction    | In Table A12.12, the value for Tags match is corrected to be 0b11, not<br>0b10.                                                                                                                                   |
| User Loopback signaling                     | Clarification | Clarification of the rules for LOOP_x_WIDTH properties.                                                                                                                                                           |
| MMUFLOW_Present<br>property default         | Correction    | The default value for MMUFLOW_Present is corrected to be False to<br>make it compatible with the default for the Untranslated_Transactions<br>property.                                                           |
| StashTranslation and<br>UnstashTranslation  | Enhancement   | StashTranslation and UnstashTranslation are enhanced to enable the<br>stash or unstash of Granule Protection Table entries.                                                                                       |
| DVM messages                                | Clarification | It is clarified that the AC and CR channels are ordered.                                                                                                                                                          |
|                                             | Correction    | The mapping for the 2nd part of a PICI message was incorrect in Table<br>A15.22. ACADDR[11:4] should be PA[11:4].                                                                                                 |
| Poison                                      | Correction    | The width of WPOISON and RPOISON is corrected to be<br>ceil(DATA_WIDTH/64) rather than DATA_WIDTH/64.                                                                                                             |
| Interface parity for<br>CRTRACE             | Correction    | In Table A16.4, the enable signal for CRTRACECHK was indicated as<br>ACVALID when it should be CRVALID.                                                                                                           |
| Loopback check signal<br>width              | Change        | In Table A16.4, the width of check signals for Loopback signals is<br>changed from 1 to ceil(LOOP_x_WIDTH) to cover cases where the<br>maximum recommendation of 8 for loopback width is exceeded.                |
| ACE5-LiteDVM<br>interface                   | Correction    | The list of signals no longer supported in ACE5-LiteDVM is corrected<br>to ACSNOOP, ACPROT and CRRESP.                                                                                                            |
|                                             | Correction    | DVM_Message_Support must be Receiver for ACE5-LiteDVM<br>interfaces. Therefore, the snoop channels are mandatory rather than<br>optional.                                                                         |
| BROADCAST* signals                          | Correction    | In the signal matrix Table B2.2, the BROADCAST* signal presence was<br>listed as dependent on a Broadcast_Signals property which was not<br>defined. Presence conditions for these signals have now been removed. |
| Parity check signal<br>matrix               | Clarification | A matrix of parity check signals vs interface type is added for clarity.                                                                                                                                          |
| Read Interleaving<br>Disabled and AXI5-Lite | Correction    | Read_Interleaving_Disabled was incorrectly constrained to True for<br>AXI5-Lite interfaces, it should be False.                                                                                                   |

# <span id="page-310-0"></span>**B4.3 Differences between Issue K and Issue L**

| Feature                             | Change        | Detail                                                                                                                                                                                                                      |
|-------------------------------------|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Credited transport                  | New feature   | New credited transport option for all channels.                                                                                                                                                                             |
| Arm Compression<br>Technology       | New feature   | Added support for Arm Compression Technology.                                                                                                                                                                               |
| Protection attributes               | New feature   | New options for signaling physical address space and other protection<br>attributes.                                                                                                                                        |
| RME - Granular Data<br>Isolation    | New feature   | Added support for the GDI extension to RME.                                                                                                                                                                                 |
| Reset                               | Clarification | It is clarified that all signals that are required to be deasserted during<br>reset must wait until at least the rising ACLK edge after ARESETn is<br>HIGH.                                                                 |
| Memory Encryption<br>Contexts (MEC) | Correction    | In Table B2.4, the MECID_WIDTH row has been corrected to say<br>values can be 0,16 (two values) rather than 016 (range).                                                                                                    |
|                                     | Clarification | It is clarified that the constraint for zero MECID only applies to requests<br>where MECID is applicable.                                                                                                                   |
|                                     | Clarification | Removed misleading paragraph regarding mismatched widths of<br>AxMECID.                                                                                                                                                     |
| Untranslated<br>Transactions        | Correction    | The default value for AWMMUVALID and ARMMUVALID is<br>corrected to be 0b1 rather than 0b0.                                                                                                                                  |
|                                     | Correction    | When the AxMMUVALID signals were added to the specification, it<br>was expected that translated and untranslated transactions would use<br>different AXI ID values, but these rules were missing from the<br>specification. |
|                                     | New feature   | New v4 option for Untranslated Transactions supports address<br>translation with GDI and PCIe XT mode.                                                                                                                      |
| Transaction address<br>calculation  | Correction    | The expression to determine the address states for a wrap transaction<br>has been corrected to:<br>Address_N<br>=<br>Aligned_Addr<br>+<br>((N<br>-<br>1)<br>Size)<br>-<br>*<br>(Size<br>Length)<br>*                        |
| Wrapping bursts                     | New feature   | New property Wrap_CLS_Modifiable, used to determine whether<br>WRAP transactions must be cache line sized and Modifiable.                                                                                                   |
| Exclusive accesses                  | Clarification | It is clarified that mismatched attributes do not always cause a failure.                                                                                                                                                   |
| Atomic Transactions                 | Clarification | It is clarified that Atomic transactions must update the entire written<br>location atomically.                                                                                                                             |
|                                     | Clarification | AtomicCompare transactions count as a Regular Transaction, even<br>though the address might not be aligned to Size.                                                                                                         |
|                                     | Clarification | Clarification of ID rules for Atomic transactions.                                                                                                                                                                          |
| Memory Tagging<br>Extension (MTE)   | Clarification | If is clarified that transactions that carry tags must be physically<br>addressed.                                                                                                                                          |

Table B4.3 – *Continued from previous page*

| Feature                          | Change        | Detail                                                                                                                                                                                                                                                                                                                  |
|----------------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Cache line sized<br>transactions | Change        | The following Opcodes can now be Non-modifiable or Modifiable:<br>WriteZero, WriteNoSnoopFull, WritePtlCMO, WriteFullCMO.                                                                                                                                                                                               |
| Caching Shareable lines          | Correction    | In Table A8.8, the entry for a Non-shareable CleanShared CMO has a<br>footnote added that it must hit a Shareable Dirty line if RME_Support is<br>True.                                                                                                                                                                 |
|                                  | Enhancement   | Added a statement regarding Outer Cacheable mode in attached CPUs.                                                                                                                                                                                                                                                      |
| Cache maintenance<br>operations  | Clarification | It is clarified that if the AxDOMAIN signals are missing, a CMO is<br>assumed to be Non-shareable.                                                                                                                                                                                                                      |
|                                  | Correction    | In the example of a Non-shareable WriteFullCMO with CleanInvalid,<br>all in-line and peer caches must be cleaned and invalidated because the<br>CMO is considered to be shareable.                                                                                                                                      |
|                                  | New feature   | New cache maintenance operation, CleanInvalidStorage.                                                                                                                                                                                                                                                                   |
| DVM Messages                     | Correction    | In the ASID field section, the statement "For a 16-bit ASID agent<br>sending a message to an 8-bit VMID agent" has been corrected to "For a<br>16-bit ASID agent sending a message to an 8-bit ASID agent".                                                                                                             |
|                                  | Clarification | The use of the Range field in DVM TLBI messages is clarified.                                                                                                                                                                                                                                                           |
|                                  | Clarification | It is clarified that the range calculation uses the Translation Granule size<br>in bytes, derived from TG.                                                                                                                                                                                                              |
| DVM Complete<br>transaction      | Clarification | When DATA_WIDTH is 1024 and Max_Transaction_Bytes is 64 bytes,<br>it is not possible that a DVM Complete can have ARSIZE equal to data<br>channel width. It is clarified that for a DVM Complete, ARSIZE must<br>be equal to the data channel width or Max_Transaction_Bytes if that is<br>smaller than the data width. |
| DVM connection                   | Clarification | It is clarified that there might be a race between the assertion of<br>SYSCOACK and ACVALID.                                                                                                                                                                                                                            |
| AWCACHE meanings                 | Correction    | The meaning of the Bufferable bit (AWCACHE[0]) is corrected to say<br>that the write response indicates that the data has reached its final<br>destination only if AWCACHE[3:2] are both deasserted.                                                                                                                    |
| ACE-LiteACP cache line<br>size   | Clarification | It is clarified that the constraints on ACE5-LiteACP interfaces include a<br>cache line size of 64 bytes.                                                                                                                                                                                                               |
| Trace signals                    | Clarification | Added recommendation that a component that provides a response to a<br>transaction with the Trace signal deasserted in the request provides a<br>response with the Trace signal deasserted.                                                                                                                             |
| Loopback signals                 | Clarification | It is clarified that Loopback signals can be used on only read or only<br>write channels.                                                                                                                                                                                                                               |
| Cache line sized and<br>Regular  | Clarification | ReadNoSnoop with MTE Fetch is added to the list of Opcodes that must<br>be cache line sized and Regular.                                                                                                                                                                                                                |
| ID constraints                   | Clarification | It is clarified that transactions with unique ID constraints are only<br>constrained against other transactions on the same channels.                                                                                                                                                                                   |

<span id="page-312-0"></span>**Part C Glossary** <span id="page-313-0"></span>Chapter C1 **Glossary**

#### **Aligned**

A data item stored at an address that is divisible by the highest power of 2 that divides into its size in bytes. Aligned halfwords, words and doublewords therefore have addresses that are divisible by 2, 4 and 8 respectively.

An aligned access is one where the address of the access is aligned to the size of each element of the access.

### **At approximately the same time**

Two events occur at approximately the same time if a remote observer might not be able to determine the order in which they occurred.

#### **Barrier**

An operation that forces a defined ordering of other actions.

#### **Big-endian memory**

Means that *the most significant byte* (MSB) of the data is stored in the memory location with the lowest address.

#### **Blocking**

Describes an operation that prevents following actions from continuing until the operation completes.

#### **Branch prediction**

Is where a processor selects a future execution path to fetch along. For example, after a branch instruction, the processor can choose to speculatively fetch either the instruction following the branch or the instruction at the branch target.

#### **Byte**

An 8-bit data item.

### <span id="page-314-1"></span>**Cache**

Any cache, buffer, or other storage structure in a caching Manager that can hold a copy of the data value for a particular address location.

# **Cache hit**

A memory access that can be processed at high speed because the data it addresses is already in the cache.

# <span id="page-314-2"></span>**Cache line**

The basic unit of storage in a cache. Its size in words is always a power of two. A cache line must be aligned to the size of the cache line.

### **Cache miss**

A memory access that cannot be processed at high speed because the data it addresses is not in the cache.

#### **ceil()**

A function that returns the lowest integer value that is equal to or greater than the input to the function.

### **Coherent**

Data accesses from a set of observers to a memory location are coherent accesses to that memory location by the members of the set of observers are consistent with there being a single total order of all writes to that memory location by all members of the set of observers.

### <span id="page-314-0"></span>**Component**

A distinct functional unit that has at least one AMBA interface. Component can be used as a general term for Manager, Subordinate, peripheral, and interconnect components.

#### **Deprecated**

Something that is present in the specification for backwards compatibility. Whenever possible you must avoid using deprecated features. These features might not be present in future versions of the specification.

#### <span id="page-315-1"></span>**Downstream**

An AXI transaction operates between a Manager component and one or more Subordinate components, and can pass through one or more intermediate components. At any intermediate component, for a given transaction, *downstream* means between that component and a destination Subordinate component, and includes the destination Subordinate component.

Downstream and upstream are defined relative to the transaction as a whole, not relative to individual data flows within the transaction.

### **Downstream cache**

A downstream cache is defined from the perspective of an initiating Manager. A downstream cache for a Manager is one that it accesses using the fundamental AXI transaction channels. An initiating Manager can allocate cache lines into a downstream cache.

### **Endianness**

An aspect of the system memory mapping.

### **Full coherency**

A fully coherent Manager can share data with other Managers and allocate that data in its local caches; it can snoop and be snooped.

### **I/O coherency**

An I/O coherent Manager can share data with other Managers but cannot allocate that data in its local caches; it can snoop but not be snooped.

### **IMPLEMENTATION DEFINED**

Means that the behavior is not defined by this specification, but must be defined and documented by individual implementations.

#### <span id="page-315-2"></span>**in a timely manner**

The protocol cannot define an absolute time within which something must occur. However, in a sufficiently idle system, it will make progress and complete without requiring any explicit action.

#### **Initiating Manager**

A Manager that issues a transaction that starts a sequence of events. When describing a sequence of transactions, the term initiating Manager distinguishes the Manager that triggers the sequence of events from any snooped Manager that is accessed as a result of the action of the initiating Manager.

Initiating Manager is a temporal definition, meaning it applies at particular points in time, and typically is used when describing sequences of events. A Manager that is an initiating Manager for one sequence of events can be a snooped Manager for another sequence of events.

### <span id="page-315-0"></span>**Interconnect component**

A component with more than one AMBA interface that connects one or more Manager components to one or more Subordinate components.

An interconnect component can be used to group together either:

- A set of Managers so that they appear as a single Manager interface.
- A set of Subordinates so that they appear as a single Subordinate interface.

### **Little-endian memory**

Means that the *least significant byte* (LSB) of the data is stored in the memory location with the lowest address.

### **Load**

The action of a Manager component reading the value held at a particular address location. For a processor, a load occurs as the result of executing a particular instruction. Whether the load results in the Manager issuing a read transaction depends on whether the accessed cache line is held in the local cache.

#### **Local cache**

A local cache is defined from the perspective of an initiating Manager. A local cache is one that is internal to the Manager. Any access to the local cache is performed within the Manager.

### **Main memory**

The memory that holds the data value of an address location when no cached copies of that location exist. For any location, main memory can be out of date with respect to the cached copies of the location, but main memory is updated with the most recent data value when no cached copies exist.

Main memory can be referred to as memory when the context makes the intended meaning clear.

#### **Manager**

An agent that initiates transactions.

#### <span id="page-316-0"></span>**Manager component**

A component that initiates transactions.

It is possible that a single component can act as both a Manager component and as a Subordinate component. For example, a *Direct Memory Access* (DMA) component can be a Manager component when it is initiating transactions to move data, and a Subordinate component when it is being programmed.

#### **Memory Encryption Contexts (MEC)**

Memory Encryption Contexts are configurations of encryption that are associated with areas of memory, assigned by the MMU.

MEC is an extension to the *Arm Realm Management Extension (RME)*. The RME system architecture requires that the Realm, Secure, and Root Physical Address Spaces (PAS) are encrypted. The encryption key or encryption context, used with each of these PASs is global within that PAS. For example, for the Realm PAS, all Realm memory uses the same encryption context. With MEC this concept is broadened, and for the Realm PAS specifically, each Realm is allowed to have a unique encryption context. This provides additional defense in depth to the isolation already provided in RME. MECIDs are identifying tags that are associated with different Memory Encryption Contexts.

#### **Memory Management Unit (MMU)**

Provides detailed control of the part of a memory system that provides address translation. Most of the control is provided using translation tables that are held in memory, and define the attributes of different regions of the physical memory map.

### <span id="page-316-1"></span>**Memory Subordinate component**

A Memory Subordinate component, or *Memory Subordinate*, is a Subordinate component with the following properties:

- A read of a byte from a Memory Subordinate returns the last value written to that byte location.
- A write to a byte location in a Memory Subordinate updates the value at that location to a new value that is obtained by subsequent reads.
- Reading a location multiple times has no side-effects on any other byte location.
- Reading or writing one byte location has no side-effects on any other byte location.

### **Observer**

A processor or other Manager component, such as a peripheral device, that can generate reads from or writes to memory.

### **Page-based Hardware Attributes (PBHA)**

Page Based Hardware Attributes (PBHA) is an optional, implementation defined feature. It allows software to set up to 4 bits in the translation tables, which are then propagated though the memory system with transactions, and can be used in the system to control system components. The meaning of the bits is specific to the system design.

#### **Peer cache**

A peer cache is defined from the perspective of an initiating Manager. A peer cache for that Manager is one that is accessed using snoop channels. An initiating Manager cannot allocate cache lines into a peer cache.

#### <span id="page-317-0"></span>**Peripheral Subordinate component**

A Peripheral Subordinate component is also described as a *Peripheral Subordinate*. A Peripheral Subordinate typically has an IMPLEMENTATION DEFINED method of access that is described in the data sheet for the component. Any access that is not defined as permitted might cause the Peripheral Subordinate to fail, but must complete in a protocol-correct manner to prevent system deadlock. The protocol does not require continued correct operation of the peripheral.

In the context of the descriptions in this specification, Peripheral Subordinate is synonymous with *peripheral*, *peripheral component*, *peripheral device*, and *device*.

#### **PoS**

Point of Serialization. The point through which all transactions to a given address must pass and the order in which the transactions are processed is determined.

#### **Prefetching**

Prefetching refers to speculatively fetching instructions or data from the memory system. In particular, instruction prefetching is the process of fetching instructions from memory before the instructions that precede them, in simple sequential execution of the program, have finished executing. Prefetching an instruction does not mean that the instruction has to be executed.

In this specification, references to instruction or data fetching apply also to prefetching, unless the context explicitly indicates otherwise.

#### **RAZ/WI, Read-As-Zero, Writes Ignored**

Hardware must implement the field as Read-as-Zero, and must ignore writes to the field. Software can rely on the field reading as all 0s, and on writes being ignored. This description can apply to a single bit that reads as 0, or to a field that reads as all 0s.

#### **Realm Management Extensions (RME)**

The Realm Management Extension (RME) is an extension to the Armv9 A-profile architecture. RME is one component of the Arm Confidential Compute Architecture (Arm CCA). Together with the other components of the Arm CCA, RME enables support for dynamic, attestable and trusted execution environments (Realms) to be run on an Arm PE. RME adds two additional Security states (Root and Realm) and two physical address spaces (Root and Realm), and provides hardware-based isolation that allows execution contexts to run in different Security states and share resources in the system.

### **Snoop filter**

A precise snoop filter that is able to track precisely the cache lines that might be allocated within a Manager.

#### **Snooped cache**

A hardware-coherent cache on a snooped Manager. That is, it is a hardware-coherent cache that receives snoop transactions.

The term snooped cache is used in preference to the term snooped Manager when the sequence of events being described only involves the cache and does not involve any actions or events on the associated Manager.

### **Snooped Manager**

A caching Manager that receives snoop transactions.

Snooped Manager is a temporal definition, meaning it applies at particular points in time, and typically is used when describing sequences of events. A Manager that is a snooped Manager for one sequence of events can be an initiating Manager for another sequence of events.

#### **Speculative read**

A transaction that a Manager issues when it might not need the transaction to be performed because it already has a copy of the accessed cache line in its local cache. Typically, a Manager issues a speculative read in parallel with a local cache lookup. This gives lower latency than looking in the local cache first, and then issuing a read transaction only if the required cache line is not found in the local cache.

#### **Store**

The action of a Manager component changing the value held at a particular address location. For a processor, a store occurs as the result of executing a particular instruction. Whether the store results in the Manager issuing a read or write transaction depends on whether the accessed cache line is held in the local cache, and if it is in the local cache, the state it is in.

### **Subordinate**

An agent that receives and responds to requests.

#### <span id="page-318-0"></span>**Subordinate component**

A component that receives transactions and responds to them.

It is possible that a single component can act as both a Subordinate component and as a Manager component. For example, a *Direct Memory Access* (DMA) component can be a Subordinate component when it is being programmed and a Manager component when it is initiating transactions to move data.

#### **System Memory Management Unit (SMMU)**

A system-level MMU. That is, a system component that provides address translation from one address space to another. An SMMU provides one or more of:

- *virtual address* (VA) to *physical address* (PA) translation.
- VA to *intermediate physical address* (IPA) translation.
- IPA to PA translation.

When using the Realm Management Extension (RME), an SMMU can also perform the Granule Protection Check.

### **Transaction**

An AXI Manager initiates an AXI transaction to communicate with an AXI Subordinate. Typically, the transaction requires information to be exchanged between the Manager and Subordinate on multiple channels. The complete set of required information exchanges form the AXI transaction.

#### **Translation Lookaside Buffer (TLB)**

A memory structure containing the results of translation table walks. TLBs help to reduce the average cost of a memory access.

# **Translation table**

A table held in memory that defines the properties of memory areas of various sizes from 1KB.

#### **Translation table walk**

The process of doing a full translation table lookup.

#### **Unaligned**

An unaligned access is an access where the address of the access is not aligned to the size of an element of the access.

#### **Unaligned memory accesses**

Are memory accesses that are not, or might not be, appropriately halfword-aligned, word-aligned, or doubleword-aligned.

#### **UNPREDICTABLE**

In the AMBA AXI Architecture means that the behavior cannot be relied upon.

UNPREDICTABLE behavior must not be documented or promoted as having a defined effect.

### <span id="page-319-0"></span>**Upstream**

An AXI transaction operates between a Manager component and one or more Subordinate components, and can pass through one or more intermediate components. At any intermediate component, for a given transaction, *upstream* means between that component and the originating Manager component, and includes the originating Manager component.

Downstream and upstream are defined relative to the transaction as a whole, not relative to individual data flows within the transaction.

#### **Write-Back cache**

A cache in which when a cache hit occurs on a store access, the data is only written to the cache. Data in the cache can therefore be more up-to-date than data in main memory. Any such data is written back to main memory when the cache line is cleaned or re-allocated. Another common term for a Write-Back cache is a *copy-back cache*.

#### **Write-Through cache**

A cache in which when a cache hit occurs on a store access, the data is written both to the cache and to main memory. This is normally done via a write buffer to avoid slowing down the processor.