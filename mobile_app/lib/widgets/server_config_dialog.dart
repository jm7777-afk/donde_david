import 'package:flutter/material.dart';
import '../core/services/storage_service.dart';
import '../core/theme/app_colors.dart';
import 'donde_david_button.dart';

class ServerConfigDialog extends StatefulWidget {
  final StorageService storage;
  final VoidCallback onSaved;

  const ServerConfigDialog({
    super.key,
    required this.storage,
    required this.onSaved,
  });

  @override
  State<ServerConfigDialog> createState() => _ServerConfigDialogState();
}

class _ServerConfigDialogState extends State<ServerConfigDialog> {
  late TextEditingController _urlController;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(text: widget.storage.getBaseUrl());
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  void _setPreset(String url) {
    setState(() {
      _urlController.text = url;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Row(
                  children: [
                    Icon(Icons.dns, color: AppColors.brandOrange, size: 22),
                    SizedBox(width: 8),
                    Text(
                      'CONEXIÓN AL BACKEND',
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w900,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close, color: AppColors.textMuted),
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Text(
              'Ajusta la dirección IP y puerto del backend FastAPI según tu entorno:',
              style: TextStyle(color: AppColors.textMuted, fontSize: 12),
            ),
            const SizedBox(height: 12),

            TextField(
              controller: _urlController,
              decoration: const InputDecoration(
                labelText: 'URL Base de la API',
                hintText: 'http://10.0.2.2:8000 o http://localhost:8000',
                prefixIcon: Icon(Icons.link, color: AppColors.textMuted),
              ),
              style: const TextStyle(fontSize: 13),
            ),

            const SizedBox(height: 12),
            const Text(
              'ACCESOS RÁPIDOS:',
              style: TextStyle(
                color: AppColors.goldAccent,
                fontSize: 10,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _buildPresetChip('Emulador Android', 'http://10.0.2.2:8000'),
                _buildPresetChip('Localhost PC', 'http://localhost:8000'),
                _buildPresetChip('IP Local LAN', 'http://192.168.1.100:8000'),
              ],
            ),

            const SizedBox(height: 20),

            DondeDavidButton(
              text: 'GUARDAR Y APLICAR',
              variant: ButtonVariant.primaryOrange,
              width: double.infinity,
              onPressed: () async {
                final url = _urlController.text.trim();
                if (url.isNotEmpty) {
                  await widget.storage.setBaseUrl(url);
                  widget.onSaved();
                  if (mounted) {
                    Navigator.pop(context);
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Servidor actualizado a $url')),
                    );
                  }
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPresetChip(String label, String url) {
    return ActionChip(
      label: Text(
        label,
        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
      ),
      backgroundColor: const Color(0xFF1E293B),
      side: const BorderSide(color: AppColors.border),
      onPressed: () => _setPreset(url),
    );
  }
}
