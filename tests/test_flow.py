"""Testes do pacote; não substituem os testes do aplicativo KIROS."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]

class FlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kiros-flow-')
        self.root = Path(self.temp.name)/'project with spaces'
        shutil.copytree(SOURCE, self.root, ignore=shutil.ignore_patterns('__pycache__', '.kiros', '.git'))
        self.script = self.root/'scripts/kiros_flow.py'
        # Cada cenário parte de um pacote novo, independentemente do avanço real.
        # Alterar somente a cópia temporária; preservar as asserções de transição.
        state = self.state()
        for milestone in state['milestones']:
            milestone['status'] = 'pending'
            milestone['checkpoint'] = None
            milestone['blocker'] = None
            milestone.pop('last_failure', None)
        self.write_json('docs/milestones.yaml', state)

    def tearDown(self):
        self.temp.cleanup()

    def run_flow(self,*args,expected=0,env=None):
        result=subprocess.run([sys.executable,str(self.script),*args],cwd=self.temp.name,
                              capture_output=True,text=True,env=env)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return result

    def state(self):
        return json.loads((self.root/'docs/milestones.yaml').read_text())

    def write_json(self,path,data):
        (self.root/path).write_text(json.dumps(data))

    def prepare(self,code='pass'):
        self.run_flow('start')
        state=self.state(); m=state['milestones'][0]
        self.write_json('docs/checks.json',{'M00':[{'name':'fixture local','argv':[sys.executable,'-c',code],'timeout_seconds':5}]})
        report={'milestone':'M00','summary':'Teste isolado do mecanismo', 'critical_errors':[],
                'limitations':['Fixture; não é evidência do aplicativo.'],
                'acceptance':{a['id']:{'files':['README.md'],'verification':'Fixture do teste de orquestração'} for a in m['acceptance']}}
        self.write_json('docs/evidence/M00.json',report)
        return report

    def test_original_manifest_and_coverage(self):
        self.run_flow('validate')
        state=self.state()
        self.assertEqual(len(state['milestones']),13)
        self.assertTrue(all(m['status']=='pending' for m in state['milestones']))

    def test_selective_context(self):
        text=self.run_flow('context').stdout
        self.assertIn('# 5. Arquitetura',text)
        self.assertNotIn('# 27. Product Fidelity',text)

    def test_changed_spec_refuses_execution(self):
        with (self.root/'docs/kiros-studio-v1-spec.md').open('a') as f: f.write('alteração')
        self.run_flow('start',expected=2)

    def test_empty_checks_cannot_complete(self):
        self.prepare()
        self.write_json('docs/checks.json',{'M00':[]})
        self.run_flow('checkpoint','docs/evidence/M00.json',expected=2)
        self.assertEqual(self.state()['milestones'][0]['status'],'in_progress')

    def test_incomplete_evidence_cannot_complete(self):
        report=self.prepare(); report['acceptance'].pop('M00-A01')
        self.write_json('docs/evidence/M00.json',report)
        self.run_flow('checkpoint','docs/evidence/M00.json',expected=2)

    def test_external_evidence_rejected(self):
        report=self.prepare(); report['acceptance']['M00-A01']['files']=['/etc/hosts']
        self.write_json('docs/evidence/M00.json',report)
        self.run_flow('checkpoint','docs/evidence/M00.json',expected=2)

    def test_failed_check_preserves_current_milestone(self):
        self.prepare('raise SystemExit(1)')
        self.run_flow('checkpoint','docs/evidence/M00.json',expected=2)
        self.assertEqual(self.state()['milestones'][0]['status'],'in_progress')
        self.assertEqual(self.state()['milestones'][1]['status'],'pending')

    def test_timeout_preserves_status(self):
        self.prepare()
        self.write_json('docs/checks.json',{'M00':[{'argv':[sys.executable,'-c','import time; time.sleep(5)'],'timeout_seconds':1}]})
        self.run_flow('checkpoint','docs/evidence/M00.json',expected=2)
        self.assertEqual(self.state()['milestones'][0]['status'],'in_progress')

    def test_success_checkpoint_then_next_remains_pending(self):
        self.prepare()
        self.run_flow('checkpoint','docs/evidence/M00.json')
        state=self.state()
        self.assertEqual(state['milestones'][0]['status'],'completed')
        self.assertEqual(state['milestones'][1]['status'],'pending')
        cp=json.loads((self.root/state['milestones'][0]['checkpoint']['path']).read_text())
        self.assertEqual(cp['checks'][0]['exit_code'],0)
        self.assertIn('README.md',cp['evidence_sha256'])
        self.assertIn('M01',self.run_flow('context').stdout)
        self.run_flow('checkpoint','docs/evidence/M00.json',expected=2)

    def test_mock_environment_passed_to_checks(self):
        self.prepare("import os; assert os.environ['KIROS_PROVIDER_MODE']=='mock'; assert os.environ['KIROS_ALLOW_PAID_APIS']=='0'; assert os.environ['KIROS_ALLOW_PUBLISH']=='0'")
        self.run_flow('checkpoint','docs/evidence/M00.json')

    def test_block_and_resume(self):
        self.run_flow('block','Aguardando dado indispensável')
        self.assertEqual(self.state()['milestones'][0]['status'],'blocked')
        self.run_flow('start')
        self.assertEqual(self.state()['milestones'][0]['status'],'in_progress')

    def test_state_lock_rejects_concurrent_mutation(self):
        (self.root/'.kiros').mkdir(exist_ok=True)
        with (self.root/'.kiros/state.lock').open('w') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.run_flow('start',expected=2)

    def test_rebuild_status(self):
        (self.root/'docs/STATUS.md').write_text('desatualizado')
        self.run_flow('status')
        self.assertIn('M00',(self.root/'docs/STATUS.md').read_text())

    def test_out_of_order_completion_is_invalid(self):
        state=self.state(); state['milestones'][1]['status']='completed'
        state['milestones'][1]['checkpoint']={'path':'README.md'}
        self.write_json('docs/milestones.yaml',state)
        self.run_flow('validate',expected=2)

    def test_cli_exit_zero_does_not_complete_milestone(self):
        bindir=Path(self.temp.name)/'bin'; bindir.mkdir()
        fake=bindir/'codex'; fake.write_text('#!/bin/sh\nexit 0\n'); fake.chmod(0o755)
        env=dict(os.environ,PATH=str(bindir)+os.pathsep+os.environ.get('PATH',''))
        self.run_flow('run','--exec',expected=2,env=env)
        self.assertEqual(self.state()['milestones'][0]['status'],'pending')

    def test_final_readiness_requires_real_validation(self):
        state=self.state()
        for m in state['milestones'][:-1]:
            m['status']='completed'; m['checkpoint']={'path':'README.md','at':'fixture'}
        state['milestones'][-1]['status']='in_progress'
        self.write_json('docs/milestones.yaml',state)
        m=state['milestones'][-1]
        report={'milestone':'M12','summary':'Fixture', 'critical_errors':[], 'limitations':[], 'real_readiness':False,
                'acceptance':{a['id']:{'files':['README.md'],'verification':'Fixture'} for a in m['acceptance']}}
        self.write_json('docs/evidence/M12.json',report)
        result=self.run_flow('checkpoint','docs/evidence/M12.json',expected=2)
        self.assertIn('Aceite real pendente',result.stderr)

if __name__=='__main__':
    unittest.main()
