"""iommu_tb — RISC-V IOMMU 用 cocotb テストベンチ・ライブラリ

新しいテストファイルは原則これ 1 つを import すれば足りる:
    from iommu_tb import IommuEnv, PTE_LEAF_RWX_AD, CAUSE_LOAD_PAGE_FAULT, ...

低レイヤ API を直接触りたい場合は submodule から:
    from iommu_tb.memory import build_dc, make_pte
    from iommu_tb.regs   import write_reg64, read_reg64
"""

# ----- Env (中心 API) -----
from .env import IommuEnv, reset_dut

# ----- 定数 (test 側で直接参照しがちなもの) -----
from .const import (
    # registers
    REG_CAPABILITIES_L, REG_FCTL, REG_DDTP_L, REG_CQB_L, REG_FQB_L,
    REG_CQH, REG_CQT, REG_FQH, REG_FQT,
    REG_CQCSR, REG_FQCSR, REG_IPSR,

    # ddtp
    DDTP_MODE_OFF, DDTP_MODE_BARE, DDTP_MODE_1LVL, DDTP_MODE_2LVL, DDTP_MODE_3LVL,
    DDTP_MODE_MASK, DDTP_BUSY_BIT, DDTP_PPN_SHIFT,

    # fctl
    FCTL_BE, FCTL_WSI, FCTL_GXL,

    # tc / DC
    DC_SIZE,
    TC_V, TC_EN_ATS, TC_EN_PRI, TC_T2GPA, TC_DTF, TC_PDTV,
    TC_PRPR, TC_GADE, TC_SADE, TC_DPE, TC_SBE, TC_SXL,

    # mode (satp 系)
    ATGP_MODE_BARE, ATGP_MODE_SV39, ATGP_MODE_SV48, ATGP_MODE_SV57,
    HGATP_MODE_BARE, HGATP_MODE_SV39X4,

    # PTE flags
    PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_G, PTE_A, PTE_D,
    PTE_LEAF_RWX_AD, PTE_LEAF_R_AD, PTE_LEAF_RW_AD, PTE_LEAF_X_AD, PTE_NONLEAF,

    # fault causes
    CAUSE_INSTRUCTION_ACCESS_FAULT,
    CAUSE_LOAD_ACCESS_FAULT, CAUSE_STORE_ACCESS_FAULT,
    CAUSE_INSTRUCTION_PAGE_FAULT, CAUSE_LOAD_PAGE_FAULT, CAUSE_STORE_PAGE_FAULT,
    CAUSE_INSTRUCTION_GUEST_PAGE_FAULT,
    CAUSE_LOAD_GUEST_PAGE_FAULT, CAUSE_STORE_GUEST_PAGE_FAULT,
    CAUSE_DDT_ENTRY_INVALID, CAUSE_DDT_ENTRY_MISCONFIGURED,
    CAUSE_PDT_ENTRY_INVALID, CAUSE_PDT_ENTRY_MISCONFIGURED,

    # ttyp
    TTYP_UNTRANSLATED_RD, TTYP_UNTRANSLATED_WR, TTYP_UNTRANSLATED_INSTR,
    TTYP_TRANSLATED_RD, TTYP_TRANSLATED_WR,

    # PPN プリセット
    DEFAULT_DDT_BASE_PPN,
    DEFAULT_S1_ROOT_PPN, DEFAULT_S1_MID_PPN, DEFAULT_S1_LEAF_PPN,
    DEFAULT_G_ROOT_PPN,  DEFAULT_G_MID_PPN,  DEFAULT_G_LEAF_PPN,
    DEFAULT_PDT_ROOT_PPN, DEFAULT_PDT_L1_PPN, DEFAULT_PDT_LEAF_PPN,
    DEFAULT_CQ_BASE_PPN, DEFAULT_FQ_BASE_PPN,
    # Process Context 固定値
    PC_PROCESS_ID_FIXED, PC_PSCID_FIXED,
)

# ----- 個別 API (高度な用途) -----
from .memory import (
    make_pte, vpn_indices_sv39, vpn_indices_sv39x4,
    build_dc, build_dc_identity, build_dc_sv39_s1,
    build_dc_sv39x4_s2, build_dc_sv39_2stage,
    build_dc_sv39_s1_pc, build_dc_sv39x4_s2_pc, build_dc_sv39_2stage_pc,
    install_dc_1lvl, install_pdt_pd20,
    pack_pc_ta, pack_pc_fsc, pack_pdte,
    PDT_MODE_PD20,
    setup_sv39_4k, setup_sv39_2m, setup_sv39_1g, setup_sv39_custom_leaf,
    pack_satp_like, pack_iohgatp, pack_ddtp,
)
from .regs import (
    write_reg64, read_reg64, write_reg32, read_reg32, poll_reg,
    configure_ddt_mode,
)
from .faultq import FaultQueue, FaultRecord, decode_fault_record, expect_fault
from .cmdq   import CommandQueue


__all__ = [
    "IommuEnv", "reset_dut",
    "FaultQueue", "FaultRecord", "decode_fault_record", "expect_fault",
    "CommandQueue",
    # 残りは module 名としてもアクセス可能。__all__ に列挙はしない (長すぎる)。
]
