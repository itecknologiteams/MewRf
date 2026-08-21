import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/features/notifications/data/push_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// One push event, flattened out of [RemoteMessage].
///
/// The app reads `data`, never the notification's own title/body, for anything it acts on:
/// `notification` is the payload the SYSTEM tray renders and is absent on a data-only send,
/// while `data` is always there. Deciding what to refresh from a display string would break
/// the moment the wording changed.
class PushEvent {
  const PushEvent({
    required this.type,
    required this.title,
    required this.body,
    this.route,
  });

  factory PushEvent.fromMessage(RemoteMessage message) {
    final data = message.data;
    return PushEvent(
      type: data['type']?.toString() ?? '',
      title: message.notification?.title ?? '',
      body: message.notification?.body ?? '',
      // Built by the server (`/activity?account=…`, `/topup?account=…`) so the tap target
      // stays a server decision and does not have to be re-derived here per type.
      route: (data['route']?.toString().isEmpty ?? true)
          ? null
          : data['route'].toString(),
    );
  }

  final String type;
  final String title;
  final String body;
  final String? route;

  /// Money moved. Every one of these invalidates a balance the app is displaying.
  bool get affectsBalance => type == 'transaction' || type == 'topup_failed';
}

class PushState {
  const PushState({
    required this.availability,
    required this.optedIn,
    this.serverCanSend = false,
    this.token,
  });

  final PushAvailability availability;

  /// The user's own choice, persisted. Separate from [availability]: a user who has opted
  /// in on a build with no Firebase config is not "off", they are waiting on a build fix,
  /// and the UI has to be able to say which.
  final bool optedIn;

  /// Whether the BACKEND has FCM credentials. A perfectly valid token on a deployment with
  /// no service-account file receives nothing, so both halves must be true before the app
  /// tells anyone that alerts are working.
  final bool serverCanSend;

  final String? token;

  bool get isWorking =>
      optedIn && availability == PushAvailability.ready && serverCanSend;

  PushState copyWith({
    PushAvailability? availability,
    bool? optedIn,
    bool? serverCanSend,
    String? token,
    bool clearToken = false,
  }) => PushState(
    availability: availability ?? this.availability,
    optedIn: optedIn ?? this.optedIn,
    serverCanSend: serverCanSend ?? this.serverCanSend,
    token: clearToken ? null : (token ?? this.token),
  );
}

/// Owns the device token's lifecycle against the session.
///
/// Three things happen here that are easy to leave out and invisible when missing:
///
///   1. **Register on sign-in.** A token is meaningless until the server knows whose it is.
///   2. **Unregister on sign-out, BEFORE the cookies go.** The endpoint is authenticated
///      and scoped to `request.user`, so unregistering after the session is cleared 401s
///      and leaves the row — meaning the next person to hold the phone keeps receiving the
///      previous user's balance alerts. That is a privacy leak, not a missing feature.
///   3. **Re-register on rotation.** FCM rotates tokens routinely and the server cannot
///      detect a stale one: sends just stop arriving, silently, forever.
class PushController extends AsyncNotifier<PushState> {
  static const _optInKey = 'mtag_push_opt_in';

  PushService? _service;
  StreamSubscription<PushRegistration>? _refreshSub;

  /// Foreground events, for whoever is listening (the app shell shows a banner and
  /// refreshes the wallet). A broadcast controller because more than one listener is
  /// legitimate and a single-subscription stream would throw on the second.
  final _events = StreamController<PushEvent>.broadcast();

  Stream<PushEvent> get events => _events.stream;

  /// Notifications the user TAPPED, which brought the app back from the background.
  ///
  /// Kept separate from [events] because the two mean opposite things to the UI: a
  /// foreground message is news to show in place, a tap is an instruction to navigate. One
  /// stream carrying both would send a user to the Activity tab because a toll was charged
  /// while they were mid-top-up.
  final _taps = StreamController<PushEvent>.broadcast();

  Stream<PushEvent> get taps => _taps.stream;

  /// The notification that launched the app from a terminated state, if any.
  ///
  /// A one-shot pull rather than a stream event: the tap happened before this object
  /// existed, so there was no listener to receive it. Returns null on a normal launch.
  Future<PushEvent?> initialTap() async {
    final service = _service;
    if (service == null) return null;
    final message = await service.initialMessage();
    return message == null ? null : PushEvent.fromMessage(message);
  }

