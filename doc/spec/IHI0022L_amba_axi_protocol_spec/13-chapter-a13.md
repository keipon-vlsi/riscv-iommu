# <span id="page-203-0"></span>Chapter A13

# **Untranslated Transactions**

This chapter describes how AXI supports the use of virtual addresses and translation stash hints for components upstream of a System Memory Management Unit (SMMU). It contains the following sections:

- [A13.1](#page-204-0) *[Introduction to Distributed Virtual Memory](#page-204-0)*
- [A13.2](#page-205-0) *[Support for untranslated transactions](#page-205-0)*
- [A13.3](#page-206-0) *[Untranslated transaction signaling](#page-206-0)*
- [A13.4](#page-208-0) *[Translation identifiers](#page-208-0)*
- [A13.5](#page-211-0) *[PCIe considerations](#page-211-0)*
- [A13.6](#page-213-0) *[Translation fault flows](#page-213-0)*
- [A13.7](#page-216-0) *[Untranslated transaction qualifier](#page-216-0)*
- [A13.8](#page-217-0) *[Permitted combinations of MMU signals and PAS](#page-217-0)*
- [A13.9](#page-218-0) *[StashTranslation Opcode](#page-218-0)*
- [A13.10](#page-219-0) *[UnstashTranslation Opcode](#page-219-0)*

# <span id="page-204-1"></span><span id="page-204-0"></span>**A13.1 Introduction to Distributed Virtual Memory**

An example system using Distributed Virtual Memory (DVM) is shown in [Figure](#page-204-1) [A13.1.](#page-204-1)

![](_page_204_Figure_3.jpeg)

**Figure A13.1: Virtual memory system**

In Figure [A13.1,](#page-204-1) the System Memory Management Units (SMMUs) translate addresses in the virtual address space to addresses in the physical address space. Although all components in the system must use a single physical address space, SMMU components enable different Manager components to operate in their own independent virtual address or intermediate physical address space.

A typical process in the virtual memory system shown in [Figure](#page-204-1) [A13.1](#page-204-1) might operate as follows:

- 1. A Manager component operating in a virtual address (VA) space issues a transaction that uses a VA.
- 2. The SMMU receives the VA for translation to a physical address (PA):
  - If the SMMU has recently performed the requested translation, then it might obtain a cached copy of the translation from its TLB.
  - Otherwise, the SMMU must perform a translation table walk, accessing translation table in memory to obtain the required VA to PA translation.
- 3. The SMMU uses the PA to issue the transaction for the requesting component.

At step 2 of this process, the translation for the required VA might not exist. In this case, the translation table walk generates a fault that must be notified to the agent that maintains the translation tables. For the required access to proceed, that agent must then provide the required VA to PA translation. Typically, it updates the translation tables with the required information.

Maintaining the translation tables can require changes to translation table entries that are cached in TLBs. To prevent the use of these entries, a DVM message can be used to issue a TLB invalidate operation.

After the translation tables have been updated and the necessary TLB invalidations have been performed, a DVM Sync transaction is used to ensure that all required transactions have completed.

<span id="page-204-2"></span>Details of DVM messages used to maintain SMMUs can be found in Chapter [A15](#page-230-0) *[Distributed Virtual Memory](#page-230-0) [messages](#page-230-0)*.

# <span id="page-205-0"></span>**A13.2 Support for untranslated transactions**

AXI supports the use of virtual addresses through the untranslated transactions extension.

The Untranslated\_Transactions property is used to indicate which version of untranslated transactions is supported by an interface.

**Table A13.1: Untranslated\_Transactions property**

| Untranslated_Transactions | Default | Description                                       |
|---------------------------|---------|---------------------------------------------------|
| v4                        |         | Untranslated transactions version 4 is supported. |
| v3                        |         | Untranslated transactions version 3 is supported. |
| v2                        |         | Untranslated transactions version 2 is supported. |
| v1                        |         | Untranslated transactions version 1 is supported. |
| True                      |         | Untranslated transactions version 1 is supported. |
| False                     | Y       | Untranslated transactions are not supported.      |

Address translation is the process of translating an input address to an output address based on address mapping and memory attribute information that is held in translation tables. This process permits agents in the system to use their own virtual address space, but ensures that the addresses for all transactions are eventually translated to a single physical address space for the entire system.

The use of a single physical address space is required for the correct operation of hardware coherency and therefore the SMMU functionality is typically located before a coherent interconnect.

The additional signals that are specified in this section provide sufficient information for an SMMU to determine the translation that is required for a particular transaction and permit different transactions on the same interface to use different translation schemes.

All signals in the Untranslated Transactions extension are prefixed with AWMMU for write transactions and ARMMU for read transactions.

<span id="page-205-1"></span>In this specification, AxMMU indicates AWMMU or ARMMU.

# <span id="page-206-0"></span>**A13.3 Untranslated transaction signaling**

The signals to support untranslated transactions are shown in Table [A13.2.](#page-206-1) Each signal is described in following sections, including the property values which determine whether they are present.

**Table A13.2: Signals for Untranslated Transactions**

<span id="page-206-16"></span><span id="page-206-15"></span><span id="page-206-14"></span><span id="page-206-13"></span><span id="page-206-12"></span><span id="page-206-7"></span><span id="page-206-6"></span><span id="page-206-5"></span><span id="page-206-4"></span><span id="page-206-3"></span><span id="page-206-1"></span>

| Name                                | Width        | Default              | Description                                                                                                                  |
|-------------------------------------|--------------|----------------------|------------------------------------------------------------------------------------------------------------------------------|
| AWMMUSECSID,<br>ARMMUSECSID         | SECSID_WIDTH | 0b00<br>(Non-secure) | Secure Stream Identifier for untranslated<br>transactions.                                                                   |
| AWMMUSID,<br>ARMMUSID               | SID_WIDTH    | All zeros            | Stream Identifier for untranslated<br>transactions.                                                                          |
| AWMMUSSIDV,<br>ARMMUSSIDV           | 1            | 0b0                  | Asserted HIGH to indicate that a<br>transaction has a valid substream identifier.                                            |
| AWMMUSSID,<br>ARMMUSSID             | SSID_WIDTH   | All zeros            | Substream identifier for untranslated<br>transactions.                                                                       |
| AWMMUATST,<br>ARMMUATST             | 1            | 0b0                  | Indicates that the transaction has already<br>undergone PCIe ATS translation.                                                |
| AWMMUFLOW,<br>ARMMUFLOW             | 2            | 0b00<br>(Stall)      | Indicates the SMMU flow for managing<br>translation faults for this transaction.                                             |
| AWMMUVALID,<br>ARMMUVALID           | 1            | 0b1                  | MMU qualifier signal. When deasserted,<br>the transaction address is a physical<br>address and does not require translation. |
| AWMMUPM,<br>ARMMUPM                 | 1            | 0b0                  | Protected Mode indicator                                                                                                     |
| AWMMUPASUNKNOWN,<br>ARMMUPASUNKNOWN | 1            | 0b0                  | HIGH to indicate that there is no PAS<br>expectation                                                                         |

<span id="page-206-19"></span><span id="page-206-18"></span><span id="page-206-17"></span><span id="page-206-11"></span><span id="page-206-10"></span><span id="page-206-9"></span><span id="page-206-8"></span><span id="page-206-2"></span>When Untranslated\_Transactions is v2 or higher, RRESP and BRESP are extended to 3-bits to accommodate the signaling of the TRANSFAULT response. See [A3.3](#page-60-0) *[Transaction response](#page-60-0)* for encodings.

In Table [A13.3](#page-207-0) there is a summary of which MMU signals are present for which version of untranslated transactions.

- 'Y' indicates that the signal is mandatory.
- 'C' indicates that the presence is configurable.
- <span id="page-207-0"></span>• '-' indicates that the signal must not be present.

**Table A13.3: Signals in each version of untranslated transactions**

| Signals         | Version 1 | Version 2 | Version 3 | Version 4 |
|-----------------|-----------|-----------|-----------|-----------|
| AxMMUSECSID     | Y         | Y         | Y         | Y         |
| AxMMUSID        | C         | C         | C         | C         |
| AxMMUSSIDV      | C         | C         | C         | C         |
| AxMMUSSID       | C         | C         | C         | C         |
| AxMMUATST       | C         | -         | -         | -         |
| AxMMUFLOW       | -         | C         | C         | C         |
| AxMMUVALID      | -         | -         | Y         | Y         |
| AxMMUPM         | -         | -         | -         | C         |
| AxMMUPASUNKNOWN | -         | -         | -         | C         |

# <span id="page-208-0"></span>**A13.4 Translation identifiers**

Requests using virtual addressing can have up to three identifiers that are used during address translation:

- Secure Stream Identifier [A13.4.1](#page-208-1) *[Secure Stream Identifier \(SECSID\)](#page-208-1)*
- Stream Identifier [A13.4.2](#page-209-0) *[StreamID \(SID\)](#page-209-0)*
- Substream Identifier [A13.4.3](#page-209-1) *[SubstreamID \(SSID\)](#page-209-1)*

During the building of a system, it is possible that the stream identifiers for a given component have some ID bits provided by the component and some ID bits that are tied off for that component. This fixes the range of values in the stream identifier name space that can be used by that component. Typically, the low-order bits are provided by the component and the high-order bits are tied off.

Any additional identifier field bits for AxMMUSID or AxMMUSSID, that are not supplied by the component or hard coded by the interconnect, must be tied LOW.

## <span id="page-208-2"></span><span id="page-208-1"></span>**A13.4.1 Secure Stream Identifier (SECSID)**

The Secure Stream Identifier is used to indicate the virtual address space of the request. It is transported using the AxMMUSECSID signal, Table [A13.4](#page-208-2) shows the encodings.

**Table A13.4: AxMMUSECSID encodings**

| AxMMUSECSID | Label      | Meaning                  |
|-------------|------------|--------------------------|
| 0b00        | Non-secure | Non-secure address space |
| 0b01        | Secure     | Secure address space     |
| 0b10        | Realm      | Realm address space      |
| 0b11        | RESERVED   | -                        |

The width of AxMMUSECSID is determined by the property SECSID\_WIDTH.

**Table A13.5: SECSID\_WIDTH property**

| Name         | Values  | Default | Description                                      |
|--------------|---------|---------|--------------------------------------------------|
| SECSID_WIDTH | 0, 1, 2 | 0       | Width of AWMMUSECSID and<br>ARMMUSECSID in bits. |

The following rules apply:

- SECSID\_WIDTH must be 0 when Untranslated\_Transactions is False. AxMMUSECSID signals are not present.
- SECSID\_WIDTH must be 1 when Untranslated\_Transactions is not False and RME\_Support is False. Only Non-secure and Secure address spaces can be used.
- SECSID\_WIDTH must be 2 when Untranslated\_Transactions is not False and RME\_Support is True.
- When AxMMUSECSID is Non-secure, the physical address space must be Non-secure.
- When AxMMUSECSID is Secure, the physical address space must be Non-secure or Secure.
- When AxMMUSECSID is Realm, the physical address space must be Non-secure or Realm.

### <span id="page-209-0"></span>**A13.4.2 StreamID (SID)**

The StreamID can be used to map a request to a translation context in the MMU. Each address space uses a different namespace, so they can have the same Stream Identifier values.

The width of AxMMUSID is determined by the property SID\_WIDTH.

**Table A13.6: SID\_WIDTH property**

| Name      | Values | Default | Description                                                  |  |
|-----------|--------|---------|--------------------------------------------------------------|--|
| SID_WIDTH | 032    | 0       | StreamID width in bits, applies to<br>AWMMUSID and ARMMUSID. |  |

If SID\_WIDTH is 0, AxMMUSID signals are not present and the default value is used.

## <span id="page-209-1"></span>**A13.4.3 SubstreamID (SSID)**

The SubstreamID can be used with requests that have the same StreamID to associate different application address translations to different logical blocks.

There is a separate enable signal AxMMUSSIDV for the SubstreamID, so a Manager can issue requests with or without a SubstreamID.

• When AxMMUSSIDV is deasserted, AxMMUSSID must be 0.

Note that a stream with a SubstreamID of 0 is different from a stream with no valid substream (AxMMUSSIDV is deasserted).

The width of AxMMUSSID is determined by the property SSID\_WIDTH.

**Table A13.7: SSID\_WIDTH property**

| Name       | Values | Default | Description                                                       |  |
|------------|--------|---------|-------------------------------------------------------------------|--|
| SSID_WIDTH | 020    | 0       | SubstreamID width in bits, applies to<br>AWMMUSSID and ARMMUSSID. |  |

When SSID\_WIDTH is 0, AxMMUSSID and AxMMUSSIDV are not present on the interface and there are no valid SubstreamIDs.

### <span id="page-210-0"></span>**A13.4.4 Untranslated Transactions and GDI**

When using untranslated transactions and GDI, the Untranslated\_Transactions property must be v4 and the following signals are included.

**Table A13.8: AxMMUPM signals**

| Name                | Width | Default | Presence                                                   | Description              |
|---------------------|-------|---------|------------------------------------------------------------|--------------------------|
| AWMMUPM,<br>ARMMUPM | 1     | 0       | GDI_Support == True and<br>Untranslated_Transactions == v4 | Protected Mode indicator |

The Protected Mode (PM) indicator is used to indicate which address spaces the request is permitted to access. The following rules apply:

- AxMMUPM can only be asserted for requests with a Non-secure context.
- When ARMMUPM is asserted, it means that the request can read from both NS and NSP address spaces.
- When AWMMUPM is asserted, it means that the request can write to the NSP address space but is not permitted to write to the NS address space.
- Requests to the Non-secure Protected or System Agent physical address space must be physically addressed, that means:
  - When AxPAS is NSP or SA, AxMMUVALID must be LOW.
- When AxMMUPM is asserted, AxMMUFLOW must not be Stall.

# <span id="page-211-0"></span>**A13.5 PCIe considerations**

When the Untranslated\_Transactions signaling is used for interfacing to PCIe Root Complex, the following considerations apply:

- AxMMUSECSID must be Non-secure or Realm.
- AxMMUSID corresponds to the PCIe Requester ID.
- AxMMUSSID corresponds to the PCIe PASID.
- AxMMUSSIDV is asserted if the transaction had a PASID prefix, otherwise it is deasserted.

### <span id="page-211-1"></span>**A13.5.1 PCIe XT mode**

PCIe eXtended TEE (XT) extends the access modes available for PCIe requests.

To support PCIe XT mode, AxMMUPASUNKNOWN signals are included, present when Untranslated\_Transactions is v4, RME\_Support is True and PAS\_WIDTH is not 0.

**Table A13.9: AxMMUPASUNKNOWN signals**

| Name                                | Width | Default | Description                                          |
|-------------------------------------|-------|---------|------------------------------------------------------|
| AWMMUPASUNKNOWN,<br>ARMMUPASUNKNOWN | 1     | 0b0     | HIGH to indicate that there is no<br>PAS expectation |

The following rules apply when AxMMUVALID and AxMMUPASUNKNOWN are asserted:

- AxMMUSECSID must be Realm.
- AxPAS is inapplicable and must be Realm.

A PCIe device in eXtended TEE (XT) mode provides XT and T bits which should map to AXI as shown in [Table](#page-211-2) [A13.10.](#page-211-2)

**Table A13.10: Mapping PCIe T and XT to AXI**

<span id="page-211-2"></span>

| XT | T | AxMMUSECSID | AxPAS      | AxMMUPASUNKNOWN | Meaning                                                       |
|----|---|-------------|------------|-----------------|---------------------------------------------------------------|
| 0  | 0 | Non-secure  | Non-secure | 0               | Non-trusted request that must<br>target a Non-secure PAS.     |
| 0  | 1 | Realm       | Realm      | 1               | Trusted request that can target a<br>Realm or Non-secure PAS. |
| 1  | 0 | Realm       | Non-secure | 0               | Trusted request that must target<br>a Non-secure PAS.         |
| 1  | 1 | Realm       | Realm      | 0               | Trusted request that must target<br>a Realm PAS.              |

When PCIe XT mode is not used, the T bit should map to AXI as shown in Table [A13.11.](#page-212-0)

#### **Table A13.11: Mapping PCIe T bit to AXI**

<span id="page-212-1"></span><span id="page-212-0"></span>

| T | AxMMUSECSID | AxMMUPASUNKNOWN | AxPAS      | Meaning                                                   |
|---|-------------|-----------------|------------|-----------------------------------------------------------|
| 0 | Non-secure  | 0               | Non-secure | Non-trusted request that must<br>target a Non-secure PAS. |
| 1 | Realm       | 0               | Realm      | Trusted request that must target<br>a Realm PAS.          |

# <span id="page-213-0"></span>**A13.6 Translation fault flows**

An untranslated transaction can indicate which flow can be used when an SMMU encounters a translation fault.

If no flow is indicated, a *Stall* flow is assumed. The property MMUFLOW\_Present is used to indicate whether other SMMU flows are supported.

**Table A13.12: MMUFLOW\_Present property**

| MMUFLOW_Present | Default | Description                              |
|-----------------|---------|------------------------------------------|
| True            |         | AxMMUFLOW or AxMMUATST are present.      |
| False           | Y       | AxMMUFLOW and AxMMUATST are not present. |

MMUFLOW\_Present must be False if Untranslated\_Transactions is False.

If MMUFLOW\_Present is True, then:

- If Untranslated\_Transactions is True or v1, ARMMUATST and AWMMUATST are present on the interface.
- If Untranslated\_Transactions is v2 or higher, ARMMUFLOW and AWMMUFLOW are present on the interface.

Version 1 of the specification for untranslated transactions supports the Stall and ATST flows, using the AxMMUATST signals.

- When AxMMUATST is deasserted LOW, the Stall flow is used.
- When AxMMUATST is asserted HIGH, the ATST flow is used.

For version 2 and above, the AxMMUFLOW signals are used to indicate which flow can be used.

**Table A13.13: AxMMUFLOW encodings**

| AxMMUFLOW | Flow type | Meaning                             |
|-----------|-----------|-------------------------------------|
| 0b00      | Stall     | The SMMU Stall flow can be used.    |
| 0b01      | ATST      | The SMMU ATST flow must be used.    |
| 0b10      | NoStall   | The SMMU NoStall flow must be used. |
| 0b11      | PRI       | The SMMU PRI flow can be used.      |

The following sections describe each flow in turn.

### <span id="page-214-0"></span>**A13.6.1 Stall flow**

When the Stall flow is used, software can configure the SMMU to take one of the following actions when a translation fault occurs:

- Terminate the transaction with an SLVERR response.
- Terminate the transaction with an OKAY response, data is RAZ/WI.
- Stall the translation and inform software that the translation is stalled. Software can then instruct the SMMU to terminate the transaction or update the translation tables and retry the translation. The Manager is not aware of the stall.

This flow enables software to manage translation faults and demand paging without the Manager being aware. However, it has the following limitations:

- The Manager can see very long transaction latency, potentially triggering timeouts.
- Due to the dependence of software activity, the Stall flow can cause deadlocks in some systems.

For example, it is not recommended for use with PCIe because of dependencies between outgoing transactions to PCIe from a CPU, and incoming transactions from PCIe through the SMMU.

Enabling the Stall flow does not necessarily cause a stall when a translation fault occurs. Stalls only occur when enabled by software. Software does not normally enable stalling for PCIe endpoints.

## <span id="page-214-1"></span>**A13.6.2 ATST flow**

The Address Translation Service Translated (ATST) flow indicates that the transaction has already been translated by Address Translation Services (ATS). It is only used by PCIe Root Ports.

When the flow is ATST, the transaction might still undergo some translation, depending on the configuration of the SMMU. For more information, see *Arm® System Memory Management Unit Architecture Specification* [\[7\]](#page-16-7).

If a translation fault occurs, the transaction must be terminated with an SLVERR response.

When the flow is ATST, the following constraints apply:

- AxMMUSECSID must be Non-secure or Realm.
- If Untranslated\_Transactions is True, v1 or v2 then AxMMUSSIDV must be LOW.

When Untranslated\_Transactions is v3 or higher, it is permitted to assert AxMMUSSIDV when AxMMUFLOW indicates ATST. This is to enable the transport of PASID and other attributes from a PCIe transaction using the AxMMUSSID signal.

### <span id="page-214-2"></span>**A13.6.3 NoStall flow**

The NoStall flow is used by a Manager that is not able to be stalled.

If a translation fault occurs when using this flow, the Subordinate must terminate the transaction with an SLVERR or OKAY response, even if software has configured the device to be stalled when a translation fault occurs.

This flow is recommended for Managers such as PCIe Root Ports which might deadlock if stalling is enabled by software.

### <span id="page-215-0"></span>**A13.6.4 PRI flow**

The PRI flow is designed for use with a PCIe integrated endpoint. The Manager uses the PRI flow to enable software to respond to translation faults without risking deadlock.

When the flow is PRI and a translation fault occurs, the transaction is terminated with a TRANSFAULT response. The Manager can then use a separate mechanism to request that the page is made available, before retrying the transaction. This mechanism is normally PCIe PRI.

When this flow is used, software enables ATS but no ATS features are required in hardware.

A transaction that uses this flow might still be terminated by the SMMU with an SLVERR, if the translation failed for a reason which cannot be resolved by a PRI request, for example because the SMMU is incorrectly configured.

The following rules apply to a TRANSFAULT response:

- TRANSFAULT is indicated by setting RRESP or BRESP to 0b101. See [A3.3](#page-60-0) *[Transaction response](#page-60-0)* for all encodings.
- A TRANSFAULT response is only permitted for requests using the PRI flow.
- If TRANSFAULT is used for one response transfer, it must be used for all response transfers of a transaction.
- <span id="page-215-1"></span>• If RRESP is TRANSFAULT, the read data in that transfer is not valid.

# <span id="page-216-0"></span>**A13.7 Untranslated transaction qualifier**

When the Untranslated\_Transactions property is v3 or higher, a qualifier signal AxMMUVALID is added to the read and write request channels.

When AxMMUVALID is deasserted, the transaction address is a physical address and does not require translation. This enables a Manager to issue a mixture of translated and untranslated transactions.

The rules for using these signals are:

- When AxMMUVALID is asserted, the following signals are constrained:
  - AxTAGOP must be 0b00 (Invalid)
- When AxMMUVALID is deasserted, the following signals are not applicable and can take any value:
  - AxMMUSECSID
  - AxMMUSID
  - AxMMUSSIDV
  - AxMMUSSID
  - AxMMUFLOW
  - AxMMUPM
  - AxMMUPASUNKNOWN
- Translated and untranslated transactions must not use the same ID for in-flight transactions, and this applies to the following:
  - Transactions with AWMMUVALID asserted and others with AWMMUVALID deasserted.
  - Transactions with ARMMUVALID asserted and others with ARMMUVALID deasserted.

# <span id="page-217-0"></span>**A13.8 Permitted combinations of MMU signals and PAS**

Table [A13.14](#page-217-1) shows the legal combinations of AxMMU signals and PAS. Other combinations are not permitted.

**Table A13.14: Legal combinations of MMU signals and PAS**

<span id="page-217-1"></span>

| MUVALID<br>M<br>Ax | MUSECSID<br>M<br>Ax | W<br>MUFLO<br>M<br>Ax | M<br>MUP<br>M<br>Ax | WN<br>MUPASUNKNO<br>M<br>Ax | PAS        | Meaning                                          |
|--------------------|---------------------|-----------------------|---------------------|-----------------------------|------------|--------------------------------------------------|
| 0                  | -                   | -                     | -                   | -                           | Secure     | NoStreamID, Secure PAS                           |
| 0                  | -                   | -                     | -                   | -                           | Non-secure | NoStreamID, Non-secure PAS                       |
| 0                  | -                   | -                     | -                   | -                           | Root       | NoStreamID, Root PAS                             |
| 0                  | -                   | -                     | -                   | -                           | Realm      | NoStreamID, Realm PAS                            |
| 0                  | -                   | -                     | -                   | -                           | SA         | NoStreamID, System Agent PAS                     |
| 0                  | -                   | -                     | -                   | -                           | NSP        | NoStreamID, Non-secure Protected PAS             |
| 1                  | Non-secure          | Stall, NoStall, PRI   | 0                   | 0                           | Non-secure | Untranslated, Non-secure context                 |
| 1                  | Non-secure          | NoStall, PRI          | 1                   | 0                           | Non-secure | Untranslated, Non-secure context, Protected Mode |
| 1                  | Non-secure          | ATST                  | 0                   | 0                           | Non-secure | Translated, Non-secure context                   |
| 1                  | Non-secure          | ATST                  | 1                   | 0                           | Non-secure | Translated, Non-secure context, Protected Mode   |
| 1                  | Secure              | Stall, NoStall, PRI   | 0                   | 0                           | Secure     | Untranslated, Secure context, Secure PAS         |
| 1                  | Secure              | Stall, NoStall, PRI   | 0                   | 0                           | Non-secure | Untranslated, Secure context, Non-secure PAS     |
| 1                  | Realm               | Stall, NoStall, PRI   | 0                   | 0                           | Non-secure | Untranslated, Realm context, Non-secure PAS      |
| 1                  | Realm               | Stall, NoStall, PRI   | 0                   | 0                           | Realm      | Untranslated, Realm context, Realm PAS           |
| 1                  | Realm               | Stall, NoStall, PRI   | 0                   | 1                           | Realm      | Untranslated, Realm context, no PAS expectation  |
| 1                  | Realm               | ATST                  | 0                   | 0                           | Non-secure | Translated, Realm context, Non-secure PAS        |
| 1                  | Realm               | ATST                  | 0                   | 0                           | Realm      | Translated, Realm context, Realm PAS             |
| 1                  | Realm               | ATST                  | 0                   | 1                           | Realm      | Translated, Realm context, no PAS expectation    |

# <span id="page-218-1"></span><span id="page-218-0"></span>**A13.9 StashTranslation Opcode**

The StashTranslation Opcode is a hint that an MMU should cache the table entry required to process the given address, to reduce the latency for any future transactions using that table entry.

The requirements on the MMU depend on whether the address is virtual or physical, and if the Realm Management Extension is being used:

- If AWMMUVALID is asserted or not present, the StashTranslation request has a virtual address and the MMU should cache the relevant page table entry.
- If AWMMUVALID is deasserted, the StashTranslation request has a physical address and the MMU should cache the relevant Granule Protection Table entry.

If RME\_Support is False, AWMMUVALID must be asserted for a StashTranslation request.

The StashTranslation Opcode can be used by a Manager and supported by a Subordinate if the following property conditions apply:

- Untranslated\_Transactions is v1 or higher.
- Untranslated\_Transactions is True and Cache\_Stash\_Transactions is True.

The rules for a StashTranslation operation are:

- The StashTranslation transaction consists of a request on the AW channel and a single response transfer on the B channel. There are no write data transfers.
- AWSNOOP is 0b01110 to indicate StashTranslation, AWSNOOP\_WIDTH can be 4 or 5.
- No stash target is supported. If present, AWSTASHNID, AWSTASHNIDEN, AWSTASHLPID, and AWSTASHLPIDEN must be LOW.
- Any legal combination of AWCACHE and AWDOMAIN values is permitted. See [Table](#page-135-2) [A8.7.](#page-135-2)
- AWATOP is 0b000000 (Non-atomic transaction).
- AWTAGOP is 0b00 (Invalid).
- StashTranslation requests must not use the same AXI ID values that are used by non-StashTranslation transactions on the write channels that are outstanding at the same time. This rule ensures that there are no ordering constraints between StashTranslation transactions and other transactions, so a Subordinate that does not stash translations can respond immediately.
- An OKAY response indicates that the StashTranslation request has been accepted, not that the translation is stashed. The request is a hint and is not guaranteed to be acted upon by a Completer.

# <span id="page-219-1"></span><span id="page-219-0"></span>**A13.10 UnstashTranslation Opcode**

The UnstashTranslation Opcode is a hint that the page table or granule table entry that corresponds to the given transaction address and StreamID is not likely to be used again.

The requirements on the MMU depend on whether the address is virtual or physical, and if the Realm Management Extension is being used:

- If AWMMUVALID is asserted or not present, the UnstashTranslation request has a virtual address and the MMU should deallocate the relevant page table entry.
- If AWMMUVALID is deasserted, the StashTranslation request has a physical address and the MMU should deallocate the relevant Granule Protection Table entry.

If RME\_Support is False, AWMMUVALID must be asserted for an UnstashTranslation request.

The UnstashTranslation\_Transaction property is used to indicate whether an interface supports the UnstashTranslation Opcode.

**Table A13.15: UnstashTranslation\_Transaction property**

| UnstashTranslation_Transaction | Default | Description                          |
|--------------------------------|---------|--------------------------------------|
| True                           |         | UnstashTranslation is supported.     |
| False                          | Y       | UnstashTranslation is not supported. |

The following table shows compatibility between Manager and Subordinate interfaces, according to the values of the UnstashTranslation\_Transaction property.

**Table A13.16: UnstashTranslation\_Transaction compatibility**

| UnstashTranslation_Transaction | Subordinate: False | Subordinate: True |
|--------------------------------|--------------------|-------------------|
| Manager: False                 | Compatible.        | Compatible.       |
| Manager: True                  | Not compatible.    | Compatible.       |

The rules for an UnstashTranslation operation are:

- The UnstashTranslation transaction consists of a request on the AW channel and a single response transfer on the B channel. There are no write data transfers.
- AWSNOOP is 0b10001 to indicate UnstashTranslation, AWSNOOP\_WIDTH must be 5.
- No stash target is supported. If present, AWSTASHNID, AWSTASHNIDEN, AWSTASHLPID, and AWSTASHLPIDEN must be LOW.
- Any legal combination of AWCACHE and AWDOMAIN values is permitted. See [Table](#page-135-2) [A8.7.](#page-135-2)
- AWATOP is 0b000000 (Non-atomic transaction).
- AWTAGOP is 0b00 (Invalid).
- AWID is unique-in-flight, which means:
  - An UnstashTranslation request can only be issued if there are no outstanding transactions on the write channels using the same ID value.
  - A Manager must not issue a request on the write channels with the same ID as an outstanding UnstashTranslation transaction.

*Chapter A13. Untranslated Transactions A13.10. UnstashTranslation Opcode*

- If present, AWIDUNQ must be asserted for an UnstashTranslation request.
- An OKAY response indicates that the UnstashTranslation request has been accepted, not that the translation is deallocated. The request is a hint and is not guaranteed to be acted upon by a Completer.
