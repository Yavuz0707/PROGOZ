import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';
import 'config/theme.dart';
import 'firebase_options.dart';
import 'providers/auth_provider.dart';
import 'providers/incidents_provider.dart';
import 'providers/plates_provider.dart';
import 'providers/settings_provider.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'services/notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('tr_TR', null);
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
  } catch (e) {
    debugPrint('Firebase init error: $e');
  }
  runApp(const ProgozApp());
}

class ProgozApp extends StatelessWidget {
  const ProgozApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => IncidentsProvider()),
        ChangeNotifierProvider(create: (_) => PlatesProvider()),
        ChangeNotifierProvider(create: (_) => SettingsProvider()),
      ],
      child: MaterialApp(
        title: 'PROGÖZ',
        theme: buildDarkTheme(),
        home: const _AppRouter(),
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}

class _AppRouter extends StatefulWidget {
  const _AppRouter();

  @override
  State<_AppRouter> createState() => _AppRouterState();
}

class _AppRouterState extends State<_AppRouter> {
  final _notificationService = NotificationService();

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final auth = context.read<AuthProvider>();
    final settings = context.read<SettingsProvider>();
    await settings.load();
    await auth.checkAuth();

    await _notificationService.initialize(
      onMessage: (message) {
        if (!mounted) return;
        final incidents = context.read<IncidentsProvider>();
        if (message.data.isNotEmpty) {
          incidents.addIncidentFromNotification(message.data);
        } else {
          incidents.load();
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final status = context.watch<AuthProvider>().status;

    return switch (status) {
      AuthStatus.unknown => Scaffold(
          body: Container(
            decoration: const BoxDecoration(gradient: AppColors.bgGradient),
            child: const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            ),
          ),
        ),
      AuthStatus.authenticated => const HomeScreen(),
      AuthStatus.unauthenticated => const LoginScreen(),
    };
  }
}
