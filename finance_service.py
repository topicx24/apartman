from datetime import date, timedelta


def iso_today() -> str:
    return date.today().isoformat()


def ym_of_today() -> str:
    d = date.today()
    return f"{d.year:04d}-{d.month:02d}"


def validate_period(donem: str) -> bool:
    if not donem or len(donem) != 7 or donem[4] != "-":
        return False
    try:
        y = int(donem[:4])
        m = int(donem[5:])
        return 2000 <= y <= 2100 and 1 <= m <= 12
    except Exception:
        return False


def safe_float(value: str) -> float:
    s = (value or "").strip()
    if not s:
        return 0.0
    s = s.replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def add_months(ym: str, add: int) -> str:
    y = int(ym[:4])
    m = int(ym[5:])
    m2 = m + add
    y += (m2 - 1) // 12
    m2 = ((m2 - 1) % 12) + 1
    return f"{y:04d}-{m2:02d}"


def months_range(ym_start: str, ym_end: str):
    ys = int(ym_start[:4])
    ms = int(ym_start[5:])
    ye = int(ym_end[:4])
    me = int(ym_end[5:])
    out = []
    cur_y, cur_m = ys, ms
    while (cur_y, cur_m) <= (ye, me):
        out.append(f"{cur_y:04d}-{cur_m:02d}")
        cur_m += 1
        if cur_m == 13:
            cur_m = 1
            cur_y += 1
    return out


def compute_vade_date(donem: str, vade_gun: int = 10):
    y, m = donem.split("-")
    y = int(y)
    m = int(m)
    if m == 12:
        next_month = date(y + 1, 1, 1)
    else:
        next_month = date(y, m + 1, 1)
    last_day = next_month - timedelta(days=1)
    day = min(vade_gun, last_day.day)
    return date(y, m, day)


def status_for_balance(donem: str, bakiye: float, vade_gun: int = 10, gecikme_gun: int = 5) -> str:
    if bakiye <= 0.00001:
        return "Ödedi"
    vade = compute_vade_date(donem, vade_gun)
    limit = vade + timedelta(days=gecikme_gun)
    if date.today() > limit:
        return "Gecikmiş"
    return "Borçlu"