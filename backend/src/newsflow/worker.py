"""Worker process placeholder; task dispatch remains PostgreSQL-outbox driven."""

import time


def main() -> None:
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
