import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/theme.dart';
import '../models/plate.dart';
import '../providers/auth_provider.dart';
import '../providers/plates_provider.dart';

// Güven skoru -> renk (yeşil >80, sarı 50-80, kırmızı <50)
Color confidenceColor(double percent) {
  if (percent > 80) return AppColors.primary;
  if (percent >= 50) return AppColors.warning;
  return AppColors.error;
}

class PlatesScreen extends StatefulWidget {
  const PlatesScreen({super.key});

  @override
  State<PlatesScreen> createState() => _PlatesScreenState();
}

class _PlatesScreenState extends State<PlatesScreen> {
  String? _selectedSource;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<PlatesProvider>().load();
    });
  }

  // Aynı plaka + aynı kaynak için en yüksek confidence'lı kaydı tut.
  List<Plate> _dedupe(List<Plate> plates) {
    final unique = <String, Plate>{};
    for (final plate in plates) {
      final key = '${plate.plateText}_${plate.sourceName}';
      final existing = unique[key];
      if (existing == null || plate.confidence > existing.confidence) {
        unique[key] = plate;
      }
    }
    final result = unique.values.toList();
    result.sort((a, b) => b.detectedAt.compareTo(a.detectedAt));
    return result;
  }

  Map<String, int> _sourceCounts(List<Plate> plates) {
    final counts = <String, int>{};
    for (final p in plates) {
      counts[p.sourceName] = (counts[p.sourceName] ?? 0) + 1;
    }
    return counts;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: _GradientAppBar(),
      body: Consumer<PlatesProvider>(
        builder: (context, provider, _) {
          if (provider.error == 'unauthorized') {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              context.read<AuthProvider>().logout();
            });
          }

          final deduped = _dedupe(provider.plates);
          final sourceCounts = _sourceCounts(deduped);
          final filtered = deduped.where((p) {
            if (_selectedSource != null && p.sourceName != _selectedSource) {
              return false;
            }
            if (_searchQuery.isNotEmpty &&
                !p.plateText.toUpperCase().contains(_searchQuery)) {
              return false;
            }
            return true;
          }).toList();

          return RefreshIndicator(
            color: AppColors.primary,
            backgroundColor: AppColors.surface,
            onRefresh: provider.load,
            child: Column(
              children: [
                if (provider.plates.isNotEmpty) _buildSearchBar(),
                if (deduped.isNotEmpty)
                  _SourceChips(
                    sourceCounts: sourceCounts,
                    totalCount: deduped.length,
                    selectedSource: _selectedSource,
                    onSelected: (s) => setState(() => _selectedSource = s),
                  ),
                Expanded(child: _buildBody(provider, filtered)),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: TextField(
        onChanged: (value) =>
            setState(() => _searchQuery = value.toUpperCase()),
        style: const TextStyle(color: AppColors.textPrimary),
        textCapitalization: TextCapitalization.characters,
        decoration: InputDecoration(
          hintText: 'Plaka ara... (örn: 34ABC)',
          prefixIcon: const Icon(Icons.search, color: AppColors.primary),
          filled: true,
          fillColor: AppColors.card,
          isDense: true,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.primaryGlow),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.primaryGlow),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.primary),
          ),
        ),
      ),
    );
  }

  Widget _buildBody(PlatesProvider provider, List<Plate> filtered) {
    if (provider.loading && provider.plates.isEmpty) {
      return ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: 5,
        itemBuilder: (_, __) => const Padding(
          padding: EdgeInsets.only(bottom: 12),
          child: ShimmerBox(width: double.infinity, height: 96, borderRadius: 18),
        ),
      );
    }

    if (provider.error != null &&
        provider.error != 'unauthorized' &&
        provider.plates.isEmpty) {
      return ListView(
        children: [
          const SizedBox(height: 100),
          Center(
            child: Column(
              children: [
                const Icon(Icons.error_outline, color: AppColors.error, size: 48),
                const SizedBox(height: 12),
                Text(provider.error!,
                    style: const TextStyle(color: AppColors.textSecondary)),
                const SizedBox(height: 16),
                ElevatedButton(
                    onPressed: provider.load, child: const Text('Tekrar Dene')),
              ],
            ),
          ),
        ],
      );
    }

    if (provider.plates.isEmpty) {
      return ListView(
        children: const [
          SizedBox(height: 120),
          Icon(Icons.directions_car_outlined, size: 64, color: AppColors.primary),
          SizedBox(height: 16),
          Center(
            child: Text('Henüz plaka kaydı yok',
                style: TextStyle(color: AppColors.textSecondary)),
          ),
        ],
      );
    }

    if (filtered.isEmpty) {
      return ListView(
        children: const [
          SizedBox(height: 120),
          Center(
            child: Text('Bu kaynakta plaka yok',
                style: TextStyle(color: AppColors.textSecondary)),
          ),
        ],
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: filtered.length,
      itemBuilder: (context, index) => StaggerItem(
        index: index,
        child: _PlateCard(plate: filtered[index]),
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
      child: SafeArea(
        bottom: false,
        child: const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Plakalar',
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

class _SourceChips extends StatelessWidget {
  final Map<String, int> sourceCounts;
  final int totalCount;
  final String? selectedSource;
  final ValueChanged<String?> onSelected;

  const _SourceChips({
    required this.sourceCounts,
    required this.totalCount,
    required this.selectedSource,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final sources = sourceCounts.keys.toList()..sort();
    return SizedBox(
      height: 52,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          _SourceChip(
            label: 'Tüm Kaynaklar',
            count: totalCount,
            selected: selectedSource == null,
            onTap: () => onSelected(null),
          ),
          for (final s in sources)
            _SourceChip(
              label: s,
              count: sourceCounts[s] ?? 0,
              selected: selectedSource == s,
              onTap: () => onSelected(s),
            ),
        ],
      ),
    );
  }
}

class _SourceChip extends StatelessWidget {
  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;

  const _SourceChip({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
          padding: const EdgeInsets.symmetric(horizontal: 14),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: selected ? AppColors.primary : AppColors.card,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: selected ? AppColors.primary : AppColors.border,
            ),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: AppColors.primary.withValues(alpha: 0.4),
                      blurRadius: 14,
                      spreadRadius: -2,
                    ),
                  ]
                : null,
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
      ),
    );
  }
}

