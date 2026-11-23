import 'package:flutter/material.dart';
import '../core/constants/dish_images.dart';
import '../core/theme/app_colors.dart';

class DondeDavidDishImage extends StatelessWidget {
  final String? rawImageUrl;
  final String productName;
  final String? categoryName;
  final double? width;
  final double? height;
  final BoxFit fit;
  final BorderRadius? borderRadius;

  const DondeDavidDishImage({
    super.key,
    this.rawImageUrl,
    required this.productName,
    this.categoryName,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.borderRadius,
  });

  @override
  Widget build(BuildContext context) {
    final String targetUrl = DishImages.resolveProductImageUrl(
      rawImageUrl: rawImageUrl,
      productName: productName,
      categoryName: categoryName,
    );

    Widget imageWidget = Image.network(
      targetUrl,
      width: width,
      height: height,
      fit: fit,
      loadingBuilder: (context, child, loadingProgress) {
        if (loadingProgress == null) return child;
        return Container(
          width: width,
          height: height,
          color: const Color(0xFF161F30),
          child: Center(
            child: SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.goldAccent.withAlpha(180),
                value: loadingProgress.expectedTotalBytes != null
                    ? loadingProgress.cumulativeBytesLoaded /
                          loadingProgress.expectedTotalBytes!
                    : null,
              ),
            ),
          ),
        );
      },
      errorBuilder: (context, error, stackTrace) {
        return _buildLocalAssetFallback();
      },
    );

    if (borderRadius != null) {
      return ClipRRect(borderRadius: borderRadius!, child: imageWidget);
    }

    return imageWidget;
  }

  Widget _buildLocalAssetFallback() {
    return Container(
      width: width,
      height: height,
      color: const Color(0xFF182338),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Image.asset(
            DishImages.localFallbackAsset,
            width: width,
            height: height,
            fit: fit,
            errorBuilder: (_, __, ___) => const Icon(
              Icons.fastfood,
              color: AppColors.goldAccent,
              size: 28,
            ),
          ),
          Container(color: Colors.black.withAlpha(80)),
          const Icon(Icons.restaurant, color: AppColors.goldAccent, size: 24),
        ],
      ),
    );
  }
}
