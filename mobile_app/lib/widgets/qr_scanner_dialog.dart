import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../core/theme/app_colors.dart';
import 'donde_david_button.dart';

class QrScannerDialog extends StatefulWidget {
  final String? currentTable;
  final Function(String table) onTableSelected;
  final VoidCallback onClearTable;

  const QrScannerDialog({
    super.key,
    this.currentTable,
    required this.onTableSelected,
    required this.onClearTable,
  });

  @override
  State<QrScannerDialog> createState() => _QrScannerDialogState();
}

class _QrScannerDialogState extends State<QrScannerDialog> {
  final TextEditingController _customController = TextEditingController();
  late final MobileScannerController _cameraController;
  bool _useLiveCamera = true;
  bool _hasScanned = false;

  final List<String> _quickTables = [
    'Mesa 1',
    'Mesa 2',
    'Mesa 3',
    'Mesa 4',
    'Mesa 5',
    'Mesa 6',
    'Mesa 7',
    'Mesa 8',
    'Mesa 9',
    'Mesa 10',
    'Mesa 12',
    'Mesa 15',
  ];

  @override
  void initState() {
    super.initState();
    _cameraController = MobileScannerController(
      detectionSpeed: DetectionSpeed.normal,
      returnImage: false,
    );
  }

  @override
  void dispose() {
    _customController.dispose();
    _cameraController.dispose();
    super.dispose();
  }

