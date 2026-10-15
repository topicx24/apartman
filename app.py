# app.py
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from db_manager import DbManager
from finance_service import validate_period, safe_float, ym_of_today, iso_today, status_for_balance

from gider_rapor import GiderRaporWidget
from kasa_export import KasaExportWidget


class ApartmanAidatApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DbManager()
        self.db.init_db()
        self.setWindowTitle("Apartman Aidat Sistemi - Temiz Sürüm")
        self.resize(1100, 780)
        self.build_ui()
        self.refresh_all()

    def build_ui(self):
        self.tabs = QTabWidget()
        outer = QVBoxLayout(self)
        outer.addWidget(self.tabs)

        main_tab = QWidget()
        main_content = QWidget()
        root = QVBoxLayout(main_content)

        title = QLabel("Apartman Aidat Sistemi")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        # ---------- Daire form ----------
        form = QFormLayout()
        self.daire_no = QLineEdit()
        self.daire_ad = QLineEdit()
        self.daire_tel = QLineEdit()
        self.daire_aidat = QLineEdit()
        self.daire_aidat.setPlaceholderText("Örn: 400")

        self.btn_save_daire = QPushButton("Daire Kaydet")
        self.btn_save_daire.clicked.connect(self.save_daire)

        form.addRow("Daire No", self.daire_no)
        form.addRow("Ad Soyad", self.daire_ad)
        form.addRow("Telefon", self.daire_tel)
        form.addRow("Aidat (TL)", self.daire_aidat)
        form.addRow("", self.btn_save_daire)

        root.addLayout(form)

        self.tbl_daire = QTableWidget(0, 6)
        self.tbl_daire.setHorizontalHeaderLabels(["ID", "Daire", "İsim", "Telefon", "Aidat", "Aktif"])
        self.tbl_daire.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_daire.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_daire.setMinimumHeight(140)
        root.addWidget(self.tbl_daire)

        # ---------- Tahakkuk ----------
        gh = QHBoxLayout()
        self.t_daire_combo = QComboBox()
        self.t_daire_combo.currentIndexChanged.connect(self.refresh_borc_table)
        self.t_from = QLineEdit(ym_of_today())
        self.t_to = QLineEdit(ym_of_today())
        self.t_tutar = QLineEdit()
        self.t_tutar.setPlaceholderText("400")

        self.btn_tahakkuk = QPushButton("Tahakkuk Oluştur")
        self.btn_tahakkuk.clicked.connect(self.create_tahakkuk)

        gh.addWidget(QLabel("Daire:"))
        gh.addWidget(self.t_daire_combo)
        gh.addWidget(QLabel("Başlangıç"))
        gh.addWidget(self.t_from)
        gh.addWidget(QLabel("Bitiş"))
        gh.addWidget(self.t_to)
        gh.addWidget(QLabel("Tutar"))
        gh.addWidget(self.t_tutar)
        gh.addWidget(self.btn_tahakkuk)

        root.addLayout(gh)

        # ---------- Ödeme ----------
        op = QHBoxLayout()
        self.p_daire_combo = QComboBox()
        self.p_daire_combo.currentIndexChanged.connect(self.refresh_borc_table)
        self.p_donem = QLineEdit(ym_of_today())
        self.p_tutar = QLineEdit()
        self.p_yontem = QComboBox()
        self.p_yontem.addItems(["Banka", "Elden"])

        self.btn_fill_balance = QPushButton("Kalanı Doldur")
        self.btn_fill_balance.clicked.connect(self.fill_balance_for_period)

        self.btn_save_payment = QPushButton("Ödemeyi Kaydet")
        self.btn_save_payment.clicked.connect(self.save_payment_quick)

        op.addWidget(QLabel("Daire:"))
        op.addWidget(self.p_daire_combo)
        op.addWidget(QLabel("Dönem"))
        op.addWidget(self.p_donem)
        op.addWidget(QLabel("Tutar"))
        op.addWidget(self.p_tutar)
        op.addWidget(self.p_yontem)
        op.addWidget(self.btn_fill_balance)
        op.addWidget(self.btn_save_payment)

        root.addLayout(op)

        # ---------- Borç tabelası ----------
        self.tbl_borc = QTableWidget(0, 3)
        self.tbl_borc.setHorizontalHeaderLabels(["Dönem", "Borç", "Kalan"])
        self.tbl_borc.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_borc.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_borc.setMinimumHeight(120)
        root.addWidget(self.tbl_borc)

        # ---------- Gider ----------
        gb_gider = QGroupBox("Giderler")
        gbox = QVBoxLayout(gb_gider)

        gform = QFormLayout()
        self.g_donem = QLineEdit(ym_of_today())
        self.g_tarih = QLineEdit(iso_today())
        self.g_kategori = QComboBox()
        self.g_kategori.addItems(["Elektrik", "Temizlik", "Bakım", "Diğer"])
        self.g_tutar = QLineEdit()
        self.g_yontem = QComboBox()
        self.g_yontem.addItems(["Banka", "Elden"])
        self.g_aciklama = QLineEdit()

        self.btn_gider_save = QPushButton("Gider Kaydet")
        self.btn_gider_save.clicked.connect(self.save_expense)

        gform.addRow("Dönem", self.g_donem)
        gform.addRow("Tarih (yyyy-mm-dd)", self.g_tarih)
        gform.addRow("Kategori", self.g_kategori)
        gform.addRow("Tutar (TL)", self.g_tutar)
        gform.addRow("Yöntem", self.g_yontem)
        gform.addRow("Açıklama", self.g_aciklama)
        gform.addRow("", self.btn_gider_save)

        gbox.addLayout(gform)

        self.tbl_gider = QTableWidget(0, 7)
        self.tbl_gider.setHorizontalHeaderLabels(["ID", "Dönem", "Tarih", "Kategori", "Tutar", "Yöntem", "Açıklama"])
        self.tbl_gider.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_gider.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_gider.setMaximumHeight(220)
        gbox.addWidget(self.tbl_gider)
        root.addWidget(gb_gider)

        # ---------- Rapor ----------
        gb_rapor = QGroupBox("Rapor")
        rbox = QVBoxLayout(gb_rapor)

        rtop = QHBoxLayout()
        self.r_donem = QLineEdit(ym_of_today())
        self.r_only_unpaid = QComboBox()
        self.r_only_unpaid.addItems(["Hepsi", "Sadece borçlu", "Sadece geciken"])
        self.btn_rapor = QPushButton("Raporu Yenile")
        self.btn_rapor.clicked.connect(self.refresh_report)

        rtop.addWidget(QLabel("Dönem"))
        rtop.addWidget(self.r_donem)
        rtop.addWidget(QLabel("Filtre"))
        rtop.addWidget(self.r_only_unpaid)
        rtop.addWidget(self.btn_rapor)
        rbox.addLayout(rtop)

        self.lbl_summary = QLabel("Özet: -")
        self.lbl_summary.setStyleSheet("font-weight: bold;")
        rbox.addWidget(self.lbl_summary)

        self.tbl_rapor = QTableWidget(0, 8)
        self.tbl_rapor.setHorizontalHeaderLabels([
            "Daire", "Ad Soyad", "Telefon", "Aidat",
            "Borç", "Ödeme", "Kalan", "Durum"
        ])
        self.tbl_rapor.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_rapor.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_rapor.setMinimumHeight(220)
        rbox.addWidget(self.tbl_rapor)

        root.addWidget(gb_rapor)

        refresh_row = QHBoxLayout()
        self.btn_refresh_all = QPushButton("Yenile")
        self.btn_refresh_all.clicked.connect(self.refresh_all)
        refresh_row.addStretch()
        refresh_row.addWidget(self.btn_refresh_all)
        root.addLayout(refresh_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(main_content)

        self.tabs.addTab(scroll, "Yönetim Paneli")
        self.gider_rapor = GiderRaporWidget(self.db)
        self.tabs.addTab(self.gider_rapor, "Gider & Rapor")
        self.kasa_widget = KasaExportWidget(self.db)
        self.tabs.addTab(self.kasa_widget, "Kasa")

    # ----------------- Daire işlemleri -----------------
    def save_daire(self):
        dno = self.daire_no.text().strip()
        ad = self.daire_ad.text().strip()
        tel = self.daire_tel.text().strip()
        try:
            aidat = safe_float(self.daire_aidat.text())
        except Exception:
            QMessageBox.warning(self, "Uyarı", "Aidat sayısal olmalı.")
            return

        if not dno or not ad:
            QMessageBox.warning(self, "Uyarı", "Daire No ve İsim zorunlu.")
            return

        did = self.db.add_or_update_daire(dno, ad, tel, aidat, 1)
        QMessageBox.information(self, "OK", f"Daire kaydedildi. ID={did}")
        self.daire_no.clear()
        self.daire_ad.clear()
        self.daire_tel.clear()
        self.daire_aidat.clear()
        self.refresh_all()

    def refresh_daire_table(self):
        rows = self.db.get_all_daireler()
        self.tbl_daire.setRowCount(0)

        self.t_daire_combo.clear()
        self.p_daire_combo.clear()

        self.t_daire_combo.addItem("-- seç --", -1)
        self.p_daire_combo.addItem("-- seç --", -1)

        for r in rows:
            row = self.tbl_daire.rowCount()
            self.tbl_daire.insertRow(row)
            for c, v in enumerate(r):
                self.tbl_daire.setItem(row, c, QTableWidgetItem(str(v)))

            did, dno, ad, tel, aidat, aktif = r
            display = f"Daire {dno} - {ad}"
            self.t_daire_combo.addItem(display, did)
            self.p_daire_combo.addItem(display, did)

    # ----------------- Tahakkuk işlemleri -----------------
    def create_tahakkuk(self):
        daire_id = self.t_daire_combo.currentData()
        if daire_id in (-1, None):
            QMessageBox.warning(self, "Uyarı", "Daire seçin.")
            return

        start = self.t_from.text().strip()
        end = self.t_to.text().strip()
        if not validate_period(start) or not validate_period(end):
            QMessageBox.warning(self, "Uyarı", "Dönem formatı YYYY-MM olmalı.")
            return

        if start > end:
            QMessageBox.warning(self, "Uyarı", "Başlangıç dönemi bitişten büyük olamaz.")
            return

        try:
            tutar = safe_float(self.t_tutar.text())
        except Exception:
            QMessageBox.warning(self, "Uyarı", "Tutar sayısal olmalı.")
            return

        if tutar <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalı.")
            return

        adet = self.db.add_tahakkuk_range(int(daire_id), start, end, tutar)
        QMessageBox.information(self, "OK", f"{adet} döneme tahakkuk kaydedildi.")
        self.t_tutar.clear()
        self.refresh_all()

    # ----------------- Ödeme işlemleri -----------------
    def fill_balance_for_period(self):
        daire_id = self.p_daire_combo.currentData()
        if daire_id in (-1, None):
            QMessageBox.warning(self, "Uyarı", "Daire seçin.")
            return

        donem = self.p_donem.text().strip()
        if not validate_period(donem):
            QMessageBox.warning(self, "Uyarı", "Dönem formatı YYYY-MM olmalı.")
            return

        borc, odeme, bakiye = self.db.get_balance_for_period(int(daire_id), donem)
        if bakiye <= 0:
            self.p_tutar.clear()
            QMessageBox.information(self, "Bilgi", "Bu dönemde kalan borç yok.")
            return

        self.p_tutar.setText(f"{bakiye:.2f}")

    def save_payment_quick(self):
        daire_id = self.p_daire_combo.currentData()
        if daire_id in (-1, None):
            QMessageBox.warning(self, "Uyarı", "Daire seçin.")
            return

        donem = self.p_donem.text().strip()
        if not validate_period(donem):
            QMessageBox.warning(self, "Uyarı", "Dönem formatı YYYY-MM olmalı.")
            return

        try:
            tutar = safe_float(self.p_tutar.text())
        except Exception:
            QMessageBox.warning(self, "Uyarı", "Tutar sayısal olmalı.")
            return

        if tutar <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalı.")
            return

        due = self.db.get_all_debt_periods(int(daire_id))
        if not due:
            borc, odeme, bakiye = self.db.get_balance_for_period(int(daire_id), donem)
            if bakiye > 0:
                due = [(donem, bakiye)]
            else:
                QMessageBox.information(self, "Bilgi", "Bu dairenin borcu yok.")
                return

        allocations = DbManager.allocate_payment(tutar, due)
        if not allocations:
            QMessageBox.warning(self, "Uyarı", "Dağıtım yapılamadı.")
            return

        yontem = self.p_yontem.currentText()
        tarih = iso_today()
        aciklama = f"Hızlı ödeme: {donem}"
        makbuz = self.db.save_payment(int(daire_id), allocations, tarih, yontem, aciklama)

        QMessageBox.information(self, "OK", f"Ödeme kaydedildi.\nMakbuz: {makbuz}")
        self.p_tutar.clear()
        self.refresh_all()

    # ----------------- Borç tablosu -----------------
    def refresh_borc_table(self):
        daire_id = self.p_daire_combo.currentData()
        self.tbl_borc.setRowCount(0)

        if daire_id in (-1, None):
            return

        rows = self.db.get_all_debt_periods(int(daire_id))
        if not rows:
            return

        for donem, kalan in rows:
            row = self.tbl_borc.rowCount()
            self.tbl_borc.insertRow(row)
            self.tbl_borc.setItem(row, 0, QTableWidgetItem(str(donem)))
            self.tbl_borc.setItem(row, 1, QTableWidgetItem(f"{kalan:.2f}"))
            self.tbl_borc.setItem(row, 2, QTableWidgetItem(f"{kalan:.2f}"))

    # ----------------- Gider işlemleri -----------------
    def save_expense(self):
        donem = self.g_donem.text().strip()
        if not validate_period(donem):
            QMessageBox.warning(self, "Uyarı", "Dönem formatı YYYY-MM olmalı.")
            return

        tarih = self.g_tarih.text().strip()
        kat = self.g_kategori.currentText()
        try:
            tutar = safe_float(self.g_tutar.text())
        except Exception:
            QMessageBox.warning(self, "Uyarı", "Tutar sayısal olmalı.")
            return
        if tutar <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalı.")
            return

        yontem = self.g_yontem.currentText()
        aciklama = self.g_aciklama.text().strip()

        con = self.db.connect()
        try:
            con.execute("""
                INSERT INTO giderler(donem, tarih, kategori, tutar, yontem, aciklama)
                VALUES(?,?,?,?,?,?)
            """, (donem, tarih, kat, float(tutar), yontem, aciklama))
            con.commit()
        finally:
            con.close()

        QMessageBox.information(self, "OK", "Gider kaydedildi.")
        self.g_tutar.clear()
        self.g_aciklama.clear()
        self.refresh_expense_table()

    def refresh_expense_table(self):
        con = self.db.connect()
        rows = con.execute("""
            SELECT id, donem, tarih, kategori, tutar, yontem, aciklama
            FROM giderler
            ORDER BY tarih DESC, id DESC
        """).fetchall()
        con.close()

        self.tbl_gider.setRowCount(0)
        for rid, donem, tarih, kat, tutar, yontem, aciklama in rows:
            row = self.tbl_gider.rowCount()
            self.tbl_gider.insertRow(row)
            vals = [str(rid), donem, tarih, kat, f"{float(tutar):.2f}", yontem, aciklama or ""]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tbl_gider.setItem(row, c, item)

    # ----------------- Rapor işlemleri -----------------
    def refresh_report(self):
        donem = self.r_donem.text().strip()
        if not validate_period(donem):
            QMessageBox.warning(self, "Uyarı", "Dönem formatı YYYY-MM olmalı.")
            return

        con = self.db.connect()
        rows = con.execute("""
            SELECT id, daire_no, ad_soyad, telefon, aidat, aktif
            FROM daireler
            ORDER BY CAST(daire_no AS INTEGER), daire_no
        """).fetchall()

        summary = {
            "gelir": 0.0,
            "gider": 0.0,
            "net": 0.0,
            "borc": 0.0,
        }

        out_rows = []
        for daire_id, daire_no, ad, tel, aidat, aktif in rows:
            borc, odeme, bakiye = self.db.get_balance_for_period(int(daire_id), donem)
            summary["borc"] += borc

            durum = status_for_balance(donem, bakiye)
            if self.r_only_unpaid.currentText() == "Sadece borçlu" and bakiye <= 0:
                continue
            if self.r_only_unpaid.currentText() == "Sadece geciken" and durum != "Gecikmiş":
                continue

            out_rows.append({
                "daire_no": daire_no,
                "ad": ad,
                "tel": tel,
                "aidat": aidat,
                "period_borc": borc,
                "period_odeme": odeme,
                "period_bakiye": bakiye,
                "durum": durum,
            })

        gelir = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE donem=?", (donem,)).fetchone()[0] or 0.0
        gider = con.execute("SELECT COALESCE(SUM(tutar),0) FROM giderler WHERE donem=?", (donem,)).fetchone()[0] or 0.0
        summary["gelir"] = float(gelir)
        summary["gider"] = float(gider)
        summary["net"] = summary["gelir"] - summary["gider"]

        con.close()

        self.lbl_summary.setText(
            f"{donem} | Gelir: {summary['gelir']:.2f} TL | "
            f"Gider: {summary['gider']:.2f} TL | "
            f"Net: {summary['net']:.2f} TL | "
            f"Toplam Borç: {summary['borc']:.2f} TL"
        )

        self.tbl_rapor.setRowCount(0)
        for r in out_rows:
            row = self.tbl_rapor.rowCount()
            self.tbl_rapor.insertRow(row)
            vals = [
                r["daire_no"],
                r["ad"],
                r["tel"],
                f"{float(r['aidat']):.2f}",
                f"{float(r['period_borc']):.2f}",
                f"{float(r['period_odeme']):.2f}",
                f"{float(r['period_bakiye']):.2f}",
                r["durum"],
            ]

            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c in (3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if r["period_bakiye"] > 0:
                    item.setBackground(QColor(255, 200, 200))
                else:
                    item.setBackground(QColor(200, 255, 205))
                self.tbl_rapor.setItem(row, c, item)

    def refresh_all(self):
        self.refresh_daire_table()
        self.refresh_expense_table()
        self.refresh_borc_table()
        self.refresh_report()


def main():
    app = QApplication([])
    window = ApartmanAidatApp()
    window.show()
    app.exec()
