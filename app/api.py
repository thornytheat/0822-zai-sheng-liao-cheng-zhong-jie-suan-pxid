from flask import Blueprint, Response, current_app, jsonify, request

from app.business import DomainIssue
from app.evidence.render import artifact
from app.inputs import read_input
from app.modules.pipeline import run
from app.review.corrections import submit
from app.review.service import execute, review

api = Blueprint('api',__name__,url_prefix='/api')
STAGES = {'intake':1,'prepare':2,'calculate':3,'policy':4,'balance':5}


@api.post('/stages/<stage>')
def preview(stage):
    if stage not in STAGES:
        raise DomainIssue('STAGE_UNKNOWN')
    return jsonify(run(read_input(),STAGES[stage]))


@api.route('/runs',methods=['GET','POST'])
def runs():
    store = current_app.extensions['runs']
    if request.method == 'GET':
        return jsonify(items=store.list())
    report = execute(store,read_input())
    report['ledger'] = store.ledger(report['id'])
    return jsonify(report)


@api.route('/runs/<run_id>', methods=['GET','PATCH'])
def batch(run_id):
    store = current_app.extensions['runs']
    if request.method == 'GET':
        report = store.load(run_id)
        report['ledger'] = store.ledger(run_id)
        return jsonify(report)
    result = review(store,run_id,request.get_json(silent=True))
    result['ledger'] = store.ledger(run_id)
    return jsonify(result)


@api.get('/runs/<run_id>/ledger')
def ledger(run_id):
    return jsonify(current_app.extensions['runs'].ledger(run_id))


@api.route('/runs/<run_id>/corrections', methods=['GET','POST'])
def corrections(run_id):
    store = current_app.extensions['runs']
    if request.method == 'GET':
        return jsonify(items=store.corrections(run_id))
    reference = request.form.get('reference')
    return jsonify(submit(store,run_id,read_input(),reference))


@api.get('/runs/<run_id>/corrections/<correction_id>')
def correction(run_id, correction_id):
    return jsonify(current_app.extensions['runs'].correction(run_id,correction_id))


@api.get('/runs/<run_id>/evidence')
def export(run_id):
    store = current_app.extensions['runs']
    report = store.load(run_id)
    return Response(artifact(report, store.ledger(run_id)),mimetype='application/json', headers={
        'Content-Disposition':f'attachment; filename="review-{report["id"][:12]}.json"',
        'Cache-Control':'no-store',
    })
