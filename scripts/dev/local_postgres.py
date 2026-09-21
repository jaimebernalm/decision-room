"""Manage a repo-local development cluster; no TCP listener or login service."""
import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[2]
BIN = Path(os.environ.get('DECISION_ROOM_PG_BIN', ROOT / '.tools/postgres/Postgres.app/Contents/Versions/18/bin'))
LOCAL = ROOT / '.local'
DATA = LOCAL / 'postgres'
SOCKET = LOCAL / 'pgsocket'
PORT = '55432'


def run(tool, *args, **kwargs):
    return subprocess.run([str(BIN / tool), *args], **kwargs)


def active():
    return DATA.exists() and run('pg_ctl', '-D', str(DATA), 'status', stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL).returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status', 'restart'])
    action = parser.parse_args().action
    if not (BIN / 'pg_ctl').exists():
        sys.exit('PostgreSQL binaries missing. Run scripts/dev/install_local_postgres.py or set DECISION_ROOM_PG_BIN.')
    if action == 'status':
        print('running' if active() else 'stopped')
        return
    if action in ('stop', 'restart') and active():
        run('pg_ctl', '-D', str(DATA), '-m', 'fast', '-w', 'stop', check=True)
    if action == 'stop':
        return
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    SOCKET.mkdir(mode=0o700, exist_ok=True)
    LOCAL.chmod(0o700)
    SOCKET.chmod(0o700)
    if not (DATA / 'PG_VERSION').exists():
        run('initdb', '-D', str(DATA), '--encoding=UTF8', '--locale=C',
            '--auth-local=peer', '--auth-host=reject', '-U', getpass.getuser(), check=True)
        socket_literal = str(SOCKET).replace("'", "''")
        with (DATA / 'postgresql.conf').open('a') as stream:
            stream.write(f"\nlisten_addresses = ''\nport = {PORT}\nunix_socket_directories = '{socket_literal}'\n"
                         "unix_socket_permissions = 0700\nmax_connections = 20\nshared_buffers = '64MB'\n")
    if not active():
        run('pg_ctl', '-D', str(DATA), '-l', str(LOCAL / 'postgres.log'), '-w', 'start', check=True)
    dsn = make_conninfo(host=str(SOCKET), port=PORT, user=getpass.getuser(), dbname='postgres')
    with psycopg.connect(dsn, autocommit=True) as db:
        if not db.execute('SELECT 1 FROM pg_database WHERE datname=%s', ('decision_room',)).fetchone():
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier('decision_room')))
    print('Local development PostgreSQL ready (private Unix socket, no TCP listener).')


if __name__ == '__main__':
    main()
