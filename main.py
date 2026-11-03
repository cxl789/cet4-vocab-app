# -*- coding: utf-8 -*-
"""
看单词 App —— 安卓端（Kivy，纯 Python）
=====================================================
功能：
  1. 四级词汇库：内置 4544 个 CET-4 单词（音标 / 词性 / 中文释义 / 例句 / 真题例句），
     支持搜索、按教材单元浏览、点选加入"必看列表"。
  2. 必看列表：每日新选的单词自动入列并记录日期；四种排序方式
        (1) 添加顺序  每日新词排在已有单词后面
        (2) 字母排序  A→Z
        (3) 词族排序  按词典词族归类汇总
        (4) 随机打乱  一键洗牌
  3. 词族统计：必看词的词族分布汇总，识别"一个词带出一串"的高价值词族。

数据：
  data/cet4.json      四级词库
  data/families.json  词族库（族名 / 成员 / 词性 / 词典派生近亲）

运行：
  桌面预览： pip install kivy && python main.py
  打包 APK： 见 README.md（buildozer / GitHub Actions 云端打包）
"""

import json
import os
import random
from collections import Counter, OrderedDict
from datetime import date

from kivy.app import App
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

BASE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ 字体
# CN  = Noto Sans SC（中文；Kivy 默认 Roboto 不含汉字，必须自带）
# IPA = DejaVu Sans（音标专用：ˈ æ ʃ ə 等 IPA 字符 Noto Sans SC 没有）
FONT_CN = os.path.join(BASE, "assets", "fonts", "NotoSansSC-Regular.otf")
FONT_IPA = os.path.join(BASE, "assets", "fonts", "DejaVuSans.ttf")
if os.path.exists(FONT_CN):
    LabelBase.register(name="CN", fn_regular=FONT_CN)
if os.path.exists(FONT_IPA):
    LabelBase.register(name="IPA", fn_regular=FONT_IPA)

C_PRIMARY = "#3A6FF0"
C_DANGER = "#E5534B"
C_CARD = "#FFFFFF"
C_TEXT = "#1F2328"
C_SUB = "#6B7280"
C_LINE = "#E5E7EB"

SORT_MODES = ["添加顺序", "字母排序", "词族排序", "随机打乱"]
ROW_H = dp(58)


def _resource(name):
    """定位打包进 APK 的数据文件"""
    for base in (BASE, os.path.join(BASE, "data")):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def mk_label(text="", halign="left", valign="middle", shorten=True, **kw):
    """
    统一创建 Label：
      - 默认用中文字体 CN
      - 自动把 text_size 绑到自身尺寸（Kivy 的 halign 只有设了 text_size 才生效，
        否则文字会居中显示而不是左对齐）
    """
    kw.setdefault("font_name", "CN")
    lab = Label(text=text, halign=halign, valign=valign, shorten=shorten,
                shorten_from="right", **kw)

    def _fit(*_):
        if lab.width > 1 and lab.height > 1:
            lab.text_size = (lab.width, lab.height)

    lab.bind(size=_fit, pos=_fit)
    return lab


def _mk_button(text, bg=C_PRIMARY, fg="#FFFFFF", size=13, w=None, h=None):
    b = Button(text=text, font_name="CN", font_size=sp(size),
               background_normal="", background_color=bg, color=fg)
    if w:
        b.size_hint_x = None
        b.width = w
    if h:
        b.size_hint_y = None
        b.height = h
    return b


def _sync_rv_height(rv, row_h=ROW_H):
    """RecycleView 的 layout manager 高度必须等于内容总高，
    否则 viewport 只有 100px，列表既不滚动也只显示一两行。"""
    lm = rv.layout_manager
    if lm is None:
        return
    lm.height = max(len(rv.data) * row_h, rv.height)


# ------------------------------------------------------------ 列表行组件

