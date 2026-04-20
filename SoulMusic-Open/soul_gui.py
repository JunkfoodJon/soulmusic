"""
╔═══════════════════════════════════════════════════════════════╗
║  S O U L M U S I C   —   T E S T   C O N T R O L   G U I   ║
║  Pip-Boy-style dashboard for acoustic pipeline validation    ║
║  Run:  python soul_gui.py                                    ║
╚═══════════════════════════════════════════════════════════════╝

Visual control surface covering:
  • All 10 test_harness.py synthetic tests        (no hardware needed)
  • bench_test.py hardware tests                  (with gyro + transducer)
  • MEMS profile browser                          (resonance reference)
  • SubharmonicLadder zone visualiser             (engagement ladder)
  • Beamforming array calculator                  (geometry + gain)
  • Platform database viewer                      (detection reference)
  • Shell preset viewer                           (probe.py reference)
  • Real-time result trophy wall                  (data placeholders)

Requires: PySide6, numpy
"""

import sys
import os
import time
import traceback
import threading
from pathlib import Path
from dataclasses import dataclass, field
from io import StringIO

import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame, QTabWidget, QTabBar,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QProgressBar, QTextEdit, QSplitter, QGridLayout,
    QGroupBox, QSizePolicy, QCheckBox, QLineEdit,
    QGraphicsOpacityEffect, QStackedWidget,
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QObject, QThread, QPropertyAnimation,
    QEasingCurve, QSize,
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QLinearGradient,
    QIcon, QPixmap, QPalette,
)

# ── SoulMusic imports ──
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from acoustic.resonance import (
    MEMS_PROFILES, SubharmonicLadder, SPEED_OF_SOUND,
    SweepConfig, BurstConfig, generate_chirp, generate_burst_train,
    get_broad_sweep, get_targeted_sweep, get_broad_burst,
    get_targeted_burst, get_shock_burst, doppler_precompensate,
)
from acoustic.beam import (
    ArrayGeometry, BeamFormer, BeamController, SteeringVector,
    estimate_beamwidth, estimate_gain_db, estimate_focal_gain_db,
)
from acoustic.probe import SHELL_PRESETS, ShellProfile
from detection.acoustic_detect import PLATFORM_DB


# ═══════════════════════════════════════════════════════════════
#  COLOUR PALETTE  —  matches SoulMusic-index.html design language
# ═══════════════════════════════════════════════════════════════

class C:
    # Core surfaces (exact website CSS custom properties)
    BG           = "#0e0e10"   # --bg
    BG_MID       = "#18181b"   # --panel
    CARD_BG      = "#16161a"   # --button-bg
    CARD_BORDER  = "#23232a"   # --edge
    # Text
    TEXT         = "#efeff1"   # --fg
    TEXT_DIM     = "#b9b9c2"   # --muted
    # Accent / interactive highlight (silver-white spectrum)
    PRIMARY      = "#e8e8ed"   # --accent
    PRIMARY_DIM  = "#b9b9c2"   # --accent-2 / --muted
    SECONDARY    = "#b9b9c2"   # muted — group-box titles
    ACCENT       = "#5fb3ff"   # --tag-blue (run-all / info)
    # Semantic status colours (website tag palette)
    GREEN        = "#4ade80"   # .tag-green  — test pass
    RED          = "#f87171"   # .tag-red    — test fail / error
    YELLOW       = "#facc15"   # .tag-yellow — running / warning
    BLUE         = "#5fb3ff"   # .tag-blue   — info / beamforming
    # Scrollbar
    SCROLLBAR    = "#23232a"
    SCROLLBAR_H  = "#404055"


# ═══════════════════════════════════════════════════════════════
#  GLOBAL STYLESHEET
# ═══════════════════════════════════════════════════════════════

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C.BG};
    color: {C.TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}}
