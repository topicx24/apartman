# app.py
import datetime
import sqlite3
import webbrowser
import urllib.parse
from db_manager import DbManager
from finance_service import (
    iso_today,
    safe_float,
    status_for_balance,
    validate_period,
    ym_of_today,
)
from gider_rapor import GiderRaporWidget
from kasa_export import KasaExportWidget
from PySide6.QtCore import QDate, QMarginsF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ApartmanAidatApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DbManager()
        self.db.init_db()
        self.check_and_update_db_schema()
        self.setWindowTitle("Apartman Aidat Sistemi - Yönetim Paneli")
        self.resize(1250, 850)
        self.build_ui()
        self.apply_modern_theme()
        self.refresh_all()

    def check_and_update_db_schema(self):
        con = self.db.connect()
        try:
            cursor = con.cursor()
            cursor.execute("PRAGMA table_info(daireler)")
            columns = [row[1] for row in cursor.fetchall()]
            if "acilis_bakiyesi" not in columns:
                cursor.execute("ALTER TABLE daireler ADD COLUMN acilis_bakiyesi REAL DEFAULT 0.0")
                con.commit()
        except Exception as e:
            print(f"Veritabanı güncelleme hatası: {e}")
        finally:
            con.close()

    def apply_modern_theme(self):
        self.setStyleSheet(
            "QWidget{background-color:#f4f6f7;font-family:'Segoe UI';font-size:13px;color:#212529;}"
            " QTabWidget::panel{border:1px solid #cfd8dc;background:#fff;border-radius:6px;}"
            " QTabBar::tab{background:#eceff1;border:1px solid #cfd8dc;padding:10px 20px;font-weight:bold;color:#546e7a;}"
            " QTabBar::tab:selected{background:#fff;color:#00796b;}"
            " QGroupBox{font-weight:bold;border:1px solid #cfd8dc;border-radius:6px;margin-top:12px;padding-top:16px;background:#fff;}"
            " QGroupBox::title{subcontrol-origin:margin;left:12px;color:#00796b;}"
            " QLineEdit,QComboBox{border:1px solid #b0bec5;border-radius:4px;padding:6px 10px;}"
            " QPushButton{background:#00796b;color:white;font-weight:bold;border-radius:4px;padding:8px 15px;}"
            " QPushButton:hover{background:#004d40;}"
            " QTableWidget{border:1px solid #cfd8dc;gridline-color:#eaeded;selection-background-color:#e0f2f1;selection-color:#004d40;}"
            " QHeaderView::section{background:#e5ecef;color:#212529;padding:8px;font-weight:bold;}"
        )

    def build_ui(self):
        self.tabs = QTabWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 15, 15, 15)
        outer.setSpacing(10)
        outer.addWidget(self.tabs)

        main_panel = QWidget()
        main_layout = QVBoxLayout(main_panel)
        self.main_tabs = QTabWidget()
        main_layout.addWidget(self.main_tabs)

        # 1. Daireler Sekmesi
        tab_daire = QWidget()
        d_layout = QVBoxLayout(tab_daire)
        gb_daire_form = QGroupBox("Yeni Daire Kayıt / Düzenleme Formu")
        form = QFormLayout(gb_daire_form)

        self.daire_no = QLineEdit()
        self.daire_ad = QLineEdit()
        self.daire_tel = QLineEdit()
        self.daire_aidat = QLineEdit()
        self.daire_acilis_bakiyesi = QLineEdit()
        self.daire_acilis_bakiyesi.setPlaceholderText("Örn: 1500.00 (Eski sitemden devreden borç)")
        
        self.daire_aktif = QComboBox()
        self.daire_aktif.addItems(["Aktif", "Pasif"])
        
        self.btn_save_daire = QPushButton("Daire Kaydet")
        self.btn_save_daire.clicked.connect(self.save_daire)

        form.addRow("Daire No:", self.daire_no)
        form.addRow("Ad Soyad:", self.daire_ad)
        form.addRow("Telefon:", self.daire_tel)
        form.addRow("Sabit Aidat (TL):", self.daire_aidat)
        form.addRow("Açılış Borç Bakiyesi (TL):", self.daire_acilis_bakiyesi)
        form.addRow("Durum:", self.daire_aktif)
        form.addRow("", self.btn_save_daire)
        d_layout.addWidget(gb_daire_form)

        self.tbl_daire = QTableWidget(0, 7)
        self.tbl_daire.setHorizontalHeaderLabels(
            ["ID", "Daire", "İsim", "Telefon", "Aidat", "Açılış Bakiyesi", "Durum"]
        )
        self.tbl_daire.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_daire.setAlternatingRowColors(True)
        d_layout.addWidget(self.tbl_daire)
        self.tbl_daire.itemDoubleClicked.connect(self.on_daire_double_clicked)

        self.btn_delete_daire = QPushButton("Seçili Daireyi Sil")
        self.btn_delete_daire.setStyleSheet("background:#e74c3c;color:white;font-weight:bold;")
        self.btn_delete_daire.clicked.connect(self.delete_selected_daire)
        d_layout.addWidget(self.btn_delete_daire)
        self.main_tabs.addTab(tab_daire, "Daireler")

        # 2. Tahakkuk Sekmesi
        tab_tahakkuk = QWidget()
        t_layout = QVBoxLayout(tab_tahakkuk)
        t_layout.addWidget(QLabel("<b>Dairenin Mevcut Tahakkukları:</b>"))

        self.tbl_tahakkuklar = QTableWidget(0, 3)
        self.tbl_tahakkuklar.setHorizontalHeaderLabels(["Tahakkuk ID", "Dönem", "Tutar (TL)"])
        self.tbl_tahakkuklar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t_layout.addWidget(self.tbl_tahakkuklar)

        self.btn_delete_tahakkuk = QPushButton("Seçili Tahakkuku İptal Et / Sil")
        self.btn_delete_tahakkuk.setStyleSheet("background:#e74c3c;")
        self.btn_delete_tahakkuk.clicked.connect(self.delete_selected_tahakkuk)
        t_layout.addWidget(self.btn_delete_tahakkuk)

        gb_tahakkuk_ekle = QGroupBox("Tahakkuk Oluştur")
        gh = QHBoxLayout(gb_tahakkuk_ekle)
        self.t_daire_combo = QComboBox()
        self.t_from = QLineEdit(ym_of_today())
        self.t_to = QLineEdit(ym_of_today())
        self.t_tutar = QLineEdit()
        self.t_daire_combo.currentIndexChanged.connect(self.on_tahakkuk_daire_changed)

        btn_t = QPushButton("Oluştur")
        btn_t.clicked.connect(self.create_tahakkuk)

        gh.addWidget(QLabel("Daire:"))
        gh.addWidget(self.t_daire_combo)
        gh.addWidget(QLabel("Başlangıç:"))
        gh.addWidget(self.t_from)
        gh.addWidget(QLabel("Bitiş:"))
        gh.addWidget(self.t_to)
        gh.addWidget(QLabel("Tutar:"))
        gh.addWidget(self.t_tutar)
        gh.addWidget(btn_t)
        t_layout.addWidget(gb_tahakkuk_ekle)
        self.main_tabs.addTab(tab_tahakkuk, "Tahakkuk")

        # 3. Ödeme Sekmesi
        tab_odeme = QWidget()
        o_layout = QVBoxLayout(tab_odeme)
        o_layout.setSpacing(12)

        gb_hizli_odeme = QGroupBox("Hızlı Ödeme Kayıt Paneli")
        op = QHBoxLayout(gb_hizli_odeme)

        self.p_daire_combo = QComboBox()
        self.p_donem = QLineEdit(ym_of_today())
        self.p_tutar = QLineEdit()

        self.p_tarih = QDateEdit()
        self.p_tarih.setCalendarPopup(True)
        self.p_tarih.setDate(QDate.currentDate())
        self.p_tarih.setDisplayFormat("dd-MM-yyyy")

        self.p_yontem = QComboBox()
        self.p_daire_combo.currentIndexChanged.connect(self.on_payment_daire_changed)
        self.p_yontem.addItems(["Banka", "Elden"])

        btn_f = QPushButton("Kalanı Doldur")
        btn_f.setStyleSheet("background:#2ecc71;")
        btn_f.clicked.connect(self.fill_balance_for_period)

        btn_s = QPushButton("Ödemeyi Kaydet")
        btn_s.clicked.connect(self.save_payment_quick)

        op.addWidget(QLabel("Daire:"))
        op.addWidget(self.p_daire_combo)
        op.addWidget(QLabel("Dönem:"))
        op.addWidget(self.p_donem)
        op.addWidget(QLabel("Tutar:"))
        op.addWidget(self.p_tutar)
        op.addWidget(QLabel("Öd. Tarihi:"))
        op.addWidget(self.p_tarih)
        op.addWidget(self.p_yontem)
        op.addWidget(btn_f)
        op.addWidget(btn_s)
        o_layout.addWidget(gb_hizli_odeme)

        self.tbl_gecmis_odemeler = QTableWidget(0, 5)
        self.tbl_gecmis_odemeler.setHorizontalHeaderLabels(["Ödeme ID", "Dönem", "Tarih", "Tutar", "Yöntem"])
        self.tbl_gecmis_odemeler.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_gecmis_odemeler.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_gecmis_odemeler.itemDoubleClicked.connect(self.on_past_payment_double_clicked)
        o_layout.addWidget(self.tbl_gecmis_odemeler)

        btn_odeme_alt = QHBoxLayout()
        self.btn_print_receipt = QPushButton("Makbuz Al (PDF)")
        self.btn_print_receipt.setStyleSheet("background:#27ae60;")
        self.btn_print_receipt.clicked.connect(self.print_selected_receipt)

        self.btn_delete_payment = QPushButton("Ödemeyi Sil")
        self.btn_delete_payment.setStyleSheet("background:#e74c3c;")
        self.btn_delete_payment.clicked.connect(self.delete_selected_payment)

        btn_odeme_alt.addWidget(self.btn_print_receipt)
        btn_odeme_alt.addWidget(self.btn_delete_payment)
        o_layout.addLayout(btn_odeme_alt)

        self.tbl_borc = QTableWidget(0, 3)
        self.tbl_borc.setHorizontalHeaderLabels(["Dönem", "Borç", "Kalan"])
        self.tbl_borc.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        o_layout.addWidget(self.tbl_borc)
        self.main_tabs.addTab(tab_odeme, "Ödeme")
        self.tbl_borc.itemDoubleClicked.connect(self.on_debt_double_clicked)

        # 4. GİDERLER SEKMESİ
        tab_gider = QWidget()
        g_layout = QVBoxLayout(tab_gider)
        g_layout.setSpacing(8)

        gb_gider = QGroupBox("Gider Ekle / Düzenle")
        gform = QFormLayout(gb_gider)

        gform.setContentsMargins(10, 10, 10, 10)
        gform.setSpacing(6)
        self.g_donem = QLineEdit(ym_of_today())
        self.g_tarih = QDateEdit()
        self.g_tarih.setCalendarPopup(True)
        self.g_tarih.setDate(QDate.currentDate())
        self.g_tarih.setDisplayFormat("dd.MM.yyyy")
        self.g_kategori = QComboBox()
        self.g_tutar = QLineEdit()
        self.g_yontem = QComboBox()
        self.g_aciklama = QLineEdit()
        self.g_kategori.addItems(["Elektrik", "Temizlik", "Bakım", "Diğer"])
        self.g_yontem.addItems(["Banka", "Elden"])
        self.btn_gider_save = QPushButton("Gider Kaydet")
        self.btn_gider_save.clicked.connect(self.save_expense)
        gform.addRow("Dönem (YYYY-MM):", self.g_donem)
        gform.addRow("Tarih (GG.AA.YYYY):", self.g_tarih)
        gform.addRow("Kategori:", self.g_kategori)
        gform.addRow("Tutar (TL):", self.g_tutar)
        gform.addRow("Yöntem:", self.g_yontem)
        gform.addRow("Açıklama:", self.g_aciklama)
        gform.addRow("", self.btn_gider_save)
        g_layout.addWidget(gb_gider)

        self.tbl_gider = QTableWidget(0, 7)
        self.tbl_gider.setHorizontalHeaderLabels(["ID", "Dönem", "Tarih", "Kategori", "Tutar", "Yöntem", "Açıklama"])
        self.tbl_gider.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_gider.itemDoubleClicked.connect(self.on_expense_double_clicked)
        g_layout.addWidget(self.tbl_gider)

        self.btn_delete_expense = QPushButton("Seçili Gideri Sil")
        self.btn_delete_expense.setStyleSheet("background:#e74c3c;")
        self.btn_delete_expense.clicked.connect(self.delete_selected_expense)
        g_layout.addWidget(self.btn_delete_expense)
        self.main_tabs.addTab(tab_gider, "Gider")

        # 5. RAPOR SEKMESİ
        tab_rapor = QWidget()
        r_layout = QVBoxLayout(tab_rapor)
        gb_filtre = QGroupBox("Filtreleme Kriterleri")
        rpt_top = QHBoxLayout(gb_filtre)
        self.r_donem = QLineEdit(ym_of_today())
        self.r_only_unpaid = QComboBox()
        self.r_only_unpaid.addItems(["Hepsi", "Sadece borçlu", "Sadece geciken"])
        btn_r = QPushButton("Yenile")
        btn_r.clicked.connect(self.refresh_report)
        rpt_top.addWidget(QLabel("Dönem:"))
        rpt_top.addWidget(self.r_donem)
        rpt_top.addWidget(QLabel("Filtre:"))
        rpt_top.addWidget(self.r_only_unpaid)
        rpt_top.addWidget(btn_r)
        r_layout.addWidget(gb_filtre)

        self.lbl_summary = QLabel("Özet: -")
        self.lbl_summary.setStyleSheet(
            "font-weight:bold;padding:10px;background:#eef2f3;border-radius:4px;"
        )
        r_layout.addWidget(self.lbl_summary)

        self.tbl_rapor = QTableWidget(0, 9)
        self.tbl_rapor.setHorizontalHeaderLabels(
            ["Daire", "İsim", "Telefon", "Aidat", "Borç", "Ödenen", "Kalan", "Toplam Borç", "Durum"]
        )
        self.tbl_rapor.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        r_layout.addWidget(self.tbl_rapor)
        self.tbl_rapor.itemDoubleClicked.connect(self.on_report_item_double_clicked)
        self.main_tabs.addTab(tab_rapor, "Rapor")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(main_panel)
        self.tabs.addTab(scroll, "Yönetim Paneli")

        self.gider_rapor = GiderRaporWidget(self.db)
        self.tabs.addTab(self.gider_rapor, "Gider & Rapor")

        self.kasa_widget = KasaExportWidget(self.db)
        self.tabs.addTab(self.kasa_widget, "Kasa")

    def save_daire(self):
        dno = self.daire_no.text().strip()
        ad = self.daire_ad.text().strip()
        tel = self.daire_tel.text().strip()
        try:
            aidat = safe_float(self.daire_aidat.text())
            acilis = safe_float(self.daire_acilis_bakiyesi.text())
        except:
            QMessageBox.warning(self, "Uyarı", "Aidat ve Açılış Bakiyesi sayısal olmalı.")
            return
        if not dno or not ad:
            QMessageBox.warning(self, "Uyarı", "Daire No ve İsim zorunlu.")
            return
        is_active = 1 if self.daire_aktif.currentText() == "Aktif" else 0
        con = self.db.connect()
        if getattr(self, "_editing_daire_id", None) is not None:
            con.execute(
                "UPDATE daireler SET daire_no=?, ad_soyad=?, telefon=?, aidat=?, acilis_bakiyesi=?, aktif=? WHERE id=?",
                (dno, ad, tel, float(aidat), float(acilis), is_active, self._editing_daire_id)
            )
        else:
            con.execute(
                "INSERT INTO daireler (daire_no, ad_soyad, telefon, aidat, acilis_bakiyesi, aktif) VALUES (?,?,?,?,?,?)",
                (dno, ad, tel, float(aidat), float(acilis), is_active)
            )
        con.commit()
        con.close()
        self._editing_daire_id = None
        self.daire_no.clear()
        self.daire_ad.clear()
        self.daire_tel.clear()
        self.daire_aidat.clear()
        self.daire_acilis_bakiyesi.clear()
        self.daire_aktif.setCurrentIndex(0)
        self.daire_no.setEnabled(True)
        self.btn_save_daire.setText("Daire Kaydet")
        self.refresh_all()

    def on_daire_double_clicked(self, item):
        row = item.row()
        self._editing_daire_id = int(self.tbl_daire.item(row, 0).text())
        self.daire_no.setText(self.tbl_daire.item(row, 1).text())
        self.daire_no.setEnabled(False)
        self.daire_ad.setText(self.tbl_daire.item(row, 2).text())
        self.daire_tel.setText(self.tbl_daire.item(row, 3).text())
        self.daire_aidat.setText(self.tbl_daire.item(row, 4).text())
        self.daire_acilis_bakiyesi.setText(self.tbl_daire.item(row, 5).text())
        self.daire_aktif.setCurrentText(self.tbl_daire.item(row, 6).text())
        self.btn_save_daire.setText("Daire Bilgilerini Güncelle")

    def delete_selected_daire(self):
        row = self.tbl_daire.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Daire seçin.")
            return
        did = self.tbl_daire.item(row, 0).text()
        if QMessageBox.question(self, "Onay", "Seçili daire silinsin mi?") != QMessageBox.Yes:
            return
        con = self.db.connect()
        con.execute("DELETE FROM daireler WHERE id=?", (int(did),))
        con.commit()
        con.close()
        self.refresh_all()

    def on_debt_double_clicked(self, item):
        row = item.row()
        donem_item = self.tbl_borc.item(row, 0)
        tutar_item = self.tbl_borc.item(row, 2)
        if donem_item and tutar_item:
            self.p_donem.setText(donem_item.text().strip())
            self.p_tutar.setText(tutar_item.text().strip())
            self.p_tarih.setFocus()
            self.p_tarih.selectAll()

    def refresh_daire_table(self):
        rows = self.db.get_all_daireler()
        self.tbl_daire.setRowCount(0)
        self.t_daire_combo.blockSignals(True)
        self.p_daire_combo.blockSignals(True)
        self.t_daire_combo.clear()
        self.p_daire_combo.clear()
        self.t_daire_combo.addItem("-- seç --", -1)
        self.p_daire_combo.addItem("-- seç --", -1)
        for r in rows:
            row = self.tbl_daire.rowCount()
            self.tbl_daire.insertRow(row)
            self.tbl_daire.setItem(row, 0, QTableWidgetItem(str(r[0])))
            self.tbl_daire.setItem(row, 1, QTableWidgetItem(str(r[1])))
            self.tbl_daire.setItem(row, 2, QTableWidgetItem(str(r[2])))
            self.tbl_daire.setItem(row, 3, QTableWidgetItem(str(r[3])))
            self.tbl_daire.setItem(row, 4, QTableWidgetItem(f"{float(r[4]):.2f}"))
            acilis_val = r[5] if len(r) > 5 and r[5] is not None else 0.0
            self.tbl_daire.setItem(row, 5, QTableWidgetItem(f"{float(acilis_val):.2f}"))
            aktif_val = r[6] if len(r) > 6 else (r[5] if len(r) == 6 else 1)
            status_text = "Aktif" if aktif_val == 1 else "Pasif"
            status_item = QTableWidgetItem(status_text)
            self.tbl_daire.setItem(row, 6, status_item)
            if aktif_val != 1:
                for c in range(7):
                    item = self.tbl_daire.item(row, c)
                    if item:
                        item.setForeground(QColor(140, 140, 140))
            if aktif_val == 1:
                display = f"Daire {r[1]} - {r[2]}"
                self.t_daire_combo.addItem(display, r[0])
                self.p_daire_combo.addItem(display, r[0])
        self.t_daire_combo.blockSignals(False)
        self.p_daire_combo.blockSignals(False)

    def create_tahakkuk(self):
        did = self.t_daire_combo.currentData()
        if did in (-1, None):
            QMessageBox.warning(self, "Uyarı", "Daire seçin.")
            return
        start = self.t_from.text().strip()
        end = self.t_to.text().strip()
        if not validate_period(start) or not validate_period(end) or start > end:
            QMessageBox.warning(self, "Uyarı", "Dönem hatası.")
            return
        tutar_str = self.t_tutar.text().strip()
        if not tutar_str:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir tutar giriniz!")
            return
        try:
            tutar = safe_float(tutar_str)
            if tutar <= 0:
                QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalıdır.")
                return
        except:
            QMessageBox.warning(self, "Uyarı", "Tutar sayısal olmalı.")
            return
        self.db.add_tahakkuk_range(int(did), start, end, tutar)
        self.t_tutar.clear()
        QMessageBox.information(self, "Başarılı", "Tahakkuk başarıyla oluşturuldu.")
        self.refresh_all()

    def fill_balance_for_period(self):
        did = self.p_daire_combo.currentData()
        donem = self.p_donem.text().strip()
        if did in (-1, None):
            return
        if donem.upper() == "DEVİR":
            con = self.db.connect()
            acilis = con.execute("SELECT COALESCE(acilis_bakiyesi, 0.0) FROM daireler WHERE id=?", (int(did),)).fetchone()[0] or 0.0
            odenen_devir = con.execute("SELECT COALESCE(SUM(tutar), 0.0) FROM odemeler WHERE daire_id=? AND donem='DEVİR'", (int(did),)).fetchone()[0] or 0.0
            con.close()
            kalan_devir = float(acilis) - float(odenen_devir)
            self.p_tutar.setText(f"{max(kalan_devir, 0.0):.2f}")
            return
        if not validate_period(donem):
            return
        b, o, bakiye = self.db.get_balance_for_period(int(did), donem)
        if bakiye <= 0:
            self.p_tutar.clear()
            QMessageBox.information(self, "Bilgi", "Borç yok.")
            return
        self.p_tutar.setText(f"{bakiye:.2f}")

    def save_payment_quick(self):
        did = self.p_daire_combo.currentData()
        donem = self.p_donem.text().strip()
        odeme_tarihi = self.p_tarih.date().toString("yyyy-MM-dd")
        if did in (-1, None):
            QMessageBox.warning(self, "Uyarı", "Eksik veya hatalı bilgi.")
            return
        if donem.upper() != "DEVİR" and not validate_period(donem):
            QMessageBox.warning(self, "Uyarı", "Geçersiz dönem formatı.")
            return
        try:
            tutar = safe_float(self.p_tutar.text())
        except:
            QMessageBox.warning(self, "Uyarı", "Tutar sayısal olmalı.")
            return
        alloc = [(donem, tutar)]
        try:
            makbuz = self.db.save_payment(
                int(did),
                alloc,
                odeme_tarihi,
                self.p_yontem.currentText(),
                f"Hızlı ödeme / Dönem: {donem}"
            )
            QMessageBox.information(self, "Başarılı", f"Ödeme başarıyla kaydedildi.\nMakbuz No: {makbuz}")
            self.p_tutar.clear()
            self.p_tarih.setDate(QDate.currentDate())
            self.refresh_all()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Ödeme kaydedilemedi: {e}")

    def on_payment_daire_changed(self):
        self.refresh_borc_table()
        self.refresh_gecmis_odemeler_table()

    def on_tahakkuk_daire_changed(self):
        self.refresh_tahakkuk_table()

    def refresh_gecmis_odemeler_table(self):
        did = self.p_daire_combo.currentData()
        self.tbl_gecmis_odemeler.setRowCount(0)
        if did in (-1, None):
            return
        con = self.db.connect()
        rows = con.execute(
            "SELECT id, donem, tarih, tutar, yontem FROM odemeler WHERE daire_id=? ORDER BY tarih DESC, id DESC",
            (int(did),),
        ).fetchall()
        con.close()
        for r in rows:
            row = self.tbl_gecmis_odemeler.rowCount()
            self.tbl_gecmis_odemeler.insertRow(row)
            vals = [str(r[0]), str(r[1]), str(r[2]), f"{float(r[3]):.2f}", str(r[4])]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tbl_gecmis_odemeler.setItem(row, c, item)

    def on_past_payment_double_clicked(self, item):
        row = item.row()
        donem_item = self.tbl_gecmis_odemeler.item(row, 1)
        tutar_item = self.tbl_gecmis_odemeler.item(row, 3)
        if donem_item and tutar_item:
            self.p_donem.setText(donem_item.text().strip())
            self.p_tutar.setText(tutar_item.text().strip())
            self.p_tarih.setFocus()

    def delete_selected_payment(self):
        row = self.tbl_gecmis_odemeler.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Ödeme seçin.")
            return
        pid = self.tbl_gecmis_odemeler.item(row, 0).text()
        if QMessageBox.question(self, "Onay", "Silinsin mi?") != QMessageBox.Yes:
            return
        con = self.db.connect()
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("DELETE FROM odemeler WHERE id=?", (int(pid),))
        con.commit()
        con.close()
        self.refresh_all()

    def print_selected_receipt(self):
        row = self.tbl_gecmis_odemeler.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Ödeme seçin.")
            return
        pid, donem, tarih, tutar, yontem = [
            self.tbl_gecmis_odemeler.item(row, i).text() for i in range(5)
        ]
        d_text = self.p_daire_combo.currentText()
        name = d_text.split(" - ")[-1].strip() if " - " in d_text else "DAIRE"
        s_name = name.translate(str.maketrans("ÇĞİÖŞÜçğıöşü ", "CGIOSUcgiosu_")).upper()
        f_date = tarih.replace("-", ".")
        path, _ = QFileDialog.getSaveFileName(
            self, "Makbuz Kaydet", f"{s_name}{f_date}-makbuz_no_{pid}.pdf", "PDF Files (.pdf)"
        )
        if not path:
            return
        try:
            pdf = QPdfWriter(path)
            layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(10, 10, 10, 10))
            pdf.setPageLayout(layout)
            painter = QPainter()
            if not painter.begin(pdf):
                raise Exception("Başlatılamadı.")
            mx = pdf.logicalDpiX() / 25.4
            my = pdf.logicalDpiY() / 25.4
            painter.setPen(QPen(QColor(44, 62, 80), int(1.5 * mx)))
            painter.drawRect(int(15 * mx), int(20 * my), int(180 * mx), int(105 * my))
            painter.setFont(QFont("Helvetica", 14, 75))
            painter.drawText(int(25 * mx), int(35 * my), "AİDAT TAHSİLAT MAKBUZU")
            painter.setFont(QFont("Helvetica", 11))
            painter.drawText(int(140 * mx), int(32 * my), f"Makbuz No: {pid}")
            painter.drawText(int(140 * mx), int(39 * my), f"Tarih: {f_date}")
            painter.drawLine(int(25 * mx), int(45 * my), int(185 * mx), int(45 * my))
            lbls = ["Daire Bilgisi:", "Ödeme Dönemi:", "Ödeme Yöntemi:", "Tahsil Edilen:"]
            vals = [d_text, f"{donem} Dönemi Aidatı" if donem != "DEVİR" else "Geçmiş Dönem Devir Borcu", yontem, f"{tutar} TL"]
            for i in range(4):
                painter.setFont(QFont("Helvetica", 11, 75 if i == 3 else -1))
                painter.drawText(int(25 * mx), int((57 + i * 10) * my), lbls[i])
                painter.setFont(QFont("Helvetica", 11, 75 if i == 3 else -1))
                painter.setPen(QPen(QColor(39, 174, 96) if i == 3 else QColor(0, 0, 0)))
                painter.drawText(int(65 * mx), int((57 + i * 10) * my), vals[i])
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.drawLine(int(25 * mx), int(93 * my), int(185 * mx), int(93 * my))
            painter.drawText(int(35 * mx), int(105 * my), "Teslim Eden (Daire)")
            painter.drawText(int(135 * mx), int(105 * my), "Tahsil Eden (Yönetim)")
            painter.end()
            QMessageBox.information(self, "Başarılı", "Makbuz PDF olarak kaydedildi.")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"PDF hatası: {e}")

    def delete_selected_expense(self):
        row = self.tbl_gider.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Gider seçin.")
            return
        eid = self.tbl_gider.item(row, 0).text()
        if QMessageBox.question(self, "Onay", "Silinsin mi?") != QMessageBox.Yes:
            return
        con = self.db.connect()
        con.execute("DELETE FROM giderler WHERE id=?", (int(eid),))
        con.commit()
        con.close()
        self.refresh_all()

    def refresh_borc_table(self):
        did = self.p_daire_combo.currentData()
        self.tbl_borc.setRowCount(0)
        if did in (-1, None):
            return
        con = self.db.connect()
        acilis = con.execute("SELECT COALESCE(acilis_bakiyesi, 0.0) FROM daireler WHERE id=?", (int(did),)).fetchone()[0] or 0.0
        odenen_devir = con.execute("SELECT COALESCE(SUM(tutar), 0.0) FROM odemeler WHERE daire_id=? AND donem='DEVİR'", (int(did),)).fetchone()[0] or 0.0
        con.close()
        kalan_devir = float(acilis) - float(odenen_devir)
        if kalan_devir > 0.00001:
            row = self.tbl_borc.rowCount()
            self.tbl_borc.insertRow(row)
            self.tbl_borc.setItem(row, 0, QTableWidgetItem("DEVİR"))
            self.tbl_borc.setItem(row, 1, QTableWidgetItem(f"{float(acilis):.2f}"))
            self.tbl_borc.setItem(row, 2, QTableWidgetItem(f"{float(kalan_devir):.2f}"))
        for p in self.db.get_all_debt_periods(int(did)) or []:
            row = self.tbl_borc.rowCount()
            self.tbl_borc.insertRow(row)
            donem, kalan = p if isinstance(p, tuple) else ("Borç", p)
            self.tbl_borc.setItem(row, 0, QTableWidgetItem(str(donem)))
            self.tbl_borc.setItem(row, 1, QTableWidgetItem(f"{float(kalan):.2f}"))
            self.tbl_borc.setItem(row, 2, QTableWidgetItem(f"{float(kalan):.2f}"))

    def save_expense(self):
        donem = self.g_donem.text().strip()
        tarih = self.g_tarih.date().toString("yyyy-MM-dd")
        if not validate_period(donem):
            QMessageBox.warning(self, "Uyarı", "Dönem formatı geçersiz.")
            return
        try:
            tutar = safe_float(self.g_tutar.text())
        except:
            QMessageBox.warning(self, "Uyarı", "Tutar geçersiz.")
            return
        con = self.db.connect()
        if getattr(self, "_editing_expense_id", None) is not None:
            con.execute(
                "UPDATE giderler SET donem=?, tarih=?, kategori=?, tutar=?, yontem=?, aciklama=? WHERE id=?",
                (donem, tarih, self.g_kategori.currentText(), float(tutar), self.g_yontem.currentText(), self.g_aciklama.text().strip(), self._editing_expense_id)
            )
        else:
            con.execute(
                "INSERT INTO giderler(donem, tarih, kategori, tutar, yontem, aciklama) VALUES(?,?,?,?,?,?)",
                (donem, tarih, self.g_kategori.currentText(), float(tutar), self.g_yontem.currentText(), self.g_aciklama.text().strip())
            )
        con.commit()
        con.close()
        self._editing_expense_id = None
        self.btn_gider_save.setText("Gider Kaydet")
        self.g_tutar.clear()
        self.g_aciklama.clear()
        self.g_tarih.setDate(QDate.currentDate())
        self.refresh_all()

    def on_expense_double_clicked(self, item):
        row = item.row()
        self._editing_expense_id = int(self.tbl_gider.item(row, 0).text())
        self.g_donem.setText(self.tbl_gider.item(row, 1).text())
        tarih_str = self.tbl_gider.item(row, 2).text()
        if "." in tarih_str:
            parts = tarih_str.split(".")
            if len(parts) == 3:
                tarih_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
        q_date = QDate.fromString(tarih_str, "yyyy-MM-dd")
        if q_date.isValid():
            self.g_tarih.setDate(q_date)
        self.g_kategori.setCurrentText(self.tbl_gider.item(row, 3).text())
        self.g_tutar.setText(self.tbl_gider.item(row, 4).text())
        self.g_yontem.setCurrentText(self.tbl_gider.item(row, 5).text())
        self.g_aciklama.setText(self.tbl_gider.item(row, 6).text())
        self.btn_gider_save.setText("Gider Bilgilerini Güncelle")

    def refresh_expense_table(self):
        con = self.db.connect()
        rows = con.execute(
            "SELECT id, donem, tarih, kategori, tutar, yontem, aciklama FROM giderler ORDER BY tarih DESC, id DESC"
        ).fetchall()
        con.close()
        self.tbl_gider.setRowCount(0)
        for r in rows:
            row = self.tbl_gider.rowCount()
            self.tbl_gider.insertRow(row)
            tarih_ham = str(r[2])
            if "-" in tarih_ham and len(tarih_ham.split("-")) == 3:
                p = tarih_ham.split("-")
                tarih_goster = f"{p[2]}.{p[1]}.{p[0]}"
            else:
                tarih_goster = tarih_ham.replace("-", ".")
            for c, v in enumerate([r[0], r[1], tarih_goster, r[3], f"{float(r[4]):.2f}", r[5], r[6]]):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if c == 4 else Qt.AlignLeft)
                self.tbl_gider.setItem(row, c, item)

    def refresh_tahakkuk_table(self):
        did = self.t_daire_combo.currentData()
        self.tbl_tahakkuklar.setRowCount(0)
        if did in (-1, None):
            return
        con = self.db.connect()
        rows = con.execute("SELECT id, donem, tutar FROM tahakkuk WHERE daire_id=? ORDER BY donem DESC", (int(did),)).fetchall()
        con.close()
        for r in rows:
            row = self.tbl_tahakkuklar.rowCount()
            self.tbl_tahakkuklar.insertRow(row)
            for col, val in enumerate([r[0], r[1], f"{float(r[2]):.2f}"]):
                self.tbl_tahakkuklar.setItem(row, col, QTableWidgetItem(str(val)))

    def delete_selected_tahakkuk(self):
        row = self.tbl_tahakkuklar.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Tahakkuk seçin.")
            return
        rid = int(self.tbl_tahakkuklar.item(row, 0).text())
        if QMessageBox.question(self, "Onay", "Silinsin mi?") != QMessageBox.Yes:
            return
        con = self.db.connect()
        con.execute("DELETE FROM tahakkuk WHERE id=?", (rid,))
        con.commit()
        con.close()
        self.refresh_all()

    def refresh_report(self):
        donem = self.r_donem.text().strip()
        if not validate_period(donem):
            return
        con = self.db.connect()
        daireler = con.execute(
            "SELECT id, daire_no, ad_soyad, telefon, aidat, COALESCE(acilis_bakiyesi,0.0), aktif FROM daireler ORDER BY CAST(daire_no AS INTEGER), daire_no"
        ).fetchall()
        gelir = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE donem=?", (donem,)).fetchone()[0]
        gider = con.execute("SELECT COALESCE(SUM(tutar),0) FROM giderler WHERE donem=?", (donem,)).fetchone()[0]
        con.close()
        self.tbl_rapor.setRowCount(0)
        total_debts = 0.0
        for did, dno, name, phone, fee, acilis, active in daireler:
            debt, paid, balance = self.db.get_balance_for_period(int(did), donem)
            periods = self.db.get_all_debt_periods(int(did)) or []
            con = self.db.connect()
            odenen_devir = con.execute("SELECT COALESCE(SUM(tutar), 0.0) FROM odemeler WHERE daire_id=? AND donem='DEVİR'", (int(did),)).fetchone()[0] or 0.0
            con.close()
            kalan_acilis = max(float(acilis) - float(odenen_devir), 0.0)
            total = sum(float(p[1] if isinstance(p, tuple) else p) for p in periods) + kalan_acilis
            status = status_for_balance(donem, balance)
            if self.r_only_unpaid.currentText() == "Sadece borçlu" and total <= 0:
                continue
            if self.r_only_unpaid.currentText() == "Sadece geciken" and status != "Gecikmiş":
                continue
            total_debts += total
            row = self.tbl_rapor.rowCount()
            self.tbl_rapor.insertRow(row)
            vals = [dno, name, phone, f"{float(fee):.2f}", f"{float(debt):.2f}", f"{float(paid):.2f}", f"{float(balance):.2f}", f"{total:.2f}", status]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setBackground(QColor(255, 235, 235) if total > 0 else QColor(235, 255, 235))
                if c == 0:
                    item.setData(Qt.UserRole, int(did))
                if 3 <= c <= 7:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tbl_rapor.setItem(row, c, item)
        self.lbl_summary.setText(
            f"{donem} | Gelir: {float(gelir):.2f} TL | Gider: {float(gider):.2f} TL | Net: {float(gelir)-float(gider):.2f} TL | Toplam Birikmiş Borç: {total_debts:.2f} TL"
        )

    def send_whatsapp_message(self, phone, name, total_debt):
        """WhatsApp üzerinden daire sahibine borç hatırlatması gönderir."""
        if not phone or phone.strip() == "" or phone == "-":
            QMessageBox.warning(self, "Uyarı", "Bu daireye ait geçerli bir telefon numarası kayıtlı değil!")
            return
        
        clean_phone = "".join(filter(str.isdigit, phone))
        if not clean_phone.startswith("90") and len(clean_phone) == 10:
            clean_phone = "90" + clean_phone

        message = (
            f"Sayın {name},\n\n"
            f"Apartman aidat borç bilgilendirmesidir.\n"
            f"Güncel toplam birikmiş borç tutarınız: *{total_debt:.2f} TL* 'dir.\n\n"
            f"Ödemenizi yapmanızı rica ederiz. İyi günler dileriz."
        )
        
        encoded_message = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_message}"
        webbrowser.open(whatsapp_url)

    def on_report_item_double_clicked(self, item):
        row = item.row()
        first = self.tbl_rapor.item(row, 0)
        if first is None:
            return
        did = first.data(Qt.UserRole)
        dno = first.text()
        d_isim = self.tbl_rapor.item(row, 1).text()
        d_telefon = self.tbl_rapor.item(row, 2).text()
        
        con = sqlite3.connect("apartman_aidat.db")
        acilis_bakiyesi = con.execute("SELECT COALESCE(acilis_bakiyesi, 0.0) FROM daireler WHERE id=?", (int(did),)).fetchone()[0] or 0.0
        odenen_devir = con.execute("SELECT COALESCE(SUM(tutar), 0.0) FROM odemeler WHERE daire_id=? AND donem='DEVİR'", (int(did),)).fetchone()[0] or 0.0
        con.close()
        kalan_acilis = max(float(acilis_bakiyesi) - float(odenen_devir), 0.0)
        periods = self.db.get_all_debt_periods(int(did)) or []
        total = sum(float(p[1] if isinstance(p, tuple) else p) for p in periods) + kalan_acilis

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Daire {dno} - {d_isim} Detaylı Durum ve Ödeme Raporu")
        dlg.setMinimumSize(600, 600)
        lay = QVBoxLayout(dlg)

        lbl_t = QLabel(f"Toplam Birikmiş Aktif Borç (Açılış Dahil): {total:.2f} TL")
        lbl_t.setStyleSheet("font-size:15px; font-weight:bold; color:" + ("#c0392b;" if total > 0 else "#27ae60;"))
        lay.addWidget(lbl_t)

        gb_tarih_filtre = QGroupBox("Gelişmiş Tarih Aralıklı Ödeme Geçmişi")
        g_lay = QVBoxLayout(gb_tarih_filtre)
        t_row = QHBoxLayout()
        txt_start = QLineEdit("2026-01-01")
        txt_end = QLineEdit(iso_today())
        btn_filter_p = QPushButton("Listele / Filtrele")
        t_row.addWidget(QLabel("Başlangıç:"))
        t_row.addWidget(txt_start)
        t_row.addWidget(QLabel("Bitiş:"))
        t_row.addWidget(txt_end)
        t_row.addWidget(btn_filter_p)
        g_lay.addLayout(t_row)

        tbl_history = QTableWidget(0, 4)
        tbl_history.setHorizontalHeaderLabels(["Dönem", "Ödeme Tarihi", "Tutar (TL)", "Yöntem"])
        tbl_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_history.setAlternatingRowColors(True)
        g_lay.addWidget(tbl_history)
        lay.addWidget(gb_tarih_filtre)

        def filter_payments():
            tbl_history.setRowCount(0)
            con = sqlite3.connect("apartman_aidat.db")
            p_rows = con.execute(
                "SELECT donem, tarih, tutar, yontem FROM odemeler WHERE daire_id = ? AND tarih BETWEEN ? AND ? ORDER BY tarih DESC",
                (int(did), txt_start.text().strip(), txt_end.text().strip())
            ).fetchall()
            con.close()
            for r_donem, r_tarih, r_tutar, r_yontem in p_rows:
                r_idx = tbl_history.rowCount()
                tbl_history.insertRow(r_idx)
                tbl_history.setItem(r_idx, 0, QTableWidgetItem(str(r_donem)))
                tbl_history.setItem(r_idx, 1, QTableWidgetItem(str(r_tarih).replace("-", ".")))
                item_m = QTableWidgetItem(f"{float(r_tutar):.2f}")
                item_m.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tbl_history.setItem(r_idx, 2, item_m)
                tbl_history.setItem(r_idx, 3, QTableWidgetItem(str(r_yontem)))

        btn_filter_p.clicked.connect(filter_payments)
        filter_payments()

        bx = QHBoxLayout()
        
        # WhatsApp Butonu Entegrasyonu
        btn_whatsapp = QPushButton("WhatsApp ile Hatırlat")
        btn_whatsapp.setStyleSheet("background:#25D366; color:white; font-weight:bold;")
        btn_whatsapp.clicked.connect(lambda: self.send_whatsapp_message(d_telefon, d_isim, total))

        btn_c = QPushButton("Borçları Kopyala")
        btn_p = QPushButton("Ekstre Al (PDF)")
        btn_p.setStyleSheet("background:#2980b9; color:white; font-weight:bold;")
        btn_x = QPushButton("Kapat")
        
        bx.addWidget(btn_whatsapp)
        bx.addWidget(btn_c)
        bx.addWidget(btn_p)
        bx.addWidget(btn_x)
        lay.addLayout(bx)

        def pdf_ekstre_save():
            raw_start = txt_start.text().strip()
            raw_end = txt_end.text().strip()
            s_date = raw_start.replace("-", ".")
            e_date = raw_end.replace("-", ".")
            start_period = raw_start[:7]
            end_period = raw_end[:7]
            s_name = d_isim.translate(str.maketrans("ÇĞİÖŞÜçğıöşü ", "CGIOSUcgiosu_")).upper()
            default_filename = f"DAIRE_{dno}_{s_name}_HESAP_EKSTRESI.pdf"
            path, _ = QFileDialog.getSaveFileName(dlg, "Hesap Ekstresi PDF Kaydet", default_filename, "PDF Files (.pdf)")
            if not path:
                return
            try:
                pdf = QPdfWriter(path)
                layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(15, 15, 15, 15))
                pdf.setPageLayout(layout)
                painter = QPainter()
                if not painter.begin(pdf):
                    raise Exception("PDF başlatılamadı.")
                mx = pdf.logicalDpiX() / 25.4
                my = pdf.logicalDpiY() / 25.4

                con = sqlite3.connect("apartman_aidat.db")
                db_acilis = con.execute("SELECT COALESCE(acilis_bakiyesi, 0.0) FROM daireler WHERE id=?", (int(did),)).fetchone()[0] or 0.0
                eski_borclar = con.execute("SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE daire_id = ? AND donem < ?", (int(did), start_period)).fetchone()[0] or 0.0
                eski_odemeler = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE daire_id = ? AND tarih < ?", (int(did), raw_start)).fetchone()[0] or 0.0
                devir_bakiyesi = float(db_acilis) + float(eski_borclar) - float(eski_odemeler)

                db_tahakkuklar = con.execute(
                    "SELECT donem, tutar FROM tahakkuk WHERE daire_id = ? AND donem >= ? AND donem <= ? ORDER BY donem ASC",
                    (int(did), start_period, end_period)
                ).fetchall()
                db_odemeler = con.execute(
                    "SELECT donem, tarih, tutar, yontem FROM odemeler WHERE daire_id = ? AND tarih BETWEEN ? AND ? ORDER BY tarih ASC",
                    (int(did), raw_start, raw_end)
                ).fetchall()
                con.close()

                ekstre_items = []
                for dnm, tutar in db_tahakkuklar:
                    sanal_tarih = f"{dnm}-01"
                    ekstre_items.append((sanal_tarih, dnm, f"{dnm} Dönemi Aidat Borcu", "-", float(tutar), "BORÇ"))
                for dnm, trh, tutar, yntm in db_odemeler:
                    t_goster = str(trh).replace("-", ".")
                    ekstre_items.append((str(trh), dnm, f"{t_goster} Tarihli Aidat Ödemesi" if dnm != "DEVİR" else "Geçmiş Dönem Devir Borcu", yntm, float(tutar), "ÖDEME"))
                ekstre_items.sort(key=lambda x: x)

                total_borc_sum = 0.0
                total_odeme_sum = 0.0

                def draw_page_headers():
                    painter.setPen(QPen(QColor(52, 73, 94), int(1 * mx)))
                    painter.drawRect(int(10 * mx), int(10 * my), int(190 * mx), int(265 * my))
                    painter.setPen(QPen(QColor(52, 73, 94)))
                    painter.setFont(QFont("Helvetica", 16, 75))
                    painter.drawText(int(15 * mx), int(25 * my), "DAİRE HESAP EKSTRESİ RAPORU")
                    painter.setFont(QFont("Helvetica", 10))
                    painter.drawText(int(145 * mx), int(23 * my), f"Düzenleme T.: {iso_today().replace('-', '.')}")
                    painter.drawLine(int(15 * mx), int(28 * my), int(190 * mx), int(28 * my))
                    painter.setFont(QFont("Helvetica", 11, 75))
                    painter.drawText(int(15 * mx), int(38 * my), "Mülk Bilgisi : ")
                    painter.setFont(QFont("Helvetica", 11))
                    painter.drawText(int(45 * mx), int(38 * my), f"Daire {dno} - {d_isim}")
                    painter.setFont(QFont("Helvetica", 11, 75))
                    painter.drawText(int(15 * mx), int(45 * my), "Ekstre Dönemi: ")
                    painter.setFont(QFont("Helvetica", 11))
                    painter.drawText(int(45 * mx), int(45 * my), f"{s_date} - {e_date} Tarihleri Arası")
                    painter.setPen(QPen(QColor(189, 195, 199), int(0.5 * mx)))
                    painter.drawLine(int(15 * mx), int(53 * my), int(190 * mx), int(53 * my))
                    painter.setPen(QPen(QColor(52, 73, 94)))
                    painter.setFont(QFont("Helvetica", 10, 75))
                    painter.drawText(int(20 * mx), int(60 * my), "İşlem Dönemi")
                    painter.drawText(int(60 * mx), int(60 * my), "Açıklama / İşlem Türü")
                    painter.drawText(int(120 * mx), int(60 * my), "Yöntem")
                    painter.drawText(int(160 * mx), int(60 * my), "Tutar")
                    painter.setPen(QPen(QColor(189, 195, 199), int(0.5 * mx)))
                    painter.drawLine(int(15 * mx), int(65 * my), int(190 * mx), int(65 * my))

                draw_page_headers()
                y_mm = 73
                painter.setFont(QFont("Helvetica", 10, 75))
                painter.setPen(QPen(QColor(44, 62, 80)))
                painter.drawText(int(20 * mx), int(y_mm * my), "DEVİR")
                painter.drawText(int(60 * mx), int(y_mm * my), "Sistem Açılış / Geçmiş Dönem Toplam Devir")
                painter.drawText(int(120 * mx), int(y_mm * my), "Sistem")
                isaret_devir = "+" if devir_bakiyesi >= 0 else ""
                painter.drawText(int(160 * mx), int(y_mm * my), f"{isaret_devir}{devir_bakiyesi:.2f} TL")
                y_mm += 8

                for s_tarih, dnm, acik, yntm, tutar, tur in ekstre_items:
                    if y_mm > 245:
                        pdf.newPage()
                        draw_page_headers()
                        y_mm = 73
                    painter.setFont(QFont("Helvetica", 10))
                    painter.setPen(QPen(QColor(192, 57, 43) if tur == "BORÇ" else QColor(39, 174, 96)))
                    painter.drawText(int(20 * mx), int(y_mm * my), str(dnm))
                    painter.drawText(int(60 * mx), int(y_mm * my), str(acik))
                    painter.drawText(int(120 * mx), int(y_mm * my), str(yntm))
                    isaret = "+" if tur == "BORÇ" else "-"
                    painter.drawText(int(160 * mx), int(y_mm * my), f"{isaret}{tutar:.2f} TL")
                    if tur == "BORÇ":
                        total_borc_sum += tutar
                    else:
                        total_odeme_sum += tutar
                    y_mm += 8

                if y_mm > 225:
                    pdf.newPage()
                    draw_page_headers()
                    y_mm = 73

                painter.setPen(QPen(QColor(149, 165, 166), int(0.5 * mx)))
                painter.drawLine(int(15 * mx), int(y_mm * my), int(190 * mx), int(y_mm * my))
                y_mm += 8
                painter.setFont(QFont("Helvetica", 11, 75))
                painter.setPen(QPen(QColor(52, 73, 94)))
                painter.drawText(int(50 * mx), int(y_mm * my), f"Sistem Açılış ve Geçmiş Devir Bakiyesi: {devir_bakiyesi:.2f} TL")
                y_mm += 7
                painter.drawText(int(50 * mx), int(y_mm * my), f"Seçilen Dönem İçi Borç (+): {total_borc_sum:.2f} TL")
                y_mm += 7
                painter.setPen(QPen(QColor(39, 174, 96)))
                painter.drawText(int(50 * mx), int(y_mm * my), f"Seçilen Dönem İçi Tahsilat (-): {total_odeme_sum:.2f} TL")
                y_mm += 8

                kalan_net_bakiye = devir_bakiyesi + total_borc_sum - total_odeme_sum
                painter.setPen(QPen(QColor(192, 57, 43) if kalan_net_bakiye > 0 else QColor(39, 174, 96)))
                painter.drawText(int(50 * mx), int(y_mm * my), f"GÜNCEL TOPLAM NET BORÇ BAKİYESİ: {kalan_net_bakiye:.2f} TL")
                painter.setPen(QPen(QColor(127, 140, 141)))
                painter.setFont(QFont("Helvetica", 9, -1, True))
                painter.drawText(int(15 * mx), int(262 * my), "Bu döküm, apartman otomasyonu mali ekstre modülü tarafından güvenli veritabanından üretilmiştir.")
                painter.end()
                QMessageBox.information(dlg, "Başarılı", "Daire hesap ekstresi devir dengeli olarak PDF formatında başarıyla kaydedildi.")
            except Exception as e:
                QMessageBox.warning(dlg, "Hata", f"PDF üretilemedi: {e}")

        btn_p.clicked.connect(pdf_ekstre_save)
        btn_c.clicked.connect(lambda: QApplication.clipboard().setText(f"Daire: {dno}\nToplam Borç: {total:.2f} TL"))
        btn_x.clicked.connect(dlg.accept)
        dlg.exec()

    def refresh_all(self):
        self.refresh_daire_table()
        self.refresh_expense_table()
        self.refresh_borc_table()
        self.refresh_gecmis_odemeler_table()
        self.refresh_tahakkuk_table()
        self.refresh_report()
        if hasattr(self, "gider_rapor"):
            self.gider_rapor.refresh_expense_table()
        if hasattr(self, "kasa_widget"):
            self.kasa_widget.refresh_kasa_report()


def main():
    import sys
    app = QApplication(sys.argv)
    window = ApartmanAidatApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
