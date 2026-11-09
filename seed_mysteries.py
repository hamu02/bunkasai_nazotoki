import os
import django

# Django環境のセットアップ
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from escape_game.models import Mystery

def create_mysteries():
    # 既存の問題データを一旦クリア（重複防止）
    Mystery.objects.all().delete()

    mysteries = [
        # ── 1組目の問題 ──
        {
            "stage_number": 1,
            "title": "【1組目・第1問】使役動物の証言",
            "statement": """
<p>部屋の中にある「使役動物（ぬいぐるみ）」を見つけ、その言葉を解き明かせ。</p>
<div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; margin: 10px 0;">
  <p><strong>Aのうさぎ:</strong> 「Bのくまは正直者だよ」</p>
  <p><strong>Bのくま:</strong> 「Aのうさぎは嘘つきだ」</p>
  <p><strong>Cのふくろう:</strong> 「Aのうさぎは正直者だよ」</p>
</div>
<p><strong>【問】</strong> 1人だけ嘘をついている動物の名前（カタカナ）を入力せよ。</p>
""",
            "answer": "くま",
            "hint_ice": "AとCは同じことを言っているよ。もしAが嘘つきならCも嘘つきになってしまうね...",
            "hint_grass": "「くま」または「クマ」が答えだよ。",
            "hint_fire": "嘘をついている動物が隠していた『魔法瓶（色水入り）』を手に入れ、棚へ向かえ！"
        },
        {
            "stage_number": 2,
            "title": "【1組目・第2問】秘薬の調合",
            "statement": """
<p>手に入れた魔法瓶を指示通りに棚へ配置し、後ろのダミー文字を隠せ。</p>
<div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; margin: 10px 0;">
  <p>・赤のポーション ➔ 左から1番目</p>
  <p>・青のポーション ➔ 左から3番目</p>
</div>
<p>残った文字を順番に読み解き、浮かび上がった言葉を入力せよ。</p>
""",
            "answer": "いすのうら",
            "hint_ice": "魔法瓶を棚の指定の位置に置くと、邪魔な文字が消えて読みやすくなるよ。",
            "hint_grass": "浮かび上がる言葉は「い・す・の・う・ら」だよ。",
            "hint_fire": "正解したら、部屋の中にある『黒い布がかぶせられた椅子』を探そう！"
        },
        {
            "stage_number": 3,
            "title": "【1組目・第3問】封印された椅子と最後の暗号",
            "statement": """
<p>黒き布に覆われし『椅子』を暴き、背もたれに刻まれた呪文を解読せよ。</p>
<p>解き明かした最終合言葉を入力せよ！</p>
""",
            "answer": "magic",
            "hint_ice": "椅子の背もたれにある紙に書かれたアルファベットをそのまま読もう。",
            "hint_grass": "合言葉は英単語「MAGIC（マジック）」だよ。",
            "hint_fire": "本棚の頂上にある『宝石』を手に取って脱出完了だ！"
        },

        # ── 2組目の問題 ──
        {
            "stage_number": 4,
            "title": "【2組目・第1問】二つの時の交点",
            "statement": """
<p>机の上にある金と銀の懐中時計を見よ。</p>
<div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; margin: 10px 0;">
  <p>・【金の長針】が示す数字 ➔ 『縦の列』</p>
  <p>・【銀の短針】が示す数字 ➔ 『横の列』</p>
</div>
<p>壁にある『文字の書（座標表）』から、その位置の言葉を読み解いて入力せよ。</p>
""",
            "answer": "とけい",
            "hint_ice": "金の長針と銀の短針の数字をそのまま座標表に当てはめてみよう。",
            "hint_grass": "導き出される言葉は身近な「とけい」だよ。",
            "hint_fire": "正解したら、文字のない五十音表グリッドシートへ移動しよう！"
        },
        {
            "stage_number": 5,
            "title": "【2組目・第2問】無のグリッドと灯火",
            "statement": """
<p>空白のグリッド（五十音の理）に以下の位置に蝋燭を置け。</p>
<div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; margin: 10px 0;">
  <p>・【上から3段目、右から2列目】</p>
  <p>・【上から1段目、右から5列目】</p>
  <p>・【上から5段目、右から7列目】</p>
</div>
<p>該当するマスの文字を拾い、並べ替えてできる単語を入力せよ。</p>
""",
            "answer": "つくえ",
            "hint_ice": "この枠組みはあいうえお（五十音表）の形になっているよ。「あ・い・う・え・お」の順で数えてみよう。",
            "hint_grass": "文字を並べ替えると「つ・く・え」になるよ。",
            "hint_fire": "正解したら、スチールラックに並んだ『大量のジャム瓶』の場所へ向かおう！"
        },
        {
            "stage_number": 6,
            "title": "【2組目・第3問】秘密の試薬と魔法使いの日誌",
            "statement": """
<p>【魔法使いの調剤日誌】</p>
<blockquote style="border-left: 3px solid #00f3ff; padding-left: 10px; color: #cbd5e1;">
「陽の光を浴びた素材は、すべて毒を帯びておる。<br>
我が真の秘宝を封じたのは、熱を嫌い、静寂なる夜の空を照らす【月と星の輝き】を宿した瓶である。<br>
太陽の温もりを知らぬその瓶を1つだけ開き、底の用紙に書かれた合言葉を入力せよ。」
</blockquote>
""",
            "answer": "exit",
            "hint_ice": "「太陽」「炎」「昼」などの熱そうな名前の瓶はダミーだよ。「星」や「月」の文字が入った瓶を探して！",
            "hint_grass": "『星くずの欠片』の瓶を開けると中に紙が入っているよ。",
            "hint_fire": "中に入っている紙の合言葉は「EXIT」だよ！"
        }
    ]

    for m in mysteries:
        Mystery.objects.create(**m)
    
    print("全6問の問題データを正常にインポートしました！")

if __name__ == '__main__':
    create_mysteries()