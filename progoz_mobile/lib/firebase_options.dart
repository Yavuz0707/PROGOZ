import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      default:
        throw UnsupportedError(
          'Bu platform için FirebaseOptions tanımlı değil.',
        );
    }
  }

  // Web app'i Firebase konsolunda oluşturup buraya web config'i yapıştırın.
  // Firebase Console → Project Settings → Your apps → Web app → Config
  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyCxfR_lzwFisDuDL9JOSlcFO0L5tkfz3rM',
    appId: '1:814845663832:web:000000000000000000000000',
    messagingSenderId: '814845663832',
    projectId: 'progoz',
    storageBucket: 'progoz.firebasestorage.app',
  );

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyCxfR_lzwFisDuDL9JOSlcFO0L5tkfz3rM',
    appId: '1:814845663832:android:008222e492229cb8c7882d',
    messagingSenderId: '814845663832',
    projectId: 'progoz',
    storageBucket: 'progoz.firebasestorage.app',
  );
}
