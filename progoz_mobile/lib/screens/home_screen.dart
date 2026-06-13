import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../models/incident.dart';
import '../providers/auth_provider.dart';
import '../providers/incidents_provider.dart';
import 'event_detail_screen.dart';
import 'plates_screen.dart';
import 'settings_screen.dart';

// Severity → renk eşlemesi
Color severityColor(String level) {
  switch (level.toUpperCase()) {
    case 'KAVGA':
      return AppColors.error;
    case 'OLASI_KAVGA':
      return AppColors.warning;
    case 'SUPHELI':
    case 'ŞÜPHELI':
      return AppColors.caution;
    default:
      return AppColors.textSecondary;
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: IndexedStack(
        index: _selectedIndex,
        children: const [
          _IncidentsTab(),
          PlatesScreen(),
          SettingsScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (i) => setState(() => _selectedIndex = i),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.notifications_outlined),
            activeIcon: Icon(Icons.notifications),
            label: 'Bildirimler',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.directions_car_outlined),
            activeIcon: Icon(Icons.directions_car),
            label: 'Plakalar',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.settings_outlined),
            activeIcon: Icon(Icons.settings),
            label: 'Ayarlar',
          ),
        ],
      ),
    );
  }
}

class _IncidentsTab extends StatefulWidget {
  const _IncidentsTab();

  @override
  State<_IncidentsTab> createState() => _IncidentsTabState();
}

class _IncidentsTabState extends State<_IncidentsTab> {
  String? _selectedSource; // null = Tüm Kaynaklar
  String? _selectedLevel; // null = TÜMÜ
  final ScrollController _scrollController = ScrollController();

