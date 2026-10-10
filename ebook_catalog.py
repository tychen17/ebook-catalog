# -*- coding: utf-8 -*-
"""Scan folders for ebooks and export a catalog table. Read-only, never touches source files."""

import os
import re
import sys
import csv
import ctypes
import threading
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "电子书目录整理工具"
DEFAULT_EXTS = "txt pdf epub mobi azw3 azw djvu fb2 chm doc docx rtf html htm md mht cbz cbr"
DEFAULT_MIN_CHAPTERS = 3

CHAPTER_PATTERNS = [
    re.compile(r'^\d+$'),                             # 1.txt
    re.compile(r'^\d+[\s\-_.]'),                      # 01-intro.txt
    re.compile(r'^第[0-9一二三四五六七八九十百千万零两]+[章节回卷部集讲课篇]'),  # 第一章
    re.compile(r'^[卷部集][一二三四五六七八九十百千万]'),  # 卷一
]


def chapter_ratio(files):
    if not files:
        return 0.0
    return sum(1 for f in files if any(p.match(f) for p in CHAPTER_PATTERNS)) / len(files)


def _rel(root, dirpath, fn=None):
    rel = os.path.relpath(dirpath, root)
    if rel == ".":
        return fn if fn is not None else os.path.basename(os.path.normpath(root)) or root
    return os.path.join(rel, fn) if fn is not None else rel


def scan(root, exts, min_chapters, drive_name="", include_others=True, progress_cb=None, cancel=None):
    groups = {}
    others = {}
    dirs_seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if cancel and cancel():
            break
        dirs_seen += 1
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in exts:
                groups.setdefault((dirpath, ext), []).append(fn)
            elif include_others:
                others.setdefault((dirpath, ext), []).append(fn)
        if progress_cb:
            progress_cb(dirs_seen)

    ebooks = []
    for (dirpath, ext), files in groups.items():
        files.sort()
        if len(files) >= min_chapters and chapter_ratio(files) >= 0.6:
            name = os.path.basename(os.path.normpath(dirpath)) or dirpath
            ebooks.append((drive_name, name, ext, _rel(root, dirpath), "分%d个章节合并" % len(files)))
        else:
            for fn in files:
                ebooks.append((drive_name, os.path.splitext(fn)[0], ext, _rel(root, dirpath, fn), ""))
    ebooks.sort(key=lambda r: (r[1].lower(), r[2]))

    olist = []
    for (dirpath, ext), files in others.items():
        for fn in sorted(files):
            olist.append((drive_name, os.path.splitext(fn)[0], ext, _rel(root, dirpath, fn), "非电子书格式"))
    olist.sort(key=lambda r: (r[3].lower(), r[1].lower()))
    return ebooks, olist


