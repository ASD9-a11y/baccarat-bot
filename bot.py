import os
import random
import requests
from flask import Flask, request

app = Flask(__name__)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8775721468:AAG4fu0wtigofI5p41eVq-mT--sqCIGezwc")
TARGET_CHANNEL = int(os.environ.get("TARGET_CHANNEL", "-1003371779273"))
DATABASE_URL = os.environ.get("DATABASE_URL")
MAX_GAME_NUM = 1440
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== БАЗА ДАННЫХ ==========
def get_conn():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect("bot.db")

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    id INT PRIMARY KEY,
                    auto_mode BOOLEAN DEFAULT FALSE,
                    game_num INT DEFAULT 0
                )
            """)
            cur.execute("INSERT INTO state (id, auto_mode, game_num) VALUES (1, FALSE, 0) ON CONFLICT (id) DO NOTHING")
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    id INTEGER PRIMARY KEY,
                    auto_mode INTEGER DEFAULT 0,
                    game_num INTEGER DEFAULT 0
                )
            """)
            cur.execute("INSERT OR IGNORE INTO state (id, auto_mode, game_num) VALUES (1, 0, 0)")
        conn.commit()
    except Exception as e:
        print("DB init error:", e)
    finally:
        cur.close()
        conn.close()

def load_state():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT auto_mode, game_num FROM state WHERE id = 1")
        row = cur.fetchone()
        return bool(row[0]), int(row[1])
    except Exception as e:
        print("DB load error:", e)
        return False, 0
    finally:
        cur.close()
        conn.close()

def save_state(auto_mode, game_num):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("UPDATE state SET auto_mode = %s, game_num = %s WHERE id = 1", (auto_mode, game_num))
        else:
            cur.execute("UPDATE state SET auto_mode = ?, game_num = ? WHERE id = 1", (int(auto_mode), game_num))
        conn.commit()
    except Exception as e:
        print("DB save error:", e)
    finally:
        cur.close()
        conn.close()

init_db()

# ========== ГЕНЕРАТОР ==========
class BaccaratGenerator:
    def __init__(self):
        self.suits = ['♠️', '♥️', '♣️', '♦️']
        self.ranks = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
        self.rank_values = {
            'A':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
            '10':0,'J':0,'Q':0,'K':0
        }
        self.o_map = {
            '2':'O2','3':'O3','4':'O4','5':'O5','6':'O6','7':'O7','8':'O8',
            '9':'O9','10':'O10','J':'O11','Q':'O12','K':'O13','A':'O14'
        }
        self.colors = ['🔵','🟢','🔴','🟡']

    def random_card(self):
        return random.choice(self.ranks), random.choice(self.suits)

    def card_value(self, rank):
        return self.rank_values.get(rank, 0)

    def generate_hand(self, cards):
        return sum(self.card_value(r) for r, s in cards) % 10

    def generate_game(self, num):
        deck = [(r, s) for _ in range(6) for s in self.suits for r in self.ranks]
        random.shuffle(deck)

        p = [deck.pop(), deck.pop()]
        b = [deck.pop(), deck.pop()]
        ps = self.generate_hand(p)
        bs = self.generate_hand(b)
        p3 = None

        if ps not in (8,9) and bs not in (8,9):
            if ps <= 5:
                p3 = deck.pop()
                p.append(p3)
                ps = self.generate_hand(p)
            p3val = self.card_value(p3[0]) if p3 else None
            if p3 is None:
                if bs <= 5:
                    b.append(deck.pop())
                    bs = self.generate_hand(b)
            else:
                if bs <= 2: b.append(deck.pop())
                elif bs == 3 and p3val != 8: b.append(deck.pop())
                elif bs == 4 and 2 <= p3val <= 7: b.append(deck.pop())
                elif bs == 5 and 4 <= p3val <= 7: b.append(deck.pop())
                elif bs == 6 and p3val in (6,7): b.append(deck.pop())
                bs = self.generate_hand(b)

        if ps > bs:
            winner, win_symbol = 'P', '✅'
        elif bs > ps:
            winner, win_symbol = 'B', '✅'
        else:
            winner, win_symbol = 'T', '🤝'

        p_str = ''.join(f"{r}{s}" for r, s in p)
        b_str = ''.join(f"{r}{s}" for r, s in b)
        color = random.choice(self.colors)
        tags = self._tags(ps, bs, len(p), len(b), winner)
        return f"{color}#n{num}\n {ps}({p_str}) - {win_symbol}{bs}({b_str})\n {' '.join(tags)}\n #p2.225 | #x6.37 | #b2.225"

    def _tags(self, ps, bs, pc, bc, w):
        tags = []
        total = ps + bs
        tags.append('#C2_2' if pc==2 and bc==2 else '#C2_3' if pc==2 and bc==3 else '#C3_2' if pc==3 and bc==2 else '#C3_3')
        tags.append('#П1' if w=='P' else '#П2' if w=='B' else '#Х')
        if pc==2 and bc==2: tags.append('#R')
        tags.append(f'#Т{total}')
        for lim, tag in [(10.5,'#M10'),(9.5,'#М9'),(8.5,'#М8'),(7.5,'#М7')]:
            if total < lim: tags.append(tag)
        for lim, tag in [(10.5,'#B10'),(11.5,'#B11'),(12.5,'#B12'),(13.5,'#B13')]:
            if total > lim: tags.append(tag)
        if ps < 2.5: tags.append('#М')
        if ps > 7.5: tags.append('#B')
        if ps < 5.5: tags.append('#И_М5')
        if ps + 3.5 > bs: tags.append('#F3')
        if ps + 2.5 > bs: tags.append('#F2')
        if ps + 1.5 > bs: tags.append('#F1')
        if random.random() < 0.5:
            tags.append(f'#S{"".join(random.choice("1234") for _ in range(3))}')
        rank_tags = [self.o_map[r] for r in self.ranks if random.random() < 0.3]
        if rank_tags:
            tags.extend(random.sample(rank_tags, min(len(rank_tags), random.randint(2,4))))
        if random.random() < 0.3: tags.append(f'#K{random.randint(1,5)}')
        if random.random() < 0.3: tags.append(f'#m{random.randint(0,58)}')
        return tags

