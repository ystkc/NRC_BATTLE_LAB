"""只校正既有123探针的文字计数，不重新执行或覆盖手工补证。"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
probe = HERE / 'probe_output.json'
before_hash = hashlib.sha256(probe.read_bytes()).hexdigest()
cases = json.loads(probe.read_text(encoding='utf-8'))
assert len(cases) == 123 and len({x['case'] for x in cases}) == 123
changed = []
for name in ['report.py', 'issues.md', 'coverage.csv']:
    path = HERE / name
    old = path.read_bytes()
    text = old.decode('utf-8')
    updated = text.replace('122个探针', '123个探针').replace('122探针', '123探针')
    if updated != text:
        path.write_bytes(updated.encode('utf-8'))
        changed.append(name)
assert hashlib.sha256(probe.read_bytes()).hexdigest() == before_hash
checkpoint = json.loads((HERE / 'checkpoint.json').read_text(encoding='utf-8'))
assert checkpoint['cases'] == len(cases)
result = {'actual_json_cases': len(cases), 'unique_case_names': len({x['case'] for x in cases}), 'checkpoint_cases': checkpoint['cases'], 'report_count': 123, 'updated_text_only': changed, 'probe_output_sha256': before_hash, 'probe_output_unchanged': True, 'reran_probe': False, 'preserved_manual_issue_supplements': True}
(HERE / 'case_count_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
