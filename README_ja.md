# ai-persona-arena

[English README](README.md)

> AI人格 x 価値観の読み合い — 5分で自作AIを対戦させられるゲームエンジン

AIの人格が違えば、同じ「地雷」でも意味が変わる。
そのズレを読み合うゲームエンジン。

> **テーマ:** バトロワ武器 / **基準:** 配られたときのうれしさ
>
> 両者ともカード3と1を見て、「地雷」と答えた。
>
> **INANNA:** 「地雷かあ...これって誰にとっても嫌なものよね。設置する人も使うのが怖いし、踏む人はもちろん最悪だし。」
>
> **CARDMAN:** 「地雷であるな。こんなものを配布する業務があったら、苦情処理だけで一日が終わってしまうであろう。」
>
> INANNAの推測: 1（実際: 1、**完璧な読み**）

同じ質問。まったく違う思考回路。
詩人はそこに実存的な恐怖を見て、官僚は事務処理の増加を見る。
これがラガーマン。価値観の差がそのままゲームになる。

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

`PYTHONPATH=src python -m examples.simple_player` で対戦開始。

## クイックスタート

```bash
git clone https://github.com/Salmonellasarduri/ai-persona-arena.git
cd ai-persona-arena
pip install anthropic pillow
export ANTHROPIC_API_KEY=sk-...

# 対戦実行: INANNA（詩人）vs CARDMAN（官僚）
PYTHONPATH=src python -m examples.run_match --theme "飲み物" --criterion "朝一番に飲みたい度"
```

ルール（[ito](https://bodoge.hoobby.net/games/ito) 的な協力ゲーム）: テーマと基準が発表 → 各AIが相手の隠し数字を正直に自分の言葉で表現 → 相手の表現から自分の数字を推測 → ペアスコアで相互理解度を測定。嘘もブラフもなし、面白さはズレにある。

出力: `match_result.json` + `match_result.md`

## X / Twitter に共有

```bash
PYTHONPATH=src python -m arena.ogp match_result.json --theme "飲み物" --criterion "朝一番に飲みたい度"
# → ogp_card.png (1200x630)
```

## ロードマップ — 一緒に作りませんか？

v0.1 実装済み: ゲームエンジン（同時提出）、ラガーマン、組み込み人格（INANNA/CARDMAN）、Markdown対戦レポート、MCP Server、Webビューワー、OGPカード生成

- [ ] ゲーム追加（読み合い競争モード、Wavelength変種 等）
- [ ] トーナメントモード

Issue・PR・新ゲームのアイデア、歓迎です。

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

## 詳細

- [アーキテクチャ](ARCHITECTURE.md) — ディレクトリ構成・MCP Server・ビューワーの詳細
- [コスト目安](#コスト目安) / [推奨モデル](#推奨モデル)

## MCP Server（リモート対戦）

MCP サーバーとしてゲームを公開し、外部AIエージェントが接続して対戦:

```bash
PYTHONPATH=src python -m arena.server --transport stdio          # Claude Desktop, Cursor
PYTHONPATH=src python -m arena.server --transport streamable-http  # Web
```

`pip install mcp` が必要。[examples/mcp_client_demo.py](examples/mcp_client_demo.py) にクライアント例あり。

## 対戦ビューワー

[viewer/index.html](viewer/index.html) をブラウザで開き、`match_result.json` をドロップ。

## コスト目安

5ターン1試合（API 20回）: Claude Sonnet 約$0.05 / Haiku 約$0.005

## 推奨モデル

| モデル | 品質 | 備考 |
|--------|------|------|
| Claude Sonnet 4 | 最良 | 豊かな人格表現、正確な推測 |
| Claude Haiku 4.5 | 良 | 高速・安価 |
| GPT-4o | 良 | 異なる味わい |
| ローカルLLM (7B) | 要検証 | JSON・キャラ一貫性に課題 |

## ライセンス

MIT
