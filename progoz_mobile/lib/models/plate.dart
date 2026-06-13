class Plate {
  final String id;
  final String plateText; // boşsa "Okunamadı" gösterilecek
  final String? normalizedText;
  final double confidence; // 0-1 ölçeğinde
  final String sourceType; // camera / video / webcam
  final String sourceName; // kaynak adı (kamera/video)
  final int? cameraId;
  final String? videoFilename;
  final int seenCount;
  final DateTime? firstSeenAt;
  final DateTime detectedAt; // last_seen_at ?? created_at
  final String? cropImageUrl;

  Plate({
    required this.id,
    required this.plateText,
    this.normalizedText,
    required this.confidence,
    required this.sourceType,
    required this.sourceName,
    this.cameraId,
    this.videoFilename,
    this.seenCount = 1,
    this.firstSeenAt,
    required this.detectedAt,
    this.cropImageUrl,
  });

  factory Plate.fromJson(Map<String, dynamic> json) {
    final sourceType = (json['source_type'] ?? '').toString();
    final videoFilename = json['video_filename']?.toString();
    final cameraId = json['camera_id'] is int
        ? json['camera_id'] as int
        : int.tryParse(json['camera_id']?.toString() ?? '');

    final raw = json['plate_text_raw']?.toString();
    final normalized = json['plate_text_normalized']?.toString();
    final text = (normalized != null && normalized.isNotEmpty)
        ? normalized
        : (raw ?? '');

    return Plate(
      id: json['id']?.toString() ?? '',
      plateText: text,
      normalizedText: normalized,
      confidence: (json['confidence'] ?? json['score'] ?? 0).toDouble(),
      sourceType: sourceType,
      sourceName: _deriveSourceName(
        sourceType: sourceType,
        videoFilename: videoFilename,
        cameraName: json['camera_name']?.toString(),
        cameraId: cameraId,
      ),
      cameraId: cameraId,
      videoFilename: videoFilename,
      seenCount: json['seen_count'] is int
          ? json['seen_count'] as int
          : int.tryParse(json['seen_count']?.toString() ?? '') ?? 1,
      firstSeenAt: json['first_seen_at'] != null
          ? DateTime.tryParse(json['first_seen_at'].toString())
          : null,
      detectedAt: DateTime.tryParse(
            (json['last_seen_at'] ?? json['created_at'] ?? '').toString(),
          ) ??
          DateTime.now(),
      cropImageUrl: json['crop_url'] ??
          json['best_snapshot_url'] ??
          json['crop_image_url'] ??
          json['image_url'],
    );
  }

  static String _deriveSourceName({
    required String sourceType,
    String? videoFilename,
    String? cameraName,
    int? cameraId,
  }) {
    if (cameraName != null && cameraName.isNotEmpty) {
      return cameraName;
    }
    if (videoFilename != null && videoFilename.isNotEmpty) {
      return videoFilename;
    }
    if (sourceType == 'webcam') {
      return 'Webcam';
    }
    if (cameraId != null) {
      return 'Kamera $cameraId';
    }
    return 'Bilinmeyen Kaynak';
  }

  bool get isVideoSource => sourceType == 'video';

  bool get isReadable => plateText.trim().isNotEmpty;

  String get displayText => isReadable ? plateText : 'Okunamadı';
}
