"""
StoryWeaver 手动注册辅助（GUI 版）
流程：打开 StoryWeaver -> 显示当前邮箱 -> [打开收件箱] 跳转对应 url -> [下一条] 标记已注册并写回 jsonl，循环
重启脚本自动跳过 status 为「已注册」的记录，断点续跑
"""
import json
import threading
from pathlib import Path
from tkinter import Button, Frame, Label, StringVar, Tk

from DrissionPage import ChromiumPage

BASE_DIR = Path(__file__).resolve().parent.parent
JSONL_PATH = BASE_DIR / "01Reverse crawler" / "outlook.jsonl"
SITE_URL = "https://storyweaver.org.in/en"
PASSWORD = "12345678"


def load_records():
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_records(records):
    tmp = JSONL_PATH.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(JSONL_PATH)


class App:
    def __init__(self, root):
        self.root = root
        root.title("StoryWeaver 注册辅助")
        root.resizable(False, False)

        self.records = load_records()
        self.index = 0
        while self.index < len(self.records) and self.records[self.index]["status"] == "已注册":
            self.index += 1
        self.stage = "site"  # site: 注册页 / inbox: 收件箱
        self.page = None
        self.inbox_tab = None
        self.busy = True

        self.progress = StringVar()
        self.email = StringVar()
        self.status = StringVar()
        self.url = StringVar()
        self.hint = StringVar(value="正在启动浏览器...")

        frame = Frame(root, padx=16, pady=12)
        frame.grid()
        rows = [
            ("进度", self.progress),
            ("邮箱", self.email),
            ("密码", StringVar(value=PASSWORD)),
            ("状态", self.status),
            ("收件箱", self.url),
        ]
        for r, (label, var) in enumerate(rows):
            Label(frame, text=label, width=6, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
            Label(frame, textvariable=var, font=("Menlo", 12), anchor="w").grid(row=r, column=1, sticky="w", pady=2)

        self.copy_btn = Button(frame, text="复制", width=4, command=self.copy_email)
        self.copy_btn.grid(row=1, column=2, padx=(4, 0))

        btn_frame = Frame(frame)
        btn_frame.grid(row=len(rows), column=0, columnspan=2, pady=(12, 4))
        self.inbox_btn = Button(btn_frame, text="打开收件箱", width=12, command=self.on_open_inbox, state="disabled")
        self.inbox_btn.grid(row=0, column=0, padx=4)
        self.next_btn = Button(btn_frame, text="下一条", width=12, command=self.on_next, state="disabled")
        self.next_btn.grid(row=0, column=1, padx=4)
        Label(frame, textvariable=self.hint, fg="#666").grid(row=len(rows) + 1, column=0, columnspan=2)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        if self.index < len(self.records):
            self.busy = True
            self.run_async(self.open_site, self._after_startup)
        else:
            self.busy = False

    # ---------- 浏览器操作（在子线程执行） ----------

    def ensure_page(self):
        if self.page is None:
            self.page = ChromiumPage()
        return self.page

    def open_site(self):
        self.ensure_page().get(SITE_URL)

    def open_inbox(self):
        self.inbox_tab = self.ensure_page().new_tab(self.records[self.index]["url"])

    def next_record(self):
        if self.inbox_tab is not None:
            self.inbox_tab.close()
            self.inbox_tab = None
        self.records[self.index]["status"] = "已注册"
        save_records(self.records)
        self.index += 1
        while self.index < len(self.records) and self.records[self.index]["status"] == "已注册":
            self.index += 1
        self.stage = "site"
        if self.index < len(self.records):
            self.ensure_page().get(SITE_URL)

    # ---------- UI ----------

    def copy_email(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.email.get())
        self.copy_btn.config(text="已复制")
        self.copy_btn.after(1500, lambda: self.copy_btn.config(text="复制"))

    def on_open_inbox(self):
        if self.busy:
            return
        self.busy = True
        self.inbox_btn.config(state="disabled")
        self.hint.set("正在打开收件箱...")
        self.run_async(self.open_inbox, self._after_open_inbox)

    def on_next(self):
        if self.busy:
            return
        self.busy = True
        self.next_btn.config(state="disabled")
        self.hint.set("正在切换下一条...")
        self.run_async(self.next_record, self._after_next)

    def run_async(self, fn, on_done):
        def worker():
            try:
                fn()
                error = None
            except Exception as e:
                error = str(e)
            self.root.after(0, lambda: on_done(error))

        threading.Thread(target=worker, daemon=True).start()

    def _after_startup(self, error):
        self.busy = False
        self.refresh(error)

    def _after_open_inbox(self, error):
        self.busy = False
        if error:
            self.hint.set(f"出错: {error}")
            self.inbox_btn.config(state="normal")
            return
        self.stage = "inbox"
        self.refresh()

    def _after_next(self, error):
        self.busy = False
        if error:
            self.hint.set(f"出错: {error}")
            self.next_btn.config(state="normal")
            return
        self.refresh()

    def refresh(self, error=None):
        done = self.index >= len(self.records)
        if done:
            self.hint.set("全部完成")
        else:
            rec = self.records[self.index]
            self.progress.set(f"{self.index + 1} / {len(self.records)}")
            self.email.set(rec["email"])
            self.status.set(rec["status"])
            self.url.set(rec["url"])

        self.inbox_btn.config(state="disabled" if done or error else "normal")
        self.next_btn.config(state="disabled" if done or error else "normal")

        if error:
            self.hint.set(f"出错: {error}")
        elif not done:
            if self.stage == "site":
                self.hint.set("填写邮箱密码注册，完成后点【打开收件箱】")
            else:
                self.hint.set("查完邮件点【下一条】进入下一封邮箱")

    def on_close(self):
        if self.page is not None:
            try:
                self.page.quit()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = Tk()
    App(root)
    root.mainloop()
