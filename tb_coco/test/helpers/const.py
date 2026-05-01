"""iommu_tb.const — RISC-V IOMMU テストベンチ全体の定数定義

`rv_iommu_reg_pkg.sv` および RISC-V IOMMU spec 1.0 に準拠。
新しい cause 値や PTE bit を追加する時はここに集約してください。
"""

# =============================================================================
# レジスタアドレス (mmio offset)
# =============================================================================
# 8 byte registers — _L が下位 4 byte, _H が上位 4 byte。
# 8 byte 単位の R/W が通る場合は _L だけ使えば OK。
REG_CAPABILITIES_L = 0x000
REG_CAPABILITIES_H = 0x004
REG_FCTL           = 0x008      # 4 byte
REG_DDTP_L         = 0x010
REG_DDTP_H         = 0x014
REG_CQB_L          = 0x018
REG_CQB_H          = 0x01C
REG_CQH            = 0x020      # 4 byte (RO)
REG_CQT            = 0x024      # 4 byte
REG_FQB_L          = 0x028
REG_FQB_H          = 0x02C
REG_FQH            = 0x030      # 4 byte
REG_FQT            = 0x034      # 4 byte (RO)
REG_PQB_L          = 0x038
REG_PQB_H          = 0x03C
REG_PQH            = 0x040
REG_PQT            = 0x044
REG_CQCSR          = 0x048      # 4 byte
REG_FQCSR          = 0x04C      # 4 byte
REG_PQCSR          = 0x050      # 4 byte
REG_IPSR           = 0x054      # 4 byte

# =============================================================================
# ddtp フィールド
# =============================================================================
DDTP_MODE_OFF   = 0x0
DDTP_MODE_BARE  = 0x1
DDTP_MODE_1LVL  = 0x2
DDTP_MODE_2LVL  = 0x3
DDTP_MODE_3LVL  = 0x4

DDTP_MODE_MASK  = 0xF
DDTP_BUSY_BIT   = 0x10          # bit[4]
DDTP_PPN_SHIFT  = 10            # bits [53:10]

# =============================================================================
# fctl フィールド
# =============================================================================
FCTL_BE   = 1 << 0
FCTL_WSI  = 1 << 1
FCTL_GXL  = 1 << 2

# =============================================================================
# cqcsr / fqcsr / pqcsr 共通フィールド
# =============================================================================
QCSR_EN          = 1 << 0       # enable
QCSR_IE          = 1 << 1       # interrupt enable
QCSR_MF          = 1 << 8       # memory fault (W1C)
QCSR_CMD_TO      = 1 << 9       # command timeout (cqcsr only)
QCSR_CMD_ILL     = 1 << 10      # illegal command (cqcsr only)
QCSR_FENCE_W_IP  = 1 << 11      # iofence wait-IP (cqcsr only)
QCSR_BUSY        = 1 << 17      # WIP indicator
QCSR_ON          = 1 << 16      # queue is on

# 旧名称: 互換のため残す
FQCSR_FQEN = QCSR_EN
FQCSR_FIE  = QCSR_IE
FQCSR_FQON = QCSR_ON
FQCSR_BUSY = QCSR_BUSY
FQCSR_FQMF = QCSR_MF            # fault-queue memory fault

CQCSR_CQEN = QCSR_EN
CQCSR_CIE  = QCSR_IE
CQCSR_CQON = QCSR_ON
CQCSR_BUSY = QCSR_BUSY

# =============================================================================
# Device Context (DC) レイアウト — Extended format = 64 bytes
# =============================================================================
# 各 8 byte 単位で順に並ぶ。CDW は 1 burst でこの並びを連続読み出す。
DC_SIZE                  = 64
DC_OFF_TC                = 0
DC_OFF_IOHGATP           = 8
DC_OFF_TA                = 16
DC_OFF_FSC               = 24
DC_OFF_MSIPTP            = 32
DC_OFF_MSI_ADDR_MASK     = 40
DC_OFF_MSI_ADDR_PATTERN  = 48
DC_OFF_RESERVED          = 56

# DC.tc bit 位置 (spec section 2.1.4)
TC_V        = 1 << 0
TC_EN_ATS   = 1 << 1
TC_EN_PRI   = 1 << 2
TC_T2GPA    = 1 << 3
TC_DTF      = 1 << 4
TC_PDTV     = 1 << 5
TC_PRPR     = 1 << 6
TC_GADE     = 1 << 7
TC_SADE     = 1 << 8
TC_DPE      = 1 << 9
TC_SBE      = 1 << 10
TC_SXL      = 1 << 11

