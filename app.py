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
        self.tbl_daire.itemDoubleClicked.connect(self.on_daire_double_clicked)

        # --- DAİRE SİLME BUTONU (BURADA OLMALI) ---
        self.tbl_daire.setSelectionBehavior(QTableWidget.SelectRows)
        self.btn_delete_daire = QPushButton("Seçili Daireyi Sil")
        self.btn_delete_daire.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_delete_daire.clicked.connect(self.delete_selected_daire)
        d_layout.addWidget(self.btn_delete_daire)

        self.main_tabs.addTab(tab_daire, "Daireler")

        # --- Tahakkuk tab ---
        tab_tahakkuk = QWidget()
        t_layout = QVBoxLayout(tab_tahakkuk)
        
        # --- TAHAKKUK İPTAL BÖLÜMÜ ---
        t_layout.addWidget(QLabel("<b>Dairenin Mevcut Tahakkukları (Seçip İptal Edebilirsiniz):</b>"))
        self.tbl_tahakkuklar = QTableWidget(0, 3)
        self.tbl_tahakkuklar.setHorizontalHeaderLabels(["Tahakkuk ID", "Dönem", "Tutar (TL)"])
        self.tbl_tahakkuklar.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_tahakkuklar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_tahakkuklar.setMaximumHeight(200)
        t_layout.addWidget(self.tbl_tahakkuklar)

        self.btn_delete_tahakkuk = QPushButton("Seçili Tahakkuku İptal Et / Sil")
        self.btn_delete_tahakkuk.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_delete_tahakkuk.clicked.connect(self.delete_selected_tahakkuk)
        t_layout.addWidget(self.btn_delete_tahakkuk)
        gh = QHBoxLayout()
        self.t_daire_combo = QComboBox()
        self.t_daire_combo.currentIndexChanged.connect(self.on_tahakkuk_daire_changed)
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
        self.p_daire_combo.currentIndexChanged.connect(self.on_payment_daire_changed)

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
                # --- ÖDEME SEKRESİ DEĞİŞİKLİĞİ ---
        # Mevcut self.tbl_borc kodunuzun altına bu blok gelecek:
        o_layout.addWidget(QLabel("<b>Dairenin Geçmiş Ödemeleri (Seçip İptal Edebilirsiniz):</b>"))
        self.tbl_gecmis_odemeler = QTableWidget(0, 5)
        self.tbl_gecmis_odemeler.setHorizontalHeaderLabels(["Ödeme ID", "Dönem", "Tarih", "Tutar", "Yöntem"])
        self.tbl_gecmis_odemeler.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_gecmis_odemeler.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_gecmis_odemeler.setMaximumHeight(180)
        o_layout.addWidget(self.tbl_gecmis_odemeler)

        self.btn_delete_payment = QPushButton("Seçili Ödemeyi İptal Et / Sil")
        self.btn_print_receipt = QPushButton("Seçili Ödemenin Makbuzunu Al (PDF)")
        self.btn_print_receipt.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; margin-bottom: 5px;")
        self.btn_print_receipt.clicked.connect(self.print_selected_receipt)
        o_layout.addWidget(self.btn_print_receipt)
        self.btn_delete_payment.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_delete_payment.clicked.connect(self.delete_selected_payment)
        o_layout.addWidget(self.btn_delete_payment)

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

        # --- GİDER SEKRESİ DEĞİŞİKLİĞİ ---
        # Mevcut gbox.addWidget(self.tbl_gider) kodunuzun altına bu blok gelecek:
        self.tbl_gider.setSelectionBehavior(QTableWidget.SelectRows) # Satır seçimini kolaylaştırır
        
        self.btn_delete_expense = QPushButton("Seçili Gider Kaydını Sil")
        self.btn_delete_expense.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_delete_expense.clicked.connect(self.delete_selected_expense)
        gbox.addWidget(self.btn_delete_expense)


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
        """Formdaki bilgileri kaydeder veya mevcut daireyi günceller"""
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

        # DbManager sınıfınızın add_or_update_daire metodu zaten güncellemeyi destekliyor.
        did = self.db.add_or_update_daire(dno, ad, tel, aidat, 1)
        QMessageBox.information(self, "OK", f"Daire bilgileri kaydedildi/güncellendi. ID={did}")
        
        # Formu temizle ve butonu eski haline getir
        self.daire_no.clear()
        self.daire_no.setEnabled(True) # Daire No alanını tekrar aç
        self.daire_ad.clear()
        self.daire_tel.clear()
        self.daire_aidat.clear()
        self.btn_save_daire.setText("Daire Kaydet")
        
        self.refresh_all()

    def on_daire_double_clicked(self, item):
        """Tablodaki daireye çift tıklandığında bilgileri yukarıdaki forma taşır"""
        row = item.row()
        
        # Tablodaki satır verilerini oku
        did = self.tbl_daire.item(row, 0).text()
        dno = self.tbl_daire.item(row, 1).text()
        ad = self.tbl_daire.item(row, 2).text()
        tel = self.tbl_daire.item(row, 3).text()
        aidat = self.tbl_daire.item(row, 4).text()
        
        # Form alanlarına yerleştir
        self.daire_no.setText(dno)
        self.daire_no.setEnabled(False) # Güncellerken daire numarasının değiştirilmesini engellemek için
        self.daire_ad.setText(ad)
        self.daire_tel.setText(tel)
        self.daire_aidat.setText(aidat)
        
        # Buton metnini değiştirerek kullanıcıya rehberlik et
        self.btn_save_daire.setText("Daire Bilgilerini Güncelle")

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
            for c, v in enumerate(r):
                self.tbl_daire.setItem(row, c, QTableWidgetItem(str(v)))

            did, dno, ad, tel, aidat, aktif = r
            display = f"Daire {dno} - {ad}"
            self.t_daire_combo.addItem(display, did)
            self.p_daire_combo.addItem(display, did)

        self.t_daire_combo.blockSignals(False)
        self.p_daire_combo.blockSignals(False)

    # ... rest of file unchanged ...
