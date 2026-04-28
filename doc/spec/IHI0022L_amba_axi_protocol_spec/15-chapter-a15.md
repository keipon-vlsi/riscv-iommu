# <span id="page-230-0"></span>Chapter A15

# **Distributed Virtual Memory messages**

This chapter describes how AXI supports distributed system MMUs using Distributed Virtual Memory (DVM) messages to maintain all MMUs in a virtual memory system.

It contains the following sections:

- [A15.1](#page-231-0) *[Introduction to DVM transactions](#page-231-0)*
- [A15.2](#page-232-0) *[Support for DVM messages](#page-232-0)*
- [A15.3](#page-233-0) *[DVM messages](#page-233-0)*
- [A15.4](#page-247-0) *[Transporting DVM messages](#page-247-0)*
- [A15.5](#page-257-0) *[DVM Sync and Complete](#page-257-0)*
- [A15.6](#page-259-0) *[Coherency Connection signaling](#page-259-0)*

# <span id="page-231-0"></span>**A15.1 Introduction to DVM transactions**

DVM transactions are an optional feature used to pass messages that support the maintenance of a virtual memory system. There are two types of DVM transactions: DVM message and DVM Complete.

A DVM message supports the following operations:

- TLB Invalidate
- Branch Predictor Invalidate
- Physical Instruction Cache Invalidate
- Virtual Instruction Cache Invalidate
- Synchronization
- Hint

DVM message requests are sent from a Subordinate interface, usually on an interconnect, to a Manager interface using the snoop request (AC) channel.

DVM message responses are sent from a Manager to Subordinate interface using the snoop response (CR) channel.

A DVM Complete transaction is issued on the read request channel (AR) in response to a DVM Synchronization (Sync) message, to indicate that all required operations and any associated transactions have completed.

# <span id="page-232-2"></span><span id="page-232-0"></span>**A15.2 Support for DVM messages**

The DVM\_Message\_Support property is used to indicate if an interface supports DVM messages.

**Table A15.1: DVM\_Message\_Support property**

| DVM_Message_Support | Default | Description                                                                                                                                                                                                                               |
|---------------------|---------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Receiver            |         | DVM message and Synchronization transactions are<br>supported from Subordinate to Manager interfaces on the<br>AC/CR channels. DVM Complete transactions are<br>supported from Manager to Subordinate interfaces on the<br>AR/R channels. |
| False               | Y       | DVM message transactions are not supported.                                                                                                                                                                                               |

Note that the Bidirectional option for DVM\_Message\_Support in previous issues of this specification is deprecated in this specification.

DVM Complete messages require that ARDOMAIN is set to Shareable. Therefore, when DVM\_Message\_Support is Receiver the Shareable\_Transactions property must be True.

DVM messages were introduced in the Armv7 architecture and were extended in Armv8, Armv8.1, Armv8.4, and Armv9.2 architectures. It is essential that interfaces initiating and receiving DVM messages support the same architecture versions.

The following properties define the version that is supported by an interface:

- DVM\_v8
- DVM\_v8.1
- DVM\_v8.4
- DVM\_v9.2

Each property can take the values: True or False. If a property is not declared, then it is considered False.

In Table [A15.2](#page-232-1) there is an indication of which message versions are supported, depending on the property values. A component that supports DVM messages from a specific version must also support earlier architecture versions.

**Table A15.2: DVM message versions**

<span id="page-232-1"></span>

| DVM property |               |               |               | Architecture support |         |         |       |       |
|--------------|---------------|---------------|---------------|----------------------|---------|---------|-------|-------|
| DVM_v9.2     | DVM_v8.4      | DVM_v8.1      | DVM_v8        | Armv9.2              | Armv8.4 | Armv8.1 | Armv8 | Armv7 |
| True         | True or False | True or False | True or False | Y                    | Y       | Y       | Y     | Y     |
| False        | True          | True or False | True or False | -                    | Y       | Y       | Y     | Y     |
| False        | False         | True          | True or False | -                    | -       | Y       | Y     | Y     |
| False        | False         | False         | True          | -                    | -       | -       | Y     | Y     |
| False        | False         | False         | False         | -                    | -       | -       | -     | Y     |

# <span id="page-233-0"></span>**A15.3 DVM messages**

The following DVM messages are supported by the protocol:

- TLB Invalidate
- Branch Predictor Invalidate
- Physical Instruction Cache Invalidate
- Virtual Instruction Cache Invalidate
- Synchronization
- Hint

DVM transactions only operate on read-only structures, such as Instruction cache, Branch Predictor, and TLB, and therefore only invalidation operations are required. The concept of cleaning does not apply to a read-only structure. This means that it is functionally correct to invalidate more entries than the DVM message requires, although the extra invalidations can affect performance.

### <span id="page-233-2"></span><span id="page-233-1"></span>**A15.3.1 DVM message fields**

The fields in DVM messages are shown in Table [A15.3.](#page-233-2)

**Table A15.3: DVM message fields**

| Name    | Width   | Description                                                                                    |                                                                                                |  |  |
|---------|---------|------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|--|--|
| VA      | 32-57   |                                                                                                | Virtual Address or Intermediate Physical Address (IPA).                                        |  |  |
| PA      | 32-52   | Physical Address                                                                               |                                                                                                |  |  |
| ASID    | 8 or 16 |                                                                                                | Address Space ID                                                                               |  |  |
| ASIDV   | 1       |                                                                                                | Asserted HIGH to indicate that the ASID field is valid.<br>When deasserted, ASID must be zero. |  |  |
| VMID    | 8 or 16 | Virtual Machine ID                                                                             |                                                                                                |  |  |
| VMIDV   | 1       | Asserted HIGH to indicate that the VMID field is valid.<br>When deasserted, VMID must be zero. |                                                                                                |  |  |
| DVMType | 3       | DVM message type:                                                                              |                                                                                                |  |  |
|         |         | 0b000                                                                                          | TLB Invalidate (TLBI)                                                                          |  |  |
|         |         | 0b001                                                                                          | Branch Predictor Invalidate (BPI)                                                              |  |  |
|         |         | 0b010                                                                                          | Physical Instruction Cache Invalidate (PICI)                                                   |  |  |
|         |         | 0b011                                                                                          | Virtual Instruction Cache Invalidate (VICI)                                                    |  |  |
|         |         | 0b100                                                                                          | Synchronization (Sync)                                                                         |  |  |
|         |         | 0b101                                                                                          | Reserved                                                                                       |  |  |
|         |         | 0b110                                                                                          | Hint                                                                                           |  |  |
|         |         | 0b111                                                                                          | Reserved                                                                                       |  |  |

Table A15.3 – *Continued from previous page*

| Name      | Width | Description                                                                                        |                                                                                                                                       |  |  |
|-----------|-------|----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|--|--|
| Exception | 2     |                                                                                                    | Indicates the Exception level that the transaction applies to:                                                                        |  |  |
|           |       | 0b00                                                                                               | Hypervisor and all Guest OS                                                                                                           |  |  |
|           |       | 0b01                                                                                               | EL3                                                                                                                                   |  |  |
|           |       | 0b10                                                                                               | Guest OS                                                                                                                              |  |  |
|           |       | 0b11                                                                                               | Hypervisor                                                                                                                            |  |  |
| Security  | 2     |                                                                                                    | Indicates which Security state the invalidation applies to.<br>See Table A15.6 for encodings.                                         |  |  |
| Leaf      | 1     |                                                                                                    | Indicates whether only leaf entries are invalidated:                                                                                  |  |  |
|           |       | 0b0                                                                                                | Invalidate all associated translations.                                                                                               |  |  |
|           |       | 0b1                                                                                                | Invalidate Leaf Entry only.                                                                                                           |  |  |
| Stage     | 2     |                                                                                                    | Indicates which stages are invalidated:                                                                                               |  |  |
|           |       | 0b00                                                                                               | Armv7: Stage of invalidation varies with invalidation type.<br>Armv8 and later: Stage 1 and Stage 2 invalidation.                     |  |  |
|           |       | 0b01                                                                                               | Stage 1 only invalidation.                                                                                                            |  |  |
|           |       | 0b10                                                                                               | Stage 2 only invalidation.                                                                                                            |  |  |
|           |       | 0b11                                                                                               | GPT                                                                                                                                   |  |  |
| Num       | 5     | Used as a constant multiplication factor in the range calculation.<br>All binary values are valid. |                                                                                                                                       |  |  |
| Scale     | 2     | Used as a constant in address range exponent calculation.<br>All binary values are valid.          |                                                                                                                                       |  |  |
| TTL       | 2     |                                                                                                    | Hint of Translation Table Level (TTL) which includes the addresses to be<br>invalidated. See Table A15.4 and Table A15.5 for details. |  |  |
| TG        | 2     | 0b00                                                                                               | Translation Granule (TG).<br>For TLB Invalidations by range, TG indicates the granule size:<br>Reserved.                              |  |  |
|           |       | 0b01                                                                                               | 4KB                                                                                                                                   |  |  |
|           |       | 0b10                                                                                               | 16KB                                                                                                                                  |  |  |
|           |       | 0b11<br>Table A15.5.                                                                               | 64KB<br>For non-range TLB Invalidations, TG and TTL indicate the table level hint, see                                                |  |  |
| VI        | 16    |                                                                                                    | Virtual Index, used for PICI messages.                                                                                                |  |  |
| VIV       | 2     | Virtual Index Valid:<br>0b00                                                                       | Virtual Index not valid                                                                                                               |  |  |
|           |       | 0b01                                                                                               | Reserved                                                                                                                              |  |  |
|           |       | 0b10                                                                                               | Reserved                                                                                                                              |  |  |
|           |       | 0b11                                                                                               | Virtual Index valid                                                                                                                   |  |  |

Table A15.3 – *Continued from previous page*

| Name       | Width | Description                                                             |                                               |  |
|------------|-------|-------------------------------------------------------------------------|-----------------------------------------------|--|
| IS         | 4     | Invalidation Size encoding for GPT TLBI by PA operations:               |                                               |  |
|            |       | 0b0000                                                                  | 4KB                                           |  |
|            |       | 0b0001                                                                  | 16KB                                          |  |
|            |       | 0b0010                                                                  | 64KB                                          |  |
|            |       | 0b0011                                                                  | 2MB                                           |  |
|            |       | 0b0100                                                                  | 32MB                                          |  |
|            |       | 0b0101                                                                  | 512MB                                         |  |
|            |       | 0b0110                                                                  | 1GB                                           |  |
|            |       | 0b0111                                                                  | 16GB                                          |  |
|            |       | 0b1000                                                                  | 64GB                                          |  |
|            |       | 0b1001                                                                  | 512GB                                         |  |
|            |       | 0b1010-<br>0b1111                                                       | Reserved                                      |  |
| Addr       | 1     |                                                                         | Indicates if the message includes an address. |  |
|            |       | 0b0                                                                     | No address information.                       |  |
|            |       | 0b1                                                                     | Address included, this is a two-part message. |  |
| Range      | 1     | Asserted HIGH to indicate that the 2nd part indicates an address range. |                                               |  |
| Completion | 1     | Asserted HIGH to indicate that a Completion message is required.        |                                               |  |

#### *TLB Invalidate level hint*

<span id="page-236-0"></span>For TLB Invalidations by address range, the TTL field indicates which level of translation table walk holds the leaf entry for the address being invalidated. The encodings are shown in Table [A15.4.](#page-236-0)

**Table A15.4: Leaf entry hint for range-based TLB Invalidations**

| TTL  | Meaning                                                     |
|------|-------------------------------------------------------------|
| 0b00 | No level hint information.                                  |
| 0b01 | The leaf entry is on level 1 of the translation table walk. |
| 0b10 | The leaf entry is on level 2 of the translation table walk. |
| 0b11 | The leaf entry is on level 3 of the translation table walk. |

<span id="page-236-1"></span>For TLB Invalidations by non-range address, the TTL and TG fields indicate which level of translation table walk holds the leaf entry for the address being invalidated. The encodings are shown in Table [A15.5.](#page-236-1)

**Table A15.5: Leaf entry hint for non-range TLB Invalidations**

| TG   | TTL  | Meaning                                                     |
|------|------|-------------------------------------------------------------|
| 0b00 | 0b00 | No level hint                                               |
|      | 0b01 | Reserved                                                    |
|      | 0b10 | Reserved                                                    |
|      | 0b11 | Reserved                                                    |
| 0b01 | 0b00 | No level hint                                               |
|      | 0b01 | The leaf entry is on level 1 of the translation table walk. |
|      | 0b10 | The leaf entry is on level 2 of the translation table walk. |
|      | 0b11 | The leaf entry is on level 3 of the translation table walk. |
| 0b10 | 0b00 | No level hint                                               |
|      | 0b01 | No level hint                                               |
|      | 0b10 | The leaf entry is on level 2 of the translation table walk. |
|      | 0b11 | The leaf entry is on level 3 of the translation table walk. |
| 0b11 | 0b00 | No level hint                                               |
|      | 0b01 | The leaf entry is on level 1 of the translation table walk. |
|      | 0b10 | The leaf entry is on level 2 of the translation table walk. |
|      | 0b11 | The leaf entry is on level 3 of the translation table walk. |

#### *Security field*

<span id="page-237-0"></span>The Security field has different meanings depending on the DVM Type, as shown in Table [A15.6.](#page-237-0)

**Table A15.6: Security field encodings per DVM Type**

| Security | TLBI                                           | BPI                      | PICI All                                  | PICI by PA | VICI                     |
|----------|------------------------------------------------|--------------------------|-------------------------------------------|------------|--------------------------|
| 0b00     | Realm                                          | Secure and<br>Non-secure | Root, Realm,<br>Secure, and<br>Non-secure | Root       | Secure and<br>Non-secure |
| 0b01     | Non-secure<br>address from a<br>Secure context | Reserved                 | Realm and<br>Non-secure                   | Realm      | Reserved                 |
| 0b10     | Secure                                         | Reserved                 | Secure and<br>Non-secure                  | Secure     | Secure                   |
| 0b11     | Non-secure                                     | Reserved                 | Non-secure                                | Non-secure | Non-secure               |

#### <span id="page-237-1"></span>*ASID field*

The ASID field contains an 8-bit or 16-bit Address Space ID.

- Armv7 supports only an 8-bit ASID.
- Armv8 and above support both 8-bit and 16-bit ASID.

It cannot be determined from a DVM message whether the message uses an 8-bit or 16-bit ASID. All 8-bit ASID messages are required to set the ASID[15:8] bits to zero.

It is expected that most systems will use a single ASID size across the entire system, either 8-bit ASID or 16-bit ASID.

In a system that contains a mix of 8-bit ASID and 16-bit ASID components, it is expected that all maintenance is done by an agent that uses 16-bit ASID. This ensures that the agent can perform maintenance on both the 8-bit ASID and 16-bit ASID components.

The interoperability requirements are:

- For an 8-bit ASID agent sending a message to a 16-bit ASID agent, a message appears as a 16-bit ASID with the upper 8 bits set to zero.
- For a 16-bit ASID agent sending a message to an 8-bit ASID agent:
  - If the upper 8 bits are zero, the message was received correctly.
  - If the upper 8 bits are non-zero, then over-invalidation will occur, since the 8-bit ASID agent ignores the upper 8 bits.

### *VMID field*

The VMID field contains an 8-bit or 16-bit Virtual Machine ID.

- Armv7 and Armv8 support only 8-bit VMIDs.
- Armv8.1 and above support both 8-bit and 16-bit VMIDs.

It cannot be determined from a DVM message whether the message uses an 8-bit or 16-bit VMID. All 8-bit VMID messages are required to set the VMID[15:8] field to zero.

It is expected that most systems use a single VMID size across the entire system, either 8-bit VMID or 16-bit VMID.

In a system that contains a mix of 8-bit VMID and 16-bit VMID components, it is expected that all maintenance is done by an agent that uses 16-bit VMID. This ensures that the agent can perform maintenance on both the 8-bit VMID and 16-bit VMID components.

The interoperability requirements are:

- For an 8-bit VMID agent sending a message to a 16-bit VMID agent, a message appears as a 16-bit VMID with the upper 8 bits set to zero.
- For a 16-bit VMID agent sending a message to an 8-bit VMID agent:
  - If the upper 8 bits are zero, the message was received correctly.
  - If the upper 8 bits are nonzero, then over-invalidation will occur, since the 8-bit VMID agent ignores the upper 8 bits.

When Armv8.1 and above is supported, ACVMIDEXT is included on the AC channel to transport the upper byte of 16-bit VMIDs. See [A15.4](#page-247-0) *[Transporting DVM messages](#page-247-0)* for more details.

### <span id="page-238-1"></span><span id="page-238-0"></span>**A15.3.2 TLB Invalidate messages**

This section details the TLB Invalidate (TLBI) message.

For a TLBI message some fields have a fixed value, as shown in Table [A15.7.](#page-238-1)

**Table A15.7: Fixed field values for a TLBI message**

| Name       | Value | Meaning                  |  |  |  |  |
|------------|-------|--------------------------|--|--|--|--|
| DVMType    | 0b000 | TLB Invalidate opcode.   |  |  |  |  |
| Completion | 0b0   | Completion not required. |  |  |  |  |

The entries on which the TLBI must operate depends on the fields in the message. All supported TLBI operations are shown in Table [A15.8.](#page-238-2)

The Arm column indicates the minimum Arm architecture version required to support the message.

The field to signal mappings for TLBI messages are detailed in Table [A15.20.](#page-251-0)

**Table A15.8: TLBI messages**

<span id="page-238-2"></span>

| Operation                                            | Arm  | Exception | Security | VMIDV | ASIDV | Leaf | Stage | Addr |
|------------------------------------------------------|------|-----------|----------|-------|-------|------|-------|------|
| EL3 TLBI all                                         | v8   | 0b01      | 0b10     | 0b0   | 0b0   | 0b0  | 0b00  | 0b0  |
| EL3 TLBI by VA                                       | v8   | 0b01      | 0b10     | 0b0   | 0b0   | 0b0  | 0b00  | 0b1  |
| EL3 TLBI by VA, Leaf only                            | v8   | 0b01      | 0b10     | 0b0   | 0b0   | 0b1  | 0b00  | 0b1  |
| Secure Guest OS TLBI by Non-secure IPA               | v8.4 | 0b10      | 0b01     | 0b1   | 0b0   | 0b0  | 0b10  | 0b1  |
| Secure Guest OS TLBI by Non-secure IPA,<br>Leaf only | v8.4 | 0b10      | 0b01     | 0b1   | 0b0   | 0b1  | 0b10  | 0b1  |
| Secure TLBI all                                      | v7   | 0b10      | 0b10     | 0b0   | 0b0   | 0b0  | 0b00  | 0b0  |
| Secure TLBI by VA                                    | v7   | 0b10      | 0b10     | 0b0   | 0b0   | 0b0  | 0b00  | 0b1  |
| Secure TLBI by VA, Leaf only                         | v8   | 0b10      | 0b10     | 0b0   | 0b0   | 0b1  | 0b00  | 0b1  |

Table A15.8 – *Continued from previous page*

|                                                     |      |           |          | Table A15.8 – Continued from previous page |       |      |       |      |
|-----------------------------------------------------|------|-----------|----------|--------------------------------------------|-------|------|-------|------|
| Operation                                           | Arm  | Exception | Security | VMIDV                                      | ASIDV | Leaf | Stage | Addr |
| Secure TLBI by ASID                                 | v7   | 0b10      | 0b10     | 0b0                                        | 0b1   | 0b0  | 0b00  | 0b0  |
| Secure TLBI by ASID and VA                          | v7   | 0b10      | 0b10     | 0b0                                        | 0b1   | 0b0  | 0b00  | 0b1  |
| Secure TLBI by ASID and VA, Leaf only               | v8   | 0b10      | 0b10     | 0b0                                        | 0b1   | 0b1  | 0b00  | 0b1  |
| Secure Guest OS TLBI all                            | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b0   | 0b0  | 0b00  | 0b0  |
| Secure Guest OS TLBI by VA                          | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b0   | 0b0  | 0b00  | 0b1  |
| Secure Guest OS TLBI all, Stage 1 only              | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b0   | 0b0  | 0b01  | 0b0  |
| Secure Guest OS TLBI by Secure IPA                  | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b0   | 0b0  | 0b10  | 0b1  |
| Secure Guest OS TLBI by VA, Leaf only               | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b0   | 0b1  | 0b00  | 0b1  |
| Secure Guest OS TLBI by Secure IPA,<br>Leaf only    | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b0   | 0b1  | 0b10  | 0b1  |
| Secure Guest OS TLBI by ASID                        | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b1   | 0b0  | 0b00  | 0b0  |
| Secure Guest OS TLBI by ASID and VA                 | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b1   | 0b0  | 0b00  | 0b1  |
| Secure Guest OS TLBI by ASID and VA,<br>Leaf only   | v8.4 | 0b10      | 0b10     | 0b1                                        | 0b1   | 0b1  | 0b00  | 0b1  |
| All OS TLBI all                                     | v7   | 0b10      | 0b11     | 0b0                                        | 0b0   | 0b0  | 0b00  | 0b0  |
| Guest OS TLBI all, Stage 1 and 2                    | v7   | 0b10      | 0b11     | 0b1                                        | 0b0   | 0b0  | 0b00  | 0b0  |
| Guest OS TLBI by VA                                 | v7   | 0b10      | 0b11     | 0b1                                        | 0b0   | 0b0  | 0b00  | 0b1  |
| Guest OS TLBI all, Stage 1 only                     | v8   | 0b10      | 0b11     | 0b1                                        | 0b0   | 0b0  | 0b01  | 0b0  |
| Guest OS TLBI by IPA                                | v8   | 0b10      | 0b11     | 0b1                                        | 0b0   | 0b0  | 0b10  | 0b1  |
| Guest OS TLBI by VA, Leaf only                      | v8   | 0b10      | 0b11     | 0b1                                        | 0b0   | 0b1  | 0b00  | 0b1  |
| Guest OS TLBI by IPA, Leaf only                     | v8   | 0b10      | 0b11     | 0b1                                        | 0b0   | 0b1  | 0b10  | 0b1  |
| Guest OS TLBI by ASID                               | v7   | 0b10      | 0b11     | 0b1                                        | 0b1   | 0b0  | 0b00  | 0b0  |
| Guest OS TLBI by ASID and VA                        | v7   | 0b10      | 0b11     | 0b1                                        | 0b1   | 0b0  | 0b00  | 0b1  |
| Guest OS TLBI by ASID and VA, Leaf<br>only          | v8   | 0b10      | 0b11     | 0b1                                        | 0b1   | 0b1  | 0b00  | 0b1  |
| Secure Hypervisor TLBI all                          | v8.4 | 0b11      | 0b10     | 0b0                                        | 0b0   | 0b0  | 0b00  | 0b0  |
| Secure Hypervisor TLBI by VA                        | v8.4 | 0b11      | 0b10     | 0b0                                        | 0b0   | 0b0  | 0b00  | 0b1  |
| Secure Hypervisor TLBI by VA, Leaf only             | v8.4 | 0b11      | 0b10     | 0b0                                        | 0b0   | 0b1  | 0b00  | 0b1  |
| Secure Hypervisor TLBI by ASID                      | v8.4 | 0b11      | 0b10     | 0b0                                        | 0b1   | 0b0  | 0b00  | 0b0  |
| Secure Hypervisor TLBI by ASID and VA               | v8.4 | 0b11      | 0b10     | 0b0                                        | 0b1   | 0b0  | 0b00  | 0b1  |
| Secure Hypervisor TLBI by ASID and VA,<br>Leaf only | v8.4 | 0b11      | 0b10     | 0b0                                        | 0b1   | 0b1  | 0b00  | 0b1  |
| Hypervisor TLBI all                                 | v7   | 0b11      | 0b11     | 0b0                                        | 0b0   | 0b0  | 0b00  | 0b0  |
| Hypervisor TLBI by VA                               | v7   | 0b11      | 0b11     | 0b0                                        | 0b0   | 0b0  | 0b00  | 0b1  |
|                                                     |      |           |          |                                            |       |      |       |      |

Table A15.8 – *Continued from previous page*

| Operation                                          | Arm  | Exception | Security | VMIDV | ASIDV | Leaf | Stage | Addr |
|----------------------------------------------------|------|-----------|----------|-------|-------|------|-------|------|
| Hypervisor TLBI by VA, Leaf only                   | v8   | 0b11      | 0b11     | 0b0   | 0b0   | 0b1  | 0b00  | 0b1  |
| Hypervisor TLBI by ASID                            | v8.1 | 0b11      | 0b11     | 0b0   | 0b1   | 0b0  | 0b00  | 0b0  |
| Hypervisor TLBI by ASID and VA                     | v8.1 | 0b11      | 0b11     | 0b0   | 0b1   | 0b0  | 0b00  | 0b1  |
| Hypervisor TLBI by ASID and VA, Leaf<br>only       | v8.1 | 0b11      | 0b11     | 0b0   | 0b1   | 0b1  | 0b00  | 0b1  |
| Realm TLBI all                                     | v9.2 | 0b10      | 0b00     | 0b0   | 0b0   | 0b0  | 0b00  | 0b0  |
| Realm Guest OS TLBI all, Stage 1 only              | v9.2 | 0b10      | 0b00     | 0b1   | 0b0   | 0b0  | 0b01  | 0b0  |
| Realm Guest OS TLBI all, Stage 1 and 2             | v9.2 | 0b10      | 0b00     | 0b1   | 0b0   | 0b0  | 0b00  | 0b0  |
| Realm Guest OS TLBI by VA                          | v9.2 | 0b10      | 0b00     | 0b1   | 0b0   | 0b0  | 0b00  | 0b1  |
| Realm Guest OS TLBI by VA, Leaf only               | v9.2 | 0b10      | 0b00     | 0b1   | 0b0   | 0b1  | 0b00  | 0b1  |
| Realm Guest OS TLBI by ASID                        | v9.2 | 0b10      | 0b00     | 0b1   | 0b1   | 0b0  | 0b00  | 0b0  |
| Realm Guest OS TLBI by ASID and VA                 | v9.2 | 0b10      | 0b00     | 0b1   | 0b1   | 0b0  | 0b00  | 0b1  |
| Realm Guest OS TLBI by ASID and VA,<br>Leaf only   | v9.2 | 0b10      | 0b00     | 0b1   | 0b1   | 0b1  | 0b00  | 0b1  |
| Realm Guest OS TLBI by IPA                         | v9.2 | 0b10      | 0b00     | 0b1   | 0b0   | 0b0  | 0b10  | 0b1  |
| Realm Guest OS TLBI by IPA, Leaf only              | v9.2 | 0b10      | 0b00     | 0b1   | 0b0   | 0b1  | 0b10  | 0b1  |
| Realm Hypervisor TLBI all                          | v9.2 | 0b11      | 0b00     | 0b0   | 0b0   | 0b0  | 0b00  | 0b0  |
| Realm Hypervisor TLBI by VA                        | v9.2 | 0b11      | 0b00     | 0b0   | 0b0   | 0b0  | 0b00  | 0b1  |
| Realm Hypervisor TLBI by VA, Leaf only             | v9.2 | 0b11      | 0b00     | 0b0   | 0b0   | 0b1  | 0b00  | 0b1  |
| Realm Hypervisor TLBI by ASID                      | v9.2 | 0b11      | 0b00     | 0b0   | 0b1   | 0b0  | 0b00  | 0b0  |
| Realm Hypervisor TLBI by ASID and VA               | v9.2 | 0b11      | 0b00     | 0b0   | 0b1   | 0b0  | 0b00  | 0b1  |
| Realm Hypervisor TLBI by ASID and VA,<br>Leaf only | v9.2 | 0b11      | 0b00     | 0b0   | 0b1   | 0b1  | 0b00  | 0b1  |
| GPT TLBI by PA                                     | v9.2 | 0b01      | 0b10     | 0b0   | 0b0   | 0b0  | 0b11  | 0b1  |
| GPT TLBI by PA, Leaf only                          | v9.2 | 0b01      | 0b10     | 0b0   | 0b0   | 0b1  | 0b11  | 0b1  |
| GPT TLBI all                                       | v9.2 | 0b01      | 0b10     | 0b0   | 0b0   | 0b0  | 0b11  | 0b0  |
|                                                    |      |           |          |       |       |      |       |      |

#### <span id="page-241-0"></span>*Range field*

The Range field indicates that an invalidation operates on a range of addresses.

Range can be 0b1 for messages where both of the following apply:

- Arm is v8.4 or later.
- The Addr bit is 0b1, so the message includes an address.

#### *Range based TLB Invalidate by IPA or VA*

When the Range field is 0b1 for a TLBI by VA or IPA, the address range to invalidate is calculated using the following formula:

BaseAddr ≤ AddressRange < BaseAddr+ (Num + 1) × 2 (5×Scale+1) × T ranslation\_Granule\_Size

### Where:

- *Translation\_Granule\_Size* in bytes is determined from the TG value provided in the message. See [Table](#page-233-2) [A15.3](#page-233-2) for encodings.
- *Scale* is provided in the message, it can take any value from 0-3.
- *Num* is provided in the message, it can take any value from 0-31.
- *BaseAddr* is the base address of the range, based on TG:
  - 4K: BaseAddr is VA[MaxVA:12].
  - 16K: BaseAddr is VA[MaxVA:14], VA[13:12] must be zero.
  - 64K: BaseAddr is VA[MaxVA:16], VA[15:12] must be zero.

A TLBI by Range is a 2-part message with field mappings described in Table [A15.20.](#page-251-0)

#### *GPT TLB Invalidate*

Granule Protection Table (GPT) TLBI by PA operations perform range-based invalidation and invalidate TLB entries starting from the PA, within the range as specified in the *Invalidation Size* (IS) field. See Table [A15.3](#page-233-2) for encodings.

If the PA is not aligned to the IS value, no TLB entries are required to be invalidated.

The IS field is applicable only in GPT TLBI by PA operations.

- A *GPT TLBI all* message is signaled using a 1-part message with the Range field set to 0b0.
- A *GPT TLBI by PA* message is signaled using a 2-part message with the Range field set to 0b1.

The field to signal mappings for GPT TLBI messages are shown in Table [A15.20.](#page-251-0)

### <span id="page-242-0"></span>**A15.3.3 Branch Predictor Invalidate messages**

The *Branch Predictor Invalidate* (BPI) message is used to invalidate virtual addresses from branch predictors.

<span id="page-242-1"></span>A BPI message is signaled using a 1-part or 2-part message with field to signal mappings detailed in Table [A15.21.](#page-253-0) The fixed field values for a BPI message are shown in Table [A15.9.](#page-242-1)

**Table A15.9: Fixed field values for a BPI message**

| Name       | Value | Meaning                            |
|------------|-------|------------------------------------|
| DVMType    | 0b001 | Branch Predictor Invalidate opcode |
| Completion | 0b0   | Completion not required            |
| Range      | 0b0   | Address is not a range             |
| VMIDV      | 0b0   | VMID field not valid               |
| ASIDV      | 0b0   | ASID field not valid               |
| Exception  | 0b00  | Hypervisor and all Guest OS        |
| Security   | 0b00  | Secure and Non-secure              |
| Leaf       | 0b0   | Leaf information is N/A            |
| Stage      | 0b00  | Stage information is N/A           |

All supported BPI operations are shown in Table [A15.10.](#page-242-2)

<span id="page-242-2"></span>The Arm column indicates the minimum Arm architecture version required to support the message.

**Table A15.10: BPI messages**

| Operation                         | Arm | Addr |
|-----------------------------------|-----|------|
| Branch Predictor Invalidate all   | v7  | 0b0  |
| Branch Predictor Invalidate by VA | v7  | 0b1  |

### <span id="page-243-0"></span>**A15.3.4 Instruction cache invalidations**

Instruction caches can use either a physical address or a virtual address to tag the data they contain. A system might contain a mixture of both forms of cache.

The DVM protocol includes instruction cache invalidation operations that use physical addresses and operations that use virtual addresses. A component that receives DVM messages must support both forms of message, independent of the style of instruction cache implemented. It might be necessary to over-invalidate in the case where a message is received in a format that is not native to the cache type.

### *Physical Instruction Cache Invalidate*

This section lists the *Physical Instruction Cache Invalidate* (PICI) operations that the DVM message supports. This message type is also used for Instruction Caches which are *Virtually Indexed Physically Tagged* (VIPT).

<span id="page-243-1"></span>A PICI message is signaled using a 1-part or 2-part message with field to signal mappings detailed in [Table](#page-255-0) [A15.22.](#page-255-0) The fixed field values for a PICI message are shown in Table [A15.11.](#page-243-1)

**Table A15.11: Fixed field values for a PICI message**

| Name       | Value | Meaning                                      |
|------------|-------|----------------------------------------------|
| DVMType    | 0b010 | Physical Instruction Cache Invalidate opcode |
| Completion | 0b0   | Completion not required                      |
| Range      | 0b0   | Address is not a range                       |
| Exception  | 0b00  | Hypervisor and all Guest OS                  |
| Leaf       | 0b0   | Leaf information is N/A                      |
| Stage      | 0b00  | Stage information is N/A                     |

All supported PICI operations are shown in Table [A15.12.](#page-244-0)

**Table A15.12: PICI messages**

<span id="page-244-0"></span>

| Operation                                         | Arm  | Security | VIV  | Addr |
|---------------------------------------------------|------|----------|------|------|
| PICI all Root, Realm, Secure and Non-secure       | v9.2 | 0b00     | 0b00 | 0b0  |
| PICI by PA without Virtual Index, Root only       |      | 0b00     | 0b00 | 0b1  |
| PICI by PA with Virtual Index, Root only          | v9.2 | 0b00     | 0b11 | 0b1  |
| PICI all Realm and Non-secure                     | v9.2 | 0b01     | 0b00 | 0b0  |
| PICI by PA without Virtual Index, Realm only      | v9.2 | 0b01     | 0b00 | 0b1  |
| PICI by PA with Virtual Index, Realm only         | v9.2 | 0b01     | 0b11 | 0b1  |
| PICI all Secure and Non-secure                    | v7   | 0b10     | 0b00 | 0b0  |
| PICI by PA without Virtual Index, Secure only     | v7   | 0b10     | 0b00 | 0b1  |
| PICI by PA with Virtual Index, Secure only        | v7   | 0b10     | 0b11 | 0b1  |
| PICI all, Non-secure only                         | v7   | 0b11     | 0b00 | 0b0  |
| PICI by PA without Virtual Index, Non-secure only | v7   | 0b11     | 0b00 | 0b1  |
| PICI by PA with Virtual Index, Non-secure only    | v7   | 0b11     | 0b11 | 0b1  |

When the Virtual Index Valid (VIV) field is 0b11, then VI[27:12] is used as part of the Physical Address.

Note that in previous issues of this specification, a *PICI all* with Security value of 0b10 was incorrectly labeled as *Secure only* when it should have been *Secure and Non-secure*.

### *Virtual Instruction Cache Invalidate*

This section lists the *Virtual Instruction Cache Invalidate* (VICI) operations that the DVM message supports.

A VICI message is signaled using a 1-part or 2-part message with field to signal mappings detailed in [Table](#page-255-0) [A15.22.](#page-255-0)

<span id="page-244-1"></span>The fixed field values for a VICI message are shown in Table [A15.13.](#page-244-1)

**Table A15.13: Fixed field values for a VICI message**

| Name       | Value | Meaning                                     |
|------------|-------|---------------------------------------------|
| DVMType    | 0b011 | Virtual Instruction Cache Invalidate opcode |
| Completion | 0b0   | Completion not required                     |
| Range      | 0b0   | Address is not a range                      |
| Leaf       | 0b0   | Leaf information is N/A                     |
| Stage      | 0b00  | Stage information is N/A                    |

All supported VICI operations are shown in Table [A15.14.](#page-245-0)

The Arm column indicates the minimum Arm architecture version required to support the message.

**Table A15.14: VICI messages**

<span id="page-245-0"></span>

| Operation                                                   |      | Exception | Security | VMIDV | ASIDV | Addr |
|-------------------------------------------------------------|------|-----------|----------|-------|-------|------|
| Hypervisor and all Guest OS VICI all, Secure and Non-secure | v7   | 0b00      | 0b00     | 0b0   | 0b0   | 0b0  |
| Hypervisor and all Guest OS VICI all, Non-secure only       | v7   | 0b00      | 0b11     | 0b0   | 0b0   | 0b0  |
| All Guest OS VICI by ASID and VA, Secure only               | v7   | 0b10      | 0b10     | 0b0   | 0b1   | 0b1  |
| All Guest OS VICI by VMID, Secure only                      |      | 0b10      | 0b10     | 0b1   | 0b0   | 0b0  |
| All Guest OS VICI by ASID, VA and VMID, Secure only         |      | 0b10      | 0b10     | 0b1   | 0b1   | 0b1  |
| All Guest OS VICI by VMID, Non-secure only                  | v7   | 0b10      | 0b11     | 0b1   | 0b0   | 0b0  |
| All Guest OS VICI by ASID, VA and VMID, Non-secure only     | v7   | 0b10      | 0b11     | 0b1   | 0b1   | 0b1  |
| Hypervisor VICI by VA, Non-secure only                      |      | 0b11      | 0b11     | 0b0   | 0b0   | 0b1  |
| Hypervisor VICI by ASID and VA, Non-secure only             | v8.1 | 0b11      | 0b11     | 0b0   | 0b1   | 0b1  |

### <span id="page-246-0"></span>**A15.3.5 Synchronization message**

A Synchronization (Sync) message is used when the requester needs to know when all previous invalidations are complete. For more information on how to use the Sync message, see [A15.5](#page-257-0) *[DVM Sync and Complete](#page-257-0)*.

A Sync message is signaled using a 1-part message with field to signal mappings detailed in Table [A15.21.](#page-253-0)

<span id="page-246-2"></span>The fixed field values for a Sync message are shown in Table [A15.15.](#page-246-2)

**Table A15.15: Fixed field values for a Sync message**

| Name       | Value | Meaning                      |
|------------|-------|------------------------------|
| DVMType    | 0b100 | Sync opcode                  |
| Completion | 0b1   | Completion required          |
| ASIDV      | 0b0   | No ASID information          |
| VMIDV      | 0b0   | No VMID information          |
| Addr       | 0b0   | No address information       |
| Range      | 0b0   | No address range             |
| Exception  | 0b00  | Exception information is N/A |
| Security   | 0b00  | Security information is N/A  |
| Leaf       | 0b0   | Leaf information is N/A      |
| Stage      | 0b00  | Stage information is N/A     |

### <span id="page-246-3"></span><span id="page-246-1"></span>**A15.3.6 Hint message**

A reserved message address space is provided for future Hint messages.

<span id="page-246-4"></span>The fixed field values for a Hint message are shown in Table [A15.16.](#page-246-3)

**Table A15.16: Fixed field values for a Hint message**

| Name       | Value | Meaning                 |
|------------|-------|-------------------------|
| DVMType    | 0b110 | Hint opcode             |
| Completion | 0b0   | Completion not required |

# <span id="page-247-0"></span>**A15.4 Transporting DVM messages**

To transport DVM messages, two channels are added to an interface:

- Snoop request channel, used to transfer DVM message requests. Signals on this channel have the prefix AC.
- Snoop response channel, used to transfer DVM message responses. Signals on this channel have the prefix CR.

A DVM message transaction consists of one request transfer on the snoop request channel and one response on the snoop response channel. There can be one or two transactions per message, the *Addr* field in the first request indicates if another transaction is required.

DVM messages that do not include an address are sent using one transaction.

DVM messages that include an address are sent using two transactions.

An interconnect is usually used to replicate and distribute DVM message requests to participating Manager components. Managers can use the Coherency Connection signaling to opt into receiving messages at runtime, see [A15.6](#page-259-0) *[Coherency Connection signaling](#page-259-0)*.

Flows for one-part and two-part messages are shown in Figure [A15.1.](#page-247-1)

<span id="page-247-1"></span>![](_page_247_Figure_10.jpeg)

**Figure A15.1: DVM message flows**

The following rules apply to two-part DVM messages:

- The requests are always sent as successive transfers, with no other message requests between them.
- A component issuing a two-part DVM message must be able to issue the second part of the message without requiring a response to the first part of the message.

### <span id="page-248-0"></span>**A15.4.1 Signaling for DVM messages**

Snoop channels for DVM messages use the same transport as the other AXI channels as determined by the AXI\_Transport property. See [A2.2](#page-27-0) *[AXI transport options](#page-27-0)* for more details on transport.

DVM message requests use the snoop request channel from a Subordinate to a Manager interface. Table [A15.17](#page-248-1) shows the signals that can be included in the snoop request channel.

**Table A15.17: Snoop request channel**

<span id="page-248-1"></span>

| Name      | Width      | Source      | Presence                                                         | Description                                                 |
|-----------|------------|-------------|------------------------------------------------------------------|-------------------------------------------------------------|
| ACVALID   | 1          | Subordinate | DVM_Message_Support                                              | DVM message request valid<br>indicator.                     |
| ACREADY   | 1          | Manager     | DVM_Message_Support and<br>AXI_Transport == Ready                | DVM message request ready<br>indicator.                     |
| ACPENDING | 1          | Subordinate | DVM_Message_Support and<br>AXI_Transport == Credited             | Pending signal for the AC<br>channel.                       |
| ACCRDT    | 1          | Manager     | DVM_Message_Support and<br>AXI_Transport == Credited             | Asserted high to give one<br>DVM message request<br>credit. |
| ACADDR    | ADDR_WIDTH | Subordinate | DVM_Message_Support                                              | Used to carry the payload<br>for DVM message requests.      |
| ACVMIDEXT | 4          | Subordinate | DVM_Message_Support and<br>(DVM_v8.1 or DVM_v8.4 or<br>DVM_v9.2) | Extension to support 16-bit<br>VMID in DVM messages.        |
| ACTRACE   | 1          | Subordinate | DVM_Message_Support and<br>Trace_Signals                         | Trace signal for the AC<br>channel.                         |

<span id="page-248-5"></span><span id="page-248-4"></span><span id="page-248-3"></span><span id="page-248-2"></span>The response to a DVM request is transported on the snoop response channel from a Manager to a Subordinate interface. Table [A15.18](#page-248-2) shows the signals that can be included in the snoop response channel.

**Table A15.18: Snoop response channel**

| Name      | Width | Source      | Presence                                             | Description                                                  |
|-----------|-------|-------------|------------------------------------------------------|--------------------------------------------------------------|
| CRVALID   | 1     | Manager     | DVM_Message_Support                                  | DVM message response<br>valid indicator.                     |
| CRREADY   | 1     | Subordinate | DVM_Message_Support and<br>AXI_Transport == Ready    | DVM message response<br>ready indicator.                     |
| CRPENDING | 1     | Manager     | DVM_Message_Support and<br>AXI_Transport == Credited | Pending signal for the CR<br>channel.                        |
| CRCRDT    | 1     | Subordinate | DVM_Message_Support and<br>AXI_Transport == Credited | Asserted high to give one<br>DVM message response<br>credit. |
| CRTRACE   | 1     | Manager     | DVM_Message_Support and<br>Trace_Signals             | Trace signal for the CR<br>channel.                          |

<span id="page-248-6"></span>A DVM response acknowledges that the request has been received but does not indicate the success or failure of a

DVM message. Reordering is not supported on the AC or CR channels, so responses are returned in the same order as the AC requests were issued.

The ACTRACE and CRTRACE signals act the same as trace signals on other channels, see [A12.3](#page-198-0) *[Trace signals](#page-198-0)* for more information.

### <span id="page-249-0"></span>**A15.4.2 Snoop channels using Valid-Ready transport**

When using a Valid-Ready transport, the following rules apply:

- ACVALID must only be asserted by a Subordinate when there is valid address and control information.
- When asserted, ACVALID must remain asserted until the rising clock edge after the Manager asserts the ACREADY signal.
- CRVALID is asserted to indicate that the Manager has acknowledged the DVM message.
- When asserted, CRVALID must remain asserted until the rising clock edge after the Subordinate asserts the CRREADY signal.

The rules for dependencies between the snoop request and response channels are listed below and illustrated in [Figure](#page-249-3) [A15.2.](#page-249-3)

- The Subordinate must not wait for the Manager to assert ACREADY before asserting ACVALID.
- The Manager can wait for ACVALID to be asserted before it asserts ACREADY.
- The Manager can assert ACREADY before ACVALID is asserted.
- The Manager must wait for both ACVALID and ACREADY to be asserted before it asserts CRVALID to indicate that a valid response is available.
- The Manager must not wait for the Subordinate to assert CRREADY before asserting CRVALID.
- The Subordinate can wait for CRVALID to be asserted before it asserts CRREADY.
- <span id="page-249-3"></span>• The Subordinate can assert CRREADY before CRVALID is asserted.

![](_page_249_Figure_17.jpeg)

**Figure A15.2: Snoop transaction handshake dependencies**

### <span id="page-249-1"></span>**A15.4.3 Snoop channels using credited transport**

When using credited transport, the rules of [A2.4](#page-32-0) *[Credited transport](#page-32-0)* and [A2.4.4](#page-37-0) *[Transfer-level clock gating](#page-37-0)* apply to the snoop channels. In addition:

- The Manager must wait for a DVM message request before sending a DVM message response.
- Multiple Resource Planes and shared credits are not supported on the snoop channels.

### <span id="page-249-2"></span>**A15.4.4 Address widths in DVM messages**

The property ADDR\_WIDTH is used to specify the width of ARADDR, AWADDR, and ACADDR. This sets the physical address width used by an interface.

<span id="page-250-1"></span>The ACADDR signal is also used to transport the Virtual Address (VA), so the required VA width also sets a minimum constraint on ADDR\_WIDTH. Table [A15.19](#page-250-1) shows some common VA widths and the minimum ADDR\_WIDTH required.

**Table A15.19: Common VA widths and minimum ADDR\_WIDTH**

| VA width | Minimum<br>ADDR_WIDTH |
|----------|-----------------------|
| 32       | 32                    |
| 41       | 40                    |
| 49       | 44                    |
| 53       | 48                    |
| 57       | 48                    |

VA widths greater than 57-bits are not supported.

If the PA width exceeds the VA width, then virtual address operations might receive additional address information in a DVM message. In this case, any additional address information must be ignored and operations performed using only the supported address bits.

If a component supports a larger VA width than its PA width, the component must take appropriate action regarding the additional physical address bits. See [A3.1.5](#page-48-0) *[Transfer address](#page-48-0)* for more details on mismatched address widths.

### <span id="page-250-2"></span><span id="page-250-0"></span>**A15.4.5 Mapping message fields to signals**

The fields in DVM messages are transported using bits of the ACADDR and ACVMIDEXT signals.

There are different mappings for each message type, shown in the tables below. The bit position allocation might appear irregular but is used to ease the translation between implementations with different address widths.

For Hint messages, the Completion (0b0) and DVMType (0b110) fields are at ACADDR[15] and ACADDR[14:12] respectively, other mappings are IMPLEMENTATION DEFINED.

The mappings for TLB Invalidate messages are shown in Table [A15.20.](#page-251-0)

**Table A15.20: Field mappings for TLB Invalidate messages**

<span id="page-251-0"></span>

| 0b0<br>0b0<br>0b0<br>0b0<br>0b0<br>ACADDR[51]<br>0b0<br>0b0<br>0b0<br>0b0<br>0b0<br>ACADDR[50]<br>0b0<br>0b0<br>0b0<br>0b0<br>0b0<br>ACADDR[49]<br>0b0<br>0b0<br>0b0<br>0b0<br>0b0<br>ACADDR[48]<br>0b0<br>0b0<br>ACADDR[47]<br>VA[56]<br>VA[52]<br>VA[52]<br>0b0<br>0b0<br>ACADDR[46]<br>VA[55]<br>VA[51]<br>VA[51]<br>0b0<br>0b0<br>ACADDR[45]<br>VA[54]<br>VA[50]<br>VA[50]<br>0b0<br>0b0<br>ACADDR[44]<br>VA[53]<br>VA[49]<br>VA[49]<br>0b0<br>ACADDR[43]<br>VMID[15]<br>VA[48]<br>VA[44]<br>VA[44]<br>0b0<br>ACADDR[42]<br>VMID[14]<br>VA[47]<br>VA[43]<br>VA[43]<br>0b0<br>ACADDR[41]<br>VMID[13]<br>VA[46]<br>VA[42]<br>VA[42]<br>0b0<br>ACADDR[40]<br>VMID[12]<br>VA[45]<br>VA[41]<br>VA[41]<br>0b0<br>ACADDR[39]<br>ASID[15]<br>ASID[15]<br>VA[39]<br>VA[39]<br>0b0<br>ACADDR[38]<br>ASID[14]<br>ASID[14]<br>VA[38]<br>VA[38]<br>0b0<br>ACADDR[37]<br>ASID[13]<br>ASID[13]<br>VA[37]<br>VA[37]<br>0b0<br>ACADDR[36]<br>ASID[12]<br>ASID[12]<br>VA[36]<br>VA[36]<br>0b0<br>ACADDR[35]<br>ASID[11]<br>ASID[11]<br>VA[35]<br>VA[35]<br>0b0<br>ACADDR[34]<br>ASID[10]<br>ASID[10]<br>VA[34]<br>VA[34]<br>0b0<br>ACADDR[33]<br>ASID[9]<br>ASID[9]<br>VA[33]<br>VA[33]<br>0b0<br>ACADDR[32]<br>ASID[8]<br>ASID[8]<br>VA[32]<br>VA[32]<br>0b0<br>ACADDR[31]<br>VMID[7]<br>VMID[7]<br>VA[31]<br>VA[31]<br>0b0<br>ACADDR[30]<br>VMID[6]<br>VMID[6]<br>VA[30]<br>VA[30]<br>0b0<br>ACADDR[29]<br>VMID[5]<br>VMID[5]<br>VA[29]<br>VA[29]<br>0b0<br>ACADDR[28]<br>VMID[4]<br>VMID[4]<br>VA[28]<br>VA[28]<br>0b0<br>ACADDR[27]<br>VMID[3]<br>VMID[3]<br>VA[27]<br>VA[27] | GPT TLBI<br>GPT TLBI<br>1st part<br>2nd part |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[51]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[50]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[49]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[48]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[47]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[46]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[45]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[44]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[43]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[42]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[41]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[40]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[39]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[38]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[37]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[36]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[35]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[34]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[33]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[32]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[31]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[30]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[29]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[28]                                       |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | PA[27]                                       |
| 0b0<br>ACADDR[26]<br>VMID[2]<br>VMID[2]<br>VA[26]<br>VA[26]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | PA[26]                                       |
| 0b0<br>ACADDR[25]<br>VMID[1]<br>VMID[1]<br>VA[25]<br>VA[25]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | PA[25]                                       |
| 0b0<br>ACADDR[24]<br>VMID[0]<br>VMID[0]<br>VA[24]<br>VA[24]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | PA[24]                                       |
| 0b0<br>ACADDR[23]<br>ASID[7]<br>ASID[7]<br>VA[23]<br>VA[23]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | PA[23]                                       |
| 0b0<br>ACADDR[22]<br>ASID[6]<br>ASID[6]<br>VA[22]<br>VA[22]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | PA[22]                                       |
| 0b0<br>ACADDR[21]<br>ASID[5]<br>ASID[5]<br>VA[21]<br>VA[21]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | PA[21]                                       |

Table A15.20 – *Continued from previous page*

| Signal       | TLBI 1-part         | TLBI 1st of<br>2-part | TLBI 2nd<br>part by VA<br>or IPA | TLBI 2nd<br>part by range | GPT TLBI<br>1st part | GPT TLBI<br>2nd part |
|--------------|---------------------|-----------------------|----------------------------------|---------------------------|----------------------|----------------------|
| ACADDR[20]   | ASID[4]             | ASID[4]               | VA[20]                           | VA[20]                    | 0b0                  | PA[20]               |
| ACADDR[19]   | ASID[3]             | ASID[3]               | VA[19]                           | VA[19]                    | 0b0                  | PA[19]               |
| ACADDR[18]   | ASID[2]             | ASID[2]               | VA[18]                           | VA[18]                    | 0b0                  | PA[18]               |
| ACADDR[17]   | ASID[1]             | ASID[1]               | VA[17]                           | VA[17]                    | 0b0                  | PA[17]               |
| ACADDR[16]   | ASID[0]             | ASID[0]               | VA[16]                           | VA[16]                    | 0b0                  | PA[16]               |
| ACADDR[15]   | 0b0<br>(Completion) | 0b0<br>(Completion)   | VA[15]                           | VA[15]                    | 0b0<br>(Completion)  | PA[15]               |
| ACADDR[14]   | 0b0<br>(DVMType[2]) | 0b0<br>(DVMType[2])   | VA[14]                           | VA[14]                    | 0b0<br>(DVMType[2])  | PA[14]               |
| ACADDR[13]   | 0b0<br>(DVMType[1]) | 0b0<br>(DVMType[1])   | VA[13]                           | VA[13]                    | 0b0<br>(DVMType[1])  | PA[13]               |
| ACADDR[12]   | 0b0<br>(DVMType[0]) | 0b0<br>(DVMType[0])   | VA[12]                           | VA[12]                    | 0b0<br>(DVMType[0])  | PA[12]               |
| ACADDR[11]   | Exception[1]        | Exception[1]          | TG[1]                            | TG[1]                     | Exception[1]         | IS[3]                |
| ACADDR[10]   | Exception[0]        | Exception[0]          | TG[0]                            | TG[0]                     | Exception[0]         | IS[2]                |
| ACADDR[9]    | Security[1]         | Security[1]           | TTL[1]                           | TTL[1]                    | Security[1]          | IS[1]                |
| ACADDR[8]    | Security[0]         | Security[0]           | TTL[0]                           | TTL[0]                    | Security[0]          | IS[0]                |
| ACADDR[7]    | 0b0 (Range)         | Range                 | 0b0                              | Scale[1]                  | Range                | 0b0                  |
| ACADDR[6]    | VMIDV               | VMIDV                 | 0b0                              | Scale[0]                  | 0b0<br>(VMIDV)       | 0b0                  |
| ACADDR[5]    | ASIDV               | ASIDV                 | 0b0                              | Num[4]                    | 0b0 (ASIDV)          | 0b0                  |
| ACADDR[4]    | 0b0                 | Leaf                  | 0b0                              | Num[3]                    | Leaf                 | 0b0                  |
| ACADDR[3]    | Stage[1]            | Stage[1]              | VA[40]                           | VA[40]                    | Stage[1]             | 0b0                  |
| ACADDR[2]    | Stage[0]            | Stage[0]              | 0b0                              | Num[2]                    | Stage[0]             | 0b0                  |
| ACADDR[1]    | 0b0                 | 0b0                   | 0b0                              | Num[1]                    | 0b0                  | 0b0                  |
| ACADDR[0]    | 0b0 (Addr)          | 0b1 (Addr)            | 0b0                              | Num[0]                    | Addr                 | 0b0                  |
| ACVMIDEXT[3] | VMID[11]            | VMID[11]              | VMID[15]                         | VMID[15]                  | 0b0                  | 0b0                  |
| ACVMIDEXT[2] | VMID[10]            | VMID[10]              | VMID[14]                         | VMID[14]                  | 0b0                  | 0b0                  |
| ACVMIDEXT[1] | VMID[9]             | VMID[9]               | VMID[13]                         | VMID[13]                  | 0b0                  | 0b0                  |
| ACVMIDEXT[0] | VMID[8]             | VMID[8]               | VMID[12]                         | VMID[12]                  | 0b0                  | 0b0                  |

<span id="page-253-0"></span>The mappings for Branch Predictor Invalidate and Sync messages are shown in Table [A15.21.](#page-253-0)

**Table A15.21: Field mappings for BPI and Sync messages**

| 0b0<br>0b0<br>0b0<br>ACADDR[51]<br>0b0<br>0b0<br>0b0<br>ACADDR[50]<br>0b0<br>0b0<br>0b0<br>ACADDR[49]<br>0b0<br>0b0<br>0b0<br>ACADDR[48]<br>0b0<br>ACADDR[47]<br>VA[56]<br>VA[52]<br>0b0<br>ACADDR[46]<br>VA[55]<br>VA[51]<br>0b0<br>ACADDR[45]<br>VA[54]<br>VA[50]<br>0b0<br>ACADDR[44]<br>VA[53]<br>VA[49]<br>0b0<br>ACADDR[43]<br>VA[48]<br>VA[44]<br>0b0<br>ACADDR[42]<br>VA[47]<br>VA[43]<br>0b0<br>ACADDR[41]<br>VA[46]<br>VA[42]<br>0b0<br>ACADDR[40]<br>VA[45]<br>VA[41]<br>0b0<br>0b0<br>ACADDR[39]<br>VA[39]<br>0b0<br>0b0<br>ACADDR[38]<br>VA[38]<br>0b0<br>0b0<br>ACADDR[37]<br>VA[37]<br>0b0<br>0b0<br>ACADDR[36]<br>VA[36]<br>0b0<br>0b0<br>ACADDR[35]<br>VA[35]<br>0b0<br>0b0<br>ACADDR[34]<br>VA[34]<br>0b0<br>0b0<br>ACADDR[33]<br>VA[33]<br>0b0<br>0b0<br>ACADDR[32]<br>VA[32]<br>0b0<br>0b0<br>ACADDR[31]<br>VA[31]<br>0b0<br>0b0<br>ACADDR[30]<br>VA[30]<br>0b0<br>0b0<br>ACADDR[29]<br>VA[29]<br>0b0<br>0b0<br>ACADDR[28]<br>VA[28]<br>0b0<br>0b0<br>ACADDR[27]<br>VA[27]<br>0b0<br>0b0<br>ACADDR[26]<br>VA[26]<br>0b0<br>0b0<br>ACADDR[25]<br>VA[25]<br>0b0<br>0b0<br>ACADDR[24]<br>VA[24]<br>0b0<br>0b0<br>ACADDR[23]<br>VA[23]<br>0b0<br>0b0<br>ACADDR[22]<br>VA[22] | Signal     | BPI all or Sync | BPI by VA 1st part | BPI by VA 2nd part |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|-----------------|--------------------|--------------------|
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |            |                 |                    |                    |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | ACADDR[21] | 0b0             | 0b0                | VA[21]             |

Table A15.21 – *Continued from previous page*

| Signal       | BPI all or Sync    | BPI by VA 1st part | BPI by VA 2nd part |
|--------------|--------------------|--------------------|--------------------|
| ACADDR[20]   | 0b0                | 0b0                | VA[20]             |
| ACADDR[19]   | 0b0                | 0b0                | VA[19]             |
| ACADDR[18]   | 0b0                | 0b0                | VA[18]             |
| ACADDR[17]   | 0b0                | 0b0                | VA[17]             |
| ACADDR[16]   | 0b0                | 0b0                | VA[16]             |
| ACADDR[15]   | Completion         | 0b0 (Completion)   | VA[15]             |
| ACADDR[14]   | DVMType[2]         | 0b0 (DVMType[2])   | VA[14]             |
| ACADDR[13]   | DVMType[1]         | 0b0 (DVMType[1])   | VA[13]             |
| ACADDR[12]   | DVMType[0]         | 0b1 (DVMType[0])   | VA[12]             |
| ACADDR[11]   | 0b0 (Exception[1]) | 0b0 (Exception[1]) | VA[11]             |
| ACADDR[10]   | 0b0 (Exception[0]) | 0b0 (Exception[0]) | VA[10]             |
| ACADDR[9]    | 0b0 (Security[1])  | 0b0 (Security[1])  | VA[9]              |
| ACADDR[8]    | 0b0 (Security[0])  | 0b0 (Security[0])  | VA[8]              |
| ACADDR[7]    | 0b0 (Range)        | 0b0 (Range)        | VA[7]              |
| ACADDR[6]    | 0b0 (VMIDV)        | 0b0 (VMIDV)        | VA[6]              |
| ACADDR[5]    | 0b0 (ASIDV)        | 0b0 (ASIDV)        | VA[5]              |
| ACADDR[4]    | 0b0 (Leaf)         | 0b0 (Leaf)         | VA[4]              |
| ACADDR[3]    | 0b0 (Stage[1])     | 0b0 (Stage[1])     | VA[40]             |
| ACADDR[2]    | 0b0 (Stage[0])     | 0b0 (Stage[0])     | 0b0                |
| ACADDR[1]    | 0b0                | 0b0                | 0b0                |
| ACADDR[0]    | 0b0 (Addr)         | 0b1 (Addr)         | 0b0                |
| ACVMIDEXT[3] | 0b0                | 0b0                | 0b0                |
| ACVMIDEXT[2] | 0b0                | 0b0                | 0b0                |
| ACVMIDEXT[1] | 0b0                | 0b0                | 0b0                |
| ACVMIDEXT[0] | 0b0                | 0b0                | 0b0                |
|              |                    |                    |                    |

The mappings for Instruction Cache Invalidation messages are shown in Table [A15.22.](#page-255-0)

**Table A15.22: Field mappings for VICI and PICI messages**

<span id="page-255-0"></span>

| Signal     | VICI all | VICI by VA 1st<br>part | VICI by VA 2nd<br>part | PICI 1st part | PICI 2nd part |
|------------|----------|------------------------|------------------------|---------------|---------------|
| ACADDR[51] | 0b0      | 0b0                    | 0b0                    | 0b0           | PA[51]        |
| ACADDR[50] | 0b0      | 0b0                    | 0b0                    | 0b0           | PA[50]        |
| ACADDR[49] | 0b0      | 0b0                    | 0b0                    | 0b0           | PA[49]        |
| ACADDR[48] | 0b0      | 0b0                    | 0b0                    | 0b0           | PA[48]        |
| ACADDR[47] | 0b0      | VA[56]                 | VA[52]                 | 0b0           | PA[47]        |
| ACADDR[46] | 0b0      | VA[55]                 | VA[51]                 | 0b0           | PA[46]        |
| ACADDR[45] | 0b0      | VA[54]                 | VA[50]                 | 0b0           | PA[45]        |
| ACADDR[44] | 0b0      | VA[53]                 | VA[49]                 | 0b0           | PA[44]        |
| ACADDR[43] | VMID[15] | VA[48]                 | VA[44]                 | 0b0           | PA[43]        |
| ACADDR[42] | VMID[14] | VA[47]                 | VA[43]                 | 0b0           | PA[42]        |
| ACADDR[41] | VMID[13] | VA[46]                 | VA[42]                 | 0b0           | PA[41]        |
| ACADDR[40] | VMID[12] | VA[45]                 | VA[41]                 | 0b0           | PA[40]        |
| ACADDR[39] | ASID[15] | ASID[15]               | VA[39]                 | 0b0           | PA[39]        |
| ACADDR[38] | ASID[14] | ASID[14]               | VA[38]                 | 0b0           | PA[38]        |
| ACADDR[37] | ASID[13] | ASID[13]               | VA[37]                 | 0b0           | PA[37]        |
| ACADDR[36] | ASID[12] | ASID[12]               | VA[36]                 | 0b0           | PA[36]        |
| ACADDR[35] | ASID[11] | ASID[11]               | VA[35]                 | 0b0           | PA[35]        |
| ACADDR[34] | ASID[10] | ASID[10]               | VA[34]                 | 0b0           | PA[34]        |
| ACADDR[33] | ASID[9]  | ASID[9]                | VA[33]                 | 0b0           | PA[33]        |
| ACADDR[32] | ASID[8]  | ASID[8]                | VA[32]                 | 0b0           | PA[32]        |
| ACADDR[31] | VMID[7]  | VMID[7]                | VA[31]                 | VI[27]        | PA[31]        |
| ACADDR[30] | VMID[6]  | VMID[6]                | VA[30]                 | VI[26]        | PA[30]        |
| ACADDR[29] | VMID[5]  | VMID[5]                | VA[29]                 | VI[25]        | PA[29]        |
| ACADDR[28] | VMID[4]  | VMID[4]                | VA[28]                 | VI[24]        | PA[28]        |
| ACADDR[27] | VMID[3]  | VMID[3]                | VA[27]                 | VI[23]        | PA[27]        |
| ACADDR[26] | VMID[2]  | VMID[2]                | VA[26]                 | VI[22]        | PA[26]        |
| ACADDR[25] | VMID[1]  | VMID[1]                | VA[25]                 | VI[21]        | PA[25]        |
| ACADDR[24] | VMID[0]  | VMID[0]                | VA[24]                 | VI[20]        | PA[24]        |
| ACADDR[23] | ASID[7]  | ASID[7]                | VA[23]                 | VI[19]        | PA[23]        |
| ACADDR[22] | ASID[6]  | ASID[6]                | VA[22]                 | VI[18]        | PA[22]        |
|            |          |                        |                        |               |               |

Table A15.22 – *Continued from previous page*

<span id="page-256-0"></span>

| ACADDR[21]<br>ASID[5]<br>ASID[5]<br>VA[21]<br>VI[17]<br>PA[21]<br>ACADDR[20]<br>ASID[4]<br>ASID[4]<br>VA[20]<br>VI[16]<br>PA[20]<br>ACADDR[19]<br>ASID[3]<br>ASID[3]<br>VA[19]<br>VI[15]<br>PA[19]<br>ACADDR[18]<br>ASID[2]<br>ASID[2]<br>VA[18]<br>VI[14]<br>PA[18]<br>ACADDR[17]<br>ASID[1]<br>ASID[1]<br>VA[17]<br>VI[13]<br>PA[17]<br>ACADDR[16]<br>ASID[0]<br>ASID[0]<br>VA[16]<br>VI[12]<br>PA[16]<br>0b0<br>0b0<br>0b0<br>ACADDR[15]<br>VA[15]<br>PA[15]<br>(Completion)<br>(Completion)<br>(Completion)<br>0b0<br>0b0<br>0b0<br>ACADDR[14]<br>VA[14]<br>PA[14]<br>(DVMType[2])<br>(DVMType[2])<br>(DVMType[2])<br>0b1<br>0b1<br>0b1<br>ACADDR[13]<br>VA[13]<br>PA[13]<br>(DVMType[1])<br>(DVMType[1])<br>(DVMType[1])<br>0b1<br>0b1<br>0b0<br>ACADDR[12]<br>VA[12]<br>PA[12]<br>(DVMType[0])<br>(DVMType[0])<br>(DVMType[0])<br>0b0<br>ACADDR[11]<br>Exception[1]<br>Exception[1]<br>VA[11]<br>PA[11]<br>(Exception[1])<br>0b0<br>ACADDR[10]<br>Exception[0]<br>Exception[0]<br>VA[10]<br>PA[10]<br>(Exception[0])<br>ACADDR[9]<br>Security[1]<br>Security[1]<br>VA[9]<br>Security[1]<br>PA[9]<br>ACADDR[8]<br>Security[0]<br>Security[0]<br>VA[8]<br>Security[0]<br>PA[8]<br>0b0 (Range)<br>0b0 (Range)<br>0b0 (Range)<br>ACADDR[7]<br>VA[7]<br>PA[7]<br>ACADDR[6]<br>VMIDV<br>VMIDV<br>VA[6]<br>VIV[1]<br>PA[6]<br>ACADDR[5]<br>ASIDV<br>ASIDV<br>VA[5]<br>VIV[0]<br>PA[5]<br>0b0 (Leaf)<br>0b0 (Leaf)<br>0b0<br>ACADDR[4]<br>VA[4]<br>PA[4]<br>0b0 (Stage[1])<br>0b0 (Stage[1])<br>0b0<br>0b0<br>ACADDR[3]<br>VA[40] | Signal | VICI all | VICI by VA 1st<br>part | VICI by VA 2nd<br>part | PICI 1st part | PICI 2nd part |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|----------|------------------------|------------------------|---------------|---------------|
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |        |          |                        |                        |               |               |
| 0b0 (Stage[0])<br>0b0 (Stage[0])<br>0b0<br>0b0<br>0b0<br>ACADDR[2]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |        |          |                        |                        |               |               |
| 0b0<br>0b0<br>0b0<br>0b0<br>0b0<br>ACADDR[1]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |        |          |                        |                        |               |               |
| 0b0 (Addr)<br>0b1 (Addr)<br>0b0<br>0b0<br>ACADDR[0]<br>Addr                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |        |          |                        |                        |               |               |
| 0b0<br>0b0<br>ACVMIDEXT[3]<br>VMID[11]<br>VMID[11]<br>VMID[15]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |        |          |                        |                        |               |               |
| 0b0<br>0b0<br>ACVMIDEXT[2]<br>VMID[10]<br>VMID[10]<br>VMID[14]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |        |          |                        |                        |               |               |
| 0b0<br>0b0<br>ACVMIDEXT[1]<br>VMID[9]<br>VMID[9]<br>VMID[13]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |        |          |                        |                        |               |               |
| 0b0<br>0b0<br>ACVMIDEXT[0]<br>VMID[8]<br>VMID[8]<br>VMID[12]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |        |          |                        |                        |               |               |

# <span id="page-257-1"></span><span id="page-257-0"></span>**A15.5 DVM Sync and Complete**

A DVM Sync message is used when the requester needs to know when all previous invalidations are complete.

A DVM Complete request is sent when a component has received a DVM Sync message and all preceding invalidation operations are complete. The following rules apply in determining when an operation is complete:

#### TLB Invalidate

Complete when a Manager can no longer use an invalidated translation and all previous transactions that could have used an invalidated translation are complete.

#### Branch Predictor Invalidate

Complete when cached copies of predicted instruction fetches have been invalidated and can no longer be accessed by the associated Manager. The invalidated cached copies might be from any virtual address or from a specified virtual address.

#### Instruction Cache Invalidate

Complete when cached instructions have been invalidated and can no longer be accessed by the associated Manager.

The synchronization flow between an interconnect and one receiving Manager is shown in [Figure](#page-257-2) [A15.3.](#page-257-2)

The process is:

- 1. The Manager acknowledges receipt of the DVM Sync message using the snoop response (CR) channel. This response must not be dependent on the forward progress of any transactions on the AR or AW channels.
- 2. The Manager must issue a DVM Complete request on the AR channel when it has completed all the necessary actions. This must be after the handshake of the associated DVM Sync on the snoop request channel of the same Manager. The Manager must send a DVM Complete in a timely manner, even if it continues to receive more DVM invalidation operations and more DVM Sync messages.
- <span id="page-257-2"></span>3. The interconnect component responds to the DVM Complete request using the read data (R) channel of the component that issued the DVM Complete. Read data is not valid in this response.

![](_page_257_Figure_15.jpeg)

**Figure A15.3: DVM Synchronization flow**

Every DVM Sync message must have one corresponding DVM Complete request.

A DVM Complete request can only be sent if there is a corresponding DVM Sync message.

<span id="page-258-0"></span>A DVM Complete request is signaled on the AR channel, Table [A15.23](#page-258-0) shows the constraints on other AR channel signals if they are present.

**Table A15.23: DVM Complete request constraints**

| Signal     | Constraint                                                                                                  |
|------------|-------------------------------------------------------------------------------------------------------------|
| ARSNOOP    | Must be 0b1110.                                                                                             |
| ARADDR     | Must be zero.                                                                                               |
| ARID       | Must be different from that of any outstanding, non-DVM<br>Complete transaction on the read channels.       |
| ARBURST    | Must be INCR (0b01).                                                                                        |
| ARLEN      | Must be 1 transfer (0x00).                                                                                  |
| ARSIZE     | Must be equal to the data channel width or<br>Max_Transaction_Bytes if that is smaller than the data width. |
| ARDOMAIN   | Must be Shareable (0b01 or 0b10).                                                                           |
| ARCACHE    | Must be Modifiable, Non-cacheable (0b0010).                                                                 |
| ARCHUNKEN  | Must be 0b0.                                                                                                |
| ARMMUVALID | Must be 0b0. If not present, ARMMUVALID is assumed to be<br>0b0 for a DVM Complete request.                 |
| ARMMUATST  | Must be 0b0.                                                                                                |
| ARMMUFLOW  | Must be 0b00.                                                                                               |
| ARTAGOP    | Must be 0b00.                                                                                               |
| ARLOCK     | Must be 0b0.                                                                                                |

When using credited transport, a DVM Complete message can use any value for ARRP, but all DVM Complete messages on an interface must use the same RP.

# <span id="page-259-0"></span>**A15.6 Coherency Connection signaling**

DVM message requests are transferred from a Subordinate to a Manager interface, which is the opposite direction to other requests. A Manager which is idle might be powered down and unable to accept any DVM requests. Coherency Connection signaling can be used to enable a Manager to control whether it receives DVM message requests.

The Coherency\_Connection\_Signals property is used to indicate whether a component supports the Coherency Connection signals.

**Table A15.24: Coherency\_Connection\_Signals property**

| Coherency_Connection_Signals | Default | Description                                      |
|------------------------------|---------|--------------------------------------------------|
| True                         |         | Coherency Connection signaling is supported.     |
| False                        | Y       | Coherency Connection signaling is not supported. |

When Coherency\_Connection\_Signals is True, the following signals are included on an interface.

**Table A15.25: Coherency Connection signals**

<span id="page-259-3"></span><span id="page-259-2"></span>

| Name     | Width | Default | Description                                                                                                                           |
|----------|-------|---------|---------------------------------------------------------------------------------------------------------------------------------------|
| SYSCOREQ | 1     | -       | Output from a Manager, asserted HIGH to request<br>that it receives DVM messages on the AC channel.                                   |
| SYSCOACK | 1     | -       | Output from a Subordinate, asserted HIGH to<br>acknowledge that the attached Manager might<br>receive DVM messages on the AC channel. |

Coherency Connection signals do not have default values, so connected interfaces must both support or not support Coherency Connection signaling.

The Coherency Connection signals use a four-phase scheme which can safely cross clock domains.

Disconnecting from DVM messages is typically used before entering a low-power state in which DVM requests cannot be processed.

### <span id="page-259-4"></span><span id="page-259-1"></span>**A15.6.1 Coherency Connection Handshake**

SYSCOREQ and SYSCOACK must be deasserted when ARESETn is asserted. When not in reset, the following requests are permitted:

- A Manager requests to receive DVM messages by asserting SYSCOREQ HIGH. The interconnect indicates that DVM messages are enabled by asserting SYSCOACK HIGH.
- The Manager requests to stop receiving DVM messages by deasserting SYSCOREQ LOW. The interconnect indicates that DVM messages is disabled by deasserting SYSCOACK LOW.

The handshake timing is shown in [Figure](#page-260-0) [A15.4.](#page-260-0)

<span id="page-260-0"></span>![](_page_260_Figure_1.jpeg)

**Figure A15.4: Coherency Connection handshake timing**

The connection signaling obeys the four-phase handshake rules:

- A Manager can only change SYSCOREQ when SYSCOACK is at the same level.
- A Subordinate can only change SYSCOACK when SYSCOREQ is at the opposite level.

The rules for Managers and Subordinate components in each state are shown in Table [A15.26.](#page-260-1)

**Table A15.26: Coherency Connection signaling states**

<span id="page-260-1"></span>

| State    | SYSCOREQ | SYSCOACK | Rules                                                                                                                                                                                                                                                                                                                                                                                                                   |
|----------|----------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Disabled | 0        | 0        | Manager:<br>• Must not fetch and use DVM-managed translation table<br>data to perform translations.<br>• Asserts SYSCOREQ if it needs to perform DVM-managed<br>translations.<br>Subordinate:<br>• Must not issue any DVM message requests.<br>• Must not issue any DVM Sync requests, these are assumed<br>to complete immediately.                                                                                    |
| Connect  | 1        | 0        | Manager:<br>• Must not fetch and use DVM-managed translation table<br>data to perform translations.<br>• Must be able to receive and respond to DVM message<br>requests.<br>• Waiting for SYSCOACK to be asserted before using<br>DVM-managed translations.<br>Subordinate:<br>• Asserts SYSCOACK when it has enabled DVM messages<br>to the attached Manager.                                                          |
| Enabled  | 1        | 1        | Manager:<br>• Can fetch and use DVM-managed translation table data.<br>• Must be able to receive and respond to DVM message<br>requests.<br>• Deasserts SYSCOREQ if it has finished using<br>DVM-managed translation table data and wants to enter a<br>low power state. Any transaction using previously fetched<br>data must have been completed.<br>Subordinate:<br>• Can send DVM messages to the attached Manager. |

Table A15.26 – *Continued from previous page*

| State      | SYSCOREQ | SYSCOACK | Rules                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
|------------|----------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Disconnect | 0        | 1        | Manager:<br>• Must not fetch or use any DVM-managed translation table<br>data.<br>• Must be able to receive and respond to DVM message<br>requests.<br>• Waiting for SYSCOACK to be deasserted before disabling<br>DVM-managed logic.<br>Subordinate:<br>• Must wait for all outstanding DVM messages to receive a<br>response before deasserting SYSCOACK.<br>• Must stop issuing DVM messages in a timely manner.<br>• Must issue the second part of a 2-part DVM message if the<br>first part has already been issued. |

Note that a Subordinate is not permitted to send DVM messages in the Connect state, but a Manager must be able to receive DVM messages in the Connect state. This is because there might be a race between the assertion of SYSCOACK and ACVALID.

If an interconnect has sent a DVM Sync message that requires a DVM Complete message on the AR channel, then the interconnect is permitted to deassert SYSCOACK before the DVM Complete request is received. The Manager is required to send the DVM Complete request on the AR channel, even when DVM messages are disabled.

Transitions on the Coherency Connection signals might rely on AWAKEUP being asserted, see [A14.1.2](#page-223-0) *[AWAKEUP and Coherency Connection signaling](#page-223-0)* for details.

# <span id="page-262-0"></span>**A15.7 Snoop channels credit control**

When using credited transport, the snoop channels can include control signals to determine when channel receivers can give credits. This can be used to clock or power gate snoop channels when they are idle.

The following rules apply:

- Credit control is independent of the other channels on the interface. For example, the DVM channels can be in RUN when other channels are in STOP.
- All of the rules in [A14.2](#page-224-0) *[Interface gating with credited transport](#page-224-0)* apply to the DVM credit control signals, but the Manager and Subordinate terms are swapped.
- A DVM transaction is considered to be complete when the response is received on CR. For a DVM Sync, the DVM channels can be stopped once the CR response is received. The Manager must start the main channels to send a DVM Complete request on the AR channel.
- Credit control is independent of the coherency connection state. For example, DVM messages might be enabled by setting SYSCOREQ and SYSCOACK HIGH, but the AC and CR channels remain in STOP until a DVM message needs to be sent.

<span id="page-262-1"></span>Table [A15.27](#page-262-1) shows the signals that are included when DVM\_Message\_Support is Receiver and Credit\_Control is Implicit\_Return\_Uni.

**Table A15.27: Credit control signals**

<span id="page-262-4"></span><span id="page-262-3"></span><span id="page-262-2"></span>

| Name         | Width | Default | Description                                                                                     |  |
|--------------|-------|---------|-------------------------------------------------------------------------------------------------|--|
| ACTIVATEREQD | 1     | 0b1     | Activation / deactivation request from a Subordinate for the<br>snoop channels.                 |  |
| ACTIVATEACKD | 1     | 0b1     | Activation / deactivation acknowledge from a Manager for the<br>snoop channels.                 |  |
| ASKSTOPD     | 1     | 0b0     | Asserted HIGH to indicate that the Manager wants the<br>Subordinate to stop the snoop channels. |  |

<span id="page-263-0"></span>

| Chapter A16                   |  |
|-------------------------------|--|
| Interface and data protection |  |

This chapter specifies schemes for the protection of data and interfaces using poison and parity signaling. It contains the following sections:

- [A16.1](#page-264-0) *[Data protection using Poison](#page-264-0)*
- <span id="page-263-1"></span>• [A16.2](#page-265-0) *[Parity protection for data and interface signals](#page-265-0)*

# <span id="page-264-0"></span>**A16.1 Data protection using Poison**

Poison signaling is used to indicate that a set of data bytes has been previously corrupted. Passing the Poison signaling alongside the data permits any future user of the data to be notified that the data might be corrupt. Poison signaling is supported at the granularity of 1 bit for every 64 bits of data.

**Table A16.1: Poison signals**

<span id="page-264-2"></span><span id="page-264-1"></span>

| Name                | Width                 | Default | Description                                                                                                     |
|---------------------|-----------------------|---------|-----------------------------------------------------------------------------------------------------------------|
| WPOISON,<br>RPOISON | ceil(DATA_WIDTH / 64) | -       | Asserted high to indicate that the data in this transfer<br>is corrupted. There is one bit per 64-bits of data. |

The presence of Poison signals is configured using the *Poison* property.

**Table A16.2: Poison property**

| Poison | Default | Description                        |
|--------|---------|------------------------------------|
| True   |         | Poison signaling is supported.     |
| False  | Y       | Poison signaling is not supported. |

The validity of the Poison signaling is identical to the validity of the associated data.

Poison signaling is independent of error response signaling:

- It is permitted to signal an error with no Poison violation.
- It is permitted to signal a Poison violation without signaling an error response.

A 64-bit granule is defined as an 8-byte address range that is aligned to an 8-byte boundary.

Where the transaction size, as indicated by AxSIZE, is less than 64-bits then it is permitted for the Poison bit to be different on each data transfer. In this situation the receiving component must examine all data transfers to determine if the 64-bit granule is poisoned.

Poison bits can be set for data lanes that are invalid for a transfer. For example, a 64-bit transfer on a 128-bit channel can have both Poison bits set.

For implications of Poison with MTE Tags, see [A12.2.10](#page-197-1) *[MTE and Poison](#page-197-1)*.

# <span id="page-265-0"></span>**A16.2 Parity protection for data and interface signals**

For safety-critical applications it is necessary to detect and possibly correct, transient and functional errors on individual wires within an SoC.

An error in a system component can propagate and cause multiple errors within connected components. Error detection and correction (EDC) is required to operate end-to-end, covering all logic and wires from source to destination.

One way to implement end-to-end protection, is to employ customized EDC schemes in components and implement a simple error detection scheme between components. Between these components there is no logic and single bit errors do not propagate to multi-bit errors. This section describes a parity scheme for detecting single-bit errors on the AMBA interface between components. Multi-bit errors can be detected if they occur in different parity signal groups. [Figure](#page-265-3) [A16.1](#page-265-3) shows locations where parity can be used in AMBA.

<span id="page-265-3"></span>![](_page_265_Figure_5.jpeg)

**Figure A16.1: Parity use in AMBA**

### <span id="page-265-1"></span>**A16.2.1 Configuration of parity protection**

The protection scheme employed on an interface is defined by the property *Check\_Type*.

**Table A16.3: Check\_Type property**

| Check_Type           | Default | Description                                                                                                                                                                                            |
|----------------------|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Odd_Parity_Byte_All  |         | Odd parity checking included for all signals. Each bit of<br>the parity signal generally covers up to 8 bits. However, a<br>parity bit can cover more than 8 bits if the configuration<br>requires it. |
| Odd_Parity_Byte_Data |         | Odd parity checking included for data signals with names<br>that end in DATA. Each bit of the parity signal covers<br>exactly 8 bits.                                                                  |
| False                | Y       | No checking signals on the interface.                                                                                                                                                                  |

# <span id="page-265-2"></span>**A16.2.2 Error detection behavior**

This specification is not prescriptive regarding component or system behavior when a parity error is detected. Depending on the system and affected signals, a flipped bit can have a wide range of effects. It might be harmless, cause performance issues, data corruption, security violations, or deadlock. The transaction response is independent of parity error detection.

When an error is detected, the receiver can do any of the following:

- Terminate or propagate the transaction. Termination might or might not be protocol compliant.
- Correct the parity check signal or propagate the signal in error.
- Update its memory or leave untouched. The location might be marked as poisoned.
- Signal an error response through other means, for example with an interrupt.

### <span id="page-266-1"></span><span id="page-266-0"></span>**A16.2.3 Parity check signals**

The parity check signals are listed in Table [A16.4.](#page-267-0) They have the following attributes and rules:

- Odd parity is used.
  - Odd parity means that check signals are added to groups of signals on the interface and driven such that there is always an odd number of asserted bits in that group.
- Parity signals covering data and payload are defined such that in most cases there are no more than 8 bits per group.
  - This limitation assumes that there is a maximum of 3 logic levels available in the timing budget for generating each parity bit.
- Parity signals covering critical control signals, which are likely to have a smaller timing budget available, are defined with a single odd parity bit. This single odd parity bit is the inversion of the original critical control signal.
- Check signals are synchronous to ACLK and must be driven correctly in every cycle that the signal in the *Check enable* column is HIGH, see Table [A16.4.](#page-267-0)
- Control signals have ARESETn as the Check enable.
  - If the check signal for a control signal is wider than 1 bit, check bit [n] corresponds to bit [n] in the control signal.
- Payload signals have xVALID as the Check enable.
  - If the check signal for a payload signal is wider than 1 bit:
    - \* Where a check signal covers multiple signals, parity is calculated by concatenating the signals in the order they are listed in Table [A16.4,](#page-267-0) with the first signal listed at the LSB.
    - \* Check bit [n] corresponds to bits [(8n+7):8n] in the payload, with the following exceptions:
      - · WTAGCHK[n] is the parity of {WTAGUPDATE[n],WTAG[4n+3:4n]}.
      - · RTAGCHK[n] is the parity of RTAG[4n+3:4n].
    - \* If the payload is not an integer number of bytes, the most significant bit of the check signal covers fewer than 8-bits in the most significant portion of the payload.
- Parity signals must be driven appropriately to all the bits in the associated payload, irrespective of whether those bits are actively used in the transfer. For example, all bits of WDATACHK must be driven correctly when WVALID is asserted, even if some byte lanes are not being used.
- If none of the signals covered by a check signal are present on an interface, then the check signal is omitted from the interface.

The following rules apply for CHK signals which cover multiple signals where one or more of the inputs or outputs are missing:

- If there is a missing signal output, the value is assumed to be the default for that signal. Signals with a non-zero default must be considered when calculating parity, for example BCOMP which has a default value of 0b1.
- If there is an output signal with no corresponding input, the missing input cannot be assumed to take a fixed value. Therefore, the CHK signal cannot be used reliably.
- It is recommended that input signals that are part of a CHK group are either all present or all not present.

**Table A16.4: Parity check signals**

<span id="page-267-0"></span>

| Name           | Signals covered                                | Width                                            | Check enable |
|----------------|------------------------------------------------|--------------------------------------------------|--------------|
| AWVALIDCHK     | AWVALID                                        | 1                                                | ARESETn      |
| AWREADYCHK     | AWREADY                                        | 1                                                | ARESETn      |
| AWPENDINGCHK   | AWPENDING                                      | 1                                                | ARESETn      |
| AWCRDTCHK      | AWCRDT                                         | Num_RP_AWW                                       | ARESETn      |
| AWCRDTSHCHK    | AWCRDTSH                                       | 1                                                | ARESETn      |
| AWRPCHK        | AWRP                                           | 1                                                | AWVALID      |
| AWSHAREDCRDCHK | AWSHAREDCRD                                    | 1                                                | AWVALID      |
| AWIDCHK        | AWID<br>AWIDUNQ                                | ceil((ID_W_WIDTH +<br>int(Unique_ID_Support))/8) | AWVALID      |
| AWADDRCHK      | AWADDR                                         | ceil(ADDR_WIDTH/8)                               | AWVALID      |
| AWLENCHK       | AWLEN                                          | 1                                                | AWVALID      |
| AWCTLCHK0      | AWSIZE<br>AWBURST<br>AWLOCK<br>AWPROT<br>AWNSE | 1                                                | AWVALID      |
| AWCTLCHK1      | AWREGION<br>AWCACHE<br>AWQOS                   | 1                                                | AWVALID      |
| AWCTLCHK2      | AWDOMAIN<br>AWSNOOP                            | 1                                                | AWVALID      |
| AWCTLCHK3      | AWATOP<br>AWCMO<br>AWTAGOP                     | 1                                                | AWVALID      |
| AWPASCHK       | AWPAS                                          | 1                                                | AWVALID      |
| AWINSTPRIVCHK  | AWINST<br>AWPRIV                               | 1                                                | AWVALID      |
| AWUSERCHK      | AWUSER                                         | ceil(USER_REQ_WIDTH/8)                           | AWVALID      |
| AWSTASHNIDCHK  | AWSTASHNID<br>AWSTASHNIDEN                     | 1                                                | AWVALID      |
| AWSTASHLPIDCHK | AWSTASHLPID<br>AWSTASHLPIDEN                   | 1                                                | AWVALID      |

Table A16.4 – *Continued from previous page*

| Name               | Signals covered                                                   | Width                   | Check enable |
|--------------------|-------------------------------------------------------------------|-------------------------|--------------|
| AWTRACECHK         | AWTRACE                                                           | 1                       | AWVALID      |
| AWLOOPCHK          | AWLOOP                                                            | ceil(LOOP_W_WIDTH/8)    | AWVALID      |
| AWMMUCHK           | AWMMUATST<br>AWMMUFLOW<br>AWMMUSECSID<br>AWMMUSSIDV<br>AWMMUVALID | 1                       | AWVALID      |
| AWMMUSIDCHK        | AWMMUSID                                                          | ceil(SID_WIDTH/8)       | AWVALID      |
| AWMMUSSIDCHK       | AWMMUSSID                                                         | ceil(SSID_WIDTH/8)      | AWVALID      |
| AWMMUPASUNKNOWNCHK | AWMMUPASUNKNOWN                                                   | 1                       | AWVALID      |
| AWMMUPMCHK         | AWMMUPM                                                           | 1                       | AWVALID      |
| AWPBHACHK          | AWPBHA                                                            | 1                       | AWVALID      |
| AWMECIDCHK         | AWMECID                                                           | ceil(MECID_WIDTH/8)     | AWVALID      |
| AWNSAIDCHK         | AWNSAID                                                           | 1                       | AWVALID      |
| AWMPAMCHK          | AWMPAM                                                            | 1                       | AWVALID      |
| AWSUBSYSIDCHK      | AWSUBSYSID                                                        | 1                       | AWVALID      |
| AWACTCHK           | AWACTV<br>AWACT                                                   | ceil((ACT_W_WIDTH+1)/8) | AWVALID      |
| WVALIDCHK          | WVALID                                                            | 1                       | ARESETn      |
| WREADYCHK          | WREADY                                                            | 1                       | ARESETn      |
| WPENDINGCHK        | WPENDING                                                          | 1                       | ARESETn      |
| WCRDTCHK           | WCRDT                                                             | Num_RP_AWW              | ARESETn      |
| WCRDTSHCHK         | WCRDTSH                                                           | 1                       | ARESETn      |
| WRPCHK             | WRP                                                               | 1                       | WVALID       |
| WSHAREDCRDCHK      | WSHAREDCRD                                                        | 1                       | WVALID       |
| WDATACHK           | WDATA                                                             | DATA_WIDTH/8            | WVALID       |
| WSTRBCHK           | WSTRB                                                             | ceil(DATA_WIDTH/64)     | WVALID       |
| WTAGCHK            | WTAG<br>WTAGUPDATE                                                | ceil(DATA_WIDTH/128)    | WVALID       |
| WLASTCHK           | WLAST                                                             | 1                       | WVALID       |
| WUSERCHK           | WUSER                                                             | ceil(USER_DATA_WIDTH/8) | WVALID       |
| WPOISONCHK         | WPOISON                                                           | ceil(DATA_WIDTH/512)    | WVALID       |
| WTRACECHK          | WTRACE                                                            | 1                       | WVALID       |
| BVALIDCHK          | BVALID                                                            | 1                       | ARESETn      |
| BREADYCHK          | BREADY                                                            | 1                       | ARESETn      |

Table A16.4 – *Continued from previous page*

| Name           | Signals covered                                  | Width                                            | Check enable |
|----------------|--------------------------------------------------|--------------------------------------------------|--------------|
| BPENDINGCHK    | BPENDING                                         | 1                                                | ARESETn      |
| BCRDTCHK       | BCRDT                                            | 1                                                | ARESETn      |
| BIDCHK         | BID<br>BIDUNQ                                    | ceil((ID_W_WIDTH +<br>int(Unique_ID_Support))/8) | BVALID       |
| BRESPCHK       | BRESP<br>BCOMP<br>BPERSIST<br>BTAGMATCH<br>BBUSY | 1                                                | BVALID       |
| BUSERCHK       | BUSER                                            | ceil(USER_RESP_WIDTH/8)                          | BVALID       |
| BTRACECHK      | BTRACE                                           | 1                                                | BVALID       |
| BLOOPCHK       | BLOOP                                            | ceil(LOOP_W_WIDTH/8)                             | BVALID       |
| ARVALIDCHK     | ARVALID                                          | 1                                                | ARESETn      |
| ARREADYCHK     | ARREADY                                          | 1                                                | ARESETn      |
| ARPENDINGCHK   | ARPENDING                                        | 1                                                | ARESETn      |
| ARCRDTCHK      | ARCRDT                                           | Num_RP_AR                                        | ARESETn      |
| ARCRDTSHCHK    | ARCRDTSH                                         | 1                                                | ARESETn      |
| ARRPCHK        | ARRP                                             | 1                                                | ARVALID      |
| ARSHAREDCRDCHK | ARSHAREDCRD                                      | 1                                                | ARVALID      |
| ARIDCHK        | ARID<br>ARIDUNQ                                  | ceil((ID_R_WIDTH +<br>int(Unique_ID_Support))/8) | ARVALID      |
| ARADDRCHK      | ARADDR                                           | ceil(ADDR_WIDTH/8)                               | ARVALID      |
| ARLENCHK       | ARLEN                                            | 1                                                | ARVALID      |
| ARCTLCHK0      | ARSIZE<br>ARBURST<br>ARLOCK<br>ARPROT<br>ARNSE   | 1                                                | ARVALID      |
| ARCTLCHK1      | ARREGION<br>ARCACHE<br>ARQOS                     | 1                                                | ARVALID      |
| ARCTLCHK2      | ARDOMAIN<br>ARSNOOP                              | 1                                                | ARVALID      |
| ARCTLCHK3      | ARCHUNKEN<br>ARTAGOP                             | 1                                                | ARVALID      |
| ARPASCHK       | ARPAS                                            | 1                                                | ARVALID      |
| ARINSTPRIVCHK  | ARINST<br>ARPRIV                                 | 1                                                | ARVALID      |

Table A16.4 – *Continued from previous page*

| Name               | Signals covered                                                   | Width                                            | Check enable |
|--------------------|-------------------------------------------------------------------|--------------------------------------------------|--------------|
| ARUSERCHK          | ARUSER                                                            | ceil(USER_REQ_WIDTH/8)                           | ARVALID      |
| ARTRACECHK         | ARTRACE                                                           | 1                                                | ARVALID      |
| ARLOOPCHK          | ARLOOP                                                            | ceil(LOOP_R_WIDTH/8)                             | ARVALID      |
| ARMMUCHK           | ARMMUATST<br>ARMMUFLOW<br>ARMMUSECSID<br>ARMMUSSIDV<br>ARMMUVALID | 1                                                | ARVALID      |
| ARMMUSIDCHK        | ARMMUSID                                                          | ceil(SID_WIDTH/8)                                | ARVALID      |
| ARMMUSSIDCHK       | ARMMUSSID                                                         | ceil(SSID_WIDTH/8)                               | ARVALID      |
| ARMMUPASUNKNOWNCHK | ARMMUPASUNKNOWN                                                   | 1                                                | ARVALID      |
| ARMMUPMCHK         | ARMMUPM                                                           | 1                                                | ARVALID      |
| ARNSAIDCHK         | ARNSAID                                                           | 1                                                | ARVALID      |
| ARMPAMCHK          | ARMPAM                                                            | 1                                                | ARVALID      |
| ARPBHACHK          | ARPBHA                                                            | 1                                                | ARVALID      |
| ARMECIDCHK         | ARMECID                                                           | ceil(MECID_WIDTH/8)                              | ARVALID      |
| ARSUBSYSIDCHK      | ARSUBSYSID                                                        | 1                                                | ARVALID      |
| ARACTCHK           | ARACTV<br>ARACT                                                   | ceil((ACT_R_WIDTH+1)/8)                          | ARVALID      |
| RVALIDCHK          | RVALID                                                            | 1                                                | ARESETn      |
| RREADYCHK          | RREADY                                                            | 1                                                | ARESETn      |
| RPENDINGCHK        | RPENDING                                                          | 1                                                | ARESETn      |
| RCRDTCHK           | RCRDT                                                             | 1                                                | ARESETn      |
| RIDCHK             | RID<br>RIDUNQ                                                     | ceil((ID_R_WIDTH +<br>int(Unique_ID_Support))/8) | RVALID       |
| RDATACHK           | RDATA                                                             | DATA_WIDTH/8                                     | RVALID       |
| RTAGCHK            | RTAG                                                              | ceil(DATA_WIDTH/128)                             | RVALID       |
| RRESPCHK           | RRESP<br>RBUSY                                                    | 1                                                | RVALID       |
| RLASTCHK           | RLAST                                                             | 1                                                | RVALID       |
| RCHUNKCHK          | RCHUNKV<br>RCHUNKNUM<br>RCHUNKSTRB                                | 1                                                | RVALID       |
| RUSERCHK           | RUSER                                                             | ceil((USER_DATA_WIDTH +<br>USER_RESP_WIDTH)/8)   | RVALID       |
| RPOISONCHK         | RPOISON                                                           | ceil(DATA_WIDTH/512)                             | RVALID       |

Table A16.4 – *Continued from previous page*

| Name            | Signals covered | Width                | Check enable |
|-----------------|-----------------|----------------------|--------------|
| RTRACECHK       | RTRACE          | 1                    | RVALID       |
| RLOOPCHK        | RLOOP           | ceil(LOOP_R_WIDTH/8) | RVALID       |
| ACVALIDCHK      | ACVALID         | 1                    | ARESETn      |
| ACREADYCHK      | ACREADY         | 1                    | ARESETn      |
| ACPENDINGCHK    | ACPENDING       | 1                    | ARESETn      |
| ACCRDTCHK       | ACCRDT          | 1                    | ARESETn      |
| ACADDRCHK       | ACADDR          | ceil(ADDR_WIDTH/8)   | ACVALID      |
| ACVMIDEXTCHK    | ACVMIDEXT       | 1                    | ACVALID      |
| ACTRACECHK      | ACTRACE         | 1                    | ACVALID      |
| CRVALIDCHK      | CRVALID         | 1                    | ARESETn      |
| CRREADYCHK      | CRREADY         | 1                    | ARESETn      |
| CRPENDINGCHK    | CRPENDING       | 1                    | ARESETn      |
| CRCRDTCHK       | CRCRDT          | 1                    | ARESETn      |
| CRTRACECHK      | CRTRACE         | 1                    | CRVALID      |
| VAWQOSACCEPTCHK | VAWQOSACCEPT    | 1                    | ARESETn      |
| VARQOSACCEPTCHK | VARQOSACCEPT    | 1                    | ARESETn      |
| AWAKEUPCHK      | AWAKEUP         | 1                    | ARESETn      |
| ACWAKEUPCHK     | ACWAKEUP        | 1                    | ARESETn      |
| ACTIVATEREQCHK  | ACTIVATEREQ     | 1                    | ARESETn      |
| ACTIVATEACKCHK  | ACTIVATEACK     | 1                    | ARESETn      |
| ASKSTOPCHK      | ASKSTOP         | 1                    | ARESETn      |
| ACTIVATEREQDCHK | ACTIVATEREQD    | 1                    | ARESETn      |
| ACTIVATEACKDCHK | ACTIVATEACKD    | 1                    | ARESETn      |
| ASKSTOPDCHK     | ASKSTOPD        | 1                    | ARESETn      |
| SYSCOREQCHK     | SYSCOREQ        | 1                    | None         |
| SYSCOACKCHK     | SYSCOACK        | 1                    | None         |
|                 |                 |                      |              |

<span id="page-272-0"></span>**Part B Appendices**