  void _handleBarcode(String rawValue) {
    if (_hasScanned) return;
    _hasScanned = true;

    // Support URLs like "http://.../mesa?numero=5" or direct text "Mesa 5"
    String table = rawValue.trim();
    if (table.contains('numero=')) {
      final match = RegExp(r'numero=([0-9]+)').firstMatch(table);
      if (match != null) {
        table = 'Mesa ${match.group(1)}';
      }
    } else if (table.toLowerCase().contains('mesa')) {
      final match = RegExp(
        r'mesa\s*#?([0-9]+)',
        caseSensitive: false,
      ).firstMatch(table);
      if (match != null) {
        table = 'Mesa ${match.group(1)}';
      }
    } else if (int.tryParse(table) != null) {
      table = 'Mesa $table';
    }

    widget.onTableSelected(table);
    if (mounted) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('✅ $table vinculada por código QR')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 20),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: AppColors.border),
      ),
      backgroundColor: AppColors.bgSurface,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Top Bar
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                color: AppColors.colorDark,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.qr_code_scanner,
                          color: AppColors.cyanAccent,
                          size: 22,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'ESCÁNER QR DE MESA',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w900,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, color: AppColors.textMuted),
                      onPressed: () => Navigator.pop(context),
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                ),
              ),

              // Mode toggle (Cámara Real vs Selector Manual)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                child: Row(
                  children: [
                    Expanded(
                      child: ChoiceChip(
                        label: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.camera_alt, size: 14),
                            SizedBox(width: 6),
                            Text('Cámara Real'),
                          ],
                        ),
                        selected: _useLiveCamera,
                        onSelected: (val) =>
                            setState(() => _useLiveCamera = true),
                        selectedColor: AppColors.cyanAccent,
                        backgroundColor: const Color(0xFF1E293B),
                        labelStyle: TextStyle(
                          color: _useLiveCamera ? Colors.black : Colors.white,
                          fontWeight: FontWeight.w800,
                          fontSize: 11,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: ChoiceChip(
                        label: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.touch_app, size: 14),
                            SizedBox(width: 6),
                            Text('Selector Táctil'),
                          ],
                        ),
                        selected: !_useLiveCamera,
                        onSelected: (val) =>
                            setState(() => _useLiveCamera = false),
                        selectedColor: AppColors.cyanAccent,
                        backgroundColor: const Color(0xFF1E293B),
                        labelStyle: TextStyle(
                          color: !_useLiveCamera ? Colors.black : Colors.white,
                          fontWeight: FontWeight.w800,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // Camera Scanner View or Manual Selector
              if (_useLiveCamera)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(
                        height: 240,
                        width: double.infinity,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: AppColors.cyanAccent,
                            width: 2,
                          ),
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(14),
                          child: MobileScanner(
                            controller: _cameraController,
                            onDetect: (capture) {
                              final barcodes = capture.barcodes;
                              for (final barcode in barcodes) {
                                final val = barcode.rawValue;
                                if (val != null && val.isNotEmpty) {
                                  _handleBarcode(val);
                                  break;
                                }
                              }
                            },
                          ),
                        ),
                      ),

                      // Laser Scanner Line
                      Container(
                        width: 220,
                        height: 2,
                        decoration: BoxDecoration(
                          color: AppColors.cyanAccent,
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.cyanAccent.withAlpha(200),
                              blurRadius: 10,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                      ),

                      // Camera Torch & Flip Overlays
                      Positioned(
                        bottom: 10,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.black.withAlpha(180),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(
                                  Icons.flash_on,
                                  color: AppColors.goldAccent,
                                  size: 18,
                                ),
                                onPressed: () =>
                                    _cameraController.toggleTorch(),
                                visualDensity: VisualDensity.compact,
                                tooltip: 'Linterna',
                              ),
                              IconButton(
                                icon: const Icon(
                                  Icons.flip_camera_android,
                                  color: Colors.white,
                                  size: 18,
                                ),
                                onPressed: () =>
                                    _cameraController.switchCamera(),
                                visualDensity: VisualDensity.compact,
                                tooltip: 'Cambiar cámara',
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                )
              else
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'SELECCIONA TU MESA EN EL SALÓN:',
                        style: TextStyle(
                          color: AppColors.goldAccent,
                          fontSize: 11,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 0.5,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _quickTables.map((table) {
                          final isCurrent = widget.currentTable == table;
                          return InkWell(
                            onTap: () {
                              widget.onTableSelected(table);
                              Navigator.pop(context);
                            },
                            borderRadius: BorderRadius.circular(8),
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 8,
                              ),
                              decoration: BoxDecoration(
                                color: isCurrent
                                    ? AppColors.cyanAccent
                                    : const Color(0xFF1E293B),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: isCurrent
                                      ? AppColors.cyanAccent
                                      : AppColors.border,
                                ),
                              ),
                              child: Text(
                                table,
                                style: TextStyle(
                                  color: isCurrent
                                      ? Colors.black
                                      : AppColors.textPrimary,
                                  fontWeight: FontWeight.w800,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          );
                        }).toList(),
                      ),
                    ],
                  ),
                ),

              // Active Table Status / Clear Table Button
              if (widget.currentTable != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.cyanAccent.withAlpha(20),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: AppColors.cyanAccent.withAlpha(100),
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Mesa activa: ${widget.currentTable}',
                          style: const TextStyle(
                            color: AppColors.cyanAccent,
                            fontWeight: FontWeight.w800,
                            fontSize: 12,
                          ),
                        ),
                        TextButton(
                          onPressed: () {
                            widget.onClearTable();
                            Navigator.pop(context);
                          },
                          child: const Text(
                            'Desvincular',
                            style: TextStyle(
                              color: AppColors.danger,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              // Manual Input
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _customController,
                        decoration: const InputDecoration(
                          hintText: 'Ingresa número manual (Ej. 7)...',
                          contentPadding: EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 10,
                          ),
                        ),
                        keyboardType: TextInputType.number,
                        style: const TextStyle(fontSize: 13),
                      ),
                    ),
                    const SizedBox(width: 8),
                    DondeDavidButton(
                      text: 'APLICAR',
                      variant: ButtonVariant.gold,
                      height: 44,
                      onPressed: () {
                        final val = _customController.text.trim();
                        if (val.isNotEmpty) {
                          _handleBarcode(val);
                        }
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
