"""仅检查审计交付文档和主基线哈希，不重审其他任务业务源码。"""
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent
AUDIT=OUT.parents[1]
ROOT=AUDIT.parents[2]


def digest(path):
    """只读计算SHA256，不导入或执行业务模块。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    """读取所有现有三类任务文档并记录交付检查依据。"""
    documents=[];sections=[];missing_documents=[]
    for directory in sorted((AUDIT/'tasks').glob('T[0-9][0-9]')):
        for filename in ('issues.md','questions.md','report.md'):
            path=directory/filename
            if not path.exists():
                missing_documents.append(str(path.relative_to(ROOT)).replace('\\','/'));continue
            text=path.read_text(encoding='utf-8-sig')
            documents.append({'path':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':digest(path),'bytes':path.stat().st_size,
                              'line_count':len(text.splitlines()),'read_scope':'全文UTF-8只读；只核交付，未执行其probe或重审其业务文件'})
            if filename=='issues.md':
                matches=list(re.finditer(r'^##\s+(.*)$',text,re.M))
                for index,match in enumerate(matches):
                    title=match.group(1);identifier=re.search(r'T\d{2}-I\d+',title)
                    if not identifier:continue
                    block=text[match.end():matches[index+1].start() if index+1<len(matches) else len(text)]
                    prefix=text[:matches[0].start()] if matches else text
                    # 只作字段索引，字段缺失须人工判断全局声明/对象表是否已提供。
                    checks={'severity':bool(re.search('严重度|P[123]|High|Medium|Low',block+title+prefix)),
                            'ownership':bool(re.search('主责|协同',block+prefix)),
                            'rule_basis':bool(re.search('依据|规则|原文',block)),
                            'implementation':bool(re.search('代码|位置|\.py[:：]|\.js[:：]|\.toml',block)),
                            'minimal_input':bool(re.search('最小|输入|步骤|复现',block)),
                            'expected_actual':bool(re.search('预期|应|expected',block) and re.search('实际|actual|抛|返回',block)),
                            'impact':bool(re.search('影响|范围|对象',block)),
                            'evidence':bool(re.search('证据|probe|repro|\.json',block))}
                    sections.append({'item_id':identifier.group(),'title':title,'document':str(path.relative_to(ROOT)).replace('\\','/'),
                                     'line':text[:match.start()].count('\n')+1,'field_index':checks,
                                     'automatic_missing_candidates':[key for key,value in checks.items() if not value],
                                     'limits':'字段索引不自动证明依据支持结论，也不替代实际输入运行；详见人工final_review.md'})
    with (AUDIT/'baseline_files.csv').open(encoding='utf-8-sig',newline='') as stream:baseline=list(csv.DictReader(stream))
    hashes=[]
    for row in baseline:
        if row['owner'] not in {'T07','T08','T09'}:continue
        path=ROOT/row['path']
        actual=digest(path) if path.exists() else None
        hashes.append({'owner':row['owner'],'path':row['path'],'baseline_sha256':row['sha256'],'current_sha256':actual,
                       'matches':actual==row['sha256'],'baseline_bytes':int(row['bytes']),'current_bytes':path.stat().st_size if path.exists() else None})
    baseline_head=json.loads((AUDIT/'baseline.json').read_text(encoding='utf-8'))['head']
    result={'created_utc':datetime.now(timezone.utc).isoformat(),'baseline_head':baseline_head,
            'scope':'所有tasks/Txx现有issues/questions/report全文只读；业务文件仅对本人T07/08/09所属基线项读取字节计算哈希，不解释或重审源码',
            'document_count':len(documents),'missing_documents':missing_documents,'documents':documents,
            'issue_count_before_dedup':len(sections),'issue_sections':sections,
            'hash_scope':{'baseline':'baseline_files.csv按owner=T07/T08/T09选择；新增审计文档不在业务基线，只有本次文档指纹，不能声称其相对开审时已稳定',
                          'file_count':len(hashes),'all_match':all(row['matches'] for row in hashes),'files':hashes},
            'manual_review':'final_review.md；主汇总由主协调生成，本任务不修改其他任务文件'}
    (OUT/'final_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'documents':len(documents),'missing_documents':missing_documents,'issue_sections':len(sections),
                      'automatic_missing_candidates':[{key:row[key] for key in ('item_id','automatic_missing_candidates')} for row in sections if row['automatic_missing_candidates']],
                      'hashes':hashes},ensure_ascii=False))


if __name__=='__main__':main()