# iohgatp / fsc / msiptp の MODE encoding
# (注: これらは SATP 互換レイアウト = MODE が最上位 4 bit。
#  ddtp は別レイアウトなので混同しないこと)
ATGP_MODE_BARE  = 0
ATGP_MODE_SV39  = 8
ATGP_MODE_SV48  = 9
ATGP_MODE_SV57  = 10

# Sv39x4 (G-stage)
HGATP_MODE_BARE   = 0
HGATP_MODE_SV39X4 = 8
HGATP_MODE_SV48X4 = 9
HGATP_MODE_SV57X4 = 10

# msiptp.mode
MSIPTP_MODE_OFF  = 0
MSIPTP_MODE_FLAT = 1

# =============================================================================
# Sv39 PTE フォーマット
# =============================================================================
# bits [9:0]   : flags + RSW
# bits [53:10] : PPN (44 bits)
# bits [63:54] : reserved
PTE_V = 1 << 0     # Valid
PTE_R = 1 << 1     # Read
PTE_W = 1 << 2     # Write
PTE_X = 1 << 3     # eXecute
PTE_U = 1 << 4     # User accessible
PTE_G = 1 << 5     # Global
PTE_A = 1 << 6     # Accessed
PTE_D = 1 << 7     # Dirty

# よく使うプリセット
PTE_LEAF_RWX_AD     = PTE_V | PTE_R | PTE_W | PTE_X | PTE_U | PTE_A | PTE_D
PTE_LEAF_R_AD       = PTE_V | PTE_R | PTE_U | PTE_A
PTE_LEAF_RW_AD      = PTE_V | PTE_R | PTE_W | PTE_U | PTE_A | PTE_D
PTE_LEAF_X_AD       = PTE_V | PTE_X | PTE_U | PTE_A
PTE_NONLEAF         = PTE_V                     # 中段: V のみ立てる

# =============================================================================
# Fault Queue record フォーマット (32 byte)
# =============================================================================
# spec section 3.7 Figure 4
#   DW0: cause[11:0] | PID[19:0] | PV[1] | PRIV[1] | TTYP[6] | DID[24]
#   DW1: iotval (= original IOVA)
#   DW2: iotval2 (= GPA in case of guest page fault)
#   DW3: reserved
FQ_RECORD_SIZE = 32

# =============================================================================
# Fault cause codes (spec section 3.7.2 Table 9)
# =============================================================================
CAUSE_INSTRUCTION_ACCESS_FAULT       = 1
CAUSE_DATA_CORRUPTION                = 2     # spec extension
CAUSE_LOAD_ADDR_MISALIGNED           = 4
CAUSE_LOAD_ACCESS_FAULT              = 5
CAUSE_STORE_ADDR_MISALIGNED          = 6
CAUSE_STORE_ACCESS_FAULT             = 7
CAUSE_INSTRUCTION_PAGE_FAULT         = 12
CAUSE_LOAD_PAGE_FAULT                = 13
CAUSE_STORE_PAGE_FAULT               = 15
CAUSE_INSTRUCTION_GUEST_PAGE_FAULT   = 20
CAUSE_LOAD_GUEST_PAGE_FAULT          = 21
CAUSE_STORE_GUEST_PAGE_FAULT         = 23

# IOMMU 固有 cause
CAUSE_ALL_INBOUND_DISALLOWED      = 256
CAUSE_DDT_ENTRY_LOAD_ACCESS_FAULT = 257
CAUSE_DDT_ENTRY_INVALID           = 258
CAUSE_DDT_ENTRY_MISCONFIGURED     = 259
CAUSE_TTYP_BLOCKED                = 260
CAUSE_MSI_PT_LOAD_ACCESS_FAULT    = 261
CAUSE_MSI_PT_ENTRY_INVALID        = 262
CAUSE_MSI_PT_MISCONFIGURED        = 263
CAUSE_MRIF_ACCESS_FAULT           = 264
CAUSE_PDT_ENTRY_LOAD_ACCESS_FAULT = 265
CAUSE_PDT_ENTRY_INVALID           = 266
CAUSE_PDT_ENTRY_MISCONFIGURED     = 267
CAUSE_DDT_DATA_CORRUPTION         = 268
CAUSE_PDT_DATA_CORRUPTION         = 269
CAUSE_MSI_PT_DATA_CORRUPTION      = 270
CAUSE_MSI_MRIF_DATA_CORRUPTION    = 271
CAUSE_INTERNAL_DATAPATH_FAULT     = 272
CAUSE_IOMMU_MSI_WRITE_ACCESS_FAULT = 273
CAUSE_PT_DATA_CORRUPTION          = 274  # first/second-stage PT data corruption

