import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/network/api_envelope.dart';

/// The envelope parser is the single place every response passes through, so a bug here
/// is a bug in every screen. These tests pin the shapes the Django backend actually
/// sends, including the awkward ones.
void main() {
  group('ApiEnvelope', () {
    test('unwraps a successful object response', () {
      final envelope = ApiEnvelope.parse<Map<String, dynamic>>(
        {
          'success': true,
          'message': 'Success',
          'data': {'id': 7, 'balance': '1250.00'},
        },
        (data) => data as Map<String, dynamic>,
      );

      expect(envelope.success, isTrue);
      expect(envelope.required['id'], 7);
      expect(envelope.required['balance'], '1250.00');
    });

    test('accepts data:null on endpoints that legitimately return none', () {
      // /auth/logout/ and /auth/change-password/ both succeed with data: null.
      final envelope = ApiEnvelope.parse<Map<String, dynamic>>(
        {'success': true, 'message': 'Logged out successfully', 'data': null},
        (data) => data as Map<String, dynamic>,
      );

      expect(envelope.data, isNull);
      expect(() => envelope.required, throwsA(isA<MalformedResponseFailure>()));
    });

    test('success:false becomes a ValidationFailure carrying field errors', () {
      expect(
        () => ApiEnvelope.parse<void>(
          {
            'success': false,
            'message': 'Registration failed',
            'errors': {
              'phone': ['This field must be unique.'],
            },
          },
          null,
        ),
        throwsA(
          isA<ValidationFailure>()
              .having((f) => f.message, 'message', 'Registration failed')
              .having(
                (f) => f.fieldErrors?['phone'],
                'phone error',
                'This field must be unique.',
              ),
        ),
      );
    });

    test('a body with no `success` key is malformed, not empty', () {
      // The real-world case: a captive portal or a proxy returning HTML with a 200.
      // Reporting that as "no data" would show an empty wallet instead of an error.
      expect(
        () => ApiEnvelope.parse<void>({'detail': 'Not found'}, null),
        throwsA(isA<MalformedResponseFailure>()),
      );
      expect(
        () => ApiEnvelope.parse<void>('<html>hello</html>', null),
        throwsA(isA<MalformedResponseFailure>()),
      );
    });
  });

  group('flattenFieldErrors', () {
    test('joins a list of messages for one field', () {
      final errors = flattenFieldErrors({
        'amount': ['Must be at least 100.', 'Required.'],
      });
      expect(errors?['amount'], 'Must be at least 100. Required.');
    });

    test('handles a bare string, which DRF also produces', () {
      expect(flattenFieldErrors({'detail': 'Nope'})?['detail'], 'Nope');
    });

    test('flattens a nested map', () {
      final errors = flattenFieldErrors({
        'vehicle': {
          'plate_number': ['Already taken.'],
        },
      });
      expect(errors?['vehicle'], 'Already taken.');
    });

    test('keeps non_field_errors, which is where login failures arrive', () {
      // LoginSerializer.validate raises on the whole payload, so bad credentials and a
      // blocked account BOTH land here rather than under `phone` or `password`. A form
      // that only looked at per-field keys would show no error at all.
      final errors = flattenFieldErrors({
        'non_field_errors': ['Account is blocked. Contact support.'],
      });
      expect(
        errors?['non_field_errors'],
        'Account is blocked. Contact support.',
      );
    });

    test('returns null rather than an empty map when there is nothing', () {
      expect(flattenFieldErrors(null), isNull);
      expect(flattenFieldErrors('not a map'), isNull);
      expect(flattenFieldErrors(<String, dynamic>{}), isNull);
    });
  });

  group('PagedEnvelope', () {
    Map<String, dynamic> body({
      required int count,
      required int page,
      required int totalPages,
      String? next,
    }) => {
      'success': true,
      'message': 'Success',
      'data': [
        {'id': 1},
        {'id': 2},
      ],
      'meta': {
        'count': count,
        'next': next,
        'previous': null,
        'total_pages': totalPages,
        'current_page': page,
      },
    };

    test('parses items and meta', () {
      final page = PagedEnvelope.parse<int>(
        body(count: 137, page: 1, totalPages: 7, next: 'http://x/?page=2'),
        (json) => json['id'] as int,
      );

      expect(page.items, [1, 2]);
      expect(page.meta.count, 137);
      expect(page.meta.totalPages, 7);
      expect(page.meta.hasMore, isTrue);
      expect(page.meta.nextPage, 2);
    });

    test('hasMore is false on the last page even if next is set', () {
      final page = PagedEnvelope.parse<int>(
        body(count: 2, page: 7, totalPages: 7, next: 'http://x/?page=8'),
        (json) => json['id'] as int,
      );
      expect(page.meta.hasMore, isFalse);
    });

    test('synthesises a single page for an unpaginated list endpoint', () {
      // /vehicles/my/, /tolls/plazas/, /tolls/rates/ and /payments/history/ all return
      // bare arrays with no `meta`. Wrapping them keeps the list widgets uniform.
      final page = PagedEnvelope.parse<int>(
        {
          'success': true,
          'message': 'Success',
          'data': [
            {'id': 1},
            {'id': 2},
            {'id': 3},
          ],
        },
        (json) => json['id'] as int,
      );

      expect(page.items.length, 3);
      expect(page.meta.count, 3);
      expect(page.meta.totalPages, 1);
      expect(page.meta.hasMore, isFalse);
    });

    test('rejects a non-list `data` on a paginated read', () {
      expect(
        () => PagedEnvelope.parse<int>(
          {
            'success': true,
            'message': 'Success',
            'data': {'id': 1},
          },
          (json) => json['id'] as int,
        ),
        throwsA(isA<MalformedResponseFailure>()),
      );
    });

    test('append accumulates items and takes the newer meta', () {
      final first = PagedEnvelope.parse<int>(
        body(count: 4, page: 1, totalPages: 2, next: 'http://x/?page=2'),
        (json) => json['id'] as int,
      );
      final second = PagedEnvelope.parse<int>(
        body(count: 4, page: 2, totalPages: 2),
        (json) => json['id'] as int,
      );

      final combined = first.append(second);
      expect(combined.items.length, 4);
      expect(combined.meta.currentPage, 2);
      expect(combined.meta.hasMore, isFalse);
    });
  });
}
