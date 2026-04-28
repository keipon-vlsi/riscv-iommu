"""Top test driver for rv_iommu_ptw_sv39x4_pc.
Individual test cases live in scenario/test_directed.py, test_fault.py, test_random.py.
This file provides a coverage summary test (runs last).
"""

import cocotb
from tb_coco.common.helpers import report_br_coverage

# All BR-IDs expected from the module card §6.
# BR13/BR32/BR33 require MSITrans!=DISABLED — excluded from coverage target.
_EXPECTED_BRS = [
    "BR01", "BR02", "BR03", "BR04", "BR05",
    "BR06", "BR07", "BR08", "BR09", "BR10",
    "BR11", "BR12",
    # BR13 – UNTESTABLE (MSITrans=DISABLED)
    "BR14", "BR15", "BR16", "BR17", "BR18",
    "BR19", "BR20", "BR21", "BR22", "BR23",
    "BR24", "BR25", "BR26", "BR27", "BR28",
    "BR29", "BR30", "BR31",
    # BR32, BR33 – UNTESTABLE (MSITrans=DISABLED)
]


@cocotb.test()
async def test_zzz_coverage_summary(dut):
    """Coverage summary. Always runs last (zzz prefix). Covers: all BRs."""
    report_br_coverage(dut, _EXPECTED_BRS)
