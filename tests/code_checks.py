"""Check runtime anchors against independent read-only capture windows."""
import json,re

def run(source,root):
    fixture=json.loads((root/'tests/fixtures/code_windows_build25480438.json').read_text())
    windows=[(int(w['rva'],16),bytes.fromhex(w['hex'])) for w in fixture['windows']]
    def actual(rva,length):
        for start,data in windows:
            if start<=rva and rva+length<=start+len(data):return data[rva-start:rva-start+length]
        raise AssertionError(f'No independent code window at {rva:#x}')
    def mismatches(text):
        anchors=re.findall(rb"\{(0x[0-9a-f]+),'([0-9a-f]+)'\}",text)
        assert len(anchors)>=11
        return [int(r,16) for r,h in anchors if actual(int(r,16),len(h)//2)!=bytes.fromhex(h.decode())]
    assert not mismatches(source),f'Anchors differ from independent capture: {mismatches(source)}'
    # Reproduce the exact shipped regression without manufacturing its bytes
    # in the mock module. The old expectation joins two non-adjacent instructions.
    broken=source.replace(b"{0x89f1a6,'f3440f1045ac'}",b"{0x89f1a6,'f3440f1045acf3440f5905a274b201'}")
    assert broken!=source and 0x89f1a6 in mismatches(broken)
    name='independent captured code windows match runtime anchors and reject the v0.5.4 concatenated-anchor regression'
    print('PASS',name)
    return [name]
