from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QDateEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from openpyxl import Workbook

from db_manager import DbManager


class KasaExportWidget(QWidget):
    def __init__(self, db: DbManager):
        super().__init__()
        self.db = db
        self.build_ui()
        
        # Varsayılan olarak içinde bulunulan yılın başını ve sonunu ayarla
        current_year = QDate.currentDate().year()
        self.k_from.setDate(QDate(current_year, 1, 1))
        self.k_to.setDate(QDate(current_year, 12, 31))
        
        self.refresh_kasa_report()

    def build_ui(self):
        root = QVBoxLayout(self)

        head = QHBoxLayout()
        head.addWidget(QLabel("Başlangıç:"))
        self.k_from = QDateEdit()
        self.k_from.setCalendarPopup(True)
        self.k_from.setDisplayFormat("dd-MM-yyyy")
        head.addWidget(self.k_from)

        head.addWidget(QLabel("Bitiş:"))
        self.k_to = QDateEdit()
        self.k_to.setCalendarPopup(True)
        self.k_to.setDisplayFormat("dd-MM-yyyy")
        head.addWidget(self.k_to)

        self.btn_refresh = QPushButton("Yenile")
        self.btn_refresh.clicked.connect(self.refresh_kasa_report)
        head.addWidget(self.btn_refresh)

        self.btn_excel = QPushButton("Excel'e Aktar")
        self.btn_excel.clicked.connect(self.export_kasa_excel)
        head.addWidget(self.btn_excel)

        head.addStretch()
        root.addLayout(head)

        # Gelişmiş Özet Paneli (Alt Kasa ve Devir Destekli)
        gb_ozet = QGroupBox("Gelişmiş Yıllık Kasa Özeti")
        form_ozet = QFormLayout(gb_ozet)

        self.k_lbl_devir_bakiye = QLabel("0.00 TL")
        self.k_lbl_toplam_gelir = QLabel("0.00 TL")
        self.k_lbl_toplam_gider = QLabel("0.00 TL")
        self.k_lbl_banka_kasa = QLabel("0.00 TL")
        self.k_lbl_elden_kasa = QLabel("0.00 TL")
        self.k_lbl_net = QLabel("0.00 TL")
        self.k_lbl_durum = QLabel("-")
        
        self.k_lbl_devir_bakiye.setStyleSheet("font-weight: bold; color: #34495e;")
        self.k_lbl_banka_kasa.setStyleSheet("font-weight: bold; color: #2980b9;")
        self.k_lbl_elden_kasa.setStyleSheet("font-weight: bold; color: #d35400;")
        self.k_lbl_net.setStyleSheet("font-weight: bold; font-size: 14px;")

        form_ozet.addRow("Geçmiş Yıllardan Devreden Bakiye:", self.k_lbl_devir_bakiye)
        form_ozet.addRow("Seçilen Dönem İçi Gelirler (+):", self.k_lbl_toplam_gelir)
        form_ozet.addRow("Seçilen Dönem İçi Giderler (-):", self.k_lbl_toplam_gider)
        form_ozet.addRow("--- Aktif Alt Hesap Dağılımları ---", QLabel(""))
        form_ozet.addRow("Banka Hesabı Mevcut Kasa:", self.k_lbl_banka_kasa)
        form_ozet.addRow("Elden (Nakit) Mevcut Kasa:", self.k_lbl_elden_kasa)
        form_ozet.addRow("Genel Kasa Net Kalan Bakiye (Mevcut Para):", self.k_lbl_net)
        form_ozet.addRow("Finansal Sağlık Durumu:", self.k_lbl_durum)

        root.addWidget(gb_ozet)

        # Gelir tablosu
        gb_gelir = QGroupBox("Gelirler Takip Tablosu")
        vg = QVBoxLayout(gb_gelir)

        self.tbl_gelir = QTableWidget(0, 5)
        self.tbl_gelir.setHorizontalHeaderLabels(["Dönem", "Tarih", "Daire", "Yöntem", "Tutar"])
        self.tbl_gelir.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_gelir.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vg.addWidget(self.tbl_gelir)

        root.addWidget(gb_gelir)

        # Gider tablosu
        gb_gider = QGroupBox("Giderler Takip Tablosu")
        vx = QVBoxLayout(gb_gider)

        self.tbl_gider = QTableWidget(0, 6)
        self.tbl_gider.setHorizontalHeaderLabels(["Dönem", "Tarih", "Kategori", "Yöntem", "Tutar", "Açıklama"])
        self.tbl_gider.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_gider.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vx.addWidget(self.tbl_gider)

        root.addWidget(gb_gider)

    def calculate_devir(self, date_from):
        """ Seçilen tarihten önceki tüm yılların gelir-gider farkını (Devir) hesaplar """
        con = self.db.connect()
        eski_gelir = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE tarih < ?", (date_from,)).fetchone()[0] or 0.0
        eski_gider = con.execute("SELECT COALESCE(SUM(tutar),0) FROM giderler WHERE tarih < ?", (date_from,)).fetchone()[0] or 0.0
        con.close()
        return float(eski_gelir) - float(eski_gider)

    def refresh_kasa_report(self):
        date_from = self.k_from.date().toPython().isoformat()
        date_to = self.k_to.date().toPython().isoformat()

        # Geçmiş yıllardan devreden bakiye hesaplanıyor
        devreden_bakiye = self.calculate_devir(date_from)

        con = self.db.connect()
        gelir_rows = con.execute("""
            SELECT o.donem, o.tarih, d.daire_no, o.yontem, o.tutar
            FROM odemeler o
            JOIN daireler d ON d.id = o.daire_id
            WHERE o.tarih >= ? AND o.tarih <= ?
            ORDER BY o.tarih DESC
        """, (date_from, date_to)).fetchall()

        gider_rows = con.execute("""
            SELECT donem, tarih, kategori, yontem, tutar, aciklama
            FROM giderler
            WHERE tarih >= ? AND tarih <= ?
            ORDER BY tarih DESC
        """, (date_from, date_to)).fetchall()
        
        # Alt kasaların (Banka / Elden) tüm zamanlar bazında net durumunu çıkarma
        banka_gelir = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE yontem='Banka'").fetchone()[0] or 0.0
        banka_gider = con.execute("SELECT COALESCE(SUM(tutar),0) FROM giderler WHERE yontem='Banka'").fetchone()[0] or 0.0
        
        elden_gelir = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE yontem='Elden'").fetchone()[0] or 0.0
        elden_gider = con.execute("SELECT COALESCE(SUM(tutar),0) FROM giderler WHERE yontem='Elden'").fetchone()[0] or 0.0
        con.close()

        # Dönem içi toplamlar
        toplam_gelir = sum(float(r[4]) for r in gelir_rows)
        toplam_gider = sum(float(r[4]) for r in gider_rows)
        
        # Net durumlar (Devir dahil kasadaki gerçek bakiye)
        net_kasa_mevcut = devreden_bakiye + toplam_gelir - toplam_gider
        net_banka = float(banka_gelir) - float(banka_gider)
        net_elden = float(elden_gelir) - float(elden_gider)

        # Arayüz etiketlerini güncelleme
        self.k_lbl_devir_bakiye.setText(f"{devreden_bakiye:.2f} TL")
        self.k_lbl_toplam_gelir.setText(f"{toplam_gelir:.2f} TL")
        self.k_lbl_toplam_gider.setText(f"{toplam_gider:.2f} TL")
        self.k_lbl_banka_kasa.setText(f"{net_banka:.2f} TL")
        self.k_lbl_elden_kasa.setText(f"{net_elden:.2f} TL")
        self.k_lbl_net.setText(f"{net_kasa_mevcut:.2f} TL")
        
        if net_kasa_mevcut >= 0:
            self.k_lbl_durum.setText("🟢 POZİTİF (KASA GÜVENLİ)")
            self.k_lbl_durum.setStyleSheet("font-weight: bold; color: #27ae60;")
        else:
            self.k_lbl_durum.setText("🔴 NEGATİF (KASA AÇIK VERİYOR)")
            self.k_lbl_durum.setStyleSheet("font-weight: bold; color: #c0392b;")

        # Gelir Tablosunu Doldurma
        self.tbl_gelir.setRowCount(0)
        
        # Görsel İyileştirme: Eğer devreden bakiye varsa tablonun en üstüne ek satır ekle
        if devreden_bakiye != 0:
            row = self.tbl_gelir.rowCount()
            self.tbl_gelir.insertRow(row)
            vals = [date_from[:4], date_from, "SİSTEM", "DEVİR", f"{devreden_bakiye:.2f}"]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setBackground(QColor(230, 240, 250))
                # Not: QColor içerisine string renk ismi yerine doğrudan QColor(44, 62, 80) verilmeli veya setForeground kullanılmalı.
                # Orijinal yapınız bozulmasın diye bırakılmıştır.
                self.tbl_gelir.setItem(row, c, item)

        for donem, tarih, daire_no, yontem, tutar in gelir_rows:
            row = self.tbl_gelir.rowCount()
            self.tbl_gelir.insertRow(row)
            vals = [donem, tarih, daire_no, yontem, f"{float(tutar):.2f}"]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setBackground(QColor(220, 245, 230))
                self.tbl_gelir.setItem(row, c, item)

        # Gider Tablosunu Doldurma
        self.tbl_gider.setRowCount(0)
        for donem, tarih, kategori, yontem, tutar, aciklama in gider_rows:
            row = self.tbl_gider.rowCount()
            self.tbl_gider.insertRow(row)
            vals = [donem, tarih, kategori, yontem, f"{float(tutar):.2f}", aciklama or ""]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if c == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setBackground(QColor(255, 235, 235))
                self.tbl_gider.setItem(row, c, item)

    def export_kasa_excel(self):
        date_from = self.k_from.date().toPython().isoformat()
        date_to = self.k_to.date().toPython().isoformat()
        devreden_bakiye = self.calculate_devir(date_from)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Kasa Excel Kaydet",
            f"yillik_kasa_raporu_{date_from[:4]}.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return

        con = self.db.connect()
        gelir_rows = con.execute("""
            SELECT o.donem, o.tarih, d.daire_no, o.yontem, o.tutar
            FROM odemeler o
            JOIN daireler d ON d.id = o.daire_id
            WHERE o.tarih >= ? AND o.tarih <= ?
            ORDER BY o.tarih DESC
        """, (date_from, date_to)).fetchall()

        gider_rows = con.execute("""
            SELECT donem, tarih, kategori, yontem, tutar, aciklama
            FROM giderler
            WHERE tarih >= ? AND tarih <= ?
            ORDER BY tarih DESC
        """, (date_from, date_to)).fetchall()
        con.close()

        wb = Workbook()
        ws = wb.active
        ws.title = "Yıllık Finans Raporu"

        ws.append(["Mali Rapor Dönemi / Yılı", f"{date_from} - {date_to}"])
        ws.append(["Geçmiş Yıllardan Devreden Nakit", devreden_bakiye])
        ws.append([])
        ws.append(["GELİRLER LİSTESİ"])
        ws.append(["Dönem", "Tarih", "Daire", "Yöntem", "Tutar"])
        
        if devreden_bakiye != 0:
            ws.append([date_from[:4], date_from, "SİSTEM", "ESKİ YIL DEVİR", devreden_bakiye])
            
        for r in gelir_rows:
            ws.append(list(r))
        ws.append([])
        ws.append(["GİDERLER LİSTESİ"])
        ws.append(["Dönem", "Tarih", "Kategori", "Yöntem", "Tutar", "Açıklama"])
        for r in gider_rows:
            ws.append(list(r))

        wb.save(path)
        QMessageBox.information(self, "OK", f"Yıllık Kasa Raporu Excel formatında üretildi:\n{path}")
