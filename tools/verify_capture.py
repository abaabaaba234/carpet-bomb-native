"""Verify the latest bounded live capture before a CarpetBomb field test."""
from pathlib import Path
import json,struct,sys
from build import VERSION
ROOT=Path(__file__).resolve().parents[1];LIVE=ROOT/'research/live'
capture=json.loads((LIVE/'capture.json').read_text())
fixtures={r['name']:r for r in json.loads((ROOT/'tests/fixtures/payload_tables_build25480438.json').read_text())}
DONOR=0x2ea01cb1676aca29;NATIVE=0x6ccb976676ef6cc6
def lookup(raw,key,capacity,stride):
    for step in range(capacity):
        slot=(key%capacity+step)%capacity;offset=slot*stride
        value=struct.unpack_from('<Q',raw,offset)[0]
        if value==key:return raw[offset:offset+stride]
        if value==0:return None
    return None
aliases=[];errors=[];eagle=None
for t in capture['donor_tables']:
    fixture=fixtures.get(t['type'])
    if not fixture:continue
    raw=(LIVE/t['file']).read_bytes();stride=32 if fixture['nrec']==0 else 16
    donor=lookup(raw,DONOR,fixture['nidx'],stride);native=lookup(raw,NATIVE,fixture['nidx'],stride)
    ok=bool(donor and native)
    if ok and t['type']=='EagleComponentData':
        ri=struct.unpack_from('<I',native,8)[0]
        row=raw[320+ri*152:320+(ri+1)*152]
        original=bytes.fromhex(fixture['eagle_data_hex'])
        eagle={'native_record_index':ri,'native_payload_mode':struct.unpack_from('<I',row,16)[0],
               'projectile_type':struct.unpack_from('<I',row,24)[0],
               'approach_height':struct.unpack_from('<f',row,0x3c)[0],
               'original_rows_preserved':raw[320:1992]==original[320:1992],
               'private_allocation_size':t['length']}
        ok=eagle['native_record_index']==11 and eagle['native_payload_mode']==6 and eagle['projectile_type']==170 and eagle['approach_height']==120 and eagle['original_rows_preserved']
    elif ok:ok=native[8:]==donor[8:]
    aliases.append({'component':t['type'],'verified':ok})
    if not ok:errors.append(t['type'])
carrier=(LIVE/'stratagem_33.bin').read_bytes();native=(LIVE/'stratagem_103.bin').read_bytes();donor=(LIVE/'stratagem_18.bin').read_bytes()
grant=struct.unpack_from('<I',carrier,0xc8)[0]==103
identity=struct.unpack_from('<I',native)[0]==103 and capture['stratagems']['103']['payload']==[hex(NATIVE)]
transport=all(native[o:o+n]==donor[o:o+n] for o,n in ((0x70,4),(0x94,4),(0xa8,8),(0xc8,4),(0x104,4)))
rearm=(LIVE/'stratagem_49.bin').read_bytes()
rearm_identity=struct.unpack_from('<I',rearm)[0]==49 and struct.unpack_from('<I',rearm,0x3c)[0]==7
expected_rearm=float(sys.argv[1]) if len(sys.argv)>1 else None
rearm_seconds=capture['stratagems']['49']['cooldown']
rearm_verified=rearm_identity and (expected_rearm is None or rearm_seconds==expected_rearm)
ready=len(aliases)==18 and not errors and grant and identity and transport and rearm_verified
field_report=json.loads((ROOT/'validation/report.json').read_text(encoding='utf-8'))
bombing_verified=(field_report.get('version')==VERSION and field_report.get('in_game_bombing_verified') is True
                  and field_report.get('battlefield_test',{}).get('pid')==capture['pid'])
result={'version':VERSION,'pid':capture['pid'],'native_default_grant_verified':grant,
        'native_identity_and_payload_verified':identity,'personal_eagle_transport_verified':transport,
        'component_aliases':aliases,'eagle':eagle,'uses':capture['stratagems']['103']['uses'],
        'cooldown':capture['stratagems']['103']['cooldown'],'ready_for_field_test':ready,
        'rearm_cooldown':rearm_seconds,'expected_rearm':expected_rearm,
        'shared_eagle_rearm_identity_verified':rearm_identity,
        'configured_rearm_value_verified':rearm_verified if expected_rearm is not None else None,
        'actual_bombing_verified':bombing_verified,'bombing_evidence':'validation/report.json user field report'}
(ROOT/'validation/live_state.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
assert ready,'Do not field-test: payload repair is incomplete.'
