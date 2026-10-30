from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QGroupBox, QComboBox, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from db_manager import DbManager
from finance_service import validate_period, safe_float, iso_today, status_for_balance


class GiderRaporWidget(QWidget):
    def __init__(self, db: DbManager):
        super().__init__()
        self.db = db
        self.build_ui()
        self.refresh_expense_table()
        self.refresh_report()

    def build_ui(self):
        root = QVBoxLayout(self)

        # ---------- Gider ekleme ----------
        gb_gider = QGroupBox("Giderler")
        gbox = QVBoxLayout(gb_gider)

        gform = QFormLayout()
        self.g_donem = QLineEdit()
        self.g_donem.setText(iso_today()[:7])
        self.g_tarih = QLineEdit(iso_today())
        self.g_kategori = QComboBox()
        self.g_kategori.addItems(["Elektrik", "Temizlik", "Bakım", "Diğer"])

        self.g_tutar = QLineEdit()
        self.g_yontem = QComboBox()
        self.g_yontem.addItems(["Banka", "Elden"])
        self.g_aciklama = QLineEdit()

        self.btn_gider_save = QPushButton("Gider Kaydet")
        self.btn_gider_save.clicked.connect(self.save_expense)

        gform.addRow("Dönem (YYYY-MM)", self.g_donem)
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
        gbox.addWidget(self.tbl_gider)

        root.addWidget(gb_gider)

        # ---------- Rapor ----------
        gb_rapor = QGroupBox("Yıllık Raporlama Yönetimi")
        rbox = QVBoxLayout(gb_rapor)

        rtop = QHBoxLayout()
        self.r_yil = QLineEdit(iso_today()[:4])  # Sadece Yıl girişi (Örn: 2026)
        self.r_yil.setPlaceholderText("YYYY")
        self.r_only_unpaid = QComboBox()
        self.r_only_unpaid.addItems(["Hepsi", "Sadece borçlu", "Sadece geciken"])
        self.btn_rapor = QPushButton("Yıllık Raporu Yenile")
        self.btn_rapor.clicked.connect(self.refresh_report)

        rtop.addWidget(QLabel("Rapor Yılı:"))
        rtop.addWidget(self.r_yil)
        rtop.addWidget(QLabel("Filtre:"))
        rtop.addWidget(self.r_only_unpaid)
        rtop.addWidget(self.btn_rapor)
        rbox.addLayout(rtop)

        self.lbl_summary = QLabel("Yıllık Özet: -")
        self.lbl_summary.setStyleSheet("font-weight: bold; padding: 5px; background-color: #eef2f3; border-radius: 4px;")
        rbox.addWidget(self.lbl_summary)

        self.tbl_rapor = QTableWidget(0, 8)
        self.tbl_rapor.setHorizontalHeaderLabels([
            "Daire", "Ad Soyad", "Telefon", "Yıllık Aidat Şablonu",
            "Toplam Borç", "Toplam Ödeme", "Kalan Borç", "Durum"
        ])
        self.tbl_rapor.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_rapor.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rbox.addWidget(self.tbl_rapor)

        root.addWidget(gb_rapor)

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
        self.refresh_report()

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

    def refresh_report(self):
        yil = self.r_yil.text().strip()
        if len(yil) != 4 or not yil.isdigit():
            QMessageBox.warning(self, "Uyarı", "Geçerli bir yıl formatı giriniz (YYYY).")
            return

        start_date = f"{yil}-01-01"
        end_date = f"{yil}-12-31"

        con = self.db.connect()
        rows = con.execute("""
            SELECT id, daire_no, ad_soyad, telefon, aidat, aktif
            FROM daireler
            ORDER BY CAST(daire_no AS INTEGER), daire_no
        """).fetchall()

        summary = {"gelir": 0.0, "gider": 0.0, "net": 0.0, "borc": 0.0}
        out_rows = []

        # Yıllık bazda tüm ayları simüle etmek veya toplamak için döngü oluşturuluyor
        for daire_id, daire_no, ad, tel, aidat, aktif in rows:
            toplam_daire_borc = 0.0
            toplam_daire_odeme = 0.0
            
            # Yılın 12 ayı için daire finansal durumları hesaplanıyor
            for m in range(1, 13):
                donem_str = f"{yil}-{m:02d}"
                borc, odeme, bakiye = self.db.get_balance_for_period(int(daire_id), donem_str)
                toplam_daire_borc += borc
                toplam_daire_odeme += odeme

            toplam_daire_kalan = toplam_daire_borc - toplam_daire_odeme
            durum = "Ödendi" if toplam_daire_kalan <= 0 else "Gecikmiş"

            if self.r_only_unpaid.currentText() == "Sadece borçlu" and toplam_daire_kalan <= 0:
                continue
            if self.r_only_unpaid.currentText() == "Sadece geciken" and durum != "Gecikmiş":
                continue

            out_rows.append({
                "daire_no": daire_no,
                "ad": ad,
                "tel": tel,
                "aidat": aidat,
                "period_borc": toplam_daire_borc,
                "period_odeme": toplam_daire_odeme,
                "period_bakiye": toplam_daire_kalan,
                "durum": durum
            })
            summary["borc"] += toplam_daire_kalan

        # Belirtilen yıl aralığındaki tüm genel gelir ve gider tahsilatları toplanıyor
        gelir = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE tarih >= ? AND tarih <= ?", (start_date, end_date)).fetchone()[0] or 0.0
        gider = con.execute("SELECT COALESCE(SUM(tutar),0) FROM giderler WHERE tarih >= ? AND tarih <= ?", (start_date, end_date)).fetchone()[0] or 0.0
        summary["gelir"] = float(gelir)
        summary["gider"] = float(gider)
        summary["net"] = summary["gelir"] - summary["gider"]

        con.close()

        self.lbl_summary.setText(
            f"{yil} Yılı Genel Toplamı | Toplam Gelir: {summary['gelir']:.2f} TL | "
            f"Toplam Gider: {summary['gider']:.2f} TL | "
            f"Yıl İçi Net Kalan: {summary['net']:.2f} TL | "
            f"Dairelerin Kalan Birikmiş Borcu: {summary['borc']:.2f} TL"
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
                r["durum"]
            ]

            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c in (3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if r["period_bakiye"] > 0:
                    item.setBackground(QColor(255, 230, 230))
                else:
                    item.setBackground(QColor(230, 255, 235))
                self.tbl_rapor.setItem(row, c, item)
