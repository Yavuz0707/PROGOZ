import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ---------------------------------------------------------------------------
// PROGÖZ – "Obsidian Sentinel" monokrom güvenlik teması (Stitch referansı)
// Tüm renkler tek merkezde; gradient/glow/gölge KULLANILMAZ (düz, opak yüzeyler,
// 1px #2A2A2A kenarlık). Aksан renkler yalnız fonksiyonel alarm anlamı taşır.
// ---------------------------------------------------------------------------
class AppColors {
  // Yüzeyler (monokrom ton katmanlama)
  static const background = Color(0xFF141313); // ana zemin
  static const surface = Color(0xFF0D0D0D); // appbar / input / bottom nav zemini
  static const card = Color(0xFF161616); // kart zemini (düz)
  static const cardHover = Color(0xFF1C1B1B);
  static const surfaceVariant = Color(0xFF2A2A2A); // ikincil dolgu / track / badge
  static const border = Color(0xFF2A2A2A); // 1px kenarlık (her yerde)

  // Vurgu: saf beyaz (tek "marka" rengi, gradient yok)
  static const primary = Color(0xFFFFFFFF);
  // ESKİ glow alanı — artık düz, nötr kenarlık rengi (API uyumu için isim korundu)
  static const primaryGlow = Color(0xFF2A2A2A);

  // Fonksiyonel alarm renkleri (yalnız KAVGA/OLASI_KAVGA/ŞÜPHELİ için)
  static const error = Color(0xFFFF3B30); // KAVGA
  static const warning = Color(0xFFFF9500); // OLASI_KAVGA
  static const caution = Color(0xFFFFCC00); // ŞÜPHELİ

  // Nötrleştirilmiş yardımcılar (eski mavi → gri/beyaz; dekoratif renk yok)
  static const info = Color(0xFFC4C7C8);
  static const plate = Color(0xFFFFFFFF);

  // Metin
  static const textPrimary = Color(0xFFFFFFFF);
  static const textSecondary = Color(0xFFC4C7C8); // on-surface-variant

  // Gradient'ler kaldırıldı — geri uyumluluk için isim korundu, tek renkli (düz).
  static const bgGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [background, background],
  );

  static const primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, primary],
  );

  static Color forLevel(String level) {
    switch (level.toUpperCase()) {
      case 'KAVGA':
        return error;
      case 'OLASI_KAVGA':
        return warning;
      case 'SUPHELI':
      case 'ŞÜPHELI':
      case 'SUSPECT':
        return caution;
      case 'PLATE':
      case 'PLAKA':
        return plate;
      default:
        return textSecondary;
    }
  }
}

// JetBrains Mono — plaka metni, zaman damgaları ve teknik etiketler için.
String get monoFontFamily => GoogleFonts.jetBrainsMono().fontFamily!;

ThemeData buildDarkTheme() {
  // Stitch referansı Geist istiyor; bu google_fonts sürümünde Geist yok.
  // En yakın eşdeğer olan Inter kullanıldı (aynı nötr-grotesk karakter, teknik okunabilirlik).
  final baseFont = GoogleFonts.inter().fontFamily;

  return ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AppColors.background,
    fontFamily: baseFont,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.primary,
      onPrimary: Colors.black,
      surface: AppColors.surface,
      error: AppColors.error,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: AppColors.textPrimary,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.black,
        elevation: 0,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.textPrimary,
        side: const BorderSide(color: AppColors.border),
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
        ),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
      ),
      labelStyle: const TextStyle(color: AppColors.textSecondary),
      hintStyle: const TextStyle(color: AppColors.textSecondary),
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: AppColors.surface,
      selectedItemColor: AppColors.primary,
      unselectedItemColor: AppColors.textSecondary,
      type: BottomNavigationBarType.fixed,
      elevation: 0,
    ),
    textTheme: const TextTheme(
      bodyLarge: TextStyle(color: AppColors.textPrimary),
      bodyMedium: TextStyle(color: AppColors.textPrimary),
      bodySmall: TextStyle(color: AppColors.textSecondary),
      titleLarge: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
      titleMedium: TextStyle(color: AppColors.textPrimary),
      titleSmall: TextStyle(color: AppColors.textSecondary),
    ),
    dividerColor: AppColors.border,
    switchTheme: SwitchThemeData(
      // Stitch toggle: kapalı = #161616 track + #2A2A2A kenarlık + beyaz knob;
      //               açık  = beyaz track + siyah knob.
      thumbColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? Colors.black : Colors.white,
      ),
      trackColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? AppColors.primary : AppColors.card,
      ),
      trackOutlineColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? AppColors.primary : AppColors.border,
      ),
    ),
    sliderTheme: const SliderThemeData(
      activeTrackColor: AppColors.primary,
      thumbColor: AppColors.primary,
      inactiveTrackColor: AppColors.surfaceVariant,
    ),
  );
}

