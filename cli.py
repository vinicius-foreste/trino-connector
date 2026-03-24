"""Minimal CLI entrypoint for the trino_connector package.

This is a lightweight placeholder so `pyproject.toml` can expose
`trino-connector` as a console script. Extend this to implement real
CLI behavior (connect, preview, extract, diagnostics).
"""

def main():
    import argparse

    parser = argparse.ArgumentParser(prog="trino-connector", description="Trino connector CLI")
    parser.add_argument("--version", action="store_true", help="Show package version")
    args = parser.parse_args()

    if args.version:
        print("trino_connector 0.1.0")
    else:
        print("Trino connector CLI — see README for usage and examples")


if __name__ == "__main__":
    main()
