from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QDateEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from openpyxl import Workbook

from db_manager import DbManager


class KasaExportWidget(QWidget):
    def __init__(self, db: DbManager):
        super().__init__()
        self.db = db
        self.build_ui()
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

        # Özet paneli
        gb_ozet = QGroupBox("Kasa Özeti")
        form_ozet = QFormLayout(gb_ozet)

        self.k_lbl_toplam_gelir = QLabel("0.00 TL")
        self.k_lbl_toplam_gider = QLabel("0.00 TL")
        self.k_lbl_net = QLabel("0.00 TL")
        self.k_lbl_durum = QLabel("-")

        form_ozet.addRow("Toplam Gelir", self.k_lbl_toplam_gelir)
        form_ozet.addRow("Toplam Gider", self.k_lbl_toplam_gider)
        form_ozet.addRow("Net Kalan", self.k_lbl_net)
        form_ozet.addRow("Durum", self.k_lbl_durum)

        root.addWidget(gb_ozet)

        # Gelir tablosu
        gb_gelir = QGroupBox("Gelirler")
        vg = QVBoxLayout(gb_gelir)

        self.tbl_gelir = QTableWidget(0, 5)
        self.tbl_gelir.setHorizontalHeaderLabels(["Dönem", "Tarih", "Daire", "Yöntem", "Tutar"])
        self.tbl_gelir.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_gelir.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vg.addWidget(self.tbl_gelir)

        root.addWidget(gb_gelir)

        # Gider tablosu
        gb_gider = QGroupBox("Giderler")
        vx = QVBoxLayout(gb_gider)

        self.tbl_gider = QTableWidget(0, 6)
        self.tbl_gider.setHorizontalHeaderLabels(["Dönem", "Tarih", "Kategori", "Yöntem", "Tutar", "Açıklama"])
        self.tbl_gider.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_gider.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vx.addWidget(self.tbl_gider)

        root.addWidget(gb_gider)

    def refresh_kasa_report(self):
        date_from = self.k_from.date().toPython().isoformat()
        date_to = self.k_to.date().toPython().isoformat()

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

        toplam_gelir = sum(float(r[4]) for r in gelir_rows)
        toplam_gider = sum(float(r[4]) for r in gider_rows)
        net = toplam_gelir - toplam_gider

        self.k_lbl_toplam_gelir.setText(f"{toplam_gelir:.2f} TL")
        self.k_lbl_toplam_gider.setText(f"{toplam_gider:.2f} TL")
        self.k_lbl_net.setText(f"{net:.2f} TL")
        self.k_lbl_durum.setText("POZİTİF" if net >= 0 else "NEGATİF")

        self.tbl_gelir.setRowCount(0)
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

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Kasa Excel Kaydet",
            f"kasa_raporu_{date_from}_{date_to}.xlsx",
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
        ws.title = "Kasa Raporu"

        ws.append(["Tarih Aralığı", f"{date_from} - {date_to}"])
        ws.append([])
        ws.append(["Gelirler"])
        ws.append(["Dönem", "Tarih", "Daire", "Yöntem", "Tutar"])
        for r in gelir_rows:
            ws.append(list(r))
        ws.append([])
        ws.append(["Giderler"])
        ws.append(["Dönem", "Tarih", "Kategori", "Yöntem", "Tutar", "Açıklama"])
        for r in gider_rows:
            ws.append(list(r))

        wb.save(path)
        QMessageBox.information(self, "OK", f"Kasa raporu Excel oluşturuldu:\n{path}")