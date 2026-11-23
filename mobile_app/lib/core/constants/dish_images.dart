class DishImages {
  // Curated, verified high-resolution food photography URLs (Unsplash CDN)
  static const String defaultHeroBurger =
      'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600&auto=format&fit=crop';
  static const String defaultBurgerDouble =
      'https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=600&auto=format&fit=crop';
  static const String defaultBurgerBbq =
      'https://images.unsplash.com/photo-1550547660-d9450f859349?w=600&auto=format&fit=crop';

  static const String defaultHotDogLoaded =
      'https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=600&auto=format&fit=crop';
  static const String defaultHotDogClassic =
      'https://images.unsplash.com/photo-1541214113241-21578d2d9b62?w=600&auto=format&fit=crop';

  static const String defaultPepitoMixto =
      'https://images.unsplash.com/photo-1509722747041-616f39b57569?w=600&auto=format&fit=crop';
  static const String defaultPepitoSimple =
      'https://images.unsplash.com/photo-1550547660-d9450f859349?w=600&auto=format&fit=crop';

  static const String defaultSalchipapasSmall =
      'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=600&auto=format&fit=crop';
  static const String defaultSalchipapasLoaded =
      'https://images.unsplash.com/photo-1585109649139-366815a0d713?w=600&auto=format&fit=crop';

  static const String defaultDrink =
      'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=600&auto=format&fit=crop';
  static const String defaultShake =
      'https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=600&auto=format&fit=crop';
  static const String defaultDessert =
      'https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=600&auto=format&fit=crop';

  // Fallback bundled local asset logo
  static const String localFallbackAsset = 'assets/images/logo-donde-david.jpg';

  /// Resolves the optimal, reliable image URL for a given product
  static String resolveProductImageUrl({
    required String? rawImageUrl,
    required String productName,
    String? categoryName,
    String? baseUrl,
  }) {
    // 1. If backend URL is an external HTTPS link (e.g. Unsplash, Cloudinary, S3), use it directly
    if (rawImageUrl != null &&
        (rawImageUrl.startsWith('http://') ||
            rawImageUrl.startsWith('https://'))) {
      return rawImageUrl;
    }

    final lowerName = productName.toLowerCase();
    final lowerCat = (categoryName ?? '').toLowerCase();

    // 2. Exact dish matching for Donde David menu
    if (lowerName.contains('especial') &&
        (lowerName.contains('perro') ||
            lowerCat.contains('dog') ||
            lowerCat.contains('perro'))) {
      return defaultHotDogLoaded;
    }
    if (lowerName.contains('polaco')) {
      return defaultHotDogLoaded;
    }
    if (lowerName.contains('sencillo') &&
        (lowerName.contains('perro') ||
            lowerCat.contains('dog') ||
            lowerCat.contains('perro'))) {
      return defaultHotDogClassic;
    }
    if (lowerName.contains('david') &&
        (lowerName.contains('hot') || lowerName.contains('perro'))) {
      return defaultHotDogClassic;
    }
    if (lowerName.contains('perro') ||
        lowerCat.contains('dog') ||
        lowerCat.contains('perro')) {
      return defaultHotDogLoaded;
    }

    if (lowerName.contains('pepito') || lowerCat.contains('pepito')) {
      if (lowerName.contains('mixto') || lowerName.contains('especial')) {
        return defaultPepitoMixto;
      }
      return defaultPepitoSimple;
    }

    if (lowerName.contains('salchipapa') || lowerCat.contains('salchipapa')) {
      if (lowerName.contains('grande') || lowerName.contains('familiar')) {
        return defaultSalchipapasLoaded;
      }
      return defaultSalchipapasSmall;
    }

    if (lowerName.contains('doble')) {
      return defaultBurgerDouble;
    }
    if (lowerName.contains('bbq')) {
      return defaultBurgerBbq;
    }
    if (lowerName.contains('hamburguesa') ||
        lowerCat.contains('burger') ||
        lowerCat.contains('hamburguesa')) {
      return defaultHeroBurger;
    }

    if (lowerName.contains('malteada') ||
        lowerName.contains('shake') ||
        lowerName.contains('oreo')) {
      return defaultShake;
    }
    if (lowerName.contains('bebida') ||
        lowerName.contains('refresco') ||
        lowerCat.contains('bebida')) {
      return defaultDrink;
    }
    if (lowerName.contains('postre') ||
        lowerCat.contains('postre') ||
        lowerName.contains('helado')) {
      return defaultDessert;
    }

    // 3. Category Fallback
    if (lowerCat.contains('hamburguesa')) return defaultHeroBurger;
    if (lowerCat.contains('perro') || lowerCat.contains('dog'))
      return defaultHotDogLoaded;
    if (lowerCat.contains('pepito')) return defaultPepitoMixto;
    if (lowerCat.contains('salchipapa') || lowerCat.contains('papa'))
      return defaultSalchipapasLoaded;
    if (lowerCat.contains('bebida')) return defaultDrink;
    if (lowerCat.contains('postre')) return defaultDessert;

    // 4. Default Hero Burger
    return defaultHeroBurger;
  }
}
