import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';

/// Dates, in PKT.
///
/// Two classes of bug here, both invisible without a test:
///
///  1. **Zone.** Django serialises with an offset, so a parsed `DateTime` is correct but in
///     the device's zone. A trip at 01:00 Karachi shows as the previous day on a phone set
///     to UTC, and "grouped by day" history files it under the wrong heading.
///  2. **Urdu times.** CLDR's `ur` data abbreviates the day period to a bare `a`/`p`, so
///     20:30 formats as "8:30 p" — indistinguishable from morning.
void main() {
  setUpAll(initializeDateFormatting);

  group('parsing', () {
    test('normalises a server timestamp to UTC', () {
      // The +05:00 form Django actually sends.
      final parsed = AppDates.tryParseUtc('2026-08-15T02:55:00.819704+05:00');
      expect(parsed!.isUtc, isTrue);
      expect(parsed, DateTime.utc(2026, 8, 14, 21, 55, 0, 819, 704));
    });

    test('accepts the Z form too', () {
      final parsed = AppDates.tryParseUtc('2026-08-14T21:55:00.820732Z');
      expect(parsed, DateTime.utc(2026, 8, 14, 21, 55, 0, 820, 732));
    });

    test('a bare date (a DateField) parses as UTC midnight', () {
      expect(AppDates.tryParseUtc('2099-12-31'), DateTime.utc(2099, 12, 31));
    });

    test('null and garbage stay null', () {
      expect(AppDates.tryParseUtc(null), isNull);
      expect(AppDates.tryParseUtc('not a date'), isNull);
    });
  });

  group('PKT rendering', () {
    // 21:55 UTC on the 14th is 02:55 on the 15th in Karachi — the exact case where a
    // device-zone bug puts a trip on the wrong day.
    final lateNight = DateTime.utc(2026, 8, 14, 21, 55);

    test('renders the Karachi calendar day, not the UTC one', () {
      expect(AppDates.date(lateNight), '15 Aug 2026');
    });

    test('groups by the Karachi day', () {
      expect(AppDates.pktDayKey(lateNight), DateTime.utc(2026, 8, 15));
      // 18:55 UTC is 23:55 the same day in Karachi — a different day from the above.
      expect(
        AppDates.pktDayKey(DateTime.utc(2026, 8, 14, 18, 55)),
        DateTime.utc(2026, 8, 14),
      );
      expect(
        AppDates.isSamePktDay(lateNight, DateTime.utc(2026, 8, 14, 18, 55)),
        isFalse,
      );
    });

    test('English uses a 12-hour clock with a marker', () {
      expect(AppDates.time(DateTime.utc(2026, 8, 14, 15, 30)), '8:30 PM');
    });

    test('URDU uses a 24-hour clock, because CLDR gives it a useless "p"', () {
      // DateFormat('h:mm a', 'ur') renders this as "8:30 p", which an Urdu reader cannot
      // tell from 8:30 in the morning. 24-hour needs no marker and matches the booths'
      // printed receipts, which use %H:%M:%S.
      expect(
        AppDates.time(DateTime.utc(2026, 8, 14, 15, 30), locale: 'ur'),
        '20:30',
      );
      expect(
        AppDates.time(DateTime.utc(2026, 8, 14, 3, 30), locale: 'ur'),
        '08:30',
      );
      // And it never contains the ambiguous marker.
      expect(
        AppDates.time(DateTime.utc(2026, 8, 14, 15, 30), locale: 'ur'),
        isNot(contains('p')),
      );
    });

    test('the Urdu date uses Urdu month names', () {
      expect(AppDates.date(lateNight, locale: 'ur'), contains('اگست'));
    });

    test('dateTime combines both correctly per locale', () {
      expect(AppDates.dateTime(lateNight), '15 Aug 2026, 2:55 AM');
      expect(AppDates.dateTime(lateNight, locale: 'ur'), contains('02:55'));
    });

    test('null renders as a dash everywhere', () {
      expect(AppDates.date(null), '—');
      expect(AppDates.time(null), '—');
      expect(AppDates.dateTime(null), '—');
      expect(AppDates.dayHeader(null), '—');
    });
  });

  group('daysUntil', () {
    test('compares PKT calendar days, not elapsed hours', () {
      // At 23:00 Karachi, a tag expiring "tomorrow" must read as 1, not 0.
      final nowUtc = DateTime.utc(2026, 8, 14, 18); // 23:00 PKT on the 14th
      expect(
        AppDates.daysUntil(DateTime.utc(2026, 8, 15), now: nowUtc),
        1,
      );
      expect(
        AppDates.daysUntil(DateTime.utc(2026, 8, 14), now: nowUtc),
        0,
      );
      expect(
        AppDates.daysUntil(DateTime.utc(2026, 8, 13), now: nowUtc),
        -1,
      );
    });
  });

  group('relative', () {
    final now = DateTime.utc(2026, 8, 14, 12);

    test('describes the age of a cached read', () {
      expect(AppDates.relative(now, now: now), 'just now');
      expect(
        AppDates.relative(now.subtract(const Duration(minutes: 1)), now: now),
        '1 minute ago',
      );
      expect(
        AppDates.relative(now.subtract(const Duration(minutes: 4)), now: now),
        '4 minutes ago',
      );
      expect(
        AppDates.relative(now.subtract(const Duration(hours: 3)), now: now),
        '3 hours ago',
      );
      expect(
        AppDates.relative(now.subtract(const Duration(days: 2)), now: now),
        '2 days ago',
      );
    });

    test('falls back to a date past a week', () {
      expect(
        AppDates.relative(now.subtract(const Duration(days: 30)), now: now),
        '15 Jul 2026',
      );
    });

    test('a clock skewed into the future reads as just now, not negative', () {
      expect(
        AppDates.relative(now.add(const Duration(minutes: 5)), now: now),
        'just now',
      );
    });
  });

  group('duration', () {
    test('formats the fractional minutes the server sends', () {
      expect(AppDates.duration(42), '42m');
      expect(AppDates.duration(42.4), '42m');
      expect(AppDates.duration(60), '1h');
      expect(AppDates.duration(84), '1h 24m');
      expect(AppDates.duration(125.6), '2h 6m');
      expect(AppDates.duration(null), '—');
    });
  });
}
