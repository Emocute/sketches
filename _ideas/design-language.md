# 理論 toy 連作 — デザイン言語（v2 洗練）

全 toy で共有する見た目の規範。Sketches 規約 3（共有ライブラリ禁止）のため、この CSS トークン群を各 toy 内に**埋め込んで**統一する。正本はこのファイル。

## カラートークン（elevation 付き）

```
--bg:#0b0b0f          /* 最下層 */
--bg2:#0f0f15         /* 微妙な縦グラデ上端 */
--surface:#15151c     /* カード面 */
--surface2:#1b1b24    /* 入力・押せる面 */
--ink:#ecECf2         /* 主文字 */
--ink-dim:#8c8c9a     /* 副次 */
--line:#262630        /* 境界（低コントラスト） */
--accent:#cfac6e      /* 金 — 主アクセント */
--accent-soft:#e0c894 /* 金ハイライト */
--accent2:#6fa3cf     /* 青 — 第二アクセント */
--good:#6fc996 --warn:#cf6f6f --mag:#cf6f9e
--radius:14px --radius-sm:9px
--ease:cubic-bezier(.2,.7,.3,1)
```

背景は `radial-gradient` の淡いビネット（中央やや明・端暗）で奥行き。装飾図形は置かない（solid 基調を保つ）。

## タイポgrafィ

- 見出し: system sans, 600–700, letter-spacing .01em。`h1` 21px、セクション見出しは 11px / uppercase / letter-spacing .12em / --ink-dim
- 本文: 13–14px / line-height 1.55
- 数値・度数・パターン: `ui-monospace, Menlo` で必ず monospace（理論データの可読性）

## 余白

8px グリッド。カード内 padding 16–18px、要素間 gap 10–14px、セクション間 margin 22–28px。

## コンポーネント

- **ボタン**: surface2 + 1px line、radius-sm、padding 9/13。hover で border→accent + わずかに持ち上げ（translateY -1px）。`:focus-visible` で accent の 2px リング。primary = 金グラデ + 暗文字
- **セグメント**: pill 群。active = accent2 塗り + 暗文字。150ms ease で切替
- **カード**: surface + line + radius。hover で border→accent・1px 外側グロー・translateY -2px。左に育つアクセントバー（任意）
- **select / input**: surface2、focus で accent ボーダー、カスタム矢印
- **鍵盤 / 円 / グリッド**: 点灯は accent、最低音/特殊は accent2/mag。点灯時 0.15s で色遷移

## モーション

- すべての interactive に 150–200ms ease のトランジション
- **発音フィードバック**: 音が鳴った要素は短いグロー脈動（box-shadow を 0→accent→0、~360ms）。`.pulse` クラス + animation
- レイアウトはトランジションさせない（カクつき防止）、色と影と transform のみ

## レスポンシブ

`max-width` でセンタリング。≤640px で 2 カラム→1、コントロールは wrap、鍵盤は横スクロールでなく縮小。

## アクセシビリティ

`:focus-visible` リング必須。コントラスト比は本文 ≥ 7:1。色だけに依存せずラベル併記（機能 T/S/D は文字 + 色）。
