#!/usr/bin/env python3
import json
import os
import shutil

# normalize_rule_json.py
# Reads rule.json, strips // comments and replaces Infinity, merges entries with identical params
# into a single object with 'params' and 'conditions': [{condition, buckets}, ...].

def load_raw_rule_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        txt = f.read()
    # remove lines starting with // (simple preprocessing)
    lines = []
    for line in txt.splitlines():
        stripped = line.lstrip()
        if stripped.startswith('//'):
            continue
        lines.append(line)
    txt = '\n'.join(lines)
    # replace bare Infinity with a large numeric sentinel
    txt = txt.replace('Infinity', '1e9')
    return json.loads(txt)


def merge_rules(rules):
    grouped = {}
    for item in rules:
        params = item.get('params', {}) or {}
        # use stable key
        key = json.dumps(params, sort_keys=True, default=str)
        if key not in grouped:
            grouped[key] = {'params': params, 'conditions': []}
        cond = {'condition': item.get('condition'), 'buckets': item.get('buckets', [])}
        grouped[key]['conditions'].append(cond)
    return list(grouped.values())


def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    rule_path = os.path.join(base_dir, 'rule.json')
    if not os.path.exists(rule_path):
        print('rule.json not found at', rule_path)
        return

    try:
        rules = load_raw_rule_json(rule_path)
    except Exception as e:
        print('Failed to parse rule.json:', e)
        return

    grouped = merge_rules(rules)

    # backup
    bak_path = rule_path + '.bak'
    shutil.copyfile(rule_path, bak_path)

    with open(rule_path, 'w', encoding='utf-8') as f:
        json.dump(grouped, f, ensure_ascii=False, indent=2)

    print(f'Grouped {len(rules)} entries into {len(grouped)} params groups.')
    print('Backup saved to', bak_path)
    print('Updated rule.json written to', rule_path)


if __name__ == '__main__':
    main()
