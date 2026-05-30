# Chord-Scale Mapper

ブラウザ単一 HTML の chord-scale theory toy。コード（root + quality）を入れると、その上で吹ける／弾けるスケールを提示し、コードを鳴らしてからスケールを上行する。voicing-lab（積み方）と mode-mixer（旋法）の橋渡し＝「このコードにはどの音列が乗るか」を耳で繋ぐ。

対応はコード構成音がスケールに含まれることを `node` で検証済み（素の dominant 7 は natural 5 を持つので Altered には乗らない＝7alt 専用、等）。Tone.js のみ依存。アーティスト名非依存。
