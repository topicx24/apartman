from dataclasses import dataclass


@dataclass
class Daire:
    id: int
    daire_no: str
    ad_soyad: str
    telefon: str
    aidat: float
    aktif: bool


@dataclass
class Tahakkuk:
    id: int
    donem: str
    daire_id: int
    tutar: float
    created_at: str


@dataclass
class Odemeler:
    id: int
    donem: str
    tarih: str
    daire_id: int
    tutar: float
    yontem: str
    makbuz_no: str
    aciklama: str