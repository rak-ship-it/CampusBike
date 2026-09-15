"""Operator tools. Backups include private records: store them securely."""
import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from settings import DB_NAME


def copy_database(source, destination, restore=False):
    source=Path(source).resolve()
    destination=Path(destination).resolve()
    if not source.is_file():
        raise ValueError('Source database does not exist.')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('Source database failed integrity_check.')
        # Do not overwrite an existing database, including the live database.
        fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(fd)
        try:
            with closing(sqlite3.connect(destination)) as dst:
                src.backup(dst)
                if restore:
                    dst.execute('DELETE FROM mobile_sessions')
                    dst.commit()
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return str(destination)


def audit(path=DB_NAME):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        checks={
            'duplicate_active_students': "SELECT COUNT(*) FROM (SELECT student_id FROM rides WHERE returned_at IS NULL GROUP BY student_id HAVING COUNT(*)>1)",
            'duplicate_active_bikes': "SELECT COUNT(*) FROM (SELECT bike_id FROM rides WHERE returned_at IS NULL GROUP BY bike_id HAVING COUNT(*)>1)",
            'occupied_dock_mismatches': "SELECT COUNT(*) FROM slots sl LEFT JOIN bikes b ON b.bike_id=sl.bike_id WHERE sl.status='Occupied' AND (b.bike_id IS NULL OR b.status NOT IN ('Available','Maintenance') OR b.station_id IS NOT sl.station_id OR b.slot IS NOT sl.slot_number)",
            'active_ride_mismatches': "SELECT COUNT(*) FROM rides r LEFT JOIN bikes b ON b.bike_id=r.bike_id WHERE r.returned_at IS NULL AND (b.status IS NOT 'In use' OR b.current_user IS NOT r.student_id)",
        }
        return {'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],**{k:db.execute(q).fetchone()[0] for k,q in checks.items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('audit')
    backup=sub.add_parser('backup');backup.add_argument('destination')
    restore=sub.add_parser('restore');restore.add_argument('source');restore.add_argument('destination')
    args=parser.parse_args()
    try:
        if args.command=='audit':
            result=audit();print(json.dumps(result,indent=2))
            raise SystemExit(0 if result['integrity']=='ok' and not any(v for k,v in result.items() if k!='integrity') else 1)
        elif args.command=='backup':print(copy_database(DB_NAME,args.destination))
        else:print(copy_database(args.source,args.destination,restore=True))
    except (ValueError,sqlite3.Error,OSError) as error:
        parser.exit(1,str(error)+'\n')
