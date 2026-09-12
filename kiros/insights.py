"""M10: análise local descritiva, com proveniência e autorização de experimentos.

Sem scraping, inferência visual, LLM, publicação ou coleta de analytics. Campos
ausentes são desconhecidos. Avaliações de tendências são fornecidas pelo operador.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import uuid


DIMENSIONS = {
    'environment': 'Ambiente', 'architecture': 'Arquitetura', 'material': 'Material',
    'palette': 'Paleta', 'framing': 'Enquadramento', 'camera_distance': 'Distância da câmera',
    'angle': 'Ângulo', 'lighting': 'Iluminação', 'composition': 'Composição',
    'layout': 'Layout', 'product': 'Produto', 'decoration': 'Decoração',
    'photo_style': 'Estilo fotográfico', 'fragrance': 'Fragrância', 'theme': 'Tema',
    'pillar': 'Pilar', 'format': 'Formato', 'cta': 'CTA', 'campaign': 'Campanha',
}
VARIABLES = {
    'image': ('Imagem', 'medium'), 'composition': ('Composição', 'medium'),
    'copy': ('Copy', 'medium'), 'cta': ('CTA', 'medium'),
    'framing': ('Enquadramento', 'low'), 'palette': ('Paleta', 'low'),
    'product': ('Produto', 'high'), 'other': ('Outra variável', 'high'),
}
RISK_LABELS = {'low': 'Baixo', 'medium': 'Médio', 'high': 'Alto'}
STATES = {'awaiting_approval': 'Aguardando aprovação', 'approved': 'Aprovado',
          'running': 'Em acompanhamento local', 'completed': 'Resultado registrado'}
TREND_FIELDS = ('trend', 'relevance', 'saturation', 'copy_risk', 'kiros_interpretation',
                'potential', 'confidence', 'recommendation')
TREND_LABELS = ('Tendência', 'Relevância', 'Saturação', 'Risco de cópia',
                'Interpretação KIROS', 'Potencial', 'Confiança', 'Recomendação')


def clean(value, label, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label}: preencha texto com até {limit} caracteres.')
    return value.strip()


def timestamp(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError()
        return dt.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise ValueError('Data inválida: informe data, horário e fuso (ex.: 2026-09-12T15:00:00-03:00).') from None


class InsightsService:
    def __init__(self, database, clock=None):
        self.db = database
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def connect(self):
        conn = sqlite3.connect(self.db.path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def now(self):
        return self.clock().astimezone(timezone.utc)

    def record_diversity(self, title, dimensions, occurred_at, source,
                         campaign_id=None, intentional_reason=''):
        title, source = clean(title, 'Título'), clean(source, 'Origem')
        occurred = timestamp(occurred_at)
        if occurred > self.now():
            raise ValueError('Observação de histórico não pode estar no futuro.')
        if not isinstance(dimensions, dict) or not dimensions or set(dimensions) - DIMENSIONS.keys():
            raise ValueError('Informe pelo menos uma dimensão conhecida.')
        values = {k: clean(v, DIMENSIONS[k], 200) for k, v in dimensions.items()}
        if campaign_id:
            with self.connect() as conn:
                if not conn.execute('SELECT 1 FROM campaigns WHERE id=?', (campaign_id,)).fetchone():
                    raise ValueError('Campanha não encontrada.')
            values['campaign'] = campaign_id
        if intentional_reason:
            intentional_reason = clean(intentional_reason, 'Motivo da repetição')
        oid = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute('INSERT INTO diversity_observations VALUES (?,?,?,?,?,?,?,?)',
                         (oid, campaign_id, title, json.dumps(values), occurred.isoformat(),
                          source, intentional_reason, self.now().isoformat()))
        return oid

    def saturation(self, days=30):
        if type(days) is not int or not 1 <= days <= 365:
            raise ValueError('Janela deve ter de 1 a 365 dias.')
        now = self.now()
        cutoff = now - timedelta(days=days)
        samples = []
        with self.connect() as conn:
            for row in conn.execute('SELECT * FROM diversity_observations'):
                when = timestamp(row['occurred_at'])
                if cutoff <= when <= now:
                    samples.append({'id': row['id'], 'title': row['title'], 'time': when,
                                    'dimensions': json.loads(row['dimensions_json']),
                                    'source': row['source'], 'scope': 'observação informada',
                                    'intentional_reason': row['intentional_reason']})
            # Calendário planejado e histórico informado têm escopos separados.
            # Não inferir atributos visuais a partir de prompts ou de nomes de produto.
            for row in conn.execute("SELECT * FROM calendar_entries WHERE status NOT IN ('draft','cancelled','canceled','archived')"):
                value = row['selected_time'] or row['scheduled_for']
                if not value:
                    continue
                try:
                    when = timestamp(value)
                except ValueError:
                    continue
                if cutoff <= when <= now:
                    dims = {'pillar': row['pillar'], 'format': row['content_type']}
                    if row['campaign_id']:
                        dims['campaign'] = row['campaign_id']
                    if row['seasonal_tag']:
                        dims['theme'] = row['seasonal_tag']
                    samples.append({'id': row['id'], 'title': row['title'], 'time': when,
                                    'dimensions': dims, 'source': 'Calendário local / ' + row['status'],
                                    'scope': 'calendário', 'intentional_reason': ''})
        maps = []
        for scope in ('observação informada', 'calendário'):
            group = [s for s in samples if s['scope'] == scope]
            for key, label in DIMENSIONS.items():
                known = [s for s in group if s['dimensions'].get(key)]
                counts = Counter(s['dimensions'][key].strip().casefold() for s in known)
                for value, count in counts.most_common():
                    subset = [s for s in known if s['dimensions'][key].strip().casefold() == value]
                    share = count / len(known)
                    maps.append({'dimension': key, 'label': label, 'value': value,
                                 'count': count, 'known': len(known), 'unknown': len(group) - len(known),
                                 'share': round(share * 100, 1), 'scope': scope,
                                 'last_seen': max(s['time'] for s in subset).isoformat(),
                                 'per_week': round(count * 7 / days, 2),
                                 'warning': count >= 3 and share >= .5})
        return {'days': days, 'samples': samples, 'map': maps,
                'missing_dimensions': [label for key, label in DIMENSIONS.items()
                                       if not any(s['dimensions'].get(key) for s in samples)],
                'basis': 'Alerta descritivo: ao menos 3 ocorrências e 50% dos registros conhecidos na janela. '
                         'Frequência é a média por 7 dias; calendário não comprova publicação. '
                         'Repetição intencional permanece permitida.'}

    def record_competitor(self, profile, category, location, source, observed_at,
                          observation, trend, is_mock=False):
        fields = [clean(v, name) for v, name in ((profile, 'Perfil'), (category, 'Categoria'),
                  (location, 'Localização'), (source, 'Fonte'), (observation, 'Observação'))]
        observed = timestamp(observed_at)
        if observed > self.now():
            raise ValueError('A data da fonte não pode estar no futuro.')
        if type(is_mock) is not bool:
            raise ValueError('Identificação de simulação inválida.')
        if not isinstance(trend, dict) or set(trend) != set(TREND_FIELDS):
            raise ValueError('Preencha todos os oito campos da tendência.')
        assessment = {key: clean(trend[key], label) for key, label in zip(TREND_FIELDS, TREND_LABELS)}
        oid = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute('INSERT INTO competitive_observations VALUES (?,?,?,?,?,?,?,?,?,?)',
                         (oid, *fields[:4], observed.isoformat(), self.now().isoformat(),
                          int(is_mock), fields[4], json.dumps(assessment)))
        return oid

    def discover(self, category='', location='', profile='', include_mock=False):
        # Literal matching rather than SQL LIKE wildcards supplied by the user.
        with self.connect() as conn:
            rows = conn.execute('SELECT * FROM competitive_observations ORDER BY recorded_at DESC,id').fetchall()
        result = []
        for row in rows:
            if row['is_mock'] and not include_mock:
                continue
            if any(query.strip().casefold() not in row[field].casefold()
                   for field, query in (('category', category), ('location', location), ('profile', profile))):
                continue
            item = dict(row)
            item['trend'] = json.loads(item.pop('trend_json'))
            result.append(item)
        return result

    def create_experiment(self, hypothesis, control, variant, variable, metric,
                          protected_change=False, authorization='', operator=''):
        hypothesis, control, variant, metric = [clean(v, name) for v, name in (
            (hypothesis, 'Hipótese'), (control, 'Controle'), (variant, 'Variante'), (metric, 'Métrica'))]
        if control.casefold() == variant.casefold():
            raise ValueError('Controle e variante devem ser diferentes.')
        if variable not in VARIABLES or type(protected_change) is not bool:
            raise ValueError('Variável ou classificação inválida.')
        risk = 'high' if protected_change else VARIABLES[variable][1]
        reason = ('Afeta identidade, direitos ou dados comerciais protegidos.' if protected_change else
                  'Classificação conservadora pela variável: ' + VARIABLES[variable][0] + '.')
        if authorization:
            authorization = clean(authorization, 'Referência da autorização')
            operator = clean(operator, 'Responsável pela autorização', 120)
        # Existing scope authorization only covers low risk. It cannot auto-approve others.
        approved = risk == 'low' and bool(authorization)
        eid, now = uuid.uuid4().hex, self.now().isoformat()
        with self.connect() as conn:
            conn.execute('INSERT INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (eid, hypothesis, control, variant, variable, metric, risk, reason,
                          'approved' if approved else 'awaiting_approval', authorization,
                          operator if approved else None, now if approved else None, now, None))
            self._event(conn, eid, 'created', operator or 'Operador local', reason)
        return eid

    def _event(self, conn, eid, action, operator, detail):
        conn.execute('INSERT INTO experiment_events VALUES (?,?,?,?,?,?)',
                     (uuid.uuid4().hex, eid, action, operator, detail, self.now().isoformat()))

    def approve_experiment(self, eid, operator, confirmation, authorization):
        operator = clean(operator, 'Responsável', 120)
        authorization = clean(authorization, 'Escopo da aprovação')
        if confirmation is not True:
            raise PermissionError('Confirme explicitamente a aprovação deste experimento.')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            cur = conn.execute("UPDATE experiments SET state='approved', approved_by=?, approved_at=?, authorization=? "
                               "WHERE id=? AND state='awaiting_approval'",
                               (operator, self.now().isoformat(), authorization, eid))
            if cur.rowcount != 1:
                raise ValueError('Experimento não encontrado ou já aprovado.')
            self._event(conn, eid, 'approved', operator, authorization)

    def start_experiment(self, eid, operator):
        operator = clean(operator, 'Responsável', 120)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            cur = conn.execute("UPDATE experiments SET state='running' WHERE id=? AND state='approved' "
                               "AND approved_by IS NOT NULL AND authorization != ''", (eid,))
            if cur.rowcount != 1:
                raise PermissionError('Acompanhamento exige aprovação válida; verifique o estado do experimento.')
            self._event(conn, eid, 'started_local', operator, 'Acompanhamento local. Não gera nem publica conteúdo.')

    def record_result(self, eid, control_sample, control_successes, variant_sample,
                      variant_successes, source, operator):
        source, operator = clean(source, 'Fonte do resultado'), clean(operator, 'Responsável', 120)
        values = (control_sample, control_successes, variant_sample, variant_successes)
        if any(type(v) is not int or not 0 <= v <= 1_000_000_000 for v in values):
            raise ValueError('Amostras e eventos devem ser inteiros não negativos, até 1 bilhão.')
        if min(control_sample, variant_sample) == 0 or control_successes > control_sample or variant_successes > variant_sample:
            raise ValueError('Cada braço precisa de amostra positiva e eventos menores ou iguais à amostra.')
        small = min(control_sample, variant_sample) < 100
        result = {'control_sample': control_sample, 'control_successes': control_successes,
                  'variant_sample': variant_sample, 'variant_successes': variant_successes,
                  'control_rate': round(100 * control_successes / control_sample, 3),
                  'variant_rate': round(100 * variant_successes / variant_sample, 3),
                  'source': source, 'recorded_at': self.now().isoformat(),
                  'confidence': 'baixa — amostra pequena' if small else 'limitada — análise descritiva',
                  'conclusion': 'Sem vencedor declarado. ' + ('Amostra pequena; recolha mais observações.' if small else
                      'Diferenças observadas não demonstram causalidade nem significância estatística.'),
                  'basis': '100 observações por braço é apenas um limiar de cautela, não cálculo de poder estatístico.'}
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            cur = conn.execute("UPDATE experiments SET state='completed',result_json=? WHERE id=? AND state='running'",
                               (json.dumps(result), eid))
            if cur.rowcount != 1:
                raise PermissionError('Registre resultado somente após iniciar o acompanhamento; resultados são preservados.')
            self._event(conn, eid, 'result_recorded', operator, json.dumps(result))
        return result

    def experiments(self):
        with self.connect() as conn:
            result = []
            for row in conn.execute('SELECT * FROM experiments ORDER BY created_at DESC,id'):
                item = dict(row)
                item['result'] = json.loads(item.pop('result_json') or 'null')
                item['events'] = [dict(e) for e in conn.execute(
                    'SELECT * FROM experiment_events WHERE experiment_id=? ORDER BY recorded_at,rowid', (item['id'],))]
                result.append(item)
            return result
