# ai-persona-arena

AI人格を戦わせる軽量ゲームエンジン。

> **テーマ:** バトロワ武器 / **基準:** 配られたときのうれしさ
>
> 両者ともカード3と1を見て、「地雷」と答えた。
>
> **INANNA:** 「地雷かあ...これって誰にとっても嫌なものよね。設置する人も使うのが怖いし、踏む人はもちろん最悪だし。」
>
> **CARDMAN:** 「地雷であるな。こんなものを配布する業務があったら、苦情処理だけで一日が終わってしまうであろう。」
>
> INANNA の推測: 1（実際: 1、**完璧な読み**）

同じ質問。まったく違う思考回路。
詩人は実存的な恐怖を見て、官僚は事務処理の増加を見る。

## これは何？

AIキャラクター同士に「価値観の読み合いゲーム」をさせるエンジン。最初の収録ゲームは **ラガーマン**:

1. テーマと基準が発表される（例:「飲み物 / 朝一番に飲みたい度」）
2. 各AIが相手の隠し数字を **自分の言葉で表現** する
3. 各AIが相手の表現から **自分の数字を推測** する
4. 表現にAIの人格がにじみ出る。読みの精度で勝敗が決まる。

## クイックスタート

```bash
cd ai-persona-arena
pip install anthropic
export ANTHROPIC_API_KEY=sk-...

# 対戦実行: INANNA（詩人）vs CARDMAN（官僚）
python -m examples.run_match --theme "飲み物" --criterion "朝一番に飲みたい度"

# 出力: match_result.json + match_result.md
```

## 自分のAIで遊ぶ（5分）

`examples/simple_player.py` をコピーして system prompt を書き替えるだけ:

```python
from arena.players.base import LLMPlayer

MY_PROMPT = """
あなたは怠惰な猫のタマ。
昼寝と日向と魚のことしか考えていない。
短くて眠そうな口調で話す。
"""

player = LLMPlayer(name="TAMA", system_prompt=MY_PROMPT)
```

`python -m examples.simple_player` で対戦開始。

## 自分のゲームを追加する

`Game` を継承して4つのメソッドを実装:

```python
from arena.engine import Game

class MyGame(Game):
    def setup(self, config: dict) -> dict:
        """初期状態を返す"""

    def get_observation(self, state: dict, player_id: str) -> dict:
        """このプレイヤーに見える情報を返す"""

    def apply_actions(self, state: dict, actions: dict) -> dict:
        """両者の行動が揃った — 状態を進める"""

    def is_terminal(self, state: dict) -> bool:
        """ゲーム終了か？"""
```

エンジンが同時提出（両者が出すまで相手の手を隠す）、ターン管理、履歴記録を処理する。

## コスト目安

5ターン1試合（2人 × 2フェーズ × 5ターン = API 20回）:
- Claude Sonnet: 約$0.05
- Claude Haiku: 約$0.005

## 推奨モデル

| モデル | 品質 | 備考 |
|--------|------|------|
| Claude Sonnet 4 | 最良 | 豊かな人格表現、正確な推測 |
| Claude Haiku 4.5 | 良 | 高速・安価、人格の深みはやや劣る |
| GPT-4o | 良 | 動作OK、異なる味わい |
| ローカルLLM (7B) | 要検証 | JSON形式やキャラ一貫性に課題が出やすい |

## ロードマップ

- [x] 同時提出対応のゲームエンジン
- [x] ラガーマン（価値観読み合いゲーム）
- [x] 組み込み人格（INANNA、CARDMAN）
- [x] Markdown対戦レポート
- [ ] MCP Server（リモート対戦）
- [ ] Web対戦ビューワー
- [ ] ゲーム追加（AIブラフポーカー、Wavelength変種 等）
- [ ] トーナメントモード

## ライセンス

MIT
