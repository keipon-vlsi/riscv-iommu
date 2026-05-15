# RISC-V IOMMU プレゼン骨子

- 発表時間: 15 分
- 質疑応答: 15 分
- スライド: 13 枚 (= 本編 12 + まとめ 1)
- 目標: IOMMU 全体を理解していることと、その中での自分の到達度を正確に示す

---

## スライド構成

| #  | タイトル | 時間 | 主な内容 |
|----|---------|------|---------|
| 1  | Title / 発表の流れ | 30 s | プロジェクト名、自己紹介、5 行 outline |
| 2  | IOMMU とは | 60 s | 役割 (= device DMA を仮想化 / 隔離)、システムの中で居る位置、無いと何が困るか |
| 3  | RISC-V IOMMU spec のスコープ | 60 s | Sv39 / Sv39x4、 DDT / PDT、 S1 / S2、 IOTLB、 PASID、 spec 全体のうち今回触ったところを薄く色付け |
| 4  | タスクと自分のスコープ | 90 s | 出発点の RTL、 「OoO / pipeline 化に向けた refactoring」 という自分で定めた目標、 in-scope (= 翻訳パス全体) と out-of-scope (= MSI 完全実装 / HW A/D は今回スコープ外) を明示 |
| 5  | Design の方針 | 90 s | 「全 cache が SPA を保持」 という不変条件、 walker を pt_walker と walk_ctrl に分離、 DDTW と PDTW を分割、 何を解きたかったか (= testability + 将来 OoO + 責務分離) |
| 6  | マイクロアーキテクチャ 全体図 | 120 s | block diagram、 DDTC/PDTC/IOTLB-S1/IOTLB-S2/DDTW/PDTW/PTW、 AXI トポロジ (= internal masters → axi4_bc → ds_req_o)、 各 walker の責務マトリクス |
| 7  | Walker 共通 FSM パターン | 90 s | IDLE/ISSUE/WAIT/PROC/ERROR の 5 state + Phase 直交分離、 init の rising edge 内部検出、 PROC で検査 → 分岐、 なぜこれが OoO 化への布石になるか |
| 8  | 検証環境 | 90 s | cocotb 2.0 + Verilator 5.046、 libiommu C reference を golden に replay-driven、 18 カテゴリ × 全 ~140k ケース (quick tier 10,382)、 Docker で env を pin |
| 9  | 検証結果 | 90 s | 10,382 ケース全完走、 PASS率の breakdown、 残る ~20 cases (= s2_only iotval2) の位置づけ、 cause / iotval / ttyp は全一致 |
| 10 | 到達度の自己評価 | 60 s | 「機能完成度」 と「検証完成度」 を分けてマップ、 自分は今ここ、 という到達度を 1 枚で図示 |
| 11 | 製品化に向けて足りないもの | 60 s | MSI translation 完全実装、 HW A/D 更新、 OoO walks (= refactor が活きる)、 power/area opt、 formal verification |
| 12 | トレーニングを通して | 60 s | 学んだこと、 一番時間を取られた箇所 (= PTW hang debug, AXI バーストの罠)、 次やるなら最初にやること |
| 13 | まとめ + 質疑へ | 30 s | 3 行サマリ、 「ここから質問よろしくお願いします」 |

合計 ~15 分 (本編 14 分 + バッファ 1 分)

---

## Appendix slides (= 質疑用の backup)

質疑 15 分は長いので、 想定 Q への 1 枚答えを appendix に仕込んでおくと「準備されている」 評価になります。 用意したい backup:

- **A1**: なぜ cocotb? UVM 比較
- **A2**: 全 cache に SPA を保持する設計の area / latency への影響
- **A3**: OoO 化するときに必要な追加機構 (= multi-master arbitration、 hazard 検出)
- **A4**: libiommu との順序差 (shifted-match) をどう許容したか
- **A5**: bad_gpaddr / iotval2 計算の実装案
- **A6**: AXI BURST_FIXED に至った経緯 (= デバッグ履歴)
- **A7**: テストケース生成戦略の詳細
- **A8**: 残課題の見積もり工数

---

## プリトレーニング発表として意識すること

