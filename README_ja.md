# ai-persona-arena

[English README](README.md)

AI人格同士がどれだけ通じ合えるかを測る、協力型ゲームエンジン。

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
詩人は実存的な恐怖を見て、官僚は事務処理の増加を見る。

## これは何？

AI人格ごとの「世界の見え方の違い」を可視化するゲームエンジン。最初の収録ゲームは **ラガーマン** — [ito](https://bodoge.hoobby.net/games/ito) 的な協力型の価値観読み合いゲーム:

1. テーマと基準が発表される（例:「飲み物 / 朝一番に飲みたい度」）
2. 各AIが相手の隠し数字を正直に **自分の言葉で表現** する
3. 各AIが相手の表現から **自分の数字を推測** する
4. **ペアスコア** で、2つの人格がどれだけ通じ合えたかを測る

嘘もブラフもなし — ただ違うレンズで正直に表現するだけ。面白さはそのズレにある。

## クイックスタート

```bash
git clone https://github.com/Salmonellasarduri/ai-persona-arena.git
cd ai-persona-arena
pip install anthropic pillow
export ANTHROPIC_API_KEY=sk-...

# 対戦実行: INANNA（詩人）vs CARDMAN（官僚）
PYTHONPATH=src python -m examples.run_match --theme "飲み物" --criterion "朝一番に飲みたい度"

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

`PYTHONPATH=src python -m examples.simple_player` で対戦開始。

## X / Twitter に共有

対戦結果から OGP カード（1200×630）を生成:

```bash
PYTHONPATH=src python -m arena.ogp match_result.json --theme "飲み物" --criterion "朝一番に飲みたい度"
# → ogp_card.png
```

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

## アーキテクチャ

```
ai-persona-arena/
├── src/arena/
│   ├── engine.py          # ゲームエンジン（状態機械 + 同時提出）
│   ├── formatter.py       # Markdown出力
│   ├── ogp.py             # OGP画像生成（1200×630）
│   ├── games/
│   │   └── ragaman.py     # ラガーマン（協力型）
│   └── players/
│       ├── base.py        # Player基底クラス + LLMPlayer
│       ├── inanna.py      # 詩人人格
│       └── cardman.py     # 官僚人格
├── examples/
│   ├── run_match.py       # CLI対戦
│   ├── simple_player.py   # 自作プレイヤー例
│   └── mcp_client_demo.py # MCPクライアント例
├── viewer/
│   └── index.html         # ブラウザ対戦ビューワー
└── tests/
    └── test_ragaman.py    # 14テスト
```

## MCP Server（リモート対戦）

MCP サーバーとしてゲームを公開し、外部AIエージェントが接続して対戦:

```bash
# stdio（Claude Desktop、Cursor等向け）
PYTHONPATH=src python -m arena.server --transport stdio

# HTTP（Webクライアント向け）
PYTHONPATH=src python -m arena.server --transport streamable-http
```

`pip install mcp` が必要。[examples/mcp_client_demo.py](examples/mcp_client_demo.py) にクライアント例あり。

ツール: `create_room`, `join_room`, `get_observation`, `submit_action`, `get_history`, `list_rooms`, `delete_room`

## 対戦ビューワー

[viewer/index.html](viewer/index.html) をブラウザで開き、`match_result.json` をドロップすると対戦をビジュアルで再生できる。

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
- [x] ラガーマン（協力型・価値観読み合い）
- [x] 組み込み人格（INANNA、CARDMAN）
- [x] Markdown対戦レポート
- [x] MCP Server（リモート対戦）
- [x] Web対戦ビューワー
- [x] OGPカード生成（SNS共有用）
- [ ] ゲーム追加
- [ ] トーナメントモード

## ライセンス

MIT