QTabWidget::pane {{
    border: 1px solid {C.CARD_BORDER};
    background: {C.BG};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {C.CARD_BG};
    color: {C.TEXT_DIM};
    border: 1px solid {C.CARD_BORDER};
    padding: 8px 20px;
    margin-right: 2px;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-weight: 600;
    font-size: 9pt;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {C.BG};
    color: {C.PRIMARY};
    border-bottom: 2px solid {C.PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    color: {C.PRIMARY};
    background: rgba(232, 232, 237, 0.04);
}}
QGroupBox {{
    border: 1px solid {C.CARD_BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 9pt;
    font-weight: 600;
    color: {C.TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QPushButton {{
    background-color: {C.CARD_BG};
    color: {C.PRIMARY};
    border: 1px solid {C.CARD_BORDER};
    border-radius: 6px;
    padding: 7px 20px;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-weight: 600;
    font-size: 9pt;
}}
QPushButton:hover {{
    background-color: rgba(232, 232, 237, 0.07);
    border-color: {C.PRIMARY};
}}
QPushButton:pressed {{
    background-color: rgba(232, 232, 237, 0.14);
}}
QPushButton:disabled {{
    color: {C.CARD_BORDER};
    border-color: {C.CARD_BORDER};
}}
QPushButton[runAll="true"] {{
    background-color: rgba(95, 179, 255, 0.08);
    color: {C.ACCENT};
    border-color: {C.ACCENT};
}}
QPushButton[runAll="true"]:hover {{
    background-color: rgba(95, 179, 255, 0.18);
}}
QComboBox {{
    background-color: {C.CARD_BG};
    color: {C.TEXT};
    border: 1px solid {C.CARD_BORDER};
    border-radius: 6px;
    padding: 4px 10px;
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {C.CARD_BG};
    color: {C.TEXT};
    border: 1px solid {C.CARD_BORDER};
    selection-background-color: rgba(232, 232, 237, 0.12);
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {C.CARD_BG};
    color: {C.TEXT};
    border: 1px solid {C.CARD_BORDER};
    border-radius: 6px;
    padding: 3px 8px;
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QTextEdit {{
    background-color: {C.CARD_BG};
    color: {C.TEXT};
    border: 1px solid {C.CARD_BORDER};
    border-radius: 6px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 9pt;
    selection-background-color: rgba(232, 232, 237, 0.18);
}}
QScrollBar:vertical {{
    background: {C.BG};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {C.SCROLLBAR};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C.SCROLLBAR_H};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {C.BG};
    height: 8px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {C.SCROLLBAR};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {C.SCROLLBAR_H};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QProgressBar {{
    background: {C.CARD_BG};
    border: 1px solid {C.CARD_BORDER};
    border-radius: 4px;
    text-align: center;
    color: {C.TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 8pt;
    height: 18px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C.PRIMARY_DIM}, stop:1 {C.PRIMARY});
    border-radius: 3px;
}}
QLabel {{
    color: {C.TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QCheckBox {{
    color: {C.TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {C.CARD_BORDER};
    border-radius: 3px;
    background: {C.CARD_BG};
}}
QCheckBox::indicator:checked {{
    background: {C.PRIMARY};
    border-color: {C.PRIMARY};
}}
QSplitter::handle {{
    background: {C.CARD_BORDER};
}}
"""


# ═══════════════════════════════════════════════════════════════
#  TROPHY CARD — placeholder that fills with data
# ═══════════════════════════════════════════════════════════════

class TrophyCard(QFrame):
    """A data-slot that starts empty (dimmed placeholder) and fills
    green/amber when a value is provided — like a trophy stand."""

    def __init__(self, label: str, unit: str = "", parent=None):
        super().__init__(parent)
        self._label_text = label
        self._unit = unit
        self._filled = False

        self.setFixedHeight(72)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.CARD_BG};
                border: 1px solid {C.CARD_BORDER};
                border-radius: 6px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)

        self.title_lbl = QLabel(label)
        self.title_lbl.setFont(QFont("Segoe UI", 8))
        self.title_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        self.title_lbl.setAlignment(Qt.AlignLeft)

        self.value_lbl = QLabel("—")
        self.value_lbl.setFont(QFont("Consolas", 18, QFont.Bold))
        self.value_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        self.value_lbl.setAlignment(Qt.AlignCenter)

        lay.addWidget(self.title_lbl)
        lay.addWidget(self.value_lbl)

    def set_value(self, value: str, color: str = C.PRIMARY):
        self._filled = True
        display = f"{value} {self._unit}".strip()
        self.value_lbl.setText(display)
        self.value_lbl.setStyleSheet(f"color: {color}; font-family: Consolas, 'Courier New', monospace;")
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.CARD_BG};
                border: 1px solid {color};
                border-radius: 6px;
            }}
        """)

    def clear_value(self):
        self._filled = False
        self.value_lbl.setText("—")
        self.value_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; font-family: Consolas, 'Courier New', monospace;")
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.CARD_BG};
                border: 1px solid {C.CARD_BORDER};
                border-radius: 6px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
#  TEST RUNNER WORKER (background thread via QThread)
# ═══════════════════════════════════════════════════════════════

class TestWorker(QObject):
    """Runs test functions in a background thread, emitting signals."""
    test_started  = Signal(str)           # test name
    test_finished = Signal(str, bool, str) # name, passed_all, output
    all_done      = Signal(int, int)       # passed, failed
    progress      = Signal(int)            # percent 0-100

    def __init__(self):
        super().__init__()
        self._tests_to_run: list[tuple[str, callable]] = []
        self._stop = False

    def set_tests(self, tests: list[tuple[str, callable]]):
        self._tests_to_run = tests
        self._stop = False

    def run(self):
        total_pass = 0
        total_fail = 0
        n = len(self._tests_to_run)

        for i, (name, fn) in enumerate(self._tests_to_run):
            if self._stop:
                break
            self.test_started.emit(name)

            # Capture stdout
            capture = StringIO()
            old_out = sys.stdout
            sys.stdout = capture
            passed = True
            try:
                from test_harness import TestResults
                results = TestResults()
                fn(results)
                if results.failed > 0:
                    passed = False
                total_pass += results.passed
                total_fail += results.failed
            except Exception as exc:
                passed = False
                total_fail += 1
                traceback.print_exc(file=capture)
            finally:
                sys.stdout = old_out

            output = capture.getvalue()
            self.test_finished.emit(name, passed, output)
            self.progress.emit(int((i + 1) / n * 100))

        self.all_done.emit(total_pass, total_fail)

    def stop(self):
        self._stop = True


# ═══════════════════════════════════════════════════════════════
#  TAB 1: TEST SUITE DASHBOARD
# ═══════════════════════════════════════════════════════════════

class TestSuiteTab(QWidget):
    """Runs all 10 synthetic tests and displays pass/fail + output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._thread = None
        self._worker = None

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Header row ──
        hdr = QHBoxLayout()
        title = QLabel("TEST SUITE")
        title.setFont(QFont("Consolas", 13, QFont.Bold))
        title.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 2px;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.btn_run_all = QPushButton("▶  RUN ALL TESTS")
        self.btn_run_all.setProperty("runAll", True)
        self.btn_run_all.setFixedHeight(34)
        self.btn_run_all.clicked.connect(self._run_all)
        hdr.addWidget(self.btn_run_all)

        self.btn_stop = QPushButton("■  STOP")
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setStyleSheet(
            f"QPushButton {{ color: {C.RED}; border-color: {C.RED}; }}"
            f"QPushButton:hover {{ background: rgba(255,65,65,0.1); }}")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_tests)
        hdr.addWidget(self.btn_stop)
        root.addLayout(hdr)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("  %p% — %v of 10 tests")
        self.progress.setMaximum(100)
        root.addWidget(self.progress)

        # ── Trophy row: summary stats ──
        trophy_row = QHBoxLayout()
        trophy_row.setSpacing(8)
        self.t_total    = TrophyCard("TOTAL ASSERTIONS")
        self.t_passed   = TrophyCard("PASSED", "✓")
        self.t_failed   = TrophyCard("FAILED", "✗")
        self.t_coverage = TrophyCard("COVERAGE")
        for t in (self.t_total, self.t_passed, self.t_failed, self.t_coverage):
            trophy_row.addWidget(t)
        root.addLayout(trophy_row)

        # ── Splitter: test list (left) + output (right) ──
        splitter = QSplitter(Qt.Horizontal)

        # Test list
        list_frame = QFrame()
        list_lay = QVBoxLayout(list_frame)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(4)

        list_label = QLabel("TESTS")
        list_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        list_label.setStyleSheet(f"color: {C.TEXT_DIM}; letter-spacing: 1px;")
        list_lay.addWidget(list_label)

        self.test_buttons: dict[str, QPushButton] = {}
        test_defs = self._get_test_defs()
        for name, _fn in test_defs:
            btn = QPushButton(f"  {name}")
            btn.setFixedHeight(28)
            btn.setStyleSheet(self._test_btn_style("idle"))
            btn.clicked.connect(lambda checked, n=name: self._run_single(n))
            list_lay.addWidget(btn)
            self.test_buttons[name] = btn

        list_lay.addStretch()
        list_scroll = QScrollArea()
        list_scroll.setWidget(list_frame)
        list_scroll.setWidgetResizable(True)
        list_scroll.setFixedWidth(340)
        splitter.addWidget(list_scroll)

        # Output console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))  # monospace kept for output
        splitter.addWidget(self.console)

        splitter.setSizes([340, 600])
        root.addWidget(splitter, 1)

    @staticmethod
    def _test_btn_style(state: str) -> str:
        if state == "running":
            return (f"QPushButton {{ text-align: left; color: {C.YELLOW}; "
                    f"border-color: {C.YELLOW}; background: rgba(250,204,21,0.06); }}")
        elif state == "pass":
            return (f"QPushButton {{ text-align: left; color: {C.GREEN}; "
                    f"border-color: {C.GREEN}; background: rgba(74,222,128,0.06); }}")
        elif state == "fail":
            return (f"QPushButton {{ text-align: left; color: {C.RED}; "
                    f"border-color: {C.RED}; background: rgba(248,113,113,0.06); }}")
        return (f"QPushButton {{ text-align: left; color: {C.TEXT_DIM}; "
                f"border-color: {C.CARD_BORDER}; }}")

    @staticmethod
    def _get_test_defs() -> list[tuple[str, callable]]:
        from test_harness import (
            test_propeller_detection, test_doppler_speed,
            test_platform_identification, test_beamforming,
            test_waveform_generation, test_probe_classification,
            test_full_pipeline, test_passive_detector_loop,
            test_subharmonic_ladder, test_doppler_precompensation,
        )
        return [
            ("1 — Propeller Detection",      test_propeller_detection),
            ("2 — Doppler Speed",             test_doppler_speed),
            ("3 — Platform Identification",   test_platform_identification),
            ("4 — Beamforming Array",         test_beamforming),
            ("5 — Waveform Generation",       test_waveform_generation),
            ("6 — Probe / Shell Classify",    test_probe_classification),
            ("7 — Full Pipeline (E2E)",       test_full_pipeline),
            ("8 — Passive Detector Loop",     test_passive_detector_loop),
            ("9 — Subharmonic Ladder",        test_subharmonic_ladder),
            ("10 — Doppler Pre-Compensation", test_doppler_precompensation),
        ]

    def _run_all(self):
        self._reset_ui()
        tests = self._get_test_defs()
        self._start_worker(tests)

    def _run_single(self, name: str):
        self._reset_ui()
        tests = [(n, fn) for n, fn in self._get_test_defs() if n == name]
        self._start_worker(tests)

    def _start_worker(self, tests):
        self.btn_run_all.setEnabled(False)
        self.btn_stop.setEnabled(True)
        for btn in self.test_buttons.values():
            btn.setEnabled(False)

        self._thread = QThread()
        self._worker = TestWorker()
        self._worker.set_tests(tests)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.test_started.connect(self._on_test_started)
        self._worker.test_finished.connect(self._on_test_finished)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.all_done.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _cleanup_thread(self):
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _reset_ui(self):
        self.console.clear()
        self.progress.setValue(0)
        for t in (self.t_total, self.t_passed, self.t_failed, self.t_coverage):
            t.clear_value()
        for btn in self.test_buttons.values():
            btn.setStyleSheet(self._test_btn_style("idle"))

    def _on_test_started(self, name: str):
        if name in self.test_buttons:
            self.test_buttons[name].setStyleSheet(self._test_btn_style("running"))
        self.console.append(f"\n{'─'*50}")
        self.console.append(f"▸ Running: {name}")
        self.console.append(f"{'─'*50}")

    def _on_test_finished(self, name: str, passed: bool, output: str):
        state = "pass" if passed else "fail"
        if name in self.test_buttons:
            self.test_buttons[name].setStyleSheet(self._test_btn_style(state))
        # Strip ANSI codes for the GUI console
        clean = output
        for code in ("\033[92m", "\033[91m", "\033[0m", "\033[1m",
                     "\033[1;95m", "\033[96m"):
            clean = clean.replace(code, "")
        self.console.append(clean)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_all_done(self, passed: int, failed: int):
        total = passed + failed
        self.t_total.set_value(str(total), C.BLUE)
        self.t_passed.set_value(str(passed), C.GREEN)
        if failed > 0:
            self.t_failed.set_value(str(failed), C.RED)
        else:
            self.t_failed.set_value("0", C.GREEN)
        pct = f"{passed/total*100:.0f}%" if total > 0 else "—"
        color = C.GREEN if failed == 0 else C.RED
        self.t_coverage.set_value(pct, color)

        self.btn_run_all.setEnabled(True)
        self.btn_stop.setEnabled(False)
        for btn in self.test_buttons.values():
            btn.setEnabled(True)

    def _stop_tests(self):
        if self._worker:
            self._worker.stop()


# ═══════════════════════════════════════════════════════════════
#  TAB 2: MEMS PROFILES + SUBHARMONIC LADDER
# ═══════════════════════════════════════════════════════════════

class ResonanceTab(QWidget):
    """MEMS profile browser + SubharmonicLadder zone visualiser."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("MEMS RESONANCE & ENGAGEMENT LADDER")
        title.setFont(QFont("Consolas", 13, QFont.Bold))
        title.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 2px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)

        # ── Left: MEMS Profiles table ──
        left = QFrame()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        profiles_group = QGroupBox("MEMS PROFILES  (11 sensors)")
        pg_lay = QVBoxLayout(profiles_group)

        # Column headers
        hdr_row = QHBoxLayout()
        for text, w in [("SENSOR", 140), ("MFR", 120), ("RESONANCE", 90)]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
            lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
            lbl.setFixedWidth(w)
            hdr_row.addWidget(lbl)
        hdr_row.addStretch()
        pg_lay.addLayout(hdr_row)

        # Sensor rows
        scroll_profiles = QScrollArea()
        scroll_profiles.setWidgetResizable(True)
        profile_list = QWidget()
        pl_lay = QVBoxLayout(profile_list)
        pl_lay.setSpacing(2)

        sorted_sensors = sorted(MEMS_PROFILES.items(),
                                key=lambda x: x[1]["resonance_hz"], reverse=True)
        for name, prof in sorted_sensors:
            row = QHBoxLayout()
            row.setSpacing(0)
            n_lbl = QLabel(name)
            n_lbl.setFixedWidth(140)
            n_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
            n_lbl.setStyleSheet(f"color: {C.PRIMARY};")

            mfr = prof.get("manufacturer", "?")
            mfr_color = {
                "InvenSense": C.RED, "TDK": C.RED,
                "Bosch": C.YELLOW, "STMicro": C.BLUE
            }.get(mfr, C.TEXT_DIM)
            m_lbl = QLabel(mfr)
            m_lbl.setFixedWidth(120)
            m_lbl.setStyleSheet(f"color: {mfr_color};")

            freq = prof["resonance_hz"]
            f_lbl = QLabel(f"{freq / 1000:.0f} kHz")
            f_lbl.setFixedWidth(90)
            f_lbl.setFont(QFont("Consolas", 10, QFont.Bold))
            f_lbl.setStyleSheet(f"color: {C.ACCENT};")

            row.addWidget(n_lbl)
            row.addWidget(m_lbl)
            row.addWidget(f_lbl)
            row.addStretch()
            pl_lay.addLayout(row)

        pl_lay.addStretch()
        scroll_profiles.setWidget(profile_list)
        pg_lay.addWidget(scroll_profiles)
        left_lay.addWidget(profiles_group)
        splitter.addWidget(left)

        # ── Right: SubharmonicLadder calculator ──
        right = QFrame()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)

        ladder_group = QGroupBox("SUBHARMONIC LADDER  (engagement zones)")
        lg_lay = QVBoxLayout(ladder_group)

        # Controls
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Target sensor:"))
        self.sensor_combo = QComboBox()
        self.sensor_combo.addItems(sorted(MEMS_PROFILES.keys()))
        self.sensor_combo.setCurrentText("ICM-42688-P")
        ctrl_row.addWidget(self.sensor_combo)

        ctrl_row.addWidget(QLabel("Range (m):"))
        self.range_spin = QSpinBox()
        self.range_spin.setRange(1, 300)
        self.range_spin.setValue(100)
        ctrl_row.addWidget(self.range_spin)

        ctrl_row.addWidget(QLabel("Speed (m/s):"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(-100, 100)
        self.speed_spin.setValue(0.0)
        self.speed_spin.setSingleStep(5.0)
        ctrl_row.addWidget(self.speed_spin)

        btn_calc = QPushButton("CALCULATE")
        btn_calc.clicked.connect(self._calculate_ladder)
        ctrl_row.addWidget(btn_calc)
        ctrl_row.addStretch()
        lg_lay.addLayout(ctrl_row)

        # Trophy cards for ladder result
        self.ladder_trophies = QHBoxLayout()
        self.ladder_trophies.setSpacing(8)
        self.lt_zone     = TrophyCard("ACTIVE ZONE")
        self.lt_base     = TrophyCard("BASE FREQ", "kHz")
        self.lt_tones    = TrophyCard("TONE COUNT")
        self.lt_mode     = TrophyCard("EMISSION MODE")
        self.lt_doppler  = TrophyCard("DOPPLER SHIFT", "Hz")
        for t in (self.lt_zone, self.lt_base, self.lt_tones,
                  self.lt_mode, self.lt_doppler):
            self.ladder_trophies.addWidget(t)
        lg_lay.addLayout(self.ladder_trophies)

        # Zone detail panel
        self.zone_detail = QTextEdit()
        self.zone_detail.setReadOnly(True)
        self.zone_detail.setFont(QFont("Consolas", 9))  # monospace kept for output
        self.zone_detail.setMaximumHeight(220)
        lg_lay.addWidget(self.zone_detail)

        # All zones reference
        self.all_zones_label = QLabel()
        self.all_zones_label.setWordWrap(True)
        self.all_zones_label.setFont(QFont("Consolas", 8))  # monospace for data table
        self.all_zones_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        lg_lay.addWidget(self.all_zones_label)

        right_lay.addWidget(ladder_group)
        splitter.addWidget(right)
        splitter.setSizes([380, 620])
        root.addWidget(splitter, 1)

        # Auto-calculate on load
        QTimer.singleShot(100, self._calculate_ladder)

    def _calculate_ladder(self):
        sensor = self.sensor_combo.currentText()
        freq = MEMS_PROFILES[sensor]["resonance_hz"]
        range_m = self.range_spin.value()
        speed = self.speed_spin.value()

        ladder = SubharmonicLadder(base_freq_hz=freq)
        zone = ladder.get_zone(float(range_m))
        status = ladder.get_status(float(range_m))

        self.lt_base.set_value(f"{freq / 1000:.0f}", C.PRIMARY)

        if zone is None:
            self.lt_zone.set_value("OUTSIDE", C.TEXT_DIM)
            self.lt_tones.clear_value()
            self.lt_mode.clear_value()
            self.lt_doppler.clear_value()
            self.zone_detail.setText("Target is outside all engagement zones (>200m).")
        else:
            zone_colors = {
                "priming": C.BLUE, "charging": C.YELLOW,
                "disruption": C.SECONDARY, "kill": C.RED,
            }
            zc = zone_colors.get(zone.name, C.PRIMARY)
            self.lt_zone.set_value(zone.name.upper(), zc)

            freqs = ladder.get_zone_frequencies(zone, speed)
            self.lt_tones.set_value(str(len(freqs)), zc)
            self.lt_mode.set_value(zone.mode.upper(), zc)

            # Doppler shift on base freq
            if abs(speed) > 0.01:
                f_emit = doppler_precompensate(freq, speed)
                shift = f_emit - freq
                self.lt_doppler.set_value(f"{shift:+.1f}", C.YELLOW)
            else:
                self.lt_doppler.set_value("0", C.TEXT_DIM)

            # Detailed frequency list
            lines = [f"Zone: {zone.name}  |  Range: {zone.range_min_m}–{zone.range_max_m} m"]
            lines.append(f"Mode: {zone.mode}  |  RepRate: {zone.rep_rate_hz} Hz  |  Pulse: {zone.pulse_ms} ms")
            lines.append(f"Divisors: {zone.divisors}")
            lines.append("")
            lines.append("Frequencies emitted:")
            for i, f in enumerate(freqs):
                div_label = f"f/{zone.divisors[i]}" if i < len(zone.divisors) and zone.divisors[i] > 1 else "f₀ (direct)"
                lines.append(f"  {div_label:>12}  →  {f:,.1f} Hz  ({f/1000:.2f} kHz)")
            self.zone_detail.setText("\n".join(lines))

        # All zones reference
        ref_lines = ["ALL ZONES:"]
        for z in ladder.zones:
            zf = ladder.get_zone_frequencies(z, 0.0)
            fstr = ", ".join(f"{f/1000:.1f}k" for f in zf)
            ref_lines.append(
                f"  {z.name:>12}  {z.range_min_m:>5.0f}–{z.range_max_m:<5.0f}m  "
                f"{z.mode:>10}  tones: {fstr}")
        self.all_zones_label.setText("\n".join(ref_lines))


# ═══════════════════════════════════════════════════════════════
#  TAB 3: BEAMFORMING CALCULATOR
# ═══════════════════════════════════════════════════════════════

class BeamformTab(QWidget):
    """Array geometry calculator + beam steering preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("BEAMFORMING ARRAY CALCULATOR")
        title.setFont(QFont("Consolas", 13, QFont.Bold))
        title.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 2px;")
        root.addWidget(title)

        # ── Controls ──
        ctrl_group = QGroupBox("ARRAY CONFIGURATION")
        cg_lay = QGridLayout(ctrl_group)

        cg_lay.addWidget(QLabel("Rows:"), 0, 0)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 32)
        self.rows_spin.setValue(16)
        cg_lay.addWidget(self.rows_spin, 0, 1)

        cg_lay.addWidget(QLabel("Cols:"), 0, 2)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 32)
        self.cols_spin.setValue(16)
        cg_lay.addWidget(self.cols_spin, 0, 3)

        cg_lay.addWidget(QLabel("Spacing (mm):"), 0, 4)
        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(1.0, 50.0)
        self.spacing_spin.setValue(6.9)
        self.spacing_spin.setSingleStep(0.5)
        self.spacing_spin.setDecimals(1)
        cg_lay.addWidget(self.spacing_spin, 0, 5)

        cg_lay.addWidget(QLabel("Frequency (kHz):"), 0, 6)
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(15.0, 45.0)
        self.freq_spin.setValue(25.0)
        self.freq_spin.setSingleStep(1.0)
        self.freq_spin.setDecimals(1)
        cg_lay.addWidget(self.freq_spin, 0, 7)

        cg_lay.addWidget(QLabel("Azimuth (°):"), 1, 0)
        self.az_spin = QDoubleSpinBox()
        self.az_spin.setRange(-90, 90)
        self.az_spin.setValue(0)
        cg_lay.addWidget(self.az_spin, 1, 1)

        cg_lay.addWidget(QLabel("Elevation (°):"), 1, 2)
        self.el_spin = QDoubleSpinBox()
        self.el_spin.setRange(-90, 90)
        self.el_spin.setValue(0)
        cg_lay.addWidget(self.el_spin, 1, 3)

        cg_lay.addWidget(QLabel("Focus (m):"), 1, 4)
        self.focus_spin = QDoubleSpinBox()
        self.focus_spin.setRange(0, 200)
        self.focus_spin.setValue(0)
        self.focus_spin.setSpecialValueText("Far-field")
        cg_lay.addWidget(self.focus_spin, 1, 5)

        btn_calc = QPushButton("CALCULATE")
        btn_calc.clicked.connect(self._calculate)
        cg_lay.addWidget(btn_calc, 1, 6, 1, 2)

        root.addWidget(ctrl_group)

        # ── Trophy cards ──
        trow = QHBoxLayout()
        trow.setSpacing(8)
        self.bt_elements  = TrophyCard("ELEMENTS")
        self.bt_beamwidth = TrophyCard("BEAMWIDTH", "°")
        self.bt_gain      = TrophyCard("ARRAY GAIN", "dB")
        self.bt_focal     = TrophyCard("FOCAL GAIN", "dB")
        self.bt_total     = TrophyCard("TOTAL GAIN", "dB")
        self.bt_delay_spread = TrophyCard("DELAY SPREAD", "µs")
        for t in (self.bt_elements, self.bt_beamwidth, self.bt_gain,
                  self.bt_focal, self.bt_total, self.bt_delay_spread):
            trow.addWidget(t)
        root.addLayout(trow)

        # ── Detail output ──
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setFont(QFont("Consolas", 9))  # monospace for data output
        root.addWidget(self.detail, 1)

        # ── Preset buttons ──
        presets = QHBoxLayout()
        presets_label = QLabel("PRESETS:")
        presets_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        presets_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        presets.addWidget(presets_label)
        for label, r, c, sp, f in [
            ("1×4 Bench", 1, 4, 15.0, 25.0),
            ("4×4 Mid", 4, 4, 6.9, 25.0),
            ("8×8 Large", 8, 8, 6.9, 25.0),
            ("16×16 Prod", 16, 16, 6.9, 25.0),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.clicked.connect(
                lambda checked, _r=r, _c=c, _sp=sp, _f=f:
                    self._apply_preset(_r, _c, _sp, _f))
            presets.addWidget(btn)
        presets.addStretch()
        root.addLayout(presets)

        QTimer.singleShot(100, self._calculate)

    def _apply_preset(self, rows, cols, spacing, freq):
        self.rows_spin.setValue(rows)
        self.cols_spin.setValue(cols)
        self.spacing_spin.setValue(spacing)
        self.freq_spin.setValue(freq)
        self._calculate()

    def _calculate(self):
        rows = self.rows_spin.value()
        cols = self.cols_spin.value()
        spacing = self.spacing_spin.value() / 1000.0
        freq_hz = self.freq_spin.value() * 1000.0
        az = self.az_spin.value()
        el = self.el_spin.value()
        focus = self.focus_spin.value()

        grid = ArrayGeometry.rectangular_grid(rows, cols, spacing_m=spacing)
        bf = BeamFormer(grid)

        n = grid.n_elements
        self.bt_elements.set_value(str(n), C.PRIMARY)

        bw = estimate_beamwidth(grid, freq_hz)
        self.bt_beamwidth.set_value(f"{bw:.1f}", C.BLUE)

        gain = estimate_gain_db(grid)
        self.bt_gain.set_value(f"{gain:.1f}", C.PRIMARY)

        if focus > 0:
            fg = estimate_focal_gain_db(grid, focus, freq_hz)
            self.bt_focal.set_value(f"{fg:.1f}", C.SECONDARY)
            total = gain + fg
        else:
            self.bt_focal.set_value("N/A", C.TEXT_DIM)
            total = gain
        self.bt_total.set_value(f"{total:.1f}", C.ACCENT)

        steer = SteeringVector(azimuth_deg=az, elevation_deg=el,
                               focal_distance_m=focus)
        delays = bf.compute_delays(steer, freq_hz)
        spread = (np.max(delays) - np.min(delays)) * 1e6  # µs
        self.bt_delay_spread.set_value(f"{spread:.1f}", C.YELLOW)

        # Build detail text
        wavelength = SPEED_OF_SOUND / freq_hz * 1000  # mm
        aperture = max(rows - 1, 1) * spacing * 1000   # mm
        lines = [
            f"Array: {rows}×{cols} = {n} elements",
            f"Spacing: {spacing*1000:.1f} mm  ({spacing/wavelength*1000:.2f}λ at {freq_hz/1000:.1f} kHz)",
            f"Aperture: {aperture:.1f} mm × {max(cols-1,1)*spacing*1000:.1f} mm",
            f"Wavelength: {wavelength:.2f} mm",
            f"",
            f"Steering: az={az:.1f}°  el={el:.1f}°" + (f"  focus={focus:.1f}m" if focus else "  (far-field)"),
            f"Beamwidth: {bw:.1f}°",
            f"Array gain: {gain:.1f} dB",
        ]
        if focus > 0:
            lines.append(f"Near-field focal gain: +{fg:.1f} dB")
        lines.extend([
            f"Total gain: {total:.1f} dB",
            f"Delay spread: {spread:.1f} µs",
            f"",
            "──── Performance Across Array Sizes ────",
        ])
        for label, r2, c2 in [("1×4", 1, 4), ("4×4", 4, 4),
                                ("8×8", 8, 8), ("16×16", 16, 16)]:
            g2 = ArrayGeometry.rectangular_grid(r2, c2, spacing_m=spacing)
            bw2 = estimate_beamwidth(g2, freq_hz)
            gn2 = estimate_gain_db(g2)
            lines.append(f"  {label:>6}  {r2*c2:>4} el  "
                         f"beamwidth={bw2:>6.1f}°  gain={gn2:>5.1f} dB")

        self.detail.setText("\n".join(lines))


# ═══════════════════════════════════════════════════════════════
#  TAB 4: PLATFORM DATABASE + SHELL PRESETS
# ═══════════════════════════════════════════════════════════════

class PlatformTab(QWidget):
    """Platform database browser + shell preset reference."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("PLATFORM DATABASE & SHELL PRESETS")
        title.setFont(QFont("Consolas", 13, QFont.Bold))
        title.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 2px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)

        # ── Left: Platform DB ──
        left = QFrame()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        plat_group = QGroupBox(f"PLATFORM DATABASE  ({len(PLATFORM_DB)} entries)")
        plg_lay = QVBoxLayout(plat_group)

        plat_scroll = QScrollArea()
        plat_scroll.setWidgetResizable(True)
        plat_list = QWidget()
        pl_lay = QVBoxLayout(plat_list)
        pl_lay.setSpacing(6)

        cat_colors = {
            "commercial": C.BLUE, "racing": C.YELLOW,
            "military": C.RED, "hobby": C.PRIMARY,
            "unknown": C.TEXT_DIM,
        }

        for pid, plat in PLATFORM_DB.items():
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {C.CARD_BG};
                    border: 1px solid {C.CARD_BORDER};
                    border-radius: 6px;
                    border-left: 3px solid {cat_colors.get(plat.category, C.TEXT_DIM)};
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(2)

            # Name + category
            name_row = QHBoxLayout()
            name_lbl = QLabel(pid.replace("_", " ").upper())
            name_lbl.setFont(QFont("Consolas", 10, QFont.Bold))
            name_lbl.setStyleSheet(f"color: {C.PRIMARY};")
            name_row.addWidget(name_lbl)

            cat_lbl = QLabel(plat.category.upper())
            cat_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
            cat_lbl.setStyleSheet(
                f"color: {cat_colors.get(plat.category, C.TEXT_DIM)}; "
                f"background: rgba(255,255,255,0.03); "
                f"padding: 2px 8px; border-radius: 3px;")
            name_row.addStretch()
            name_row.addWidget(cat_lbl)
            cl.addLayout(name_row)

            # Details
            details = (
                f"Motors: {plat.motor_count}  |  Blades: {plat.blade_count}  |  "
                f"BPF: {plat.bpf_range_hz[0]}–{plat.bpf_range_hz[1]} Hz  |  "
                f"MEMS: {plat.mems_sensor or '?'}  |  Shell: {plat.shell_class}")
            det_lbl = QLabel(details)
            det_lbl.setFont(QFont("Segoe UI", 8))
            det_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
            det_lbl.setWordWrap(True)
            cl.addWidget(det_lbl)

            if plat.description:
                desc_lbl = QLabel(plat.description)
                desc_lbl.setFont(QFont("Segoe UI", 8))
                desc_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
                desc_lbl.setWordWrap(True)
                cl.addWidget(desc_lbl)

            pl_lay.addWidget(card)

        pl_lay.addStretch()
        plat_scroll.setWidget(plat_list)
        plg_lay.addWidget(plat_scroll)
        left_lay.addWidget(plat_group)
        splitter.addWidget(left)

        # ── Right: Shell Presets ──
        right = QFrame()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)

        shell_group = QGroupBox(f"SHELL PRESETS  ({len(SHELL_PRESETS)} types)")
        sg_lay = QVBoxLayout(shell_group)

        shell_colors = {
            "none": C.PRIMARY, "foam": C.BLUE,
            "plastic": C.YELLOW, "composite": C.SECONDARY,
            "metal": C.RED, "unknown": C.TEXT_DIM,
        }

        for shell_name, preset in SHELL_PRESETS.items():
            sc = shell_colors.get(shell_name, C.TEXT_DIM)
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {C.CARD_BG};
                    border: 1px solid {C.CARD_BORDER};
                    border-radius: 6px;
                    border-left: 3px solid {sc};
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(2)

            name_lbl = QLabel(f"◆  {shell_name.upper()}")
            name_lbl.setFont(QFont("Consolas", 10, QFont.Bold))
            name_lbl.setStyleSheet(f"color: {sc};")
            cl.addWidget(name_lbl)

            mode = preset.get("mode", "?")
            power = preset.get("power", "?")
            pulse = preset.get("pulse_ms", "?")
            rep = preset.get("rep_rate_hz", "?")
            desc = preset.get("description", "")

            params = f"Mode: {mode}  |  Power: {power}  |  Pulse: {pulse} ms  |  RepRate: {rep} Hz"
            p_lbl = QLabel(params)
            p_lbl.setFont(QFont("Segoe UI", 8))
            p_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
            cl.addWidget(p_lbl)

            if desc:
                d_lbl = QLabel(desc)
                d_lbl.setFont(QFont("Segoe UI", 8))
                d_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
                d_lbl.setWordWrap(True)
                cl.addWidget(d_lbl)

            sg_lay.addWidget(card)

        sg_lay.addStretch()
        right_lay.addWidget(shell_group)

        right_scroll = QScrollArea()
        right_scroll.setWidget(right)
        right_scroll.setWidgetResizable(True)
        splitter.addWidget(right_scroll)

        splitter.setSizes([550, 450])
        root.addWidget(splitter, 1)


# ═══════════════════════════════════════════════════════════════
#  TAB 5: TROPHY WALL — Calculation Placeholders
# ═══════════════════════════════════════════════════════════════

class TrophyWallTab(QWidget):
    """The trophy stand — all major calculated values as empty
    placeholders that fill as tests/hardware runs provide data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._trophies: dict[str, TrophyCard] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("TROPHY WALL  —  Calculation Results")
        title.setFont(QFont("Consolas", 13, QFont.Bold))
        title.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 2px;")
        root.addWidget(title)

        subtitle = QLabel(
            "Empty pedestals waiting for data. Run tests or connect "
            "hardware to fill them in.")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet(f"color: {C.TEXT_DIM};")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(14)

        # ── Detection & Classification ──
        det_group = QGroupBox("DETECTION & CLASSIFICATION")
        dg = QGridLayout(det_group)
        dg.setSpacing(8)
        det_items = [
            ("det_bpf", "Detected BPF", "Hz"),
            ("det_harmonics", "Harmonic Count", ""),
            ("det_confidence", "Detection Confidence", "%"),
            ("det_range", "Estimated Range", "m"),
            ("det_speed", "Radial Speed", "m/s"),
            ("det_platform", "Matched Platform", ""),
            ("det_mems", "Resolved MEMS Sensor", ""),
            ("det_attack_freq", "Attack Frequency", "Hz"),
        ]
        for i, (key, label, unit) in enumerate(det_items):
            t = TrophyCard(label, unit)
            dg.addWidget(t, i // 4, i % 4)
            self._trophies[key] = t
        cl.addWidget(det_group)

        # ── Waveform Generation ──
        wf_group = QGroupBox("WAVEFORM GENERATION")
        wg = QGridLayout(wf_group)
        wg.setSpacing(8)
        wf_items = [
            ("wf_broad_sweep", "Broad Sweep", "samples"),
            ("wf_targeted_sweep", "Targeted Sweep", "samples"),
            ("wf_broad_burst", "Broad Burst", "samples"),
            ("wf_targeted_burst", "Targeted Burst", "samples"),
            ("wf_shock_burst", "Shock Burst", "samples"),
            ("wf_peak_amp", "Peak Amplitude", ""),
            ("wf_duration", "Train Duration", "ms"),
            ("wf_freq_range", "Frequency Range", "kHz"),
        ]
        for i, (key, label, unit) in enumerate(wf_items):
            t = TrophyCard(label, unit)
            wg.addWidget(t, i // 4, i % 4)
            self._trophies[key] = t
        cl.addWidget(wf_group)

        # ── Beamforming ──
        bf_group = QGroupBox("BEAMFORMING")
        bg = QGridLayout(bf_group)
        bg.setSpacing(8)
        bf_items = [
            ("bf_elements", "Array Elements", ""),
            ("bf_beamwidth", "Beamwidth", "°"),
            ("bf_gain", "Array Gain", "dB"),
            ("bf_focal_gain", "Focal Gain", "dB"),
            ("bf_delay_spread", "Delay Spread", "µs"),
            ("bf_steer_az", "Steering Azimuth", "°"),
        ]
        for i, (key, label, unit) in enumerate(bf_items):
            t = TrophyCard(label, unit)
            bg.addWidget(t, i // 3, i % 3)
            self._trophies[key] = t
        cl.addWidget(bf_group)

        # ── SubharmonicLadder ──
        sl_group = QGroupBox("ENGAGEMENT LADDER")
        sg = QGridLayout(sl_group)
        sg.setSpacing(8)
        sl_items = [
            ("sl_zone", "Active Zone", ""),
            ("sl_tones", "Tone Count", ""),
            ("sl_base_freq", "Base Frequency", "kHz"),
            ("sl_mode", "Emission Mode", ""),
            ("sl_zone_seq", "Zone Sequence", ""),
            ("sl_doppler_shift", "Doppler Correction", "Hz"),
        ]
        for i, (key, label, unit) in enumerate(sl_items):
            t = TrophyCard(label, unit)
            sg.addWidget(t, i // 3, i % 3)
            self._trophies[key] = t
        cl.addWidget(sl_group)

        # ── Probe / Shell ──
        pr_group = QGroupBox("PROBE & SHELL CHARACTERISATION")
        pg = QGridLayout(pr_group)
        pg.setSpacing(8)
        pr_items = [
            ("pr_shell_class", "Shell Class", ""),
            ("pr_attenuation", "Attenuation", "dB"),
            ("pr_confidence", "Probe Confidence", "%"),
            ("pr_weak_freq", "Weak Frequency", "Hz"),
        ]
        for i, (key, label, unit) in enumerate(pr_items):
            t = TrophyCard(label, unit)
            pg.addWidget(t, i // 4, i % 4)
            self._trophies[key] = t
        cl.addWidget(pr_group)

        # ── Doppler Pre-Compensation ──
        dp_group = QGroupBox("DOPPLER PRE-COMPENSATION")
        dpg = QGridLayout(dp_group)
        dpg.setSpacing(8)
        dp_items = [
            ("dp_emit_freq", "Emitted Frequency", "Hz"),
            ("dp_received_freq", "Target Receives", "Hz"),
            ("dp_round_trip_err", "Round-Trip Error", "Hz"),
            ("dp_max_err_80ms", "Max Error ±80 m/s", "Hz"),
        ]
        for i, (key, label, unit) in enumerate(dp_items):
            t = TrophyCard(label, unit)
            dpg.addWidget(t, i // 4, i % 4)
            self._trophies[key] = t
        cl.addWidget(dp_group)

        # ── Hardware Bench (empty until hardware provides data) ──
        hw_group = QGroupBox("HARDWARE BENCH  (connect gyro + transducer)")
        hg = QGridLayout(hw_group)
        hg.setSpacing(8)
        hw_items = [
            ("hw_baseline_mean", "Baseline Mean", "°/s"),
            ("hw_baseline_std", "Baseline Std", "°/s"),
            ("hw_peak_response", "Peak Gyro Response", "°/s"),
            ("hw_peak_freq", "Peak Resonance Freq", "Hz"),
            ("hw_snr", "Signal-to-Noise Ratio", "×"),
            ("hw_convergence_steps", "Convergence Steps", ""),
        ]
        for i, (key, label, unit) in enumerate(hw_items):
            t = TrophyCard(label, unit)
            hg.addWidget(t, i // 3, i % 3)
            self._trophies[key] = t
        cl.addWidget(hw_group)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ── Quick-fill button ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_fill = QPushButton("POPULATE FROM TEST RESULTS")
        btn_fill.setProperty("runAll", True)
        btn_fill.clicked.connect(self._populate_from_tests)
        btn_row.addWidget(btn_fill)

        btn_clear = QPushButton("CLEAR ALL")
        btn_clear.setStyleSheet(
            f"QPushButton {{ color: {C.RED}; border-color: {C.RED}; }}")
        btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        root.addLayout(btn_row)

    def _populate_from_tests(self):
        """Run quick calculations to fill trophy stands with computed values."""
        # Waveform trophies
        try:
            bs = get_broad_sweep(duration_ms=100)
            self._trophies["wf_broad_sweep"].set_value(str(len(bs)), C.PRIMARY)
            self._trophies["wf_peak_amp"].set_value(
                f"{np.max(np.abs(bs)):.3f}", C.PRIMARY)

            ts = get_targeted_sweep("ICM-42688-P", duration_ms=50)
            self._trophies["wf_targeted_sweep"].set_value(str(len(ts)), C.PRIMARY)

            bb = get_broad_burst()
            self._trophies["wf_broad_burst"].set_value(str(len(bb)), C.PRIMARY)

            tb = get_targeted_burst("ICM-42688-P")
            self._trophies["wf_targeted_burst"].set_value(str(len(tb)), C.PRIMARY)
            self._trophies["wf_duration"].set_value(
                f"{len(tb)/96000*1000:.0f}", C.PRIMARY)

            sh = get_shock_burst()
            self._trophies["wf_shock_burst"].set_value(str(len(sh)), C.PRIMARY)
            self._trophies["wf_freq_range"].set_value("18–35", C.PRIMARY)
        except Exception:
            pass

        # Beamforming trophies
        try:
            grid = ArrayGeometry.rectangular_grid(16, 16)
            self._trophies["bf_elements"].set_value("256", C.PRIMARY)
            bw = estimate_beamwidth(grid, 25000)
            self._trophies["bf_beamwidth"].set_value(f"{bw:.1f}", C.BLUE)
            g = estimate_gain_db(grid)
            self._trophies["bf_gain"].set_value(f"{g:.1f}", C.PRIMARY)
            fg = estimate_focal_gain_db(grid, 3.0, 25000)
            self._trophies["bf_focal_gain"].set_value(f"+{fg:.1f}", C.SECONDARY)

            bf_obj = BeamFormer(grid)
            steer = SteeringVector(azimuth_deg=30.0, elevation_deg=0.0)
            delays = bf_obj.compute_delays(steer, 25000)
            spread = (np.max(delays) - np.min(delays)) * 1e6
            self._trophies["bf_delay_spread"].set_value(f"{spread:.1f}", C.YELLOW)
            self._trophies["bf_steer_az"].set_value("30.0", C.BLUE)
        except Exception:
            pass

        # Ladder trophies
        try:
            ladder = SubharmonicLadder(base_freq_hz=25000)
            self._trophies["sl_base_freq"].set_value("25", C.PRIMARY)
            z = ladder.get_zone(10.0)
            if z:
                freqs = ladder.get_zone_frequencies(z, 0.0)
                self._trophies["sl_zone"].set_value("KILL", C.RED)
                self._trophies["sl_tones"].set_value(str(len(freqs)), C.RED)
                self._trophies["sl_mode"].set_value(z.mode.upper(), C.RED)
            self._trophies["sl_zone_seq"].set_value(
                "P→C→D→K", C.PRIMARY)

            f_emit = doppler_precompensate(25000, 30.0)
            shift = f_emit - 25000
            self._trophies["sl_doppler_shift"].set_value(
                f"{shift:+.0f}", C.YELLOW)
        except Exception:
            pass

        # Doppler pre-comp trophies
        try:
            f_res = 27015.0
            v = 30.0
            f_emit = doppler_precompensate(f_res, v)
            f_rx = f_emit * (343.0 + v) / 343.0
            self._trophies["dp_emit_freq"].set_value(f"{f_emit:.0f}", C.PRIMARY)
            self._trophies["dp_received_freq"].set_value(f"{f_rx:.0f}", C.PRIMARY)
            self._trophies["dp_round_trip_err"].set_value(
                f"{abs(f_rx - f_res):.4f}", C.PRIMARY)
            max_err = 0.0
            for vt in np.linspace(-80, 80, 33):
                fo = doppler_precompensate(f_res, vt)
                fr = fo * (343.0 + vt) / 343.0
                max_err = max(max_err, abs(fr - f_res))
            self._trophies["dp_max_err_80ms"].set_value(
                f"{max_err:.4f}", C.PRIMARY)
        except Exception:
            pass

    def _clear_all(self):
        for t in self._trophies.values():
            t.clear_value()

    def get_trophy(self, key: str) -> TrophyCard | None:
        return self._trophies.get(key)


# ═══════════════════════════════════════════════════════════════
#  TAB 6: WAVEFORM TOOLS
# ═══════════════════════════════════════════════════════════════

class WaveformTab(QWidget):
    """Quick waveform generation + parameter tweaking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("WAVEFORM GENERATOR")
        title.setFont(QFont("Consolas", 13, QFont.Bold))
        title.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 2px;")
        root.addWidget(title)

        # ── Controls ──
        ctrl_group = QGroupBox("SWEEP / BURST PARAMETERS")
        cg = QGridLayout(ctrl_group)

        cg.addWidget(QLabel("Mode:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Broad Sweep (18–35 kHz)", "Targeted Sweep",
            "Broad Burst", "Targeted Burst", "Shock Burst",
            "SubharmonicLadder Zone",
        ])
        cg.addWidget(self.mode_combo, 0, 1, 1, 2)

        cg.addWidget(QLabel("Sensor:"), 0, 3)
        self.wf_sensor = QComboBox()
        self.wf_sensor.addItems(sorted(MEMS_PROFILES.keys()))
        self.wf_sensor.setCurrentText("ICM-42688-P")
        cg.addWidget(self.wf_sensor, 0, 4)

        cg.addWidget(QLabel("Duration (ms):"), 1, 0)
        self.wf_dur = QSpinBox()
        self.wf_dur.setRange(10, 10000)
        self.wf_dur.setValue(200)
        cg.addWidget(self.wf_dur, 1, 1)

        cg.addWidget(QLabel("Amplitude:"), 1, 2)
        self.wf_amp = QDoubleSpinBox()
        self.wf_amp.setRange(0.01, 1.0)
        self.wf_amp.setValue(0.8)
        self.wf_amp.setSingleStep(0.1)
        cg.addWidget(self.wf_amp, 1, 3)

        cg.addWidget(QLabel("Rep Rate (Hz):"), 1, 4)
        self.wf_rep = QSpinBox()
        self.wf_rep.setRange(1, 500)
        self.wf_rep.setValue(50)
        cg.addWidget(self.wf_rep, 1, 5)

        btn_gen = QPushButton("GENERATE")
        btn_gen.clicked.connect(self._generate)
        cg.addWidget(btn_gen, 0, 5)

        root.addWidget(ctrl_group)

        # Trophy cards
        trow = QHBoxLayout()
        trow.setSpacing(8)
        self.wt_samples = TrophyCard("SAMPLES")
        self.wt_duration = TrophyCard("DURATION", "ms")
        self.wt_peak = TrophyCard("PEAK AMP", "")
        self.wt_rms = TrophyCard("RMS", "")
        self.wt_freq_peak = TrophyCard("FFT PEAK", "kHz")
        for t in (self.wt_samples, self.wt_duration, self.wt_peak,
                  self.wt_rms, self.wt_freq_peak):
            trow.addWidget(t)
        root.addLayout(trow)

        # Output
        self.wf_output = QTextEdit()
        self.wf_output.setReadOnly(True)
        self.wf_output.setFont(QFont("Consolas", 9))  # monospace for data output
        root.addWidget(self.wf_output, 1)

    def _generate(self):
        mode = self.mode_combo.currentText()
        sensor = self.wf_sensor.currentText()
        dur = self.wf_dur.value()
        amp = self.wf_amp.value()
        rep = self.wf_rep.value()

        try:
            if "Broad Sweep" in mode:
                wf = get_broad_sweep(duration_ms=dur, amplitude=amp)
                desc = f"Broad sweep 18–35 kHz, {dur} ms"
            elif "Targeted Sweep" in mode:
                wf = get_targeted_sweep(sensor, duration_ms=dur, amplitude=amp)
                freq = MEMS_PROFILES[sensor]["resonance_hz"]
                desc = f"Targeted sweep ±1 kHz around {freq} Hz ({sensor})"
            elif "Broad Burst" in mode:
                wf = get_broad_burst(rep_rate_hz=rep, pulse_ms=3.0, train_ms=dur)
                desc = f"Broad burst train, {rep} Hz rep, {dur} ms"
            elif "Targeted Burst" in mode:
                wf = get_targeted_burst(sensor, rep_rate_hz=rep,
                                        pulse_ms=3.0, train_ms=dur)
                freq = MEMS_PROFILES[sensor]["resonance_hz"]
                desc = f"Targeted burst @ {freq} Hz ({sensor}), {rep} Hz rep"
            elif "Shock" in mode:
                wf = get_shock_burst(rep_rate_hz=rep, pulse_ms=1.0, train_ms=dur)
                desc = f"Shock burst, {rep} Hz rep, {dur} ms"
            elif "Ladder" in mode:
                freq = MEMS_PROFILES[sensor]["resonance_hz"]
                ladder = SubharmonicLadder(base_freq_hz=freq)
                z = ladder.get_zone(50.0)
                if z:
                    wf = ladder.generate_stacked_waveform(z, duration_ms=dur)
                    desc = f"Ladder zone '{z.name}' @ 50m, {sensor}"
                else:
                    self.wf_output.setText("ERROR: No zone at 50m")
                    return
            else:
                return

            n = len(wf)
            dur_actual = n / 96000 * 1000
            peak = np.max(np.abs(wf))
            rms = np.sqrt(np.mean(wf ** 2))

            # FFT peak
            fft_mag = np.abs(np.fft.rfft(wf))
            freqs = np.fft.rfftfreq(n, 1.0 / 96000)
            fft_peak = freqs[np.argmax(fft_mag)] / 1000

            self.wt_samples.set_value(f"{n:,}", C.PRIMARY)
            self.wt_duration.set_value(f"{dur_actual:.1f}", C.PRIMARY)
            self.wt_peak.set_value(f"{peak:.4f}", C.PRIMARY)
            self.wt_rms.set_value(f"{rms:.4f}", C.BLUE)
            self.wt_freq_peak.set_value(f"{fft_peak:.2f}", C.YELLOW)

            lines = [
                desc, "",
                f"Samples: {n:,}",
                f"Duration: {dur_actual:.1f} ms",
                f"Peak amplitude: {peak:.4f}",
                f"RMS: {rms:.4f}",
                f"FFT peak: {fft_peak:.2f} kHz",
                "",
                "First 20 sample values:",
                ", ".join(f"{v:.4f}" for v in wf[:20]),
            ]
            self.wf_output.setText("\n".join(lines))

        except Exception as exc:
            self.wf_output.setText(f"ERROR: {exc}\n\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
#  HELPER — COPYABLE CODE BLOCK
# ═══════════════════════════════════════════════════════════════

class CopyableCodeBlock(QFrame):
    """Monospaced code display with a one-click copy button."""

    def __init__(self, code: str, parent=None):
        super().__init__(parent)
        self._code = code
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.CARD_BG};
                border: 1px solid {C.CARD_BORDER};
                border-left: 3px solid {C.ACCENT};
                border-radius: 6px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(8)

        self._edit = QTextEdit()
        self._edit.setReadOnly(True)
        self._edit.setFont(QFont("Consolas", 9))
        self._edit.setPlainText(code)
        self._edit.setStyleSheet(
            f"background: transparent; border: none; color: {C.PRIMARY};")
        lines = code.count('\n') + 1
        self._edit.setFixedHeight(max(lines * 18 + 8, 32))
        lay.addWidget(self._edit, 1)

        btn = QPushButton("COPY")
        btn.setFixedSize(52, 24)
        btn.setFont(QFont("Segoe UI", 8, QFont.Bold))
        btn.clicked.connect(self._copy)
        lay.addWidget(btn, 0, Qt.AlignTop)

    def _copy(self):
        QApplication.clipboard().setText(self._code)


# ═══════════════════════════════════════════════════════════════
#  TAB: GETTING STARTED  (Tutorial)
# ═══════════════════════════════════════════════════════════════

class TutorialTab(QWidget):
    """Step-by-step guide — installation, build, hardware, and plugin authoring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ── helpers ──────────────────────────────────────────────

    def _section(self, title: str, subtitle: str = "") -> tuple:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {C.BG_MID};
                border: 1px solid {C.CARD_BORDER};
                border-radius: 8px;
                border-left: 3px solid {C.PRIMARY};
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        h = QLabel(title)
        h.setFont(QFont("Consolas", 11, QFont.Bold))
        h.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 1px;")
        lay.addWidget(h)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setFont(QFont("Segoe UI", 9))
            sub.setStyleSheet(f"color: {C.TEXT_DIM};")
            sub.setWordWrap(True)
            lay.addWidget(sub)
        return frame, lay

    def _step(self, lay, num, text: str, color=None):
        color = color or C.TEXT
        row = QHBoxLayout()
        row.setSpacing(10)
        num_lbl = QLabel(str(num))
        num_lbl.setFixedSize(26, 26)
        num_lbl.setAlignment(Qt.AlignCenter)
        num_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        num_lbl.setStyleSheet(
            f"color: {C.BG}; background: {C.PRIMARY}; border-radius: 4px;")
        row.addWidget(num_lbl)
        txt = QLabel(text)
        txt.setFont(QFont("Segoe UI", 9))
        txt.setStyleSheet(f"color: {color};")
        txt.setWordWrap(True)
        row.addWidget(txt, 1)
        lay.addLayout(row)

    def _body(self, lay, text: str):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 9))
        lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

    def _code(self, lay, code: str):
        lay.addWidget(CopyableCodeBlock(code))

    # ── build ─────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sticky header
        hdr = QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            f"background: {C.BG_MID}; border-bottom: 1px solid {C.CARD_BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("GETTING STARTED")
        t.setFont(QFont("Consolas", 12, QFont.Bold))
        t.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 3px;")
        hl.addWidget(t)
        hl.addStretch()
        s = QLabel("Installation · Build · Hardware · Plugin API — everything in one place.")
        s.setFont(QFont("Segoe UI", 9))
        s.setStyleSheet(f"color: {C.TEXT_DIM};")
        hl.addWidget(s)
        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(20, 20, 20, 20)
        cl.setSpacing(16)

        # §1 What Is This?
        s1, s1l = self._section(
            "§1 — What Is SoulMusic?",
            "A non-lethal drone-neutralisation platform. It transmits an ultrasonic tone at the "
            "MEMS gyroscope resonance frequency of a drone's flight controller. When the gyroscope "
            "saturates, the stabilisation loop collapses and the drone lands itself — no explosion, "
            "no RF jamming, no hardware damage, zero casualties.")
        self._body(s1l,
            "This GUI lets you run the full software test suite, browse the sensor and platform "
            "databases, compute beamforming parameters, generate test waveforms, load your own "
            "calculation plugins, and verify your system environment — all without touching the "
            "terminal once it's running.")
        cl.addWidget(s1)

        # §2 Requirements
        s2, s2l = self._section(
            "§2 — Requirements",
            "Two packages. That is the entire mandatory dependency list.")
        req_row = QHBoxLayout()
        for req, note, color in [
            ("Python  ≥ 3.10", "python.org/downloads", C.GREEN),
            ("PySide6  ≥ 6.5",  "Qt for Python — this GUI", C.BLUE),
            ("NumPy   ≥ 1.24",  "Array maths + FFT", C.YELLOW),
        ]:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {C.CARD_BG};
                    border: 1px solid {color};
                    border-radius: 6px;
                }}
            """)
            cl2 = QVBoxLayout(card)
            cl2.setContentsMargins(12, 8, 12, 8)
            n = QLabel(req)
            n.setFont(QFont("Consolas", 10, QFont.Bold))
            n.setStyleSheet(f"color: {color};")
            cl2.addWidget(n)
            d = QLabel(note)
            d.setFont(QFont("Segoe UI", 8))
            d.setStyleSheet(f"color: {C.TEXT_DIM};")
            cl2.addWidget(d)
            req_row.addWidget(card)
        s2l.addLayout(req_row)
        self._body(s2l,
            "Optional extras:  pyserial (Arduino/serial comms),  "
            "sounddevice (real-time audio output).  "
            "Install them with:  pip install pyserial sounddevice")
        cl.addWidget(s2)

        # §3 Installation
        s3, s3l = self._section(
            "§3 — Installation",
            "Three commands from any terminal. Copy each one with the button and run in order.")
        self._step(s3l, 1, "Clone or download the SoulMusic repository.")
        self._code(s3l, "git clone https://github.com/your-org/SoulMusic.git")
        self._step(s3l, 2, "Navigate into the project folder.")
        self._code(s3l, "cd SoulMusic")
        self._step(s3l, 3, "Install required packages.")
        self._code(s3l, "pip install PySide6 numpy")
        self._step(s3l, 4, "Launch the GUI.")
        self._code(s3l, "python soul_gui.py")
        self._body(s3l,
            "On Windows you can also double-click soul_gui.py if Python is your default handler "
            "for .py files. The SYSTEM INFO tab will verify all imports on first launch.")
        cl.addWidget(s3)

        # §4 Running Tests
        s4, s4l = self._section(
            "§4 — Running the Test Suite",
            "All 10 tests run entirely in software — no hardware required. They validate the "
            "physics maths, waveform generation, platform detection, and the full pipeline.")
        self._step(s4l, "A",
            "In this GUI: switch to TEST SUITE and click RUN ALL TESTS.", C.GREEN)
        self._step(s4l, "B", "Or run the test harness directly from a terminal:")
        self._code(s4l, "python test_harness.py")
        self._step(s4l, "C", "For benchmark timing data:")
        self._code(s4l, "python bench_test.py")
        self._body(s4l,
            "Expected: 10/10 pass, 167 assertions green. If a test fails, check the "
            "SYSTEM INFO tab — a missing import is the most common cause.")
        cl.addWidget(s4)

        # §5 Hardware Bench
        s5, s5l = self._section(
            "§5 — Hardware Bench Setup  (optional)",
            "To run live acoustic tests you need an Arduino Nano, an MPU-6050 gyro board "
            "(GY-521), a PAM8610 amplifier, and a horn tweeter. Total cost ~$25–$40.")
        for hw, desc in [
            ("Arduino Nano / Uno",      "Sends gyro data over USB serial at 115200 baud"),
            ("GY-521 / MPU-6050",       "The MEMS gyroscope that receives the acoustic signal"),
            ("PAM8610 amplifier",       "Drives the transducer — up to 15 W output"),
            ("Horn tweeter (25–40 kHz)", "The acoustic emitter — aim at the target gyro"),
            ("USB cable",               "Connects Arduino to PC"),
        ]:
            r = QHBoxLayout()
            r.setSpacing(8)
            dot = QLabel("◆")
            dot.setFont(QFont("Consolas", 9))
            dot.setStyleSheet(f"color: {C.YELLOW};")
            dot.setFixedWidth(14)
            r.addWidget(dot)
            hw_l = QLabel(f"<b>{hw}</b>  —  {desc}")
            hw_l.setFont(QFont("Segoe UI", 9))
            hw_l.setStyleSheet(f"color: {C.TEXT};")
            hw_l.setTextFormat(Qt.RichText)
            r.addWidget(hw_l, 1)
            s5l.addLayout(r)
        self._body(s5l,
            "Wiring: GY-521 SDA→A4, SCL→A5. Upload the SoulMusic Arduino sketch. "
            "Connect PAM8610 output to tweeter. Aim at the GY-521 from 5–30 cm distance.")
        self._code(s5l, "python bench_test.py")
        cl.addWidget(s5)

        # §6 Build the EXE
        s6, s6l = self._section(
            "§6 — Building the Standalone EXE",
            "The project ships with a PyInstaller spec that produces a single-folder Windows "
            "executable. An Inno Setup installer script is also included.")
        self._step(s6l, 1, "Install PyInstaller (once):")
        self._code(s6l, "pip install pyinstaller")
        self._step(s6l, 2, "Build using the project spec file (run from the project root):")
        self._code(s6l, "pyinstaller --clean SoulMusic.spec")
        self._step(s6l, 3, "The executable will be at:")
        self._code(s6l, r"dist\SoulMusic\SoulMusic.exe")
        self._step(s6l, 4,
            "(Optional) Build the Windows installer — requires Inno Setup 6:")
        self._code(s6l, r"iscc installer\setup.iss")
        self._body(s6l,
            "The spec file already lists all hidden imports for acoustic/, detection/, and "
            "flight/ packages. If you add new modules, append their dotted name to the "
            "hiddenimports list in SoulMusic.spec before rebuilding.")
        cl.addWidget(s6)

        # §7 Tab Reference
        s7, s7l = self._section("§7 — Tab Reference")
        tab_info = [
            ("GETTING STARTED", C.PRIMARY,
             "You are here. All commands, hardware setup, and plugin docs in one place."),
            ("TEST SUITE",      C.GREEN,
             "Run all 10 synthetic tests. Click any test name to run it solo. "
             "Green = pass, Red = fail."),
            ("RESONANCE",       C.BLUE,
             "Browse MEMS sensor profiles and compute SubharmonicLadder engagement "
             "zones for any target range and approach speed."),
            ("BEAMFORMING",     C.YELLOW,
             "Phased-array geometry calculator. Beamwidth, array gain, near-field "
             "focal gain, and per-element delay schedules."),
            ("PLATFORMS",       C.RED,
             "Detection database — 24 drone platforms with motor count, blade count, "
             "BPF range, and linked MEMS sensor profile."),
            ("WAVEFORMS",       C.ACCENT,
             "Generate and inspect acoustic waveforms: broad sweeps, targeted bursts, "
             "shock trains, and SubharmonicLadder stacked tones."),
            ("TROPHY WALL",     C.PRIMARY_DIM,
             "Live scoreboard of all computed values. Click 'Populate' to fill every "
             "placeholder from software calculations."),
            ("MODULE LOADER",   C.GREEN,
             "Load your own .py calculation modules at runtime. Auto-discovers the "
             "plugins/ folder. Runs calculations in a background thread with a "
             "dynamic parameter form — no code changes required."),
            ("SYSTEM INFO",     C.BLUE,
             "Verifies your Python environment: package versions, SoulMusic module "
             "imports, detected serial ports, and audio output devices."),
        ]
        for tab_name, color, desc in tab_info:
            r = QHBoxLayout()
            r.setSpacing(10)
            badge = QLabel(tab_name)
            badge.setFixedWidth(170)
            badge.setFont(QFont("Consolas", 8, QFont.Bold))
            badge.setStyleSheet(f"color: {color};")
            r.addWidget(badge)
            d = QLabel(desc)
            d.setFont(QFont("Segoe UI", 9))
            d.setStyleSheet(f"color: {C.TEXT_DIM};")
            d.setWordWrap(True)
            r.addWidget(d, 1)
            s7l.addLayout(r)
        cl.addWidget(s7)

        # §8 Plugin API
        s8, s8l = self._section(
            "§8 — Writing a Plugin / Calculation Module",
            "Drop a .py file in the plugins/ folder and it will be auto-discovered on "
            "next launch (or click SCAN plugins/ in the MODULE LOADER tab at any time).")
        self._body(s8l, "Minimum plugin structure:")
        self._code(s8l, (
            "# my_plugin.py\n"
            "SOUL_VERSION     = '1.0'\n"
            "SOUL_DESCRIPTION = 'My custom calculations'\n\n"
            "def my_formula(freq_hz: float, range_m: float) -> dict:\n"
            "    \"\"\"Scale frequency by inverse-sqrt of range.\"\"\"\n"
            "    return {'result': freq_hz / (range_m ** 0.5), 'units': 'Hz/sqrt(m)'}\n\n"
            "SOUL_CALCULATIONS = [\n"
            "    {\n"
            "        'name':        'My Formula',\n"
            "        'fn':          my_formula,\n"
            "        'description': 'Scales frequency by inverse sqrt of range',\n"
            "        'category':    'Acoustics',\n"
            "        'params': [\n"
            "            {'name': 'freq_hz', 'type': 'float', 'default': 25000.0,\n"
            "             'description': 'MEMS resonance in Hz'},\n"
            "            {'name': 'range_m', 'type': 'float', 'default': 10.0,\n"
            "             'min': 0.1, 'max': 300.0,\n"
            "             'description': 'Target range in metres'},\n"
            "        ],\n"
            "    }\n"
            "]"
        ))
        self._body(s8l,
            "The function can return any value — dict, float, list, or string. "
            "The MODULE LOADER will pretty-print the output. "
            "If SOUL_CALCULATIONS is absent the loader falls back to introspecting all "
            "top-level public callables and auto-generating parameter forms from type hints.")
        cl.addWidget(s8)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)


# ═══════════════════════════════════════════════════════════════
#  SYSTEM INFO — background check worker
# ═══════════════════════════════════════════════════════════════

class SysCheckWorker(QObject):
    result   = Signal(str, str, str)  # key, status ("ok"|"warn"|"fail"), detail
    finished = Signal()

    def run(self):
        checks = [
            ("python",       self._check_python),
            ("pyside6",      lambda: self._check_pkg("PySide6", "6.5")),
            ("numpy",        lambda: self._check_pkg("numpy", "1.24")),
            ("pyserial",     lambda: self._check_optional("serial")),
            ("sounddev",     lambda: self._check_optional("sounddevice")),
            ("acoustic",     lambda: self._check_import("acoustic.resonance", "MEMS_PROFILES")),
            ("beam",         lambda: self._check_import("acoustic.beam", "ArrayGeometry")),
            ("probe",        lambda: self._check_import("acoustic.probe", "SHELL_PRESETS")),
            ("detect",       lambda: self._check_import("detection.acoustic_detect", "PLATFORM_DB")),
            ("flight",       lambda: self._check_import("flight.telemetry")),
            ("serial_ports",    self._check_serial_ports),
            ("audio_dev",       self._check_audio_devices),
            ("platform_compat", self._check_platform_compat),
        ]
        for key, fn in checks:
            status, detail = fn()
            self.result.emit(key, status, detail)
        self.finished.emit()

    @staticmethod
    def _ver_ok(installed: str, minimum: str) -> bool:
        def _t(s): return tuple(int(x) for x in s.split(".")[:3] if x.isdigit())
        try:
            return _t(installed) >= _t(minimum)
        except Exception:
            return True

    @staticmethod
    def _check_python():
        import sys as _s
        v = _s.version_info
        ver = f"{v.major}.{v.minor}.{v.micro}"
        return ("ok", f"Python {ver}") if v >= (3, 10) else \
               ("warn", f"Python {ver} — 3.10+ required")

    def _check_pkg(self, pkg_name: str, min_ver: str):
        import importlib.metadata as meta
        try:
            ver = meta.version(pkg_name)
            if self._ver_ok(ver, min_ver):
                return "ok", f"{pkg_name} {ver}"
            return "warn", f"{pkg_name} {ver} — {min_ver}+ recommended"
        except Exception:
            try:
                import importlib
                importlib.import_module(pkg_name)
                return "ok", f"{pkg_name} (version undetected)"
            except ImportError:
                return "fail", f"{pkg_name} NOT FOUND  —  pip install {pkg_name.lower()}"

    @staticmethod
    def _check_optional(pkg_name: str):
        import importlib
        try:
            importlib.import_module(pkg_name)
            return "ok", f"{pkg_name} available"
        except ImportError:
            return "warn", f"{pkg_name} not installed (optional)"

    @staticmethod
    def _check_import(module: str, attr: str = ""):
        import importlib
        try:
            m = importlib.import_module(module)
            if attr and not hasattr(m, attr):
                return "warn", f"{module} loaded but '{attr}' missing"
            return "ok", f"{module} OK"
        except Exception as e:
            return "fail", f"{module} — {e}"

    @staticmethod
    def _check_serial_ports():
        try:
            import serial.tools.list_ports as lp
            ports = list(lp.comports())
            if ports:
                names = ", ".join(p.device for p in ports[:6])
                return "ok", f"{len(ports)} port(s): {names}"
            return "warn", "No serial ports detected"
        except ImportError:
            return "warn", "pyserial not installed — run: pip install pyserial"

    @staticmethod
    def _check_audio_devices():
        try:
            import sounddevice as sd
            out = [d for d in sd.query_devices() if d["max_output_channels"] > 0]
            if out:
                return "ok", f"{len(out)} output device(s): {out[0]['name'][:50]}"
            return "warn", "No audio output devices found"
        except ImportError:
            return "warn", "sounddevice not installed — run: pip install sounddevice"
        except Exception as e:
            return "warn", f"Audio query failed: {e}"

    @staticmethod
    def _check_platform_compat():
        """Report OK/WARN based on whether the current OS is a tested target."""
        import platform as _p
        plt = sys.platform
        if plt == "win32":
            try:
                vi = sys.getwindowsversion()
                build = vi.build
                if vi.major == 10 and build >= 22000:
                    return "ok", f"Windows 11 (build {build})"
                elif vi.major == 10 and build >= 19041:
                    return "ok", f"Windows 10 (build {build})"
                elif vi.major == 10:
                    return "warn", f"Windows 10 build {build} — older build; update recommended"
                else:
                    return "warn", f"Windows {vi.major}.{vi.minor} — untested; use Win10/11"
            except Exception as exc:
                return "warn", f"Windows version check failed: {exc}"
        elif plt == "linux":
            try:
                info = _p.freedesktop_os_release()
                name = info.get("NAME", "")
                ver_id = info.get("VERSION_ID", "")
                full = f"{name} {ver_id}".strip()
                _TESTED: dict = {
                    "Ubuntu": {"20.04", "22.04", "24.04"},
                    "Debian GNU/Linux": {"11", "12"},
                    "Debian": {"11", "12"},
                    "Fedora Linux": {"38", "39"},
                    "Fedora": {"38", "39"},
                }
                if "Raspberry" in name or "Raspbian" in name:
                    return "ok", f"Raspberry Pi OS ({full}) — supported"
                for dist, vers in _TESTED.items():
                    if dist in name:
                        if ver_id in vers:
                            return "ok", f"{full} — supported"
                        return "warn", (
                            f"{full} — tested on {sorted(vers)}; "
                            "this version is untested"
                        )
                return "warn", (
                    f"{full} — untested distribution; "
                    "verify Qt 6.5 is available via pip"
                )
            except Exception:
                return "warn", (
                    "Linux detected; distro check unavailable "
                    "— verify Qt 6.5 is installed"
                )
        elif plt == "darwin":
            try:
                ver = _p.mac_ver()[0]
                major = int(ver.split(".")[0]) if ver else 0
                if major >= 13:
                    return "warn", f"macOS {ver} — best-effort only; no official installer"
                return "warn", f"macOS {ver} — untested; macOS 13+ (Ventura) recommended"
            except Exception:
                return "warn", "macOS — best-effort support; no official installer"
        else:
            return "warn", f"Platform '{plt}' is untested — use Windows 10/11 or a supported Linux"


# ═══════════════════════════════════════════════════════════════
#  TAB: SYSTEM INFO
# ═══════════════════════════════════════════════════════════════

class SystemInfoTab(QWidget):
    _CHECK_META = {
        "python":       ("Python",                  "Runtime version"),
        "pyside6":      ("PySide6",                 "Qt GUI framework"),
        "numpy":        ("NumPy",                   "Array maths + FFT"),
        "pyserial":     ("pyserial",                "Serial / Arduino comms"),
        "sounddev":     ("sounddevice",             "Audio output stream"),
        "acoustic":     ("acoustic.resonance",      "MEMS profile engine"),
        "beam":         ("acoustic.beam",           "Beamforming maths"),
        "probe":        ("acoustic.probe",          "Shell characterisation"),
        "detect":       ("detection.acoustic_detect", "Platform database"),
        "flight":       ("flight.telemetry",        "Telemetry parsing"),
        "serial_ports":     ("Serial Ports",        "Detected COM / tty devices"),
        "audio_dev":        ("Audio Devices",       "Output device enumeration"),
        "platform_compat":  ("Platform Compat",     "OS version compatibility"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict = {}   # key -> (status_lbl, detail_lbl, card_frame)
        self._thread = None
        self._worker = None
        self._build_ui()
        QTimer.singleShot(600, self._run_checks)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            f"background: {C.BG_MID}; border-bottom: 1px solid {C.CARD_BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("SYSTEM INFO  &  VERIFICATION")
        t.setFont(QFont("Consolas", 12, QFont.Bold))
        t.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 2px;")
        hl.addWidget(t)
        hl.addStretch()
        self.refresh_btn = QPushButton("RE-CHECK")
        self.refresh_btn.setFixedHeight(28)
        self.refresh_btn.clicked.connect(self._run_checks)
        hl.addWidget(self.refresh_btn)
        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(20, 20, 20, 20)
        cl.setSpacing(16)

        # Environment & packages
        env_group = QGroupBox("ENVIRONMENT & PACKAGES")
        eg = QGridLayout(env_group)
        eg.setSpacing(8)
        for i, key in enumerate(["python", "pyside6", "numpy", "pyserial", "sounddev"]):
            name, desc = self._CHECK_META[key]
            card, sl, dl = self._make_card(name, desc)
            eg.addWidget(card, i // 2, i % 2)
            self._cards[key] = (sl, dl, card)
        cl.addWidget(env_group)

        # Module imports
        mod_group = QGroupBox("SOULMUSIC MODULE IMPORTS")
        mg = QGridLayout(mod_group)
        mg.setSpacing(8)
        for i, key in enumerate(["acoustic", "beam", "probe", "detect", "flight"]):
            name, desc = self._CHECK_META[key]
            card, sl, dl = self._make_card(name, desc)
            mg.addWidget(card, i // 3, i % 3)
            self._cards[key] = (sl, dl, card)
        cl.addWidget(mod_group)

        # Hardware detection + platform check
        hw_group = QGroupBox("HARDWARE DETECTION & PLATFORM")
        hg = QGridLayout(hw_group)
        hg.setSpacing(8)
        hw_keys = ["serial_ports", "audio_dev", "platform_compat"]
        for i, key in enumerate(hw_keys):
            name, desc = self._CHECK_META[key]
            card, sl, dl = self._make_card(name, desc)
            hg.addWidget(card, i // 2, i % 2)
            self._cards[key] = (sl, dl, card)
        cl.addWidget(hw_group)

        # Runtime details
        info_group = QGroupBox("RUNTIME DETAILS")
        ig = QVBoxLayout(info_group)
        import platform as _plat
        for line in [
            f"OS:          {_plat.system()} {_plat.release()}  ({_plat.machine()})",
            f"Python exe:  {sys.executable}",
            f"Project dir: {_HERE}",
        ]:
            lbl = QLabel(line)
            lbl.setFont(QFont("Consolas", 9))
            lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            ig.addWidget(lbl)
        cl.addWidget(info_group)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _make_card(self, name: str, desc: str):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {C.CARD_BG};
                border: 1px solid {C.CARD_BORDER};
                border-radius: 6px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(3)

        name_row = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        name_lbl.setStyleSheet(f"color: {C.PRIMARY};")
        name_row.addWidget(name_lbl)
        name_row.addStretch()
        status_lbl = QLabel("CHECKING…")
        status_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        status_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        name_row.addWidget(status_lbl)
        cl.addLayout(name_row)

        desc_lbl = QLabel(desc)
        desc_lbl.setFont(QFont("Segoe UI", 8))
        desc_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        cl.addWidget(desc_lbl)

        detail_lbl = QLabel("—")
        detail_lbl.setFont(QFont("Segoe UI", 8))
        detail_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        detail_lbl.setWordWrap(True)
        cl.addWidget(detail_lbl)

        return card, status_lbl, detail_lbl

    def _run_checks(self):
        for sl, dl, card in self._cards.values():
            sl.setText("CHECKING…")
            sl.setStyleSheet(f"color: {C.TEXT_DIM};")
            dl.setText("—")
            card.setStyleSheet(f"""
                QFrame {{
                    background: {C.CARD_BG};
                    border: 1px solid {C.CARD_BORDER};
                    border-radius: 6px;
                }}
            """)

        if self._thread and self._thread.isRunning():
            return
        self._thread = QThread()
        self._worker = SysCheckWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.result.connect(self._on_result)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_result(self, key: str, status: str, detail: str):
        if key not in self._cards:
            return
        sl, dl, card = self._cards[key]
        color_map = {"ok": C.GREEN, "warn": C.YELLOW, "fail": C.RED}
        text_map  = {"ok": "OK ✓",  "warn": "WARN",  "fail": "FAIL ✗"}
        color = color_map.get(status, C.TEXT_DIM)
        sl.setText(text_map.get(status, "?"))
        sl.setStyleSheet(f"color: {color}; font-weight: bold;")
        dl.setText(detail)
        card.setStyleSheet(f"""
            QFrame {{
                background: {C.CARD_BG};
                border: 1px solid {C.CARD_BORDER};
                border-left: 3px solid {color};
                border-radius: 6px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
#  MODULE LOADER — dataclasses + registry
# ═══════════════════════════════════════════════════════════════

import importlib.util as _iutil
import inspect as _inspect


@dataclass
class ParamSpec:
    name:        str
    type_hint:   str         # "int" | "float" | "str" | "bool"
    default:     object
    description: str   = ""
    min_val:     object = None
    max_val:     object = None


@dataclass
class CalculationDef:
    name:        str
    fn:          object      # callable
    params:      list        # list[ParamSpec]
    description: str  = ""
    category:    str  = "General"


@dataclass
class PluginEntry:
    name:         str
    path:         Path
    module:       object
    version:      str  = "?"
    description:  str  = ""
    calculations: list = field(default_factory=list)
    load_error:   str  = ""


class ModuleRegistry:
    """Loads and manages external Python calculation modules at runtime."""

    def __init__(self):
        self._plugins: dict = {}   # name -> PluginEntry

    # ── public ───────────────────────────────────────────────

    def load_file(self, path: Path) -> PluginEntry:
        name = path.stem
        try:
            spec = _iutil.spec_from_file_location(name, path)
            mod  = _iutil.module_from_spec(spec)
            spec.loader.exec_module(mod)

            version = getattr(mod, "SOUL_VERSION",
                              getattr(mod, "__version__", "?"))
            description = (
                getattr(mod, "SOUL_DESCRIPTION", None)
                or getattr(mod, "__doc__", "No description")
                or "No description"
            ).strip()[:240]

            calcs = self._extract_calculations(mod)
            entry = PluginEntry(
                name=name, path=path, module=mod,
                version=str(version), description=description,
                calculations=calcs,
            )
        except Exception as exc:
            entry = PluginEntry(
                name=path.stem, path=path, module=None,
                load_error=f"{exc}\n\n{traceback.format_exc()}",
            )
        self._plugins[entry.name] = entry
        return entry

    def unload(self, name: str):
        self._plugins.pop(name, None)

    def get_all(self) -> list:
        return list(self._plugins.values())

    def auto_discover(self, directory: Path) -> list:
        loaded = []
        if not directory.is_dir():
            return loaded
        for py_file in sorted(directory.glob("*.py")):
            if py_file.stem.startswith("_"):
                continue
            if py_file.stem not in self._plugins:
                loaded.append(self.load_file(py_file))
        return loaded

    # ── private ──────────────────────────────────────────────

    @staticmethod
    def _extract_calculations(mod) -> list:
        calcs = []

        # Protocol 1: explicit SOUL_CALCULATIONS list
        soul_list = getattr(mod, "SOUL_CALCULATIONS", None)
        if soul_list:
            for item in soul_list:
                params = [
                    ParamSpec(
                        name=p["name"],
                        type_hint=p.get("type", "float"),
                        default=p.get("default", 0.0),
                        description=p.get("description", ""),
                        min_val=p.get("min"),
                        max_val=p.get("max"),
                    )
                    for p in item.get("params", [])
                ]
                calcs.append(CalculationDef(
                    name=item.get("name", "?"),
                    fn=item.get("fn"),
                    params=params,
                    description=item.get("description", ""),
                    category=item.get("category", "General"),
                ))
            return calcs

        # Protocol 2: introspect top-level public callables
        for attr_name in dir(mod):
            if attr_name.startswith("_"):
                continue
            obj = getattr(mod, attr_name)
            if not callable(obj):
                continue
            try:
                sig = _inspect.signature(obj)
            except (ValueError, TypeError):
                continue
            params = []
            for pname, param in sig.parameters.items():
                ann = param.annotation
                if ann is _inspect.Parameter.empty:
                    th = "float"
                elif ann in (int,):
                    th = "int"
                elif ann in (str,):
                    th = "str"
                elif ann in (bool,):
                    th = "bool"
                else:
                    th = "float"
                dflt = (param.default
                        if param.default is not _inspect.Parameter.empty
                        else (0 if th in ("int", "float") else ""))
                params.append(ParamSpec(name=pname, type_hint=th, default=dflt,
                                        description=str(ann) if ann is not _inspect.Parameter.empty else ""))
            calcs.append(CalculationDef(
                name=attr_name, fn=obj, params=params,
                description=(obj.__doc__ or "").strip()[:200],
            ))
        return calcs


# Singleton registry shared across the whole application
_REGISTRY = ModuleRegistry()


class CalcWorker(QObject):
    """Runs a plugin calculation in a background thread, emits string result."""
    finished = Signal(str, str)   # result_text, error_text

    def __init__(self, fn, kwargs: dict):
        super().__init__()
        self._fn = fn
        self._kwargs = kwargs

    def run(self):
        import json
        try:
            result = self._fn(**self._kwargs)
            try:
                text = json.dumps(result, indent=2, default=str)
            except Exception:
                text = str(result)
            self.finished.emit(text, "")
        except Exception as exc:
            self.finished.emit("", f"{exc}\n\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
#  TAB: MODULE LOADER
# ═══════════════════════════════════════════════════════════════

class ModuleLoaderTab(QWidget):
    """Load any .py file and run its calculations with a dynamic parameter form."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_plugin = None
        self._selected_calc   = None
        self._param_widgets: list = []   # [(name, widget)]
        self._thread = None
        self._worker = None
        self._build_ui()
        QTimer.singleShot(300, self._auto_discover)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            f"background: {C.BG_MID}; border-bottom: 1px solid {C.CARD_BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("MODULE LOADER")
        t.setFont(QFont("Consolas", 12, QFont.Bold))
        t.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 3px;")
        hl.addWidget(t)
        hl.addStretch()
        warn = QLabel("⚠  Loads and executes Python files.  Only load modules you trust.")
        warn.setFont(QFont("Segoe UI", 8))
        warn.setStyleSheet(f"color: {C.YELLOW};")
        hl.addWidget(warn)
        root.addWidget(hdr)

        splitter = QSplitter(Qt.Horizontal)

        # ── Left: module list ──────────────────────────────
        left = QFrame()
        left.setMinimumWidth(260)
        left.setMaximumWidth(340)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(8)

        mod_lbl = QLabel("LOADED MODULES")
        mod_lbl.setFont(QFont("Consolas", 10, QFont.Bold))
        mod_lbl.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 1px;")
        ll.addWidget(mod_lbl)

        btn_row = QHBoxLayout()
        btn_load = QPushButton("LOAD FILE…")
        btn_load.setFixedHeight(28)
        btn_load.clicked.connect(self._load_file)
        btn_row.addWidget(btn_load)
        btn_scan = QPushButton("SCAN plugins/")
        btn_scan.setFixedHeight(28)
        btn_scan.clicked.connect(self._auto_discover)
        btn_row.addWidget(btn_scan)
        ll.addLayout(btn_row)

        btn_unload = QPushButton("UNLOAD SELECTED")
        btn_unload.setFixedHeight(26)
        btn_unload.setStyleSheet(
            f"QPushButton {{ color: {C.RED}; border-color: {C.RED}; }}")
        btn_unload.clicked.connect(self._unload_selected)
        ll.addWidget(btn_unload)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_widget = QWidget()
        self._list_lay = QVBoxLayout(self._list_widget)
        self._list_lay.setSpacing(4)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.addStretch()
        self._list_scroll.setWidget(self._list_widget)
        ll.addWidget(self._list_scroll, 1)

        hint = QLabel(f"Auto-scan dir:\n{_HERE / 'plugins'}")
        hint.setFont(QFont("Segoe UI", 8))
        hint.setStyleSheet(f"color: {C.TEXT_DIM};")
        hint.setWordWrap(True)
        ll.addWidget(hint)

        splitter.addWidget(left)

        # ── Right: calculation runner ──────────────────────
        right = QFrame()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(10)

        self.mod_info_lbl = QLabel("Select a module from the left panel.")
        self.mod_info_lbl.setFont(QFont("Segoe UI", 9))
        self.mod_info_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        self.mod_info_lbl.setWordWrap(True)
        rl.addWidget(self.mod_info_lbl)

        calc_row = QHBoxLayout()
        calc_row.addWidget(QLabel("Calculation:"))
        self.calc_combo = QComboBox()
        self.calc_combo.setMinimumWidth(240)
        self.calc_combo.currentIndexChanged.connect(self._on_calc_selected)
        calc_row.addWidget(self.calc_combo, 1)
        rl.addLayout(calc_row)

        self.calc_desc_lbl = QLabel()
        self.calc_desc_lbl.setFont(QFont("Segoe UI", 9))
        self.calc_desc_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        self.calc_desc_lbl.setWordWrap(True)
        rl.addWidget(self.calc_desc_lbl)

        param_group = QGroupBox("PARAMETERS")
        self.param_lay = QGridLayout(param_group)
        self.param_lay.setSpacing(6)
        rl.addWidget(param_group)

        run_row = QHBoxLayout()
        self.run_btn = QPushButton("▶  RUN CALCULATION")
        self.run_btn.setProperty("runAll", True)
        self.run_btn.setFixedHeight(34)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_calculation)
        run_row.addWidget(self.run_btn)
        clr_btn = QPushButton("CLEAR OUTPUT")
        clr_btn.setFixedHeight(34)
        clr_btn.clicked.connect(lambda: self.output.clear())
        run_row.addWidget(clr_btn)
        rl.addLayout(run_row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 9))
        rl.addWidget(self.output, 1)

        splitter.addWidget(right)
        splitter.setSizes([300, 720])

        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(splitter, 1)
        root.addLayout(wrapper, 1)

    # ── module management ────────────────────────────────────

    def _load_file(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Calculation Module", str(_HERE),
            "Python Files (*.py)")
        if not path:
            return
        entry = _REGISTRY.load_file(Path(path))
        self._refresh_list()
        if entry.load_error:
            self.output.append(
                f"[ERROR] Could not load '{entry.name}':\n{entry.load_error}")
        else:
            self.output.append(
                f"[OK] Loaded '{entry.name}'  v{entry.version}  "
                f"— {len(entry.calculations)} calculation(s).")
            self._select_plugin(entry)

    def _auto_discover(self):
        plugins_dir = _HERE / "plugins"
        loaded = _REGISTRY.auto_discover(plugins_dir)
        self._refresh_list()
        if loaded:
            ok  = [e.name for e in loaded if not e.load_error]
            err = [e.name for e in loaded if e.load_error]
            parts = []
            if ok:  parts.append(f"Loaded: {', '.join(ok)}")
            if err: parts.append(f"Errors: {', '.join(err)}")
            self.output.append("[SCAN] " + " | ".join(parts))
        elif not plugins_dir.is_dir():
            self.output.append(
                f"[SCAN] No plugins/ folder at {plugins_dir}\n"
                "       Create it and drop .py modules inside.")
        else:
            self.output.append("[SCAN] No new modules found in plugins/.")

    def _unload_selected(self):
        if not self._selected_plugin:
            return
        name = self._selected_plugin.name
        _REGISTRY.unload(name)
        self._selected_plugin = None
        self._refresh_list()
        self._clear_calc_ui()
        self.output.append(f"[UNLOAD] '{name}' removed.")

    def _refresh_list(self):
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for entry in _REGISTRY.get_all():
            is_sel = (self._selected_plugin
                      and self._selected_plugin.name == entry.name)
            btn = QPushButton()
            if entry.load_error:
                btn.setText(f"✗  {entry.name}")
                btn.setStyleSheet(
                    f"QPushButton {{ text-align: left; color: {C.RED}; "
                    f"border-color: {C.RED}; background: rgba(248,113,113,0.05); }}")
            elif is_sel:
                btn.setText(f"◆  {entry.name}  [{len(entry.calculations)} calcs]")
                btn.setStyleSheet(
                    f"QPushButton {{ text-align: left; color: {C.GREEN}; "
                    f"border-color: {C.GREEN}; background: rgba(74,222,128,0.06); }}")
            else:
                btn.setText(f"◆  {entry.name}  [{len(entry.calculations)} calcs]")
                btn.setStyleSheet(
                    f"QPushButton {{ text-align: left; color: {C.PRIMARY}; }}")
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda checked, e=entry: self._select_plugin(e))
            self._list_lay.insertWidget(self._list_lay.count() - 1, btn)

    def _select_plugin(self, entry: PluginEntry):
        if entry.load_error:
            self.mod_info_lbl.setText(
                f"Error loading '{entry.name}':\n{entry.load_error}")
            self._clear_calc_ui()
            return
        self._selected_plugin = entry
        self._refresh_list()
        self.mod_info_lbl.setText(
            f"{entry.name}  v{entry.version}  ·  {entry.path.name}\n"
            f"{entry.description}")
        self.calc_combo.blockSignals(True)
        self.calc_combo.clear()
        for c in entry.calculations:
            self.calc_combo.addItem(f"[{c.category}]  {c.name}")
        self.calc_combo.blockSignals(False)
        if entry.calculations:
            self.calc_combo.setCurrentIndex(0)
            self._on_calc_selected(0)
            self.run_btn.setEnabled(True)
        else:
            self._clear_calc_ui()
            self.mod_info_lbl.setText(
                self.mod_info_lbl.text() +
                "\n\n(No calculations found — define SOUL_CALCULATIONS in the module.)")

    def _on_calc_selected(self, index: int):
        if not self._selected_plugin or index < 0:
            return
        calcs = self._selected_plugin.calculations
        if index >= len(calcs):
            return
        calc = calcs[index]
        self._selected_calc = calc
        self.calc_desc_lbl.setText(calc.description or "(no description)")
        self._build_param_form(calc)

    def _build_param_form(self, calc: CalculationDef):
        while self.param_lay.count():
            item = self.param_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._param_widgets.clear()

        if not calc.params:
            lbl = QLabel("(no parameters)")
            lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
            self.param_lay.addWidget(lbl, 0, 0, 1, 4)
            return

        for row, ps in enumerate(calc.params):
            nl = QLabel(ps.name)
            nl.setFont(QFont("Consolas", 9))
            nl.setStyleSheet(f"color: {C.PRIMARY};")
            self.param_lay.addWidget(nl, row, 0)

            if ps.description:
                dl = QLabel(ps.description)
                dl.setFont(QFont("Segoe UI", 8))
                dl.setStyleSheet(f"color: {C.TEXT_DIM};")
                self.param_lay.addWidget(dl, row, 1)

            if ps.type_hint == "int":
                w = QSpinBox()
                w.setRange(
                    int(ps.min_val) if ps.min_val is not None else -999999,
                    int(ps.max_val) if ps.max_val is not None else  999999)
                w.setValue(int(ps.default) if ps.default is not None else 0)
            elif ps.type_hint == "bool":
                w = QCheckBox()
                w.setChecked(bool(ps.default))
            elif ps.type_hint == "str":
                w = QLineEdit(str(ps.default) if ps.default is not None else "")
            else:   # float
                w = QDoubleSpinBox()
                w.setDecimals(4)
                w.setRange(
                    float(ps.min_val) if ps.min_val is not None else -1e9,
                    float(ps.max_val) if ps.max_val is not None else  1e9)
                w.setValue(float(ps.default) if ps.default is not None else 0.0)
                w.setSingleStep(1.0)

            self.param_lay.addWidget(w, row, 2)

            tl = QLabel(f"({ps.type_hint})")
            tl.setFont(QFont("Segoe UI", 8))
            tl.setStyleSheet(f"color: {C.TEXT_DIM};")
            self.param_lay.addWidget(tl, row, 3)

            self._param_widgets.append((ps.name, w))

    def _clear_calc_ui(self):
        self.calc_combo.clear()
        self.calc_desc_lbl.clear()
        while self.param_lay.count():
            item = self.param_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._param_widgets.clear()
        self.run_btn.setEnabled(False)
        self._selected_calc = None

    # ── run ──────────────────────────────────────────────────

    def _run_calculation(self):
        if not self._selected_calc:
            return
        calc = self._selected_calc
        kwargs = {}
        for pname, widget in self._param_widgets:
            if isinstance(widget, QCheckBox):
                kwargs[pname] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                kwargs[pname] = widget.text()
            elif isinstance(widget, QDoubleSpinBox):
                kwargs[pname] = widget.value()
            elif isinstance(widget, QSpinBox):
                kwargs[pname] = widget.value()

        self.output.append(f"\n{'─'*50}")
        self.output.append(f"▸ {calc.name}")
        self.output.append(f"  params: {kwargs}")
        self.output.append(f"{'─'*50}")
        self.run_btn.setEnabled(False)

        self._thread = QThread()
        self._worker = CalcWorker(calc.fn, kwargs)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_calc_done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_calc_done(self, result_text: str, error_text: str):
        self.run_btn.setEnabled(True)
        if error_text:
            self.output.append(f"ERROR:\n{error_text}")
        else:
            self.output.append(result_text if result_text else "(no output)")
        self.output.verticalScrollBar().setValue(
            self.output.verticalScrollBar().maximum())


# ═══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════

class SoulMusicGUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoulMusic — Test Control")
        self.setMinimumSize(1100, 750)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar ──
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background: {C.BG_MID};
                border-bottom: 1px solid {C.CARD_BORDER};
            }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)

        logo = QLabel("SOULMUSIC")
        logo.setFont(QFont("Consolas", 13, QFont.Bold))
        logo.setStyleSheet(f"color: {C.PRIMARY}; letter-spacing: 4px;")
        hl.addWidget(logo)

        hl.addStretch()

        version = QLabel("Dashboard  v1.1  |  9 tabs")
        version.setFont(QFont("Segoe UI", 8))
        version.setStyleSheet(f"color: {C.TEXT_DIM};")
        hl.addWidget(version)

        root.addWidget(header)

        # ── Tab widget ──
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tutorial_tab  = TutorialTab()
        self.test_tab     = TestSuiteTab()
        self.resonance_tab = ResonanceTab()
        self.beam_tab     = BeamformTab()
        self.platform_tab = PlatformTab()
        self.waveform_tab = WaveformTab()
        self.trophy_tab   = TrophyWallTab()
        self.module_tab   = ModuleLoaderTab()
        self.sysinfo_tab  = SystemInfoTab()

        self.tabs.addTab(self.tutorial_tab,  "GETTING STARTED")
        self.tabs.addTab(self.test_tab,       "TEST SUITE")
        self.tabs.addTab(self.resonance_tab,  "RESONANCE")
        self.tabs.addTab(self.beam_tab,       "BEAMFORMING")
        self.tabs.addTab(self.platform_tab,   "PLATFORMS")
        self.tabs.addTab(self.waveform_tab,   "WAVEFORMS")
        self.tabs.addTab(self.trophy_tab,     "TROPHY WALL")
        self.tabs.addTab(self.module_tab,     "MODULE LOADER")
        self.tabs.addTab(self.sysinfo_tab,    "SYSTEM INFO")

        root.addWidget(self.tabs, 1)

        # ── Status bar ──
        status = QFrame()
        status.setFixedHeight(26)
        status.setStyleSheet(f"""
            QFrame {{
                background: {C.BG_MID};
                border-top: 1px solid {C.CARD_BORDER};
            }}
        """)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(12, 0, 12, 0)

        self.status_label = QLabel(
            f"MEMS Profiles: {len(MEMS_PROFILES)}  ·  "
            f"Platforms: {len(PLATFORM_DB)}  ·  "
            f"Shell Presets: {len(SHELL_PRESETS)}  ·  "
            f"Tests: 10  ·  Tabs: 9")
        self.status_label.setFont(QFont("Segoe UI", 8))
        self.status_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        sl.addWidget(self.status_label)
        sl.addStretch()

        self.clock_label = QLabel()
        self.clock_label.setFont(QFont("Consolas", 8))  # monospace for clock
        self.clock_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        sl.addWidget(self.clock_label)

        root.addWidget(status)

        # Clock tick
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def _tick_clock(self):
        t = time.strftime("%H:%M:%S")
        self.clock_label.setText(t)


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)

    # Dark palette fallback for OS-native widgets
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(C.BG))
    palette.setColor(QPalette.WindowText, QColor(C.TEXT))
    palette.setColor(QPalette.Base, QColor(C.CARD_BG))
    palette.setColor(QPalette.Text, QColor(C.TEXT))
    palette.setColor(QPalette.Button, QColor(C.CARD_BG))
    palette.setColor(QPalette.ButtonText, QColor(C.PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(C.PRIMARY_DIM))
    palette.setColor(QPalette.HighlightedText, QColor(C.BG))
    app.setPalette(palette)

    window = SoulMusicGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
