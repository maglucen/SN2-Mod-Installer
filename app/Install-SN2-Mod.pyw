from __future__ import annotations

import json
import msvcrt
import os
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox


APP_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = APP_DIR / "Install-SN2-Mod.settings.json"
LOCK_PATH = APP_DIR / "Install-SN2-Mod.lock"
SN2_SOURCE_SUBPATH = Path(r"Subnautica2-Project\Paks\Windows\Subnautica2\Content\Paks")
SN2_LOGICMODS_SUBPATH = Path(r"steamapps\common\Subnautica2\Subnautica2\Content\Paks\LogicMods")


def _first_existing(candidates: list[Path], fallback: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return fallback


def _steam_library_roots() -> list[Path]:
    roots: list[Path] = []
    raw_roots = [
        os.environ.get("STEAM_DIR"),
        os.environ.get("STEAM_PATH"),
        r"C:\Program Files (x86)\Steam",
        r"C:\Program Files\Steam",
        r"C:\SteamLibrary",
        r"D:\SteamLibrary",
    ]

    for raw_root in raw_roots:
        if raw_root:
            root = Path(raw_root)
            if root not in roots:
                roots.append(root)

    for root in list(roots):
        library_file = root / "steamapps" / "libraryfolders.vdf"
        if not library_file.exists():
            continue

        try:
            text = library_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith('"path"'):
                continue
            parts = stripped.split('"')
            if len(parts) >= 4:
                library = Path(parts[3].replace("\\\\", "\\"))
                if library not in roots:
                    roots.append(library)

    return roots


def _resolve_default_source() -> Path:
    candidates = [
        APP_DIR / SN2_SOURCE_SUBPATH,
        APP_DIR.parent / SN2_SOURCE_SUBPATH,
        APP_DIR.parent.parent / SN2_SOURCE_SUBPATH,
        Path(r"A:\SN2_Devkit") / SN2_SOURCE_SUBPATH,
    ]
    return _first_existing(candidates, APP_DIR.parent.parent / SN2_SOURCE_SUBPATH)


def _resolve_default_target() -> Path:
    candidates = [root / SN2_LOGICMODS_SUBPATH for root in _steam_library_roots()]
    fallback = Path(r"C:\SteamLibrary") / SN2_LOGICMODS_SUBPATH
    return _first_existing(candidates, fallback)


SOURCE_DEFAULT = _resolve_default_source()
TARGET_DEFAULT = _resolve_default_target()


def acquire_single_instance_lock():
    handle = LOCK_PATH.open("a+b")
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None

    return handle

BG = "#06151D"
PANEL = "#0D2733"
PANEL_ALT = "#123847"
ENTRY_BG = "#0A202A"
TEXT = "#EAFBFF"
MUTED = "#7FB6C7"
ACCENT = "#45E5FF"
ACCENT_DEEP = "#0B8EB1"
WARM = "#FFB34D"
WARM_DEEP = "#C96A18"
SUCCESS = "#7FFFD4"
ERROR = "#FF8B7A"


class SN2InstallerApp:
    def __init__(self) -> None:
        self.settings = self._load_settings()
        self.root = tk.Tk()
        self.root.title("SN2 LogicMods Installer")
        self.root.minsize(900, 580)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Configure>", self._on_configure)

        self._save_after_id: str | None = None
        self._restoring_geometry = True
        self._last_normal_geometry = self._resolve_saved_normal_geometry()
        self._saved_window_state = self._resolve_saved_window_state()

        self.mod_name = tk.StringVar(value=self.settings.get("mod_name", "DemoMod"))
        self.chunk_id = tk.StringVar(value=self.settings.get("chunk_id", "14"))
        self.source_dir = tk.StringVar(value=self.settings.get("source_dir", str(SOURCE_DEFAULT)))
        self.target_dir = tk.StringVar(value=self.settings.get("target_dir", str(TARGET_DEFAULT)))
        self.launch_after_install = tk.BooleanVar(value=self.settings.get("launch_after_install", False))
        self.status = tk.StringVar(value="Ready. Package in Unreal, then install from here.")

        self._build_ui()
        self._bind_setting_watchers()
        self.root.after(0, self._apply_saved_geometry)

    def _build_ui(self) -> None:
        self._build_header()
        self._build_content()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG, height=120)
        header.pack(fill="x", padx=22, pady=(18, 8))
        header.pack_propagate(False)

        canvas = tk.Canvas(
            header,
            bg=BG,
            highlightthickness=0,
            bd=0,
            relief="flat",
            height=120,
        )
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Configure>", self._paint_header)
        self.header_canvas = canvas

    def _paint_header(self, event: tk.Event) -> None:
        c = self.header_canvas
        c.delete("all")
        width = max(event.width, 1)
        height = max(event.height, 1)

        steps = 28
        for i in range(steps):
            ratio = i / max(steps - 1, 1)
            color = self._blend("#0B1C26", "#0C5364", ratio)
            y0 = int(height * ratio)
            y1 = int(height * ((i + 1) / steps)) + 2
            c.create_rectangle(0, y0, width, y1, outline="", fill=color)

        c.create_rectangle(0, height - 8, width, height, outline="", fill=ACCENT)
        c.create_oval(width - 210, 18, width - 60, 108, outline="", fill="#114B5A")
        c.create_oval(width - 185, 30, width - 78, 96, outline="", fill="#16677B")
        c.create_oval(width - 155, 20, width - 120, 55, outline="", fill=WARM)

        c.create_text(
            28,
            34,
            anchor="w",
            text="SUBNAUTICA 2",
            fill=WARM,
            font=("Segoe UI Semibold", 24),
        )
        c.create_text(
            28,
            76,
            anchor="w",
            text="LogicMods Installer",
            fill=TEXT,
            font=("Segoe UI", 34, "bold"),
        )
        c.create_text(
            width - 28,
            height - 22,
            anchor="e",
            text="Copy, rename and deploy pak chunks into the game in one step.",
            fill=MUTED,
            font=("Segoe UI", 10),
        )

    def _build_content(self) -> None:
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=22, pady=(4, 22))

        left = tk.Frame(content, bg=PANEL, highlightbackground=ACCENT_DEEP, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right = tk.Frame(content, bg=PANEL_ALT, width=250, highlightbackground="#1A5B6E", highlightthickness=1)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._build_form(left)
        self._build_sidebar(right)

    def _build_form(self, parent: tk.Frame) -> None:
        title = tk.Label(
            parent,
            text="Deploy Packaged Mod",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 18),
        )
        title.pack(anchor="w", padx=24, pady=(22, 4))

        subtitle = tk.Label(
            parent,
            text="Use the same mod folder name you have under Content/Mods in Unreal.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10),
        )
        subtitle.pack(anchor="w", padx=24, pady=(0, 16))

        fields = tk.Frame(parent, bg=PANEL)
        fields.pack(fill="x", padx=24)

        self._labeled_entry(fields, "Mod Name", self.mod_name, 0)
        self._labeled_entry(fields, "Chunk Id", self.chunk_id, 1, width=150)
        self._path_row(fields, "Source Paks Folder", self.source_dir, 2)
        self._path_row(fields, "LogicMods Folder", self.target_dir, 3)
        self._toggle_row(fields, 4)

        button_row = tk.Frame(parent, bg=PANEL)
        button_row.pack(fill="x", padx=24, pady=(18, 12))

        self._button(button_row, "Install Mod", self.install_mod, ACCENT, "#031820", 0, primary=True)
        self._button(button_row, "Open Source", self.open_source, PANEL_ALT, TEXT, 1)
        self._button(button_row, "Open LogicMods", self.open_target, PANEL_ALT, TEXT, 2)
        self._button(button_row, "Close", self._on_close, "#17313B", TEXT, 3)

        status_panel = tk.Frame(parent, bg=ENTRY_BG, highlightbackground="#174756", highlightthickness=1)
        status_panel.pack(fill="x", padx=24, pady=(0, 10))

        status_label = tk.Label(
            status_panel,
            textvariable=self.status,
            bg=ENTRY_BG,
            fg=SUCCESS,
            justify="left",
            anchor="w",
            padx=14,
            pady=10,
            font=("Segoe UI", 10),
        )
        status_label.pack(fill="x")
        self.status_label = status_label

        log_title = tk.Label(
            parent,
            text="Activity",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 12),
        )
        log_title.pack(anchor="w", padx=24, pady=(4, 6))

        log_frame = tk.Frame(parent, bg=ENTRY_BG, highlightbackground="#174756", highlightthickness=1)
        log_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.log = tk.Text(
            log_frame,
            bg=ENTRY_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            wrap="word",
            padx=12,
            pady=12,
            font=("Consolas", 10),
            height=12,
        )
        self.log.pack(fill="both", expand=True)
        self.log.insert("end", "Waiting for input.\n")
        self.log.configure(state="disabled")

    def _build_sidebar(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=PANEL_ALT)
        box.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(
            box,
            text="Workflow",
            bg=PANEL_ALT,
            fg=TEXT,
            font=("Segoe UI Semibold", 16),
        ).pack(anchor="w")

        steps = [
            "1. Package Project in Unreal.",
            "2. Note the chunk id from PAL_<ModName>.",
            "3. Enter mod name and chunk id here.",
            "4. Click Install Mod.",
            "5. Launch the game and verify the change.",
        ]
        for step in steps:
            tk.Label(
                box,
                text=step,
                bg=PANEL_ALT,
                fg=MUTED,
                justify="left",
                wraplength=210,
                font=("Segoe UI", 10),
            ).pack(anchor="w", pady=(10, 0))

        tk.Frame(box, bg="#1A5B6E", height=1).pack(fill="x", pady=18)

        tips_title = tk.Label(
            box,
            text="Checks",
            bg=PANEL_ALT,
            fg=TEXT,
            font=("Segoe UI Semibold", 14),
        )
        tips_title.pack(anchor="w")

        tips = [
            "Chunk 0 is reserved. Use 1 to 300.",
            "Mod folder, file names and Unreal folder should match.",
            "The tool overwrites existing files for that mod.",
            "If a source chunk is missing, package again first.",
        ]
        for tip in tips:
            tk.Label(
                box,
                text="\u2022 " + tip,
                bg=PANEL_ALT,
                fg=MUTED,
                justify="left",
                wraplength=210,
                font=("Segoe UI", 10),
            ).pack(anchor="w", pady=(10, 0))

    def _labeled_entry(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        width: int = 340,
    ) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=row, column=0, sticky="ew", pady=8)
        parent.grid_columnconfigure(0, weight=1)

        tk.Label(frame, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        entry = tk.Entry(
            frame,
            textvariable=variable,
            bg=ENTRY_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#184A58",
            highlightcolor=ACCENT,
            font=("Segoe UI", 12),
            width=max(width // 10, 10),
        )
        entry.pack(fill="x", pady=(6, 0), ipady=9)

    def _path_row(self, parent: tk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=row, column=0, sticky="ew", pady=8)
        frame.grid_columnconfigure(0, weight=1)

        tk.Label(frame, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).grid(
            row=0, column=0, sticky="w", columnspan=2
        )

        entry = tk.Entry(
            frame,
            textvariable=variable,
            bg=ENTRY_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#184A58",
            highlightcolor=ACCENT,
            font=("Segoe UI", 11),
        )
        entry.grid(row=1, column=0, sticky="ew", pady=(6, 0), ipady=9)

        browse = tk.Button(
            frame,
            text="Browse",
            command=lambda v=variable: self.browse_folder(v),
            bg=WARM_DEEP,
            fg=TEXT,
            activebackground=WARM,
            activeforeground="#03212A",
            relief="flat",
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
        )
        browse.grid(row=1, column=1, padx=(10, 0), sticky="ew")

    def _toggle_row(self, parent: tk.Frame, row: int) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=row, column=0, sticky="ew", pady=(10, 2))
        parent.grid_columnconfigure(0, weight=1)

        toggle = tk.Checkbutton(
            frame,
            text="Launch Subnautica 2 after install",
            variable=self.launch_after_install,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor=ENTRY_BG,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 10),
        )
        toggle.pack(anchor="w")

        hint = tk.Label(
            frame,
            text="Uses the game .exe if found from the LogicMods path, otherwise falls back to Steam.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9),
        )
        hint.pack(anchor="w", pady=(4, 0))

    def _button(
        self,
        parent: tk.Frame,
        text: str,
        command,
        bg: str,
        fg: str,
        column: int,
        primary: bool = False,
    ) -> None:
        active_bg = self._blend(bg, "#FFFFFF", 0.12) if not primary else self._blend(bg, "#FFFFFF", 0.18)
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=20,
            pady=12,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
        )
        button.grid(row=0, column=column, padx=(0, 10), sticky="ew")
        parent.grid_columnconfigure(column, weight=1 if primary else 0)

    def browse_folder(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(initialdir=variable.get() or str(Path.home()))
        if selected:
            variable.set(selected)
            self._set_status("Folder updated.", SUCCESS)

    def open_source(self) -> None:
        self._open_folder(Path(self.source_dir.get()))

    def open_target(self) -> None:
        target = Path(self.target_dir.get())
        target.mkdir(parents=True, exist_ok=True)
        self._open_folder(target)

    def install_mod(self) -> None:
        mod_name = self.mod_name.get().strip()
        chunk_id = self.chunk_id.get().strip()
        source_dir = Path(self.source_dir.get().strip())
        target_root = Path(self.target_dir.get().strip())

        if not mod_name:
            self._show_error("Mod name is required.")
            return

        if any(char in mod_name for char in '\\/:*?"<>|'):
            self._show_error("Mod name contains invalid filename characters.")
            return

        if not chunk_id.isdigit():
            self._show_error("Chunk id must be a whole number.")
            return

        if chunk_id == "0":
            self._show_error("Chunk id 0 is reserved. Use a value between 1 and 300.")
            return

        if not source_dir.exists():
            self._show_error(f"Source pak folder not found:\n{source_dir}")
            return

        target_root.mkdir(parents=True, exist_ok=True)
        destination_dir = target_root / mod_name
        destination_dir.mkdir(parents=True, exist_ok=True)

        extensions = ("pak", "ucas", "utoc")
        copied_files: list[Path] = []

        try:
            for extension in extensions:
                source_file = source_dir / f"pakchunk{chunk_id}-Windows.{extension}"
                if not source_file.exists():
                    self._show_error(f"Missing source file:\n{source_file}")
                    return

                destination_file = destination_dir / f"{mod_name}.{extension}"
                shutil.copy2(source_file, destination_file)
                copied_files.append(destination_file)
                self._log(f"Copied {source_file.name} -> {destination_file}")
        except Exception as exc:  # pragma: no cover - defensive UI path
            self._show_error(f"Copy failed:\n{exc}")
            return

        self._set_status(f"Installed {mod_name} from chunk {chunk_id}.", SUCCESS)
        self._log("")
        self._log("Install complete:")
        for path in copied_files:
            self._log(f"  {path}")
        self._log("")
        if self.launch_after_install.get():
            self._launch_game(target_root)
        self._save_settings()

    def _launch_game(self, target_root: Path) -> None:
        game_exe = self._resolve_game_exe(target_root)

        try:
            if game_exe and game_exe.exists():
                subprocess.Popen([str(game_exe)])
                self._log(f"Launched game executable: {game_exe}")
                self._set_status("Mod installed and game launched.", SUCCESS)
                return

            os.startfile("steam://rungameid/1962700")
            self._log("Launched game through Steam.")
            self._set_status("Mod installed and game launched through Steam.", SUCCESS)
        except Exception as exc:  # pragma: no cover - defensive UI path
            self._show_error(f"Mod installed, but launching the game failed:\n{exc}")

    def _resolve_game_exe(self, target_root: Path) -> Path | None:
        try:
            game_root = target_root.parents[3]
        except IndexError:
            return None
        return game_root / "Binaries" / "Win64" / "Subnautica2.exe"

    def _open_folder(self, path: Path) -> None:
        if not path.exists():
            self._show_error(f"Folder not found:\n{path}")
            return
        subprocess.Popen(["explorer.exe", str(path)])

    def _load_settings(self) -> dict:
        if not SETTINGS_PATH.exists():
            return {}

        try:
            with SETTINGS_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_settings(self) -> None:
        window_state = self._get_window_state()
        normal_geometry = self._last_normal_geometry
        if window_state == "normal":
            normal_geometry = self.root.geometry()
            self._last_normal_geometry = normal_geometry

        settings = {
            "normal_geometry": normal_geometry,
            "window_state": window_state,
            "mod_name": self.mod_name.get(),
            "chunk_id": self.chunk_id.get(),
            "source_dir": self.source_dir.get(),
            "target_dir": self.target_dir.get(),
            "launch_after_install": self.launch_after_install.get(),
        }

        try:
            with SETTINGS_PATH.open("w", encoding="utf-8") as handle:
                json.dump(settings, handle, indent=2)
        except Exception as exc:  # pragma: no cover - defensive UI path
            self._log(f"WARNING: Could not save settings: {exc}")

    def _bind_setting_watchers(self) -> None:
        variables = (
            self.mod_name,
            self.chunk_id,
            self.source_dir,
            self.target_dir,
            self.launch_after_install,
        )
        for variable in variables:
            variable.trace_add("write", self._on_setting_changed)

    def _apply_saved_geometry(self) -> None:
        self._restoring_geometry = True
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None

        try:
            self.root.update_idletasks()
            if self._last_normal_geometry:
                self.root.geometry(self._last_normal_geometry)
            self.root.update_idletasks()

            if self._saved_window_state == "zoomed":
                self.root.after(100, self._maximize_window)
        finally:
            self.root.after(500, self._finish_geometry_restore)

    def _finish_geometry_restore(self) -> None:
        self._restoring_geometry = False

    def _get_window_state(self) -> str:
        try:
            return str(self.root.state())
        except Exception:
            return "normal"

    def _maximize_window(self) -> None:
        try:
            self.root.state("zoomed")
        except Exception:
            pass

    def _resolve_saved_normal_geometry(self) -> str | None:
        normal_geometry = self.settings.get("normal_geometry")
        if isinstance(normal_geometry, str) and normal_geometry.strip():
            return normal_geometry

        legacy_geometry = self.settings.get("geometry")
        if isinstance(legacy_geometry, str) and legacy_geometry.strip():
            return legacy_geometry

        return None

    def _resolve_saved_window_state(self) -> str:
        window_state = self.settings.get("window_state")
        if window_state in {"normal", "zoomed"}:
            return str(window_state)

        window_rect = self.settings.get("window_rect")
        if isinstance(window_rect, dict):
            try:
                if int(window_rect.get("width", 0)) >= 1800 and int(window_rect.get("height", 0)) >= 900:
                    return "zoomed"
            except Exception:
                pass

        return "normal"

    def _on_setting_changed(self, *_args) -> None:
        self._schedule_save()

    def _on_configure(self, _event: tk.Event) -> None:
        if self._restoring_geometry:
            return
        if self._get_window_state() == "normal":
            self._last_normal_geometry = self.root.geometry()
        self._schedule_save()

    def _schedule_save(self) -> None:
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(250, self._flush_scheduled_save)

    def _flush_scheduled_save(self) -> None:
        self._save_after_id = None
        self._save_settings()

    def _on_close(self) -> None:
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        self._save_settings()
        self.root.destroy()

    def _set_status(self, message: str, color: str) -> None:
        self.status.set(message)
        self.status_label.configure(fg=color)

    def _show_error(self, message: str) -> None:
        self._set_status(message, ERROR)
        self._log(f"ERROR: {message}")
        messagebox.showerror("SN2 LogicMods Installer", message)

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    @staticmethod
    def _blend(color_a: str, color_b: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        a = tuple(int(color_a[i : i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(color_b[i : i + 2], 16) for i in (1, 3, 5))
        mixed = tuple(round((1 - ratio) * av + ratio * bv) for av, bv in zip(a, b))
        return "#" + "".join(f"{value:02X}" for value in mixed)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    instance_lock = acquire_single_instance_lock()
    if instance_lock is not None:
        SN2InstallerApp().run()
