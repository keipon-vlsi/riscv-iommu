## <span id="page-215-0"></span>Chapter 26. RISC-V Privileged Instruction Set Listings

This chapter presents instruction-set listings for all instructions defined in the RISC-V Privileged Architecture.

The instruction-set listings for unprivileged instructions, including the ECALL and EBREAK instructions, are provided in Volume I of this manual.

| 31 | 27      | 26<br>25  | 24<br>20 | 19<br>15                                                          | 14<br>12 | 11<br>7 | 6       | 0               |
|----|---------|-----------|----------|-------------------------------------------------------------------|----------|---------|---------|-----------------|
|    | funct7  |           | rs2      | rs1                                                               | funct3   | rd      | opcode  | R-type          |
|    |         | imm[11:0] |          | rs1                                                               | funct3   | rd      | opcode  | I-type          |
|    |         |           |          | Trap-Return Instructions                                          |          |         |         |                 |
|    | 0001000 |           | 00010    | 00000                                                             | 000      | 00000   | 1110011 | SRET            |
|    | 0011000 |           | 00010    | 00000                                                             | 000      | 00000   | 1110011 | MRET            |
|    | 0111000 |           | 00010    | 00000                                                             | 000      | 00000   | 1110011 | MNRET           |
|    |         |           |          | Interrupt-Management Instructions                                 |          |         |         |                 |
|    | 0001000 |           | 00101    | 00000                                                             | 000      | 00000   | 1110011 | WFI             |
|    |         |           |          |                                                                   |          |         |         |                 |
|    |         |           |          | Control Transfer Records Management Instructions                  |          |         |         |                 |
|    | 0001000 |           | 00100    | 00000                                                             | 000      | 00000   | 1110011 | SCTRCLR         |
|    |         |           |          | Supervisor Memory-Management Instructions                         |          |         |         |                 |
|    | 0001001 |           | rs2      | rs1                                                               | 000      | 00000   | 1110011 | SFENCE.VMA      |
|    |         |           |          | Hypervisor Memory-Management Instructions                         |          |         |         |                 |
|    | 0010001 |           | rs2      | rs1                                                               | 000      | 00000   | 1110011 | HFENCE.VVMA     |
|    | 0110001 |           | rs2      | rs1                                                               | 000      | 00000   | 1110011 | HFENCE.GVMA     |
|    |         |           |          | Hypervisor Virtual-Machine Load and Store Instructions            |          |         |         |                 |
|    | 0110000 |           | 00000    | rs1                                                               | 100      | rd      | 1110011 | HLV.B           |
|    | 0110000 |           | 00001    | rs1                                                               | 100      | rd      | 1110011 | HLV.BU          |
|    | 0110010 |           | 00000    | rs1                                                               | 100      | rd      | 1110011 | HLV.H           |
|    | 0110010 |           | 00001    | rs1                                                               | 100      | rd      | 1110011 | HLV.HU          |
|    | 0110100 |           | 00000    | rs1                                                               | 100      | rd      | 1110011 | HLV.W           |
|    | 0110010 |           | 00011    | rs1                                                               | 100      | rd      | 1110011 | HLVX.HU         |
|    | 0110100 |           | 00011    | rs1                                                               | 100      | rd      | 1110011 | HLVX.WU         |
|    | 0110001 |           | rs2      | rs1                                                               | 100      | 00000   | 1110011 | HSV.B           |
|    | 0110011 |           | rs2      | rs1                                                               | 100      | 00000   | 1110011 | HSV.H           |
|    | 0110101 |           | rs2      | rs1                                                               | 100      | 00000   | 1110011 | HSV.W           |
|    |         |           |          | Hypervisor Virtual-Machine Load and Store Instructions, RV64 only |          |         |         |                 |
|    | 0110100 |           | 00001    | rs1                                                               | 100      | rd      | 1110011 | HLV.WU          |
|    | 0110110 |           | 00000    | rs1                                                               | 100      | rd      | 1110011 | HLV.D           |
|    | 0110111 |           | rs2      | rs1                                                               | 100      | 00000   | 1110011 | HSV.D           |
|    |         |           |          |                                                                   |          |         |         |                 |
|    | 0001011 |           | rs2      | Svinval Memory-Management Extension<br>rs1                        | 000      | 00000   | 1110011 | SINVAL.VMA      |
|    | 0001100 |           | 00000    | 00000                                                             | 000      | 00000   | 1110011 | SFENCE.W.INVAL  |
|    | 0001100 |           | 00001    | 00000                                                             | 000      | 00000   | 1110011 | SFENCE.INVAL.IR |
|    | 0010011 |           | rs2      | rs1                                                               | 000      | 00000   | 1110011 | HINVAL.VVMA     |
|    |         |           |          |                                                                   |          |         |         |                 |

*Figure 125. RISC-V Privileged Instructions*

rs2 rs1 000 00000 1110011 HINVAL.GVMA
