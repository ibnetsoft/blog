import unittest
from datetime import timezone, timedelta

from services.scheduler_service import SchedulerService


class SchedulerServiceTests(unittest.TestCase):
    def test_time_to_minutes(self):
        self.assertEqual(SchedulerService._time_to_minutes("09:30"), 570)
        self.assertEqual(SchedulerService._time_to_minutes("bad"), -1)

    def test_timestamp_to_date_uses_timezone(self):
        tzinfo = timezone(timedelta(hours=9))

        date_value = SchedulerService._timestamp_to_date("2026-08-07 18:30:00", tzinfo)

        self.assertEqual(date_value, "2026-08-08")


if __name__ == "__main__":
    unittest.main()