### 1. 「全体の中で自分の位置」 を最初に確定させる

slide 3 で spec の全体図を出し、その上に自分の touched area を色付けする。 これで「 spec を理解している」 と「自分のスコープを把握している」 を同時に証明できる。 audience は senior engineer なので、 全体感が無いとすぐ見抜かれる。

### 2. 「やったこと」 ではなく「決断とその根拠」 を中心に語る

slide 5, 6, 7 が肝。 「 DDTW と PDTW を分けた」 ではなく「翻訳責任の再配分のために分けた、 これによりこういう trade-off が発生したが、 testability を優先した」 という構造にする。 「結果」 より「思考過程」 が評価される段階。

### 3. 残課題と未着手を堂々と出す

slide 10, 11。 これを隠すと「自己評価ができない」 と見られる。 逆に「ここまで実装、 ここは未着手で残工数 X 時間、 ここはスコープ外で意図的に切り捨て」 と整理されていると「設計判断ができる人」 と見られる。

### 4. 検証の「方法論」 まで含めて見せる

slide 8 が大事。 「 10,382 PASS」 だけでは「ベンチが甘いだけかも」 と疑われる。 「 libiommu reference を golden に、 全 18 カテゴリ replay-driven、 順序差は shifted-match で許容」 と方法を見せると、 結果の信頼性まで一緒に伝わる。

### 5. 「学び」 は再現可能な形で書く

slide 12 を「楽しかったです」 で終わらせない。 「最も時間を取られたのは X (= PTW の WAIT で hang する原因が `BURST_INCR` だったこと)」 「次やるなら最初に Y (= 既存 PTW の AXI 信号を完全 trace してから写経する)」 のように、 take-away を後任が再利用できる粒度で書く。 これが pretraining の質を測る指標になる。

### 6. 質疑に「布石」 を仕込む

15 分質疑があるので、 発表中にあえて深堀りしない論点を残す。 例えば「全 cache SPA 設計の area 影響は appendix に試算あります」 と一言入れておく。 これで質問が誘導でき、 議論の主導権が取れる。

### 7. デモ / 動画があるなら入れる

可能なら waveform の一例 (= PTW walk の典型遷移) を 1 枚 slide で見せると視覚的に強い。 重い波形なら別ファイルで appendix にしておき、 質疑で見せられるよう準備。

### 8. 時間配分は実測してから整える

15 分のプレゼンは想像より早く過ぎる。 6-9 (= micro-arch + 検証) が山場なので、 ここに 7-8 分を割く設計。 練習で実測して、 早く流れすぎる箇所と詰まる箇所を把握する。

### 9. 「英語スライド + 日本語発表」 が無難 (= 環境による)

社内文化に合わせるが、 spec 用語 (= DDT, PDT, IOTLB, Sv39x4 等) は英語のまま、 説明文だけ日本語、 が多くの場で読みやすい。

### 10. レビュアー視点での自己チェック

発表前に以下を自問:
- このスライドを 30 秒で説明できるか
- 「なぜ?」 と聞かれて答えられるか
- 1 枚に情報が多すぎて文字を読まれていないか
- 自分の貢献と既存実装の境界が明確か
- 数字を出すときは出典 (= cocotb log) が明示されているか

---

## 補足: スライドの中で「到達度」 を正確に伝える具体策

「設計者として完成」 と「検証者として完成」 と「製品として完成」 は別の軸。 これを 1 枚にマップして示すと、 自分が今どこに居るかが一目瞭然になる:

```
                  低                     高
  機能設計        [████████████░░░░░░░]      ← Sv39x4 / PC walk まで実装、 MSI 残
  実装           [██████████░░░░░░░░░░]      ← refactor 完了、 superpage output 残
  検証 (機能)     [█████████████████░░░]     ← 10,382/10,382 (= quick tier)
  検証 (full tier)[██████░░░░░░░░░░░░░]      ← nightly 未走、 ~140k ケース
  製品化適合      [███░░░░░░░░░░░░░░░░░]     ← MSI / HW A/D / power 未着手
```

このマトリクスは slide 10 に 1 枚で入れると「自己評価が calibrated されている」 と伝わる。
