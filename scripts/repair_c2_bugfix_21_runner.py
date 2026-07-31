from pathlib import Path

path = Path('scripts/apply_c2_bugfix_21.py')
text = path.read_text(encoding='utf-8')
old = '''text = replace_once(
    text,
    '      let buf = state.buffers.get(response_id);\\n'
    '      if (!buf) {\\n',
    '      let buf = state.buffers.get(response_id);\\n'
    '      if (buf && !shouldApplyLifecycle(buf.state, "connecting")) return state;\\n'
    '      if (!buf) {\\n',
    'stream reducer connecting monotonic',
)
'''
new = '''connecting_case = text.find('case "RESPONSE_CONNECTING"')
connecting_idx = text.find(
    '      let buf = state.buffers.get(response_id);\\n      if (!buf) {',
    connecting_case,
)
if connecting_idx == -1:
    raise RuntimeError('stream reducer connecting occurrence missing')
connecting_old = '      let buf = state.buffers.get(response_id);\\n      if (!buf) {'
connecting_new = (
    '      let buf = state.buffers.get(response_id);\\n'
    '      if (buf && !shouldApplyLifecycle(buf.state, "connecting")) return state;\\n'
    '      if (!buf) {'
)
text = text[:connecting_idx] + text[connecting_idx:].replace(
    connecting_old,
    connecting_new,
    1,
)
'''
if text.count(old) != 1:
    raise RuntimeError(f'expected one runner block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('runner repaired')
