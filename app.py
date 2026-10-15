# app.py
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QDialog, QTextEdit, QFileDialog,
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
        self.setWindowTitle("Apartman Aidat Sistemi - Sekmeli Yönetim")
        self.resize(1100, 780)
        self.build_ui()
        self.refresh_all()

    def build_ui(self):
        # Top-level tabs
        self.tabs = QTabWidget()
        outer = QVBoxLayout(self)
        outer.addWidget(self.tabs)

        # Yönetim paneli: will contain sub-tabs for Daireler, Tahakkuk, Ödeme, Gider, Rapor
        main_panel = QWidget()
        main_layout = QVBoxLayout(main_panel)

        # create inner tab widget
        self.main_tabs = QTabWidget()
        main_layout.addWidget(self.main_tabs)

        # --- Daireler tab ---
        tab_daire = QWidget()
        d_layout = QVBoxLayout(tab_daire)

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

        d_layout.addLayout(form)

        self.tbl_daire = QTableWidget(0, 6)
        self.tbl_daire.setHorizontalHeaderLabels(["ID", "Daire", "İsim", "Telefon", "Aidat", "Aktif"])
        self.tbl_daire.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_daire.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_daire.setMinimumHeight(140)
        d_layout.addWidget(self.tbl_daire)

        self.main_tabs.addTab(tab_daire, "Daireler")

        # --- Tahakkuk tab ---
        tab_tahakkuk = QWidget()
        t_layout = QVBoxLayout(tab_tahakkuk)

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

        t_layout.addLayout(gh)
        self.main_tabs.addTab(tab_tahakkuk, "Tahakkuk")

        # --- Ödeme tab ---
        tab_odeme = QWidget()
        o_layout = QVBoxLayout(tab_odeme)

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

        o_layout.addLayout(op)

        # borç tablosu shown in payment tab
        self.tbl_borc = QTableWidget(0, 3)
        self.tbl_borc.setHorizontalHeaderLabels(["Dönem", "Borç", "Kalan"])
        self.tbl_borc.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_borc.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_borc.setMinimumHeight(120)
        o_layout.addWidget(self.tbl_borc)

        self.main_tabs.addTab(tab_odeme, "Ödeme")

        # --- Gider tab ---
        tab_gider = QWidget()
        g_layout = QVBoxLayout(tab_gider)

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

        g_layout.addWidget(gb_gider)
        self.main_tabs.addTab(tab_gider, "Gider")

        # --- Rapor tab ---
        tab_rapor = QWidget()
        r_layout = QVBoxLayout(tab_rapor)

        rpt_top = QHBoxLayout()
        self.r_donem = QLineEdit(ym_of_today())
        self.r_only_unpaid = QComboBox()
        self.r_only_unpaid.addItems(["Hepsi", "Sadece borçlu", "Sadece geciken"])
        self.btn_rapor = QPushButton("Raporu Yenile")
        self.btn_rapor.clicked.connect(self.refresh_report)

        rpt_top.addWidget(QLabel("Dönem"))
        rpt_top.addWidget(self.r_donem)
        rpt_top.addWidget(QLabel("Filtre"))
        rpt_top.addWidget(self.r_only_unpaid)
        rpt_top.addWidget(self.btn_rapor)
        r_layout.addLayout(rpt_top)

        self.lbl_summary = QLabel("Özet: -")
        self.lbl_summary.setStyleSheet("font-weight: bold;")
        r_layout.addWidget(self.lbl_summary)

        self.tbl_rapor = QTableWidget(0, 8)
        self.tbl_rapor.setHorizontalHeaderLabels([
            "Daire", "Ad Soyad", "Telefon", "Aidat",
            "Borç", "Ödeme", "Kalan", "Durum"
        ])
        self.tbl_rapor.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_rapor.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_rapor.setMinimumHeight(220)
        self.tbl_rapor.itemDoubleClicked.connect(self.on_report_item_double_clicked)
        r_layout.addWidget(self.tbl_rapor)

        self.main_tabs.addTab(tab_rapor, "Rapor")

        # add main_panel as first-level tab
        # put it into a scroll area to allow whole main_panel scrolling on small screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(main_panel)
        self.tabs.addTab(scroll, "Yönetim Paneli")

        # other top-level tabs
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

        summary = {"gelir": 0.0, "gider": 0.0, "net": 0.0, "borc": 0.0}
        out_rows = []

        for daire_id, daire_no, ad, tel, aidat, aktif in rows:
            borc, odeme, bakiye = self.db.get_balance_for_period(int(daire_id), donem)
            durum = status_for_balance(donem, bakiye)

            if self.r_only_unpaid.currentText() == "Sadece borçlu" and bakiye <= 0:
                continue
            if self.r_only_unpaid.currentText() == "Sadece geciken" and durum != "Gecikmiş":
                continue

            out_rows.append((daire_id, daire_no, ad, tel, aidat, borc, odeme, bakiye, durum))
            summary["borc"] += borc

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
        for daire_id, daire_no, ad, tel, aidat, borc, odeme, bakiye, durum in out_rows:
            row = self.tbl_rapor.rowCount()
            self.tbl_rapor.insertRow(row)

            # store daire_id in the first column item user data for double-click detail
            item0 = QTableWidgetItem(str(daire_no))
            item0.setData(Qt.UserRole, int(daire_id))
            self.tbl_rapor.setItem(row, 0, item0)

            vals = [
                str(daire_no),
                ad,
                tel,
                f"{float(aidat):.2f}",
                f"{float(borc):.2f}",
                f"{float(odeme):.2f}",
                f"{float(bakiye):.2f}",
                durum,
            ]

            for c, val in enumerate(vals):
                if c == 0:
                    continue
                item = QTableWidgetItem(str(val))
                if c in (3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if bakiye > 0:
                    item.setBackground(QColor(255, 200, 200))
                else:
                    item.setBackground(QColor(200, 255, 205))
                self.tbl_rapor.setItem(row, c, item)

    def on_report_item_double_clicked(self, item):
        # get row and daire_id from first column
        row = item.row()
        id_item = self.tbl_rapor.item(row, 0)
        if not id_item:
            return
        daire_id = id_item.data(Qt.UserRole)
        if not daire_id:
            return

        # fetch debt periods
        periods = self.db.get_all_debt_periods(int(daire_id))
        total = sum(p[1] for p in periods) if periods else 0.0

        # build detail dialog with a table and copy/pdf buttons
        dlg = QDialog(self)
        dlg.setWindowTitle("Borç Detayları")
        dlg.setMinimumSize(480, 360)
        lay = QVBoxLayout(dlg)

        # total label
        lbl_total = QLabel(f"Toplam Borç: {total:.2f} TL")
        if total > 0:
            lbl_total.setStyleSheet("font-size:16px; font-weight:bold; color: #c0392b;")
        else:
            lbl_total.setStyleSheet("font-size:16px; font-weight:bold; color: #27ae60;")
        lay.addWidget(lbl_total)

        # periods table
        tbl = QTableWidget(0, 2)
        tbl.setHorizontalHeaderLabels(["Dönem", "Kalan (TL)"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        for donem, kalan in periods:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem(str(donem)))
            item_amt = QTableWidgetItem(f"{float(kalan):.2f}")
            item_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tbl.setItem(r, 1, item_amt)
        lay.addWidget(tbl)

        # buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_copy = QPushButton("Kopyala")
        btn_pdf = QPushButton("PDF Kaydet")
        btn_close = QPushButton("Kapat")
        btn_row.addWidget(btn_copy)
        btn_row.addWidget(btn_pdf)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

        def do_copy():
            s = f"Toplam Borç: {total:.2f} TL\n\nDönemler:\n"
            if periods:
                for d, k in periods:
                    s += f"{d}\t{float(k):.2f} TL\n"
            else:
                s += "Borç yok.\n"
            QApplication.clipboard().setText(s)
            QMessageBox.information(dlg, "Kopyalandı", "Borç detayları panoya kopyalandı.")

        def do_pdf():
            path, _ = QFileDialog.getSaveFileName(dlg, "PDF Kaydet", f"borc_{daire_id}.pdf", "PDF Files (*.pdf)")
            if not path:
                return
            try:
                # use QPdfWriter + QPainter to render simple text
                from PySide6.QtGui import QPdfWriter, QPainter, QFont
                pdf = QPdfWriter(path)
                pdf.setPageOrientation(pdf.Portrait)
                pdf.setPageSizeMM(pdf.pageSizeMM())
                painter = QPainter(pdf)
                font = QFont("Times", 12)
                painter.setFont(font)
                x = 50
                y = 50
                painter.drawText(x, y, f"Borç Detayları - Daire ID: {daire_id}")
                y += 30
                painter.drawText(x, y, f"Toplam Borç: {total:.2f} TL")
                y += 30
                if periods:
                    for donem, kalan in periods:
                        painter.drawText(x, y, f"{donem}: {float(kalan):.2f} TL")
                        y += 20
                else:
                    painter.drawText(x, y, "Borç yok.")
                painter.end()
                QMessageBox.information(dlg, "Kaydedildi", f"PDF kaydedildi: {path}")
            except Exception as e:
                QMessageBox.warning(dlg, "Hata", f"PDF oluşturulamadı: {e}")

        btn_copy.clicked.connect(do_copy)
        btn_pdf.clicked.connect(do_pdf)
        btn_close.clicked.connect(dlg.accept)

        dlg.exec()

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