class RowItem(RecycleDataViewBehavior, BoxLayout):
    """RecycleView 行：既可以是普通单词行，也可以是词族标题行"""

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.data = data or {}
        self.size_hint_y = None
        self._render()

    def _render(self):
        self.clear_widgets()
        d = self.data
        if d.get("type") == "header":
            strip = Widget(size_hint_x=None, width=dp(4))
            with strip.canvas.before:
                Color(rgba=[0.22, 0.43, 0.94, 1])
                rect = Rectangle(pos=strip.pos, size=strip.size)
            strip.bind(pos=lambda *_: setattr(rect, "pos", strip.pos),
                       size=lambda *_: setattr(rect, "size", strip.size))
            row = BoxLayout(orientation="horizontal", spacing=dp(6),
                            size_hint_y=None, height=ROW_H)
            row.add_widget(strip)
            row.add_widget(mk_label(
                text=f"{d.get('fam', '')}  ·  词族 · 已选 {d.get('count', 0)} 词",
                font_size=sp(14), bold=True, color=C_PRIMARY))
            self.add_widget(row)
            return

        word = d.get("w", "")
        selected = d.get("selected", False)

        row = BoxLayout(orientation="horizontal", spacing=dp(8),
                        size_hint_y=None, height=ROW_H)
        info = BoxLayout(orientation="vertical", spacing=dp(1))
        info.add_widget(mk_label(text=word, font_size=sp(16), bold=True,
                                 color=C_TEXT, size_hint_y=None, height=dp(24)))

        # 音标用 IPA 字体渲染，中文释义用中文字体（markup 混排）
        ph = d.get("ph") or ""
        ph_html = f"[font=IPA]/{ph}/[/font]" if ph else ""
        sub = mk_label(text=ph_html + ("  " if ph else "") + (d.get("extra") or ""),
                       font_size=sp(11), color=C_SUB, markup=True,
                       size_hint_y=None, height=dp(20))
        info.add_widget(sub)
        row.add_widget(info)

        row.add_widget(mk_label(text=d.get("fam", ""), font_size=sp(11),
                                color=C_PRIMARY, halign="center",
                                size_hint_x=None, width=dp(72)))

        btn = _mk_button("移除" if selected else "加入",
                         bg=C_DANGER if selected else C_PRIMARY,
                         size=13, w=dp(60), h=dp(32))
        btn.bind(on_release=lambda *_: self._toggle())
        row.add_widget(btn)
        self.add_widget(row)

    def _toggle(self):
        app = App.get_running_app()
        w = self.data.get("w")
        if not w:
            return
        if app.is_selected(w):
            app.remove_word(w)
        else:
            app.add_word(w)


Factory.register("RowItem", cls=RowItem)


# --------------------------------------------------------------- 底部导航

