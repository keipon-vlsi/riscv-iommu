---
description: 今セッションの作業内容を doc/worklog/YYYY-MM-DD.md に追記
---

# /log-today — 作業ログ追記

引数: $ARGUMENTS (省略可。あれば session の概要として使う。例: "PTW TB 調整")

## Phase 1: 状況収集

1. **日付取得**: `date +%Y-%m-%d` で今日の日付、`date +%H:%M` で時刻を取得
2. **Git 状態**: 以下を並列で実行
    - `git log --since="12 hours ago" --oneline`
    - `git diff --stat HEAD` (未コミット分)
    - `git status --short`
3. **今のセッションの内容を振り返る**: 本セッションで会話したトピック、読んだファイル、生成/変更したファイルを脳内で列挙

## Phase 2: ログファイル確認

1. `doc/worklog/<YYYY-MM-DD>.md` が存在するか確認
    - 存在しない → 新規作成 (`# Work Log <YYYY-MM-DD>` を先頭に)
    - 存在する → 末尾にセッションを追記
2. 既存ファイルに何 Session 書かれているかカウント (次の番号を決定)

## Phase 3: エントリ生成

以下の構造で **当該セッション分のエントリを追記**:

```markdown
## Session <N> (<開始時刻>-<現在時刻>) — <トピック>

### Goal / Topic
<今日このセッションで何を達成しようとしたか、1-2 行>

### Done
- <完了した作業、Claude とユーザの共同作業を bullet で 3-8 項目>

### Files changed
- Created: `<path>` (<一行説明>)
- Modified: `<path>` (<一行説明>)
- Deleted: `<path>`

### Decisions / Findings
- <設計判断、バグ発見、仕様解釈の確定 など>

### Open questions / TODO
- [ ] <次に解決したい疑問>
- [ ] <未実装で後回しにしたもの>

### Next session
<次セッションの最初のアクションを 1-2 行で>

---
```

## Phase 4: ルール

- **推測で書かない**: 実際にこのセッション内で行ったことだけを書く (git log / 会話内容を根拠に)
- **"Next session" は必須**: 空欄ならユーザに確認を取る
- **ユーザが $ARGUMENTS でトピックを指定した場合**: それを Session トピックに使う。無ければ会話内容から推測
- **セッション時間**: 正確に取れない場合は「(時刻未記録)」と書く。捏造しない
- **既存 worklog は変更しない**: 追記のみ、既存エントリは絶対に書き換えない

## Phase 5: 報告

完了したら以下を報告:

```
✓ doc/worklog/<YYYY-MM-DD>.md に Session <N> を追記しました

書いた内容:
  - Done: <N> 項目
  - Files changed: <N> 件
  - TODO: <N> 項目

次セッション先頭用に /recap で読み直せます。
```