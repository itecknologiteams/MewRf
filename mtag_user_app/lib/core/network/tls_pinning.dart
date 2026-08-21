import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:flutter/foundation.dart';
import 'package:mtag_user_app/core/env/app_env.dart';

/// Certificate pinning, on the prod flavour only.
///
/// Pinning is deliberately NOT applied to dev or lan. Those flavours run over
/// plain HTTP against a booth LAN with no certificate at all — `config.settings.lan`
/// sets `SESSION_COOKIE_SECURE = False` precisely because the toll LAN is
/// HTTP-only — so a pin there would either be vacuous or would break the profile
/// the operators actually test on.
///
/// The pins are SHA-256 hashes of the whole DER **certificate**, because that is
/// what Dart's `X509Certificate` gives access to — `cert.der`. Extracting the
/// SubjectPublicKeyInfo, which is what you would rather pin, needs an ASN.1 walk
/// this app does not carry.
///
/// The consequence is real and has to be planned for: a certificate pin breaks on
/// **every renewal**, even a renewal that reuses the same key. So
/// `MTAG_CERT_PINS` takes a list, at least two entries, and the next certificate's
/// pin must be added and shipped BEFORE the current one is replaced. The README's
/// openssl recipe produces exactly the string this file compares against.
void configureTlsPinning(Dio dio) {
  if (!AppEnv.isProd) return;

  // An explicit opt-out. Unpinned, but a DECISION rather than an omission, which is the
  // distinction the throw below exists to enforce.
  //
  // It is the correct choice against Let's Encrypt: the interceptor pins the leaf's DER,
  // certbot reissues that leaf roughly every 60 days, and the replacement's digest is
  // unknowable until it is issued — so a pinned build would fail closed at the first
  // renewal, for every install, with no app update able to arrive in time. Transport
  // security here rests on the platform trust store, HSTS and the manifest's cleartext
  // ban, which is the configuration Let's Encrypt itself recommends.
  //
  // To pin properly, pin the CA rather than the leaf — which needs the issuer chain, and
  // Dart's HttpClient exposes only the peer certificate. That is a larger change than a
  // flag, and it is why this is a sentinel and not a silent default.
  if (AppEnv.pinningExplicitlyDisabled) {
    assert(() {
      debugPrint(
        'TLS pinning DISABLED for this prod build (MTAG_CERT_PINS=none). '
        'Transport still requires HTTPS via the platform trust store.',
      );
      return true;
    }(), 'debugPrint always returns true');
    return;
  }

  final pins = AppEnv.certificatePins;
  if (pins.isEmpty) {
    // THROWS, and deliberately not `assert`.
    //
    // An assert is stripped from a release build, which is the only build this branch
    // can be reached in — so asserting here would mean a prod APK built without
    // MTAG_CERT_PINS ships completely unpinned while every code path and code review
    // says it is pinned. That is the worst possible outcome: a security control that is
    // absent and believed present.
    //
    // Failing at launch instead means the mistake is caught by whoever first opens the
    // build, which is QA, not a user. Same philosophy as AppEnv.resolvedApiBase
    // refusing a prod build with no base URL.
    throw StateError(
      'The prod flavour requires MTAG_CERT_PINS. Build with '
      '--dart-define=MTAG_CERT_PINS=sha256/AAA…=,sha256/BBB…= — supply at least two '
      'pins (the live certificate and its replacement), because a certificate pin '
      'breaks on every renewal and a single pin locks out every install the moment the '
      'certificate is rotated.\n\n'
      "If the host uses Let's Encrypt, pinning is NOT viable — the leaf is reissued "
      'about every 60 days and the next digest cannot be known in advance. Build with '
      '--dart-define=MTAG_CERT_PINS=none to opt out deliberately. '
      'See README § Certificate pinning.',
    );
  }

  final adapter = dio.httpClientAdapter;
  if (adapter is! IOHttpClientAdapter) return;

  adapter.createHttpClient = () {
    // badCertificateCallback fires only when the platform trust store has ALREADY
    // rejected the chain. Returning false keeps that rejection; the pin check below
    // is an additional constraint on chains the OS accepted, never a way to accept
    // one it did not.
    return HttpClient(context: SecurityContext(withTrustedRoots: true))
      ..badCertificateCallback = (cert, host, port) => false;
  };

  dio.interceptors.add(_PinValidationInterceptor(pins.toSet()));
}

/// Verifies the peer's SPKI pin after the handshake.
///
/// Dart's `HttpClient` exposes the peer certificate on the response, so the check
/// happens on the first response rather than during the handshake. That is one
/// round trip later than ideal — the request has been sent — but the cookies are
/// httpOnly and the request body carries no secret beyond the password on login,
/// and a mismatch aborts before any response body is handed to the app.
class _PinValidationInterceptor extends Interceptor {
  _PinValidationInterceptor(this._pins);

  final Set<String> _pins;

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    final cert = _certificateOf(response);
    if (cert == null) {
      // No certificate means no TLS, which on the prod flavour should be
      // impossible. Refuse rather than assume.
      handler.reject(
        DioException(
          requestOptions: response.requestOptions,
          type: DioExceptionType.badCertificate,
          error: 'No peer certificate on a pinned connection',
        ),
      );
      return;
    }

    if (!_matches(cert)) {
      handler.reject(
        DioException(
          requestOptions: response.requestOptions,
          type: DioExceptionType.badCertificate,
          error:
              'Certificate pin mismatch for ${response.requestOptions.uri.host}',
        ),
      );
      return;
    }

    handler.next(response);
  }

  X509Certificate? _certificateOf(Response<dynamic> response) {
    final raw = response.extra['secure_socket_certificate'];
    if (raw is X509Certificate) return raw;
    return null;
  }

  bool _matches(X509Certificate cert) {
    // `cert.der` is the whole certificate, so this hashes the certificate rather
    // than the SPKI. Extracting the SPKI needs an ASN.1 walk, which is why
    // computePin below is documented as the tool to generate the value — the two
    // must agree, and the openssl recipe in the README produces exactly this.
    final digest = sha256.convert(cert.der);
    final encoded = 'sha256/${base64.encode(digest.bytes)}';
    return _pins.contains(encoded);
  }
}

/// The pin string for a certificate, matching what [_PinValidationInterceptor]
/// computes. Debug helper — used to print the current host's pin during setup.
@visibleForTesting
String computePin(List<int> der) =>
    'sha256/${base64.encode(sha256.convert(der).bytes)}';
