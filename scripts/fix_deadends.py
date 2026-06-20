"""
Fix all dead-end NoOp nodes across all n8n flows.
- Email flows (Gmail, mail.de): Quarantine/Injection dead-ends → Telegram alerts
- All flows: Not Job Related / Skip / Failed dead-ends → empty [] connections
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N8N = os.path.join(BASE, "n8n")


def load_json(path):
    for enc in ["utf-8", "utf-8-sig"]:
        try:
            with open(path, encoding=enc) as f:
                return json.load(f)
        except Exception:
            pass
    raise Exception(f"Cannot load {path}")


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def remove_nodes_by_name(nodes, names):
    return [n for n in nodes if n["name"] not in names]


def get_pos(nodes, name, fallback=None):
    n = next((x for x in nodes if x["name"] == name), None)
    return n["position"] if n else (fallback or [0, 0])


def fix_connections(conns, removed_names, renames=None):
    """
    Remove references to removed nodes in connections.
    Rename references where renames dict is provided.
    """
    renames = renames or {}
    new_conns = {}
    for src, cfg in conns.items():
        if src in removed_names:
            continue
        main = cfg.get("main", [])
        new_main = []
        for branch in main:
            new_branch = []
            for edge in branch:
                if edge["node"] in removed_names:
                    pass  # drop → becomes implicit []
                elif edge["node"] in renames:
                    new_branch.append({**edge, "node": renames[edge["node"]]})
                else:
                    new_branch.append(edge)
            new_main.append(new_branch)
        new_conns[src] = {"main": new_main}
    return new_conns


# ---------- Node templates ----------

def make_log_quarantine(flow_label, pos, node_id):
    return {
        "parameters": {
            "jsCode": (
                "const item = $input.item.json;\n"
                "const ni = item.normalized_input || {};\n"
                "const riskLevel = item.sender_risk_level || 'unknown';\n"
                "const riskSignals = item.sender_risk_signals || [];\n\n"
                "return [{ json: {\n"
                "  sender: (ni.raw_meta && ni.raw_meta.sender) || 'unknown',\n"
                "  subject: ni.subject || '(no subject)',\n"
                "  date: ni.date || null,\n"
                "  email_account: ni.email_account_id || 'unknown',\n"
                "  risk_level: riskLevel,\n"
                "  risk_signals: riskSignals.join(', ') || 'none',\n"
                "  preview: (ni.raw_text || '').substring(0, 300)\n"
                "} }];"
            )
        },
        "id": node_id + "_log",
        "name": "Log: Quarantine",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": pos,
    }


def make_tg_quarantine(flow_label, pos, node_id):
    text_expr = (
        "={{ JSON.stringify({"
        " chat_id: $env.TELEGRAM_CHAT_ID,"
        " parse_mode: 'HTML',"
        " text: ["
        " '\\u{1F6AB} <b>Quarantine [" + flow_label + "]</b>',"
        " '',"
        " '\\u{1F4E7} ' + ($json.sender || '\\u2014'),"
        " '\\u{1F4CB} ' + ($json.subject || '\\u2014'),"
        " ($json.date ? '\\u{1F4C5} ' + String($json.date).substring(0,10) : null),"
        " '\\u26A0\\uFE0F \\u0420\\u0438\\u0441\\u043a: <code>' + ($json.risk_level || '?') + '</code>',"
        " '\\u{1F50D} \\u0421\\u0438\\u0433\\u043d\\u0430\\u043b\\u044b: <code>' + ($json.risk_signals || 'none') + '</code>',"
        " '',"
        " '<i>' + String($json.preview || '').substring(0,200) + '</i>'"
        " ].filter(Boolean).join('\\n')"
        "}) }}"
    )
    return {
        "parameters": {
            "method": "POST",
            "url": "=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage",
            "sendBody": True,
            "contentType": "raw",
            "rawContentType": "application/json",
            "body": text_expr,
            "options": {"timeout": 10000},
        },
        "id": node_id + "_tg",
        "name": "Telegram: Quarantine Alert",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [pos[0] + 240, pos[1]],
        "onError": "continueRegularOutput",
    }


def make_log_injection(pos, node_id):
    return {
        "parameters": {
            "jsCode": (
                "const item = $input.item.json;\n"
                "const ni = item.normalized_input || {};\n\n"
                "return [{ json: {\n"
                "  sender: (ni.raw_meta && ni.raw_meta.sender) || 'unknown',\n"
                "  subject: ni.subject || '(no subject)',\n"
                "  date: ni.date || null,\n"
                "  preview: (ni.raw_text || '').substring(0, 300)\n"
                "} }];"
            )
        },
        "id": node_id + "_inj_log",
        "name": "Log: Injection Detected",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": pos,
    }


def make_tg_injection(flow_label, pos, node_id):
    text_expr = (
        "={{ JSON.stringify({"
        " chat_id: $env.TELEGRAM_CHAT_ID,"
        " parse_mode: 'HTML',"
        " text: ["
        " '\\u{1F6E1}\\uFE0F <b>Injection Detected [" + flow_label + "]</b>',"
        " '',"
        " '\\u{1F4E7} ' + ($json.sender || '\\u2014'),"
        " '\\u{1F4CB} ' + ($json.subject || '\\u2014'),"
        " ($json.date ? '\\u{1F4C5} ' + String($json.date).substring(0,10) : null),"
        " '',"
        " '<i>' + String($json.preview || '').substring(0,200) + '</i>'"
        " ].filter(Boolean).join('\\n')"
        "}) }}"
    )
    return {
        "parameters": {
            "method": "POST",
            "url": "=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage",
            "sendBody": True,
            "contentType": "raw",
            "rawContentType": "application/json",
            "body": text_expr,
            "options": {"timeout": 10000},
        },
        "id": node_id + "_inj_tg",
        "name": "Telegram: Injection Alert",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [pos[0] + 240, pos[1]],
        "onError": "continueRegularOutput",
    }


# ---------- Email flows ----------

email_flows = [
    ("gmail-flow-api.json", "Gmail", "gmail"),
    ("mailde-flow-api.json", "mail.de", "mailde"),
]

for fname, label, nid in email_flows:
    path = os.path.join(N8N, fname)
    d = load_json(path)
    nodes = d["nodes"]
    conns = d["connections"]

    # Capture positions before removal
    q_pos = get_pos(nodes, "Quarantined: Stop", [1320, 520])
    inj_pos = get_pos(nodes, "Injection Detected: Stop", [q_pos[0] + 480, q_pos[1]])

    # Dead-end nodes to remove (all categories)
    dead_names = {
        "Quarantined: Stop",
        "Injection Detected: Stop",
        "Not Job Related: Stop",
        "No Operation, do nothing",
        "No Operation, do nothing2",
    }

    # Renames: old dead-end → first replacement node
    renames = {
        "Quarantined: Stop": "Log: Quarantine",
        "Injection Detected: Stop": "Log: Injection Detected",
    }

    # Remove dead nodes
    nodes = remove_nodes_by_name(nodes, dead_names)

    # Add replacement nodes
    nodes.append(make_log_quarantine(label, q_pos, nid + "_q"))
    nodes.append(make_tg_quarantine(label, [q_pos[0] + 240, q_pos[1]], nid + "_q"))
    nodes.append(make_log_injection(inj_pos, nid + "_inj"))
    nodes.append(make_tg_injection(label, [inj_pos[0] + 240, inj_pos[1]], nid + "_inj"))

    # Fix connections: renames for quarantine/injection, drop the rest
    remaining_dead = dead_names - set(renames.keys())
    conns = fix_connections(conns, remaining_dead, renames)

    # Add chain connections for new nodes
    conns["Log: Quarantine"] = {
        "main": [[{"node": "Telegram: Quarantine Alert", "type": "main", "index": 0}]]
    }
    conns["Log: Injection Detected"] = {
        "main": [[{"node": "Telegram: Injection Alert", "type": "main", "index": 0}]]
    }

    d["nodes"] = nodes
    d["connections"] = conns
    save_json(path, d)
    print(f"[OK] {label} — {fname}")

# ---------- Non-email flows ----------

non_email_flows = [
    (
        "firecrawl-flow-api.json",
        "Firecrawl",
        {"Not Job Related: Stop", "Scrape Failed: Stop", "Already Fresh: Skip"},
    ),
    (
        "gewerbe-flow-api.json",
        "Gewerbe",
        {"Not Job Related: Stop", "Scrape Failed: Stop", "Already Fresh: Skip"},
    ),
    (
        "job-apis-flow-api.json",
        "Job APIs",
        {"Not Job Related: Stop", "Already Processed: Skip"},
    ),
    (
        "corporate-flow-import.json",
        "Corporate",
        {"Not Job Related: Stop", "No Interview Date: Stop"},
    ),
]

for fname, label, dead in non_email_flows:
    path = os.path.join(N8N, fname)
    d = load_json(path)
    nodes = remove_nodes_by_name(d["nodes"], dead)
    conns = fix_connections(d["connections"], dead)
    d["nodes"] = nodes
    d["connections"] = conns
    save_json(path, d)
    print(f"[OK] {label} — {fname}")

print("\nAll flows fixed.")