class NavBar(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.size_hint_y = None
        self.height = dp(54)
        self.buttons = {}
        for key, text in (("library", "四级词库"), ("must", "必看列表"), ("stats", "词族统计")):
            b = _mk_button(text, bg="#FFFFFF", fg=C_SUB, size=14)
            b.bind(on_release=lambda inst, k=key: self.go(k))
            self.add_widget(b)
            self.buttons[key] = b

    def go(self, key):
        app = App.get_running_app()
        app.sm.current = key
        self.refresh()

    def refresh(self):
        cur = App.get_running_app().sm.current
        for k, b in self.buttons.items():
            b.background_color = C_PRIMARY if k == cur else "#FFFFFF"
            b.color = "#FFFFFF" if k == cur else C_SUB


# --------------------------------------------------------------- 词库页

class LibraryScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.query = ""
        self.unit = "全部"
        self.build_ui()
        self.reload()

    def build_ui(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))

        top = BoxLayout(orientation="horizontal", spacing=dp(6),
                        size_hint_y=None, height=dp(38))
        self.search = TextInput(
            hint_text="搜索单词或中文释义…", font_name="CN", font_size=sp(14),
            multiline=False, size_hint_y=None, height=dp(38),
            background_color=C_CARD, foreground_color=C_TEXT, cursor_color=C_PRIMARY)
        self.search.bind(text=lambda inst, val: self.on_search(val))
        top.add_widget(self.search)
        clear = _mk_button("清除", bg=C_LINE, fg=C_TEXT, size=13, w=dp(58))
        clear.bind(on_release=lambda *_: self.clear_search())
        top.add_widget(clear)
        root.add_widget(top)

        units = BoxLayout(orientation="horizontal", spacing=dp(4),
                          size_hint_y=None, height=dp(32))
        self.unit_buttons = {}
        for u in ["全部", "CET4_1", "CET4_2", "CET4_3"]:
            b = _mk_button(u, bg=C_LINE, fg=C_TEXT, size=12)
            b.bind(on_release=lambda inst, uu=u: self.set_unit(uu))
            units.add_widget(b)
            self.unit_buttons[u] = b
        root.add_widget(units)

        self.counter = mk_label(text="", font_size=sp(12), color=C_SUB,
                                size_hint_y=None, height=dp(22))
        root.add_widget(self.counter)

        self.rv = RecycleView()
        layout = RecycleBoxLayout(default_size=(None, ROW_H),
                                  default_size_hint=(1, None),
                                  size_hint_y=None, orientation="vertical",
                                  viewclass=RowItem)
        self.rv.add_widget(layout)
        root.add_widget(self.rv)

        self.add_widget(root)

    def clear_search(self):
        self.search.text = ""
        self.on_search("")

    def set_unit(self, u):
        self.unit = u
        for k, b in self.unit_buttons.items():
            b.background_color = C_PRIMARY if k == u else C_LINE
            b.color = "#FFFFFF" if k == u else C_TEXT
        self.reload()

    def on_search(self, val):
        self.query = (val or "").strip().lower()
        self.reload()

    def reload(self):
        app = App.get_running_app()
        data = []
        for e in app.cet4:
            if self.unit != "全部" and e["unit"] != self.unit:
                continue
            if self.query and self.query not in e["w"] and self.query not in e["cn"].lower():
                continue
            data.append({
                "type": "word", "w": e["w"], "ph": e["ph"],
                "extra": e["cn"][:36], "fam": app.family_of(e["w"]),
                "selected": app.is_selected(e["w"]),
            })
        self.rv.data = data
        _sync_rv_height(self.rv)
        self.counter.text = f"共 {len(data)} 个单词 · 已选 {len(app.selected)} 个"


# ------------------------------------------------------------- 必看列表页

class MustScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.mode = "添加顺序"
        self.build_ui()
        self.reload()

    def build_ui(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))

        bar = BoxLayout(orientation="horizontal", spacing=dp(4),
                        size_hint_y=None, height=dp(34))
        self.mode_buttons = {}
        for m in SORT_MODES:
            b = _mk_button(m, bg=C_LINE, fg=C_TEXT, size=12)
            b.bind(on_release=lambda inst, mm=m: self.set_mode(mm))
            bar.add_widget(b)
            self.mode_buttons[m] = b
        root.add_widget(bar)

        tools = BoxLayout(orientation="horizontal", spacing=dp(6),
                          size_hint_y=None, height=dp(32))
        self.shuffle_btn = _mk_button("🎲 重新洗牌", bg=C_LINE, fg=C_TEXT,
                                      size=12, w=dp(96))
        self.shuffle_btn.bind(on_release=lambda *_: self.shuffle())
        tools.add_widget(self.shuffle_btn)
        self.info = mk_label(text="", font_size=sp(12), color=C_SUB)
        tools.add_widget(self.info)
        root.add_widget(tools)

        self.rv = RecycleView()
        layout = RecycleBoxLayout(default_size=(None, ROW_H),
                                  default_size_hint=(1, None),
                                  size_hint_y=None, orientation="vertical",
                                  viewclass=RowItem)
        self.rv.add_widget(layout)
        root.add_widget(self.rv)

        self.add_widget(root)

    def set_mode(self, m):
        self.mode = m
        for k, b in self.mode_buttons.items():
            b.background_color = C_PRIMARY if k == m else C_LINE
            b.color = "#FFFFFF" if k == m else C_TEXT
        self.reload()

    def shuffle(self):
        App.get_running_app().reshuffle()
        self.reload()

    def reload(self):
        app = App.get_running_app()
        self.rv.data = app.build_must_rows(self.mode)
        _sync_rv_height(self.rv)
        self.info.text = f"共 {len(app.selected)} 词 · 模式：{self.mode}"


