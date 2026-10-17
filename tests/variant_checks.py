"""New payload dependencies, private approach angle and failure ownership."""
import json,struct

def run(Scenario,BASE,ROOT):
    U=lambda x:struct.pack('<I',x)
    F=lambda x:struct.pack('<f',x)
    Q=lambda x:struct.pack('<Q',x)
    def private(s):return int(s.state[b'repair'][b'eagle'][b'table'])+1992
    def direction_and_reload():
        for bomb in (170,192,239,286,141,188):
            s=Scenario({'bomb':bomb,'direction':180})
            try:
                s.tick();assert s.state[b'phase']==b'active'
                row=private(s);assert s.mem.read(row+28,4)==F(180)
                table=next(t for t in s.tables if t['row']['name']=='EagleComponentData')
                assert s.mem.read(row-1992+320,1672)==table['original'][320:]
                original_rows={t:s.r(t,0,400) for t in s.originals}
                writes=len(s.mem.writes)
                s.cfg(f'bomb={bomb}\ndirection=90\n')
                assert s.mem.writes[writes:]==[(row+28,F(90))]
                assert all(s.r(t,0,400)==r for t,r in original_rows.items())
                s.cfg(f'bomb={bomb}\ndirection=180\n')
                for invalid in ('0','1','-90','270','90.5','nan'):
                    s.cfg(f'bomb={bomb}\ndirection={invalid}\n')
                    assert s.state[b'config'][b'direction']==180 and s.mem.read(row+28,4)==F(180)
                s.cfg(f'bomb={bomb}\ndirection=manager\n')
                assert s.mem.read(row+28,4)==F(180)
                s.cfg('enabled=0\n')
                assert s.mem.read(row+28,4)==F(90) and s.mem.read(row+24,4)==U(170)
                assert not any(BASE<=p<BASE+0x4744000 for p,_ in s.mem.writes)
            finally:s.close()
    def direction_failure_ownership():
        for mode in ('partial','external','disable_failure','donor_angle'):
            s=Scenario({'direction':180})
            try:
                if mode=='donor_angle':
                    table=next(t for t in s.tables if t['row']['name']=='EagleComponentData')
                    s.mem.put(table['p']+320+152+28,F(45));s.tick()
                    assert s.state[b'phase']==b'suspended' and s.r(33,0xc8,4)==U(0)
                    continue
                s.tick();row=private(s)
                if mode=='partial':
                    s.mem.fail_address=row+28;s.cfg('direction=90\n')
                    assert s.state[b'phase']==b'suspended' and s.mem.read(row+28,4)==F(90)
                elif mode=='external':
                    s.mem.put(row+28,F(45));s.tick()
                    assert s.state[b'phase']==b'suspended' and s.mem.read(row+28,4)==F(45)
                else:
                    s.mem.fail_address=row+28;s.cfg('enabled=0\n')
                    assert s.state[b'phase']==b'suspended' and s.mem.read(row+28,4)==F(90)
                assert s.r(33,0,400)==s.originals[33]
            finally:s.close()

    def resource_and_bomblet_guards():
        for bomb,t in ((286,65),(141,133),(188,126)):
            for mode in ('late','package','identity','moved','runtime_package'):
                s=Scenario({'bomb':bomb})
                try:
                    slot=BASE+0x37cb600+t*8
                    if mode=='late':
                        s.mem.put(slot,Q(0));s.tick()
                        assert s.state[b'phase']==b'waiting' and not s.mem.allocations and not s.mem.writes
                        s.mem.put(slot,Q(s.address[t]));s.tick()
                        assert s.state[b'phase']==b'active';continue
                    if mode=='package':s.mem.put(s.address[t]+0xa8,Q(1234))
                    if mode=='identity':s.mem.put(s.address[t],U(999))
                    s.tick()
                    if mode in ('moved','runtime_package'):
                        assert s.state[b'phase']==b'active'
                        if mode=='moved':s.mem.put(slot,Q(0x77770000))
                        else:s.mem.put(s.address[t]+0xa8,Q(1234))
                        s.tick()
                    assert s.state[b'phase']==b'suspended' and s.r(33,0,400)==s.originals[33]
                    assert s.r(t,0xa8,8)==(Q(1234) if mode in ('package','runtime_package') else s.originals[t][0xa8:0xb0])
                finally:s.close()
        for stage in ('startup','active'):
            s=Scenario({'bomb':286})
            try:
                if stage=='active':s.tick()
                address,raw=s.projectiles[131];s.mem.put(address+0x90,U(999));s.tick()
                assert s.state[b'phase']==b'suspended' and s.r(33,0,400)==s.originals[33]
            finally:s.close()

    def reference_dependency_chain():
        fixture=json.loads((ROOT/'tests/fixtures/bomb_variants_build25480438.json').read_text())
        projectiles={r['type']:bytes.fromhex(r['record_hex']) for r in json.loads((ROOT/'tests/fixtures/projectiles_build25480438.json').read_text())['records']}
        strats={r['type']:bytes.fromhex(r['record_hex']) for r in json.loads((ROOT/'tests/fixtures/stratagems_build25480438.json').read_text())}
        for row in fixture['variants']:
            deps={tuple(x) for x in row['dependencies']};pid=row['projectile']
            assert strats[row['stratagem_type']][0xa8:0xb0]==Q(int(row['package'],16))
            assert ('e0a48d0be9a7453f','4e401cc877093220') in deps
            assert ('e0a48d0be9a7453f','71e52f800636b336') in deps
            assert any(t=='535a7bd3e650d799' for t,_ in deps)
            explosions={r['id']:r for r in row['explosions']}
            projectile=projectiles[pid]
            for offset in (0x90,0x9c):
                eid=struct.unpack_from('<I',projectile,offset)[0]
                if eid:assert eid in explosions
            for explosion in explosions.values():
                assert ('a8193123526fad64',explosion['particle_hash']) in deps
            if pid==286:
                raw=bytes.fromhex(explosions[417]['record_hex'])
                assert struct.unpack_from('<2I',raw,0x50)==(8,131)
                assert struct.unpack_from('<I',projectiles[131],0x90)[0]==162
            if pid==188:
                assert explosions[331]['persistent_status_template_id']==16
                assert explosions[331]['status_duration_seconds']==15
            if pid==141:
                assert struct.unpack_from('<I',bytes.fromhex(explosions[359]['record_hex']),0x60)[0]==4

    passed=[]
    for name,fn in [
        ('six payloads: private left/right and front/back angles, reload/migration and disable restoration',direction_and_reload),
        ('approach angle: partial-write rollback, disable failure, external owner and donor guard',direction_failure_ownership),
        ('selected resource packages: late loading, changed IDs/addresses/packages and cluster secondary guard',resource_and_bomblet_guards),
        ('current package references: plane/bomb/audio/particles, cluster bomblets, napalm fire and gas status chain',reference_dependency_chain)]:
        fn();passed.append(name);print('PASS',name)
    return passed
