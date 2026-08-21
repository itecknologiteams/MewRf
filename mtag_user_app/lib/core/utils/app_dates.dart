import 'package:intl/intl.dart';

/// Dates, always rendered in Pakistan Standard Time.
///
/// Django runs `USE_TZ = True` with `TIME_ZONE = 'Asia/Karachi'` and serialises
/// timestamps in ISO-8601 with an offset, so a parsed `DateTime` is correct but in
/// whatever zone the phone is set to. That matters here: a trip taken at 01:00
/// local shows as the previous day on a device set to UTC, and "grouped by day"
/// history would put a driver's late-night trips under the wrong heading.
///
/// PKT is a **fixed UTC+05:00**. Pakistan has observed no DST since 2009, so a
/// fixed offset is exact today and avoids shipping the ~500KB tz database for one
/// zone. If DST is ever reintroduced this file is the only thing that has to
/// change — swap in `package:timezone` and keep the same API.
abstract final class AppDates {
  static const Duration pktOffset = Duration(hours: 5);
  static const String pktLabel = 'PKT';

  /// Parses a server timestamp into UTC.
  ///
  /// `DateTime.parse` honours the offset in the string and yields a local-zone
  /// instant; normalising to UTC first means every later conversion starts from
  /// the same place regardless of the device's zone.
  static DateTime? tryParseUtc(Object? raw) {
    if (raw == null) return null;
    if (raw is DateTime) return raw.toUtc();

    final text = raw.toString().trim();

    // A bare `YYYY-MM-DD` — which is exactly what a Django `DateField` sends, and
    // `Tag.expiry_date` is one.
    //
    // `DateTime.parse('2099-12-31')` returns a LOCAL midnight, so `.toUtc()` then shifts
    // it by the device's offset: on a phone in Karachi the expiry silently becomes
    // 2099-12-30 19:00Z. That is a day earlier, and it is precisely the input to
    // `daysUntilExpiry` — so the "expires in N days" warning would be off by one for
    // every user east of Greenwich, and would fire a day late for everyone west of it.
    //
    // A date with no time carries no zone, so treating it as UTC midnight is the only
    // reading that does not invent an offset.
    if (RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) {
      return DateTime.tryParse('${text}T00:00:00Z');
    }

    return DateTime.tryParse(text)?.toUtc();
  }

  /// An instant shifted into PKT wall-clock time.
  ///
  /// The result is flagged `isUtc` but holds Karachi wall-clock fields. That is a
  /// deliberate lie to `DateTime`: it is the only way to get Karachi field values
  /// out of a formatter without a tz database, and it must never be used for
  /// arithmetic against another instant. Format it and discard it.
  static DateTime toPkt(DateTime instant) => instant.toUtc().add(pktOffset);

  /// `14 Aug 2026`
  static String date(DateTime? instant, {String locale = 'en'}) =>
      instant == null
      ? '—'
      : DateFormat('d MMM yyyy', locale).format(toPkt(instant));

  /// `14 Aug 2026, 8:42 PM` — `14 اگست 2026, 20:42` in Urdu. See [_timePattern].
  static String dateTime(DateTime? instant, {String locale = 'en'}) =>
      instant == null
      ? '—'
      : DateFormat(
          'd MMM yyyy, ${_timePattern(locale)}',
          locale,
        ).format(toPkt(instant));

  /// `8:42 PM` — `20:42` in Urdu. See [_timePattern].
  static String time(DateTime? instant, {String locale = 'en'}) =>
      instant == null
      ? '—'
      : DateFormat(_timePattern(locale), locale).format(toPkt(instant));

  /// 12-hour with a marker in English, **24-hour in Urdu**.
  ///
  /// Not a stylistic choice. CLDR's `ur` data abbreviates the day period to a bare Latin
  /// `a`/`p`, so `DateFormat('h:mm a', 'ur')` renders 20:30 as **"8:30 p"** — which an
  /// Urdu reader cannot tell from 8:30 in the morning. On a trip row that means a driver
  /// checking which of two journeys they are looking at gets the wrong answer.
  ///
  /// 24-hour needs no marker, is unambiguous, and matches the printed receipts the booths
  /// already issue — `apps/accounts/views.py` formats those with `%H:%M:%S`. So a time in
  /// the app reads the same as the time on the paper receipt for the same transaction.
  static String _timePattern(String locale) =>
      locale.startsWith('ur') ? 'HH:mm' : 'h:mm a';

  /// `Thursday, 14 August` — a sticky day header in a transaction list.
  static String dayHeader(DateTime? instant, {String locale = 'en'}) =>
      instant == null
      ? '—'
      : DateFormat('EEEE, d MMMM', locale).format(toPkt(instant));

  /// The PKT calendar day an instant falls on, as a key for grouping.
  ///
  /// Grouping on the raw UTC date would split a single Karachi evening across two
  /// headings for anyone whose phone is west of Pakistan.
  static DateTime pktDayKey(DateTime instant) {
    final pkt = toPkt(instant);
    return DateTime.utc(pkt.year, pkt.month, pkt.day);
  }

  static bool isSamePktDay(DateTime a, DateTime b) =>
      pktDayKey(a) == pktDayKey(b);

  /// Whole days from now until [date], negative if already past.
  ///
  /// Compared on PKT calendar days rather than elapsed hours, so a tag expiring
  /// "tomorrow" reads as 1 rather than 0 at 23:00.
  static int daysUntil(DateTime date, {DateTime? now}) {
    final today = pktDayKey(now ?? DateTime.now().toUtc());
    return pktDayKey(date).difference(today).inDays;
  }

  /// `2 minutes ago`, `3 hours ago`, `14 Aug` — the age of a cached read.
  ///
  /// Every cache-served balance in this app carries one of these. A stale balance
  /// shown without its age looks current, and the user makes a decision on it.
  static String relative(
    DateTime? instant, {
    DateTime? now,
    String locale = 'en',
  }) {
    if (instant == null) return '—';
    final delta = (now ?? DateTime.now().toUtc()).difference(instant.toUtc());

    if (delta.isNegative || delta.inSeconds < 45) return 'just now';
    if (delta.inMinutes < 60) {
      final m = delta.inMinutes;
      return '$m ${m == 1 ? 'minute' : 'minutes'} ago';
    }
    if (delta.inHours < 24) {
      final h = delta.inHours;
      return '$h ${h == 1 ? 'hour' : 'hours'} ago';
    }
    if (delta.inDays < 7) {
      final d = delta.inDays;
      return '$d ${d == 1 ? 'day' : 'days'} ago';
    }
    return date(instant, locale: locale);
  }

  /// Minutes as `1h 24m`, for a trip duration. The server sends this as a
  /// fractional double (`duration_minutes`).
  static String duration(double? minutes) {
    if (minutes == null) return '—';
    final total = minutes.round();
    if (total < 60) return '${total}m';
    final hours = total ~/ 60;
    final rest = total % 60;
    return rest == 0 ? '${hours}h' : '${hours}h ${rest}m';
  }
}
