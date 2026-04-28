# Coverage Methodology

Claude がテストプラン生成時に **必ず参照** する網羅戦略。
`/create-tb` の Phase A で読み込み、この文書のチェックリスト全項目を適用する。

---

## 1. 網羅の 5 つの切り口

全テストは以下 5 視点から生成される。**どの切り口も漏らさない**。

### 切り口 A: RTL 構造 (内部から)

- **各 BR-ID** (モジュールカード §6) → 真/偽パスそれぞれに 1 テスト以上
- **各 FSM 遷移** (モジュールカード §4.2) → 遷移トリガを発生させるテスト
- **各非同期 reset** → reset アサート中の挙動 + reset 解除直後
- **各 always_ff の初期値** → 初期状態の検査

### 切り口 B: 仕様書 (外部から)

- **仕様書の全 Table** → 1 行 1 テスト
    - 例: RISC-V IOMMU Spec Table 13 (Cause codes) の 15 行
    - 例: Sv39 PTE encoding の 8 通り (R/W/X 組合せ)
- **仕様書の SHALL / MUST 文** → 違反検出のテスト
- **仕様書の Figure / Example** → シナリオ再現テスト
- **仕様書のエンコード表** → 合法/違法の両方をカバー

### 切り口 C: 入力空間 (データ視点)

- **各入力の境界値**:
    - 0, maximum, alignment boundary, sign boundary
    - bit-width が Sv39 なら bit 38 の canonical/non-canonical
- **Cross-product** (2-3 入力の組合せを全列挙):
    - `R × W × X` (PTE 権限)
    - `priv_lvl × pte.U × SUM` (権限チェック)
    - `en_1S × en_2S × iova_is_msi` (モード)
    - `trans_type × pte.d` (Store + Dirty bit)
- **違法エンコード**:
    - PTE の reserved bit ≠ 0
    - R=0, W=1 (reserved encoding)
    - 未定義 trans_type

### 切り口 D: タイミング (時間視点)

- **Back-to-back** operations (連続要求)
- **Stall / backpressure** (ready=0 が N サイクル持続)
- **Mid-operation reset** (walk 中に rst_ni 下げる)
- **Concurrent events** (同時に複数の入力変化)
- **Single-cycle pulse** (1 cycle のみ High)
- **Late deassert** (valid/ready 遅延)

### 切り口 E: 異常系 (攻撃視点)

- **リソース枯渇**: キャッシュ満杯、キュー満杯
- **バスエラー**: RRESP / BRESP != OKAY の各種
- **Protocol violation**: valid=1 で req を途中で下げる等
- **Timeout**: 応答が戻ってこない
- **Invalid 構造体**: DDT/PDT/PT の Invalid PTE, corrupt entry

---

## 2. テスト生成アルゴリズム (Claude の思考手順)

`/create-tb` Phase A で、Claude は以下を順に実行すること。

### Step 1: RTL の系統的分析

```
目標: RTL から出せる全テストを列挙

1. モジュールカード §6 の全 BR-ID を列挙 (N 個)
2. 各 BR-ID に対して:
   - True パスを直接トリガーする directed テスト を 1 つ追加
   - False パスをトリガーするテスト を 1 つ追加
3. モジュールカード §4 の全 FSM 遷移を列挙 (M 個)
4. 各遷移に対して:
   - トリガー条件を満たすテスト を 1 つ追加
5. 各入力ポートを列挙:
   - bit 幅から境界値を特定 (0, max, bit 中央値)
   - 各境界値でのテスト を 1 つ追加
```

### Step 2: 仕様書の mining

```
目標: spec から出せる全テストを列挙

1. モジュールカード §13「関連仕様」の参照を全て開く
2. 参照章内の Table を列挙:
   - Cause code 表 → 各行 1 テスト
   - Encoding 表 → 各エントリ 1 テスト (valid) + 境界 1 テスト (invalid)
   - 権限表 → 各組合せ 1 テスト
3. 参照章内の "SHALL"/"MUST" を Grep で抽出:
   - 各文について、従う/違反の 2 ケース
```

### Step 3: Cross-product 網羅

```
目標: 交差網羅

当該モジュールに関係する入力の組合せを列挙:
- PTE の R/W/X: 8 通り (非 leaf 除いて 6)
- priv × pte.U × SUM: 8 通り
- en_1S × en_2S: 4 通り
- access_type × stage_mode: 3 × 4 = 12 通り

各組合せに対して 1 テスト (期待値は golden model から)。
```

### Step 4: タイミング / Edge case

