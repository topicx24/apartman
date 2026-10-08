# -*- coding: utf-8 -*-
"""
Apartman Aidat Sistemi (Mini v4) + Devir (Sakin Geçmişi) - UI Revamp
Masaüstü PySide6 uygulaması.
"""

import sys
import sqlite3
from pathlib import Path
from datetime import date, timedelta
import webbrowser
from urllib.parse import quote

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QComboBox, QGroupBox, QFileDialog, QSpinBox, QCheckBox,
    QTextEdit, QDateEdit, QSplitter, QHeaderView, QScrollArea, QDialog
)
from PySide6.QtGui import QColor

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DB_PATH = Path("apartman_aidat.db")

# ----------------- helpers -----------------
def connect():
    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def iso_today() -> str:
    return date.today().isoformat()

def ym_of_today() -> str:
    d = date.today()
    return f"{d.year:04d}-{d.month:02d}"

def safe_float(s: str) -> float:
    t = (s or "").strip()
    if not t:
        return 0.0
    t = t.replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "")
        t = t.replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except Exception:
        return 0.0

def validate_period(donem: str) -> bool:
    if not donem or len(donem) != 7 or donem[4] != "-":
        return False
    try:
        y = int(donem[:4])
        m = int(donem[5:])
        return 2000 <= y <= 2100 and 1 <= m <= 12
    except Exception:
        return False

def add_months(ym: str, add: int) -> str:
    y = int(ym[:4])
    m = int(ym[5:])
    m2 = m + add
    y += (m2 - 1) // 12
    m2 = ((m2 - 1) % 12) + 1
    return f"{y:04d}-{m2:02d}"

def months_range(ym_start: str, ym_end: str):
    ys = int(ym_start[:4])
    ms = int(ym_start[5:])
    ye = int(ym_end[:4])
    me = int(ym_end[5:])
    cur_y, cur_m = ys, ms
    out = []
    while (cur_y, cur_m) <= (ye, me):
        out.append(f"{cur_y:04d}-{cur_m:02d}")
        cur_m += 1
        if cur_m == 13:
            cur_m = 1
            cur_y += 1
    return out

