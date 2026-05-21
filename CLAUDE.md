The keywords "MUST", "NEVER", "SHOULD", "MAY" follow RFC 2119.

# Sketches

思いつき開発の集積場。Emocute モノレポ（`Downloads/`）配下のサブハブ。

## 位置づけ

- 「遊びで作りたい」「小ネタ」「実験」レベルの PJ を Downloads 直下に直接置かず、ここに集約
- 各サブ PJ は `Sketches/<PJ名>/` フォルダで独立。共有コードは原則なし（独立性優先）
- 着手前のアイデアメモは `_ideas/<topic>.md`

## 規約

1. MUST 新規サブ PJ を起こす時は最初に `Sketches/<PJ名>/CONCEPT.md` を書く（目的・技術スタック・最小スコープ）
2. MUST サブ PJ の README / ドキュメントは個別 PJ 内に閉じる。Sketches 全体の README には住人リストだけ
3. NEVER サブ PJ 間で共有ライブラリを切らない（独立性優先、必要なら昇格してから別 repo 化）
4. MAY アイデアだけのものは `_ideas/<topic>.md` で雑に保管。実装着手と同時にフォルダ化
5. MUST サブ PJ が大型化したら `Downloads/<PJ名>/` に昇格 + `Emocute/<name>` 独立 repo 化。`git subtree split -P <PJ名> -b <PJ名>-split` で履歴保持

## リポ

- Emocute/sketches モノレポ
- 全サブ PJ が tracked
- 昇格時のみ subtree split で剥離

## 継承

Downloads/CLAUDE.md（応答・ブランド・ファイル操作・コミット規約等）を継承。本ファイルは Sketches 固有の運用ルールのみ。