  static const _levels = ['KAVGA', 'OLASI_KAVGA', 'SUPHELI'];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<IncidentsProvider>().load();
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onBellPressed() {
    setState(() => _selectedLevel = null); // tümünü göster
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        0,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  Map<String, int> _sourceCounts(List<Incident> incidents) {
    final counts = <String, int>{};
    for (final i in incidents) {
      counts[i.sourceName] = (counts[i.sourceName] ?? 0) + 1;
    }
    return counts;
  }

  List<Incident> _filtered(List<Incident> incidents) {
    return incidents.where((i) {
      if (_selectedSource != null && i.sourceName != _selectedSource) return false;
      if (_selectedLevel != null &&
          i.level.toUpperCase() != _selectedLevel!.toUpperCase()) {
        return false;
      }
      return true;
    }).toList();
  }

  String _levelDisplay(String level) {
    switch (level.toUpperCase()) {
      case 'KAVGA':
        return 'KAVGA';
      case 'OLASI_KAVGA':
        return 'OLASI KAVGA';
      case 'SUPHELI':
        return 'ŞÜPHELİ';
      default:
        return level;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        title: const Text(
          'PROGÖZ',
          style: TextStyle(
            color: AppColors.primary,
            fontWeight: FontWeight.bold,
            letterSpacing: 3,
          ),
        ),
        actions: [
          Consumer<IncidentsProvider>(
            builder: (_, provider, __) {
              final unread = provider.unreadCount;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: IconButton(
                  onPressed: _onBellPressed,
                  icon: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      Icon(
                        unread > 0 ? Icons.notifications : Icons.notifications_none,
                        color: unread > 0 ? AppColors.primary : AppColors.textSecondary,
                      ),
                      if (unread > 0)
                        Positioned(
                          right: -4,
                          top: -4,
                          child: Container(
                            padding: const EdgeInsets.all(4),
                            constraints: const BoxConstraints(
                                minWidth: 18, minHeight: 18),
                            decoration: const BoxDecoration(
                              color: AppColors.error,
                              shape: BoxShape.circle,
                            ),
                            child: Text(
                              '$unread',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                  fontSize: 10, color: Colors.white),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
      body: Consumer<IncidentsProvider>(
        builder: (context, provider, _) {
          if (provider.error == 'unauthorized') {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              context.read<AuthProvider>().logout();
            });
          }

          final allIncidents = provider.incidents;
          final sourceCounts = _sourceCounts(allIncidents);
          final filtered = _filtered(allIncidents);

          return Column(
            children: [
              // İstatistik kartları
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 6),
                child: Row(
                  children: [
                    Expanded(
                      child: _StatCard(
                        label: 'Bugünkü Olay',
                        value: '${provider.todayCount}',
                        icon: Icons.warning_amber,
                        color: AppColors.error,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _StatCard(
                        label: 'Toplam Kayıt',
                        value: '${allIncidents.length}',
                        icon: Icons.list_alt,
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _StatCard(
                        label: 'Son Olay',
                        value: provider.lastEventTime != null
                            ? DateFormat('HH:mm', 'tr_TR')
                                .format(provider.lastEventTime!)
                            : '-',
                        icon: Icons.access_time,
                        color: AppColors.info,
                      ),
                    ),
                  ],
                ),
              ),

              // Kaynak filtresi
              if (allIncidents.isNotEmpty)
                SizedBox(
                  height: 48,
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Row(
                      children: [
                        _Chip(
                          label: 'Tüm Kaynaklar',
                          count: allIncidents.length,
                          selected: _selectedSource == null,
                          onTap: () => setState(() => _selectedSource = null),
                        ),
                        for (final s in (sourceCounts.keys.toList()..sort())) ...[
                          const SizedBox(width: 12),
                          _Chip(
                            label: s,
                            count: sourceCounts[s] ?? 0,
                            selected: _selectedSource == s,
                            onTap: () => setState(() => _selectedSource = s),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),

              // Kaynak filtresi ile seviye filtresi arası
              if (allIncidents.isNotEmpty) const SizedBox(height: 12),

              // Seviye filtreleri
              if (allIncidents.isNotEmpty)
                SizedBox(
                  height: 46,
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Row(
                      children: [
                        _LevelChip(
                          label: 'TÜMÜ',
                          color: AppColors.primary,
                          selected: _selectedLevel == null,
                          onTap: () => setState(() => _selectedLevel = null),
                        ),
                        for (final l in _levels) ...[
                          const SizedBox(width: 8),
                          _LevelChip(
                            label: _levelDisplay(l),
                            color: severityColor(l),
                            selected: _selectedLevel == l,
                            onTap: () => setState(() => _selectedLevel = l),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),

              // Seviye filtresi ile liste arası
              const SizedBox(height: 8),

              // Olay listesi
              Expanded(child: _buildList(provider, filtered)),
            ],
          );
        },
      ),
    );
  }

  Widget _buildList(IncidentsProvider provider, List<Incident> filtered) {
    if (provider.loading && provider.incidents.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: AppColors.primary));
    }

    if (provider.error != null &&
        provider.error != 'unauthorized' &&
        provider.incidents.isEmpty) {
      return _MessageState(
        icon: Icons.wifi_off,
        title: 'Bağlantı hatası',
        subtitle: provider.error,
        onRetry: provider.load,
      );
    }

    if (provider.incidents.isEmpty) {
      return const _MessageState(
        icon: Icons.check_circle_outline,
        title: 'Henüz olay yok',
      );
    }

    if (filtered.isEmpty) {
      return const _MessageState(
        icon: Icons.filter_alt_off,
        title: 'Bu filtreye uygun olay yok',
      );
    }

    return RefreshIndicator(
      color: AppColors.primary,
      backgroundColor: AppColors.surface,
      onRefresh: provider.load,
      child: ListView.builder(
        controller: _scrollController,
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        itemCount: filtered.length,
        itemBuilder: (context, index) =>
            _IncidentCard(incident: filtered[index]),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(height: 8),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 10, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;

  const _Chip({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? AppColors.primary : AppColors.card,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.border,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: TextStyle(
                  color: selected ? Colors.black : AppColors.textSecondary,
                  fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                  fontSize: 13,
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: selected
                      ? Colors.black.withValues(alpha: 0.18)
                      : AppColors.surfaceVariant,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$count',
                  style: TextStyle(
                    color: selected ? Colors.black : AppColors.textSecondary,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ),
    );
  }
}

class _LevelChip extends StatelessWidget {
  final String label;
  final Color color;
  final bool selected;
  final VoidCallback onTap;

  const _LevelChip({
    required this.label,
    required this.color,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minWidth: 80),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? color.withValues(alpha: 0.18) : AppColors.card,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: selected ? color : AppColors.border,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? color : AppColors.textSecondary,
            fontWeight: FontWeight.bold,
            fontSize: 12,
          ),
        ),
      ),
    );
  }
}

class _IncidentCard extends StatelessWidget {
  final Incident incident;
  const _IncidentCard({required this.incident});

  @override
  Widget build(BuildContext context) {
    final levelColor = severityColor(incident.level);
    final timeStr = DateFormat('HH:mm', 'tr_TR').format(incident.startTime);
    final scoreStr = incident.maxScore.toStringAsFixed(0);
    final durationStr = incident.durationSeconds > 0
        ? '${incident.durationSeconds.toStringAsFixed(1)} sn'
        : null;

    return GestureDetector(
      onTap: () {
        context.read<IncidentsProvider>().markAsRead(incident.id);
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => EventDetailScreen(incident: incident),
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(12),
          border: Border(left: BorderSide(color: levelColor, width: 4)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: levelColor.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: Icon(Icons.warning_amber, color: levelColor, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${incident.levelDisplayName} Tespit Edildi',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: incident.isRead
                            ? FontWeight.w500
                            : FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Row(
                      children: [
                        Icon(
                          incident.isVideoSource
                              ? Icons.movie_outlined
                              : Icons.videocam_outlined,
                          size: 14,
                          color: AppColors.textSecondary,
                        ),
                        const SizedBox(width: 5),
                        Expanded(
                          child: Text(
                            incident.sourceName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: AppColors.textSecondary, fontSize: 12),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(
                      durationStr != null
                          ? 'Skor: $scoreStr  •  Süre: $durationStr'
                          : 'Skor: $scoreStr',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: AppColors.textSecondary, fontSize: 12),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    timeStr,
                    style: const TextStyle(
                        color: AppColors.textSecondary, fontSize: 12),
                  ),
                  if (!incident.isRead) ...[
                    const SizedBox(height: 8),
                    Container(
                      width: 9,
                      height: 9,
                      decoration: BoxDecoration(
                        color: levelColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MessageState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Future<void> Function()? onRetry;

  const _MessageState({
    required this.icon,
    required this.title,
    this.subtitle,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 64, color: AppColors.primary),
          const SizedBox(height: 16),
          Text(title, style: const TextStyle(color: AppColors.textPrimary)),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                subtitle!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
              ),
            ),
          ],
          if (onRetry != null) ...[
            const SizedBox(height: 16),
            ElevatedButton(onPressed: onRetry, child: const Text('Tekrar Dene')),
          ],
        ],
      ),
    );
  }
}
