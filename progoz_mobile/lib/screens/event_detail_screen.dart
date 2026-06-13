import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/theme.dart';
import '../models/incident.dart';
import '../providers/incidents_provider.dart';

Color _severityColor(String level) {
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

class EventDetailScreen extends StatefulWidget {
  final Incident incident;

  const EventDetailScreen({super.key, required this.incident});

  @override
  State<EventDetailScreen> createState() => _EventDetailScreenState();
}

class _EventDetailScreenState extends State<EventDetailScreen> {
  bool _actionLoading = false;

  String _formatDuration(Duration d) {
    final m = d.inMinutes;
    final s = d.inSeconds % 60;
    if (m > 0) return '$m dk $s sn';
    return '$s sn';
  }

  Future<String> _getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('server_url') ?? 'http://10.0.2.2:8002';
  }

  String _buildImageUrl(String path, String baseUrl) {
    if (path.startsWith('http')) return path;
    return '$baseUrl$path';
  }

  Future<void> _confirm() async {
    setState(() => _actionLoading = true);
    try {
      await context.read<IncidentsProvider>().confirmIncident(widget.incident.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Olay onaylandı'), backgroundColor: AppColors.primary),
        );
        Navigator.pop(context);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('İşlem başarısız'), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _actionLoading = false);
    }
  }

  Future<void> _dismiss() async {
    setState(() => _actionLoading = true);
    try {
      await context.read<IncidentsProvider>().dismissIncident(widget.incident.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Yanlış alarm olarak işaretlendi'),
              backgroundColor: AppColors.warning),
        );
        Navigator.pop(context);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('İşlem başarısız'), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _actionLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final incident = widget.incident;
    final levelColor = _severityColor(incident.level);
    final dateFormat = DateFormat('dd MMMM yyyy', 'tr_TR');
    final timeFormat = DateFormat('HH:mm:ss', 'tr_TR');

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.bgGradient),
        child: CustomScrollView(
          slivers: [
            // Renkli gradient header
            SliverToBoxAdapter(
              child: _GradientHeader(
                levelColor: levelColor,
                level: incident.levelDisplayName,
                sourceName: incident.sourceName,
                isVideo: incident.isVideoSource,
                dateText: dateFormat.format(incident.startTime),
                timeText: timeFormat.format(incident.startTime),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.all(16),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  if (incident.thumbnailUrl != null) ...[
                    _buildThumbnail(incident),
                    const SizedBox(height: 16),
                  ],
                  _StatGrid(
                    items: [
                      _StatItem(
                        label: 'Başlangıç',
                        value: timeFormat.format(incident.startTime),
                        icon: Icons.play_arrow,
                      ),
                      _StatItem(
                        label: 'Bitiş',
                        value: incident.endTime != null
                            ? timeFormat.format(incident.endTime!)
                            : '-',
                        icon: Icons.stop,
                      ),
                      _StatItem(
                        label: 'Süre',
                        value: incident.duration != null
                            ? _formatDuration(incident.duration!)
                            : '-',
                        icon: Icons.timer_outlined,
                      ),
                      _StatItem(
                        label: 'Max Skor',
                        value: incident.maxScore.toStringAsFixed(0),
                        icon: Icons.bolt,
                        color: levelColor,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  GlassCard(
                    child: Column(
                      children: [
                        _row('Kamera / Kaynak', incident.sourceName),
                        const Divider(height: 20, color: AppColors.border),
                        _row('Ortalama Skor', incident.avgScore.toStringAsFixed(0)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 28),
                  if (_actionLoading)
                    const Center(
                        child: CircularProgressIndicator(color: AppColors.primary))
                  else
                    Row(
                      children: [
                        Expanded(
                          child: TapScale(
                            onTap: _confirm,
                            child: _ActionButton(
                              label: 'Doğru Olay',
                              icon: Icons.check_circle_outline,
                              gradient: AppColors.primaryGradient,
                              foreground: Colors.black,
                              glow: AppColors.primary,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TapScale(
                            onTap: _dismiss,
                            child: _ActionButton(
                              label: 'Yanlış Alarm',
                              icon: Icons.cancel_outlined,
                              outlineColor: AppColors.error,
                              foreground: AppColors.error,
                            ),
                          ),
                        ),
                      ],
                    ),
                  const SizedBox(height: 20),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildThumbnail(Incident incident) {
    return FutureBuilder<String>(
      future: _getBaseUrl(),
      builder: (context, snap) {
        final url = snap.hasData
            ? _buildImageUrl(incident.thumbnailUrl!, snap.data!)
            : '';
        return ClipRRect(
          borderRadius: BorderRadius.circular(18),
          child: url.isEmpty
              ? Container(
                  height: 200,
                  color: AppColors.card,
                  child: const Center(
                      child: CircularProgressIndicator(color: AppColors.primary)),
                )
              : CachedNetworkImage(
                  imageUrl: url,
                  height: 200,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  placeholder: (_, __) => Container(
                    height: 200,
                    color: AppColors.card,
                    child: const Center(
                        child: CircularProgressIndicator(color: AppColors.primary)),
                  ),
                  errorWidget: (_, __, ___) => Container(
                    height: 200,
                    color: AppColors.card,
                    child: const Center(
                        child: Icon(Icons.broken_image,
                            color: AppColors.textSecondary, size: 48)),
                  ),
                ),
        );
      },
    );
  }

  Widget _row(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textSecondary)),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600),
          ),
        ),
      ],
    );
  }
}

class _GradientHeader extends StatelessWidget {
  final Color levelColor;
  final String level;
  final String sourceName;
  final bool isVideo;
  final String dateText;
  final String timeText;

  const _GradientHeader({
    required this.levelColor,
    required this.level,
    required this.sourceName,
    required this.isVideo,
    required this.dateText,
    required this.timeText,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            levelColor.withValues(alpha: 0.35),
            AppColors.background.withValues(alpha: 0.0),
          ],
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 4, 16, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
                    onPressed: () => Navigator.pop(context),
                  ),
                  const Text('Olay Detayı',
                      style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 16,
                          fontWeight: FontWeight.w600)),
                ],
              ),
              const SizedBox(height: 8),
              Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                  decoration: BoxDecoration(
                    color: levelColor.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: levelColor),
                    boxShadow: [
                      BoxShadow(
                        color: levelColor.withValues(alpha: 0.35),
                        blurRadius: 22,
                        spreadRadius: -2,
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.warning_amber_rounded, color: levelColor, size: 22),
                      const SizedBox(width: 10),
                      Text(
                        level,
                        style: TextStyle(
                          color: levelColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 20,
                          letterSpacing: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Center(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(isVideo ? Icons.movie_outlined : Icons.videocam_outlined,
                        size: 16, color: AppColors.textSecondary),
                    const SizedBox(width: 6),
                    Text(sourceName,
                        style: const TextStyle(color: AppColors.textSecondary)),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              Center(
                child: Text(
                  '$dateText  •  $timeText',
                  style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 18,
                      fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatItem {
  final String label;
  final String value;
  final IconData icon;
  final Color? color;
  _StatItem({required this.label, required this.value, required this.icon, this.color});
}

class _StatGrid extends StatelessWidget {
  final List<_StatItem> items;
  const _StatGrid({required this.items});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 2.4,
      children: items.map((item) {
        final color = item.color ?? AppColors.primary;
        return GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(item.icon, color: color, size: 18),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(item.value,
                        style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontWeight: FontWeight.bold,
                            fontSize: 16),
                        overflow: TextOverflow.ellipsis),
                    Text(item.label,
                        style: const TextStyle(
                            color: AppColors.textSecondary, fontSize: 11),
                        overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Gradient? gradient;
  final Color? outlineColor;
  final Color foreground;
  final Color? glow;

  const _ActionButton({
    required this.label,
    required this.icon,
    this.gradient,
    this.outlineColor,
    required this.foreground,
    this.glow,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: gradient,
        color: gradient == null ? AppColors.card : null,
        borderRadius: BorderRadius.circular(14),
        border: outlineColor != null ? Border.all(color: outlineColor!) : null,
        boxShadow: glow != null
            ? [
                BoxShadow(
                  color: glow!.withValues(alpha: 0.4),
                  blurRadius: 18,
                  spreadRadius: -2,
                  offset: const Offset(0, 5),
                ),
              ]
            : null,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: foreground, size: 20),
          const SizedBox(width: 8),
          Text(label,
              style: TextStyle(
                  color: foreground, fontWeight: FontWeight.bold, fontSize: 14)),
        ],
      ),
    );
  }
}