# ------------------------------------------------------------- 统计页

class StatsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.root_box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        self.add_widget(self.root_box)

    def on_enter(self):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        self.root_box.clear_widgets()

        self.root_box.add_widget(mk_label(
            text="必看词 · 词族分布", font_size=sp(18), bold=True,
            color=C_TEXT, size_hint_y=None, height=dp(30)))

        fams = app.family_counter()
        stats = ((len(app.selected), "必看单词"),
                 (len(fams), "覆盖词族"),
                 (sum(1 for v in fams.values() if v >= 3), "高产词族(≥3)"))
        row = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(6))
        for num, lab in stats:
            inner = BoxLayout(orientation="vertical")
            inner.add_widget(mk_label(text=str(num), font_size=sp(20), bold=True,
                                      color=C_PRIMARY, halign="center"))
            inner.add_widget(mk_label(text=lab, font_size=sp(11), color=C_SUB,
                                      halign="center"))
            row.add_widget(inner)
        self.root_box.add_widget(row)

        self.root_box.add_widget(mk_label(
            text="高产词族（一个词根带出一串，优先记）",
            font_size=sp(14), bold=True, color=C_TEXT,
            size_hint_y=None, height=dp(26)))

        top = app.family_top(15)
        scroll = ScrollView()
        inner = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        inner.bind(minimum_height=inner.setter("height"))
        if not top:
            inner.add_widget(mk_label(text="还没有数据，先去词库挑几个单词",
                                      font_size=sp(13), color=C_SUB))
        maxn = max((n for _, n in top), default=1)
        for fam, n in top:
            line = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
            line.add_widget(mk_label(text=fam, font_size=sp(14), color=C_TEXT,
                                     size_hint_x=0.36))
            blocks = "█" * max(1, round(n / maxn * 12))
            line.add_widget(mk_label(text=blocks, font_size=sp(13), color=C_PRIMARY))
            line.add_widget(mk_label(text=str(n), font_size=sp(13), color=C_SUB,
                                     halign="right", size_hint_x=None, width=dp(26)))
            inner.add_widget(line)
        scroll.add_widget(inner)
        self.root_box.add_widget(scroll)


# ----------------------------------------------------------------- 主程序

