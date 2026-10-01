"""Encode only `return { value = integer }` for the game's LuaJIT 2.1 VM.

This leaf chunk has TDUP and RET1 only, with no calls, child prototypes,
upvalues or FFI constants. Its registers are identical with FR2 on or off.
The target is little endian, stripped, non-FR2, like the v18 bootstrap.
Format: https://github.com/LuaJIT/LuaJIT/blob/v2.1/src/lj_bcdump.h
Opcodes: https://github.com/LuaJIT/LuaJIT/blob/v2.1/src/lj_bc.h
"""
import struct

HEADER = b'\x1bLJ\x02\x02'

def uleb(value):
    assert 0 <= value <= 0xffffffff
    data = bytearray()
    while value >= 128:
        data.append((value & 127) | 128)
        value >>= 7
    data.append(value)
    return bytes(data)

def encode(value):
    assert isinstance(value, int) and -1 <= value <= 1800
    # Prototype: vararg, zero arguments, one register, zero upvalues,
    # one GC constant (template table), zero numbers, two instructions.
    proto = bytes((2, 0, 1, 0, 1, 0, 2))
    proto += struct.pack('<II', 0x00000035, 0x0002004c)
    # KGC_TAB, zero array entries, one hash entry, string "value", KTAB_INT.
    proto += b'\x01\x00\x01\x0avalue\x03' + uleb(value & 0xffffffff)
    return HEADER + uleb(len(proto)) + proto + b'\x00'

def validate_with_lupa(value, blob):
    """Cross-check the 2.1 compiler and execute in both available VM layouts."""
    from lupa import luajit20, luajit21
    assert blob == encode(value)
    vm = luajit21.LuaRuntime(encoding=None)
    dump = vm.eval(b'function(s)return string.dump(assert(loadstring(s)),true)end')
    compiled = dump(('return { value = %d }' % value).encode('ascii'))
    assert compiled[:4] == HEADER[:4] and compiled[4] in (2, 10)
    assert compiled[:4] + b'\x02' + compiled[5:] == blob
    native_blob = blob[:4] + bytes((compiled[4],)) + blob[5:]
    assert vm.execute(native_blob)[b'value'] == value
    # LuaJIT 2.0 on x64 is non-FR2. These two leaf opcodes are the only
    # differences for this exact template, so validate its target layout too.
    old_proto = bytearray(blob)
    old_proto[3] = 1
    assert old_proto[13] == 0x35 and old_proto[17] == 0x4c
    old_proto[13], old_proto[17] = 0x33, 0x48
    assert luajit20.LuaRuntime(encoding=None).execute(bytes(old_proto))[b'value'] == value
