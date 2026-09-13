"""Testes unitários para utilidades de fuso horário de São Paulo (24h) em kiros/tz.py."""
from datetime import datetime, timezone
import unittest
from zoneinfo import ZoneInfo

from kiros.tz import (
    SAO_PAULO_TZ,
    now_sp,
    now_sp_iso,
    to_sp,
    format_sp,
    format_sp_date,
    format_sp_time,
    format_sp_display,
    format_sp_friendly,
    format_sp_day_month,
    format_sp_input,
    ensure_sp_iso,
    normalize_input_sp_iso,
)


class TimezoneSaoPauloTests(unittest.TestCase):
    def test_sao_paulo_timezone_instance(self):
        self.assertEqual(str(SAO_PAULO_TZ), 'America/Sao_Paulo')

    def test_now_sp_is_timezone_aware(self):
        dt = now_sp()
        self.assertIsNotNone(dt.tzinfo)
        self.assertEqual(dt.tzinfo, SAO_PAULO_TZ)

    def test_utc_to_sao_paulo_conversion(self):
        # 22:30 UTC em 13/09/2026 deve ser 19:30 no fuso de São Paulo (UTC-3)
        dt_utc = datetime(2026, 9, 13, 22, 30, tzinfo=timezone.utc)
        dt_sp = to_sp(dt_utc)
        self.assertEqual(dt_sp.hour, 19)
        self.assertEqual(dt_sp.minute, 30)
        self.assertEqual(dt_sp.day, 13)

    def test_format_24h(self):
        dt_utc = datetime(2026, 9, 13, 22, 5, tzinfo=timezone.utc)
        # Formato 24h: 19:05
        self.assertEqual(format_sp_time(dt_utc), '19:05')
        self.assertEqual(format_sp_date(dt_utc), '13/09/2026')
        self.assertEqual(format_sp_display(dt_utc), '13/09/2026 às 19:05')

    def test_naive_string_localized_to_sp(self):
        # Entrada vinda de <input type="datetime-local">
        input_str = '2026-10-22T19:45'
        normalized = normalize_input_sp_iso(input_str)
        self.assertIn('-03:00', normalized)
        self.assertIn('2026-10-22T19:45:00', normalized)

    def test_aware_string_preserved_in_normalize(self):
        aware_utc = '2026-11-28T20:30:00+00:00'
        normalized = normalize_input_sp_iso(aware_utc)
        self.assertEqual(normalized, aware_utc)


if __name__ == '__main__':
    unittest.main()