class App:
    def __init__(self, root):
        self.root = root
        self.cancel_flag = False
        self.results = []
        root.title(APP_TITLE)
        root.geometry("920x600")
        root.minsize(740, 500)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        f_top = ttk.LabelFrame(root, text="扫描设置")
        f_top.pack(fill="x", padx=8, pady=6)
        ttk.Label(f_top, text="移动硬盘名称(记录用):").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.entry_name = ttk.Entry(f_top, width=24)
        self.entry_name.grid(row=0, column=1, padx=4, sticky="w")
        ttk.Label(f_top, text="(自己给硬盘起的名字，如“工作盘”，会写入表格，便于日后识别)",
                  foreground="#888").grid(row=0, column=2, padx=4, sticky="w")
        ttk.Label(f_top, text="扫描目录:").grid(row=1, column=0, padx=4, pady=4, sticky="w")
        self.entry_path = ttk.Entry(f_top, width=56)
        self.entry_path.grid(row=1, column=1, columnspan=2, padx=4, sticky="we")
        ttk.Button(f_top, text="浏览文件夹…", command=self.browse).grid(row=1, column=3, padx=4)
        ttk.Label(f_top, text="注意：本工具只读扫描，不会修改、移动或删除你的任何书籍文件。",
                  foreground="#c0392b").grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 4))
        f_top.columnconfigure(2, weight=1)

        f_opt = ttk.LabelFrame(root, text="选项")
        f_opt.pack(fill="x", padx=8, pady=6)
        ttk.Label(f_opt, text="电子书格式(空格分隔):").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.ext_var = tk.StringVar(value=DEFAULT_EXTS)
        ttk.Entry(f_opt, textvariable=self.ext_var, width=40).grid(row=0, column=1, padx=4)
        ttk.Label(f_opt, text="分章节合并阈值:").grid(row=0, column=2, padx=4)
        self.min_var = tk.IntVar(value=DEFAULT_MIN_CHAPTERS)
        ttk.Spinbox(f_opt, from_=2, to=50, textvariable=self.min_var, width=5).grid(row=0, column=3, padx=4)
        self.opt_others = tk.BooleanVar(value=True)
        ttk.Checkbutton(f_opt, text="同时列出其他格式文件(非电子书)", variable=self.opt_others).grid(
            row=1, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 4))

        f_btn = ttk.Frame(root)
        f_btn.pack(fill="x", padx=8)
        self.btn_scan = ttk.Button(f_btn, text="开始扫描", command=self.start_scan)
        self.btn_scan.pack(side="left", padx=4)
        self.btn_cancel = ttk.Button(f_btn, text="取消", command=self.cancel_scan, state="disabled")
        self.btn_cancel.pack(side="left", padx=4)
        self.btn_export = ttk.Button(f_btn, text="导出表格(CSV)", command=self.export_csv, state="disabled")
        self.btn_export.pack(side="left", padx=4)
        self.lbl_stat = ttk.Label(f_btn, text="就绪")
        self.lbl_stat.pack(side="left", padx=12)

        cols = ("drive", "name", "fmt", "path", "note")
        self.tree = ttk.Treeview(root, columns=cols, show="headings")
        self.tree.heading("drive", text="硬盘名称")
        self.tree.heading("name", text="电子书名")
        self.tree.heading("fmt", text="格式")
        self.tree.heading("path", text="电子书位置(相对路径)")
        self.tree.heading("note", text="备注")
        self.tree.column("drive", width=90)
        self.tree.column("name", width=190)
        self.tree.column("fmt", width=60, anchor="center")
        self.tree.column("path", width=380)
        self.tree.column("note", width=105, anchor="center")
        sb = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)
        sb.place(in_=self.tree, relx=1.0, rely=0, relheight=1.0, anchor="ne")

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", padx=8, pady=(0, 6))
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def browse(self):
        d = filedialog.askdirectory(title="选择要扫描的文件夹（移动硬盘根目录或任意子目录）")
        if d:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, d)

    def cancel_scan(self):
        self.cancel_flag = True

    def start_scan(self):
        root = self.entry_path.get().strip().strip('"')
        if not root or not os.path.isdir(root):
            messagebox.showwarning(APP_TITLE, "请先选择有效的扫描目录（点击“浏览文件夹…”）")
            return
        exts = {("." + e.strip().lstrip(".").lower()) for e in self.ext_var.get().replace("，", " ").split() if e.strip()}
        if not exts:
            messagebox.showwarning(APP_TITLE, "请填写至少一种电子书格式")
            return
        self.cancel_flag = False
        self.results = []
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.btn_scan.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.btn_export.config(state="disabled")
        self.progress.start(12)
        self.lbl_stat.config(text="正在扫描（只读，不会写入硬盘）…")
        threading.Thread(target=self._work, args=(root, exts, self.min_var.get()), daemon=True).start()

    def _work(self, root, exts, min_ch):
        def cb(n):
            self.root.after(0, lambda: self.lbl_stat.config(text="已扫描 %d 个文件夹…" % n))
        try:
            ebooks, others = scan(root, exts, min_ch, drive_name=self.entry_name.get().strip(),
                                  include_others=self.opt_others.get(),
                                  progress_cb=cb, cancel=lambda: self.cancel_flag)
            self.root.after(0, lambda: self._done(ebooks, others))
        except Exception as e:
            self.root.after(0, lambda: self._fail(str(e)))

    def _done(self, ebooks, others):
        self.results = list(ebooks) + list(others)
        self.progress.stop()
        self.btn_scan.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.btn_export.config(state="normal")
        for row in ebooks:
            self.tree.insert("", "end", values=row)
        for row in others:
            self.tree.insert("", "end", values=row)
        merged = sum(1 for r in ebooks if r[4])
        self.lbl_stat.config(text="完成：电子书 %d 条（%d 本分章节合并），其他文件 %d 条" % (len(ebooks), merged, len(others)))

    def _fail(self, msg):
        self.progress.stop()
        self.btn_scan.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.lbl_stat.config(text="扫描失败")
        messagebox.showerror(APP_TITLE, msg)

    def export_csv(self):
        if not self.results:
            messagebox.showinfo(APP_TITLE, "暂无结果可导出")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 表格", "*.csv")],
                                            initialfile="电子书目录.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["硬盘名称", "电子书名", "电子书格式", "电子书位置(相对路径)", "备注"])
                w.writerows(self.results)
            messagebox.showinfo(APP_TITLE, "已导出 %d 条记录到：\n%s" % (len(self.results), path))
        except Exception as e:
            messagebox.showerror(APP_TITLE, "导出失败：%s" % e)

    def on_close(self):
        self.cancel_flag = True
        self.root.destroy()


def selftest():
    base = tempfile.mkdtemp(prefix="ebook_test_")

    def w(p, content="x"):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    w(os.path.join(base, "小说.txt"))
    w(os.path.join(base, "教材.pdf"))
    w(os.path.join(base, "技术", "book.epub"))
    w(os.path.join(base, "经典文学", "红楼梦", "红楼梦.txt"))
    for i in range(1, 6):
        w(os.path.join(base, "《明史》", "%d.txt" % i))
    for i in range(1, 4):
        w(os.path.join(base, "三国演义", "第%d回.txt" % i))
    for i in range(1, 4):
        w(os.path.join(base, "随想", "笔记%d.txt" % i))
    w(os.path.join(base, "照片", "封面.png"))
    w(os.path.join(base, "打包.zip"))

    ebooks, others = scan(base, {".txt", ".pdf", ".epub"}, 3, drive_name="工作盘")
    for r in ebooks:
        print(" | ".join(r))
    for r in others:
        print(" | ".join(r))
    assert len(ebooks) == 9, "2 merged + 7 single books"
    assert sum(1 for r in ebooks if r[4]) == 2, "two multi-chapter books should be merged"
    assert len(others) == 2, "png + zip should be listed as non-ebook"
    for r in ebooks + others:
        assert not re.match(r'^[A-Za-z]:', r[3]), "location must be relative, no drive letter"
    assert len(os.listdir(os.path.join(base, "《明史》"))) == 5, "source files must not be modified"
    print("SELFTEST PASS")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    try:
        r = tk.Tk()
        App(r)
        r.mainloop()
    except Exception as e:
        messagebox.showerror(APP_TITLE, "程序启动失败：%s" % e)


if __name__ == "__main__":
    main()
