import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';

final FlutterLocalNotificationsPlugin _localNotifications =
    FlutterLocalNotificationsPlugin();

@pragma('vm:entry-point')
Future<void> firebaseBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}

class NotificationService {
  static const _channelId = 'progoz_alerts';
  static const _channelName = 'PROGÖZ Uyarılar';

  final _messaging = FirebaseMessaging.instance;

  Future<void> initialize({
    required void Function(RemoteMessage) onMessage,
  }) async {
    if (kIsWeb) return;

    await _requestPermission();
    await _initLocalNotifications();

    FirebaseMessaging.onBackgroundMessage(firebaseBackgroundHandler);

    FirebaseMessaging.onMessage.listen((message) {
      _showLocalNotification(message);
      onMessage(message);
    });

    await _saveFcmToken();
    _messaging.onTokenRefresh.listen((token) {
      _saveTokenToPrefs(token);
    });
  }

  Future<void> _requestPermission() async {
    await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
  }

  Future<void> _initLocalNotifications() async {
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const settings = InitializationSettings(android: android);
    await _localNotifications.initialize(settings);

    const channel = AndroidNotificationChannel(
      _channelId,
      _channelName,
      importance: Importance.high,
    );
    await _localNotifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);
  }

  Future<void> _saveFcmToken() async {
    final token = await _messaging.getToken();
    if (token != null) await _saveTokenToPrefs(token);
  }

  Future<void> _saveTokenToPrefs(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('fcm_token', token);
  }

  Future<String?> getFcmToken() async {
    if (kIsWeb) return null;
    return _messaging.getToken();
  }

  void _showLocalNotification(RemoteMessage message) {
    if (kIsWeb) return;
    final notification = message.notification;
    if (notification == null) return;

    const details = AndroidNotificationDetails(
      _channelId,
      _channelName,
      importance: Importance.high,
      priority: Priority.high,
    );

    _localNotifications.show(
      notification.hashCode,
      notification.title,
      notification.body,
      const NotificationDetails(android: details),
    );
  }
}
