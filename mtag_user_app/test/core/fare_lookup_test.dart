import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/toll.dart';

/// The fare-lookup join.
///
/// Two things here are easy to get wrong and impossible to notice from the UI:
///
///  1. **The join key.** `FareMatrix.from_plaza`/`to_plaza` hold plaza ROW ids, while
///     `plaza_id` (1, 2, 101–107) is the operator's number and `display_id` is that
///     zero-padded. Joining on the wrong one silently returns no fare, or the wrong one.
///  2. **Direction.** A→B and B→A are separate rows and `load_fares` writes both, so they
///     can differ. Falling back to the reverse would quote a price nobody is charged.
void main() {
  // Row ids deliberately unequal to plaza_ids, so a test passing while joining on the
  // wrong column is impossible.
  const shahfaisalRowId = 41;
  const kathorRowId = 42;
  const korangiRowId = 43;

  Fare fare({
    required int id,
    required int from,
    required int to,
    required String code,
    required int index,
    required String amount,
  }) => Fare(
    id: id,
    fromPlazaId: from,
    toPlazaId: to,
    categoryIndex: index,
    categoryCode: code,
    fare: Decimal.parse(amount),
    fromPlazaName: 'From $from',
    toPlazaName: 'To $to',
  );

  final matrix = FareMatrix([
    fare(
      id: 1,
      from: shahfaisalRowId,
      to: kathorRowId,
      code: 'car',
      index: 1,
      amount: '100.00',
    ),
    fare(
      id: 2,
      from: shahfaisalRowId,
      to: kathorRowId,
      code: 'wagon',
      index: 2,
      amount: '150.00',
    ),
    fare(
      id: 3,
      from: shahfaisalRowId,
      to: kathorRowId,
      code: 'truck_2axle',
      index: 5,
      amount: '350.00',
    ),
    fare(
      id: 4,
      from: shahfaisalRowId,
      to: kathorRowId,
      code: 'truck_4axle',
      index: 7,
      amount: '450.00',
    ),
    // Deliberately asymmetric.
    fare(
      id: 5,
      from: kathorRowId,
      to: shahfaisalRowId,
      code: 'car',
      index: 1,
      amount: '120.00',
    ),
    // Same plaza in and out — a legal combination the server explicitly allows.
    fare(
      id: 6,
      from: korangiRowId,
      to: korangiRowId,
      code: 'car',
      index: 1,
      amount: '60.00',
    ),
  ]);

  group('FareMatrix.lookup', () {
    test('joins on plaza row id and vehicle type', () {
      final result = matrix.lookup(
        fromPlazaId: shahfaisalRowId,
        toPlazaId: kathorRowId,
        vehicleType: VehicleType.car,
      );
      expect(result?.fare, Decimal.parse('100.00'));
    });

    test('distinguishes fare classes for the same route', () {
      // The reason the notification has eight classes: a wagon at 150 and a 4-axle truck
      // at 450 on the same road. Billing both as "car" was the bug that split them.
      Decimal? forType(VehicleType type) => matrix
          .lookup(
            fromPlazaId: shahfaisalRowId,
            toPlazaId: kathorRowId,
            vehicleType: type,
          )
          ?.fare;

      expect(forType(VehicleType.car), Decimal.parse('100.00'));
      expect(forType(VehicleType.wagon), Decimal.parse('150.00'));
      expect(forType(VehicleType.truck2Axle), Decimal.parse('350.00'));
      expect(forType(VehicleType.truck4Axle), Decimal.parse('450.00'));
    });

    test('A→B and B→A are different fares', () {
      final forward = matrix.lookup(
        fromPlazaId: shahfaisalRowId,
        toPlazaId: kathorRowId,
        vehicleType: VehicleType.car,
      );
      final reverse = matrix.lookup(
        fromPlazaId: kathorRowId,
        toPlazaId: shahfaisalRowId,
        vehicleType: VehicleType.car,
      );

      expect(forward?.fare, Decimal.parse('100.00'));
      expect(reverse?.fare, Decimal.parse('120.00'));
      expect(forward?.fare == reverse?.fare, isFalse);
    });

    test(
      'a missing direction returns null and does NOT fall back to the reverse',
      () {
        // Only car has a Kathor→Shahfaisal row. A wagon must get "no fare set" rather than
        // the forward figure, which it would not be charged.
        final result = matrix.lookup(
          fromPlazaId: kathorRowId,
          toPlazaId: shahfaisalRowId,
          vehicleType: VehicleType.wagon,
        );
        expect(result, isNull);
      },
    );

    test(
      'entering and exiting at the same plaza is a real, chargeable row',
      () {
        final result = matrix.lookup(
          fromPlazaId: korangiRowId,
          toPlazaId: korangiRowId,
          vehicleType: VehicleType.car,
        );
        expect(result?.fare, Decimal.parse('60.00'));
      },
    );

    test('an unknown fare class finds nothing rather than guessing', () {
      final result = matrix.lookup(
        fromPlazaId: shahfaisalRowId,
        toPlazaId: kathorRowId,
        vehicleType: VehicleType.unknown,
      );
      expect(result, isNull);
    });

    test('availableTypes reports only classes the operator has published', () {
      expect(matrix.availableTypes, {
        VehicleType.car,
        VehicleType.wagon,
        VehicleType.truck2Axle,
        VehicleType.truck4Axle,
      });
      // Offering a class with no rows would produce "no fare set" for something the app
      // itself suggested.
      expect(matrix.availableTypes.contains(VehicleType.largeBus), isFalse);
    });

    test(
      'vehicleType maps from category_code, which mirrors Vehicle.vehicle_type',
      () {
        final row = matrix.fares.firstWhere(
          (f) => f.categoryCode == 'truck_2axle',
        );
        expect(row.vehicleType, VehicleType.truck2Axle);
        expect(row.categoryIndex, 5);
      },
    );
  });

  group('Plaza id semantics', () {
    test('displayId zero-pads plaza_id and is not the row id', () {
      const plaza = Plaza(
        id: 41,
        plazaId: 1,
        name: 'Shahfaisal Main Toll Plaza',
        isActive: true,
      );
      expect(plaza.displayId, '001');
      expect(plaza.id, isNot(plaza.plazaId));
    });

    test('a three-digit plaza_id is unchanged by padding', () {
      const plaza = Plaza(
        id: 47,
        plazaId: 107,
        name: 'Mai Niyari',
        isActive: true,
      );
      expect(plaza.displayId, '107');
    });
  });

  group('parsing from the API shape', () {
    test('category arrives as the integer category_index', () {
      final parsed = Fare.fromApi({
        'id': 9,
        'from_plaza': 41,
        'to_plaza': 42,
        'from_plaza_name': 'Shahfaisal Main Toll Plaza',
        'to_plaza_name': 'Kathor Main Toll Plaza',
        'from_plaza_display_id': '001',
        'to_plaza_display_id': '002',
        'category': 5,
        'category_code': 'truck_2axle',
        'category_name': '2 Axle Truck',
        'fare': '350.00',
      });

      expect(parsed.categoryIndex, 5);
      expect(parsed.vehicleType, VehicleType.truck2Axle);
      expect(parsed.fare, Decimal.parse('350.00'));
      expect(parsed.fromPlazaDisplayId, '001');
    });
  });
}
