#!/usr/bin/env python3
"""Orquestração local sem dependências; milestones.yaml usa o subconjunto JSON de YAML 1.2."""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/milestones.yaml'
SPEC = ROOT / 'docs/kiros-studio-v1-spec.md'

def fail(message):
    raise ValueError(message)

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def dump(path, data):
    atomic(path, json.dumps(data, ensure_ascii=False, indent=2)+'\n')

@contextlib.contextmanager
def lock(name):
    directory = ROOT / '.kiros'
    directory.mkdir(exist_ok=True)
    with (directory/name).open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail('Já existe uma execução ativa. Aguarde seu término.')
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

def local_file(name):
    path = (ROOT/name).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        fail('Evidência inexistente ou fora do projeto: '+str(name))
    return path

def read_state():
    state = json.loads(MANIFEST.read_text())
    if state.get('schema_version') != 1:
        fail('Versão do manifesto incompatível.')
    if digest(SPEC) != state['spec_sha256']:
        fail('A especificação mudou. Reconcilie milestones e cobertura antes de continuar; não atualize só o hash.')
    ids = set()
    incomplete = False
    for m in state['milestones']:
        if m['id'] in ids or any(d not in ids for d in m['depends_on']):
            fail('IDs duplicados ou dependência inválida.')
        ids.add(m['id'])
        if m['status'] not in ('pending','in_progress','blocked','completed'):
            fail('Status inválido.')
        if m['status'] == 'completed':
            if incomplete or not m.get('checkpoint'):
                fail('Conclusão sem checkpoint ou fora da sequência.')
        else:
            incomplete = True
        local_file(m['file'])
    return state

def current(state):
    return next((m for m in state['milestones'] if m['status'] != 'completed'), None)

def status_text(state):
    m = current(state)
    lines = ['# Status do KIROS Studio V1', '', 'Gerado de `milestones.yaml`; não editar manualmente.', '',
             'Atual: '+(m['id']+' — '+m['title'] if m else 'Todas as milestones concluídas.'), '',
             '| Milestone | Estado | Checkpoint |', '|---|---|---|']
    for item in state['milestones']:
        cp = item.get('checkpoint')
        lines.append('| '+item['id']+' — '+item['title']+' | '+item['status']+' | '+(cp['path'] if cp else '—')+' |')
    if m and m.get('blocker'):
        lines.extend(['', 'Bloqueio: '+m['blocker']])
    lines.extend(['', 'Próxima ação: diga `continue` no Codex aberto nesta pasta. Uma execução termina no checkpoint.',
                  'Conclusões com mocks não comprovam integração real; consulte docs/INTEGRATIONS.md.'])
    return '\n'.join(lines)+'\n'

def save(state):
    dump(MANIFEST, state)
    atomic(ROOT/'docs/STATUS.md', status_text(state))

def context(state):
    m = current(state)
    if not m:
        return 'Todas as milestones concluídas. Não adicionar escopo.'
    spec = SPEC.read_text()
    matches = list(re.finditer(r'^# (\d+)\. .+$', spec, re.M))
    excerpts = []
    for i, match in enumerate(matches):
        if int(match[1]) in m['sections']:
            end = matches[i+1].start() if i+1<len(matches) else len(spec)
            excerpts.append(spec[match.start():end].strip())
    return ('Milestone atual: '+m['id']+' — '+m['title']+'\nEstado: '+m['status']+
            '\nLeia AGENTS.md, docs/CODEX_WORKFLOW.md e '+m['file']+
            '\nExecute somente esta milestone; atualize o status pelo script e pare.\n\n'+
            ('Bloqueio anterior: '+m['blocker']+'\n\n' if m.get('blocker') else '')+
            '\n\n'.join(excerpts))

def verify_report(m, path):
    report = json.loads(local_file(path).read_text())
    if report.get('milestone') != m['id'] or not report.get('summary','').strip():
        fail('Relatório deve identificar a milestone e resumir o resultado.')
    if report.get('critical_errors') != []:
        fail('Informe critical_errors como lista vazia somente se nenhum erro crítico permanece.')
    if not isinstance(report.get('limitations'), list):
        fail('Informe limitations como lista, inclusive quando vazia.')
    expected = {a['id'] for a in m['acceptance']}
    if set(report.get('acceptance',{})) != expected:
        fail('Relatório precisa cobrir todos os IDs de aceite, exatamente.')
    for evidence in report['acceptance'].values():
        if not evidence.get('verification','').strip() or not evidence.get('files'):
            fail('Cada critério exige descrição de verificação e arquivos existentes.')
        for file in evidence['files']:
            local_file(file)
    if m['id']=='M12' and report.get('real_readiness') is not True:
        fail('Aceite real pendente: registre bloqueio na M12. Não declarar V1 pronta somente com mocks.')
    return report

