"""
МайндКер — Платформа онлайн-терапії з ШІ-агентом
Автор: Белеканич Максим Олександрович
Версія: 1.1
"""

import json
import os
import sys
import uuid
import logging
import datetime
import re
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from pathlib import Path

# ─── Визначення базового шляху ─────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ─── Завантаження конфігурації ─────────────────────────────────────────
def load_config() -> dict:
    cfg_path = BASE_DIR / "config" / "settings.json"
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()

# ─── Налаштування журналювання ─────────────────────────────────────────
LOG_PATH = BASE_DIR / CONFIG["paths"]["log_file"]
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)

def log(level: str, message: str):
    getattr(logging, level.lower(), logging.info)(message)

# ─── Збереження / завантаження даних ──────────────────────────────────
DATA_DIR = BASE_DIR / CONFIG["paths"]["data_dir"]
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_FILE = BASE_DIR / CONFIG["paths"]["sessions_file"]
USERS_FILE    = BASE_DIR / CONFIG["paths"]["users_file"]
EXPORT_DIR    = BASE_DIR / CONFIG["paths"]["export_dir"]
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path: Path, default):
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log("error", f"Помилка читання {path}: {e}")
    return default

def save_json(path: Path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("error", f"Помилка збереження {path}: {e}")

# ─── ШІ-агент (локальний, на правилах) ─────────────────────────────────
EMPATHY_PHRASES = [
    "Я розумію, що зараз вам непросто.",
    "Дякую, що ви поділилися цим.",
    "Ваші почуття абсолютно нормальні.",
    "Ви не самотні у цьому.",
    "Продовжуйте — я уважно слухаю.",
]

RESPONSES = {
    "тривог": [
        "Тривога — природна реакція організму. Спробуйте дихальну вправу: вдих на 4 рахунки, затримка на 4, видих на 6.",
        "Коли тривога наростає, корисно зосередитись на 5 речах навколо, які ви бачите прямо зараз.",
        "Запишіть, що саме вас турбує. Зазвичай конкретизація тривоги зменшує її силу.",
    ],
    "сум": [
        "Смуток — важлива емоція, яка говорить про те, що для вас важливо. Не намагайтесь її придушити.",
        "У такі моменти добре зателефонувати комусь близькому або просто вийти на коротку прогулянку.",
        "Дозвольте собі відчути сум. Він не буде вічним.",
    ],
    "стрес": [
        "При сильному стресі добре допомагає метод «5-4-3-2-1»: назвіть 5 речей, які бачите, 4 — чуєте, 3 — можете доторкнутись.",
        "Розбийте завдання на маленькі кроки. Зробіть перший — і стрес відступить.",
        "Регулярний відпочинок — не розкіш, а необхідність. Коли ви останній раз відпочивали?",
    ],
    "сон": [
        "Проблеми зі сном часто пов'язані зі стресом. Спробуйте перед сном 10 хвилин без екранів.",
        "Постарайтеся лягати та вставати в один і той самий час — навіть у вихідні.",
        "Тепла ванна або читання книги перед сном допомагають організму перейти в режим відпочинку.",
    ],
    "одинок": [
        "Відчуття самотності — один із найпоширеніших людських досвідів. Ви не одні з цим.",
        "Спробуйте зробити невелику добру справу для когось — це дивовижно зближує.",
        "Чи є хобі або заняття, де ви могли б познайомитись з новими людьми?",
    ],
    "злост": [
        "Злість сигналізує, що якась ваша потреба не задоволена. Спробуємо разом зрозуміти яка?",
        "Коли відчуваєте злість, відійдіть на кілька хвилин — фізично зміните простір.",
        "Напишіть все, що хочете сказати, не відправляючи. Часто це достатньо для розрядки.",
    ],
    "дяку": [
        "Радий бути корисним! Продовжуйте — розкажіть більше.",
        "Це важливий крок — говорити про свої почуття.",
    ],
}

FALLBACK = [
    "Розкажіть мені більше про те, що ви відчуваєте.",
    "Як давно це відбувається?",
    "Що, на вашу думку, могло це спричинити?",
    "Як це впливає на ваше повсякденне життя?",
    "Чи є поряд хтось, кому ви довіряєте і з ким можна поговорити?",
]

def ai_respond(user_text: str) -> str:
    """Генерує відповідь ШІ-агента на основі ключових слів."""
    text_low = user_text.lower()
    for keyword, replies in RESPONSES.items():
        if keyword in text_low:
            empathy = random.choice(EMPATHY_PHRASES)
            reply = random.choice(replies)
            return f"{empathy}\n\n{reply}"
    return random.choice(FALLBACK)

# ─── Модель даних ──────────────────────────────────────────────────────
class UserManager:
    def __init__(self):
        self.users: dict = load_json(USERS_FILE, {})

    def register(self, name: str, email: str) -> str:
        """Реєструє нового користувача, повертає ID."""
        if not name.strip() or len(name.strip()) < 2:
            raise ValueError("Ім'я має містити щонайменше 2 символи.")
        email = email.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError("Некоректна адреса електронної пошти.")
        if any(u["email"] == email for u in self.users.values()):
            raise ValueError("Користувач з такою поштою вже зареєстрований.")
        uid = str(uuid.uuid4())[:8]
        self.users[uid] = {
            "id": uid,
            "name": name.strip(),
            "email": email,
            "created_at": datetime.datetime.now().isoformat(),
        }
        save_json(USERS_FILE, self.users)
        log("info", f"Зареєстровано нового користувача: {name} ({email})")
        return uid

    def get(self, uid: str) -> dict | None:
        return self.users.get(uid)

    def all(self) -> list:
        return list(self.users.values())


class SessionManager:
    def __init__(self):
        self.sessions: dict = load_json(SESSIONS_FILE, {})

    def start(self, user_id: str, topic: str) -> str:
        sid = str(uuid.uuid4())[:8]
        self.sessions[sid] = {
            "id": sid,
            "user_id": user_id,
            "topic": topic,
            "messages": [],
            "started_at": datetime.datetime.now().isoformat(),
            "ended_at": None,
        }
        self._save()
        log("info", f"Розпочато сесію {sid} для користувача {user_id}")
        return sid

    def add_message(self, sid: str, role: str, text: str):
        if sid not in self.sessions:
            return
        self.sessions[sid]["messages"].append({
            "role": role,
            "text": text,
            "timestamp": datetime.datetime.now().isoformat(),
        })
        self._save()

    def end(self, sid: str):
        if sid in self.sessions:
            self.sessions[sid]["ended_at"] = datetime.datetime.now().isoformat()
            self._save()
            log("info", f"Завершено сесію {sid}")

    def get(self, sid: str) -> dict | None:
        return self.sessions.get(sid)

    def for_user(self, user_id: str) -> list:
        return [s for s in self.sessions.values() if s["user_id"] == user_id]

    def all(self) -> list:
        return list(self.sessions.values())

    def export_json(self) -> str:
        """Експортує всі сесії у JSON-файл, повертає шлях."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = EXPORT_DIR / f"sessions_export_{ts}.json"
        report = {
            "meta": {
                "app_name": CONFIG["app_name"],
                "version": CONFIG["version"],
                "exported_at": datetime.datetime.now().isoformat(),
                "total_sessions": len(self.sessions),
            },
            "sessions": self.all(),
        }
        save_json(path, report)
        log("info", f"EXPORT_JSON: збережено {len(self.sessions)} сесій → {path}")
        return str(path)

    def _save(self):
        save_json(SESSIONS_FILE, self.sessions)


# ─── GUI ───────────────────────────────────────────────────────────────
COLORS = {
    "bg":        CONFIG["theme"]["background"],
    "primary":   CONFIG["theme"]["primary_color"],
    "accent":    CONFIG["theme"]["accent"],
    "white":     "#FFFFFF",
    "text":      "#2C3E50",
    "light":     "#ECF0F1",
    "error":     "#E74C3C",
    "user_msg":  "#D6E4FF",
    "ai_msg":    "#E8F8EF",
    "gray":      "#95A5A6",
}

FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_HEADER = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 11)
FONT_SMALL  = ("Segoe UI", 9)
FONT_MONO   = ("Consolas", 10)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{CONFIG['app_name']} v{CONFIG['version']}")
        self.geometry("960x680")
        self.resizable(True, True)
        self.configure(bg=COLORS["bg"])
        self.minsize(800, 560)

        self.user_mgr    = UserManager()
        self.session_mgr = SessionManager()
        self.current_user_id: str | None = None
        self.current_session_id: str | None = None

        self._style()
        self._build_ui()
        self._show_frame("welcome")
        log("info", f"Запуск програми {CONFIG['app_name']} v{CONFIG['version']}")

    # ── Стиль ttk ────────────────────────────────────────────────────
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame",       background=COLORS["bg"])
        s.configure("Card.TFrame",  background=COLORS["white"],
                    relief="flat", borderwidth=0)
        s.configure("TLabel",       background=COLORS["bg"],
                    foreground=COLORS["text"], font=FONT_BODY)
        s.configure("Title.TLabel", font=FONT_TITLE,
                    foreground=COLORS["primary"], background=COLORS["bg"])
        s.configure("Header.TLabel", font=FONT_HEADER,
                    foreground=COLORS["text"], background=COLORS["white"])
        s.configure("Small.TLabel", font=FONT_SMALL,
                    foreground=COLORS["gray"], background=COLORS["bg"])
        s.configure("TButton", font=FONT_BODY, borderwidth=0,
                    focusthickness=0, focuscolor="none")
        s.map("TButton",
              background=[("active", COLORS["primary"])],
              foreground=[("active", COLORS["white"])])
        s.configure("Primary.TButton", background=COLORS["primary"],
                    foreground=COLORS["white"], padding=(16, 8))
        s.map("Primary.TButton",
              background=[("active", "#4A7AE8")],
              foreground=[("active", COLORS["white"])])
        s.configure("Accent.TButton", background=COLORS["accent"],
                    foreground=COLORS["white"], padding=(12, 6))
        s.configure("TEntry", fieldbackground=COLORS["white"],
                    foreground=COLORS["text"], font=FONT_BODY,
                    borderwidth=1, relief="solid")
        s.configure("TNotebook",         background=COLORS["bg"], borderwidth=0)
        s.configure("TNotebook.Tab",     font=FONT_BODY, padding=(12, 6))

    # ── Головний контейнер фреймів ────────────────────────────────────
    def _build_ui(self):
        self.frames: dict[str, tk.Frame] = {}

        # Навігаційна панель (права частина шапки)
        self.nav_bar = tk.Frame(self, bg=COLORS["primary"], height=50)
        self.nav_bar.pack(fill="x", side="top")
        self.nav_bar.pack_propagate(False)

        lbl = tk.Label(self.nav_bar, text=CONFIG["app_name"],
                       font=("Segoe UI", 13, "bold"),
                       fg=COLORS["white"], bg=COLORS["primary"])
        lbl.pack(side="left", padx=16)

        self.nav_user_lbl = tk.Label(self.nav_bar, text="",
                                     font=FONT_SMALL,
                                     fg=COLORS["light"], bg=COLORS["primary"])
        self.nav_user_lbl.pack(side="right", padx=16)

        # Контейнер
        self.container = tk.Frame(self, bg=COLORS["bg"])
        self.container.pack(fill="both", expand=True, padx=24, pady=16)

        # Будуємо всі екрани
        for name, cls in [
            ("welcome",  WelcomeFrame),
            ("register", RegisterFrame),
            ("login",    LoginFrame),
            ("main",     MainFrame),
            ("chat",     ChatFrame),
            ("history",  HistoryFrame),
            ("export",   ExportFrame),
        ]:
            frame = cls(self.container, self)
            self.frames[name] = frame
            frame.place(relwidth=1, relheight=1)

    def _show_frame(self, name: str):
        frame = self.frames[name]
        frame.lift()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def go(self, name: str):
        self._show_frame(name)

    def set_user(self, uid: str):
        self.current_user_id = uid
        user = self.user_mgr.get(uid)
        if user:
            self.nav_user_lbl.config(text=f"👤 {user['name']}")

    def logout(self):
        if self.current_session_id:
            self.session_mgr.end(self.current_session_id)
            self.current_session_id = None
        self.current_user_id = None
        self.nav_user_lbl.config(text="")
        self.go("welcome")
        log("info", "Вихід з облікового запису")


# ─── Екрани (фрейми) ───────────────────────────────────────────────────
class WelcomeFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build()

    def _build(self):
        # Центруємо вміст
        inner = tk.Frame(self, bg=COLORS["bg"])
        inner.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(inner, text="🧠", font=("Segoe UI", 48),
                 bg=COLORS["bg"]).pack(pady=(0, 8))
        tk.Label(inner, text=CONFIG["app_name"],
                 font=FONT_TITLE, fg=COLORS["primary"],
                 bg=COLORS["bg"]).pack()
        tk.Label(inner,
                 text="Ваш персональний ШІ-помічник для підтримки психічного здоров'я",
                 font=FONT_BODY, fg=COLORS["gray"],
                 bg=COLORS["bg"]).pack(pady=(4, 32))

        btn_frame = tk.Frame(inner, bg=COLORS["bg"])
        btn_frame.pack()
        ttk.Button(btn_frame, text="Увійти", style="Primary.TButton",
                   command=lambda: self.app.go("login")).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Зареєструватися", style="Accent.TButton",
                   command=lambda: self.app.go("register")).pack(side="left", padx=8)

        tk.Label(inner,
                 text=f"v{CONFIG['version']} · {CONFIG['author']}",
                 font=FONT_SMALL, fg=COLORS["gray"],
                 bg=COLORS["bg"]).pack(pady=(32, 0))


class RegisterFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build()

    def _build(self):
        card = tk.Frame(self, bg=COLORS["white"],
                        relief="groove", bd=1)
        card.place(relx=0.5, rely=0.5, anchor="center",
                   width=420, height=380)

        tk.Label(card, text="Реєстрація",
                 font=FONT_TITLE, fg=COLORS["primary"],
                 bg=COLORS["white"]).pack(pady=(24, 16))

        for label, attr in [("Ім'я та прізвище", "entry_name"),
                             ("Електронна пошта", "entry_email")]:
            tk.Label(card, text=label, font=FONT_SMALL,
                     fg=COLORS["gray"], bg=COLORS["white"],
                     anchor="w").pack(fill="x", padx=32)
            e = ttk.Entry(card, font=FONT_BODY)
            e.pack(fill="x", padx=32, pady=(2, 10))
            setattr(self, attr, e)

        self.err_lbl = tk.Label(card, text="", font=FONT_SMALL,
                                fg=COLORS["error"], bg=COLORS["white"])
        self.err_lbl.pack()

        ttk.Button(card, text="Зареєструватися", style="Primary.TButton",
                   command=self._submit).pack(pady=(4, 8))
        ttk.Button(card, text="← Назад",
                   command=lambda: self.app.go("welcome")).pack()

    def _submit(self):
        self.err_lbl.config(text="")
        try:
            uid = self.app.user_mgr.register(
                self.entry_name.get(), self.entry_email.get()
            )
            self.app.set_user(uid)
            self.entry_name.delete(0, "end")
            self.entry_email.delete(0, "end")
            messagebox.showinfo("Успіх", "Обліковий запис створено!")
            self.app.go("main")
        except ValueError as e:
            self.err_lbl.config(text=str(e))
        except Exception as e:
            log("error", f"Помилка реєстрації: {e}")
            self.err_lbl.config(text="Виникла помилка. Спробуйте ще раз.")


class LoginFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build()

    def _build(self):
        card = tk.Frame(self, bg=COLORS["white"],
                        relief="groove", bd=1)
        card.place(relx=0.5, rely=0.5, anchor="center",
                   width=420, height=320)

        tk.Label(card, text="Вхід",
                 font=FONT_TITLE, fg=COLORS["primary"],
                 bg=COLORS["white"]).pack(pady=(24, 16))

        tk.Label(card, text="Електронна пошта", font=FONT_SMALL,
                 fg=COLORS["gray"], bg=COLORS["white"],
                 anchor="w").pack(fill="x", padx=32)
        self.entry_email = ttk.Entry(card, font=FONT_BODY)
        self.entry_email.pack(fill="x", padx=32, pady=(2, 10))

        self.err_lbl = tk.Label(card, text="", font=FONT_SMALL,
                                fg=COLORS["error"], bg=COLORS["white"])
        self.err_lbl.pack()

        ttk.Button(card, text="Увійти", style="Primary.TButton",
                   command=self._submit).pack(pady=(4, 8))
        ttk.Button(card, text="← Назад",
                   command=lambda: self.app.go("welcome")).pack()

    def _submit(self):
        self.err_lbl.config(text="")
        email = self.entry_email.get().strip().lower()
        if not email:
            self.err_lbl.config(text="Введіть електронну пошту.")
            return
        found = None
        for uid, u in self.app.user_mgr.users.items():
            if u["email"] == email:
                found = uid
                break
        if not found:
            self.err_lbl.config(text="Користувача з такою поштою не знайдено.")
            log("warning", f"Невдала спроба входу: {email}")
            return
        self.app.set_user(found)
        self.entry_email.delete(0, "end")
        log("info", f"Вхід: {email}")
        self.app.go("main")


class MainFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build()

    def on_show(self):
        user = self.app.user_mgr.get(self.app.current_user_id or "")
        name = user["name"] if user else "Користувач"
        self.greet_lbl.config(text=f"Вітаємо, {name}! 👋")

    def _build(self):
        tk.Label(self, text="", bg=COLORS["bg"]).pack(pady=8)
        self.greet_lbl = tk.Label(self, text="Вітаємо!",
                                  font=FONT_TITLE, fg=COLORS["primary"],
                                  bg=COLORS["bg"])
        self.greet_lbl.pack()
        tk.Label(self,
                 text="Оберіть, що хочете зробити сьогодні:",
                 font=FONT_BODY, fg=COLORS["gray"],
                 bg=COLORS["bg"]).pack(pady=(4, 24))

        grid = tk.Frame(self, bg=COLORS["bg"])
        grid.pack()

        cards = [
            ("🗨️", "Нова сесія",    "Поговоріть з ШІ-терапевтом",      "chat"),
            ("📋", "Мої сесії",     "Перегляньте історію розмов",       "history"),
            ("📤", "Експорт даних", "Збережіть сесії у JSON або CSV",   "export"),
        ]
        for i, (icon, title, desc, dest) in enumerate(cards):
            card = tk.Frame(grid, bg=COLORS["white"],
                            relief="groove", bd=1, width=230, height=190)
            card.grid(row=0, column=i, padx=12, pady=4, sticky="nsew")
            card.pack_propagate(False)
            tk.Label(card, text=icon, font=("Segoe UI", 28),
                     bg=COLORS["white"]).pack(pady=(14, 2))
            tk.Label(card, text=title, font=FONT_HEADER,
                     fg=COLORS["text"], bg=COLORS["white"]).pack()
            tk.Label(card, text=desc, font=FONT_SMALL,
                     fg=COLORS["gray"], bg=COLORS["white"],
                     wraplength=180).pack(pady=(2, 8))
            ttk.Button(card, text="Відкрити", style="Primary.TButton",
                       command=lambda d=dest: self.app.go(d)).pack(pady=(0, 10))

        ttk.Button(self, text="Вийти з облікового запису",
                   command=self.app.logout).pack(pady=32)


class ChatFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build()

    def on_show(self):
        self._start_session()

    def _build(self):
        # Тема сесії
        top = tk.Frame(self, bg=COLORS["bg"])
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="Тема сесії:", font=FONT_SMALL,
                 fg=COLORS["gray"], bg=COLORS["bg"]).pack(side="left")
        self.topic_var = tk.StringVar(value="Загальна підтримка")
        topics = ["Загальна підтримка", "Тривога", "Стрес", "Сум",
                  "Проблеми зі сном", "Самооцінка", "Стосунки", "Інше"]
        ttk.Combobox(top, textvariable=self.topic_var,
                     values=topics, state="readonly",
                     font=FONT_BODY, width=22).pack(side="left", padx=8)
        ttk.Button(top, text="← Назад",
                   command=self._back).pack(side="right")
        ttk.Button(top, text="Завершити сесію", style="Accent.TButton",
                   command=self._end_session).pack(side="right", padx=8)

        # Область чату
        self.chat_area = scrolledtext.ScrolledText(
            self, state="disabled", wrap="word",
            font=FONT_BODY, bg=COLORS["white"],
            relief="groove", bd=1, padx=12, pady=8
        )
        self.chat_area.pack(fill="both", expand=True)
        self.chat_area.tag_config("user", background=COLORS["user_msg"],
                                  lmargin1=80, rmargin=8,
                                  font=("Segoe UI", 11))
        self.chat_area.tag_config("ai",   background=COLORS["ai_msg"],
                                  lmargin1=8, rmargin=80,
                                  font=("Segoe UI", 11))
        self.chat_area.tag_config("system", foreground=COLORS["gray"],
                                  justify="center", font=FONT_SMALL)

        # Поле вводу
        bot = tk.Frame(self, bg=COLORS["bg"])
        bot.pack(fill="x", pady=(8, 0))
        self.msg_entry = ttk.Entry(bot, font=FONT_BODY)
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.msg_entry.bind("<Return>", lambda e: self._send())
        ttk.Button(bot, text="Надіслати ➤", style="Primary.TButton",
                   command=self._send).pack(side="left")

    def _start_session(self):
        uid = self.app.current_user_id
        if not uid:
            self.app.go("login")
            return
        topic = self.topic_var.get()
        sid = self.app.session_mgr.start(uid, topic)
        self.app.current_session_id = sid
        self._clear_chat()
        self._append_system(f"── Сесія розпочата · Тема: {topic} ──")
        greeting = (
            "Привіт! Я МайндКер — ваш ШІ-помічник з психологічної підтримки. "
            "Я тут, щоб вислухати вас і допомогти розібратися у своїх думках та почуттях. "
            "Розкажіть, що вас турбує сьогодні?"
        )
        self._append_ai(greeting)
        self.app.session_mgr.add_message(sid, "ai", greeting)

    def _send(self):
        text = self.msg_entry.get().strip()
        if not text:
            return
        if len(text) > 2000:
            messagebox.showwarning("Занадто довге повідомлення",
                                   "Будь ласка, скоротіть повідомлення до 2000 символів.")
            return
        self.msg_entry.delete(0, "end")
        sid = self.app.current_session_id
        self._append_user(text)
        self.app.session_mgr.add_message(sid, "user", text)

        response = ai_respond(text)
        self._append_ai(response)
        self.app.session_mgr.add_message(sid, "ai", response)

    def _append_user(self, text: str):
        self._write(f"Ви: {text}\n\n", "user")

    def _append_ai(self, text: str):
        self._write(f"МайндКер: {text}\n\n", "ai")

    def _append_system(self, text: str):
        self._write(f"{text}\n", "system")

    def _write(self, text: str, tag: str):
        self.chat_area.config(state="normal")
        self.chat_area.insert("end", text, tag)
        self.chat_area.config(state="disabled")
        self.chat_area.see("end")

    def _clear_chat(self):
        self.chat_area.config(state="normal")
        self.chat_area.delete("1.0", "end")
        self.chat_area.config(state="disabled")

    def _end_session(self):
        sid = self.app.current_session_id
        if sid:
            self.app.session_mgr.end(sid)
            self.app.current_session_id = None
            self._append_system("── Сесію завершено ──")
        messagebox.showinfo("Сесія завершена",
                            "Сесію збережено. Турбуйтесь про себе! 💙")

    def _back(self):
        if self.app.current_session_id:
            if messagebox.askyesno("Вийти із чату",
                                   "Сесія буде збережена. Вийти?"):
                self._end_session()
                self.app.go("main")
        else:
            self.app.go("main")


class HistoryFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build()

    def on_show(self):
        self._refresh()

    def _build(self):
        top = tk.Frame(self, bg=COLORS["bg"])
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="Мої сесії", font=FONT_TITLE,
                 fg=COLORS["primary"], bg=COLORS["bg"]).pack(side="left")
        ttk.Button(top, text="← Назад",
                   command=lambda: self.app.go("main")).pack(side="right")

        cols = ("Дата", "Тема", "Повідомлень", "Статус")
        self.tree = ttk.Treeview(self, columns=cols,
                                 show="headings", height=16)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=180)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Область деталей
        self.detail = scrolledtext.ScrolledText(
            self, height=8, state="disabled",
            font=FONT_SMALL, bg=COLORS["light"], wrap="word"
        )
        self.detail.pack(fill="x", pady=(8, 0))

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        uid = self.app.current_user_id
        if not uid:
            return
        sessions = self.app.session_mgr.for_user(uid)
        sessions.sort(key=lambda s: s["started_at"], reverse=True)
        for s in sessions:
            date = s["started_at"][:16].replace("T", " ")
            msgs = len(s["messages"])
            status = "Завершена" if s["ended_at"] else "Активна"
            self.tree.insert("", "end", iid=s["id"],
                             values=(date, s["topic"], msgs, status))

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        sid = sel[0]
        session = self.app.session_mgr.get(sid)
        if not session:
            return
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        for msg in session["messages"]:
            role = "Ви" if msg["role"] == "user" else "МайндКер"
            self.detail.insert("end",
                               f"[{msg['timestamp'][11:16]}] {role}: {msg['text']}\n\n")
        self.detail.config(state="disabled")
        self.detail.see("1.0")


class ExportFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=COLORS["bg"])
        top.pack(fill="x", pady=(0, 16))
        tk.Label(top, text="Експорт даних", font=FONT_TITLE,
                 fg=COLORS["primary"], bg=COLORS["bg"]).pack(side="left")
        ttk.Button(top, text="← Назад",
                   command=lambda: self.app.go("main")).pack(side="right")

        # Картка JSON
        self._card(
            icon="📄", title="Експорт у JSON",
            desc=(
                "Формує структурований звіт із метаданими, "
                "всіма сесіями та повідомленнями у форматі JSON. "
                "Зручно для інтеграції з іншими системами."
            ),
            btn_text="Експортувати JSON",
            cmd=self._export_json,
        )

        # Картка CSV
        self._card(
            icon="📊", title="Експорт у CSV",
            desc=(
                "Зберігає список сесій у форматі CSV. "
                "Зручно для аналізу у таблицях (Excel, LibreOffice)."
            ),
            btn_text="Експортувати CSV",
            cmd=self._export_csv,
        )

        self.status_lbl = tk.Label(self, text="", font=FONT_BODY,
                                   fg=COLORS["accent"], bg=COLORS["bg"])
        self.status_lbl.pack(pady=8)

    def _card(self, icon, title, desc, btn_text, cmd):
        c = tk.Frame(self, bg=COLORS["white"], relief="groove", bd=1)
        c.pack(fill="x", padx=32, pady=8, ipady=8)
        tk.Label(c, text=f"{icon} {title}", font=FONT_HEADER,
                 fg=COLORS["text"], bg=COLORS["white"]).pack(anchor="w", padx=16, pady=(10, 4))
        tk.Label(c, text=desc, font=FONT_SMALL,
                 fg=COLORS["gray"], bg=COLORS["white"],
                 justify="left", wraplength=600).pack(anchor="w", padx=16)
        ttk.Button(c, text=btn_text, style="Primary.TButton",
                   command=cmd).pack(anchor="w", padx=16, pady=(6, 10))

    def _export_json(self):
        try:
            path = self.app.session_mgr.export_json()
            dest = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON файли", "*.json")],
                initialfile=Path(path).name,
            )
            if dest:
                import shutil
                shutil.copy(path, dest)
                self.status_lbl.config(text=f"✔ Збережено: {dest}")
            else:
                self.status_lbl.config(text=f"✔ Файл у папці exports: {Path(path).name}")
        except Exception as e:
            log("error", f"Помилка експорту JSON: {e}")
            messagebox.showerror("Помилка", f"Не вдалося зберегти файл:\n{e}")

    def _export_csv(self):
        import csv, io
        try:
            uid = self.app.current_user_id
            sessions = self.app.session_mgr.for_user(uid or "")
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["ID сесії", "Тема", "Розпочата", "Завершена", "Повідомлень"])
            for s in sessions:
                writer.writerow([
                    s["id"], s["topic"],
                    s["started_at"][:16].replace("T", " "),
                    (s["ended_at"] or "—")[:16].replace("T", " "),
                    len(s["messages"])
                ])
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"sessions_{ts}.csv"
            dest = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV файли", "*.csv")],
                initialfile=default_name,
            )
            if dest:
                with open(dest, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(buf.getvalue())
                self.status_lbl.config(text=f"✔ CSV збережено: {dest}")
                log("info", f"EXPORT_CSV: {dest}")
        except Exception as e:
            log("error", f"Помилка експорту CSV: {e}")
            messagebox.showerror("Помилка", f"Не вдалося зберегти файл:\n{e}")


# ─── Запуск ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        log("critical", f"Критична помилка: {e}")
        raise