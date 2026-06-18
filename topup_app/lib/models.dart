class TagRead {
  final String tid;
  final String epc;

  const TagRead({required this.tid, required this.epc});

  Map<String, String> toJson() => {'tid': tid, 'epc': epc};

  factory TagRead.fromMap(Map<dynamic, dynamic> m) => TagRead(
        tid: (m['tid'] ?? m['TID'] ?? '').toString().replaceAll(' ', '').toUpperCase(),
        epc: (m['epc'] ?? m['EPC'] ?? '').toString().trim(),
      );
}
