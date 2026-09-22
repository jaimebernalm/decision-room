"""Start the local owner workspace without exposing it to the network."""
import argparse
import logging
import os
import threading
import webbrowser

from ..config import Config
from ..database import migrate
from ..agent.model import ModelSettings
from .server import Server
from .service import Workspace


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--open', action='store_true', help='Open the authenticated local workspace in your browser.')
    args = parser.parse_args()
    config = Config.load()
    config.storage.mkdir(parents=True, exist_ok=True, mode=0o700)
    logging.basicConfig(filename=config.storage / 'web.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    migrate(config)
    try:
        settings = ModelSettings.load()
    except ValueError:
        settings = None
    workspace = Workspace(config, settings)
    server = Server(workspace, args.port)
    thread = threading.Thread(target=workspace.worker, name='decision-room-worker', daemon=True)
    thread.start()
    print(f'Decision Room: {server.origin}', flush=True)
    print('Local access key is stored privately in the configured storage directory (.web-access-key).', flush=True)
    if args.open:
        # Fragment is exchanged by JS then immediately removed; never sent in HTTP URLs.
        webbrowser.open(server.origin + '/#access=' + server.token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        workspace.stop.set()
        workspace.wake.set()
        server.server_close()


if __name__ == '__main__':
    main()