  @override
  Future<PushState> build() async {
    ref.onDispose(() {
      unawaited(_refreshSub?.cancel());
      unawaited(_events.close());
      unawaited(_taps.close());
    });

    // WATCHED FIRST, before any await.
    //
    // Riverpod registers a dependency only for `ref.watch` calls made synchronously during
    // build. This used to sit after `await _readOptIn()`, which reads SharedPreferences —
    // so by the time the session was watched the synchronous phase was over, the dependency
    // was never recorded, and this provider did not rebuild when the user signed in.
    //
    // The effect was a device that never registered its token: `/notifications/status/`
    // reported `devices: []` for a signed-in user, so the server had nowhere to send a
    // notification and push appeared to be broken end to end. Nothing threw — the provider
    // simply held its first value forever.
    final session = ref.watch(sessionControllerProvider).value;
    final optedIn = await _readOptIn();

    // Not signed in: nothing to register a token against. Deliberately does NOT initialise
    // Firebase — asking for notification permission on the login screen, before the app has
    // said what the alerts are for, is the most reliably denied prompt there is.
    if (session is! SessionSignedIn) {
      return PushState(
        availability: PushAvailability.notConfigured,
        optedIn: optedIn,
      );
    }

    if (!optedIn) {
      return const PushState(
        availability: PushAvailability.permissionDenied,
        optedIn: false,
      );
    }

    return _enable(optedIn: true);
  }

  Future<PushState> _enable({required bool optedIn}) async {
    final service = _service ??= PushService();
    final availability = await service.initialise();
    if (availability != PushAvailability.ready) {
      return PushState(availability: availability, optedIn: optedIn);
    }

    final permission = await service.requestPermission();
    if (permission != PushAvailability.ready) {
      return PushState(availability: permission, optedIn: optedIn);
    }

    final registration = await service.registration();
    if (registration == null) {
      // A device with no Play services, or an iOS simulator with no APNS token. Not an
      // error to show anyone.
      return PushState(
        availability: PushAvailability.unsupported,
        optedIn: optedIn,
      );
    }

    var serverCanSend = false;
    try {
      final status = await ref
          .read(pushRepositoryProvider)
          .register(
            token: registration.token,
            platform: registration.platform,
          );
      serverCanSend = status.serverCanSend;
    } on Object catch (error) {
      // Registration is not worth failing a session over: the app works without push. The
      // token is retried on the next cold start and on the next rotation.
      debugPrint('Push: register failed ($error).');
    }

    _listen(service);

    return PushState(
      availability: PushAvailability.ready,
      optedIn: optedIn,
      serverCanSend: serverCanSend,
      token: registration.token,
    );
  }

  void _listen(PushService service) {
    unawaited(_refreshSub?.cancel());
    _refreshSub = service.onTokenRefresh.listen((registration) async {
      try {
        await ref.read(pushRepositoryProvider).register(
          token: registration.token,
          platform: registration.platform,
        );
        final current = state.value;
        if (current != null) {
          state = AsyncValue.data(current.copyWith(token: registration.token));
        }
      } on Object catch (error) {
        debugPrint('Push: re-register after rotation failed ($error).');
      }
    });

    service.onForegroundMessage.listen((message) {
      if (_events.isClosed) return;
      _events.add(PushEvent.fromMessage(message));
    });

    service.onMessageOpened.listen((message) {
      if (_taps.isClosed) return;
      _taps.add(PushEvent.fromMessage(message));
    });
  }

  /// Turns alerts on, asking for permission if needed.
  Future<void> optIn() async {
    await _writeOptIn(true);
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _enable(optedIn: true));
  }

  /// Turns alerts off and drops the token, so nothing arrives after the switch flips.
  Future<void> optOut() async {
    await _writeOptIn(false);
    await _releaseToken();
    state = const AsyncValue.data(
      PushState(availability: PushAvailability.permissionDenied, optedIn: false),
    );
  }

  /// Releases this device's token from the CURRENT session.
  ///
  /// Must be awaited by the sign-out path before cookies are cleared — see the class doc.
  Future<void> releaseForSignOut() => _releaseToken();

  Future<void> _releaseToken() async {
    final token = state.value?.token;
    await _refreshSub?.cancel();
    _refreshSub = null;

    if (token != null) {
      try {
        await ref.read(pushRepositoryProvider).unregister(token: token);
      } on Object catch (error) {
        // Best effort. The local delete below still stops delivery to this install even if
        // the row survives on the server.
        debugPrint('Push: server unregister failed ($error).');
      }
    }
    await _service?.deleteToken();
  }

  Future<bool> _readOptIn() async {
    final prefs = await SharedPreferences.getInstance();
    // Default ON. Money alerts are the reason a toll wallet is worth opening — a user who
    // is charged without being told has to go looking for it. The platform permission
    // prompt is still the real gate on Android 13+, so this default cannot notify anyone
    // who has not agreed at the OS level.
    return prefs.getBool(_optInKey) ?? true;
  }

  Future<void> _writeOptIn(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_optInKey, value);
  }
}

final pushControllerProvider =
    AsyncNotifierProvider<PushController, PushState>(PushController.new);