# (旧名称の互換 alias)
CAUSE_MSI_ADDR_TYPE_FAULT         = CAUSE_IOMMU_MSI_WRITE_ACCESS_FAULT

# TTYP 値 (riscv-iommu spec 1.0 §3.7.2 Table 9)
# ★ execute (instruction fetch) 用の枠が 1 に入る点に注意
TTYP_NONE                       = 0
TTYP_UNTRANSLATED_RD_FOR_EXEC   = 1   # 命令フェッチ (untranslated)
TTYP_UNTRANSLATED_RD            = 2   # 普通の load (untranslated)  ← 普通の read fault
TTYP_UNTRANSLATED_WR            = 3   # store/AMO (untranslated)
TTYP_TRANSLATED_RD_FOR_EXEC     = 4
TTYP_TRANSLATED_RD              = 5
TTYP_TRANSLATED_WR              = 6
TTYP_PCIE_ATS_TRANSLATION       = 7
TTYP_PCIE_MSG_REQUEST           = 8

# (旧名称の互換 alias — そのうち削除)
TTYP_UNTRANSLATED_INSTR  = TTYP_UNTRANSLATED_RD_FOR_EXEC
TTYP_TRANSLATED_INSTR    = TTYP_TRANSLATED_RD_FOR_EXEC

# =============================================================================
# Command Queue (CQ) — opcode/funct3 (spec section 3.1)
# =============================================================================
# 各 command は 16 byte。
# DW0 lower 7 bit = opcode, [9:7] = funct3, etc.
CMD_OPCODE_IOTINVAL = 1
CMD_OPCODE_IOFENCE  = 2
CMD_OPCODE_IODIR    = 3
CMD_OPCODE_ATS      = 4

# IOTINVAL funct3
IOTINVAL_FUNC3_VMA  = 0
IOTINVAL_FUNC3_GVMA = 1

# IOFENCE funct3
IOFENCE_FUNC3_C     = 0

# 共通フラグ
CMD_FLAG_PV = 1 << 32   # process valid (DW0[32])
CMD_FLAG_DV = 1 << 33   # device valid  (DW0[33])
CMD_FLAG_AV = 1 << 32   # address valid (IOFENCE.C, DW0[32])
CMD_FLAG_WSI = 1 << 33  # WSI (IOFENCE.C)
CMD_FLAG_GV = 1 << 33   # GSCID valid (IOTINVAL.GVMA)


# =============================================================================
# 既定のメモリレイアウト (テストで共通に使う PPN 割当て)
# =============================================================================
# ds_ram (1 MiB) 内の PPN 配置:
#   0x10  : DDT (1 page)
#   0x11  : S1 PT root (level 2)
#   0x12  : S1 PT mid  (level 1)
#   0x13  : S1 PT leaf (level 0)
#   0x14  : G  PT root (Sv39x4 用、stage-2 を使うとき)
#   0x15  : G  PT mid
#   0x16  : G  PT leaf
#   0x20  : Command Queue (size 256 entry × 16 byte = 4 KiB)
#   0x21  : Fault Queue   (size 256 entry × 32 byte = 8 KiB → 2 page)
DEFAULT_DDT_BASE_PPN = 0x10
DEFAULT_S1_ROOT_PPN  = 0x11
DEFAULT_S1_MID_PPN   = 0x12
DEFAULT_S1_LEAF_PPN  = 0x13
DEFAULT_G_ROOT_PPN   = 0x14
DEFAULT_G_MID_PPN    = 0x15
DEFAULT_G_LEAF_PPN   = 0x16
DEFAULT_CQ_BASE_PPN  = 0x20
DEFAULT_FQ_BASE_PPN  = 0x21

# Queue サイズ (entry 数 = 2^log2sz)
DEFAULT_CQ_LOG2SZ = 7   # 128 entry × 16 byte = 2 KiB
DEFAULT_FQ_LOG2SZ = 7   # 128 entry × 32 byte = 4 KiB