generator = BaccaratGenerator()

# ========== TELEGRAM API ==========
def tg_send(chat_id, text):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        return r.json()
    except Exception as e:
        print("tg error:", e)
        return None

def do_send_game():
    auto_mode, game_num = load_state()
    if not auto_mode:
        return "skipped"
    game_num += 1
    if game_num > MAX_GAME_NUM:
        game_num = 1
    text = generator.generate_game(game_num)
    res = tg_send(TARGET_CHANNEL, text)
    if res and res.get("ok"):
        save_state(auto_mode, game_num)
        return f"sent #{game_num}"
    return "failed"

# ========== ROUTES ==========
@app.route("/")
def home():
    return "Bot is alive"

@app.route("/tick", methods=["GET","POST"])
def tick():
    return {"result": do_send_game()}, 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    msg = data.get("message", {})
    if not msg:
        return "ok", 200

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1:
            try:
                n = int(parts[1])
                if 1 <= n <= MAX_GAME_NUM:
                    save_state(True, n - 1)
                    tg_send(chat_id, f"✅ Авто-режим ЗАПУЩЕН! Старт: #{n}")
                else:
                    tg_send(chat_id, f"❌ От 1 до {MAX_GAME_NUM}")
            except ValueError:
                tg_send(chat_id, "❌ Пример: /start 860")
        else:
            tg_send(chat_id, "🎴 Команды:\n/start <номер>\n/stop\n/game\n/status")

    elif text == "/stop":
        auto_mode, game_num = load_state()
        save_state(False, game_num)
        tg_send(chat_id, "🛑 Авто-режим ОСТАНОВЛЕН!")

    elif text == "/game":
        auto_mode, game_num = load_state()
        game_num += 1
        if game_num > MAX_GAME_NUM: game_num = 1
        tg_send(TARGET_CHANNEL, generator.generate_game(game_num))
        save_state(auto_mode, game_num)
        tg_send(chat_id, f"✅ Игра #{game_num} отправлена!")

    elif text == "/status":
        auto_mode, game_num = load_state()
        if auto_mode:
            nxt = game_num + 1
            if nxt > MAX_GAME_NUM: nxt = 1
            tg_send(chat_id, f"🟢 АКТИВЕН\nПоследняя: #{game_num}\nСледующая: #{nxt}")
        else:
            tg_send(chat_id, "🔴 ВЫКЛЮЧЕН\n/start <номер>")

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
