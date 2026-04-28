# Must-Test List: `<module_name>`

> **書き方**: Claude が網羅できないドメイン固有の項目だけを bullet で。
> **書かないこと**: BR 全件カバーや cross-product (Claude が機械的にやる)。
> **目標**: 15-30 項目程度。これを Claude に渡して /create-tb で展開する。

---

## 1. ドメイン経験から来る "絶対外せない" シナリオ

<!-- 例: 過去にバグった、仕様の曖昧な部分、テスト設計者の直感 -->

- [ ] (例) Nested walk で S2 leaf の U=0 を踏む — 過去にここで bug
- [ ] (例) `req_trans_i` を walk 完了前に下げる — IOTLB ヒット信号がクリアされる既知制約
- [ ] (例) DDTC ミス + PTW 同時発生時の競合
- [ ] (例) PCIe ATS Translated Request + T2GPA=1 の組合せ
- [ ] (例) ...

## 2. 仕様の "ここは試したい" 解釈

<!-- 仕様書を読んで「これ実装ちゃんとできてる?」と思った箇所 -->

- [ ] (例) Spec §3.6 の MSI アドレス判定: gpaddr が境界値 (mask 全 1, 全 0) のとき
- [ ] (例) Spec §3.4 の A/D ビット更新: hardware update vs software update の切替
- [ ] (例) Cause code の優先順位: 複数のフォルト条件が同時成立した時 (Table 13 の順序)
- [ ] (例) ...

## 3. プロジェクトのバグ履歴 (再発防止)

<!-- doc/design-log.md と doc/feedback.md から拾う。同じバグを TB で踏み続けないため -->

- [ ] (例) 2026-04-23: `bare set` バグ — テスト初期化抜けの検出
- [ ] (例) 2026-04-25: VPN2 を 9bit と勘違い — Sv39x4 で必ず 11bit テスト
- [ ] (例) ...

## 4. 跨モジュール相互作用 (このモジュール単体テストで意識すべき)

<!-- 上流/下流 が動的に状態変える時の取り扱い -->

- [ ] (例) CDW が暗黙的アクセスを発行中に外部 init_ptw がさらに来る
- [ ] (例) IOTLB flush 中の lookup
- [ ] (例) ...

## 5. リスクが高い箇所 (要重点テスト)

<!-- 設計時に「ここは怪しい」と感じた箇所 -->

- [ ] (例) FSM の ERROR 状態からの復帰経路
- [ ] (例) 例外的に長い AXI burst (7 DW)
- [ ] (例) ...

## 6. 性能 / タイミング寄りの懸念

<!-- 機能テストとは別軸 -->

- [ ] (例) Back-to-back 100 件のスループット
- [ ] (例) AXI ready=0 が長期間 (1000 cycle) 持続
- [ ] (例) ...

---

## Claude への引き継ぎ用プロンプト (このリスト完成後)

```
doc/test-plan/<module>.md を作成してください。
ベースは以下:

1. doc/_template/test_plan_template.md (構造)
2. doc/_template/coverage_methodology.md (網羅戦略)
3. doc/modules/<module>.md (BR-ID 一覧、§6)
4. doc/test-plan/_must_test_<module>.md (必須シナリオ)

特に上記 4 (must_test) の全項目は **必ず T-ID として含める**。
そのうえで methodology の機械的網羅を適用してください。
```

---

## 書き方のコツ

### ✅ 良い must-test 項目

- "Sv39x4 G-stage で leaf U=0 を踏む" ← 仕様の細かい知識
- "AXI SLVERR を L0 / L1 / L2 各レベルで注入" ← 経験的な脆弱箇所
- "back-to-back 後の TLB ヒット" ← よくあるバグパターン

### ❌ 避けたい (Claude が自動でやる)

- "全 BR-ID をカバー" ← methodology が自動でやる
- "R/W/X の 8 通り全部" ← cross-product を Claude が列挙
- "正常系の基本 walk" ← Claude のデフォルト

---

## ファイル名規則

このファイルは `doc/test-plan/_must_test_<module>.md` として保存。
`_` プレフィックスは "Claude が自動生成しない" 印。

```
doc/test-plan/
├── _must_test_rv_iommu_ptw_sv39x4_pc.md   ← 人間が書く (このファイル)
└── rv_iommu_ptw_sv39x4_pc.md              ← Claude が生成する正本
```