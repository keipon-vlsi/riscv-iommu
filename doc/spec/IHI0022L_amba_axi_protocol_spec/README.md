# IHI0022L_amba_axi_protocol_spec.md — 章別インデックス

- 全 19 章 (分割 Level 1, パターン `^(Chapter\s+[A-Z]?\d+|Preface|Glossary|Part\s+[A-Z])`)

---

## 01. [prologue](./00-prologue.md)

*Copyright © 2003-2025 Arm Limited or its affiliates. All rights reserved.*

## 02. [Chapter A1 **Introduction**](./01-chapter-a1-introduction.md)

This chapter introduces the architecture of the AXI protocol and the terminology used in this specification. It contains the following sections:

## 03. [Chapter A2 **AXI transport**](./02-chapter-a2-axi-transport.md)

AXI uses channels to transport request, data and response transfers between components.

## 04. [Chapter A3 **AXI transactions**](./03-chapter-a3-axi-transactions.md)

The AXI protocol uses transactions for communication between Managers and Subordinates. All transactions include a request and a response. Write and read transactions also include one or more data transfers.

## 05. [Chapter A4](./04-chapter-a4.md)

This chapter describes request attributes that indicate how the request should be handled by downstream components. It contains the following sections:

## 06. [Chapter A5](./05-chapter-a5.md)

This chapter describes transaction identifiers and how they can be used to control the ordering of transactions. It contains the following sections:

## 07. [Chapter A6 **Atomic accesses**](./06-chapter-a6-atomic-accesses.md)

This chapter describes single-copy and multi-copy atomicity and how to perform exclusive accesses and atomic transactions.

## 08. [Chapter A7 **Request Opcodes**](./07-chapter-a7-request-opcodes.md)

The request Opcode indicates the function of a request and how it must be processed by a Subordinate.

## 09. [Chapter A8](./08-chapter-a8.md)

This chapter describes caching in the AXI protocol.

## 10. [Chapter A9](./09-chapter-a9.md)

This chapter describes cache maintenance operations (CMOs) that assist with software cache management. It contains the following sections:

## 11. [Chapter A10](./10-chapter-a10.md)

This chapter describes some additional request qualifiers for the AXI protocol.

## 12. [Chapter A11](./11-chapter-a11.md)

This chapter describes additional write transactions supported in the AXI protocol.

## 13. [Chapter A12](./12-chapter-a12.md)

This chapter describes the AXI features for system monitoring and debug. It also describes how to add user-defined extensions to each channel.

## 14. [Chapter A13](./13-chapter-a13.md)

This chapter describes how AXI supports the use of virtual addresses and translation stash hints for components upstream of a System Memory Management Unit (SMMU). It contains the following sections:

## 15. [Chapter A14 **Interface clock and power gating**](./14-chapter-a14-interface-clock-and-power-gating.md)

This chapter describes stopping and starting interfaces for the purposes of clock and power control. It contains the following sections:

## 16. [Chapter A15](./15-chapter-a15.md)

This chapter describes how AXI supports distributed system MMUs using Distributed Virtual Memory (DVM) messages to maintain all MMUs in a virtual memory system.

## 17. [Chapter B1 **Signal list**](./16-chapter-b1-signal-list.md)

This appendix lists all the signals described within this specification. Some channels and signals are optional, so are not included on every interface. Each signal name contains a hyperlink to the section in which the signal is defined.

## 18. [Chapter B2](./17-chapter-b2.md)

The specification part in this document describes a generic fully-featured protocol, with some features being mandatory and others optional, based on properties. Previous issues of this specification defined a number of interface classes for differen…

## 19. [Chapter B4 **Revisions**](./18-chapter-b4-revisions.md)

This appendix describes the technical changes between released issues of this specification.