class _PlateCard extends StatelessWidget {
  final Plate plate;
  const _PlateCard({required this.plate});

  Future<String> _getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('server_url') ?? 'http://10.0.2.2:8002';
  }

  String _buildImageUrl(String path, String baseUrl) {
    if (path.startsWith('http')) return path;
    return '$baseUrl$path';
  }

  @override
  Widget build(BuildContext context) {
    final timeStr = DateFormat('dd.MM.yyyy HH:mm', 'tr_TR').format(plate.detectedAt);
    final percent = plate.confidence * 100;
    final confidenceStr = '%${percent.toStringAsFixed(0)}';
    final confColor = confidenceColor(percent);
    final highlight = plate.seenCount > 5;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassCard(
        glowColor: highlight ? AppColors.primary : null,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildImage(),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          plate.displayText,
                          style: TextStyle(
                            color: plate.isReadable
                                ? AppColors.textPrimary
                                : AppColors.textSecondary,
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                            letterSpacing: plate.isReadable ? 2 : 0.5,
                            fontStyle:
                                plate.isReadable ? FontStyle.normal : FontStyle.italic,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Text(
                        confidenceStr,
                        style: TextStyle(
                          color: confColor,
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  // Güven skoru progress bar
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: LinearProgressIndicator(
                      value: (percent / 100).clamp(0.0, 1.0),
                      minHeight: 6,
                      backgroundColor: AppColors.surfaceVariant,
                      valueColor: AlwaysStoppedAnimation(confColor),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Icon(
                        plate.isVideoSource
                            ? Icons.movie_outlined
                            : Icons.videocam_outlined,
                        size: 14,
                        color: AppColors.textSecondary,
                      ),
                      const SizedBox(width: 5),
                      Expanded(
                        child: Text(
                          plate.sourceName,
                          style: const TextStyle(
                              color: AppColors.textSecondary, fontSize: 12),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.access_time,
                          size: 14, color: AppColors.textSecondary),
                      const SizedBox(width: 5),
                      Text(
                        timeStr,
                        style: const TextStyle(
                            color: AppColors.textSecondary, fontSize: 12),
                      ),
                      if (plate.seenCount > 1) ...[
                        const SizedBox(width: 12),
                        Icon(Icons.repeat,
                            size: 14,
                            color: highlight ? AppColors.primary : AppColors.textSecondary),
                        const SizedBox(width: 4),
                        Text(
                          '${plate.seenCount}x görüldü',
                          style: TextStyle(
                              color: highlight
                                  ? AppColors.primary
                                  : AppColors.textSecondary,
                              fontSize: 12,
                              fontWeight:
                                  highlight ? FontWeight.bold : FontWeight.normal),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImage() {
    if (plate.cropImageUrl == null) return _PlaceholderImage();
    return FutureBuilder<String>(
      future: _getBaseUrl(),
      builder: (context, snap) {
        final url =
            snap.hasData ? _buildImageUrl(plate.cropImageUrl!, snap.data!) : '';
        return ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: url.isEmpty
              ? _PlaceholderImage()
              : CachedNetworkImage(
                  imageUrl: url,
                  width: 70,
                  height: 70,
                  fit: BoxFit.cover,
                  placeholder: (_, __) => _PlaceholderImage(),
                  errorWidget: (_, __, ___) => _PlaceholderImage(),
                ),
        );
      },
    );
  }
}

class _PlaceholderImage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 70,
      height: 70,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.primary.withValues(alpha: 0.18),
            AppColors.info.withValues(alpha: 0.12),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(10),
      ),
      child: const Icon(Icons.directions_car, color: AppColors.primary, size: 30),
    );
  }
}
