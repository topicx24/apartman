from __future__ import annotations

import sqlite3
from pathlib import Path

from finance_service import safe_float, validate_period

DB_PATH = Path("apartman_aidat.db")


def connect(db_path: str | Path = DB_PATH):
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def ensure_db(db_path: str | Path = DB_PATH):
    con = connect(db_path)
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
    """)
    con.commit()
    con.close()


def get_setting_int(key: str, default: int, db_path: str | Path = DB_PATH) -> int:
    con = connect(db_path)
    row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    con.close()
    try:
        return int(row[0]) if row else default
    except Exception:
        return default


def set_setting_int(key: str, value: int, db_path: str | Path = DB_PATH):
    con = connect(db_path)
    con.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(int(value))),
    )
    con.commit()
    con.close()


def receipt_next_for_period(donem: str, db_path: str | Path = DB_PATH) -> str:
    yyyymm = donem.replace("-", "")
    con = connect(db_path)
    row = con.execute(
        "SELECT makbuz_no FROM odemeler WHERE donem = ? ORDER BY id DESC LIMIT 1",
        (donem,),
    ).fetchone()
    con.close()

    if not row:
        return f"{yyyymm}-00001"

    try:
        last = str(row[0])
        if "-" in last:
            seq = int(last.split("-")[-1])
        else:
            seq = 0
    except Exception:
        seq = 0

    return f"{yyyymm}-{seq + 1:05d}"


def allocate_payment(total_amount: float, due_periods: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Ödenen toplamı dönemlere dağıtır.

    due_periods: [(period, debt_amount), ...]
    return: [(period, allocated_amount), ...]
    """
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

    con = connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO odemeler(donem, tarih, daire_id, tutar, yontem, makbuz_no, aciklama)
            VALUES(?,?,?,?,?,?,?)
            """,
            (period, tarih, daire_id, float(total_amount), yontem, makbuz_no, aciklama),
        )
        con.commit()
    finally:
        con.close()


def get_all_debt_periods(daire_id: int, db_path: str | Path = DB_PATH):
    con = connect(db_path)
    rows = con.execute(
        """
        SELECT t.donem, COALESCE(SUM(t.tutar), 0) AS borc, COALESCE(SUM(od.tutar), 0) AS odenen
        FROM tahakkuk t
        LEFT JOIN odeme_detay od
            ON od.donem = t.donem
           AND od.odeme_id IN (
               SELECT id FROM odemeler WHERE daire_id = ?
           )
        WHERE t.daire_id = ?
        GROUP BY t.donem
        HAVING (COALESCE(SUM(t.tutar), 0) - COALESCE(SUM(od.tutar), 0)) > 0
        ORDER BY t.donem DESC
        """,
        (daire_id, daire_id),
    ).fetchall()
    con.close()

    result = []
    for donem, borc, odenen in rows:
        result.append((donem, float(borc), float(odenen)))
    return result


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
]
