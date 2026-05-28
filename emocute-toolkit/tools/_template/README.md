# Tool Template

ツール実装テンプレート。`tools/<category>-<short_name>/` 配下に展開して使う。

## ファイル構成（推奨）
- `main.py` — エントリ。`main(argv) -> int` を実装
- `README.md` — 使い方・実装メモ・既知の制約
- `test_main.py` — pytest 単体テスト
- `fixtures/` — テスト fixtures

## 命名
`tools/<category>-<id>/` の名前は `registry/<category>/<id>.yaml` の `id:` と一致させる。
CLI `emocute <category> <short>` は `<category>-<short>` でルーティング。

## 完了の定義
- `--help` が動く
- `--apply` なしで dry-run が完了
- `--apply` で実際の副作用が動く
- logger.info / done で開始終了ログ
- README に「使い方 3 行 + 制約 3 行」を書く
- `registry/_status.yaml` の該当 id を `status: implemented` に
