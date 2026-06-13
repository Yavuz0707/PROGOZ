import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/theme.dart';
import '../providers/auth_provider.dart';
import '../providers/settings_provider.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: _GradientAppBar(),
      body: Consumer<SettingsProvider>(
        builder: (context, settings, _) {
          return Column(
            children: [
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    const _SectionHeader('Kullanıcı'),
                    _UserInfoCard(),
                    const SizedBox(height: 18),
                    const _SectionHeader('Sunucu'),
                    _ServerUrlCard(settings: settings),
                    const SizedBox(height: 18),
                    const _SectionHeader('Bildirimler'),
                    _NotificationCard(settings: settings),
                    const SizedBox(height: 18),
                    const _SectionHeader('Minimum Skor Eşiği'),
                    _ScoreSliderCard(settings: settings),
                    const SizedBox(height: 16),
                  ],
                ),
              ),
              // Alttan sticky çıkış butonu
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                child: _LogoutButton(),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _GradientAppBar extends StatelessWidget implements PreferredSizeWidget {
  @override
  Size get preferredSize => const Size.fromHeight(58);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.primaryGlow)),
        gradient: LinearGradient(
          colors: [Color(0xFF111827), Color(0xFF0A0E1A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: const SafeArea(
        bottom: false,
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: 16),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Ayarlar',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                letterSpacing: 1,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10, left: 4),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          color: AppColors.primary,
          fontSize: 11,
          fontWeight: FontWeight.bold,
          letterSpacing: 1.5,
        ),
      ),
    );
  }
}

class _UserInfoCard extends StatelessWidget {
  Future<String?> _getUsername() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('username');
  }

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      glowColor: AppColors.primary,
      child: FutureBuilder<String?>(
        future: _getUsername(),
        builder: (context, snap) {
          final username = snap.data ?? '-';
          return Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  gradient: AppColors.primaryGradient,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.person, color: Colors.black),
              ),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(username,
                      style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.bold,
                          fontSize: 16)),
                  const Text('Aktif Oturum',
                      style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}

class _ServerUrlCard extends StatefulWidget {
  final SettingsProvider settings;
  const _ServerUrlCard({required this.settings});

  @override
  State<_ServerUrlCard> createState() => _ServerUrlCardState();
}

class _ServerUrlCardState extends State<_ServerUrlCard> {
  late TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.settings.serverUrl);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Backend Sunucu Adresi',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  decoration: const InputDecoration(
                    hintText: 'http://192.168.x.x:8002',
                    isDense: true,
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                  ),
                  style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                ),
              ),
              const SizedBox(width: 8),
              TapScale(
                onTap: () {
                  widget.settings.setServerUrl(_controller.text.trim());
                  FocusScope.of(context).unfocus();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Sunucu adresi güncellendi'),
                      backgroundColor: AppColors.primary,
                    ),
                  );
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text('Kaydet',
                      style: TextStyle(
                          color: Colors.black, fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  final SettingsProvider settings;
  const _NotificationCard({required this.settings});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          SwitchListTile(
            title: const Text('Kavga Bildirimleri',
                style: TextStyle(color: AppColors.textPrimary)),
            subtitle: const Text('Kavga tespitlerinde bildirim al',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
            value: settings.fightNotifications,
            onChanged: settings.setFightNotifications,
          ),
          const Divider(height: 1, color: AppColors.border),
          SwitchListTile(
            title: const Text('Plaka Bildirimleri',
                style: TextStyle(color: AppColors.textPrimary)),
            subtitle: const Text('Plaka tespitlerinde bildirim al',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
            value: settings.plateNotifications,
            onChanged: settings.setPlateNotifications,
          ),
        ],
      ),
    );
  }
}

class _ScoreSliderCard extends StatelessWidget {
  final SettingsProvider settings;
  const _ScoreSliderCard({required this.settings});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Minimum Skor',
                  style: TextStyle(color: AppColors.textPrimary)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '%${settings.minScore.toStringAsFixed(0)}',
                  style: const TextStyle(
                      color: AppColors.primary, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          Slider(
            value: settings.minScore,
            min: 0,
            max: 100,
            divisions: 20,
            onChanged: settings.setMinScore,
          ),
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('0%', style: TextStyle(color: AppColors.textSecondary, fontSize: 11)),
              Text('100%', style: TextStyle(color: AppColors.textSecondary, fontSize: 11)),
            ],
          ),
        ],
      ),
    );
  }
}

class _LogoutButton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return TapScale(
      onTap: () => _confirmLogout(context),
      child: Container(
        height: 54,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.error.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.error),
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.logout, color: AppColors.error),
            SizedBox(width: 8),
            Text('Çıkış Yap',
                style: TextStyle(
                    color: AppColors.error,
                    fontSize: 16,
                    fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmLogout(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.card,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Text('Çıkış Yap', style: TextStyle(color: AppColors.textPrimary)),
        content: const Text('Çıkış yapmak istediğinize emin misiniz?',
            style: TextStyle(color: AppColors.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('İptal', style: TextStyle(color: AppColors.textSecondary)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('Çıkış', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      context.read<AuthProvider>().logout();
    }
  }
}
