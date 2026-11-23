import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../core/theme/app_colors.dart';
import 'donde_david_button.dart';

class DeliveryMapModal extends StatefulWidget {
  final double? initialLat;
  final double? initialLng;
  final Function(double lat, double lng, String reference) onLocationConfirmed;

  const DeliveryMapModal({
    super.key,
    this.initialLat,
    this.initialLng,
    required this.onLocationConfirmed,
  });

  @override
  State<DeliveryMapModal> createState() => _DeliveryMapModalState();
}

class _DeliveryMapModalState extends State<DeliveryMapModal> {
  late LatLng _selectedPoint;
  late final MapController _mapController;

  final Map<String, LatLng> _presets = {
    'Sede Principal': const LatLng(10.1800, -68.0000),
    'El Trigal': const LatLng(10.2030, -67.9850),
    'Prebo': const LatLng(10.2150, -68.0120),
    'San Diego': const LatLng(10.2520, -67.9540),
  };

  @override
  void initState() {
    super.initState();
    _mapController = MapController();
    _selectedPoint = LatLng(
      widget.initialLat ?? 10.1800,
      widget.initialLng ?? -68.0000,
    );
  }

  void _moveToPreset(String name, LatLng point) {
    setState(() {
      _selectedPoint = point;
    });
    _mapController.move(point, 15.5);
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 24),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: AppColors.border),
      ),
      backgroundColor: AppColors.bgSurface,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: SizedBox(
          width: double.infinity,
          height: MediaQuery.of(context).size.height * 0.78,
          child: Column(
            children: [
              // Header
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
                        Icon(Icons.map, color: AppColors.cyanAccent, size: 22),
                        SizedBox(width: 8),
                        Text(
                          'MAPA INTERACTIVO DE ENTREGA',
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

              // Quick location preset chips
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                color: const Color(0xFF161F30),
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: _presets.entries.map((entry) {
                      return Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: ActionChip(
                          label: Text(
                            entry.key,
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          backgroundColor: const Color(0xFF1E293B),
                          side: const BorderSide(color: AppColors.border),
                          onPressed: () =>
                              _moveToPreset(entry.key, entry.value),
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),

              // Interactive OpenStreetMap view
              Expanded(
                child: Stack(
                  children: [
                    FlutterMap(
                      mapController: _mapController,
                      options: MapOptions(
                        initialCenter: _selectedPoint,
                        initialZoom: 15.0,
                        onTap: (tapPosition, point) {
                          setState(() {
                            _selectedPoint = point;
                          });
                        },
                      ),
                      children: [
                        TileLayer(
                          urlTemplate:
                              'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                          userAgentPackageName: 'com.dondedavid.mobile_app',
                        ),
                        MarkerLayer(
                          markers: [
                            Marker(
                              point: _selectedPoint,
                              width: 50,
                              height: 50,
                              child: const Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.location_on,
                                    color: AppColors.danger,
                                    size: 38,
                                    shadows: [
                                      Shadow(
                                        color: Colors.black,
                                        blurRadius: 8,
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),

                    // Instruction tooltip on top of map
                    Positioned(
                      top: 10,
                      left: 12,
                      right: 12,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.black.withAlpha(200),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: AppColors.cyanAccent.withAlpha(120),
                          ),
                        ),
                        child: const Row(
                          children: [
                            Icon(
                              Icons.touch_app,
                              color: AppColors.cyanAccent,
                              size: 16,
                            ),
                            SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                'Toca cualquier punto del mapa para fijar el destino exacto.',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Coordinate pill indicator
                    Positioned(
                      bottom: 12,
                      left: 14,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.black.withAlpha(210),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppColors.border),
                        ),
                        child: Text(
                          'Coords: ${_selectedPoint.latitude.toStringAsFixed(4)}, ${_selectedPoint.longitude.toStringAsFixed(4)}',
                          style: const TextStyle(
                            color: AppColors.cyanAccent,
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // Bottom Actions
              Container(
                padding: const EdgeInsets.all(16),
                color: AppColors.bgSurface,
                child: DondeDavidButton(
                  text: '📍 CONFIRMAR ESTA UBICACIÓN',
                  variant: ButtonVariant.gold,
                  width: double.infinity,
                  onPressed: () {
                    final ref =
                        'Punto GPS (${_selectedPoint.latitude.toStringAsFixed(4)}, ${_selectedPoint.longitude.toStringAsFixed(4)})';
                    widget.onLocationConfirmed(
                      _selectedPoint.latitude,
                      _selectedPoint.longitude,
                      ref,
                    );
                    Navigator.pop(context);
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