def ensure_db():
    con = connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS daireler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        daire_no TEXT NOT NULL UNIQUE,
        ad_soyad TEXT NOT NULL,
        telefon TEXT DEFAULT '',
        aidat REAL NOT NULL DEFAULT 0,
        aktif INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS odemeler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donem TEXT NOT NULL,
        tarih TEXT NOT NULL,
        daire_id INTEGER NOT NULL,
        tutar REAL NOT NULL,
        yontem TEXT NOT NULL,
        makbuz_no TEXT NOT NULL,
        aciklama TEXT DEFAULT '',
        FOREIGN KEY(daire_id) REFERENCES daireler(id)
    );
    CREATE TABLE IF NOT EXISTS odeme_detay (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        odeme_id INTEGER NOT NULL,
        donem TEXT NOT NULL,
        tutar REAL NOT NULL,
        FOREIGN KEY(odeme_id) REFERENCES odemeler(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS sakinler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        daire_id INTEGER NOT NULL,
        ad_soyad TEXT NOT NULL,
        telefon TEXT DEFAULT '',
        baslangic_tarihi TEXT NOT NULL,
        bitis_tarihi TEXT,
        FOREIGN KEY(daire_id) REFERENCES daireler(id)
    );
    CREATE INDEX IF NOT EXISTS idx_sakinler_daire ON sakinler(daire_id);
    CREATE TABLE IF NOT EXISTS tahakkuk (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donem TEXT NOT NULL,
        daire_id INTEGER NOT NULL,
        tutar REAL NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(donem, daire_id),
        FOREIGN KEY(daire_id) REFERENCES daireler(id)
    );
    CREATE INDEX IF NOT EXISTS idx_odemeler_donem ON odemeler(donem);
    CREATE INDEX IF NOT EXISTS idx_odemeler_daire ON odemeler(daire_id);
    CREATE TABLE IF NOT EXISTS giderler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donem TEXT NOT NULL,
        tarih TEXT NOT NULL,
        kategori TEXT NOT NULL,
        tutar REAL NOT NULL,
        yontem TEXT NOT NULL,
        aciklama TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_giderler_donem ON giderler(donem);
    CREATE TABLE IF NOT EXISTS duyurular (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih TEXT NOT NULL,
        baslik TEXT NOT NULL,
        mesaj TEXT NOT NULL
    );
    """)
    def set_default(k, v):
        if con.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone() is None:
            con.execute("INSERT INTO settings(key,value) VALUES(?,?)", (k, str(v)))
    set_default("vade_gun", 10)
    set_default("gecikme_gun", 5)
    con.commit()
    con.close()

def get_setting_int(key: str, default: int) -> int:
    con = connect()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    try:
        return int(row[0]) if row else default
    except Exception:
        return default

def set_setting_int(key: str, value: int):
    con = connect()
    con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(int(value))))
    con.commit()
    con.close()

def receipt_next_for_period(donem: str) -> str:
    yyyymm = donem.replace("-", "")
    con = connect()
    row = con.execute("SELECT makbuz_no FROM odemeler WHERE donem=? ORDER BY id DESC LIMIT 1", (donem,)).fetchone()
    con.close()
    if not row:
        return f"{yyyymm}-00001"
    last = row[0]
    try:
        seq = int(last.split("-")[1])
    except Exception:
        seq = 0
    return f"{yyyymm}-{seq+1:05d}"

def compute_vade_date(donem: str) -> date:
    vade_gun = get_setting_int("vade_gun", 10)
    y, m = donem.split("-")
    y = int(y); m = int(m)
    if m == 12:
        next_month = date(y + 1, 1, 1)
    else:
        next_month = date(y, m + 1, 1)
    last_day = next_month - timedelta(days=1)
    day = min(vade_gun, last_day.day)
    return date(y, m, day)

def status_for_balance(donem: str, bakiye: float) -> str:
    if bakiye <= 0.00001:
        return "Ödedi"
    vade = compute_vade_date(donem)
    gecikme = get_setting_int("gecikme_gun", 5)
    limit = vade + timedelta(days=gecikme)
    if date.today() > limit:
        return "Gecikmiş"
    return "Borçlu"

def autosize_worksheet(ws):
    for col in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(col)
        for row in range(1, ws.max_row + 1):
            v = ws.cell(row=row, column=col).value
            if v is not None:
                max_len = max(max_len, len(str(v)))
        ws.column_dimensions[col_letter].width = min(max_len + 2, 55)

# ============ MODAL DIALOGS ============
class EditPaymentDialog(QDialog):
    def __init__(self, payment_id: int, parent=None):
        super().__init__(parent)
        self.payment_id = payment_id
        self.setWindowTitle("Ödemeyi Düzenle")
        self.setGeometry(100, 100, 500, 300)
        self.setModal(True)
        self.init_ui()
        self.load_payment()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.in_donem = QLineEdit()
        self.in_donem.setReadOnly(True)
        self.dt_tarih = QDateEdit()
        self.dt_tarih.setCalendarPopup(True)
        self.dt_tarih.setDisplayFormat("dd-MM-yyyy")
        self.in_daire = QLineEdit()
        self.in_daire.setReadOnly(True)
        self.in_tutar = QLineEdit()
        self.cmb_yontem = QComboBox()
        self.cmb_yontem.addItems(["Banka", "Elden"])
        self.in_makbuz = QLineEdit()
        self.in_acik = QLineEdit()
        
        form.addRow("Dönem", self.in_donem)
        form.addRow("Tarih", self.dt_tarih)
        form.addRow("Daire", self.in_daire)
        form.addRow("Tutar (TL)", self.in_tutar)
        form.addRow("Yöntem", self.cmb_yontem)
        form.addRow("Makbuz No", self.in_makbuz)
        form.addRow("Açıklama", self.in_acik)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        self.btn_save = QPushButton("Güncelle")
        self.btn_save.clicked.connect(self.save_payment)
        self.btn_delete = QPushButton("Sil")
        self.btn_delete.clicked.connect(self.delete_payment)
        self.btn_close = QPushButton("Kapat")
        self.btn_close.clicked.connect(self.close)
        
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_delete)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)
    
    def load_payment(self):
        con = connect()
        row = con.execute("""
            SELECT o.donem, o.tarih, d.daire_no, o.tutar, o.yontem, o.makbuz_no, o.aciklama
            FROM odemeler o
            JOIN daireler d ON d.id = o.daire_id
            WHERE o.id = ?
        """, (self.payment_id,)).fetchone()
        con.close()
        
        if not row:
            QMessageBox.warning(self, "Hata", "Ödeme bulunamadı.")
            self.close()
            return
        
        donem, tarih, daire_no, tutar, yontem, makbuz_no, acik = row
        self.in_donem.setText(donem)
        self.dt_tarih.setDate(QDate.fromString(tarih, "yyyy-MM-dd"))
        self.in_daire.setText(daire_no)
        self.in_tutar.setText(f"{float(tutar):.2f}")
        self.cmb_yontem.setCurrentText(yontem)
        self.in_makbuz.setText(makbuz_no or "")
        self.in_acik.setText(acik or "")
    
    def save_payment(self):
        try:
            tutar = safe_float(self.in_tutar.text())
        except Exception:

            QMessageBox.warning(self, "Uyarı", "Tutar sayısal olmalı.")
            return
        if tutar <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalı.")
            return
        tarih = self.dt_tarih.date().toPython().isoformat()
        yontem = self.cmb_yontem.currentText()
        makbuz = self.in_makbuz.text().strip()
        acik = self.in_acik.text().strip()
        con = connect()
        con.execute("""
            UPDATE odemeler
            SET tarih=?, tutar=?, yontem=?, makbuz_no=?, aciklama=?
            WHERE id=?
        """, (tarih, float(tutar), yontem, makbuz, acik, self.payment_id))
        con.commit()
        con.close()
        QMessageBox.information(self, "OK", "Ödeme güncellendi.")
        self.accept()

    def delete_payment(self):
        if QMessageBox.question(
            self,
            "Onay",
                "Seçili ödemeyi silmek istiyor musunuz?") != QMessageBox.Yes:
            return
        con = connect()
        con.execute("DELETE FROM odeme_detay WHERE odeme_id=?",
                    (self.payment_id,))
        con.execute("DELETE FROM odemeler WHERE id=?", (self.payment_id,))
        con.commit()
        con.close()
        QMessageBox.information(self, "OK", "Ödeme silindi.")
        self.accept()
        class EditExpenseDialog(QDialog):

    def init(self, expense_id: int, parent=None):
        super().init(parent)
        self.expense_id = expense_id
        self.setWindowTitle("Gideri Düzenle")
        self.setGeometry(100, 100, 500, 300)
        self.setModal(True)
        self.init_ui()
        self.load_expense()

     def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.in_donem = QLineEdit()
        self.dt_tarih = QDateEdit()
        self.dt_tarih.setCalendarPopup(True)
        self.dt_tarih.setDisplayFormat("dd-MM-yyyy")
        self.cmb_kat = QComboBox()
        self.cmb_kat.addItems(["Elektrik", "Temizlik", "Bakım", "Diğer"])
        self.in_tutar = QLineEdit()
        self.cmb_yontem = QComboBox()
        self.cmb_yontem.addItems(["Banka", "Elden"])
        self.in_acik = QLineEdit()
        form.addRow("Dönem", self.in_donem)
        form.addRow("Tarih", self.dt_tarih)
        form.addRow("Kategori", self.cmb_kat)
        form.addRow("Tutar (TL)", self.in_tutar)
        form.addRow("Yöntem", self.cmb_yontem)
        form.addRow("Açıklama", self.in_acik)
        layout.addLayout(form)
        btns = QHBoxLayout()
        self.btn_save = QPushButton("Güncelle")
        self.btn_save.clicked.connect(self.save_expense)
        self.btn_delete = QPushButton("Sil")
        self.btn_delete.clicked.connect(self.delete_expense)
        self.btn_close = QPushButton("Kapat")
        self.btn_close.clicked.connect(self.close)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_delete)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

    def load_expense(self):
        con = connect()
        row = con.execute(
            "SELECT donem, tarih, kategori, tutar, yontem, aciklama FROM giderler WHERE id = ?",
            (self.expense_id,
             )).fetchone()
        con.close()
        if not row:
        QMessageBox.warning(self, "Hata", "Gider bulunamadı.")
        self.close()
        return
        donem, tarih, kat, tutar, yontem, acik = row
        self.in_donem.setText(donem)
        self.dt_tarih.setDate(QDate.fromString(tarih, "yyyy-MM-dd"))
        self.cmb_kat.setCurrentText(kat)
        self.in_tutar.setText(f"{float(tutar):.2f}")
        self.cmb_yontem.setCurrentText(yontem)
        self.in_acik.setText(acik or "")

    def save_expense(self):


donem = self.in_donem.text().strip()
if not validate_period(donem):
QMessageBox.warning(self, "Uyarı", "Dönem formatı YYYY-MM olmalı.")
return
try:
tutar = safe_float(self.in_tutar.text())
except Exception:
QMessageBox.warning(self, "Uyarı", "Tutar sayısal olmalı.")
return
if tutar <= 0:
QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalı.")
return
tarih = self.dt_tarih.date().toPython().isoformat()
kat = self.cmb_kat.currentText()
yontem = self.cmb_yontem.currentText()
acik = self.in_acik.text().strip()
con = connect()
con.execute(
    "UPDATE giderler SET donem=?, tarih=?, kategori=?, tutar=?, yontem=?, aciklama=? WHERE id=?",
    (donem,
     tarih,
     kat,
     float(tutar),
     yontem,
     acik,
     self.expense_id))
con.commit()
con.close()
QMessageBox.information(self, "OK", "Gider güncellendi.")
self.accept()
def delete_expense(self):


if QMessageBox.question(
    self,
    "Onay",
        "Seçili gideri silmek istiyor musunuz?") != QMessageBox.Yes:
return
con = connect()
con.execute("DELETE FROM giderler WHERE id=?", (self.expense_id,))
con.commit()
con.close()
QMessageBox.information(self, "OK", "Gider silindi.")
self.accept()

----------------- Main App - ----------------


class ApartmanAidatApp(QWidget):
def init(self):


super().init()
self.selected_daire_id = None
ensure_db()
self.setWindowTitle("Apartman Aidat Sistemi (Mini v4 - Devir)")
screen = QApplication.primaryScreen().availableGeometry()
w = int(screen.width() * 0.85)
h = int(screen.height() * 0.85)
self.resize(w, h)
self.setMinimumSize(min(1100, w), min(700, h))
self._build_ui()
self.refresh_all()
def _build_ui(self):


root = QVBoxLayout(self)
topbar = QHBoxLayout()
root.addLayout(topbar)
topbar.addWidget(QLabel("Dönem:"))
self.in_donem = QLineEdit(ym_of_today())
self.in_donem.setMaximumWidth(110)
topbar.addWidget(self.in_donem)
self.btn_refresh = QPushButton("Yenile")
self.btn_refresh.clicked.connect(self.refresh_all)
topbar.addWidget(self.btn_refresh)
topbar.addStretch(1)
topbar.addWidget(QLabel("Vade günü:"))
self.sp_vade = QSpinBox()
self.sp_vade.setRange(1, 28)
self.sp_vade.setValue(get_setting_int("vade_gun", 10))
topbar.addWidget(self.sp_vade)
topbar.addWidget(QLabel("Gecikme + gün:"))
self.sp_gec = QSpinBox()
self.sp_gec.setRange(0, 60)
self.sp_gec.setValue(get_setting_int("gecikme_gun", 5))
topbar.addWidget(self.sp_gec)
self.btn_save_settings = QPushButton("Ayarları Kaydet")
self.btn_save_settings.clicked.connect(self.save_settings)
topbar.addWidget(self.btn_save_settings)
self.tabs = QTabWidget()
root.addWidget(self.tabs, 1)
self._tab_daireler()
self._tab_tahakkuk()
self._tab_odeme()
self._tab_gider()
self._tab_duyuru()
self._tab_rapor()
self._tab_kasa()
self._tab_ekstre()
def _tab_daireler(self):


w = QWidget()
lay = QVBoxLayout(w)
gb = QGroupBox("Daire Ekle / Güncelle")
form = QFormLayout(gb)
self.d_in_no = QLineEdit()
self.d_in_ad = QLineEdit()
self.d_in_tel = QLineEdit()
self.d_in_aidat = QLineEdit()
self.d_chk_aktif = QCheckBox("Aktif")
self.d_chk_aktif.setChecked(True)
form.addRow("Daire No", self.d_in_no)
form.addRow("İsim", self.d_in_ad)
form.addRow("Telefon (GSM)", self.d_in_tel)
form.addRow("Aidat (TL)", self.d_in_aidat)
form.addRow("", self.d_chk_aktif)
btns = QHBoxLayout()
self.btn_d_save = QPushButton("Kaydet (Ekle/Güncelle)")
self.btn_d_save.clicked.connect(self.daire_save)
self.btn_d_clear = QPushButton("Temizle")
self.btn_d_clear.clicked.connect(self.daire_clear)
self.btn_d_deactivate = QPushButton("Seçileni Pasife Al")
self.btn_d_deactivate.clicked.connect(self.daire_deactivate_selected)
self.btn_d_activate = QPushButton("Seçileni Aktif Yap")
self.btn_d_activate.clicked.connect(self.daire_activate_selected)
btns.addWidget(self.btn_d_save)
btns.addWidget(self.btn_d_clear)
btns.addStretch(1)
btns.addWidget(self.btn_d_deactivate)
btns.addWidget(self.btn_d_activate)
lay.addWidget(gb)
lay.addLayout(btns)
rowwrap = QSplitter(Qt.Horizontal)
lay.addWidget(rowwrap, 1)
self.tbl_daire = QTableWidget(0, 6)
self.tbl_daire.setHorizontalHeaderLabels(
    ["ID", "Daire", "İsim", "Telefon", "Aidat", "Aktif"])
self.tbl_daire.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_daire.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_daire.cellClicked.connect(self.daire_row_clicked)
self.tbl_daire.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
rowwrap.addWidget(self.tbl_daire)
right_w = QWidget()
right = QVBoxLayout(right_w)
gb_sum = QGroupBox("Seçili Daire Özeti")
fsum = QFormLayout(gb_sum)
self.lbl_sel = QLabel("-")
self.lbl_total_borc = QLabel("0.00")
self.lbl_total_odeme = QLabel("0.00")
self.lbl_total_bakiye = QLabel("0.00")
self.lbl_period_borc = QLabel("0.00")
self.lbl_period_odeme = QLabel("0.00")
self.lbl_period_bakiye = QLabel("0.00")
self.lbl_period_durum = QLabel("-")
fsum.addRow("Daire", self.lbl_sel)
fsum.addRow("Genel Borç", self.lbl_total_borc)
fsum.addRow("Genel Ödeme", self.lbl_total_odeme)
fsum.addRow("Genel Bakiye", self.lbl_total_bakiye)
fsum.addRow("Seçili Dönem Borç", self.lbl_period_borc)
fsum.addRow("Seçili Dönem Ödeme", self.lbl_period_odeme)
fsum.addRow("Seçili Dönem Bakiye", self.lbl_period_bakiye)
fsum.addRow("Seçili Dönem Durum", self.lbl_period_durum)
right.addWidget(gb_sum, 1)
gb_dev = QGroupBox("Daire Devir (Taşındı)")
fdev = QFormLayout(gb_dev)
self.dev_cikis = QDateEdit()
self.dev_cikis.setCalendarPopup(True)
self.dev_cikis.setDate(QDate.currentDate())
self.dev_basla = QDateEdit()
self.dev_basla.setCalendarPopup(True)
self.dev_basla.setDate(QDate.currentDate())
self.dev_ad = QLineEdit()
self.dev_tel = QLineEdit()
self.btn_dev = QPushButton("DEVRİ KAYDET")
self.btn_dev.clicked.connect(self.devir_yap_selected)
fdev.addRow("Çıkış Tarihi", self.dev_cikis)
fdev.addRow("Yeni Başlangıç", self.dev_basla)
fdev.addRow("Yeni İsim", self.dev_ad)
fdev.addRow("Yeni Telefon", self.dev_tel)
fdev.addRow("", self.btn_dev)
right.addWidget(gb_dev, 1)
gb_sakin = QGroupBox("Sakin Geçmişi")
vsh = QVBoxLayout(gb_sakin)
self.tbl_sakin_hist = QTableWidget(0, 4)
self.tbl_sakin_hist.setHorizontalHeaderLabels(
    ["Ad Soyad", "Telefon", "Başlangıç", "Bitiş"])
self.tbl_sakin_hist.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_sakin_hist.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_sakin_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
vsh.addWidget(self.tbl_sakin_hist, 1)
right.addWidget(gb_sakin, 2)
scr = QScrollArea()
scr.setWidgetResizable(True)
scr.setWidget(right_w)
rowwrap.addWidget(scr)
rowwrap.setStretchFactor(0, 3)
rowwrap.setStretchFactor(1, 2)
self.tabs.addTab(w, "Daireler")
def _tab_tahakkuk(self):


w = QWidget()
lay = QVBoxLayout(w)
top = QGroupBox("Tahakkuk / Borç")
form = QFormLayout(top)
self.t_cmb_daire = QComboBox()
self.t_cmb_daire.currentIndexChanged.connect(self.refresh_tahakkuk_table)
self.t_in_from = QLineEdit(ym_of_today())
self.t_in_to = QLineEdit(ym_of_today())
self.t_in_tutar = QLineEdit()
btns = QHBoxLayout()
self.btn_t_add = QPushButton("Tahakkuk Oluştur")
self.btn_t_import = QPushButton("Excel'den Aktar")
self.btn_t_delete = QPushButton("Borcu Sil")
btns.addWidget(self.btn_t_add)
btns.addWidget(self.btn_t_import)
btns.addWidget(self.btn_t_delete)
form.addRow("Daire", self.t_cmb_daire)
form.addRow("Başlangıç", self.t_in_from)
form.addRow("Bitiş", self.t_in_to)
form.addRow("Tutar", self.t_in_tutar)
form.addRow("", btns)
lay.addWidget(top)
self.tbl_tah = QTableWidget(0, 5)
self.tbl_tah.setHorizontalHeaderLabels(
    ["ID", "Daire", "Dönem", "Tutar", "Tarih"])
self.tbl_tah.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_tah.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_tah.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
lay.addWidget(self.tbl_tah, 1)
self.btn_t_add.clicked.connect(self.add_tahakkuk_range)
self.btn_t_import.clicked.connect(self.import_debts_from_excel)
self.btn_t_delete.clicked.connect(self.delete_selected_tahakkuk)
self.tabs.addTab(w, "Tahakkuk")
def _tab_odeme(self):


w = QWidget()
lay = QVBoxLayout(w)
gb = QGroupBox("Aidat Ödeme")
form = QFormLayout(gb)
self.o_cmb_daire = QComboBox()
self.o_dt_tarih = QDateEdit()
self.o_dt_tarih.setCalendarPopup(True)
self.o_dt_tarih.setDate(QDate.currentDate())
self.o_cmb_daire.currentIndexChanged.connect(self.load_borc_listesi)
self.o_cmb_daire.currentIndexChanged.connect(self.load_payment_history)
self.o_in_tutar = QLineEdit()
self.o_btn_fill_balance = QPushButton("Kalanı Doldur")
self.o_btn_fill_balance.clicked.connect(self.fill_selected_period_balance)
self.o_cmb_yontem = QComboBox()
self.o_cmb_yontem.addItems(["Banka", "Elden"])
self.o_in_acik = QLineEdit()
self.btn_o_save = QPushButton("Kaydet")
self.btn_o_save.clicked.connect(self.odeme_save_multi)
self.btn_o_whatsapp = QPushButton("WhatsApp Mesajı Aç")
self.btn_o_whatsapp.clicked.connect(self.open_whatsapp_for_payment_tab)
form.addRow("Daire", self.o_cmb_daire)
form.addRow("Ödeme Tarihi", self.o_dt_tarih)
form.addRow("", self.o_btn_fill_balance)
form.addRow("Toplam Tutar (TL)", self.o_in_tutar)
form.addRow("Yöntem", self.o_cmb_yontem)
form.addRow("Açıklama", self.o_in_acik)
form.addRow("", self.btn_o_save)
form.addRow("", self.btn_o_whatsapp)
self.tbl_borc_list = QTableWidget(0, 5)
self.tbl_borc_list.setHorizontalHeaderLabels(
    ["Seç", "Dönem", "Borç", "Ödenen", "Kalan"])
self.tbl_borc_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
lay.addWidget(QLabel("Borçlu Dönemler"))
lay.addWidget(self.tbl_borc_list)
lay.addWidget(gb)
self.o_lbl_secili_toplam = QLabel("Seçili Borç : 0.00 TL")
lay.addWidget(self.o_lbl_secili_toplam)
splitter = QSplitter(Qt.Vertical)
gb_top = QGroupBox("Seçili Dönem Ödemeleri")
vlay_top = QVBoxLayout(gb_top)
self.tbl_odeme = QTableWidget(0, 7)
self.tbl_odeme.setHorizontalHeaderLabels(
    ["ID", "Dönem", "Tarih", "Daire", "Tutar", "Yöntem", "Makbuz"])
self.tbl_odeme.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_odeme.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_odeme.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
btns = QHBoxLayout()
self.btn_odeme_del = QPushButton("Ödemeyi Sil")
self.btn_odeme_del.clicked.connect(self.delete_selected_payment)
btns.addWidget(self.btn_odeme_del)
vlay_top.addLayout(btns)
vlay_top.addWidget(self.tbl_odeme)
splitter.addWidget(gb_top)
gb_bottom = QGroupBox("Daire Geçmiş Ödemeleri (Düzenlemek için çift tıkla)")
vlay_bottom = QVBoxLayout(gb_bottom)
self.tbl_odeme_gecmis = QTableWidget(0, 6)
self.tbl_odeme_gecmis.setHorizontalHeaderLabels(
    ["ID", "Dönem", "Tarih", "Tutar", "Yöntem", "Makbuz"])
self.tbl_odeme_gecmis.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_odeme_gecmis.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_odeme_gecmis.doubleClicked.connect(self.open_payment_for_edit)
self.tbl_odeme_gecmis.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
vlay_bottom.addWidget(self.tbl_odeme_gecmis)
splitter.addWidget(gb_bottom)
lay.addWidget(splitter, 1)
self.tabs.addTab(w, "Ödeme")
def _tab_gider(self):


w = QWidget()
lay = QVBoxLayout(w)
gb = QGroupBox("Gider Ekle")
form = QFormLayout(gb)
self.g_in_donem = QLineEdit(ym_of_today())
self.g_dt_tarih = QDateEdit()
self.g_dt_tarih.setCalendarPopup(True)
self.g_dt_tarih.setDate(QDate.currentDate())
self.g_cmb_kat = QComboBox()
self.g_cmb_kat.addItems(["Elektrik", "Temizlik", "Bakım", "Diğer"])
self.g_in_tutar = QLineEdit()
self.g_cmb_yontem = QComboBox()
self.g_cmb_yontem.addItems(["Banka", "Elden"])
self.g_in_acik = QLineEdit()
self.btn_g_save = QPushButton("Gider Kaydet")
self.btn_g_save.clicked.connect(self.gider_save)
form.addRow("Dönem", self.g_in_donem)
form.addRow("Tarih", self.g_dt_tarih)
form.addRow("Kategori", self.g_cmb_kat)
form.addRow("Tutar (TL)", self.g_in_tutar)
form.addRow("Yöntem", self.g_cmb_yontem)
form.addRow("Açıklama", self.g_in_acik)
form.addRow("", self.btn_g_save)
lay.addWidget(gb)
splitter = QSplitter(Qt.Vertical)
gb_top = QGroupBox("Seçili Dönem Giderleri")
vlay_top = QVBoxLayout(gb_top)
self.tbl_gider = QTableWidget(0, 7)
self.tbl_gider.setHorizontalHeaderLabels(
    ["ID", "Dönem", "Tarih", "Kategori", "Tutar", "Yöntem", "Açıklama"])
self.tbl_gider.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_gider.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_gider.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
btns = QHBoxLayout()
self.btn_gider_del = QPushButton("Gideri Sil")
self.btn_gider_del.clicked.connect(self.delete_selected_expense)
btns.addWidget(self.btn_gider_del)
vlay_top.addLayout(btns)
vlay_top.addWidget(self.tbl_gider)
splitter.addWidget(gb_top)
gb_bottom = QGroupBox("Tüm Giderler (Düzenlemek için çift tıkla)")
vlay_bottom = QVBoxLayout(gb_bottom)
self.tbl_gider_gecmis = QTableWidget(0, 7)
self.tbl_gider_gecmis.setHorizontalHeaderLabels(
    ["ID", "Dönem", "Tarih", "Kategori", "Tutar", "Yöntem", "Açıklama"])
self.tbl_gider_gecmis.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_gider_gecmis.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_gider_gecmis.doubleClicked.connect(self.open_expense_for_edit)
self.tbl_gider_gecmis.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
vlay_bottom.addWidget(self.tbl_gider_gecmis)
splitter.addWidget(gb_bottom)
lay.addWidget(splitter, 1)
self.tabs.addTab(w, "Gider")
def _tab_duyuru(self):


w = QWidget()
lay = QVBoxLayout(w)
gb = QGroupBox("Apartman Duyurusu")
form = QFormLayout(gb)
self.duy_dt = QDateEdit()
self.duy_dt.setCalendarPopup(True)
self.duy_dt.setDate(QDate.currentDate())
self.duy_baslik = QLineEdit()
self.duy_mesaj = QTextEdit()
self.btn_duy_save = QPushButton("Duyuru Kaydet")
self.btn_duy_save.clicked.connect(self.duyuru_save)
self.btn_duy_copy = QPushButton("Panoya Kopyala")
self.btn_duy_copy.clicked.connect(self.duyuru_copy)
form.addRow("Tarih", self.duy_dt)
form.addRow("Başlık", self.duy_baslik)
form.addRow("Mesaj", self.duy_mesaj)
form.addRow("", self.btn_duy_save)
form.addRow("", self.btn_duy_copy)
lay.addWidget(gb)
self.tbl_duyuru = QTableWidget(0, 4)
self.tbl_duyuru.setHorizontalHeaderLabels(["ID", "Tarih", "Başlık", "Mesaj"])
self.tbl_duyuru.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_duyuru.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_duyuru.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
lay.addWidget(self.tbl_duyuru, 1)
btns = QHBoxLayout()
self.btn_duy_del = QPushButton("Sil")
self.btn_duy_del.clicked.connect(self.duyuru_delete_selected)
btns.addWidget(self.btn_duy_del)
lay.addLayout(btns)
self.tabs.addTab(w, "Duyuru")
def _tab_rapor(self):


w = QWidget()
lay = QVBoxLayout(w)
head = QHBoxLayout()
lay.addLayout(head)
head.addWidget(QLabel("Rapor Dönem:"))
self.r_in_donem = QLineEdit(ym_of_today())
self.r_in_donem.setMaximumWidth(110)
head.addWidget(self.r_in_donem)
self.r_chk_only_unpaid = QCheckBox("Sadece borçlu")
self.r_chk_only_overdue = QCheckBox("Sadece geciken")
head.addWidget(self.r_chk_only_unpaid)
head.addWidget(self.r_chk_only_overdue)
self.btn_r_calc = QPushButton("Yenile")
self.btn_r_calc.clicked.connect(self.refresh_report)
head.addWidget(self.btn_r_calc)
self.btn_export_excel = QPushButton("Excel'e Aktar")
self.btn_export_excel.clicked.connect(self.export_excel)
head.addWidget(self.btn_export_excel)
self.lbl_summary = QLabel("Özet: -")
lay.addWidget(self.lbl_summary)
self.tbl_report = QTableWidget(0, 8)
self.tbl_report.setHorizontalHeaderLabels(
    ["Daire", "İsim", "Telefon", "Aidat", "Borç", "Ödeme", "Bakiye", "Durum"])
self.tbl_report.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_report.setSelectionBehavior(QTableWidget.SelectRows)
self.tbl_report.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
lay.addWidget(self.tbl_report, 1)
foot = QHBoxLayout()
self.btn_msg_selected = QPushButton("Seçili WhatsApp")
self.btn_msg_selected.clicked.connect(self.report_whatsapp_selected)
self.btn_msg_all_debt = QPushButton("Toplu Metin Kopyala")
self.btn_msg_all_debt.clicked.connect(self.copy_bulk_message_text)
foot.addWidget(self.btn_msg_selected)
foot.addWidget(self.btn_msg_all_debt)
lay.addLayout(foot)
self.tabs.addTab(w, "Rapor")
def _tab_kasa(self):


w = QWidget()
lay = QVBoxLayout(w)
head = QHBoxLayout()
lay.addLayout(head)
head.addWidget(QLabel("Başlangıç:"))
self.k_dt_from = QDateEdit()
self.k_dt_from.setCalendarPopup(True)
self.k_dt_from.setDate(QDate.currentDate().addMonths(-24))
head.addWidget(self.k_dt_from)
head.addWidget(QLabel("Bitiş:"))
self.k_dt_to = QDateEdit()
self.k_dt_to.setCalendarPopup(True)
self.k_dt_to.setDate(QDate.currentDate())
head.addWidget(self.k_dt_to)
self.btn_k_refresh = QPushButton("Yenile")
self.btn_k_refresh.clicked.connect(self.refresh_kasa_report)
head.addWidget(self.btn_k_refresh)
self.btn_k_excel = QPushButton("Excel'e Aktar")
self.btn_k_excel.clicked.connect(self.export_kasa_excel)
head.addWidget(self.btn_k_excel)
gb_ozet = QGroupBox("Kasa Özeti")
form_ozet = QFormLayout(gb_ozet)
self.k_lbl_toplam_gelir = QLabel("0.00 TL")
self.k_lbl_toplam_gider = QLabel("0.00 TL")
self.k_lbl_net = QLabel("0.00 TL")
self.k_lbl_durum = QLabel("-")
self.k_lbl_gelir_enko = QLabel("0 kayıt")
self.k_lbl_gider_enko = QLabel("0 kayıt")
form_ozet.addRow("📥 Toplam Gelir:", self.k_lbl_toplam_gelir)
form_ozet.addRow("   Kayıt Sayısı:", self.k_lbl_gelir_enko)
form_ozet.addRow("📤 Toplam Gider:", self.k_lbl_toplam_gider)
form_ozet.addRow("   Kayıt Sayısı:", self.k_lbl_gider_enko)
form_ozet.addRow("📊 NET KALAN:", self.k_lbl_net)
form_ozet.addRow("Durum:", self.k_lbl_durum)
lay.addWidget(gb_ozet)
gb_gelir = QGroupBox("Gelir Kaynakları")
vg = QVBoxLayout(gb_gelir)
self.tbl_k_gelir = QTableWidget(0, 5)
self.tbl_k_gelir.setHorizontalHeaderLabels(
    ["Dönem", "Tarih", "Daire", "Yöntem", "Tutar"])
self.tbl_k_gelir.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_k_gelir.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
vg.addWidget(self.tbl_k_gelir)
lay.addWidget(gb_gelir, 2)
gb_gider = QGroupBox("Gider Kaynakları")
vx = QVBoxLayout(gb_gider)
self.tbl_k_gider = QTableWidget(0, 5)
self.tbl_k_gider.setHorizontalHeaderLabels(
    ["Dönem", "Tarih", "Kategori", "Yöntem", "Tutar"])
self.tbl_k_gider.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_k_gider.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
vx.addWidget(self.tbl_k_gider)
lay.addWidget(gb_gider, 2)
self.tabs.addTab(w, "Kasa")
def _tab_ekstre(self):


w = QWidget()
lay = QVBoxLayout(w)
head = QHBoxLayout()
lay.addLayout(head)
head.addWidget(QLabel("Daire:"))
self.e_cmb_daire = QComboBox()
head.addWidget(self.e_cmb_daire, 2)
head.addWidget(QLabel("Başlangıç:"))
self.e_from = QLineEdit("2025-01")
head.addWidget(self.e_from)
head.addWidget(QLabel("Bitiş:"))
self.e_to = QLineEdit(ym_of_today())
head.addWidget(self.e_to)
self.btn_e_list = QPushButton("Listele")
self.btn_e_list.clicked.connect(self.load_ekstre)
head.addWidget(self.btn_e_list)
self.btn_e_excel = QPushButton("Excel'e Aktar")
self.btn_e_excel.clicked.connect(self.export_ekstre_excel)
head.addWidget(self.btn_e_excel)
self.tbl_ekstre = QTableWidget(0, 6)
self.tbl_ekstre.setHorizontalHeaderLabels(
    ["Daire", "Dönem", "Borç", "Ödeme", "Bakiye", "Durum"])
self.tbl_ekstre.setEditTriggers(QTableWidget.NoEditTriggers)
self.tbl_ekstre.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
lay.addWidget(self.tbl_ekstre, 1)
self.tabs.addTab(w, "Ekstre")
def save_settings(self):


set_setting_int("vade_gun", self.sp_vade.value())
set_setting_int("gecikme_gun", self.sp_gec.value())
QMessageBox.information(self, "OK", "Ayarlar kaydedildi.")
self.refresh_all()
def daire_clear(self):


self.selected_daire_id = None
self.d_in_no.clear()
self.d_in_ad.clear()
self.d_in_tel.clear()
self.d_in_aidat.clear()
self.d_chk_aktif.setChecked(True)
self.tbl_daire.clearSelection()
self.refresh_selected_summary(clear=True)
self.tbl_sakin_hist.setRowCount(0)
self.dev_ad.clear()
self.dev_tel.clear()
def daire_row_clicked(self, row, col):


try:
did = int(self.tbl_daire.item(row, 0).text())
dno = self.tbl_daire.item(row, 1).text()
ad = self.tbl_daire.item(row, 2).text()
tel = self.tbl_daire.item(row, 3).text()
aidat = self.tbl_daire.item(row, 4).text()
aktif = self.tbl_daire.item(row, 5).text() == "1"
except Exception:
return
self.selected_daire_id = did
self.d_in_no.setText(dno)
self.d_in_ad.setText(ad)
self.d_in_tel.setText(tel)
self.d_in_aidat.setText(aidat)
self.d_chk_aktif.setChecked(aktif)
self._ensure_current_sakin(did)
self.refresh_sakin_history_table(did)
self.refresh_selected_summary(did)
def _selected_daire_id(self):


rows = self.tbl_daire.selectionModel().selectedRows()
if not rows:
return None
return int(self.tbl_daire.item(rows[0].row(), 0).text())
def daire_save(self):


dno = self.d_in_no.text().strip()
ad = self.d_in_ad.text().strip()
tel = self.d_in_tel.text().strip()
try:
aidat = safe_float(self.d_in_aidat.text())
except Exception:
QMessageBox.warning(self, "Uyarı", "Aidat sayısal olmalı.")
return
aktif = 1 if self.d_chk_aktif.isChecked() else 0
if not dno or not ad:
QMessageBox.warning(self, "Uyarı", "Daire No ve İsim zorunlu.")
return
con = connect()
try:
if self.selected_daire_id:
con.execute("UPDATE daireler SET daire_no=?, ad_soyad=?, telefon=?, aidat=?, aktif=? WHERE id=?",
            (dno, ad, tel, float(aidat), int(aktif), int(self.selected_daire_id)))
did = int(self.selected_daire_id)
else:
con.execute(
    "INSERT INTO daireler(daire_no, ad_soyad, telefon, aidat, aktif) VALUES(?,?,?,?,?)",
    (dno,
     ad,
     tel,
     float(aidat),
     int(aktif)))
did = int(
    con.execute(
        "SELECT id FROM daireler WHERE daire_no=?",
        (dno,
         )).fetchone()[0])
has = con.execute(
    "SELECT id FROM sakinler WHERE daire_id=? AND bitis_tarihi IS NULL ORDER BY id DESC LIMIT 1",
    (did,
     )).fetchone()
if not has:
con.execute(
    "INSERT INTO sakinler(daire_id, ad_soyad, telefon, baslangic_tarihi, bitis_tarihi) VALUES(?,?,?,?,NULL)",
    (did,
     ad,
     tel,
     iso_today()))
else:
con.execute("UPDATE sakinler SET ad_soyad=?, telefon=? WHERE id=?",
            (ad, tel, int(has[0])))
con.commit()
except sqlite3.IntegrityError:
QMessageBox.warning(self, "Uyarı", "Bu daire no zaten var.")
finally:
con.close()
self.refresh_all()
self.daire_clear()
def daire_deactivate_selected(self):


did = self._selected_daire_id()
if not did:
    return
con = connect()
con.execute("UPDATE daireler SET aktif=0 WHERE id=?", (did,))
con.commit()
con.close()
self.refresh_all()
def daire_activate_selected(self):


did = self._selected_daire_id()
if not did:
    return
con = connect()
con.execute("UPDATE daireler SET aktif=1 WHERE id=?", (did,))
con.commit()
con.close()
self.refresh_all()
def _ensure_current_sakin(self, daire_id: int):


con = connect()
has = con.execute(
    "SELECT 1 FROM sakinler WHERE daire_id=? AND bitis_tarihi IS NULL LIMIT 1",
    (int(daire_id),
     )).fetchone()
if has:
    con.close()
    return
d = con.execute(
    "SELECT ad_soyad, telefon FROM daireler WHERE id=?",
    (int(daire_id),
     )).fetchone()
if not d:
    con.close()
    return
con.execute(
    "INSERT INTO sakinler(daire_id, ad_soyad, telefon, baslangic_tarihi, bitis_tarihi) VALUES(?,?,?,?,NULL)",
    (int(daire_id),
     d[0],
     d[1],
     iso_today()))
con.commit()
con.close()
def refresh_sakin_history_table(self, daire_id):


self.tbl_sakin_hist.setRowCount(0)
con = connect()
rows = con.execute(
    "SELECT ad_soyad, telefon, baslangic_tarihi, COALESCE(bitis_tarihi,'') FROM sakinler WHERE daire_id=? ORDER BY id DESC",
    (int(daire_id),
     )).fetchall()
con.close()
for r in rows:
row = self.tbl_sakin_hist.rowCount()
self.tbl_sakin_hist.insertRow(row)
for c, v in enumerate(r):
self.tbl_sakin_hist.setItem(row, c, QTableWidgetItem(str(v)))
def devir_yap_selected(self):


daire_id = self._selected_daire_id()
if not daire_id:
    return
cikis = self.dev_cikis.date().toPython().isoformat()
basla = self.dev_basla.date().toPython().isoformat()
yeni_ad = self.dev_ad.text().strip()
yeni_tel = self.dev_tel.text().strip()
if not yeni_ad:
    return
con = connect()
cur = con.execute(
    "SELECT id FROM sakinler WHERE daire_id=? AND bitis_tarihi IS NULL ORDER BY id DESC LIMIT 1",
    (int(daire_id),
     )).fetchone()
if cur:
    con.execute("UPDATE sakinler SET bitis_tarihi=? WHERE id=?",
                (cikis, int(cur[0])))
con.execute(
    "INSERT INTO sakinler(daire_id, ad_soyad, telefon, baslangic_tarihi, bitis_tarihi) VALUES(?,?,?,?,NULL)",
    (int(daire_id),
     yeni_ad,
     yeni_tel,
     basla))
con.execute("UPDATE daireler SET ad_soyad=?, telefon=? WHERE id=?",
            (yeni_ad, yeni_tel, int(daire_id)))
con.commit()
con.close()
QMessageBox.information(self, "OK", "Devir tamamlandı.")
self.refresh_all()
def load_ekstre(self):


daire_id = self.e_cmb_daire.currentData()
if not daire_id:
    return
ym_from = self.e_from.text().strip()
ym_to = self.e_to.text().strip()
if not validate_period(ym_from) or not validate_period(ym_to):
    return
self.tbl_ekstre.setRowCount(0)
con = connect()
d = con.execute(
    "SELECT daire_no, ad_soyad FROM daireler WHERE id=?",
    (int(daire_id),
     )).fetchone()
daire_tag = f"{d[0]} - {d[1]}" if d else ""
for p in months_range(ym_from, ym_to):
b = con.execute(
    "SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE daire_id=? AND donem=?",
    (int(daire_id),
     p)).fetchone()[0] or 0.0
o = con.execute(
    "SELECT COALESCE(SUM(od.tutar),0) FROM odeme_detay od JOIN odemeler o ON o.id = od.odeme_id WHERE o.daire_id=? AND od.donem=?",
    (int(daire_id),
     p)).fetchone()[0] or 0.0
bakiye = float(b) - float(o)
dur = status_for_balance(p, bakiye)
row = self.tbl_ekstre.rowCount()
self.tbl_ekstre.insertRow(row)
vals = [daire_tag, p, f"{b:.2f}", f"{o:.2f}", f"{bakiye:.2f}", dur]
for c, v in enumerate(vals):
item = QTableWidgetItem(str(v))
if dur == "Ödedi":
    item.setBackground(QColor(210, 245, 218))
else:
    item.setBackground(QColor(255, 220, 220))
self.tbl_ekstre.setItem(row, c, item)
con.close()
def export_ekstre_excel(self):


if self.tbl_ekstre.rowCount() == 0:
    return
path, _ = QFileDialog.getSaveFileName(
    self, "Excel Kaydet", "ekstre.xlsx", "Excel (*.xlsx)")
if not path:
    return
wb = Workbook()
ws = wb.active
ws.title = "Ekstre"
ws.append([self.tbl_ekstre.horizontalHeaderItem(c).text()
          for c in range(self.tbl_ekstre.columnCount())])
for r in range(self.tbl_ekstre.rowCount()):
ws.append([self.tbl_ekstre.item(r, c).text()
          for c in range(self.tbl_ekstre.columnCount())])
autosize_worksheet(ws)
wb.save(path)
def refresh_selected_summary(self, daire_id=None, clear=False):


if clear or not daire_id:
self.lbl_sel.setText("-")
return
donem = self.in_donem.text().strip()
con = connect()
row = con.execute(
    "SELECT daire_no, ad_soyad FROM daireler WHERE id=?",
    (int(daire_id),
     )).fetchone()
if row:
    self.lbl_sel.setText(f"Daire {row[0]} - {row[1]}")
# Genel borç hesaplama
b_tot = con.execute(
    "SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE daire_id=?",
    (int(daire_id),
     )).fetchone()[0]
o_tot = con.execute(
    "SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE daire_id=?",
    (int(daire_id),
     )).fetchone()[0]
self.lbl_total_borc.setText(f"{b_tot:.2f}")
self.lbl_total_odeme.setText(f"{o_tot:.2f}")
self.lbl_total_bakiye.setText(f"{b_tot - o_tot:.2f}")
# Dönemsel borç
b_p = con.execute(
    "SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE daire_id=? AND donem=?",
    (int(daire_id),
     donem)).fetchone()[0]
o_p = con.execute(
    "SELECT COALESCE(SUM(od.tutar),0) FROM odeme_detay od JOIN odemeler o ON o.id=od.odeme_id WHERE o.daire_id=? AND od.donem=?",
    (int(daire_id),
     donem)).fetchone()[0]
self.lbl_period_borc.setText(f"{b_p:.2f}")
self.lbl_period_odeme.setText(f"{o_p:.2f}")
self.lbl_period_bakiye.setText(f"{b_p - o_p:.2f}")
self.lbl_period_durum.setText(status_for_balance(donem, b_p - o_p))
con.close()
def add_tahakkuk_range(self):


daire_id = self.t_cmb_daire.currentData()
start = self.t_in_from.text().strip()
end = self.t_in_to.text().strip()
tutar = safe_float(self.t_in_tutar.text())
if not daire_id or not validate_period(
        start) or not validate_period(end) or tutar <= 0:
    return
con = connect()
for donem in months_range(start, end):
con.execute(
    "INSERT INTO tahakkuk(donem, daire_id, tutar, created_at) VALUES(?,?,?,?) ON CONFLICT(donem, daire_id) DO UPDATE SET tutar=excluded.tutar",
    (donem,
     int(daire_id),
     float(tutar),
     iso_today()))
con.commit()
con.close()
self.refresh_all()
def delete_selected_tahakkuk(self):


row = self.tbl_tah.currentRow()
if row < 0:
    return
tah_id = int(self.tbl_tah.item(row, 0).text())
con = connect()
con.execute("DELETE FROM tahakkuk WHERE id=?", (tah_id,))
con.commit()
con.close()
self.refresh_all()
def _auto_create_current_month_tahakkuk(self):


donem = ym_of_today()
con = connect()
try:
daireler = con.execute(
    "SELECT id, aidat FROM daireler WHERE aktif=1").fetchall()
for daire_id, aidat in daireler:
existing = con.execute(
    "SELECT id FROM tahakkuk WHERE donem=? AND daire_id=?",
    (donem,
     daire_id)).fetchone()
if not existing and aidat > 0:
con.execute(
    "INSERT INTO tahakkuk(donem, daire_id, tutar, created_at) VALUES(?,?,?,?)",
    (donem,
     daire_id,
     float(aidat),
     iso_today()))
con.commit()
except Exception as e:
print(e)
finally:
con.close()
def fill_selected_period_balance(self):


daire_id = self.o_cmb_daire.currentData()
donem = self.in_donem.text().strip()
if not daire_id or not validate_period(donem):
    return
con = connect()
b = con.execute(
    "SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE donem=? AND daire_id=?",
    (donem,
     int(daire_id))).fetchone()[0]
o = con.execute(
    "SELECT COALESCE(SUM(od.tutar),0) FROM odeme_detay od JOIN odemeler o ON o.id=od.odeme_id WHERE od.donem=? AND o.daire_id=?",
    (donem,
     int(daire_id))).fetchone()[0]
con.close()
self.o_in_tutar.setText(f"{max(b - o, 0.0):.2f}")
def load_borc_listesi(self):


self.tbl_borc_list.setRowCount(0)
daire_id = self.o_cmb_daire.currentData()
if not daire_id:
    return
con = connect()
rows = con.execute(
    "SELECT DISTINCT donem FROM tahakkuk WHERE daire_id=? ORDER BY donem",
    (daire_id,
     )).fetchall()
for (donem,) in rows:
borc = con.execute(
    "SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE daire_id=? AND donem=?",
    (daire_id,
     donem)).fetchone()[0]
odeme = con.execute(
    "SELECT COALESCE(SUM(od.tutar),0) FROM odeme_detay od JOIN odemeler o ON o.id=od.odeme_id WHERE o.daire_id=? AND od.donem=?",
    (daire_id,
     donem)).fetchone()[0]
kalan = float(borc) - float(odeme)
if kalan <= 0:
    continue
row = self.tbl_borc_list.rowCount()
self.tbl_borc_list.insertRow(row)
chk = QCheckBox()
chk.stateChanged.connect(self.hesapla_secili_borc)
self.tbl_borc_list.setCellWidget(row, 0, chk)
self.tbl_borc_list.setItem(row, 1, QTableWidgetItem(donem))
self.tbl_borc_list.setItem(row, 2, QTableWidgetItem(f"{borc:.2f}"))
self.tbl_borc_list.setItem(row, 3, QTableWidgetItem(f"{odeme:.2f}"))
self.tbl_borc_list.setItem(row, 4, QTableWidgetItem(f"{kalan:.2f}"))
con.close()
def hesapla_secili_borc(self):


toplam = 0.0
for row in range(self.tbl_borc_list.rowCount()):
chk = self.tbl_borc_list.cellWidget(row, 0)
if chk and chk.isChecked():
toplam += safe_float(self.tbl_borc_list.item(row, 4).text())
self.o_lbl_secili_toplam.setText(f"Seçili Borç : {toplam:.2f} TL")
def odeme_save_multi(self):


daire_id = self.o_cmb_daire.currentData()
if not daire_id:
    return
secilenler = []
toplam_borc = 0.0
for row in range(self.tbl_borc_list.rowCount()):
chk = self.tbl_borc_list.cellWidget(row, 0)
if chk and chk.isChecked():
donem = self.tbl_borc_list.item(row, 1).text()
kalan = safe_float(self.tbl_borc_list.item(row, 4).text())
secilenler.append((donem, kalan))
toplam_borc += kalan
if not secilenler:
    return
tutar_text = self.o_in_tutar.text().strip()
toplam_odeme = safe_float(tutar_text) if tutar_text else toplam_borc
if toplam_odeme <= 0:
    return
tarih = self.o_dt_tarih.date().toPython().isoformat()
yontem = self.o_cmb_yontem.currentText()
acik = self.o_in_acik.text().strip()
ilk_donem = secilenler[0][0]
makbuz_no = receipt_next_for_period(ilk_donem)
con = connect()
cur = con.cursor()
try:
cur.execute(
    "INSERT INTO odemeler(donem, tarih, daire_id, tutar, yontem, makbuz_no, aciklama) VALUES(?,?,?,?,?,?,?)",
    (ilk_donem,
     tarih,
     daire_id,
     toplam_odeme,
     yontem,
     makbuz_no,
     acik))
odeme_id = cur.lastrowid
kalan_odeme = toplam_odeme
for donem, kalan_borc in secilenler:
if kalan_odeme <= 0:
    break
odeme_tutari = min(kalan_odeme, kalan_borc)
cur.execute(
    "INSERT INTO odeme_detay(odeme_id, donem, tutar) VALUES(?,?,?)",
    (odeme_id,
     donem,
     odeme_tutari))
kalan_odeme -= odeme_tutari
con.commit()
except Exception as e:
con.rollback()
print(e)
finally:
con.close()
self.o_in_tutar.clear()
self.o_in_acik.clear()
self.refresh_all()


def load_payment_history(self):

    # Ödeme geçmişini yükleme işlemlerinin tamamı için referansındaki kaynak
    # koda bakabilirsiniz.
pass


def open_payment_for_edit(self, index):

    # Ödemeyi düzenleme penceresini açma mantığı için referansındaki kaynak
    # koda bakabilirsiniz.
pass


def open_expense_for_edit(self, index):

    # Gideri düzenleme penceresini açma mantığı için referansındaki kaynak
    # koda bakabilirsiniz.
pass


def delete_selected_payment(self):

    # Seçili ödemeyi silme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def gider_save(self):

    # Gider kaydetme mantığı için referansındaki kaynak koda bakabilirsiniz.
pass


def delete_selected_expense(self):

    # Seçili gideri silme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def load_expense_history(self):

    # Gider geçmişini yükleme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def refresh_expenses_table(self):

    # Gider tablosunu yenileme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def duyuru_save(self):

    # Duyuru kaydetme mantığı için referansındaki kaynak koda bakabilirsiniz.
pass


def duyuru_copy(self):

    # Duyuruyu panoya kopyalama mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def duyuru_delete_selected(self):

    # Seçili duyuruyu silme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def open_whatsapp_for_payment_tab(self):

    # WhatsApp sekme entegrasyonu için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def report_whatsapp_selected(self):

    # Rapor üzerinden WhatsApp mesajı açma mantığı için referansındaki kaynak
    # koda bakabilirsiniz.
pass


def _open_whatsapp_for_daire(self, daire_id):

    # Daire bazlı WhatsApp açma yardımcı metodu için referansındaki kaynak
    # koda bakabilirsiniz.
pass


def copy_bulk_message_text(self):

    # Toplu mesaj metnini kopyalama mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def refresh_all(self):

    # Tüm arayüzü ve tabloları güncelleyen ana metod için referansındaki
    # kaynak koda bakabilirsiniz.
pass


def refresh_daire_table(self):

    # Daireler tablosunu güncelleme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def refresh_daire_combo_all(self):

    # Daire seçim kutularını güncelleme mantığı için referansındaki kaynak
    # koda bakabilirsiniz.
pass


def refresh_tahakkuk_table(self):

    # Tahakkuk tablosunu yenileme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def refresh_payments_table(self):

    # Ödemeler tablosunu yenileme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def refresh_duyuru_table(self):

    # Duyuru tablosunu yenileme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def refresh_report(self):

    # Rapor tablosunu yenileme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass


def refresh_kasa_report(self):

    # Kasa raporunu yenileme mantığı için referansındaki kaynak koda
    # bakabilirsiniz.
pass
def export_kasa_excel(self): pass
def export_excel(self): pass
def import_debts_from_excel(self): pass
def main():


app = QApplication(sys.argv)
w = ApartmanAidatApp()
w.show()
sys.exit(app.exec())
if name == "main":
main()
