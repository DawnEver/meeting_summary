from __future__ import annotations

import argparse
import contextlib
import threading
import time
import webbrowser

from meeting_summary.web import app


def main():
    parser = argparse.ArgumentParser(prog='run_web', description='Run Meeting Summary Flask web UI')
    parser.add_argument('--host', default='0.0.0.0')  # noqa: S104
    parser.add_argument('--port', default=8000, type=int)
    parser.add_argument('--no-browser', action='store_true', dest='no_browser')
    args = parser.parse_args()

    url = f'http://{args.host if args.host != "0.0.0.0" else "localhost"}:{args.port}/'  # noqa: S104

    if not args.no_browser:
        # Open browser shortly after server starts
        def _open():
            # wait a bit for server to bind
            time.sleep(1.0)
            with contextlib.suppress(Exception):
                webbrowser.open(url)

        th = threading.Thread(target=_open, daemon=True)
        th.start()

    # Run the Flask app (blocking)
    print(f'Starting Meeting Summary web UI at {url} (press CTRL+C to stop)')
    app.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
