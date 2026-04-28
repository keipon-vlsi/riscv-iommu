# <span id="page-25-0"></span>Chapter A2 **AXI transport**

AXI uses channels to transport request, data and response transfers between components.

This chapter describes the AXI transport with options for either a VALID-READY handshake or credited channels. It contains the following sections:

- [A2.1](#page-26-0) *[Clock and reset](#page-26-0)*
- [A2.2](#page-27-0) *[AXI transport options](#page-27-0)*
- [A2.3](#page-28-0) *[Valid-Ready transport](#page-28-0)*
- [A2.4](#page-32-0) *[Credited transport](#page-32-0)*
- [A2.5](#page-39-0) *[Pipelining and register stages](#page-39-0)*
- <span id="page-25-1"></span>• [A2.6](#page-40-0) *[AXI transactions and transfers](#page-40-0)*

# <span id="page-26-0"></span>**A2.1 Clock and reset**

This section describes the requirements for implementing the AXI global clock and reset signals ACLK and ARESETn.

### <span id="page-26-1"></span>**A2.1.1 Clock**

<span id="page-26-4"></span>Each AXI interface has a single clock signal, ACLK. All input signals are sampled on the rising edge of ACLK. All output signal changes can only occur after the rising edge of ACLK.

There must be no combinatorial paths between input and output signals on an interface.

### <span id="page-26-5"></span><span id="page-26-2"></span>**A2.1.2 Reset**

The AXI protocol uses a single active-LOW reset signal, ARESETn. The reset signal can be asserted asynchronously, but deassertion can only be synchronous with a rising edge of ACLK.

Signals that are required to be deasserted during reset must remain deasserted at least until the rising ACLK edge after ARESETn is HIGH. The earliest point these signals can be asserted is at a rising ACLK edge after ARESETn is HIGH.

Other signals can take any value during reset.

<span id="page-26-3"></span>For example, for VALID, this is point *b* in [Figure](#page-26-3) [A2.1.](#page-26-3)

![](_page_26_Figure_11.jpeg)

**Figure A2.1: Exit from reset**

# <span id="page-27-0"></span>**A2.2 AXI transport options**

Two options are available for AXI transport:

- Ready, where every channel includes VALID and READY signals. The transmitter asserts VALID when it has a transfer to send. A transfer occurs when VALID and READY are both HIGH.
- Credited, where every channel includes VALID and CRDT signals. The receiver uses CRDT signals to give credits to the transmitter. The transmitter can assert VALID to send a transfer if it has an appropriate credit. This transport is good for high frequency operation and enables the use of Resource Planes on a link.

<span id="page-27-1"></span>All AXI channels on an interface use the same type of transport, [Table](#page-27-1) [A2.1](#page-27-1) shows how this is configured using the AXI\_Transport property.

**Table A2.1: AXI\_Transport property**

| AXI_Transport | Default | Description                                  |
|---------------|---------|----------------------------------------------|
| Credited      |         | AXI channels use CRDT flow control signals.  |
| Ready         | Y       | AXI channels use READY flow control signals. |

The following rules apply to transport configuration:

- Connected Manager and Subordinate interfaces must have the same value for the AXI\_Transport property.
- Credited transport can be used with AXI5 interfaces only.

# <span id="page-28-0"></span>**A2.3 Valid-Ready transport**

When using a Valid-Ready transport, all AXI channels use the same VALID-READY handshake process to transfer address, data, and control information. This two-way flow control mechanism means both the Manager and Subordinate can control the rate that the information moves between Manager and Subordinate. The transmitter generates the VALID signal to indicate when the address, data, or control information is available. The receiver generates the READY signal to indicate that it can accept the information. Transfer occurs only when both the VALID and READY signals are HIGH.

VALID signals must be LOW during reset.

[Figure](#page-28-1) [A2.2,](#page-28-1) [Figure](#page-28-2) [A2.3](#page-28-2) and [Figure](#page-29-1) [A2.4](#page-29-1) show examples of the handshake process.

<span id="page-28-1"></span>The transmitter presents information after edge 1 and asserts the VALID signal as shown in [Figure](#page-28-1) [A2.2.](#page-28-1) The receiver asserts the READY signal after edge 2. The transmitter must keep its information stable until the transfer occurs at edge 3, when this assertion is recognized.

![](_page_28_Figure_6.jpeg)

**Figure A2.2: VALID before READY handshake**

A transmitter is not permitted to wait until READY is asserted before asserting VALID.

When VALID is asserted, it must remain asserted until the handshake occurs, at a rising clock edge when VALID and READY are both asserted.

<span id="page-28-2"></span>In [Figure](#page-28-2) [A2.3,](#page-28-2) the receiver asserts READY after edge 1, before the address, data, or control information is valid. This assertion indicates that it can accept the information. The transmitter presents the information and asserts VALID after edge 2, then the transfer occurs at edge 3, when this assertion is recognized. In this case, transfer occurs in a single cycle.

![](_page_28_Figure_11.jpeg)

**Figure A2.3: READY before VALID handshake**

A receiver is permitted to wait for VALID to be asserted before asserting the corresponding READY.

If READY is asserted, it is permitted to deassert READY before VALID is asserted.

<span id="page-29-1"></span>In [Figure](#page-29-1) [A2.4,](#page-29-1) both the transmitter and receiver happen to indicate that they can transfer the address, data, or control information after edge 1. In this case, the transfer occurs at the rising clock edge when the assertion of both VALID and READY can be recognized. These assertions mean that the transfer occurs at edge 2.

![](_page_29_Figure_2.jpeg)

**Figure A2.4: VALID with READY handshake**

The default state of READY signals can be either HIGH or LOW.

For request channels, it is recommended to use HIGH as the default state to minimize latency. In that case, the Subordinate must be able to accept any valid request that is presented to it.

### <span id="page-29-0"></span>**A2.3.1 Valid-Ready signals**

[Table](#page-29-2) [A2.2](#page-29-2) shows the VALID and READY signals. VALID signals are present whether using Valid-Ready transport or credited transport.

**Table A2.2: Valid and Ready signals**

<span id="page-29-12"></span><span id="page-29-11"></span><span id="page-29-10"></span><span id="page-29-9"></span><span id="page-29-8"></span><span id="page-29-7"></span><span id="page-29-6"></span><span id="page-29-5"></span><span id="page-29-4"></span><span id="page-29-3"></span><span id="page-29-2"></span>

| Width | Default | Description                                                                  |  |
|-------|---------|------------------------------------------------------------------------------|--|
| 1     | -       | Asserted high to indicate that the signals on the AW channel are valid.      |  |
| 1     | -       | Asserted high to indicate that a transfer on the AW channel can be accepted. |  |
| 1     | -       | Asserted high to indicate that the signals on the W channel are valid.       |  |
| 1     | -       | Asserted high to indicate that a transfer on the W channel can be accepted.  |  |
| 1     | -       | Asserted high to indicate that the signals on the B channel are valid.       |  |
| 1     | -       | Asserted high to indicate that a transfer on the B channel can be accepted.  |  |
| 1     | -       | Asserted high to indicate that the signals on the AR channel are valid.      |  |
| 1     | -       | Asserted high to indicate that a transfer on the AR channel can be accepted. |  |
| 1     | -       | Asserted high to indicate that the signals on the R channel are valid.       |  |
| 1     | -       | Asserted high to indicate that a transfer on the R channel can be accepted.  |  |
|       |         |                                                                              |  |

### <span id="page-30-0"></span>**A2.3.2 Dependencies between channel handshake signals**

There are dependencies between channels for write, read, and snoop transactions. These are described in the sections below and include dependency diagrams, where:

- Single-headed arrows point to signals that can be asserted before or after the signal at the start of the arrow.
- Double-headed arrows point to signals that must be asserted only after assertion of the signal at the start of the arrow.

### **A2.3.2.1 Write transaction dependencies**

For transactions on the write channels, [Figure](#page-30-1) [A2.5](#page-30-1) shows the handshake signal dependencies. The rules are:

- The Manager must not wait for the Subordinate to assert AWREADY or WREADY before asserting AWVALID or WVALID. This applies to every write data transfer in a transaction.
- The Subordinate can wait for AWVALID or WVALID, or both, before asserting AWREADY.
- The Subordinate can assert AWREADY before AWVALID or WVALID, or both, are asserted.
- The Subordinate can wait for AWVALID or WVALID, or both, before asserting WREADY.
- The Subordinate can assert WREADY before AWVALID or WVALID, or both, are asserted.
- The Subordinate must wait for AWVALID, AWREADY, WVALID, and WREADY to be asserted before asserting BVALID.
- The Subordinate must wait for the last write data transfer before asserting BVALID. The last write data transfer has WLAST asserted, see [A3.2.1](#page-52-1) *[Write data channel \(W\)](#page-52-1)*.
- The Subordinate must not wait for the Manager to assert BREADY before asserting BVALID.
- The Manager can wait for BVALID before asserting BREADY.
- <span id="page-30-1"></span>• The Manager can assert BREADY before BVALID is asserted.

![](_page_30_Figure_17.jpeg)

**Figure A2.5: Write transaction handshake dependencies**

For transactions on the write channels that do not include data, WVALID and WREADY are not included in the dependencies.

### **A2.3.2.2 Read transaction dependencies**

For transactions on the read channels, [Figure](#page-31-0) [A2.6](#page-31-0) shows the handshake signal dependencies. The rules are:

- The Manager must not wait for the Subordinate to assert ARREADY before asserting ARVALID.
- The Subordinate can wait for ARVALID to be asserted before it asserts ARREADY.
- The Subordinate can assert ARREADY before ARVALID is asserted.
- The Subordinate must wait for both ARVALID and ARREADY to be asserted before it asserts RVALID to indicate that valid data is available.
- The Subordinate must not wait for the Manager to assert RREADY before asserting RVALID.
- The Manager can wait for RVALID to be asserted before it asserts RREADY.
- <span id="page-31-0"></span>• The Manager can assert RREADY before RVALID is asserted.

![](_page_31_Picture_10.jpeg)

**Figure A2.6: Read transaction handshake dependencies**

# <span id="page-32-2"></span><span id="page-32-0"></span>**A2.4 Credited transport**

When the AXI\_Transport property is Credited, AXI channels use a credited transport.

[Table](#page-32-1) [A2.3](#page-32-1) shows a list of all signals that can be added to a channel when credited transport is used. Signal names are the base name, when instantiated each includes a prefix to indicate which channel they belong.

A channel has a transmitter (Tx) and a receiver (Rx).

**Table A2.3: Credited channel signals**

<span id="page-32-1"></span>

| Name      | Width         | Source | Presence                  | Description                                                                                                                    |
|-----------|---------------|--------|---------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| VALID     | 1             | Tx     | -                         | When asserted HIGH, there is one<br>transfer from Tx to Rx.                                                                    |
| PENDING   | 1             | Tx     | AXI_Transport == Credited | Asserted HIGH to indicate that a<br>transfer might occur in the following<br>cycle. See A2.4.4 Transfer-level<br>clock gating. |
| RP        | clog2(Num_RP) | Tx     | Num_RP > 1                | Encoded indicator of the Resource<br>Plane number for a transfer. See<br>A2.4.2 Resource Planes.                               |
| SHAREDCRD | 1             | Tx     | Shared_Credits == True    | Asserted HIGH to indicate that the<br>transfer is using a shared credit.<br>See A2.4.3 Shared credits.                         |
| CRDT      | Num_RP        | Rx     | AXI_Transport == Credited | Asserted HIGH to give one credit on<br>the respective resource plane.                                                          |
| CRDTSH    | 1             | Rx     | Shared_Credits == True    | Asserted HIGH to give one shared<br>credit. See A2.4.3 Shared credits.                                                         |

### <span id="page-33-0"></span>**A2.4.1 Credited flow control**

The following rules apply to a credited channel:

- During reset the channel transmitter has no credits, the receiver has all available credits. All CRDT and CRDTSH signals must be LOW.
- Each cycle that CRDT or CRDTSH is asserted gives one credit per bit asserted, to the channel transmitter.
- The channel transmitter uses a credit each cycle that VALID is asserted.
- VALID must not be asserted when the channel transmitter has zero credits.
- The minimum number of credits that the receiver can give is 1 per resource plane.
- The maximum number of credits that the receiver can give is 15 per resource plane and 15 shared credits.

There must not be combinatorial paths between credit signals and other signals on a channel in either direction. This restriction has the following consequences:

- A credit cannot be used for a transfer in the same cycle that it is given.
- A credit cannot be given in the same cycle that it is used by a transfer.

<span id="page-33-1"></span>An example of transfers on a channel is shown in [Figure](#page-33-1) [A2.7.](#page-33-1) In this example, the receiver has two credits available.

![](_page_33_Figure_13.jpeg)

**Figure A2.7: Example Transfers**

- Cycle 0 At reset the Tx has no credits.
- Cycle 3 One credit is given by the Rx.
- Cycle 4 The Tx uses the credit for a transfer. Another credit is given by the Rx.
- Cycle 5 The Tx uses the second credit for a transfer.
- Cycle 7 The credit used in cycle 4 is given back to the Tx.
- Cycle 8 The Tx uses the credit for a transfer.

### <span id="page-34-0"></span>**A2.4.2 Resource Planes**

Resource Planes (RP) are used to enable independence between traffic sharing a channel. This could be to avoid deadlock scenarios or to improve quality-of-service. Each RP has dedicated credits so it is possible to give credits for one RP, allowing it to make progress when another RP is blocked waiting for credit.

• Transfers using different Resource Planes must not block one another between transmitter and receiver.

If transfers remain on separate Resource Planes across multiple links, then the non-blocking guarantee can be extended.

The parameter Num\_RP specifies how many RPs are supported on a channel.

The RP signal indicates the Resource Plane number for each transfer, from 0 to Num\_RP-1.

The width of RP is clog2(Num\_RP). For example, if Num\_RP is 5 the width of RP is 3. If Num\_RP is 1, there is no RP signal.

Credits are given per Resource Plane. The CRDT signal has one bit per Resource Plane, therefore the receiver can give up to one credit per RP per cycle. The number of credits for each RP is permitted to be different.

- The transmitter can issue a transfer on a specific RP only if it has at least one credit for that RP.
- The receiver must be able to give at least one dedicated credit per RP supported.
- The AR, AW and W channels can have multiple RPs.
- The AW and W transfers in the same transaction must use the same RP number.

There are no ordering guarantees between transfers using different RPs. This means:

- A Manager must not issue a request transfer that has the same ID as an outstanding transaction on the same channel but a different RP.
- A Manager can interleave write data transfers for different transactions if they are using different RPs. See [A5.5](#page-99-0) *[Write data and response ordering](#page-99-0)*.

The B and R channels have one RP.

<span id="page-34-1"></span>[Table](#page-34-1) [A2.5](#page-34-1) shows the properties that define the number of RPs.

**Table A2.5: Resource plane number properties**

| Name       | Values | Default | Description                                         |
|------------|--------|---------|-----------------------------------------------------|
| Num_RP_AWW | 1-8    | 1       | Number of resource planes on the AW and W channels. |
| Num_RP_AR  | 1-8    | 1       | Number of resource planes on the AR channel.        |

Connected interfaces can be configured to have a different number of RPs, but a Manager must not require the use of more RPs than can be provided by the attached Subordinate.

If the AXI\_Transport property is Ready: Num\_RP\_AWW and Num\_RP\_AR must be 1.

### <span id="page-35-0"></span>**A2.4.3 Shared credits**

Any channel that includes multiple RPs can optionally include shared credits to improve buffer utilization when throughput varies on different RPs. A receiver supporting shared credits can allocate its buffers between those dedicated to one RP and those for any RP.

[Table](#page-35-1) [A2.6](#page-35-1) shows the properties that define whether shared credits are supported.

**Table A2.6: Shared credit properties**

<span id="page-35-1"></span>

| Name              | Values         | Default | Description                                                                                                       |
|-------------------|----------------|---------|-------------------------------------------------------------------------------------------------------------------|
| Shared_Credits_AW | True,<br>False | False   | If True, Shared credits are supported on the AW channel and<br>the AWCRDTSH and AWSHAREDCRD signals are included. |
| Shared_Credits_W  | True,<br>False | False   | If True, Shared credits are supported on the W channel and the<br>WCRDTSH and WSHAREDCRD signals are included.    |
| Shared_Credits_AR | True,<br>False | False   | If True, Shared credits are supported on the AR channel and<br>the ARCRDTSH and ARSHAREDCRD signals are included. |

The following rules apply:

- If the AXI\_Transport property is Ready: Shared\_Credits\_AW, Shared\_Credits\_W and Shared\_Credits\_AR must be False.
- If Num\_RP\_AWW is 1: Shared\_Credits\_AW and Shared\_Credits\_W must be False.
- If Num\_RP\_AR is 1: Shared\_Credits\_AR must be False.
- The CRDTSH signal is asserted by the receiver to give one shared credit to the transmitter. CRDTSH can be asserted without asserting CRDT.
- A transmitter can use a shared credit to send a transfer on any RP.
- A receiver must give independence guarantees between RPs, whether the transmitter is using a shared or dedicated credit.
- The SHAREDCRD signal is asserted by the transmitter alongside VALID to indicate that the transfer is using a shared credit.

It is recommended that a transmitter uses a dedicated rather than shared credit for a transfer if it has both. This is because shared credits are more flexible so could be retained for a transfer that does not have a dedicated credit.

The compatibility between Manager and Subordinate interfaces according to the values of the Shared\_Credits properties is shown in [Table](#page-35-2) [A2.7.](#page-35-2)

**Table A2.7: Shared credits compatibility**

<span id="page-35-2"></span>

| Shared_Credits | Subordinate: False | Subordinate: True                                                                                                                   |
|----------------|--------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Manager: False | Compatible.        | Compatible.<br>SHAREDCRD inputs tied LOW, CRDTSH<br>outputs unconnected.<br>Functional, but available shared credits are<br>unused. |

Manager: True Compatible. Compatible.

SHAREDCRD outputs unconnected,

CRDTSH inputs tied LOW.

Manager does not receive any shared credits.

An example of the use of a channel with 3 Resource Planes and shared credits is shown in [Figure](#page-36-0) [A2.8.](#page-36-0)

<span id="page-36-0"></span>![](_page_36_Figure_6.jpeg)

**Figure A2.8: Example of a channel with 3 Resource Planes**

- Cycle 0 The Transmitter has no credits.
- Cycle 1 The Receiver gives one credit for each RP and one shared credit.
- Cycle 2 The Transmitter sends a transfer on RP1 using a dedicated credit.
- Cycle 3 The Receiver gives a dedicated credit back to the Transmitter for RP1.
- Cycle 5 The Transmitter sends a transfer on RP2 using a dedicated credit.
- Cycle 6 The Transmitter sends a transfer on RP2 using a shared credit, as no dedicated credits are available.
- Cycle 7 The Receiver gives a shared credit, and a dedicated credit for RP2 back to the Transmitter.
- Cycle 8 The Transmitter sends a transfer on RP0 using a dedicated credit
- Cycle 9 The Receiver gives a dedicated credit back to the Transmitter for RP0, along with an additional shared credit.

### <span id="page-37-0"></span>**A2.4.4 Transfer-level clock gating**

The PENDING signal associated with a channel is guaranteed to be asserted the cycle before a transfer is sent, so can be used to gate the clock of the receiver circuitry.

The following rules apply:

- There is one PENDING signal per channel.
- It is required that PENDING is asserted in the cycle before VALID is asserted.
- When PENDING is deasserted, it is required that VALID is deasserted in the next cycle.
- When PENDING is asserted, it is permitted but not required that VALID is asserted in the next cycle.

The PENDING signal is independent of credits and credit control. For example, a transmitter is permitted to do any of the following:

- Keep PENDING permanently asserted, including during reset. It might do this if it is unable to determine in advance when a transfer is to be sent.
- Assert PENDING when it does not have a credit.
- Assert and then deassert PENDING without sending a transfer.

<span id="page-37-1"></span>An example of the use of PENDING is shown in [Figure](#page-37-1) [A2.9.](#page-37-1)

![](_page_37_Figure_13.jpeg)

**Figure A2.9: Example usage of the PENDING signal**

See [A14.2](#page-224-0) *[Interface gating with credited transport](#page-224-0)* for information regarding gating of interfaces using credited channels.

### <span id="page-38-0"></span>**A2.4.5 Credited transport signals**

[Table](#page-38-1) [A2.9](#page-38-1) shows the signals that can be included when AXI\_Transport is Credited. Each channel also has a VALID signal, as shown in [Table](#page-29-2) [A2.2.](#page-29-2)

**Table A2.9: Signals when using credited transport**

<span id="page-38-20"></span><span id="page-38-19"></span><span id="page-38-18"></span><span id="page-38-17"></span><span id="page-38-16"></span><span id="page-38-15"></span><span id="page-38-14"></span><span id="page-38-13"></span><span id="page-38-12"></span><span id="page-38-11"></span><span id="page-38-10"></span><span id="page-38-9"></span><span id="page-38-8"></span><span id="page-38-7"></span><span id="page-38-6"></span><span id="page-38-5"></span><span id="page-38-4"></span><span id="page-38-3"></span><span id="page-38-2"></span><span id="page-38-1"></span>

| Name        | Width             | Default   | Description                                                                                |
|-------------|-------------------|-----------|--------------------------------------------------------------------------------------------|
| AWPENDING   | 1                 | 0b1       | Asserted HIGH to indicate that a transfer might<br>occur in the following cycle.           |
| AWCRDT      | Num_RP_AWW        | All zeros | Asserted HIGH to give one AW credit on the<br>respective RP.                               |
| AWCRDTSH    | 1                 | 0b0       | Asserted HIGH to give one shared AW credit,<br>supports up to one shared credit per cycle. |
| AWRP        | clog2(Num_RP_AWW) | All zeros | Encoded indicator of the Resource Plane number<br>for an AW transfer.                      |
| AWSHAREDCRD | 1                 | 0b0       | Asserted HIGH to indicate that an AW transfer is<br>using a shared credit.                 |
| WPENDING    | 1                 | 0b1       | Asserted HIGH to indicate that a transfer might<br>occur in the following cycle.           |
| WCRDT       | Num_RP_AWW        | All zeros | Asserted HIGH to give one W credit on the<br>respective RP.                                |
| WCRDTSH     | 1                 | 0b0       | Asserted HIGH to give one shared W credit,<br>supports up to one shared credit per cycle.  |
| WRP         | clog2(Num_RP_AWW) | All zeros | Encoded indicator of the Resource Plane number<br>for a W transfer.                        |
| WSHAREDCRD  | 1                 | 0b0       | Asserted HIGH to indicate that a W transfer is<br>using a shared credit.                   |
| BPENDING    | 1                 | 0b1       | Asserted HIGH to indicate that a transfer might<br>occur in the following cycle.           |
| BCRDT       | 1                 | 0b0       | Asserted HIGH to give one B credit.                                                        |
| ARPENDING   | 1                 | 0b1       | Asserted HIGH to indicate that a transfer might<br>occur in the following cycle.           |
| ARCRDT      | Num_RP_AR         | All zeros | Asserted HIGH to give one AR credit on the<br>respective RP.                               |
| ARCRDTSH    | 1                 | 0b0       | Asserted HIGH to give one shared AR credit,<br>supports up to one shared credit per cycle. |
| ARRP        | clog2(Num_RP_AR)  | All zeros | Encoded indicator of the Resource Plane number<br>for an AR transfer.                      |
| ARSHAREDCRD | 1                 | 0b0       | Asserted HIGH to indicate that an AR transfer is<br>using a shared credit.                 |
| RPENDING    | 1                 | 0b1       | Asserted HIGH to indicate that a transfer might<br>occur in the following cycle.           |
| RCRDT       | 1                 | 0b0       | Asserted HIGH to give one R credit.                                                        |
|             |                   |           |                                                                                            |

# <span id="page-39-0"></span>**A2.5 Pipelining and register stages**

Each AXI channel transfers information in only one direction, and the architecture does not require any fixed relationship between the channels. This means that a register stage can be inserted at any point in any channel at the cost of an additional cycle of latency.

These qualities make the following possible:

- Trade-off between cycles of latency and maximum frequency of operation.
- Direct, fast connection between a processor and high-performance memory, while using simple register slices to isolate longer paths to less performance critical peripherals.

The following rules apply to the registering of channels:

- There can be any number of register stages on VALID, READY, and CRDT paths between components.
- Different channels can have a different number of register stages, depending on their timing requirements.
- VALID signals must be pipelined by the same number of cycles as the payload signals of that channel including RP and SHAREDCRD signals, if present.
- <span id="page-39-1"></span>• PENDING signals must retain the relationship that they are HIGH in the cycle before VALID is HIGH.

# <span id="page-40-0"></span>**A2.6 AXI transactions and transfers**

The AXI protocol requires the following relationships to be maintained:

- A write response must always follow the last write transfer in a write transaction.
- Read data and responses must always follow the read request.
- When a Manager issues a write request, it must be able to provide all write data for that transaction, without dependency on other transactions from that Manager.
- When a Manager has issued a write request and all write data, it must be able to accept all responses for that transaction, without dependency on other transactions from that Manager.
- When a Manager has issued a read request, it must be able to accept all read data for that transaction, without dependency on other transactions from that Manager.
  - Note that a Manager can rely on read data returning in order from transactions that use the same ID, so the Manager only needs enough storage for read data from transactions with different IDs.
- A Manager is permitted to wait for one transaction to complete before issuing another transaction request.
- A Subordinate is permitted to wait for one transaction to complete before accepting another request, giving credits or sending transfers for another transaction.
- A Subordinate must not block acceptance of data-less write requests due to transactions with leading write data.

The protocol does not define any other relationship between the channels.

The lack of relationship means, for example, that the write data can appear at an interface before the write request for the transaction. This can occur if the write request channel contains more register stages than the write data channel. Similarly, the write data might appear in the same cycle as the request.

When the interconnect is required to determine the destination address space or Subordinate space, it must realign the request and write data. This realignment is required to assure that the write data is signaled as being valid only to the Subordinate for which it is destined.
