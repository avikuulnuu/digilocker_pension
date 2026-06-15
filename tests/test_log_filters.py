"""Tests for production log handler filters."""

import logging

from django.test import SimpleTestCase

from config.log_filters import NoExcInfoFilter


class NoExcInfoFilterTest(SimpleTestCase):
    def test_strips_exception_info_from_record(self):
        filt = NoExcInfoFilter()
        try:
            raise RuntimeError("secret details")
        except RuntimeError:
            record = logging.LogRecord(
                name="issuer",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="Unexpected error",
                args=(),
                exc_info=True,
            )

        self.assertTrue(filt.filter(record))
        self.assertIsNone(record.exc_info)
        self.assertIsNone(record.exc_text)
