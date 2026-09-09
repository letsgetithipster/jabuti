import datetime

from po.datas import parse_data


def test_iso_com_hora():
    assert parse_data("2026-08-20 00:00:00", ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y"]) == datetime.date(2026, 8, 20)


def test_ptbr():
    assert parse_data("20/08/2026", ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y"]) == datetime.date(2026, 8, 20)


def test_us_com_extrair_as_of():
    assert parse_data("08/11/2026 as of 08/10/2026", ["%m/%d/%Y"], extrair=r"^(\S+)") == datetime.date(2026, 8, 11)


def test_datetime_e_date_passam_direto():
    assert parse_data(datetime.datetime(2026, 8, 20, 10, 0), ["%d/%m/%Y"]) == datetime.date(2026, 8, 20)
    assert parse_data(datetime.date(2026, 8, 20), []) == datetime.date(2026, 8, 20)


def test_invalido_retorna_none():
    assert parse_data("ontem", ["%d/%m/%Y"]) is None
    assert parse_data("", ["%d/%m/%Y"]) is None
    assert parse_data(None, ["%d/%m/%Y"]) is None
    assert parse_data("31/02/2026", ["%d/%m/%Y"]) is None
    assert parse_data("x 08/11/2026", ["%m/%d/%Y"], extrair=r"^(\d+/\d+/\d+)") is None
