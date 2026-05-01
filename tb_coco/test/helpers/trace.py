"""iommu_tb.trace — 波形デバッグ用の internal-signal アクセス helper

Verilator は --public-flat-rw 付きで build しているはずなので、
hierarchy 経由で IOMMU 内部の信号を覗ける。
"""


def _safe_get(dut, dotted: str):
    """`a.b.c` 形式の文字列で getattr を辿る。存在しなければ None。"""
    obj = dut
    for part in dotted.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


# 一般によく見たい IOMMU 内部信号 (top instance 名は i_dut で始まる前提)
INSPECT_PATHS = {
    # CDW (DDT/PDT walker)
    "cdw_state":     "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_cdw_pc.state_q",
    "cdw_entry_cnt": "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_cdw_pc.entry_cnt_q",
    "dc_tc_q":       "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_cdw_pc.dc_tc_q",
    "dc_iohgatp_q":  "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_cdw_pc.dc_iohgatp_q",
    "dc_fsc_q":      "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_cdw_pc.dc_fsc_q",

    # PTW (Sv39x4)
    "ptw_state":     "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_ptw.state_q",
    "ptw_lvl":       "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_ptw.ptw_lvl_q",
    "ptw_pte":       "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_ptw.ptw_pte_q",
    "ptw_cause":     "i_dut.i_rv_iommu_translation_wrapper.gen_pc_support."
                     "i_rv_iommu_tw_sv39x4_pc.i_rv_iommu_ptw.cause_q",

    # Top translation wrapper out
    "trans_valid":   "i_dut.i_rv_iommu_translation_wrapper.trans_valid_o",
    "spaddr":        "i_dut.i_rv_iommu_translation_wrapper.spaddr_o",
    "trans_error":   "i_dut.i_rv_iommu_translation_wrapper.trans_error_o",
}


def snapshot(dut) -> dict:
    """登録済み内部信号の現在値を dict に。print/log 用。"""
    out = {}
    for name, path in INSPECT_PATHS.items():
        h = _safe_get(dut, path)
        try:
            out[name] = int(h.value) if h is not None else None
        except Exception:
            out[name] = None
    return out


def format_snapshot(snap: dict) -> str:
    lines = []
    for k, v in snap.items():
        lines.append(f"  {k:14s} = {v if v is None else hex(v)}")
    return "\n".join(lines)
