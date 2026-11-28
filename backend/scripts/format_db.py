"""Script CLI para formatear todos los registros de la base de datos."""

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.core.database import SessionLocal
from backend.app.services.db_format_service import format_database_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Formatea todos los registros de la base de datos.")
    parser.add_argument(
        "--keep-admin",
        action="store_true",
        help="Conserva las cuentas admin existentes y la bandera is_installed.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        counts = format_database_records(
            db,
            wipe_all_users_and_config=not args.keep_admin,
        )
        print("Base de datos formateada:", counts)
    finally:
        db.close()


if __name__ == "__main__":
    main()