class VocabApp(App):
    title = "看单词"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.cet4 = []
        self.cet4_by_word = {}
        self.families = {}
        self.word2family = {}
        self.relatives = {}
        self.selected = OrderedDict()   # word -> {"added": "YYYY-MM-DD"}
        self.shuffle_seed = random.randint(0, 10 ** 6)
        self.sm = None
        self.nav = None

    # ---- 数据加载
    def load_data(self):
        p = _resource("cet4.json")
        if p:
            self.cet4 = json.load(open(p, encoding="utf-8"))
            self.cet4_by_word = {e["w"]: e for e in self.cet4}
        p = _resource("families.json")
        if p:
            d = json.load(open(p, encoding="utf-8"))
            self.families = d.get("families", {})
            self.word2family = d.get("word2family", {})
            self.relatives = d.get("relatives", {})
        self.load_selection()

    def _selection_path(self):
        d = self.user_data_dir
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "selection.json")

    def load_selection(self):
        p = self._selection_path()
        if os.path.exists(p):
            try:
                raw = json.load(open(p, encoding="utf-8"))
                self.selected = OrderedDict(raw.get("selected", {}))
            except Exception:
                self.selected = OrderedDict()

    def save_selection(self):
        try:
            with open(self._selection_path(), "w", encoding="utf-8") as f:
                json.dump({"selected": self.selected}, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print("保存失败:", e)

    # ---- 选词操作
    def is_selected(self, w):
        return w in self.selected

    def add_word(self, w):
        self.selected[w] = {"added": date.today().isoformat()}
        self.save_selection()
        self.refresh_all()

    def remove_word(self, w):
        self.selected.pop(w, None)
        self.save_selection()
        self.refresh_all()

    def refresh_all(self):
        if self.sm is not None:
            for s in self.sm.screens:
                if hasattr(s, "reload"):
                    s.reload()
        if self.nav is not None:
            self.nav.refresh()

    def reshuffle(self):
        self.shuffle_seed = random.randint(0, 10 ** 6)

    # ---- 词族相关
    def family_of(self, w):
        return self.word2family.get(w, "")

    def family_counter(self):
        c = Counter(self.family_of(w) for w in self.selected)
        c.pop("", None)
        return c

    def family_top(self, n=15):
        return self.family_counter().most_common(n)

    # ---- 必看列表行（按排序方式组织）
    def build_must_rows(self, mode):
        items = list(self.selected.items())
        rows = []

        if mode == "添加顺序":
            # 同一天内保持录入次序 → 每日新词自然排在一列表后面
            items.sort(key=lambda kv: kv[1]["added"])
            for w, meta in items:
                rows.append(self._word_row(w, meta))

        elif mode == "字母排序":
            items.sort(key=lambda kv: kv[0].lower())
            for w, meta in items:
                rows.append(self._word_row(w, meta))

        elif mode == "词族排序":
            fams = OrderedDict()
            for w, meta in items:
                fams.setdefault(self.family_of(w) or "未归族", []).append((w, meta))
            for fam in sorted(fams):
                rows.append({"type": "header", "fam": fam, "count": len(fams[fam])})
                for w, meta in sorted(fams[fam], key=lambda kv: kv[0]):
                    rows.append(self._word_row(w, meta))

        else:  # 随机打乱
            random.Random(self.shuffle_seed).shuffle(items)
            for w, meta in items:
                rows.append(self._word_row(w, meta))
        return rows

    def _word_row(self, w, meta):
        e = self.cet4_by_word.get(w, {})
        rel = self.relatives.get(w, [])
        extra = e.get("cn", "")[:36]
        if rel:
            extra = (extra + "  ·  近亲:" + ",".join(rel[:3])).strip()
        return {
            "type": "word", "w": w, "ph": e.get("ph", ""), "extra": extra,
            "fam": self.family_of(w), "selected": True,
            "added": meta.get("added", ""),
        }

    # ---- 界面装配
    def build(self):
        self.load_data()
        self.sm = ScreenManager(transition=NoTransition())
        self.sm.add_widget(LibraryScreen(name="library"))
        self.sm.add_widget(MustScreen(name="must"))
        self.sm.add_widget(StatsScreen(name="stats"))
        self.nav = NavBar()

        root = BoxLayout(orientation="vertical")
        root.add_widget(self.sm)
        root.add_widget(self.nav)
        self.nav.refresh()

        # 安卓返回键：在子页面先回到词库页，而不是直接退出
        Window.bind(on_keyboard=self._on_keyboard)
        return root

    def _on_keyboard(self, window, key, *args):
        if key == 27 and self.sm.current != "library":  # 27 = ESC / 返回
            self.sm.current = "library"
            self.nav.refresh()
            return True
        return False


if __name__ == "__main__":
    if platform not in ("android", "ios"):
        Window.size = (440, 820)   # 桌面预览按手机尺寸显示
    VocabApp().run()
