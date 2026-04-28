# Feedback Log

Claude Code に対する改善要望・好みを書き溜める場所。
週 1 回程度レビューして、永続化すべきものは `CLAUDE.md` や
`.claude/commands/*.md` に昇格させる。

---

## 書式

```markdown
### YYYY-MM-DD — <簡潔なタイトル>

**観察された挙動**: <Claude が実際にやったこと>
**期待する挙動**: <こうしてほしい>
**コンテキスト**: <どのセッション/コマンドで>
**優先度**: 高 / 中 / 低
**対応先**:
  - [ ] CLAUDE.md に追加
  - [ ] スラッシュコマンド `<name>` に追加
  - [ ] モジュールカードに記載
  - [ ] その他 (自由記述)
```

---

## 未整理フィードバック

### 2026-04-25 — 条件分岐の抜け

**観察された挙動**:
  `/create-module-card ptw` で §6 を生成させたら、ptw_sv39x4_pc.sv
  の `case (state_q)` 内の分岐が BR-ID に含まれていなかった。

**期待する挙動**:
  `if/else/case/三項演算子` 全部を BR-ID 対象にする (特に case 文忘れがち)。

**コンテキスト**: `/create-module-card ptw` セッション

**優先度**: 高

**対応先**:
  - [x] `.claude/commands/create-module-card.md` の Phase 5 「埋め方のルール」に
        「case 文の各 when も個別の BR-ID を振る」を明記
  - [ ] CLAUDE.md の Working Rules に移す要否は週次レビューで判断


### 2026-04-26 — helpers.py の勝手な編集

**観察された挙動**: (例)

**期待する挙動**: (例) ユーザ承認前に helpers.py を書き換えない

**優先度**: 中

**対応先**:
  - [ ] `.claude/commands/create-tb.md` に再強調

---

## 昇格済みフィードバック

(ここに、CLAUDE.md やコマンドに取り込まれたフィードバックを日付付きで列挙)

- 2026-04-20: "推測で書かない、file:line 引用必須" → CLAUDE.md Working Rules §1
- 2026-04-22: "仕様書参照時はセクション番号" → CLAUDE.md Working Rules §3