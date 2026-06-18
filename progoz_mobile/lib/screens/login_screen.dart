import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../config/theme.dart';
import '../providers/auth_provider.dart';
import '../providers/settings_provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _serverController = TextEditingController(text: kDefaultBaseUrl);
  bool _obscurePassword = true;
  bool _serverInitialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_serverInitialized) return;
    _serverController.text = context.read<SettingsProvider>().serverUrl;
    _serverInitialized = true;
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _serverController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    final serverUrl = _normalizeServerUrl(_serverController.text);
    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Kullanıcı adı ve şifre boş olamaz'),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }
    if (serverUrl.isEmpty || !serverUrl.startsWith('http')) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Sunucu adresi http://... formatinda olmali'),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }

    await context.read<SettingsProvider>().setServerUrl(serverUrl);
    final auth = context.read<AuthProvider>();
    final success = await auth.login(username, password);
    if (!success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(auth.error ?? 'Giriş başarısız'),
          backgroundColor: AppColors.error,
        ),
      );
    }
  }

  String _normalizeServerUrl(String value) {
    var text = value.trim();
    while (text.endsWith('/')) {
      text = text.substring(0, text.length - 1);
    }
    return text;
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.bgGradient),
        child: Stack(
          children: [
            // Arka plan glow lekeleri kaldırıldı (monokrom, düz zemin — gölge/glow yok).
            SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight:
                        MediaQuery.of(context).size.height -
                        MediaQuery.of(context).padding.vertical,
                  ),
                  child: IntrinsicHeight(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _buildLogo(),
                        const SizedBox(height: 36),
                        _GlassField(
                          controller: _serverController,
                          label: 'Sunucu Adresi',
                          icon: Icons.dns_outlined,
                          textInputAction: TextInputAction.next,
                        ),
                        const SizedBox(height: 16),
                        _GlassField(
                          controller: _usernameController,
                          label: 'Kullanıcı Adı',
                          icon: Icons.person_outline,
                          textInputAction: TextInputAction.next,
                        ),
                        const SizedBox(height: 16),
                        _GlassField(
                          controller: _passwordController,
                          label: 'Şifre',
                          icon: Icons.lock_outline,
                          obscureText: _obscurePassword,
                          textInputAction: TextInputAction.done,
                          onSubmitted: (_) => _login(),
                          suffix: IconButton(
                            icon: Icon(
                              _obscurePassword
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                              color: AppColors.textSecondary,
                            ),
                            onPressed: () => setState(
                              () => _obscurePassword = !_obscurePassword,
                            ),
                          ),
                        ),
                        const SizedBox(height: 32),
                        _GlowButton(loading: auth.loading, onTap: _login),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLogo() {
    return Column(
      children: [
        // PROGÖZ logosu (assets/images/progoz_logo.png).
        // Dosya yoksa kırılmaz — çerçeveli güvenlik ikonuna düşer.
        SizedBox(
          width: 260,
          height: 150,
          child: Image.asset(
            'assets/images/progoz_logo.png',
            fit: BoxFit.contain,
            filterQuality: FilterQuality.medium,
            errorBuilder: (context, error, stack) => Container(
              width: 92,
              height: 92,
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.border),
              ),
              child: const Icon(
                Icons.security,
                size: 48,
                color: AppColors.primary,
              ),
            ),
          ),
        ),
        const SizedBox(height: 22),
        const Text(
          'PROGÖZ',
          style: TextStyle(
            fontSize: 34,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
            letterSpacing: 7,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Güvenlik Sistemi',
          style: TextStyle(
            color: AppColors.textSecondary,
            fontSize: 14,
            letterSpacing: 1,
          ),
        ),
      ],
    );
  }
}

class _GlassField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final bool obscureText;
  final Widget? suffix;
  final TextInputAction textInputAction;
  final ValueChanged<String>? onSubmitted;

  const _GlassField({
    required this.controller,
    required this.label,
    required this.icon,
    this.obscureText = false,
    this.suffix,
    this.textInputAction = TextInputAction.next,
    this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      obscureText: obscureText,
      autocorrect: false,
      textInputAction: textInputAction,
      onSubmitted: onSubmitted,
      style: const TextStyle(color: AppColors.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, color: AppColors.textSecondary),
        suffixIcon: suffix,
      ),
    );
  }
}

class _GlowButton extends StatelessWidget {
  final bool loading;
  final VoidCallback onTap;
  const _GlowButton({required this.loading, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return TapScale(
      onTap: loading ? null : onTap,
      child: Container(
        height: 54,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.circular(12),
        ),
        child: loading
            ? const SizedBox(
                height: 22,
                width: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.4,
                  color: Colors.black,
                ),
              )
            : const Text(
                'Giriş Yap',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Colors.black,
                ),
              ),
      ),
    );
  }
}
