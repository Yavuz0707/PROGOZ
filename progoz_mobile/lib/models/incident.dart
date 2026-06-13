class Incident {
  final String id;
  final String level; // severity: KAVGA / OLASI_KAVGA / SUPHELI / NORMAL
  final String sourceType; // camera / video / webcam
  final String sourceName; // kamera adı veya video adı
  final int? cameraId;
  final String? videoFilename;
  final DateTime startTime;
  final DateTime? endTime;
  final double durationSeconds;
  final double maxScore; // 0-100
  final double avgScore; // 0-100
  final String? thumbnailUrl;
  bool isRead;

  Incident({
    required this.id,
    required this.level,
    required this.sourceType,
    required this.sourceName,
    this.cameraId,
    this.videoFilename,
    required this.startTime,
    this.endTime,
    required this.durationSeconds,
    required this.maxScore,
    required this.avgScore,
    this.thumbnailUrl,
    this.isRead = false,
  });

  factory Incident.fromJson(Map<String, dynamic> json) {
    final sourceType = (json['source_type'] ?? '').toString();
    final videoFilename = json['video_filename']?.toString();
    final cameraId = json['camera_id'] is int
        ? json['camera_id'] as int
        : int.tryParse(json['camera_id']?.toString() ?? '');

    return Incident(
      id: json['id']?.toString() ?? '',
      level: (json['severity'] ?? json['level'] ?? 'SUPHELI').toString(),
      sourceType: sourceType,
      sourceName: _deriveSourceName(
        sourceType: sourceType,
        videoFilename: videoFilename,
        cameraName: json['camera_name']?.toString(),
        cameraId: cameraId,
      ),
      cameraId: cameraId,
      videoFilename: videoFilename,
      startTime: DateTime.tryParse(
            (json['started_at'] ?? json['created_at'] ?? '').toString(),
          ) ??
          DateTime.now(),
      endTime: json['ended_at'] != null
          ? DateTime.tryParse(json['ended_at'].toString())
          : null,
      durationSeconds: (json['duration_seconds'] ?? 0).toDouble(),
      maxScore: (json['max_score'] ?? json['score'] ?? 0).toDouble(),
      avgScore: (json['avg_score'] ?? json['score'] ?? 0).toDouble(),
      thumbnailUrl: json['best_snapshot_url'] ?? json['thumbnail_url'],
      isRead: json['is_read'] ?? false,
    );
  }

  static String _deriveSourceName({
    required String sourceType,
    String? videoFilename,
    String? cameraName,
    int? cameraId,
  }) {
    if (videoFilename != null && videoFilename.isNotEmpty) {
      return videoFilename;
    }
    if (cameraName != null && cameraName.isNotEmpty) {
      return cameraName;
    }
    if (sourceType == 'webcam') {
      return 'Webcam';
    }
    if (cameraId != null) {
      return 'Kamera $cameraId';
    }
    return 'Bilinmeyen Kaynak';
  }

  // Kaynak ikonu için yardımcı (📹 kamera/webcam, 🎬 video)
  bool get isVideoSource => sourceType == 'video';

  Duration? get duration {
    if (endTime != null) return endTime!.difference(startTime);
    if (durationSeconds > 0) {
      return Duration(milliseconds: (durationSeconds * 1000).round());
    }
    return null;
  }

  String get levelDisplayName {
    switch (level.toUpperCase()) {
      case 'KAVGA':
        return 'KAVGA';
      case 'OLASI_KAVGA':
        return 'OLASI KAVGA';
      case 'SUPHELI':
      case 'ŞÜPHELI':
        return 'ŞÜPHELİ';
      case 'NORMAL':
        return 'NORMAL';
      default:
        return level.toUpperCase();
    }
  }

  // Eski ekranlarla (event_detail) geriye dönük uyumluluk
  String get cameraName => sourceName;

  bool get isPlateEvent {
    final l = level.toUpperCase();
    return l == 'PLATE' || l == 'PLAKA';
  }
}
