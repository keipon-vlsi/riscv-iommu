# <span id="page-185-0"></span>Chapter A12

# **System monitoring, debug, and user extensions**

This chapter describes the AXI features for system monitoring and debug. It also describes how to add user-defined extensions to each channel.

It contains the following sections:

- [A12.1](#page-186-0) *[Memory System Resource Partitioning and Monitoring \(MPAM\)](#page-186-0)*
- [A12.2](#page-189-0) *[Memory Tagging Extension \(MTE\)](#page-189-0)*
- [A12.3](#page-198-0) *[Trace signals](#page-198-0)*
- [A12.4](#page-199-0) *[User Loopback signaling](#page-199-0)*
- <span id="page-185-1"></span>• [A12.5](#page-201-0) *[User defined signaling](#page-201-0)*

# <span id="page-186-0"></span>**A12.1 Memory System Resource Partitioning and Monitoring (MPAM)**

Memory System Resource Partitioning and Monitoring (MPAM) is a technology for partitioning and monitoring memory system resources for physical and virtual machines. The full MPAM architecture is described in the Armv8.4 extensions [\[6\]](#page-16-6).

Each MPAM-enabled Manager adds MPAM information to its requests. The MPAM information is propagated through the system to memory components where it can be used to influence resource allocation decisions. Monitoring memory usage based on MPAM information can also enable the tuning of performance and accurate costing between machines.

### <span id="page-186-2"></span><span id="page-186-1"></span>**A12.1.1 MPAM signaling**

The MPAM\_Support property as shown in Table [A12.1](#page-186-2) is used to indicate whether an interface supports MPAM.

**Table A12.1: MPAM\_Support property**

| MPAM_Support | Default | Description                                                                                                                          |
|--------------|---------|--------------------------------------------------------------------------------------------------------------------------------------|
| MPAM_12_1    |         | The interface is enabled for MPAM and includes the<br>MPAM signals on AW and AR channels. The width of<br>PARTID is 12 and PMG is 1. |
| MPAM_9_1     |         | The interface is enabled for MPAM and includes the<br>MPAM signals on AW and AR channels. The width of<br>PARTID is 9 and PMG is 1.  |
| False        | Y       | MPAM is not supported, the interface is not MPAM<br>enabled and no MPAM signals are present on the<br>interface.                     |

<span id="page-186-3"></span>The signals used to support MPAM are shown in Table [A12.2.](#page-186-3)

**Table A12.2: AxMPAM signals**

<span id="page-186-5"></span><span id="page-186-4"></span>

| Name              | Width      | Default | Description                                                                             |
|-------------------|------------|---------|-----------------------------------------------------------------------------------------|
| AWMPAM,<br>ARMPAM | MPAM_WIDTH | -       | Memory System Resource Partitioning and<br>Monitoring (MPAM) information for a request. |

The value of MPAM\_WIDTH is determined by the MPAM\_Support and RME\_Support properties.

When MPAM\_Support is False, MPAM\_WIDTH must be zero.

### <span id="page-187-0"></span>**A12.1.2 MPAM fields**

MPAM fields are encoded within the AxMPAM signals depending on the MPAM\_Support and RME\_Support properties.

<span id="page-187-1"></span>When MPAM\_Support is MPAM\_9\_1 and RME\_Support is False, MPAM\_WIDTH must be 11 and the mapping is shown in Table [A12.3.](#page-187-1)

**Table A12.3: MPAM\_9\_1 fields when RME\_Support is False**

| Field   | Description               | Width | Mapping     |
|---------|---------------------------|-------|-------------|
| MPAM_NS | Security indicator        | 1     | AxMPAM[0]   |
| PARTID  | Partition identifier      | 9     | AxMPAM[9:1] |
| PMG     | Performance monitor group | 1     | AxMPAM[10]  |

<span id="page-187-2"></span>When MPAM\_Support is MPAM\_9\_1 and RME\_Support is True, MPAM\_WIDTH must be 12 and the mapping is shown in Table [A12.4.](#page-187-2)

**Table A12.4: MPAM\_9\_1 fields when RME\_Support is True**

| Field   | Description                      | Width | Mapping      |
|---------|----------------------------------|-------|--------------|
| MPAM_SP | Physical address space indicator | 2     | AxMPAM[1:0]  |
| PARTID  | Partition identifier             | 9     | AxMPAM[10:2] |
| PMG     | Performance monitor group        | 1     | AxMPAM[11]   |

<span id="page-187-3"></span>When MPAM\_Support is MPAM\_12\_1 and RME\_Support is False, MPAM\_WIDTH must be 14 and the mapping is shown in Table [A12.5.](#page-187-3)

**Table A12.5: MPAM\_12\_1 fields when RME\_Support is False**

| Field   | Description               | Width | Mapping      |
|---------|---------------------------|-------|--------------|
| MPAM_NS | Security indicator        | 1     | AxMPAM[0]    |
| PARTID  | Partition identifier      | 12    | AxMPAM[12:1] |
| PMG     | Performance monitor group | 1     | AxMPAM[13]   |

<span id="page-187-4"></span>When MPAM\_Support is MPAM\_12\_1 and RME\_Support is True, MPAM\_WIDTH must be 15 and the mapping is shown in Table [A12.6.](#page-187-4)

**Table A12.6: MPAM\_12\_1 fields when RME\_Support is True**

| Field   | Description                      | Width | Mapping      |
|---------|----------------------------------|-------|--------------|
| MPAM_SP | Physical address space indicator | 2     | AxMPAM[1:0]  |
| PARTID  | Partition identifier             | 12    | AxMPAM[13:2] |
| PMG     | Performance monitor group        | 1     | AxMPAM[14]   |

### <span id="page-188-0"></span>**A12.1.3 MPAM component interactions**

Implementation of MPAM technology has impacts on Manager, Interconnect, and Subordinate components.

If a Manager component is included in an MPAM-enabled system, but does not support MPAM signaling, then the system must add the MPAM information. The default behavior is IMPLEMENTATION DEFINED; one possible approach is to copy the physical address space of the request onto the least significant MPAM bits and zero-extend the remaining higher bits.

### *Manager components*

Manager components that are MPAM-enabled must drive MPAM signals when the corresponding AxVALID is asserted. Values used are IMPLEMENTATION DEFINED for all transaction types. It is expected, but not required, that a Manager uses the same sets of values for read and write requests. A Manager might not use all the PARTID or PMG values that can be signaled on the interface.

#### *Interconnect components*

MPAM identifiers have global scope. There is no requirement for interconnect components to make MPAM identifiers unique. When an interconnect Manager interface is connected to an MPAM-enabled Subordinate, it can use propagated values or IMPLEMENTATION DEFINED values.

#### *Subordinate components*

<span id="page-188-1"></span>A Subordinate component that is MPAM-enabled can use the MPAM information for memory partitioning and monitoring. MPAM signals are sampled when the corresponding AxVALID is asserted.

# <span id="page-189-0"></span>**A12.2 Memory Tagging Extension (MTE)**

The Memory Tagging Extension (MTE) provides a mechanism that can be used to detect memory safety violations.

When a region of memory is allocated for a particular use, it is given an Allocation Tag value. When the memory is subsequently accessed, a Physical Tag value is provided that corresponds to the physical address of the access. If the Physical Tag does not match with the Allocation Tag, a warning is generated.

Allocation Tags are stored in the memory system and can be cached in the same way as data. Each tag is 4 bits and is associated with a 16-byte aligned address location.

The following operations are supported:

- Updating the Allocation Tag value using a write transaction, with or without updating the associated data value.
- Reading of data with associated Allocation tag. The Requestor can then perform the check of Physical Tag against the Allocation Tag.
- Writing to memory with a Physical Tag to be compared with the Allocation Tag. The result is indicated in the transaction response.

When memory tagging is supported in a system, it is not required that every transaction uses memory tagging. It is also not required that every component in the system supports memory tagging.

The Memory Tagging Extension is supported on Arm A-profile architecture v8.5 onwards and is described in the *Arm® Architecture Reference Manual for A-profile architecture* [\[3\]](#page-16-3).

### <span id="page-189-1"></span>**A12.2.1 MTE support**

The MTE\_Support property of an interface is used to indicate the level of support for MTE. There are different levels of support that can be used, depending on the use-case.

**Table A12.7: MTE\_Support property**

| MTE_Support | Default | Description                                                                                                                                                                                                                                                                                    |
|-------------|---------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Standard    |         | Memory tagging is fully supported on the interface, all MTE signals<br>are present.                                                                                                                                                                                                            |
| Simplified  |         | All memory tagging operations are supported except MTE Match.<br>Partial tag writes are not permitted, so when AWTAGOP is Update,<br>all WTAGUPDATE bits that correspond to the tags inside the<br>transaction container must be asserted. BTAGMATCH is not present.<br>BCOMP is not required. |
| Basic       |         | Memory tagging is supported on the interface at a basic level. A<br>limited set of tag operations are permitted. BTAGMATCH is not<br>present. BCOMP is not required.                                                                                                                           |
| False       | Y       | Memory tagging is not supported on the interface and no MTE<br>signals are present.                                                                                                                                                                                                            |

MTE\_Support must be False when:

- DATA\_WIDTH is 32 or smaller.
- Untranslated\_Transactions is True, v1 or v2.

The compatibility between Manager and Subordinate interfaces, according to the values of the MTE\_Support property is shown in Table [A12.8.](#page-190-2)

**Table A12.8: MTE\_Support**

<span id="page-190-2"></span>

|                        | Subordinate: False                                                                                                      | Subordinate:<br>Basic | Subordinate:<br>Simplified | Subordinate:<br>Standard |  |
|------------------------|-------------------------------------------------------------------------------------------------------------------------|-----------------------|----------------------------|--------------------------|--|
| Manager:<br>False      | Compatible.                                                                                                             | Compatible.           | Compatible.                | Compatible.              |  |
| Manager:<br>Basic      | Protocol compliant.<br>The Subordinate ignores<br>AxTAGOP, so write tags are<br>lost and read tag values are<br>static. | Compatible.           | Compatible.                | Compatible.              |  |
| Manager:<br>Simplified | Protocol compliant.<br>The Subordinate ignores<br>AxTAGOP, so write tags are<br>lost and read tag values are<br>static. | Not compatible.       | Compatible.                | Compatible.              |  |
| Manager:<br>Standard   | Not compatible.                                                                                                         | Not compatible.       | Not compatible.            | Compatible.              |  |

### <span id="page-190-0"></span>**A12.2.2 MTE signaling**

The signals required to support MTE are shown in Table [A12.9.](#page-190-3)

**Table A12.9: MTE signals**

<span id="page-190-9"></span><span id="page-190-8"></span><span id="page-190-5"></span><span id="page-190-4"></span><span id="page-190-3"></span>

| Name          | Width                  | Default           | Description                                                                                                                                                                                                                   |
|---------------|------------------------|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| AWTAGOP       | 2                      | 0b00<br>(Invalid) | Indicates if MTE tags are associated with a write<br>transaction.                                                                                                                                                             |
| ARTAGOP       | 2                      | 0b00<br>(Invalid) | Indicates if MTE tags are requested with a read<br>transaction.                                                                                                                                                               |
| WTAG,<br>RTAG | ceil(DATA_WIDTH/128)*4 | -                 | Memory tag associated with data. There is a 4-bit tag per<br>128-bits of data, with a minimum of 4-bits. It has the<br>same validity rules as the associated data. It is<br>recommended that invalid tags are driven to zero. |
| WTAGUPDATE    | ceil(DATA_WIDTH/128)   | -                 | Indicates which tags must be written to memory when<br>AWTAGOP is Update. There is 1 bit per 4 bits of tag.                                                                                                                   |
| BTAGMATCH     | 2                      | -                 | Indicates the result of a tag comparison on a write<br>transaction.                                                                                                                                                           |
| BCOMP         | 1                      | 0b1               | Asserted HIGH to indicate a Completion response.                                                                                                                                                                              |

## <span id="page-190-7"></span><span id="page-190-6"></span><span id="page-190-1"></span>**A12.2.3 Caching tags**

Allocation Tags that are cached must be kept hardware-coherent. The coherence mechanism is the same as for data. Applicable tag cache states are: Invalid, Clean, and Dirty. A line that is either Clean or Dirty is Valid.

Constraints on the combination of data cache state and tag cache state are:

- Tags can be Valid only when data is Valid.
- Tags can be Invalid when data is Valid.
- When a cached line is evicted and tags are Dirty, then it is permitted to treat clean data that is evicted as dirty.
- When Dirty tags are evicted from a cache, they must be either written back to memory or passed dirty to another cache.
- When Clean tags are evicted from a cache, they can be sent to other caches or dropped silently.
- A CMO which hits a line with Valid tags applies to the data and the tag.
- When a MakeInvalid or ROMI transaction hits a line with dirty tags, the tags must be written back to memory.

# <span id="page-191-1"></span><span id="page-191-0"></span>**A12.2.4 Transporting tags**

Tag values are transported using the WTAG signal when AWTAGOP is not Invalid.

Tag values are transported using the RTAG signal when ARTAGOP is not Invalid.

When transporting tags, the following rules apply in addition to other constraints based on the transaction type:

- The transaction must be cache line sized or smaller and not cross a cache line boundary.
- AxADDR must be a physical address, therefore AxMMUVALID must be LOW if present.
- AxBURST must be INCR or WRAP, not FIXED.
- The transaction must be to Normal Write-Back memory, which means:
  - The CACHE\_Present property must be True.
  - AxCACHE[3:2] is not 0b00.
  - AxCACHE[1:0] is 0b11.
- The ID value must be unique-in-flight, which means:
  - A read with tag Transfer or Fetch can only be issued if there are no outstanding read transactions using the same ARID value.
  - A Manager must not issue a request on the read channel with the same ARID as an outstanding read with tag Transfer or Fetch.
  - If present, ARIDUNQ must be asserted for a read with tag Transfer or Fetch.
  - A write with tag Transfer, Update or Match can only be issued if there are no outstanding write transactions using the same AWID value.
  - A Manager must not issue a request on the write channel with the same AWID as an outstanding write with tag Transfer, Update, or Match.
  - If present, AWIDUNQ must be asserted for a write with tag operations Transfer, Update, or Match.
- The memory tag is transported on RTAG or WTAG, where TAG[4n-1:4(n-1)] corresponds to DATA[128n-1:128(n-1)].
- For data widths wider than 128 bits, the tag signal carries multiple tags. The tags are driven appropriate to the data being transported, with the least significant tag bits used to transport the tag for the least significant 128 bits of data.
- For read transactions that use read data chunking, only tags which correspond to valid chunk strobes are required to be valid.

• For write transactions where multiple transfers address the same tag, WTAG and WTAGUPDATE values must be consistent for each 4-bit tag that is accessed by the transaction.

### <span id="page-192-3"></span><span id="page-192-1"></span><span id="page-192-0"></span>**A12.2.5 Reads with tags**

A read can request that Allocation Tags are returned along with data, which is determined by the value of ARTAGOP, as shown in Table [A12.10.](#page-192-1)

**Table A12.10: ARTAGOP encodings**

| ARTAGOP | Operation | Meaning                                                                                                                                                                                                                                        |
|---------|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0b00    | Invalid   | Tags are not required to be returned with the data. In the response to this<br>request, RTAG is invalid and must be zero.                                                                                                                      |
| 0b01    | Transfer  | Each transfer of read data must have a valid tag value. Tags must be sent for<br>every 16-byte granule that is accessed, even if the address is not aligned to 16<br>bytes.                                                                    |
| 0b10    | RESERVED  | -                                                                                                                                                                                                                                              |
| 0b11    | Fetch     | Only tags are required to be fetched. Data is not required to be valid and must<br>not be used by the Manager. Transactions using Fetch must be cache line sized<br>and Regular. Tags must be sent for every 16-byte granule that is accessed. |

There are limitations on which read channel Opcodes can be used with MTE tag transfer. Table [A12.11](#page-192-2) shows the combinations of Opcode and TagOp that are legal for each configuration of MTE\_Support.

A TagOp encoding of Invalid is legal for all Opcodes.

An asterisk (\*) indicates all variants of the Opcode.

**Table A12.11: Legal tag operations for read transactions**

<span id="page-192-2"></span>

| Opcode               | MTE_Support = Basic |       |          | MTE_Support = Simplified | MTE_Support = Standard |       |  |
|----------------------|---------------------|-------|----------|--------------------------|------------------------|-------|--|
|                      | Transfer            | Fetch | Transfer | Fetch                    | Transfer               | Fetch |  |
| ReadNoSnoop          | Y                   | -     | Y        | Y                        | Y                      | Y     |  |
| ReadOnce             | Y                   | -     | Y        | -                        | Y                      | -     |  |
| ReadShared           | Y                   | -     | Y        | -                        | Y                      | -     |  |
| ReadClean            | Y                   | -     | Y        | -                        | Y                      | -     |  |
| ReadOnceCleanInvalid | -                   | -     | -        | -                        | -                      | -     |  |
| ReadOnceMakeInvalid  | -                   | -     | -        | -                        | -                      | -     |  |
| CleanInvalid*        | -                   | -     | -        | -                        | -                      | -     |  |
| CleanShared*         | -                   | -     | -        | -                        | -                      | -     |  |
| MakeInvalid          | -                   | -     | -        | -                        | -                      | -     |  |
| DVM Complete         | -                   | -     | -        | -                        | -                      | -     |  |

### <span id="page-193-0"></span>**A12.2.6 Writes with tags**

A write can request that Allocation Tags are written along with data or that the write includes a Physical Tag which is compared with the Allocation Tag already stored in memory. The signal AWTAGOP indicates the tag operation to be performed.

**Table A12.12: AWTAGOP encodings**

<span id="page-193-1"></span>

| AWTAGOP | Operation | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
|---------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0b00    | Invalid   | The tags are not valid; no tag updating or checking is required.<br>WTAGUPDATE must be deasserted.<br>WTAG must be zero.                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 0b01    | Transfer  | The tags are Clean. Tag check does not need to be performed. The completer of<br>the write can cache the tags if it is allocating the data.<br>WTAGUPDATE must be deasserted.<br>WTAG bits must be valid for every byte in the transaction container.                                                                                                                                                                                                                                                                                                    |
| 0b10    | Update    | Tag values have been updated and are dirty; the tags in memory must be<br>updated, according to WTAGUPDATE.<br>WTAGUPDATE can have any number of bits asserted, including none.<br>Tags that are only partially addressed in the transaction must have<br>WTAGUPDATE deasserted.<br>Write*Full* Opcodes must have all associated WTAGUPDATE bits asserted.<br>WTAG must be valid for every associated WTAGUPDATE bit that is asserted.                                                                                                                   |
| 0b11    | Match     | The tags in the write must be checked against the Allocation Tag values that are<br>obtained from memory. The Match operation must be performed for all tags<br>where any corresponding write data strobes are asserted. It is required to update<br>memory with the data, even if the match fails.<br>WTAGUPDATE must be deasserted.<br>WTAG bits must be valid for byte lanes that are enabled by WSTRB.<br>For interfaces with more than 4 bits of tags, the Match operation is performed<br>only on those tags that correspond to active byte lanes. |

For a write with tag Update, WTAGUPDATE indicates which tags must be written. It has the following rules:

- WTAGUPDATE[n] corresponds to WTAG[4n+3:4n].
- If a bit is asserted, then the corresponding tags must be written to memory.
- If a bit is deasserted, then the corresponding tags are invalid.
- WTAGUPDATE bits outside of the transaction container must be deasserted.
- For operations other than Update, WTAGUPDATE must be deasserted.
- A tag-only write can be achieved by asserting WTAGUPDATE and deasserting WSTRB.

There are limitations on which write channel Opcodes can be used with MTE tag transfer. Table [A12.13](#page-194-0) shows the combinations of Opcode and TagOp that are legal for each configuration of MTE\_Support.

A TagOp encoding of Invalid is legal for all Opcodes.

An asterisk (\*) indicates all variants of the Opcode.

**Table A12.13: Legal tag operations for write transactions**

<span id="page-194-0"></span>

|                    | MTE_Support = Basic |        |       | MTE_Support = Simplified |         |       | MTE_Support = Standard |        |       |
|--------------------|---------------------|--------|-------|--------------------------|---------|-------|------------------------|--------|-------|
| Opcode             | Transfer            | Update | Match | Transfer                 | Update1 | Match | Transfer               | Update | Match |
| WriteNoSnoop       | -                   | Y      | -     | -                        | Y       | -     | Y                      | Y      | Y2    |
| WriteUnique*       | -                   | Y      | -     | -                        | Y       | -     | -                      | Y      | -     |
| WriteNoSnoopFull   | -                   | Y      | -     | Y                        | Y       | -     | Y                      | Y      | Y     |
| WriteBackFull      | -                   | Y      | -     | Y                        | Y       | -     | Y                      | Y      | -     |
| WriteEvictFull     | Y                   | -      | -     | Y                        | -       | -     | Y                      | -      | -     |
| Atomic             | -                   | -      | -     | -                        | -       | -     | -                      | -      | Y     |
| CMO                | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |
| Write*CMO          | -                   | -      | -     | 3<br>Y                   | Y       | -     | 3<br>Y                 | Y      | -     |
| WriteZero          | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |
| WriteUnique*Stash  | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |
| StashOnce*         | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |
| StashTranslation   | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |
| Prefetch           | -                   | -      | -     | Y                        | -       | -     | Y                      | -      | -     |
| WriteDeferrable    | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |
| UnstashTranslation | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |
| InvalidateHint     | -                   | -      | -     | -                        | -       | -     | -                      | -      | -     |

<sup>1</sup> Partial tag updates are not supported.

<sup>2</sup> Not Exclusive write.

<sup>3</sup> Domain must be Non-shareable.

Write transactions with a tag Match operation (AWTAGOP is 0b11) have two parts to the response:

- A Completion response, which indicates that the write is observable.
- A Match response, which indicates whether the tag comparison passes or fails.

A two-part response enables components with separate data and tag storage parts to respond independently.

Response transfers can be sent in any order. The two parts can be optionally combined into a single response transfer.

<span id="page-195-0"></span>The responses are signaled using BCOMP and BTAGMATCH. Table [A12.14](#page-195-0) shows the encodings for BTAGMATCH.

**Table A12.14: BTAGMATCH encodings**

| BTAGMATCH | Operation | Meaning                                         |  |
|-----------|-----------|-------------------------------------------------|--|
| 0b00      | None      | No match result because not a match transaction |  |
| 0b01      | Separate  | Match result is in a separate response transfer |  |
| 0b10      | Fail      | Tags do not match                               |  |
| 0b11      | Pass      | Tags match                                      |  |

### *Completion response*

The Completion response indicates that the write is observable. It has the following rules:

- BCOMP must be asserted.
- BTAGMATCH must be 0b01 (Match result in separate response).
- BID must have the same value as AWID.
- If Loopback signaling is supported, BLOOP must have the same value as AWLOOP.
- BRESP can take any value that is legal for the request Opcode.
- The Completion response must follow normal response ordering rules.
- The ID value can be reused when this response is received.

#### *Match response*

The Match response indicates the result of the tag comparison on a write.

- If the tags match for every transfer of the entire transaction, then the response is Pass.
- If any tags associated with active write data byte lanes do not match those already stored, then the response is Fail.

A Match response has the following rules:

- BCOMP must be deasserted.
- BTAGMATCH must be 0b11 (Pass) or 0b10 (Fail).
- BID must have the same value as AWID.
- BIDUNQ can take any value, it is not required to have the same value as AWIDUNQ.
- BLOOP can take any value, it is not required to have the same value as AWLOOP.
- BRESP can take any value that is legal for the request Opcode.
- The Match response has no ordering requirements, it can overtake or be overtaken by any other response transfers.

#### *Combined response*

A Subordinate can optionally combine the two responses into a single transfer. The following rules apply:

- BCOMP must be asserted.
- BTAGMATCH must be 0b11 (Pass) or 0b10 (Fail).
- BID must have the same value as AWID.
- If Loopback signaling is supported, BLOOP must have the same value as AWLOOP.
- BRESP can take any value that is legal for the request Opcode.
- The combined response must follow normal response ordering rules.
- The ID value can be reused when this response is received.

<span id="page-196-2"></span>Possible responses to a Match operation are shown in Table [A12.15.](#page-196-2)

**Table A12.15: Possible responses to a Match operation**

| BTAGMATCH | BCOMP | Description                                               |  |
|-----------|-------|-----------------------------------------------------------|--|
| 0b00      | 0b0   | Not legal for a response to a request with tag Match.     |  |
| 0b00      | 0b1   | Not legal for a response to a request with tag Match.     |  |
| 0b01      | 0b0   | Not legal.                                                |  |
| 0b01      | 0b1   | Completion response, part of a two-part response.         |  |
| 0b10      | 0b0   | Match Fail, part of a two-part response.                  |  |
| 0b10      | 0b1   | Match Fail or MTE Match not supported, one-part response. |  |
| 0b11      | 0b0   | Match Pass, part of a two-part response.                  |  |
| 0b11      | 0b1   | Match Pass, one-part response.                            |  |

### <span id="page-196-0"></span>**A12.2.7 Memory tagging interoperability**

When an MTE operation is performed to a memory location that does not support memory tagging, the resultant data must be identical to that produced by a non-MTE operation to the same location.

- For a read with Transfer or Fetch, RTAG is recommended to be zero.
- For a write with Transfer or Update, the data must be written normally. The tag is discarded.
- For a write with Match, the data must be written normally and a single Combined response is given. BTAGMATCH must be 0b10 (Fail).

A Subordinate is expected to give an OKAY response to an MTE operation unless it would have given a different response to an equivalent non-MTE operation.

### <span id="page-196-1"></span>**A12.2.8 MTE and Atomic transactions**

An Atomic transaction to a location that is protected with memory tagging can use a write Match operation. Atomic transactions cannot be used with Transfer or Update operations.

AtomicCompare transactions with Match can be 16 bytes or 32 bytes. If the transaction is 32 bytes, the same tag value must be used for tag bits associated with the compare and swap bytes.

Read data that is returned within an Atomic Transaction does not have valid RTAG values, so RTAG is recommended to be zero.

### <span id="page-197-0"></span>**A12.2.9 MTE and Prefetch transactions**

A Prefetch transaction with AWTAGOP of Transfer indicates that the data should be prefetched with tags if possible. A Prefetch transaction has no write data, so no tag Transfer operation occurs within the transaction.

## <span id="page-197-2"></span><span id="page-197-1"></span>**A12.2.10 MTE and Poison**

Section [A16.1](#page-264-0) *[Data protection using Poison](#page-264-0)* discusses the concept of Poison associated with read and write data. There is no poison signaling directly associated with Allocation Tags. When writing a tag with poisoned data, the stored tag might be marked as poisoned.

The exact mechanism for this is IMPLEMENTATION DEFINED. Implementations might choose to do one of the following, but other implementations are possible.

- Poison associated with the data results in the tag being poisoned. Depending on the granularity of the poison associated with the tag, it may not be possible to clear the poison using the same techniques that would be used to clear poison associated with data.
- Poison associated with the data does not result in the tag being poisoned. This means that a corrupted tag might subsequently be used in an MTE Match operation, which could fail incorrectly. The rate at which this occurs should be significantly lower than the rate at which data corruption occurs.
- <span id="page-197-3"></span>• A combination of approaches may be employed, depending on the caching or storage structures in use.

# <span id="page-198-0"></span>**A12.3 Trace signals**

An optional Trace signal can be associated with each channel to support the debugging, tracing, and performance measurement of systems.

The Trace\_Signals property is used to indicate whether a component supports Trace signals.

**Table A12.16: Trace\_Signals property**

| Trace_Signals | Default | Description                                 |  |
|---------------|---------|---------------------------------------------|--|
| True          |         | Trace signals are included on all channels. |  |
| False         | Y       | Trace signals are not present.              |  |

<span id="page-198-1"></span>The Trace signals associated with each channel are shown in Table [A12.17.](#page-198-1) If the Trace\_Signals property is True, then the appropriate Trace signal must be present for all channels that are present.

**Table A12.17: Trace signals**

<span id="page-198-4"></span><span id="page-198-3"></span><span id="page-198-2"></span>

| Name    | Width | Default<br>Description |                                                          |
|---------|-------|------------------------|----------------------------------------------------------|
| AWTRACE | 1     | -                      | Trace signal associated with the write request channel.  |
| WTRACE  | 1     | -                      | Trace signal associated with the write data channel.     |
| BTRACE  | 1     | -                      | Trace signal associated with the write response channel. |
| ARTRACE | 1     | -                      | Trace signal associated with the read request channel.   |
| RTRACE  | 1     | -                      | Trace signal associated with the read data channel.      |

<span id="page-198-6"></span><span id="page-198-5"></span>The exact use for Trace signals is not detailed in this specification, but it is expected that the use of Trace signaling is coordinated across the system and only one use of the Trace signaling occurs at a given time. Trace signal behavior is IMPLEMENTATION DEFINED, but the following recommendations are given:

- A Manager interface can assert the Trace signal along with the address of a transaction that should be tracked through the system.
- A component that provides a response to a transaction with the Trace signal asserted in the request provides a response with the Trace signal asserted.
- A component that provides a response to a transaction with the Trace signal deasserted in the request provides a response with the Trace signal deasserted.
- Components that pass-through transactions, preserve the Trace attribute of requests and responses.
- If a downstream component does not support Trace signals, an interconnect can assert Trace on the appropriate transfers.
- A Subordinate that receives a request with AWTRACE asserted should assert the BTRACE signal alongside the response.
- If an interface includes BCOMP, then BTRACE can take any value for responses with BCOMP deasserted.
- WTRACE should be propagated through interconnect components.
- A Subordinate that receives a request with the ARTRACE signal asserted should assert the RTRACE signal alongside every transfer of the read response.
- <span id="page-198-7"></span>• For Atomic transactions that require a response on the read channel, the RTRACE signal should be asserted if AWTRACE was asserted.

# <span id="page-199-0"></span>**A12.4 User Loopback signaling**

User Loopback signaling permits an agent that is issuing requests to store information that is related to the transaction in an indexed table.

The transaction response can then use a fast table index to obtain the required information, rather than requiring a more complex lookup that uses the transaction ID.

The Loopback\_Signals property is used to indicate whether a component supports Loopback signals.

**Table A12.18: Loopback\_Signals property**

| Loopback_Signals<br>Default |   | Description                          |
|-----------------------------|---|--------------------------------------|
| True                        |   | Loopback signaling is supported.     |
| False                       | Y | Loopback signaling is not supported. |

<span id="page-199-1"></span>The Loopback signals associated with each channel are shown in Table [A12.19.](#page-199-1)

**Table A12.19: Loopback signals**

<span id="page-199-4"></span><span id="page-199-3"></span>

| Name   | Width        | Default   | Description                                                                                        |
|--------|--------------|-----------|----------------------------------------------------------------------------------------------------|
| AWLOOP | LOOP_W_WIDTH | All zeros | A user-defined value that must be reflected from a<br>write request to response transfers.         |
| BLOOP  | LOOP_W_WIDTH | All zeros | A user-defined value that is copied from the write<br>request to write responses.                  |
| ARLOOP | LOOP_R_WIDTH | All zeros | A user-defined value that must be reflected from a<br>read request to response and data transfers. |
| RLOOP  | LOOP_R_WIDTH | All zeros | A user-defined value that is copied from the read<br>request to response and data transfers.       |

<span id="page-199-6"></span><span id="page-199-5"></span><span id="page-199-2"></span>The width of the Loopback signals is determined by the properties shown in Table [A12.20.](#page-199-2) The maximum width is a recommendation.

**Table A12.20: Loopback signal width properties**

| Name         | Values | Default | Description                                                                  |
|--------------|--------|---------|------------------------------------------------------------------------------|
| LOOP_W_WIDTH | 08     | -       | Loop signal width on write channels in bits,<br>applies to AWLOOP and BLOOP. |
| LOOP_R_WIDTH | 08     | -       | Loop signal width on read channels in bits, applies<br>to ARLOOP and RLOOP.  |

The rules for the Loopback width properties are:

- If LOOP\_W\_WIDTH is 0, AWLOOP and BLOOP are not present.
- If LOOP\_R\_WIDTH is 0, ARLOOP and RLOOP are not present.
- If Loopback\_Signals is False, LOOP\_R\_WIDTH and LOOP\_W\_WIDTH must be 0.
- If Loopback\_Signals is True, LOOP\_W\_WIDTH or LOOP\_R\_WIDTH must be greater than 0.

The usage rules are:

- The value of BLOOP must be identical to the value that was on AWLOOP.
- If an interface includes BCOMP, then BLOOP can take any value for responses with BCOMP deasserted.
- The value of RLOOP must be identical to the value that was on ARLOOP for all read data transfers.
- For Atomic transactions that require a response on the read channel, the value of RLOOP must be identical to the value that was presented on AWLOOP. This means that the Manager must use loop values that can be signaled on both AWLOOP and RLOOP.

Loopback values are not required to be unique. Multiple outstanding transactions from the same Manager are permitted to use the same value.

It is not required that the Loopback value is preserved as a transaction progresses through a system. An intermediate component is permitted to store the Loopback value of a request it receives and use its own value for a request that it propagates downstream. When the component receives a response to the downstream transaction, it can retrieve the Loopback value for the original transaction.

# <span id="page-201-0"></span>**A12.5 User defined signaling**

An AXI interface can include a set of user-defined signals, called User signals. The signals can be used to augment information to a transaction, where there is a requirement that is not covered by the existing AMBA specification.

Information can be added to:

- A transaction request
- A transaction response
- Each transfer of read or write data within a transaction

Generally, it is recommended to avoid using User signals. The AXI protocol does not define the functions of these signals, which can lead to interoperability issues if two components use the same User signals in an incompatible manner.

### <span id="page-201-3"></span><span id="page-201-1"></span>**A12.5.1 Configuration**

The presence and width of User signals is specified by the properties in Table [A12.21:](#page-201-3)

**Table A12.21: User signal properties**

| Name            | Values | Default | Description                                                                     |
|-----------------|--------|---------|---------------------------------------------------------------------------------|
| USER_REQ_WIDTH  | 0128   | 0       | Width of user extensions to a request in<br>bits, applies to AWUSER and ARUSER. |
| USER_DATA_WIDTH | 0512   | 0       | Width of user extensions to data in bits,<br>applies to WUSER and RUSER.        |
| USER_RESP_WIDTH | 016    | 0       | Width of user extensions to responses in<br>bits, applies to BUSER and RUSER.   |

If a property has a value of zero, then the associated signals are not present on the interface.

The maximum signal widths are for guidance only, to set a reasonable maximum for configurable interfaces.

### <span id="page-201-4"></span><span id="page-201-2"></span>**A12.5.2 User signals**

The user signals that can be added to each channel are shown in Table [A12.22.](#page-201-4)

**Table A12.22: User signals**

<span id="page-201-9"></span><span id="page-201-8"></span><span id="page-201-7"></span><span id="page-201-6"></span><span id="page-201-5"></span>

| Name              | Width                                | Default   | Description                                          |
|-------------------|--------------------------------------|-----------|------------------------------------------------------|
| AWUSER,<br>ARUSER | USER_REQ_WIDTH                       | All zeros | User-defined extension to a request.                 |
| WUSER             | USER_DATA_WIDTH                      | All zeros | User-defined extension to write data.                |
| BUSER             | USER_RESP_WIDTH                      | All zeros | User-defined extension to a write response.          |
| RUSER             | USER_DATA_WIDTH +<br>USER_RESP_WIDTH | All zeros | User-defined extension to read data and<br>response. |

### <span id="page-202-0"></span>**A12.5.3 Usage considerations**

Where User signals are implemented:

- The design decision regarding presence and width of User signals is made independently for request, data, and response channels.
- It is not required that values on request User signals are reflected on response User signals.

To assist with data width and protocol conversion, it is recommended that:

- USER\_DATA\_WIDTH is an integer multiple of the width of the data channels in bytes.
- User response bits are the same value for every transfer of a read or write response.
- The lower bits of RUSER are used to transport per-transaction response information.
- <span id="page-202-1"></span>• The upper bits of RUSER are used to transport per-transfer read data information.
