# gen_vectors — Phase 1 Golden Vector Generator

This directory contains a small C harness that drives the **ved-rivos/iommu-reference** model (the spec author's golden reference implementation) to enumerate every PTE-flag combination × placement level × access type for our IOMMU testbench, and emits the reference model's response as a JSONL file.

## What it generates

Phase 1 scope (Sv39 1-stage walk, PDTV=0, G-stage Bare):

| Category | Cases |
| :--- | ---: |
| Leaf level (level=0, all 256 V/R/W/X/U/G/A/D combinations × {read, write}) | 512 |
| Non-leaf mid (level=1, all 256 × read) | 256 |
| Non-leaf root (level=2, all 256 × read) | 256 |
| Reserved-bit patterns (10 single + 90 random in PTE bits[63:54]) | 100 |
| **Total** | **1124** |

For non-leaf placements that have R=1 or X=1 (= would be a superpage leaf in the spec), we deliberately use a **misaligned PPN** (low bit set) so that even RTLs that happen to support superpages will fault deterministically (per Phase 1 Q1 case B).

## Output format (JSONL — one record per line)

```json
{"case_id":0,"name":"leaf_lvl0_f00_r","level":0,"flags":0,
 "access":"read","rsvd_pattern":0,
 "status":1,"PPN":"0x0","S":0,
 "fault":{"cause":13,"iotval":"0x2345","iotval2":"0x0","ttyp":2,"did":0}}
```

Fields:
- `status`: `0=SUCCESS`, `1=UNSUPPORTED_REQUEST`, `4=COMPLETER_ABORT`
- `PPN`/`S`: from rsp.trsp (translated PPN and superpage flag)
- `fault`: FQ record contents if a fault was raised, else `null`
  - `cause`: spec §4.2 Table 13 cause code (e.g. 13 = Read page fault)
  - `iotval`: the original IOVA (per spec §4.2)
  - `ttyp`: spec §4.2 Table 14 (2 = Untranslated read, 3 = Untranslated write/AMO)

## Build

Prerequisite: `libiommu.a` and `libtables.a` must be built in the iommu_ref_model checkout. See top-level README for that.

```bash
# (1) Make sure the libraries are built
cd /Users/keipon/Desktop/project/tt_pretraining/riscv-iommu/iommu_ref_model
make -C libiommu
make -C libtables
ls libiommu/libiommu.a libtables/libtables.a    # confirm both present

# (2) Build gen_vectors
cd /Users/keipon/Desktop/project/tt_pretraining/riscv-iommu-kawano/tb_coco/test/reference/gen_vectors
make
```

If `IOMMU_REF_DIR` is not the default path, override:

```bash
make IOMMU_REF_DIR=/path/to/iommu_ref_model
```

## Run

```bash
make run
# Equivalent: ./gen_vectors > golden_vectors.jsonl
```

Expected output:
- `golden_vectors.jsonl` with 1124 lines
- stderr: `✓ generated 1124 cases`

## Sanity checking the output

Quick checks you can run:

```bash
# Total line count
wc -l golden_vectors.jsonl
# expected: 1124

# Distribution of status codes
grep -oE '"status":[0-9]+' golden_vectors.jsonl | sort | uniq -c
# expected: many UR (status=1) for fault cases, some SUCCESS (status=0) for valid leaf

# Distribution of fault causes
grep -oE '"cause":[0-9]+' golden_vectors.jsonl | sort | uniq -c
# expected: mostly 13 (Read PF) and 15 (Store/AMO PF)

# Show one success case (should be a fully-valid RWXAD leaf with read access)
grep '"name":"leaf_lvl0_fdf_r"' golden_vectors.jsonl
# (flag 0xDF = V|R|W|X|U|A|D = 1101 1111)

# Show V=0 leaf, read access (expected fault cause=13)
grep '"name":"leaf_lvl0_f00_r"' golden_vectors.jsonl
```

## Next step

Once `golden_vectors.jsonl` is generated, the Python side (`helpers/golden.py` + `helpers/predict.py`) consumes it to:
1. Validate `predict_outcome()` against the golden vectors (one-shot check)
2. Use `predict_outcome()` in cocotb tests for runtime expected-value generation

That validation script and the helpers are deliverable in the next iteration.

## Troubleshooting

**Symptom:** `gcc: error: -liommu: cannot find ...`
**Cause:** `libiommu.a` not built or `IOMMU_REF_DIR` path wrong.
**Fix:** `cd $IOMMU_REF_DIR && make -C libiommu && make -C libtables` and verify `.a` files exist.

**Symptom:** Many "configure_iommu_phase1 failed" or "enable_fault_queue failed" stderrs.
**Cause:** `reset_iommu()` rejected the capabilities/fctl combination.
**Fix:** Compare with `iommu_ref_model/test/test_app.c` initial `cap` setup — adjust `configure_iommu_phase1()` flags accordingly.

**Symptom:** Output looks empty or all SUCCESS.
**Cause:** FQ not enabled correctly, or DC/PT not placed correctly.
**Fix:** Add `fprintf(stderr, "case %d: ...\n", tc->case_id)` debug prints in `run_case()` to trace.