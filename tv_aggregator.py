import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
from PIL import Image, ImageTk
import io
import threading
import json
import os


def resource_path(relative_path: str) -> str:
    """Resolve path for both dev mode and PyInstaller --onefile bundle."""
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w300"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".tv_aggregator_config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)


STATUS_MAP = {
    "Returning Series": "🟢 连载中",
    "Ended": "⛔ 已完结",
    "Canceled": "❌ 已取消",
    "In Production": "🎬 制作中",
    "Pilot": "🎬 试播",
}


class TVAggregator:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("美剧信息聚合器")
        self.root.geometry("1150x720")
        self.root.minsize(900, 600)

        self.config = load_config()
        self.api_key: str = self.config.get("api_key", "")
        self.current_show: dict | None = None
        self.results_data: list[dict] = []

        # Set window icon (works after PyInstaller packaging on Windows)
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self._build_styles()
        self._build_menu()
        self._build_ui()

        if not self.api_key:
            self.root.after(200, self.prompt_api_key)
        else:
            self.root.after(300, self.load_popular)

    # ── styles ─────────────────────────────────────────────────────────────
    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Helvetica", 15, "bold"))
        style.configure("Rating.TLabel", font=("Helvetica", 13, "bold"), foreground="#e8a900")
        style.configure("Meta.TLabel", font=("Helvetica", 10))
        style.configure("Gray.TLabel", font=("Helvetica", 9), foreground="gray")

    # ── menu ───────────────────────────────────────────────────────────────
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="修改 API Key", command=self.prompt_api_key)
        settings_menu.add_separator()
        settings_menu.add_command(label="加载热门美剧", command=self.load_popular)
        settings_menu.add_command(label="加载今日播出", command=self.load_airing_today)
        settings_menu.add_command(label="加载高分美剧", command=self.load_top_rated)

    # ── main UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        self._build_left_panel(main)
        self._build_right_panel(main)

    def _build_left_panel(self, parent):
        left = ttk.Frame(parent, width=270)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        # search
        search_lf = ttk.LabelFrame(left, text="搜索", padding=7)
        search_lf.pack(fill=tk.X, pady=(0, 7))

        self.search_var = tk.StringVar()
        entry = ttk.Entry(search_lf, textvariable=self.search_var, font=("Helvetica", 11))
        entry.pack(fill=tk.X, pady=(0, 5))
        entry.bind("<Return>", lambda _: self.search())

        btn_row = ttk.Frame(search_lf)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="搜索", command=self.search).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(btn_row, text="热门", command=self.load_popular).pack(side=tk.LEFT, padx=(4, 0), fill=tk.X, expand=True)
        ttk.Button(btn_row, text="高分", command=self.load_top_rated).pack(side=tk.LEFT, padx=(4, 0), fill=tk.X, expand=True)

        # filter row
        filter_row = ttk.Frame(left)
        filter_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(filter_row, text="筛选:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar(value="全部")
        filter_cb = ttk.Combobox(filter_row, textvariable=self.filter_var, state="readonly", width=12,
                                  values=["全部", "剧情", "喜剧", "犯罪", "科幻", "动作", "惊悚", "恐怖", "纪录"])
        filter_cb.pack(side=tk.LEFT, padx=(4, 0))
        filter_cb.bind("<<ComboboxSelected>>", lambda _: self.apply_filter())

        # results list
        result_lf = ttk.LabelFrame(left, text="结果列表", padding=4)
        result_lf.pack(fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(result_lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_list = tk.Listbox(
            result_lf, yscrollcommand=sb.set,
            font=("Helvetica", 10), selectmode=tk.SINGLE,
            activestyle="dotbox", relief=tk.FLAT, bd=0,
        )
        self.result_list.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.result_list.yview)
        self.result_list.bind("<<ListboxSelect>>", self.on_select)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(left, textvariable=self.status_var, style="Gray.TLabel").pack(anchor=tk.W, pady=(4, 0))

    def _build_right_panel(self, parent):
        right = ttk.Frame(parent)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # top info strip
        top = ttk.Frame(right)
        top.pack(fill=tk.X, pady=(0, 8))

        self.poster_label = ttk.Label(top)
        self.poster_label.pack(side=tk.LEFT, padx=(0, 12))
        self._show_placeholder_poster()

        info = ttk.Frame(top)
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.title_var = tk.StringVar(value="请搜索或选择一部美剧")
        ttk.Label(info, textvariable=self.title_var, style="Title.TLabel", wraplength=650).pack(anchor=tk.W)

        self.orig_title_var = tk.StringVar()
        ttk.Label(info, textvariable=self.orig_title_var, font=("Helvetica", 10), foreground="gray").pack(anchor=tk.W)

        meta_row = ttk.Frame(info)
        meta_row.pack(fill=tk.X, pady=6)
        self.rating_var = tk.StringVar()
        ttk.Label(meta_row, textvariable=self.rating_var, style="Rating.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        self.year_var = tk.StringVar()
        ttk.Label(meta_row, textvariable=self.year_var, style="Meta.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        self.status_show_var = tk.StringVar()
        ttk.Label(meta_row, textvariable=self.status_show_var, style="Meta.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        self.seasons_var = tk.StringVar()
        ttk.Label(meta_row, textvariable=self.seasons_var, style="Meta.TLabel").pack(side=tk.LEFT)

        self.genres_var = tk.StringVar()
        ttk.Label(info, textvariable=self.genres_var, font=("Helvetica", 10), foreground="#555").pack(anchor=tk.W)

        self.networks_var = tk.StringVar()
        ttk.Label(info, textvariable=self.networks_var, font=("Helvetica", 10), foreground="#555").pack(anchor=tk.W)

        # tabs
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill=tk.BOTH, expand=True)

        self._build_overview_tab()
        self._build_episodes_tab()
        self._build_cast_tab()
        self._build_watch_tab()
        self._build_similar_tab()

    # ── tabs ───────────────────────────────────────────────────────────────
    def _build_overview_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="概述")
        self.overview_text = tk.Text(
            tab, wrap=tk.WORD, font=("Helvetica", 11),
            relief=tk.FLAT, state=tk.DISABLED, height=10,
            bg=self.root.cget("bg"),
        )
        self.overview_text.pack(fill=tk.BOTH, expand=True)

    def _build_episodes_tab(self):
        tab = ttk.Frame(self.nb, padding=5)
        self.nb.add(tab, text="剧集")

        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(ctrl, text="选择季:").pack(side=tk.LEFT)
        self.season_var = tk.StringVar()
        self.season_combo = ttk.Combobox(ctrl, textvariable=self.season_var, state="readonly", width=12)
        self.season_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.season_combo.bind("<<ComboboxSelected>>", self.load_episodes)

        cols = ("ep", "title", "airdate", "rating", "runtime")
        self.ep_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for col, label, width, anchor in [
            ("ep", "集数", 60, tk.CENTER),
            ("title", "标题", 320, tk.W),
            ("airdate", "播出日期", 100, tk.CENTER),
            ("rating", "评分", 70, tk.CENTER),
            ("runtime", "时长(分)", 70, tk.CENTER),
        ]:
            self.ep_tree.heading(col, text=label)
            self.ep_tree.column(col, width=width, anchor=anchor)
        sb = ttk.Scrollbar(tab, command=self.ep_tree.yview)
        self.ep_tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.ep_tree.pack(fill=tk.BOTH, expand=True)

    def _build_cast_tab(self):
        tab = ttk.Frame(self.nb, padding=5)
        self.nb.add(tab, text="演员")
        cols = ("name", "character", "popularity")
        self.cast_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for col, label, width in [("name", "演员姓名", 220), ("character", "饰演角色", 220), ("popularity", "人气", 80)]:
            self.cast_tree.heading(col, text=label)
            self.cast_tree.column(col, width=width, anchor=tk.W if col != "popularity" else tk.CENTER)
        sb = ttk.Scrollbar(tab, command=self.cast_tree.yview)
        self.cast_tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cast_tree.pack(fill=tk.BOTH, expand=True)

    def _build_watch_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="观看平台")
        self.watch_text = tk.Text(
            tab, wrap=tk.WORD, font=("Helvetica", 11),
            relief=tk.FLAT, state=tk.DISABLED,
            bg=self.root.cget("bg"),
        )
        self.watch_text.pack(fill=tk.BOTH, expand=True)

    def _build_similar_tab(self):
        tab = ttk.Frame(self.nb, padding=5)
        self.nb.add(tab, text="相似推荐")
        cols = ("name", "year", "rating", "overview")
        self.similar_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for col, label, width in [
            ("name", "剧集名称", 220),
            ("year", "年份", 60),
            ("rating", "评分", 70),
            ("overview", "简介", 380),
        ]:
            self.similar_tree.heading(col, text=label)
            self.similar_tree.column(col, width=width, anchor=tk.W if col not in ("year", "rating") else tk.CENTER)
        sb = ttk.Scrollbar(tab, command=self.similar_tree.yview)
        self.similar_tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.similar_tree.pack(fill=tk.BOTH, expand=True)
        self.similar_tree.bind("<<TreeviewSelect>>", self.on_similar_select)

    # ── api ────────────────────────────────────────────────────────────────
    def api_get(self, endpoint: str, params: dict | None = None) -> dict | None:
        if not self.api_key:
            self.root.after(0, self.prompt_api_key)
            return None
        p = {"api_key": self.api_key, "language": "zh-CN"}
        if params:
            p.update(params)
        try:
            r = requests.get(f"{TMDB_BASE_URL}{endpoint}", params=p, timeout=12)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if r.status_code == 401:
                self.root.after(0, lambda: messagebox.showerror("API Key 无效", "请检查 API Key 是否正确。"))
            else:
                self.root.after(0, lambda: self.status_var.set(f"HTTP 错误: {e}"))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"网络错误: {e}"))
        return None

    # ── settings ───────────────────────────────────────────────────────────
    def prompt_api_key(self):
        key = simpledialog.askstring(
            "设置 TMDB API Key",
            "请输入你的 TMDB API Key:\n\n免费注册地址: https://www.themoviedb.org/settings/api\n(注册后在 API 页面复制 API Key (v3 auth))",
            initialvalue=self.api_key,
            parent=self.root,
        )
        if key and key.strip():
            self.api_key = key.strip()
            self.config["api_key"] = self.api_key
            save_config(self.config)
            self.load_popular()

    # ── data loading ───────────────────────────────────────────────────────
    def search(self):
        q = self.search_var.get().strip()
        if not q:
            return
        self.status_var.set("搜索中...")
        threading.Thread(target=self._run, args=(self._search_task, q), daemon=True).start()

    def _search_task(self, q):
        data = self.api_get("/search/tv", {"query": q, "page": 1})
        return data.get("results", []) if data else []

    def load_popular(self):
        self.status_var.set("加载热门美剧...")
        threading.Thread(target=self._run, args=(self._popular_task,), daemon=True).start()

    def _popular_task(self):
        results = []
        for page in (1, 2):
            data = self.api_get("/tv/popular", {"page": page})
            if data:
                results += data.get("results", [])
        us = [r for r in results if "US" in r.get("origin_country", [])]
        return us if us else results[:30]

    def load_top_rated(self):
        self.status_var.set("加载高分美剧...")
        threading.Thread(target=self._run, args=(self._top_rated_task,), daemon=True).start()

    def _top_rated_task(self):
        data = self.api_get("/tv/top_rated", {"page": 1})
        if not data:
            return []
        results = data.get("results", [])
        us = [r for r in results if "US" in r.get("origin_country", [])]
        return us if us else results[:30]

    def load_airing_today(self):
        self.status_var.set("加载今日播出...")
        threading.Thread(target=self._run, args=(self._airing_task,), daemon=True).start()

    def _airing_task(self):
        data = self.api_get("/tv/airing_today", {"page": 1})
        if not data:
            return []
        results = data.get("results", [])
        us = [r for r in results if "US" in r.get("origin_country", [])]
        return us if us else results[:30]

    def _run(self, task, *args):
        results = task(*args)
        self.root.after(0, self._update_results, results)

    def _update_results(self, results: list[dict]):
        self.results_data = results
        self.apply_filter()

    def apply_filter(self):
        genre_map = {
            "剧情": 18, "喜剧": 35, "犯罪": 80, "科幻": 10765,
            "动作": 10759, "惊悚": 53, "恐怖": 27, "纪录": 99,
        }
        chosen = self.filter_var.get()
        gid = genre_map.get(chosen)
        filtered = self.results_data if not gid else [
            r for r in self.results_data if gid in r.get("genre_ids", [])
        ]
        self.result_list.delete(0, tk.END)
        for show in filtered:
            name = show.get("name", "Unknown")
            year = (show.get("first_air_date") or "")[:4]
            rating = show.get("vote_average", 0)
            star = "⭐" if rating >= 8 else "  "
            self.result_list.insert(tk.END, f"{star} {name}  ({year})  {rating:.1f}")
        self.status_var.set(f"共 {len(filtered)} 条结果")

    # ── selection ──────────────────────────────────────────────────────────
    def on_select(self, _event):
        sel = self.result_list.curselection()
        if not sel:
            return
        # map back through filter
        genre_map = {
            "剧情": 18, "喜剧": 35, "犯罪": 80, "科幻": 10765,
            "动作": 10759, "惊悚": 53, "恐怖": 27, "纪录": 99,
        }
        chosen = self.filter_var.get()
        gid = genre_map.get(chosen)
        filtered = self.results_data if not gid else [
            r for r in self.results_data if gid in r.get("genre_ids", [])
        ]
        if sel[0] >= len(filtered):
            return
        show = filtered[sel[0]]
        self.load_show_details(show["id"])

    def on_similar_select(self, _event):
        sel = self.similar_tree.selection()
        if not sel:
            return
        item = self.similar_tree.item(sel[0])
        show_id = item["tags"][0] if item["tags"] else None
        if show_id:
            self.load_show_details(int(show_id))

    def load_show_details(self, show_id: int):
        self.status_var.set("加载详情...")
        threading.Thread(target=self._details_thread, args=(show_id,), daemon=True).start()

    def _details_thread(self, show_id: int):
        data = self.api_get(
            f"/tv/{show_id}",
            {"append_to_response": "credits,watch/providers,similar"},
        )
        if data:
            self.root.after(0, self._display_show, data)

    # ── display ────────────────────────────────────────────────────────────
    def _display_show(self, data: dict):
        self.current_show = data

        self.title_var.set(data.get("name", ""))
        orig = data.get("original_name", "")
        self.orig_title_var.set(f"原名: {orig}" if orig != data.get("name") else "")

        rating = data.get("vote_average", 0)
        votes = data.get("vote_count", 0)
        self.rating_var.set(f"⭐ {rating:.1f}  ({votes:,} 票)")

        first = (data.get("first_air_date") or "")[:4]
        last = (data.get("last_air_date") or "")[:4]
        self.year_var.set(f"📅 {first}–{last}" if last and last != first else f"📅 {first}")

        self.status_show_var.set(STATUS_MAP.get(data.get("status", ""), data.get("status", "")))

        n_s = data.get("number_of_seasons", 0)
        n_e = data.get("number_of_episodes", 0)
        self.seasons_var.set(f"📺 {n_s} 季 / {n_e} 集")

        self.genres_var.set(" · ".join(g["name"] for g in data.get("genres", [])))

        networks = " / ".join(n["name"] for n in data.get("networks", []))
        self.networks_var.set(f"📡 {networks}" if networks else "")

        # overview
        self._set_text(self.overview_text, data.get("overview") or "暂无简介")

        # cast
        self.cast_tree.delete(*self.cast_tree.get_children())
        for actor in (data.get("credits") or {}).get("cast", [])[:40]:
            self.cast_tree.insert("", tk.END, values=(
                actor.get("name", ""),
                actor.get("character", ""),
                f"{actor.get('popularity', 0):.1f}",
            ))

        # watch providers
        wp = (data.get("watch/providers") or {}).get("results", {})
        region = wp.get("CN") or wp.get("US") or {}
        lines = []
        if region.get("link"):
            lines.append(f"TMDB 链接: {region['link']}\n")
        for key, label in [("flatrate", "订阅"), ("rent", "租借"), ("buy", "购买"), ("free", "免费")]:
            providers = region.get(key, [])
            if providers:
                names = "、".join(p["provider_name"] for p in providers)
                lines.append(f"【{label}】{names}")
        self._set_text(self.watch_text, "\n".join(lines) if lines else "暂无该地区观看平台信息")

        # similar
        self.similar_tree.delete(*self.similar_tree.get_children())
        for s in (data.get("similar") or {}).get("results", [])[:30]:
            self.similar_tree.insert("", tk.END, tags=(str(s["id"]),), values=(
                s.get("name", ""),
                (s.get("first_air_date") or "")[:4],
                f"{s.get('vote_average', 0):.1f}",
                (s.get("overview") or "")[:80],
            ))

        # seasons
        seasons = [s for s in data.get("seasons", []) if s["season_number"] > 0]
        labels = [f"第 {s['season_number']} 季 ({s.get('episode_count', '?')} 集)" for s in seasons]
        self.season_combo["values"] = labels
        if labels:
            self.season_combo.set(labels[0])
            self.load_episodes()

        # poster
        poster_path = data.get("poster_path")
        if poster_path:
            threading.Thread(target=self._load_poster, args=(poster_path,), daemon=True).start()
        else:
            self._show_placeholder_poster()

        self.status_var.set(f"已加载: {data.get('name', '')}")

    # ── episodes ───────────────────────────────────────────────────────────
    def load_episodes(self, _event=None):
        if not self.current_show:
            return
        sel = self.season_var.get()
        if not sel:
            return
        # parse season number from "第 N 季 ..."
        try:
            season_num = int(sel.split()[1])
        except (IndexError, ValueError):
            return
        show_id = self.current_show["id"]
        threading.Thread(target=self._episodes_thread, args=(show_id, season_num), daemon=True).start()

    def _episodes_thread(self, show_id: int, season_num: int):
        data = self.api_get(f"/tv/{show_id}/season/{season_num}")
        if data:
            self.root.after(0, self._display_episodes, data)

    def _display_episodes(self, data: dict):
        self.ep_tree.delete(*self.ep_tree.get_children())
        for ep in data.get("episodes", []):
            self.ep_tree.insert("", tk.END, values=(
                f"E{ep.get('episode_number', 0):02d}",
                ep.get("name", ""),
                ep.get("air_date", ""),
                f"⭐{ep.get('vote_average', 0):.1f}" if ep.get("vote_average") else "",
                ep.get("runtime") or "",
            ))

    # ── poster ─────────────────────────────────────────────────────────────
    def _show_placeholder_poster(self):
        img = Image.new("RGB", (120, 180), color="#cccccc")
        photo = ImageTk.PhotoImage(img)
        self.poster_label.config(image=photo)
        self.poster_label.image = photo  # type: ignore[attr-defined]

    def _load_poster(self, poster_path: str):
        try:
            r = requests.get(f"{TMDB_IMAGE_BASE}{poster_path}", timeout=12)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).resize((120, 180), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.root.after(0, self._set_poster, photo)
        except Exception:
            pass

    def _set_poster(self, photo: ImageTk.PhotoImage):
        self.poster_label.config(image=photo)
        self.poster_label.image = photo  # type: ignore[attr-defined]

    # ── helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _set_text(widget: tk.Text, content: str):
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.config(state=tk.DISABLED)


if __name__ == "__main__":
    # Windows: enable high-DPI so UI isn't blurry on 4K screens
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    TVAggregator(root)
    root.mainloop()