// ---------------------------------------------------------------------------
// Sayfa geçişi: slide + fade (animasyon TÜRÜ korundu)
// ---------------------------------------------------------------------------
Route<T> slideFadeRoute<T>(Widget page) {
  return PageRouteBuilder<T>(
    transitionDuration: const Duration(milliseconds: 280),
    reverseTransitionDuration: const Duration(milliseconds: 220),
    pageBuilder: (_, __, ___) => page,
    transitionsBuilder: (_, animation, __, child) {
      final curved = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0, 0.06),
            end: Offset.zero,
          ).animate(curved),
          child: child,
        ),
      );
    },
  );
}

// ---------------------------------------------------------------------------
// Kart — düz, opak yüzey + 1px kenarlık (glow/gölge/blur YOK)
// (Sınıf adı/API geri uyumluluk için korundu; glowColor/blur artık görselsiz.)
// ---------------------------------------------------------------------------
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? glowColor; // korunuyor ama kullanılmıyor (gölge yok)
  final double borderRadius;
  final Color? fillColor;
  final Border? border;
  final bool blur; // korunuyor ama kullanılmıyor (blur yok)

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.glowColor,
    this.borderRadius = 16,
    this.fillColor,
    this.border,
    this.blur = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: fillColor ?? AppColors.card,
        borderRadius: BorderRadius.circular(borderRadius),
        border: border ?? Border.all(color: AppColors.border),
      ),
      child: child,
    );
  }
}

// ---------------------------------------------------------------------------
// Tap scale animasyonu (animasyon TÜRÜ korundu)
// ---------------------------------------------------------------------------
class TapScale extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  const TapScale({super.key, required this.child, this.onTap});

  @override
  State<TapScale> createState() => _TapScaleState();
}

class _TapScaleState extends State<TapScale> {
  double _scale = 1.0;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _scale = 0.97),
      onTapUp: (_) => setState(() => _scale = 1.0),
      onTapCancel: () => setState(() => _scale = 1.0),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _scale,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Staggered giriş animasyonu (aşağıdan yukarı + fade) — TÜR korundu
// ---------------------------------------------------------------------------
class StaggerItem extends StatefulWidget {
  final int index;
  final Widget child;
  const StaggerItem({super.key, required this.index, required this.child});

  @override
  State<StaggerItem> createState() => _StaggerItemState();
}

class _StaggerItemState extends State<StaggerItem>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 320),
    );
    final delay = (widget.index.clamp(0, 12)) * 45;
    Future.delayed(Duration(milliseconds: delay), () {
      if (mounted) _controller.forward();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final curved = CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic);
    return FadeTransition(
      opacity: curved,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0, 0.12),
          end: Offset.zero,
        ).animate(curved),
        child: widget.child,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Shimmer (skeleton loading) — monokrom ton (animasyon TÜRÜ korundu)
// ---------------------------------------------------------------------------
class ShimmerBox extends StatefulWidget {
  final double width;
  final double height;
  final double borderRadius;
  const ShimmerBox({
    super.key,
    required this.width,
    required this.height,
    this.borderRadius = 8,
  });

  @override
  State<ShimmerBox> createState() => _ShimmerBoxState();
}

class _ShimmerBoxState extends State<ShimmerBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final t = _controller.value;
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.borderRadius),
            border: Border.all(color: AppColors.border),
            gradient: LinearGradient(
              begin: Alignment(-1 - 2 * t, 0),
              end: Alignment(1 - 2 * t, 0),
              colors: const [
                AppColors.card,
                AppColors.surfaceVariant,
                AppColors.card,
              ],
            ),
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Pulse (badge / okunmamış nokta titreşimi) — TÜR korundu
// ---------------------------------------------------------------------------
class Pulse extends StatefulWidget {
  final Widget child;
  const Pulse({super.key, required this.child});

  @override
  State<Pulse> createState() => _PulseState();
}

class _PulseState extends State<Pulse> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: Tween<double>(begin: 0.85, end: 1.15).animate(
        CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
      ),
      child: widget.child,
    );
  }
}
