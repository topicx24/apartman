from __future__ import annotations

import sqlite3
from pathlib import Path

from finance_service import safe_float, validate_period, months_range, iso_today

DB_PATH = Path("apartman_aidat.db")


def connect(db_path: str | Path = DB_PATH):
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def ensure_db(db_path: str | Path = DB_PATH):
    con = connect(db_path)
    try:
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

            CREATE TABLE IF NOT EXISTS sakinler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                daire_id INTEGER NOT NULL,
                ad_soyad TEXT NOT NULL,
                telefon TEXT DEFAULT '',
                baslangic_tarihi TEXT NOT NULL,
                bitis_tarihi TEXT,
                FOREIGN KEY(daire_id) REFERENCES daireler(id)
            );

            CREATE TABLE IF NOT EXISTS tahakkuk (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donem TEXT NOT NULL,
                daire_id INTEGER NOT NULL,
                tutar REAL NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(donem, daire_id),
                FOREIGN KEY(daire_id) REFERENCES daireler(id)
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
                FOREIGN KEY(odeme_id) REFERENCES odemeler(id)
            );

            CREATE TABLE IF NOT EXISTS giderler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donem TEXT NOT NULL,
                tarih TEXT NOT NULL,
                kategori TEXT NOT NULL,
                tutar REAL NOT NULL,
                yontem TEXT NOT NULL,
                aciklama TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS duyurular (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarih TEXT NOT NULL,
                baslik TEXT NOT NULL,
                mesaj TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS delete_payment_details_after_payment
            AFTER DELETE ON odemeler
            BEGIN
                DELETE FROM odeme_detay WHERE odeme_id = OLD.id;
            END;
        """)
        con.commit()
    finally:
        con.close()


def get_setting_int(key: str, default: int, db_path: str | Path = DB_PATH) -> int:
    con = connect(db_path)
    try:
        row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        try:
            return int(row[0]) if row else default
        except Exception:
            return default
    finally:
        con.close()


def set_setting_int(key: str, value: int, db_path: str | Path = DB_PATH):
    con = connect(db_path)
    try:
        con.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(int(value))),
        )
        con.commit()
    finally:
        con.close()


def receipt_next_for_period(donem: str, db_path: str | Path = DB_PATH) -> str:
    yyyymm = donem.replace("-", "")
    con = connect(db_path)
    try:
        row = con.execute(
            "SELECT makbuz_no FROM odemeler WHERE donem = ? ORDER BY id DESC LIMIT 1",
            (donem,),
        ).fetchone()
    finally:
        con.close()

    if not row:
        return f"{yyyymm}-00001"

    try:
        last = str(row[0])
        seq = int(last.split("-")[-1]) if "-" in last else 0
    except Exception:
        seq = 0
    return f"{yyyymm}-{seq + 1:05d}"


def allocate_payment(total_amount: float, due_periods: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Distribute a payment amount across due periods."""
    remaining = float(total_amount)
    allocations: list[tuple[str, float]] = []
    for period, debt in due_periods:
        if remaining <= 0:
            break
        allocation = min(remaining, float(debt))
        allocations.append((str(period), round(allocation, 2)))
        remaining = round(remaining - allocation, 2)
    return allocations


def save_payment_record(daire_id: int, period: str, total_amount: float, yontem: str, tarih: str, aciklama: str, makbuz_no: str, db_path: str | Path = DB_PATH):
    if not validate_period(period):
        raise ValueError("Dönem formatı YYYY-MM olmalı.")
    if float(total_amount) <= 0:
        raise ValueError("Ödeme tutarı 0'dan büyük olmalı.")

    con = connect(db_path)
    try:
        con.execute(
            "INSERT INTO odemeler(donem, tarih, daire_id, tutar, yontem, makbuz_no, aciklama) VALUES(?,?,?,?,?,?,?)",
            (period, tarih, daire_id, float(total_amount), yontem, makbuz_no, aciklama),
        )
        con.commit()
    finally:
        con.close()


def get_all_debt_periods(daire_id: int, db_path: str | Path = DB_PATH):
    """Return periods with outstanding balances without multiplying charges by payment rows."""
    con = connect(db_path)
    try:
        rows = con.execute(
            """
            WITH tahakkuklar AS (
                SELECT donem, SUM(tutar) AS borc
                FROM tahakkuk
                WHERE daire_id = ?
                GROUP BY donem
            ), odemeler_donem AS (
                SELECT od.donem, SUM(od.tutar) AS odenen
                FROM odeme_detay od
                JOIN odemeler o ON o.id = od.odeme_id
                WHERE o.daire_id = ?
                GROUP BY od.donem
            )
            SELECT t.donem, t.borc, COALESCE(o.odenen, 0) AS odenen
            FROM tahakkuklar t
            LEFT JOIN odemeler_donem o ON o.donem = t.donem
            WHERE t.borc - COALESCE(o.odenen, 0) > 0.00001
            ORDER BY t.donem DESC
            """,
            (int(daire_id), int(daire_id)),
        ).fetchall()
        return [(donem, float(borc), float(odenen)) for donem, borc, odenen in rows]
    finally:
        con.close()


# Adapter class to provide the DbManager API expected by the UI code
class DbManager:
    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = db_path

    def init_db(self):
        ensure_db(self.db_path)

    def connect(self):
        return connect(self.db_path)

    def allocate_payment(self, total_amount: float, due_periods: list[tuple[str, float]]):
        return allocate_payment(total_amount, due_periods)

    def get_all_daireler(self):
        con = self.connect()
        try:
            return con.execute(
                "SELECT id, daire_no, ad_soyad, telefon, aidat, "
                "COALESCE(acilis_bakiyesi, 0.0), aktif "
                "FROM daireler ORDER BY CAST(daire_no AS INTEGER), daire_no"
            ).fetchall()
        finally:
            con.close()

    def add_or_update_daire(self, daire_no: str, ad: str, telefon: str, aidat: float, aktif: int = 1):
        con = self.connect()
        try:
            cur = con.execute("SELECT id FROM daireler WHERE daire_no = ?", (daire_no,)).fetchone()
            if cur:
                con.execute("UPDATE daireler SET ad_soyad=?, telefon=?, aidat=?, aktif=? WHERE id=?",
                            (ad, telefon, float(aidat), int(aktif), int(cur[0])))
                did = int(cur[0])
            else:
                con.execute("INSERT INTO daireler(daire_no, ad_soyad, telefon, aidat, aktif) VALUES(?,?,?,?,?)",
                            (daire_no, ad, telefon, float(aidat), int(aktif)))
                did = con.execute("SELECT id FROM daireler WHERE daire_no=?", (daire_no,)).fetchone()[0]
            con.commit()
            return int(did)
        finally:
            con.close()

    def add_tahakkuk_range(self, daire_id: int, start: str, end: str, tutar: float) -> int:
        con = self.connect()
        adet = 0
        try:
            for donem in months_range(start, end):
                con.execute("""
                    INSERT INTO tahakkuk(donem, daire_id, tutar, created_at)
                    VALUES(?,?,?,?)
                    ON CONFLICT(donem, daire_id) DO UPDATE SET tutar=excluded.tutar, created_at=excluded.created_at
                """, (donem, int(daire_id), float(tutar), iso_today()))
                adet += 1
            con.commit()
            return adet
        finally:
            con.close()

    def get_balance_for_period(self, daire_id: int, donem: str):
        con = self.connect()
        try:
            borc = con.execute("SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE donem=? AND daire_id=?",
                                (donem, int(daire_id))).fetchone()[0] or 0.0
            odeme = con.execute(
                "SELECT COALESCE(SUM(od.tutar),0) FROM odeme_detay od JOIN odemeler o ON o.id = od.odeme_id WHERE od.donem=? AND o.daire_id=?",
                (donem, int(daire_id))).fetchone()[0] or 0.0
            return float(borc), float(odeme), float(borc) - float(odeme)
        finally:
            con.close()

    def get_total_balance(self, daire_id: int):
        con = self.connect()
        try:
            borc = con.execute("SELECT COALESCE(SUM(tutar),0) FROM tahakkuk WHERE daire_id=?", (int(daire_id),)).fetchone()[0] or 0.0
            odeme = con.execute("SELECT COALESCE(SUM(tutar),0) FROM odemeler WHERE daire_id=?", (int(daire_id),)).fetchone()[0] or 0.0
            return float(borc), float(odeme), float(borc) - float(odeme)
        finally:
            con.close()

    def get_all_debt_periods(self, daire_id: int):
        rows = get_all_debt_periods(int(daire_id), self.db_path)
        return [(donem, float(borc) - float(odenen)) for donem, borc, odenen in rows]

    def save_payment(self, daire_id: int, allocations: list[tuple[str, float]], tarih: str, yontem: str, aciklama: str):
        if not allocations:
            raise ValueError("En az bir ödeme dönemi ve tutarı girilmelidir.")
        normalized_allocations = []
        for period, amount in allocations:
            period = str(period).strip()
            amount = float(amount)
            if period.upper() != "DEVİR" and not validate_period(period):
                raise ValueError("Dönem YYYY-MM formatında veya DEVİR olmalı.")
            if amount <= 0:
                raise ValueError("Ödeme tutarı 0'dan büyük olmalı.")
            normalized_allocations.append((period, amount))

        period = normalized_allocations[0][0]
        total = sum(amount for _, amount in normalized_allocations)
        makbuz = receipt_next_for_period(period, self.db_path)
        con = self.connect()
        try:
            cur = con.execute(
                "INSERT INTO odemeler(donem, tarih, daire_id, tutar, yontem, makbuz_no, aciklama) VALUES(?,?,?,?,?,?,?)",
                (period, tarih, int(daire_id), float(total), yontem, makbuz, aciklama)
            )
            odeme_id = cur.lastrowid
            for allocation_period, amount in normalized_allocations:
                con.execute(
                    "INSERT INTO odeme_detay(odeme_id, donem, tutar) VALUES(?,?,?)",
                    (int(odeme_id), allocation_period, float(amount)),
                )
            con.commit()
        finally:
            con.close()
        return makbuz


__all__ = [
    "DB_PATH",
    "connect",
    "ensure_db",
    "get_setting_int",
    "set_setting_int",
    "receipt_next_for_period",
    "allocate_payment",
    "save_payment_record",
    "get_all_debt_periods",
    "DbManager",
]