def checkpoint(state, report_path):
    m = current(state)
    if not m or m['status'] != 'in_progress':
        fail('Use start antes de concluir a milestone atual.')
    report = verify_report(m, report_path)
    checks = json.loads((ROOT/'docs/checks.json').read_text()).get(m['id'], [])
    if not checks:
        fail('Sem testes configurados para esta milestone em docs/checks.json.')
    for c in checks:
        if not isinstance(c.get('argv'),list) or not c['argv'] or not all(isinstance(x,str) and x for x in c['argv']):
            fail('Cada check exige argv como lista de argumentos.')
        if not isinstance(c.get('timeout_seconds'),int) or not 1<=c['timeout_seconds']<=3600:
            fail('Cada check exige timeout_seconds entre 1 e 3600.')
    attempt = ROOT/'docs/checkpoints'/m['id']/uuid.uuid4().hex
    attempt.mkdir(parents=True)
    env = dict(os.environ, KIROS_PROVIDER_MODE='mock', KIROS_ALLOW_PAID_APIS='0', KIROS_ALLOW_PUBLISH='0')
    results=[]
    for i,c in enumerate(checks):
        logfile=attempt/f'check-{i+1}.log'
        print('Validando: '+c.get('name',c['argv'][0]),flush=True)
        with logfile.open('w') as log:
            try:
                process=subprocess.Popen(c['argv'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    code=process.wait(timeout=c['timeout_seconds'])
                except subprocess.TimeoutExpired:
                    import signal
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    code=124
            except OSError as error:
                log.write(str(error))
                code=127
        results.append({'argv':c['argv'],'exit_code':code,'log':str(logfile.relative_to(ROOT))})
        dump(attempt/'checks.json',results)
        if code:
            m['last_failure']={'at':now(),'checks':str((attempt/'checks.json').relative_to(ROOT))}
            save(state)
            fail('Validação falhou; milestone continua in_progress. Consulte '+str(logfile.relative_to(ROOT)))
    # Hashes registram os arquivos de evidência no instante do checkpoint.
    paths={p for a in report['acceptance'].values() for p in a['files']}
    snapshot={'at':now(),'report':report,'checks':results,'evidence_sha256':{p:digest(local_file(p)) for p in sorted(paths)},'spec_sha256':state['spec_sha256']}
    dump(attempt/'checkpoint.json',snapshot)
    m['checkpoint']={'path':str((attempt/'checkpoint.json').relative_to(ROOT)),'at':snapshot['at']}
    m['status']='completed'
    m['blocker']=None
    m.pop('last_failure',None)
    save(state)
    print(m['id']+' concluída. Checkpoint registrado; pare antes da próxima milestone.')

def launch(state, exec_mode):
    m=current(state)
    if not m:
        print('Todas as milestones concluídas.'); return 0
    if not shutil.which('codex'):
        fail('Codex CLI não encontrado. Abra esta pasta no app Codex e diga continue, ou instale a CLI.')
    prompt=('Continue o KIROS Studio V1 seguindo AGENTS.md e docs/CODEX_WORKFLOW.md. '+
            'A milestone desta execução é '+m['id']+'. Use python3 scripts/kiros_flow.py context para os trechos relevantes. '+
            'Conclua somente essa milestone, registre evidências e checkpoint; não inicie a próxima. '+
            'Não chame scripts/continuar-codex de dentro desta execução.')
    command=['codex']+(['exec','--sandbox','workspace-write'] if exec_mode else [])+[prompt]
    with lock('run.lock'):
        result=subprocess.run(command,cwd=ROOT)
    # Retorno zero da CLI não equivale a aceite.
    latest=read_state()
    same=next(x for x in latest['milestones'] if x['id']==m['id'])
    atomic(ROOT/'docs/STATUS.md',status_text(latest))
    if result.returncode:
        return result.returncode
    if same['status']!='completed':
        print('A execução terminou sem checkpoint aprovado. Continue retomará '+m['id']+'.',file=sys.stderr)
        return 2
    return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('status','context','start','validate'):
        sub.add_parser(name)
    p=sub.add_parser('checkpoint'); p.add_argument('report')
    p=sub.add_parser('block'); p.add_argument('reason')
    p=sub.add_parser('run'); p.add_argument('--exec',action='store_true',dest='exec_mode')
    args=parser.parse_args()
    if args.command=='run':
        return launch(read_state(),args.exec_mode)
    with lock('state.lock'):
        state=read_state(); m=current(state)
        if args.command=='context': print(context(state))
        elif args.command=='status':
            atomic(ROOT/'docs/STATUS.md',status_text(state)); print(status_text(state))
        elif args.command=='validate':
            sections=[s for item in state['milestones'] for s in item['sections']]
            if sorted(sections)!=list(range(1,87)): fail('Cobertura de seções inválida.')
            for item in state['milestones']:
                if item['checkpoint']: local_file(item['checkpoint']['path'])
            print('Manifesto, origem e cobertura das 86 seções válidos.')
        elif args.command=='start':
            if not m: fail('Nenhuma milestone pendente.')
            m['status']='in_progress'; m['blocker']=None; save(state)
            print('Retomar/implementar somente '+m['id'])
        elif args.command=='block':
            if not m or not args.reason.strip(): fail('Milestone ou motivo ausente.')
            m['status']='blocked'; m['blocker']=args.reason; save(state)
        elif args.command=='checkpoint': checkpoint(state,args.report)
    return 0

if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,KeyError,OSError,TypeError) as error:
        print('KIROS: '+str(error),file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print('Interrompido. A milestone não foi avançada automaticamente.',file=sys.stderr)
        sys.exit(130)