以下を **全てチェック** (該当すれば必ずテスト追加):

```
☐ Back-to-back request (同じ入力で連続 2 回)
☐ 違う入力での連続 request
☐ Reset during operation (walk 中に rst_ni=0)
☐ Backpressure (ready=0 が 10/100/1000 cycle 持続)
☐ Flush during lookup (lookup 中に flush 入る)
☐ Single-cycle trigger (trigger pulse 1 cycle)
☐ Late response (応答が N cycle 後)
☐ Boundary alignment (4K / 2M / 1G boundary)
☐ Sign extension boundary (Sv39 iova bit 38 周辺)
```

### Step 5: ランダム網羅 (統計的)

```
目標: directed で届かない状態を統計的にカバー

1. 入力ごとにランダム生成方針を決定:
   - IOVA: random 39-bit (with valid canonical)
   - PTE: random flags (V=1 固定、他はランダム、無効組合せ 20%)
   - access_type: 均等 3 択
2. ケース数: 100 件 / 関数 (最低)
3. seed は明示的に固定 (再現性)
4. 期待値は golden model 経由
```

### Step 6: プロジェクト固有項目

プロジェクト (riscv-iommu-kawano) 特有のポイント:

```
☐ req_trans_i の High 保持制約 (完了まで)
☐ MSITrans 設定別の挙動 (DISABLED / FLAT_ONLY / FLAT_MRIF)
☐ InclPC の有無 (Process Context 対応)
☐ Force 方式で置き換えられるシナリオ
☐ CDW 暗黙的変換
```

---

## 3. ケース数の目安

BR-ID 数に対する最低テスト数の目安:

| BR-ID 数 | Directed 最低 | Random 最低 | Fault 最低 |
|---|---|---|---|
| 〜 10 | BR 数 × 2 | 100 | 各 BR 種別 |
| 10 〜 30 | BR 数 × 1.5 | 200 | 各 BR 種別 |
| 30+ | BR 数 + 重要交差 | 300+ | 各 BR 種別 + cross |

「directed で BR 数 × 2」の内訳: 各 BR に True/False 2 ケース + 交差。

---

## 4. NOT カバーの明示

**全てを網羅できない場合がある** (実装未完成、不可到達分岐等)。
そのときは、test plan §5「未カバー BR」に理由付きで記録:

```markdown
| BR-ID | 理由 | 対策 |
| BR25  | 現実装で到達不可能 (要仕様確認) | ユーザ判断待ち |
| BR30  | CDW モジュール側でテスト済 | 対象外として承認 |
```

**暗黙的に落とさない**。明示的に「落としました」と宣言する。

---

## 5. Claude の自己チェック (Phase A 後に必ず実施)

test plan 生成後、以下を自己チェックして報告:

```
✓ Step 1: BR カバー率 <X>% (BR01, BR02, ... が未カバー)
✓ Step 2: 仕様書の全 Table を mining したか (list: ...)
✓ Step 3: Cross-product を列挙したか
✓ Step 4: Edge case checklist の全項目を確認したか
✓ Step 5: Random ケース数が基準を満たすか
✓ Step 6: プロジェクト固有項目を含めたか

未対応:
  - <項目> — <理由>
```

自己チェックの結果 **未対応がある場合**、ユーザに確認を取る
("この項目を追加しますか? それとも対象外として §5 に記録しますか?")。

---

## 6. 失敗例と対策

### 失敗例 1: BR カバー率が低い

**症状**: test plan §3 の BR-ID 対応表で、複数の BR に T-ID が割り当てられていない。

**原因**: RTL を読んだが BR の存在を見落とした。

**対策**:
- モジュールカード §6 の BR-ID 数を先にカウント
- test plan §3 の行数が BR 数と一致するか確認
- 一致しないなら警告

### 失敗例 2: 仕様書テーブルを無視

**症状**: spec に明示された Cause code が全部テストされていない。

**対策**:
- モジュールカード §13 の spec file を必ず開く
- `Grep` で `"Table \d"` を検索して Table 一覧取得
- 各 Table の行数 ≤ test の数であること

### 失敗例 3: Edge case 全取っ払い

**症状**: 正常系のみで、back-to-back や stall が無い。

**対策**:
- Step 4 の checklist を全て確認
- 該当しない場合は理由を明記 (モジュールが FSM でないから、等)

### 失敗例 4: Cross-product を書かない

**症状**: R/W/X の組合せ 8 通りのうち 2-3 しかない。

**対策**:
- Step 3 で必ず enumerate
- `itertools.product` 的な列挙を強制
- random テストとは別に directed 化