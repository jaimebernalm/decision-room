"""Persistent business selection and profile for the authenticated local owner."""
import hashlib
import json
from uuid import uuid4

from ..database import connect
from .errors import WebError, bounded, identifier


def profile(db, business_id):
    row = db.execute('''SELECT b.id,b.name,b.description,b.created_at,
        w.profile_revision,w.onboarding_status,w.updated_at
        FROM web_businesses w JOIN businesses b ON b.id=w.business_id
        WHERE b.id=%s''', (business_id,)).fetchone()
    if not row:
        raise WebError('No encontramos este negocio en tu espacio local.', 404)
    return row


def state(config):
    with connect(config) as db, db.transaction():
        # Hold selection stable while constructing this response.
        selected = db.execute('SELECT active_business_id FROM web_workspace WHERE singleton FOR SHARE').fetchone()
        businesses = db.execute('''SELECT b.id,b.name,b.created_at,count(j.id) AS analysis_count
            FROM web_businesses w JOIN businesses b ON b.id=w.business_id
            LEFT JOIN web_jobs j ON j.business_id=b.id
            GROUP BY b.id ORDER BY b.created_at DESC,b.id''').fetchall()
        active = profile(db, selected['active_business_id']) if selected['active_business_id'] else None
    return {'business': active, 'businesses': businesses}


def save(config, data):
    if not isinstance(data, dict):
        raise WebError('Los datos del negocio no son válidos.')
    name = bounded(data.get('name'), 'el nombre del negocio', 100)
    description = bounded(data.get('description'), 'la descripción del negocio', 6000)
    with connect(config) as db, db.transaction():
        selected = db.execute('SELECT active_business_id FROM web_workspace WHERE singleton FOR UPDATE').fetchone()
        if data.get('business_id'):
            business_id = identifier(data['business_id'])
            if business_id != selected['active_business_id']:
                raise WebError('El negocio activo ha cambiado. Vuelve a abrir el formulario.', 409)
            current = profile(db, business_id)
            revision = data.get('profile_revision')
            if type(revision) is not int or revision != current['profile_revision']:
                # An identical retry after a successful save does not add a revision.
                if not (type(revision) is int and revision == current['profile_revision'] - 1
                        and (name, description) == (current['name'], current['description'])):
                    raise WebError('El contexto ha cambiado en otra página. Recárgalo antes de editar.', 409)
                return current
            if (name, description) != (current['name'], current['description']):
                db.execute('UPDATE businesses SET name=%s,description=%s WHERE id=%s', (name, description, business_id))
                db.execute('''UPDATE web_businesses SET profile_revision=profile_revision+1,updated_at=now()
                    WHERE business_id=%s''', (business_id,))
        else:
            key = identifier(data.get('request_key'))
            signature = hashlib.sha256(json.dumps([name, description], ensure_ascii=False).encode()).hexdigest()
            old = db.execute('SELECT * FROM web_businesses WHERE creation_key=%s', (key,)).fetchone()
            if old:
                if old['creation_sha256'] != signature or old['business_id'] != selected['active_business_id']:
                    raise WebError('Este formulario ya se guardó o el negocio activo ha cambiado.', 409)
                return profile(db, old['business_id'])
            # Creating another business is explicit and tied to the selection
            # seen by the form, so an old tab cannot replace the current choice.
            expected = identifier(data['expected_active_id']) if data.get('expected_active_id') else None
            if selected['active_business_id'] != expected:
                raise WebError('El negocio activo ha cambiado. Vuelve a abrir el formulario.', 409)
            business_id = uuid4()
            db.execute('INSERT INTO businesses(id,name,description) VALUES (%s,%s,%s)', (business_id, name, description))
            db.execute('INSERT INTO web_businesses(business_id,creation_key,creation_sha256) VALUES (%s,%s,%s)',
                       (business_id, key, signature))
            db.execute('UPDATE web_workspace SET active_business_id=%s WHERE singleton', (business_id,))
        return profile(db, business_id)


def select(config, data):
    if not isinstance(data, dict):
        raise WebError('Selecciona un negocio de tu espacio local.')
    business_id = identifier(data.get('business_id'))
    with connect(config) as db, db.transaction():
        db.execute('SELECT singleton FROM web_workspace WHERE singleton FOR UPDATE')
        current = profile(db, business_id)
        db.execute('UPDATE web_workspace SET active_business_id=%s WHERE singleton', (business_id,))
        return current
